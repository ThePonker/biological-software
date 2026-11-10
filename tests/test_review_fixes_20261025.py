# ruff: noqa: F811
"""Review fixes for the maps round (25 Oct 2026): 3D scene errors, credits, shapefile CRS and
holes, big layers, LiDAR window and gap filling, the scripts folder being absent."""
import json
import os
import subprocess
import sys
import zipfile
from datetime import date
from pathlib import Path

import numpy as np
import pytest

from tests._qt_cleanup import _delete_new_widgets  # noqa: F401  (autouse teardown)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from scripts import build_env_layers as be, env_shp  # noqa: E402
from shared.maps import env_registry as env, layers, terrain, terrain_lidar  # noqa: E402
from tests.test_env_layers import AREA, _run, _src, _write_shp  # noqa: E402
from tests.test_map_layers_r11 import _map, qapp  # noqa: E402,F401
from tests.test_map_view3d import E0, N0, FakeMap, t50, z_at  # noqa: E402,F401

ROOT = Path(__file__).resolve().parent.parent
EXT = (440000.0, 120000.0, 441000.0, 120500.0)


_KEEP = []


def _dispose(qapp, *widgets):
    """Like the other 3D tests: deleteLater + processEvents; the Python wrappers are kept so
    QtGraphs objects are not collected in an arbitrary order at the end of the test."""
    _KEEP.extend(widgets)
    for w in widgets:
        w.deleteLater()
    qapp.processEvents()


def _heights():
    g = np.linspace(0, 80, 20 * 40, dtype=np.float32).reshape(20, 40)
    return terrain.Heights(g, EXT, 25.0, "OS Terrain 50, test", np.zeros_like(g, bool))


# ---------------------------------------------------------------- 1 and 10: the 3D window
def test_scene_graph_error_is_connected_and_shown():
    """Builds real Qt Quick widgets: run in a child process (tests/_view3d_quick_checks.py)."""
    from _view3d_quick_checks import run_in_child
    out = run_in_child('scene_graph_error_is_shown')
    assert "OK scene_graph_error_is_shown" in out, out


def test_scene_creation_failure_is_a_message():
    """Builds real Qt Quick widgets: run in a child process (tests/_view3d_quick_checks.py)."""
    from _view3d_quick_checks import run_in_child
    out = run_in_child('scene_creation_failure_is_a_message')
    assert "OK scene_creation_failure_is_a_message" in out, out


@pytest.mark.parametrize("exc", [zipfile.BadZipFile("bad"), OSError("disk"), ValueError("shape")])
def test_window_never_raises_out_of_the_constructor(qapp, monkeypatch, exc):
    from PySide6.QtWidgets import QLabel
    from Observatum.src.views.mapping import view3d

    def boom(*a, **k):
        raise exc
    monkeypatch.setattr(terrain, "heights_for_extent", boom)
    w = view3d.View3DWindow(FakeMap(), EXT)
    texts = [lab.text() for lab in w.findChildren(QLabel)]
    assert any(type(exc).__name__ in t for t in texts) and not w.export_btn.isEnabled()
    _dispose(qapp, w)


def test_height_axis_is_not_clipped_below_sea_level():
    """Builds real Qt Quick widgets: run in a child process (tests/_view3d_quick_checks.py)."""
    from _view3d_quick_checks import run_in_child
    out = run_in_child('height_axis_not_clipped_below_sea_level')
    assert "OK height_axis_not_clipped_below_sea_level" in out, out


def _many_layers(tmp_path):
    d = tmp_path / "maps" / "layers"
    d.mkdir(parents=True)
    ring = [[10000, 10000], [10000, 20000], [20000, 20000], [10000, 10000]]
    feat = {"bbox": [10000, 10000, 20000, 20000], "rings": [ring]}
    for e in env.ENV_LAYERS:
        if e.kind == "polygon":
            (d / f"{e.key}_county.json").write_text(json.dumps({"features": [feat]}), encoding="utf-8")
    return tmp_path / "maps"


def test_credits_have_the_os_sentence_once_and_each_text_once(qapp, tmp_path):
    assert env.OS_PART not in env.C_NE and env.OS_PART not in env.C_NRW
    maps = _many_layers(tmp_path)
    m = _map(maps)
    m.set_layers({e.key for e in env.ENV_LAYERS if e.kind == "polygon"})
    line = m.credit_line("")
    assert line.count(env.OS_PART) == 1 and line.count(env.C_NE) == 1
    assert env.C_LE in line and env.C_NS_AWI in line
    assert layers.credit_lines(maps, ["sssi", "nnr"]).count(env.C_NE) == 1


