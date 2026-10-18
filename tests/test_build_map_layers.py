"""Tests for scripts/build_map_layers.py -- built on tiny purpose-made GeoPackages."""
import json
import sqlite3
import struct

import pytest

pytest.importorskip("shapely")    # the build script needs it; the apps do not

import shapely  # noqa: E402
import shapely.wkb  # noqa: E402
from shapely.geometry import LineString, MultiPolygon, Polygon, box  # noqa: E402

from scripts import build_map_layers as bm  # noqa: E402


def blob(geom, envelope=0, empty=False):
    """GeoPackage geometry blob: header (optionally with an envelope) + WKB."""
    flags = 1 | (envelope << 1) | (0x10 if empty else 0)
    head = b"GP" + bytes([0, flags]) + struct.pack("<i", 27700)
    if envelope:
        n = {1: 4, 2: 6, 3: 6, 4: 8}[envelope]
        head += struct.pack("<%dd" % n, *([0.0] * n))
    return head + shapely.wkb.dumps(geom)


def make_gpkg(path, tables, srs=27700):
    """tables: {name: (columns sql or '', [(geom, *extra)])}; extra = type [, Name]."""
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE gpkg_contents (table_name TEXT, data_type TEXT)")
    conn.execute("CREATE TABLE gpkg_geometry_columns (table_name TEXT, column_name TEXT, srs_id INT)")
    for name, (cols, rows) in tables.items():
        conn.execute("INSERT INTO gpkg_contents VALUES (?, 'features')", (name,))
        conn.execute("INSERT INTO gpkg_geometry_columns VALUES (?, 'shape', ?)", (name, srs))
        conn.execute(f"CREATE TABLE {name} (id INTEGER PRIMARY KEY, {cols}shape BLOB)")
        for r in rows:
            extra = [v for v in r[1:]]
            marks = ",".join("?" * (len(extra) + 1))
            names = ("type, " if cols.startswith("type") else "") + ("Name, " if "Name" in cols else "")
            conn.execute(f"INSERT INTO {name} ({names}shape) VALUES ({marks})", extra + [blob(r[0])])
    conn.commit()
    conn.close()


SQUARE = box(0, 0, 100000, 100000)
WITH_HOLES = Polygon(SQUARE.exterior.coords, [box(10000, 10000, 30000, 30000).exterior.coords,
                                              box(50000, 50000, 50500, 50500).exterior.coords])


@pytest.fixture
def src(tmp_path):
    d = tmp_path / "OS data"
    d.mkdir()
    big = box(0, 0, 1000, 1000)                       # 1e6 m2: kept at both lods
    small = box(0, 0, 50, 50)                         # 2500 m2: under both min areas
    mid = box(0, 0, 200, 200)                         # 40000 m2: kept at county only
    t = "type TEXT, "
    make_gpkg(d / "OS_Open_Zoomstack.gpkg", {
        "land": ("", [(WITH_HOLES,)]),
        "woodland": (t, [(big, "National"), (mid, "Regional"), (small, "Regional")]),
        "surfacewater": (t, [(big, "National"), (mid, "Regional")]),
        "urban_areas": (t, [(big, "National"), (mid, "Regional")]),
        "waterlines": (t, [(LineString([(0.4, 0.4), (0.2, 0.3), (5000.6, 5000.4), (9000, 9000)]), "National"),
                           (LineString([(0, 0), (100, 100)]), "Regional")]),
        "roads_national": (t, [(LineString([(0, 0), (9000, 0)]), "Motorway")]),
        "roads_regional": (t, [(LineString([(0, 0), (0, 9000)]), "A Road"),
                               (LineString([(0, 0), (500, 500)]), "B Road")]),
    })
    make_gpkg(d / "bdline_test.gpkg", {
        "district_borough_unitary": ("Name TEXT, ", [(MultiPolygon([box(0, 0, 1000, 1000), box(5000, 5000, 6000, 6000)]),
                                                      "Cherwell")])})
    return d


def run(src, out, *args):
    return bm.main(["--source", str(src), "--out", str(out), *args])


def load(out, name):
    return json.loads((out / name).read_text(encoding="utf-8"))


def test_decode_with_and_without_envelope():
    g = box(1, 2, 3, 4)
    assert bm.decode_gpkg(blob(g, 0)).equals(g)
    for env in (1, 2, 3, 4):
        assert bm.decode_gpkg(blob(g, env)).equals(g)
    assert bm.decode_gpkg(blob(g, empty=True)) is None
    with pytest.raises(ValueError):
        bm.decode_gpkg(b"XX" + bytes(20))


def test_dry_run_writes_nothing(src, tmp_path, capsys):
    out = tmp_path / "out"
    assert run(src, out) == 0
    text = capsys.readouterr().out
    assert "woodland_county: table woodland" in text and "Nothing has been changed" in text
    assert not out.exists()


def test_missing_source_prints_download_pages(tmp_path, capsys):
    assert run(tmp_path / "nothing", tmp_path / "out", "--apply") == 1
    text = capsys.readouterr().out
    assert bm.ZOOMSTACK_URL in text and bm.BOUNDARY_URL in text


