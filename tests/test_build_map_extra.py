"""18 Oct 2026: the build side of the six extra map layers (place names, railways, national parks,
foreshore, parks and green space, relief) and --describe. Tiny purpose-made GeoPackages and a tiny
fake OS Terrain 50 zip; nothing from Wil's data."""
import io
import json
import zipfile

import pytest

pytest.importorskip("shapely")

import numpy as np  # noqa: E402
from shapely.geometry import LineString, Point, box  # noqa: E402

from scripts import build_map_layers as bm  # noqa: E402
from scripts import build_map_relief as br  # noqa: E402
from tests.test_build_map_layers import load, make_gpkg, run  # noqa: E402,F401

BIG = box(0, 0, 1000, 1000)
PLACES = [(Point(450000, 200000), "City", "Oxford"),
          (Point(445000, 240000), "Town", "Banbury"),
          (Point(445200, 240300), "Town", "Banbury"),                 # a repeat in the same km
          (Point(447000, 235000), "Village", "Adderbury"),
          (Point(440000, 230000), "Hamlet", "Nethercote"),
          (Point(451000, 201000), "Suburban Area", "Headington"),
          (Point(450100, 200100), "City", ""),                         # no name: dropped
          (Point(450200, 200200), "Named Road", "A34")]                # not a place: dropped


def zoomstack(d, names_cols, names_rows, extra=None):
    t = "type TEXT, "
    tables = {"woodland": (t, []),                                      # the probe table
              "names": (names_cols, names_rows)}
    tables.update(extra or {})
    make_gpkg(d / "OS_Open_Zoomstack.gpkg", tables)


@pytest.fixture
def d(tmp_path):
    p = tmp_path / "OS data"
    p.mkdir()
    return p


def test_place_names_gb_holds_the_cities_county_the_rest(d, tmp_path):
    zoomstack(d, "type TEXT, name1 TEXT, ", PLACES)
    out = tmp_path / "out"
    assert run(d, out, "--apply", "--only", "names") == 0
    gb, co = load(out, "names_gb.json"), load(out, "names_county.json")
    assert (gb["layer"], gb["kind"], gb["lod"]) == ("names", "point", "gb")
    assert [f["n"] for f in gb["features"]] == ["Oxford"]
    assert gb["features"][0] == {"bbox": [450000, 200000, 450000, 200000], "pt": [450000, 200000],
                                 "n": "Oxford", "t": "City"}
    assert [(f["t"], f["n"]) for f in co["features"]] == [
        ("Town", "Banbury"), ("Village", "Adderbury"), ("Suburban Area", "Headington"),
        ("Hamlet", "Nethercote")]          # by class, then name; the repeat, the road, the unnamed dropped
    assert all(isinstance(v, int) for f in co["features"] for v in f["pt"] + f["bbox"])
    assert gb["attribution"].startswith("Contains OS data") and "table names" in gb["source"]


def test_place_names_find_the_columns_they_need(d, tmp_path):
    """Different column names: the text in `distname`, and `type` holds a code while the
    classes are in `local_type` (the column that holds them is the one used)."""
    rows = [(g, "populatedPlace", t, n) for g, t, n in PLACES]
    zoomstack(d, "type TEXT, local_type TEXT, distname TEXT, ", rows)
    out = tmp_path / "out"
    assert run(d, out, "--apply", "--only", "names") == 0
    assert [f["n"] for f in load(out, "names_gb.json")["features"]] == ["Oxford"]
    assert len(load(out, "names_county.json")["features"]) == 4
    d2 = d.parent / "other"
    d2.mkdir()
    zoomstack(d2, "class TEXT, text TEXT, ", [(g, t, n) for g, t, n in PLACES])
    out2 = tmp_path / "out2"
    assert run(d2, out2, "--apply", "--only", "names") == 0
    assert len(load(out2, "names_county.json")["features"]) == 4


def test_place_names_without_any_class_column_say_so(d, tmp_path, capsys):
    zoomstack(d, "type TEXT, name1 TEXT, ", [(Point(1, 1), "Mountain", "Ben Nevis")])
    assert run(d, tmp_path / "out", "--apply", "--only", "names") == 1
    assert "run --describe names" in capsys.readouterr().out


def test_other_new_layers_with_and_without_scale_versions(d, tmp_path):
    """national_parks has National / Regional rows (filtered as woodland is); foreshore has a
    different type column name and no scale values (every row at both levels); rail and
    greenspace likewise."""
    near = box(0, 0, 2000, 2000)
    zoomstack(d, "type TEXT, name1 TEXT, ", [], {
        "national_parks": ("type TEXT, ", [(BIG, "National"), (near, "Regional")]),
        "foreshore": ("class TEXT, ", [(BIG, "Foreshore"), (near, "Foreshore")]),
        "greenspace": ("", [(BIG,), (near,)]),
        "rail": ("type TEXT, ", [(LineString([(0, 0), (9000, 0)]), "Railway"),
                                 (LineString([(0, 5000), (9000, 5000)]), "Railway")])})
    out = tmp_path / "out"
    assert run(d, out, "--apply", "--only", "national_parks,foreshore,greenspace,rail") == 0
    assert len(load(out, "national_parks_gb.json")["features"]) == 1
    assert load(out, "national_parks_county.json")["features"][0]["bbox"] == [0, 0, 2000, 2000]
    assert len(load(out, "foreshore_gb.json")["features"]) == 2
    assert len(load(out, "greenspace_county.json")["features"]) == 2
    rail = load(out, "rail_gb.json")
    assert rail["kind"] == "line" and len(rail["features"]) == 2 and rail["features"][0]["t"] == "Railway"