def test_credit_year_follows_the_date():
    assert env.YEAR == date.today().year and str(env.YEAR) in layers.OS_CREDIT


def test_many_layers_grow_the_credit_box_and_shrink_the_map(qapp, tmp_path):
    maps = _many_layers(tmp_path)
    m = _map(maps)
    legend = [("#336699", "Recorded")] * 3
    m.set_layers({"sssi"})
    few = m._reserve_mm(900, 100, legend, "12 squares")
    img_few = m.render_sheet("T", legend=legend, footer="12 squares", dpi=100)
    box_few = m._sheet_box(img_few.width(), img_few.height(), 100, few)
    m.set_layers({e.key for e in env.ENV_LAYERS if e.kind == "polygon"})
    many = m._reserve_mm(900, 100, legend, "12 squares")
    assert many > few
    img = m.render_sheet("T", legend=legend, footer="12 squares", dpi=100)
    box = m._sheet_box(img.width(), img.height(), 100, many)
    assert box.height() < box_few.height() and box.top() == box_few.top()
    # no overlap: credits (bottom-aligned, measured) start below the legend row
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QFontMetricsF
    from shared.maps.atlas_sheet import _font
    mm = 100 / 25.4
    text_h = QFontMetricsF(_font(7), img).boundingRect(
        QRectF(0, 0, img.width() - 24 * mm, 10 ** 6),
        int(Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap), m.credit_line("12 squares")).height()
    credit_top = img.height() - 12 * mm - text_h
    legend_end = box.bottom() + 4 * mm + 4 * mm
    assert credit_top >= legend_end
    # the view shown by sheet_view agrees with the page
    _e, shown = m.sheet_view(None, "A4", 100, legend, "12 squares")
    assert shown[3] - shown[1] > 0


def test_3d_export_credits_use_the_shared_helper(qapp, tmp_path):
    from Observatum.src.views.mapping import view3d_drape as dr
    maps = _many_layers(tmp_path)
    m = FakeMap()
    m._maps_dir = str(maps)
    m.layers_drawn = lambda: ["land", "sssi", "nnr", "living_england"]
    lines = dr.footer_lines(EXT, 2, "LiDAR DTM (1 tile(s)), 2 m cells", 2, dr.export_credits(m, "LiDAR DTM"))
    assert lines.count(layers.OS_CREDIT) == 1 and lines.count(env.C_NE) == 1
    assert env.C_LE in lines and terrain.EA_CREDIT in lines
    assert terrain.EA_CREDIT not in dr.export_credits(m, "OS Terrain 50")
    assert layers.OS_CREDIT in dr.export_credits(FakeMap(), "OS Terrain 50")
    from PySide6.QtGui import QImage
    img = QImage(300, 100, QImage.Format.Format_RGB32)
    short = dr.compose_export(img, ["a"], "#ffffff", "#000000")
    long = dr.compose_export(img, ["word " * 200], "#ffffff", "#000000")
    assert long.height() > short.height() + 100


def test_credit_wording_in_the_registry():
    assert "OS Open Data" not in env.C_NS_AWI and "Copyright NatureScot" in env.C_NS_AWI
    assert env.C_NS_AWI in env.ENV_BY_KEY["ancient_woodland"].credits
    assert env.ENV_BY_KEY["living_england"].credits == (env.C_LE,)
    assert "Natural England" in env.C_LE and "data.gov.uk" in Path(env.__file__).read_text(encoding="utf-8")


# ---------------------------------------------------------------- 5 and 6: shapefiles
@pytest.mark.parametrize("prj, ok", [
    ('PROJCS["OSGB_1936_British_National_Grid",GEOGCS["GCS_OSGB_1936"]]', True),
    ('PROJCS["x",GEOGCS["GCS_OSGB_1936",DATUM["D_OSGB_1936"]],PROJECTION["Transverse_Mercator"],'
     'PARAMETER["False_Easting",400000.0],PARAMETER["False_Northing",-100000.0]]', True),
    ('GEOGCS["GCS_OSGB_1936",DATUM["D_OSGB_1936",SPHEROID["Airy_1830",6377563.396,299.3249646]],'
     'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]', False),
    ('PROJCS["x",GEOGCS["GCS_OSGB_1936"],PROJECTION["Transverse_Mercator"],'
     'PARAMETER["False_Easting",500000.0],PARAMETER["False_Northing",0.0]]', False),
    ('PROJCS["WGS_1984_UTM_Zone_30N",GEOGCS["GCS_WGS_1984"]]', False)])
