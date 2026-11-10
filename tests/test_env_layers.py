"""25 Oct 2026: the Environment map layers (shared/maps/env_registry.py, value_grid.py, layers.py,
identify.py) and scripts/build_env_layers.py. Small made-up GeoPackages, shapefiles and grids in
tmp_path; nothing from Wil's data."""
# ruff: noqa: F811  (pytest fixtures imported from test_map_layers_r11)
import json
import os
import struct

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("shapely")
import numpy as np  # noqa: E402
from shapely.geometry import box  # noqa: E402

from scripts import build_env_layers as be  # noqa: E402
from shared.maps import env_registry as env, layers, value_grid  # noqa: E402
from tests.test_build_map_layers import make_gpkg  # noqa: E402
from tests.test_map_layers_r11 import _map, _pixel, qapp, settings_sandbox  # noqa: E402,F401

AREA = box(10000, 10000, 30000, 30000)


def _src(tmp_path, tables_by_folder):
    """A made-up --source folder: {"SSSI England/sssi.gpkg": (table, cols, rows)}."""
    root = tmp_path / "Environment data"
    for rel, (table, cols, rows) in tables_by_folder.items():
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        make_gpkg(f, {table: (cols, rows)})
    return root


def _run(capsys, *args):
    code = be.main(list(args))
    return code, capsys.readouterr().out


# ---------------------------------------------------------------- registry

def test_registry_entries_all_off_by_default_and_grouped():
    keys = [e.key for e in env.ENV_LAYERS]
    assert len(keys) == len(set(keys)) == 21
    for k in keys:
        tg = next(t for t in layers.TOGGLES if t.key == k)
        assert tg.default is False and tg.group == "Environment" and tg.section and tg.credits
        assert any(lay.key == k and lay.toggle == k for lay in layers.LAYERS)
    assert layers.defaults() == {"water"}
    assert {lay.kind for lay in layers.LAYERS if lay.key.startswith("haduk")} == {"grid"}
    names = [lay.key for lay in layers.LAYERS]
    assert names.index("geology_bedrock") < names.index("relief") < names.index("woodland") \
        < names.index("ancient_woodland") < names.index("national_parks") < names.index("sssi")


def test_soilscapes_hidden_unless_the_setting(qapp, settings_sandbox):
    assert "soilscapes" not in {t.key for t in layers.visible_toggles()}
    from PySide6.QtCore import QSettings
    from src.views.mapping.display_bar import MapDisplayBar
    assert "soilscapes" not in MapDisplayBar().layer_actions
    QSettings().setValue(env.SOILSCAPES_SETTING, True)
    assert "soilscapes" in {t.key for t in layers.visible_toggles()}
    bar = MapDisplayBar()
    assert "soilscapes" in bar.layer_actions and "sssi" in bar.layer_actions
    win = bar.layers_window()           # the Layers window replaced the Environment sub-menu
    assert win.group_titles[0] == "Base map" and env.DESIG in win.group_titles
    assert "Sites of Special Scientific Interest (SSSI)" in [cb.text() for cb in win.checks.values()]


def test_credits_for():
    c = layers.credits_for(["sssi", "haduk_rain", "haduk_sun", "woodland"])
    assert c == [env.C_MET, env.C_NE, env.C_NRW, env.C_NS]      # the registry's order, each once
    assert layers.credits_for(["woodland", "land"]) == [] and layers.credits_for(None) == []
    assert layers.credits_for(["geology_bedrock", "soil_pm"]) == [env.C_BGS]
    assert "Hollis et al. 2018" in env.C_MET and "UKRI" in env.C_BGS


# ---------------------------------------------------------------- build from GeoPackage

def test_dry_run_writes_nothing_and_says_so(tmp_path, capsys):
    src = _src(tmp_path, {"SSSI England/sssi.gpkg": ("sites", "SSSI_NAME TEXT, ", [(AREA, "Ashen Bank")])})
    out = tmp_path / "out"
    code, text = _run(capsys, "--source", str(src), "--out", str(out), "--only", "sssi")
    assert code == 0 and "Nothing has been changed" in text and "1 features" in text
    assert "name field SSSI_NAME" in text and "Wales: not found" in text
    assert not out.exists()


def test_designated_sites_built_with_name_and_type(tmp_path, capsys):
    src = _src(tmp_path, {"SSSI England/sssi.gpkg": ("sites", "SSSI_NAME TEXT, ", [(AREA, "Ashen Bank")])})
    out = tmp_path / "out"
    code, text = _run(capsys, "--source", str(src), "--out", str(out), "--only", "sssi", "--apply")
    assert code == 0 and "Done." in text
    doc = json.loads((out / "sssi_county.json").read_text(encoding="utf-8"))
    assert (out / "sssi_gb.json").is_file() and doc["layer"] == "sssi" and "Natural England" in doc["attribution"]
    assert len(doc["features"]) == 1
    f = doc["features"][0]
    assert f["n"] == "Ashen Bank" and f["t"] == "SSSI" and f["bbox"] == [10000, 10000, 30000, 30000]