def test_apply_format_and_type_filtering(src, tmp_path):
    out = tmp_path / "out"
    assert run(src, out, "--apply") == 0
    assert sorted(p.name for p in out.iterdir()) == sorted(
        f"{k}_{lod}.json" for k in bm.LAYERS for lod in bm.LODS)
    wgb, wco = load(out, "woodland_gb.json"), load(out, "woodland_county.json")
    assert (wgb["layer"], wgb["lod"], wgb["kind"]) == ("woodland", "gb", "polygon")
    assert wgb["tolerance_m"] == 250 and wco["min_area_m2"] == 10000
    assert wgb["attribution"].startswith("Contains OS data") and "woodland" in wgb["source"]
    assert len(wgb["features"]) == 1 and len(wco["features"]) == 1      # National / Regional, small dropped
    assert wgb["features"][0]["bbox"] == [0, 0, 1000, 1000]
    assert wco["features"][0]["bbox"] == [0, 0, 200, 200]
    rivers = load(out, "rivers_gb.json")["features"][0]
    assert rivers["line"][0] == [0, 0] and rivers["line"][-1] == [9000, 9000]   # rounded, duplicate dropped
    assert all(isinstance(v, int) for p in rivers["line"] for v in p)
    assert all(isinstance(v, int) for v in rivers["bbox"])
    assert len(load(out, "roads_gb.json")["features"]) == 1               # Motorway only
    assert len(load(out, "roads_county.json")["features"]) == 2           # + A Road, no B Road


def test_holes_kept_or_dropped_by_min_area(src, tmp_path):
    out = tmp_path / "out"
    run(src, out, "--apply", "--only", "land")
    assert len(load(out, "land_gb.json")["features"][0]["rings"]) == 2        # 500x500 hole dropped
    assert len(load(out, "land_county.json")["features"][0]["rings"]) == 3    # both holes kept


def test_districts_have_names_and_split_multipolygon(src, tmp_path):
    out = tmp_path / "out"
    run(src, out, "--apply", "--only", "districts")
    feats = load(out, "districts_county.json")["features"]
    assert len(feats) == 2 and {f["name"] for f in feats} == {"Cherwell"}


def test_only_limits_layers(src, tmp_path):
    out = tmp_path / "out"
    run(src, out, "--apply", "--only", "woodland,rivers")
    assert sorted(p.name for p in out.iterdir()) == [
        "rivers_county.json", "rivers_gb.json", "woodland_county.json", "woodland_gb.json"]
    assert not list(out.glob("*.tmp"))
    assert run(src, out, "--only", "nonsense") == 1


def test_wrong_srs_refused(tmp_path, capsys):
    d = tmp_path / "bad"
    d.mkdir()
    make_gpkg(d / "OS_Open_Zoomstack.gpkg", {"woodland": ("type TEXT, ", [(box(0, 0, 9, 9), "National")])},
              srs=4326)
    out = tmp_path / "out"
    assert run(d, out, "--apply", "--only", "woodland") == 1
    assert "not 27700" in capsys.readouterr().out
    assert not list(out.glob("*.json"))


def test_check_output(src, tmp_path, capsys):
    out = tmp_path / "out"
    run(src, out, "--apply", "--only", "woodland")
    capsys.readouterr()
    assert run(src, out, "--check") == 0
    text = capsys.readouterr().out
    assert "woodland_gb.json" in text and "1 features, 5 points" in text and "READ ONLY" in text


def test_polygons_are_oriented_and_land_pieces_merged():
    """17 Oct: outer rings anticlockwise, holes clockwise (the map fills with WindingFill);
    two touching land pieces become one shape, so their shared edge is not drawn as coast."""
    from shapely.geometry import LinearRing
    sq = Polygon([(0, 0), (0, 2000), (2000, 2000), (2000, 0)],      # clockwise outer
                 [[(500, 500), (1500, 500), (1500, 1500), (500, 1500)]])   # anticlockwise hole
    f = bm.to_features(sq, "polygon", 1, 0)[0]
    assert LinearRing(f["rings"][0]).is_ccw and not LinearRing(f["rings"][1]).is_ccw
    merged = bm.to_features(shapely.unary_union([box(0, 0, 1000, 1000), box(1000, 0, 2000, 1000)]),
                            "polygon", 1, 0)
    assert len(merged) == 1 and len(merged[0]["rings"]) == 1


def test_lines_are_joined_per_type_before_simplifying(tmp_path):
    """Roads cut into many segments become one line per run, grouped by the source type;
    a different type never joins, and each feature carries its type as "t"."""
    d = tmp_path / "joined"
    d.mkdir()
    seg = [(LineString([(i * 1000, 0), ((i + 1) * 1000, 0)]), "Motorway") for i in range(40)]
    seg += [(LineString([(i * 1000, 5000), ((i + 1) * 1000, 5000)]), "Primary") for i in range(10)]
    seg += [(LineString([(40000, 0), (40000, 3000)]), "Primary")]       # touches nothing else
    make_gpkg(d / "OS_Open_Zoomstack.gpkg", {"woodland": ("type TEXT, ", []),      # the probe table
                                                   "roads_national": ("type TEXT, ", seg),
                                                   "roads_regional": ("type TEXT, ", [])})
    out = tmp_path / "out"
    assert run(d, out, "--apply", "--only", "roads") == 0
    feats = load(out, "roads_gb.json")["features"]
    assert len(seg) == 51 and len(feats) == 3
    by_type = sorted((f["t"], len(f["line"])) for f in feats)
    assert [t for t, _n in by_type] == ["Motorway", "Primary", "Primary"]
    motorway = next(f for f in feats if f["t"] == "Motorway")
    assert motorway["bbox"] == [0, 0, 40000, 0] and motorway["line"][0] in ([0, 0], [40000, 0])
    assert bm.merge_lines([]) is None