def test_prj_must_be_a_projected_british_national_grid(tmp_path, prj, ok):
    (tmp_path / "a.prj").write_text(prj)
    assert env_shp.crs_is_27700(tmp_path / "a.shp")[0] is ok


def test_geographic_osgb_shapefile_is_refused(tmp_path, capsys):
    folder = tmp_path / "Environment data" / "NNR England"
    folder.mkdir(parents=True)
    ring = [(0, 0), (0, 10), (10, 10), (10, 0), (0, 0)]
    _write_shp(folder / "NNR_England", [[ring]], ["X"])
    (folder / "NNR_England.prj").write_text('GEOGCS["GCS_OSGB_1936",DATUM["D_OSGB_1936"]]')
    code, text = _run(capsys, "--source", str(tmp_path / "Environment data"), "--out",
                      str(tmp_path / "o"), "--only", "nnr", "--apply")
    assert code == 1 and "not a projected British National Grid" in text


def test_hole_touching_the_outer_boundary_at_its_first_vertex():
    a = [(0, 0), (0, 10), (20, 10), (20, 0), (0, 0)]                  # clockwise, 200
    b = [(100, 100), (100, 110), (110, 110), (110, 100), (100, 100)]  # 100
    hole = [(0, 0), (5, 0), (5, 5), (0, 5), (0, 0)]                   # anticlockwise, 25, first vertex on A
    g = env_shp._polygon([a, b, hole])
    assert g.area == pytest.approx(175 + 100)
    inner = [(1, 1), (1, 9), (19, 9), (19, 1), (1, 1)]                # an outer ring inside A's area
    h2 = [(5, 2), (8, 2), (8, 4), (5, 4), (5, 2)]                     # inside both A and the inner ring
    g2 = env_shp._polygon([a, inner, h2])
    smallest = min(g2.geoms, key=lambda p: p.area)
    assert len(smallest.interiors) == 1                               # the smallest covering outer


# ---------------------------------------------------------------- 7: big layers
def _phi_src(tmp_path):
    return _src(tmp_path, {"Priority Habitat/phi.gpkg": (
        "phi", "MAIN_HABIT TEXT, ", [(AREA, "Lowland fens"), (AREA, "Deciduous woodland")])})


def test_big_county_file_is_refused_unless_allowed(tmp_path, capsys, monkeypatch):
    src, out = _phi_src(tmp_path), tmp_path / "out"
    monkeypatch.setattr(be, "MAX_COUNTY_BYTES", 10)
    code, text = _run(capsys, "--source", str(src), "--out", str(out), "--only", "phi", "--apply")
    assert code == 1 and "features, about" in text and "--allow-large" in text and "--types" in text
    assert not list(out.glob("phi_*"))
    code, text = _run(capsys, "--source", str(src), "--out", str(out), "--only", "phi", "--apply",
                      "--allow-large")
    assert code == 0 and (out / "phi_county.json").is_file() and "features kept" in text


def test_phi_subset_does_not_overwrite_a_full_file_without_replace(tmp_path, capsys):
    src, out = _phi_src(tmp_path), tmp_path / "out"
    _run(capsys, "--source", str(src), "--out", str(out), "--only", "phi", "--apply")
    full = (out / "phi_county.json").read_text(encoding="utf-8")
    code, text = _run(capsys, "--source", str(src), "--out", str(out), "--only", "phi", "--apply",
                      "--types", "Lowland fens")
    assert code == 1 and "--replace" in text and (out / "phi_county.json").read_text(encoding="utf-8") == full
    code, _t = _run(capsys, "--source", str(src), "--out", str(out), "--only", "phi", "--apply",
                    "--types", "Lowland fens", "--replace")
    assert code == 0 and len(json.loads((out / "phi_county.json").read_text(encoding="utf-8"))["features"]) == 1