def test_only_builds_just_that_layer(tmp_path, capsys):
    src = _src(tmp_path, {
        "SSSI England/sssi.gpkg": ("sites", "SSSI_NAME TEXT, ", [(AREA, "Ashen Bank")]),
        "SAC England/sac.gpkg": ("sac", "SAC_NAME TEXT, ", [(AREA, "Oxford Meadows")])})
    out = tmp_path / "out"
    _run(capsys, "--source", str(src), "--out", str(out), "--only", "sac", "--apply")
    assert sorted(p.name for p in out.glob("*.json") if ".meta." not in p.name) == \
        ["sac_county.json", "sac_gb.json"]
    assert (out / "sac_gb.meta.json").is_file() and (out / "sac_gb.coords.npy").is_file()   # the binary form too


def test_ancient_woodland_class_codes(tmp_path, capsys):
    rows = [(AREA, "Foo Wood", "Ancient & Semi-Natural Woodland"),
            (box(50000, 50000, 60000, 60000), "Bar Wood", "Planted Ancient Woodland Site")]
    src = _src(tmp_path, {"Ancient Woodland England/awi.gpkg": ("aw", "NAME TEXT, THEMNAME TEXT, ", rows)})
    out = tmp_path / "out"
    _run(capsys, "--source", str(src), "--out", str(out), "--only", "ancient_woodland", "--apply")
    feats = json.loads((out / "ancient_woodland_county.json").read_text(encoding="utf-8"))["features"]
    assert {(f["n"], f["t"]) for f in feats} == {("Foo Wood", "ASNW"), ("Bar Wood", "PAWS")}


def test_non_27700_source_is_refused(tmp_path, capsys):
    root = tmp_path / "Environment data" / "SSSI England"
    root.mkdir(parents=True)
    make_gpkg(root / "sssi.gpkg", {"sites": ("SSSI_NAME TEXT, ", [(AREA, "X")])}, srs=4326)
    out = tmp_path / "out"
    code, text = _run(capsys, "--source", str(tmp_path / "Environment data"), "--out", str(out),
                      "--only", "sssi", "--apply")
    assert code == 1 and "refused" in text and "4326" in text
    assert not list(out.glob("*.json"))


def test_missing_name_field_is_reported_with_the_columns(tmp_path, capsys):
    src = _src(tmp_path, {"SSSI England/sssi.gpkg": ("sites", "TITLE TEXT, ", [(AREA, "X")])})
    code, text = _run(capsys, "--source", str(src), "--out", str(tmp_path / "o"), "--only", "sssi")
    assert code == 1 and "none of the name fields" in text and "TITLE" in text


# ---------------------------------------------------------------- shapefile reader