def test_describe_prints_columns_rows_geometry_and_common_values(d, tmp_path, capsys):
    zoomstack(d, "type TEXT, name1 TEXT, ", PLACES)
    out = tmp_path / "out"
    assert run(d, out, "--describe", "names") == 0
    text = capsys.readouterr().out
    assert "rows: 8" in text and "name1 TEXT" in text and "shape" in text
    assert "most common values of type" in text
    assert "         2  City" in text and "         2  Town" in text and "         1  Hamlet" in text
    assert "POINT" in text and "READ ONLY" in text and "Nothing has been changed" in text
    assert not out.exists()
    assert run(d, out, "--describe", "names,nonsense") == 1
    assert "nonsense: not found" in capsys.readouterr().out


# ---------------------------------------------------------------- relief

def asc(xll, yll, fn, n=200, cell=50, nodata=-9999):
    head = (f"ncols {n}\nnrows {n}\nxllcorner {xll}\nyllcorner {yll}\ncellsize {cell}\n"
            f"NODATA_value {nodata}\n")
    rows = "\n".join(" ".join(str(fn(r, c)) for c in range(n)) for r in range(n))
    return (head + rows + "\n").encode("ascii")


def fake_terrain(path):
    """terr50_gagg_gb.zip > data/su.zip > su21.asc (high to the west, falling 10 m a cell, with
    a block of no data) and su31.asc (flat, 100 m)."""
    slope = asc(420000, 210000, lambda r, c: -9999 if (r < 20 and c < 20) else 4000 - 10 * c)
    flat = asc(430000, 210000, lambda r, c: 100)
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("su21.asc", slope)
        z.writestr("su31.asc", flat)
        z.writestr("readme.txt", "not a tile")
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("data/su.zip", inner.getvalue())


def qimage(path):
    from PySide6.QtGui import QImage
    img = QImage(str(path))
    assert not img.isNull()
    return img


def test_relief_is_built_from_the_zip_of_zips_without_extracting(tmp_path, monkeypatch):
    src, out, cwd = tmp_path / "OS data", tmp_path / "out", tmp_path / "cwd"
    for p in (src, cwd):
        p.mkdir()
    fake_terrain(src / "terr50_gagg_gb.zip")
    before = sorted(p.name for p in tmp_path.rglob("*"))

    def no_extract(*a, **k):
        raise AssertionError("a zip member was extracted to disk")
    monkeypatch.setattr(zipfile.ZipFile, "extract", no_extract)
    monkeypatch.setattr(zipfile.ZipFile, "extractall", no_extract)
    monkeypatch.chdir(cwd)
    assert bm.main(["--source", str(src), "--out", str(out), "--apply", "--only", "relief"]) == 0
    assert sorted(p.name for p in out.iterdir()) == ["relief_gb.json", "relief_gb.png"]
    new = sorted(p.name for p in tmp_path.rglob("*") if p.name not in before)
    assert new == ["out", "relief_gb.json", "relief_gb.png"] and not list(cwd.iterdir())
    doc = json.loads((out / "relief_gb.json").read_text(encoding="utf-8"))
    assert doc["extent"] == [420000, 210000, 440000, 220000] and doc["cell_m"] == 250
    assert (doc["width"], doc["height"]) == (80, 40) and doc["kind"] == "image"
    assert doc["attribution"].startswith("Contains OS data") and "Terrain 50" in doc["source"]
    img = qimage(out / "relief_gb.png")
    assert (img.width(), img.height()) == (80, 40) and img.hasAlphaChannel()
    assert img.pixelColor(2, 2).alpha() == 0                   # the no-data block is clear
    flat, hill = img.pixelColor(60, 20), img.pixelColor(20, 20)
    assert flat.alpha() == 255 and flat.red() == 255            # level ground is white
    assert hill.alpha() == 255 and hill.red() < 200             # a slope away from the light is darker


def test_relief_from_a_folder_of_asc_files_and_missing_source(tmp_path, capsys):
    src = tmp_path / "terr"
    src.mkdir()
    (src / "su21.asc").write_bytes(asc(420000, 210000, lambda r, c: 50 + r))
    assert br.find_terrain(tmp_path) == src
    out = tmp_path / "out"
    assert br.build_relief(tmp_path, out, "x", True) == 0 and (out / "relief_gb.png").is_file()
    empty = tmp_path / "empty"
    empty.mkdir()
    assert br.build_relief(empty, out, "x", True, explicit=False) == 0
    assert "Relief skipped" in capsys.readouterr().out
    assert br.build_relief(empty, out, "x", True, explicit=True) == 1
    assert br.TERRAIN_URL in capsys.readouterr().out


def test_dry_run_writes_no_relief(tmp_path):
    src = tmp_path / "OS data"
    src.mkdir()
    fake_terrain(src / "terr50_gagg_gb.zip")
    out = tmp_path / "out"
    assert bm.main(["--source", str(src), "--out", str(out), "--only", "relief"]) == 0
    assert not out.exists()


def test_hillshade_is_lit_from_the_north_west():
    r, c = np.mgrid[0:20, 0:20].astype(np.float32)
    facing_nw, facing_se = 20 * (r + c) + 10, 500 - 20 * (r + c)    # falls to the NW / to the SE
    lit, _a = br.hillshade(facing_nw)
    dark, alpha = br.hillshade(facing_se)
    assert lit[10, 10] == 255 and dark[10, 10] < 200 and alpha[10, 10] == 255
    flat, a2 = br.hillshade(np.full((5, 5), 7.0, np.float32))
    assert (flat == 255).all() and (a2 == 255).all()
    _g, sea = br.hillshade(np.zeros((5, 5), np.float32))
    assert (sea == 0).all()