def test_gpkg_is_preferred_over_a_shp_copy(tmp_path, capsys):
    src = _src(tmp_path, {"NNR England/nnr.gpkg": ("nnr", "NNR_NAME TEXT, ", [(AREA, "Hill Fen")])})
    (src / "NNR England" / "nnr.shp").write_bytes(b"")
    code, text = _run(capsys, "--source", str(src), "--out", str(tmp_path / "o"), "--only", "nnr")
    assert code == 0 and "nnr.shp skipped, the .gpkg copy" in text and "nnr.gpkg" in text


def test_unticking_a_layer_forgets_its_features(qapp, tmp_path):
    maps = _many_layers(tmp_path)
    m = _map(maps)
    m.set_layers({"phi", "sssi"})
    layers.load(str(maps), "phi", "county")
    layers.load(str(maps), "sssi", "county")
    named = lambda k: [c for c in layers._CACHE if Path(c[0]).name.startswith(k + "_")]   # noqa: E731
    assert named("phi") and named("sssi")
    m.set_layers({"sssi"})
    assert not named("phi") and named("sssi")
    layers.forget("sssi")
    assert not named("sssi")


# ---------------------------------------------------------------- 8: LiDAR
def _gap_tif(tmp_path):
    tifffile = pytest.importorskip("tifffile")
    z = np.full((100, 100), 50.0, np.float32)
    z[40:60, 40:60] = -9999.0
    path = tmp_path / "lidar" / "a.tif"
    path.parent.mkdir(exist_ok=True)
    tifffile.imwrite(str(path), z, extratags=[
        (33550, "d", 3, (2.0, 2.0, 0.0), True),
        (33922, "d", 6, (0.0, 0.0, 0.0, 441000.0, 121200.0, 0.0), True),
        (42113, "s", 6, "-9999", True)])
    return path


def test_lidar_gaps_are_filled_from_terrain_50(t50, tmp_path):
    _gap_tif(tmp_path)
    h = terrain.heights_for_extent((441000, 121000, 441200, 121200), source=t50,
                                   lidar_dir=tmp_path / "lidar")
    assert "LiDAR" in h.source_label and "gaps filled from OS Terrain 50" in h.source_label
    assert h.cell_m == 2 and not np.isnan(h.grid).any()
    centre = h.grid[50, 50]                                     # (441100, 121100): inside the gap
    assert centre == pytest.approx(z_at(441100, 121100), abs=0.3) and centre > 10
    assert h.grid[5, 5] == pytest.approx(50.0)                  # real LiDAR is untouched
    assert not h.sea[50, 50]


def test_lidar_only_for_views_up_to_10_km(t50, tmp_path):
    _gap_tif(tmp_path)
    assert terrain_lidar.lidar_heights((440000, 120000, 451000, 121000), 512, tmp_path / "lidar") is None
    h = terrain.heights_for_extent((E0, N0, E0 + 12000, N0 + 3000), source=t50, lidar_dir=tmp_path / "lidar")
    assert "Terrain 50" in h.source_label and "LiDAR" not in h.source_label


def test_lidar_reads_only_the_window(t50, tmp_path, monkeypatch):
    path = _gap_tif(tmp_path)
    tf = pytest.importorskip("tifffile")
    whole = np.asarray(tf.imread(str(path)))
    assert np.array_equal(terrain_lidar.read_window(tf, path, 10, 30, 5, 25), whole[10:30, 5:25])
    asked = []
    real = terrain_lidar.read_window
    monkeypatch.setattr(terrain_lidar, "read_window", lambda *a: asked.append(a[2:]) or real(*a))
    terrain_lidar.lidar_heights((441050, 121050, 441150, 121150), 512, tmp_path / "lidar")
    assert asked == [(25, 75, 25, 75)]


# ---------------------------------------------------------------- 9: no scripts folder
def test_mapping_modules_import_without_the_scripts_folder():
    code = (
        "import sys; sys.modules['scripts'] = None\n"
        "from shared.maps import terrain, terrain_lidar\n"
        "from Observatum.src.views.mapping import view3d, view3d_drape, view3d_scene\n"
        "try:\n"
        "    terrain.heights_for_extent((0, 0, 1000, 1000), source='/nonexistent', lidar_dir='/nonexistent')\n"
        "except terrain.TerrainUnavailable as e:\n"
        "    print('OK', e)\n")
    env_ = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONIOENCODING="utf-8",
                PYTHONPATH=os.pathsep.join([str(ROOT), str(ROOT / "Observatum")]))
    r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env_, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    assert r.returncode == 0 and "OK" in r.stdout, r.stderr[-800:]