def _write_shp(base, rings_by_record, names, prj=True):
    """A polygon shapefile: each record a list of rings (outer clockwise, holes anticlockwise)."""
    body = b""
    for i, rings in enumerate(rings_by_record, 1):
        pts = [p for r in rings for p in r]
        parts = [sum(len(r) for r in rings[:k]) for k in range(len(rings))]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        rec = struct.pack("<i4d2i", 5, min(xs), min(ys), max(xs), max(ys), len(rings), len(pts))
        rec += struct.pack(f"<{len(parts)}i", *parts)
        rec += b"".join(struct.pack("<2d", *p) for p in pts)
        body += struct.pack(">2i", i, len(rec) // 2) + rec
    head = struct.pack(">i5ii", 9994, 0, 0, 0, 0, 0, 0)[:28] + struct.pack("<2i", 1000, 5) + b"\0" * 64
    head = head[:24] + struct.pack(">i", (100 + len(body)) // 2) + head[28:]
    base.with_suffix(".shp").write_bytes(head + body)
    flen = 20
    hdr = struct.pack("<4BIHH20x", 3, 126, 10, 25, len(names), 32 + 32 + 1, 1 + flen)
    fld = b"NAME".ljust(11, b"\0") + b"C" + b"\0" * 4 + bytes([flen, 0]) + b"\0" * 14
    recs = b"".join(b" " + n.encode().ljust(flen) for n in names)
    base.with_suffix(".dbf").write_bytes(hdr + fld + b"\r" + recs + b"\x1a")
    if prj:
        base.with_suffix(".prj").write_text('PROJCS["OSGB_1936_British_National_Grid"]')


def test_shapefile_source_with_a_hole(tmp_path, capsys):
    folder = tmp_path / "Environment data" / "NNR England"
    folder.mkdir(parents=True)
    outer = [(10000, 10000), (10000, 30000), (30000, 30000), (30000, 10000), (10000, 10000)]  # clockwise
    hole = [(15000, 15000), (25000, 15000), (25000, 25000), (15000, 25000), (15000, 15000)]
    _write_shp(folder / "NNR_England", [[outer, hole]], ["Hill Fen"])
    out = tmp_path / "out"
    code, text = _run(capsys, "--source", str(tmp_path / "Environment data"), "--out", str(out),
                      "--only", "nnr", "--apply")
    assert code == 0, text
    f = json.loads((out / "nnr_county.json").read_text(encoding="utf-8"))["features"][0]
    assert f["n"] == "Hill Fen" and f["t"] == "NNR" and len(f["rings"]) == 2


def test_shapefile_without_prj_is_refused(tmp_path, capsys):
    folder = tmp_path / "Environment data" / "NNR England"
    folder.mkdir(parents=True)
    ring = [(0, 0), (0, 10), (10, 10), (10, 0), (0, 0)]
    _write_shp(folder / "NNR_England", [[ring]], ["X"], prj=False)
    code, text = _run(capsys, "--source", str(tmp_path / "Environment data"), "--out",
                      str(tmp_path / "o"), "--only", "nnr", "--apply")
    assert code == 1 and "no .prj" in text


# ---------------------------------------------------------------- Identify

def _built(tmp_path, capsys, folder, table, cols, rows, key):
    src = _src(tmp_path, {f"{folder}/x.gpkg": (table, cols, rows)})
    maps = tmp_path / "maps"
    _run(capsys, "--source", str(src), "--out", str(maps / "layers"), "--only", key, "--apply")
    return maps


def test_identify_reports_type_and_name(qapp, tmp_path, capsys):
    maps = _built(tmp_path, capsys, "SSSI England", "sites", "SSSI_NAME TEXT, ",
                  [(AREA, "Ashen Bank")], "sssi")
    m = _map(maps)
    m.set_layers({"sssi"})
    assert m.identify_at(20000, 20000) == [("SSSI", "Ashen Bank")]
    assert m.identify_at(60000, 60000) == []
    m.set_layers(set())
    assert m.identify_at(20000, 20000) == []


def test_identify_reports_class_for_ancient_woodland_and_geology(qapp, tmp_path, capsys):
    maps = _built(tmp_path, capsys, "Ancient Woodland England", "aw", "NAME TEXT, THEMNAME TEXT, ",
                  [(AREA, "Foo Wood", "Ancient Replanted Woodland")], "ancient_woodland")
    src = _src(tmp_path, {"BGS 625k bedrock/geo.gpkg": ("geo", "LEX_D TEXT, MAX_PERIOD TEXT, ",
                                                           [(AREA, "MERCIA MUDSTONE GROUP", "TRIASSIC")])})
    _run(capsys, "--source", str(src), "--out", str(maps / "layers"), "--only", "geology_bedrock", "--apply")
    m = _map(maps)
    m.set_layers({"ancient_woodland", "geology_bedrock"})
    got = dict(m.identify_at(20000, 20000))
    assert got["Ancient woodland"] == "Foo Wood (ARW)"
    assert got["Bedrock"] == "MERCIA MUDSTONE GROUP (Triassic)"


def test_popup_lists_environment_lines(qapp, tmp_path, capsys):
    from src.views.mapping.identify_popup import IdentifyPopup, IdentifyInfo
    pop = IdentifyPopup(IdentifyInfo(1, 2, [("10 km", "SP43")], "VC23", "", None, 0,
                                     [("SSSI", "Ashen Bank"), ("Mean annual rainfall", "680 mm")]))
    assert [lab.text() for lab in pop.layer_labels] == ["SSSI: Ashen Bank", "Mean annual rainfall: 680 mm"]


# ---------------------------------------------------------------- value grids

RAIN = np.array([[600.0, 650.0, np.nan], [700.0, 1200.0, 2000.0]])
EXT = (20000, 30000, 50000, 50000)      # 3 x 2 cells of 10 km


def _grid_dir(tmp_path):
    maps = tmp_path / "maps"
    value_grid.write(maps / "layers", "haduk_rain", RAIN, EXT, 10000, scale=0.1, offset=0.0,
                     units="mm", label="Mean annual rainfall")
    return maps


def test_value_grid_round_trip_value_at_and_nodata(tmp_path):
    maps = _grid_dir(tmp_path)
    g = value_grid.load(maps, "haduk_rain")
    assert g.raw.shape == (2, 3) and g.raw.dtype == np.dtype("<u2") and g.extent == EXT
    assert g.value_at(25000, 45000) == pytest.approx(600.0)        # north-west cell
    assert g.value_at(45000, 35000) == pytest.approx(2000.0)       # south-east cell
    assert g.value_at(45000, 45000) is None                        # a no-data cell
    assert g.value_at(5000, 35000) is None and g.value_at(25000, 55000) is None   # outside
    assert g.identify(25000, 45000) == ("Mean annual rainfall", "600 mm")
    assert g.identify(25000, 35000) == ("Mean annual rainfall", "700 mm")
    assert g.identify(45000, 45000) is None
    assert "palest" in g.legend_text() and "mm" in g.legend_text()
    assert "haduk_rain" in layers.available(maps)


def test_value_grid_refuses_values_that_do_not_fit(tmp_path):
    with pytest.raises(ValueError):
        value_grid.write(tmp_path, "x", np.array([[70000.0]]), (0, 0, 1, 1), 1, scale=1.0, offset=0.0,
                         units="mm", label="x")


def test_identify_text_with_units_and_drawn_extent(qapp, tmp_path):
    maps = _grid_dir(tmp_path)
    m = _map(maps)
    before_in, before_out = _pixel(m, 35000, 35000), _pixel(m, 90000, 90000)
    m.set_layers({"haduk_rain"})
    assert m.identify_at(35000, 35000) == [("Mean annual rainfall", "1,200 mm")]
    assert m.identify_at(45000, 45000) == []                       # no data there
    assert _pixel(m, 35000, 35000) != before_in                    # drawn inside the extent
    assert _pixel(m, 90000, 90000) == before_out                   # nothing outside it


def test_build_grid_from_netcdf(tmp_path, capsys):
    h5py = pytest.importorskip("h5py")
    src = tmp_path / "Environment data" / "HadUK"
    src.mkdir(parents=True)
    x = np.arange(-1500.0, 5000.0, 1000.0)          # cell centres, 1 km, wider than the data
    y = np.arange(-1500.0, 4000.0, 1000.0)
    data = np.full((1, y.size, x.size), 1e20, dtype="float32")
    data[0, 3:6, 2:5] = [[600, 650, 700], [800, 900, 1000], [1100, 1200, 1300]]
    with h5py.File(src / "rainfall_hadukgrid_uk_1km_ann-30y_199101-202012.nc", "w") as f:
        f["projection_x_coordinate"] = x
        f["projection_y_coordinate"] = y
        ds = f.create_dataset("rainfall", data=data)
        ds.attrs["_FillValue"] = np.float32(1e20)
        ds.attrs["units"] = "mm"
        ds.attrs["grid_mapping"] = "transverse_mercator"
        g = f.create_dataset("transverse_mercator", data=0)
        g.attrs["grid_mapping_name"] = "transverse_mercator"
        g.attrs["false_easting"] = 400000.0
        g.attrs["false_northing"] = -100000.0
        g.attrs["longitude_of_central_meridian"] = -2.0
    out = tmp_path / "out"
    code, text = _run(capsys, "--source", str(tmp_path / "Environment data"), "--out", str(out),
                      "--only", "haduk_rain", "--apply")
    assert code == 0, text
    maps = tmp_path / "m2"
    (maps / "layers").mkdir(parents=True)
    for p in out.iterdir():
        (maps / "layers" / p.name).write_bytes(p.read_bytes())
    g = value_grid.load(maps, "haduk_rain")
    assert g.raw.shape == (3, 3) and g.cell_m == 1000
    assert g.identify(g.extent[0] + 500, g.extent[3] - 500)[1] == "1,100 mm"   # north-west (y runs south to north in the file)
    assert g.identify(g.extent[2] - 500, g.extent[1] + 500)[1] == "700 mm"      # south-east corner


def test_netcdf_not_on_the_british_grid_is_refused(tmp_path, capsys):
    h5py = pytest.importorskip("h5py")
    src = tmp_path / "Environment data"
    src.mkdir()
    with h5py.File(src / "rainfall_hadukgrid_uk_1km_ann-30y_199101-202012.nc", "w") as f:
        f["projection_x_coordinate"] = np.arange(3.0)
        f["projection_y_coordinate"] = np.arange(3.0)
        ds = f.create_dataset("rainfall", data=np.ones((1, 3, 3), dtype="float32"))
        ds.attrs["grid_mapping"] = "crs"
        g = f.create_dataset("crs", data=0)
        g.attrs["grid_mapping_name"] = "latitude_longitude"
    out = tmp_path / "out"
    code, text = _run(capsys, "--source", str(src), "--out", str(out), "--only", "haduk_rain", "--apply")
    assert code == 1 and "refused" in text and "27700" in text and not list(out.glob("*.json"))


def test_credit_line_includes_environment_credits(qapp, tmp_path):
    maps = _grid_dir(tmp_path)
    m = _map(maps)
    m.set_layers({"haduk_rain"})
    line = m.credit_line("")
    assert env.C_MET in line and "Mean annual rainfall" in line
