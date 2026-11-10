"""The Mapping tab's 3D view (shared/maps/terrain.py, terrain_lidar.py, view3d*.py).

Tiny made-up Terrain 50 zip and GeoTIFF; nothing is rendered (no GPU needed), offscreen.
"""
import io
import os
import sys
import zipfile
from types import SimpleNamespace

import numpy as np
import pytest

from tests._qt_cleanup import _delete_new_widgets  # noqa: F401  (autouse teardown)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from shared.maps import terrain, terrain_lidar  # noqa: E402

E0, N0 = 440000, 120000          # SU42's south west corner


def z_at(e, n):
    return (e - E0) / 100.0 + (n - N0) / 50.0 + 5.0


def asc(xll, yll, sea_corner=False):
    rows = []
    for r in range(200):                       # north first
        n = yll + (199 - r) * 50 + 25
        vals = [z_at(xll + c * 50 + 25, n) for c in range(200)]
        rows.append(vals)
    if sea_corner:
        for r in range(195, 200):
            for c in range(0, 10):
                rows[r][c] = -9999 if c < 5 else 0.0
    head = f"ncols 200\nnrows 200\nxllcorner {xll}\nyllcorner {yll}\ncellsize 50\nNODATA_value -9999\n"
    return (head + "\n".join(" ".join(f"{v:.3f}" for v in row) for row in rows) + "\n").encode()


@pytest.fixture
def t50(tmp_path):
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as z:
        z.writestr("su/su42.asc", asc(E0, N0, sea_corner=True))
        z.writestr("su/su52.asc", asc(E0 + 10000, N0))
    path = tmp_path / "terr50_gagg_gb.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("data/su.zip", inner.getvalue())
    terrain.clear_cache()
    return path


NO_LIDAR = None


def heights(t50, tmp_path, extent, **kw):
    return terrain.heights_for_extent(extent, source=t50, lidar_dir=tmp_path / "nolidar", **kw)


def test_terrain50_shape_order_values(t50, tmp_path):
    h = heights(t50, tmp_path, (E0 + 1000, N0 + 1000, E0 + 3000, N0 + 2000), max_points=40)
    assert h.grid.shape == (20, 40) and h.cell_m == 50 and h.grid.dtype == np.float32
    assert h.extent == (E0 + 1000, N0 + 1000, E0 + 3000, N0 + 2000)
    assert h.grid[0, 0] == pytest.approx(z_at(E0 + 1025, N0 + 1975), abs=0.01)   # north row first
    assert h.grid[-1, -1] == pytest.approx(z_at(E0 + 2975, N0 + 1025), abs=0.01)
    assert h.grid[0, 0] > h.grid[-1, 0]
    assert "Terrain 50" in h.source_label and not h.sea.any()


def test_two_tiles_and_sea_mask(t50, tmp_path):
    h = heights(t50, tmp_path, (E0 + 9000, N0, E0 + 11000, N0 + 1000), max_points=40)
    assert h.grid.shape == (20, 40)
    assert h.grid[0, 0] == pytest.approx(z_at(E0 + 9025, N0 + 975), abs=0.01)
    assert h.grid[0, -1] == pytest.approx(z_at(E0 + 10975 - 10000, N0 + 975) + 100, abs=0.01)
    s = heights(t50, tmp_path, (E0, N0, E0 + 500, N0 + 500), max_points=10)
    assert s.sea[-1, 0] and s.sea[-1, 4] and not s.sea[0, 0]      # nodata and exactly 0.0
    assert s.grid[-1, 0] == 0.0


def test_missing_area_and_source(t50, tmp_path):
    with pytest.raises(terrain.TerrainUnavailable):
        heights(t50, tmp_path, (E0 + 50000, N0, E0 + 51000, N0 + 1000))
    with pytest.raises(terrain.TerrainUnavailable):
        terrain.heights_for_extent((E0, N0, E0 + 1000, N0 + 1000), source=tmp_path / "none",
                                   lidar_dir=tmp_path / "nolidar")


def test_resample_down_block_mean_and_up_bilinear(t50, tmp_path):
    ext = (E0, N0, E0 + 20000, N0 + 10000)                  # 400 x 200 cells
    d = heights(t50, tmp_path, ext, max_points=100)
    assert d.cell_m == 200 and d.grid.shape == (50, 100) and max(d.grid.shape) <= 100
    one = heights(t50, tmp_path, ext, max_points=400).grid
    assert d.grid[10, 20] == pytest.approx(one[40:44, 80:84].mean(), abs=0.01)
    u = heights(t50, tmp_path, (E0 + 2000, N0 + 2000, E0 + 3000, N0 + 3000), max_points=512)
    assert u.cell_m == 12.5 and u.grid.shape == (80, 80)
    assert u.grid[40, 40] == pytest.approx(z_at(E0 + 2500, N0 + 2500), abs=0.2)   # linear data stays linear


def test_tiles_come_from_the_lru(t50, tmp_path, monkeypatch):
    ext = (E0 + 1000, N0 + 1000, E0 + 3000, N0 + 2000)
    heights(t50, tmp_path, ext)
    before = terrain.cache_hits
    heights(t50, tmp_path, ext)
    assert terrain.cache_hits > before
    monkeypatch.setattr(terrain, "LRU_TILES", 1)
    heights(t50, tmp_path, (E0 + 9000, N0, E0 + 11000, N0 + 1000))
    assert len(terrain._TILES) <= 1


# ---------------------------------------------------------------- LiDAR
def _tif(tmp_path, name="a", tags=True):
    tifffile = pytest.importorskip("tifffile")
    z = np.fromfunction(lambda r, c: 50.0 + c * 0.5 - r * 0.0, (100, 100)).astype(np.float32)
    path = tmp_path / "lidar" / f"{name}.tif"
    path.parent.mkdir(exist_ok=True)
    extra = [(33550, "d", 3, (2.0, 2.0, 0.0), True),
             (33922, "d", 6, (0.0, 0.0, 0.0, 441000.0, 121200.0, 0.0), True)] if tags else None
    tifffile.imwrite(str(path), z, extratags=extra)
    if not tags:                                 # a world file: x, y are the centre of pixel 0, 0
        path.with_suffix(".tfw").write_text("2\n0\n0\n-2\n441001\n121199\n")
    return path


@pytest.mark.parametrize("tags", [True, False])
def test_lidar_used_when_covering(t50, tmp_path, tags):
    _tif(tmp_path, tags=tags)
    ext = (441050, 121050, 441150, 121150)
    h = terrain.heights_for_extent(ext, source=t50, lidar_dir=tmp_path / "lidar")
    assert "LiDAR" in h.source_label and h.cell_m == 2 and h.grid.shape == (50, 50)
    assert h.grid[0, 0] == pytest.approx(50.0 + 25 * 0.5 + 0.25, abs=0.3)      # column 25 from the tile's west edge


def test_lidar_falls_back(t50, tmp_path, monkeypatch):
    _tif(tmp_path)
    out = (E0 + 1000, N0 + 1000, E0 + 3000, N0 + 2000)       # a tile away: no LiDAR there
    h = terrain.heights_for_extent(out, source=t50, lidar_dir=tmp_path / "lidar")
    assert "Terrain 50" in h.source_label and "LiDAR not used" in h.source_label
    part = (441100, 121100, 441300, 121300)                   # only partly covered
    h = terrain.heights_for_extent(part, source=t50, lidar_dir=tmp_path / "lidar")
    assert "Terrain 50" in h.source_label
    monkeypatch.setattr(terrain_lidar, "_tifffile", lambda: None)
    h = terrain.heights_for_extent((441050, 121050, 441150, 121150), source=t50,
                                   lidar_dir=tmp_path / "lidar")
    assert "Terrain 50" in h.source_label and "tifffile is not installed" in h.source_label


# ---------------------------------------------------------------- exaggeration, columns
def test_exaggeration_clamped_and_larger_for_flat():
    ext = (0, 0, 10000, 10000)
    flat = np.full((10, 10), 5.0, np.float32)
    hill = np.linspace(0, 400, 100, dtype=np.float32).reshape(10, 10)
    mountain = np.linspace(0, 3000, 100, dtype=np.float32).reshape(10, 10)
    ef, eh, em = (terrain.sensible_exaggeration(g, ext) for g in (flat, hill, mountain))
    assert all(1 <= v <= 10 for v in (ef, eh, em)) and ef == 10
    assert eh == pytest.approx(3.0) and em == 1.0 and ef > eh > em
    gentle = np.linspace(0, 100, 100, dtype=np.float32).reshape(10, 10)
    assert terrain.sensible_exaggeration(gentle, ext) > eh


def test_columns_for_squares():
    grid = np.arange(100, dtype=np.float32).reshape(10, 10)           # extent 10 km, 1 km cells
    ext = (440000, 120000, 450000, 130000)
    sq = {"SU42": {"count": 3, "fill": "#112233"},                    # centre 445000, 125000
          "SU43": {"count": 2},                                       # north of the extent
          "SU52": {"count": 1}, "SU4222": {"count": 0}}
    cols = terrain.columns_for_squares(sq, grid, ext, 1000.0)
    assert [(c[0], c[1], c[3]) for c in cols] == [(445000, 125000, 3)]
    assert cols[0][2] == grid[5, 5]
    det = terrain.columns_for_squares(sq, grid, ext, 1000.0, detail=True)
    assert det[0][4:] == ("SU42", 10000)


# ---------------------------------------------------------------- Qt parts
@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


class FakeMap:
    def __init__(self):
        self.calls, self._layers_on, self._squares = [], {"woodland", "relief"}, {}
        self.during = None

    def width(self):
        return 800

    def height(self):
        return 600

    def set_layers(self, keys):
        self._layers_on = set(keys)

    def draw(self, p, fit, k=1.0, selected=True, zoom=1.0, base=True):
        self.calls.append((fit.extent, p.device().width(), p.device().height()))
        self.during = set(self._layers_on)

    def visible_extent(self):
        return (440000, 120000, 450000, 125000)


def test_drape_matches_extent_and_leaves_relief_off_then_back(qapp):
    from Observatum.src.views.mapping import view3d_drape as dr
    m, ext = FakeMap(), (440000, 120000, 450000, 125000)
    img = dr.make_drape(m, ext)
    assert (img.width(), img.height()) == (2048, 1024)
    assert m.calls == [(ext, 2048, 1024)]
    assert m.during == {"woodland"} and m._layers_on == {"woodland", "relief"}
    assert dr.drape_size((0, 0, 100, 400)) == (512, 2048)


def test_footer_lines():
    from Observatum.src.views.mapping import view3d_drape as dr
    from shared.maps.layers import OS_CREDIT
    a = dr.footer_lines((440000, 120000, 450000, 125000), 3.5, "OS Terrain 50, 50 m cells", 50)
    assert "3.5x" in a[0] and "SU4020 to SU4924" in a[0] and a[1] == OS_CREDIT and len(a) == 2
    b = dr.footer_lines((440000, 120000, 450000, 125000), 2, "LiDAR DTM (1 tile(s)), 2 m cells", 2)
    assert b[-1] == terrain.EA_CREDIT


def test_toolbar_button_is_greyed_out_while_the_3d_view_is_rebuilt(qapp):
    from Observatum.src.views.mapping.toolbar import MapToolbar
    tb, got = MapToolbar(), []
    tb.view3d_requested.connect(lambda: got.append(1))
    assert not tb.view3d_btn.isEnabled() and tb.view3d_btn.text() == "3D view"
    assert tb.view3d_btn.toolTip() == ("The 3D view is being rebuilt and will return in a "
                                       "later version.")
    tb.view3d_btn.click()                       # a disabled button does nothing
    assert got == []
    tb.view3d_requested.emit()                  # the signal and the code behind it are kept
    assert got == [1]
    tb.deleteLater()
    qapp.processEvents()


def test_open_view3d_keeps_one_window(qapp, monkeypatch):
    """Since Round 16 the view is its own process: open_view3d launches it and closes the previous one."""
    from Observatum.src.views.mapping import view3d
    made = []

    class Handle:
        def __init__(self, ext):
            self.closed, self.ext = False, ext

        def close(self):
            self.closed = True

        def deleteLater(self):
            pass

    def fake_launch(m, ext, parent=None):
        made.append(Handle(ext))
        return made[-1]
    monkeypatch.setattr(view3d, "launch_view3d", fake_launch)
    m = FakeMap()
    w1 = view3d.open_view3d(None, m)
    w2 = view3d.open_view3d(w1, m)
    assert w1.closed and not w2.closed and len(made) == 2 and w2.ext == m.visible_extent()


def test_mapping_tab_wiring_uses_controller(monkeypatch):
    from Observatum.src.views.mapping import mapping_tab
    seen = []
    monkeypatch.setattr(mapping_tab, "open_view3d", lambda cur, mw, parent=None: seen.append((cur, mw)) or "WIN")
    me = SimpleNamespace(_view3d="OLD", map_widget="MAP")
    mapping_tab.MappingTab._on_view3d(me)
    assert seen == [("OLD", "MAP")] and me._view3d == "WIN"


def test_wide_view_is_flagged():
    from Observatum.src.views.mapping import view3d
    # 25 km since 25 Oct 2026 (was 120 km)
    assert view3d.too_wide((0, 0, 30000, 1000)) and not view3d.too_wide((0, 0, 20000, 20000))


def test_window_falls_back_when_qtgraphs_missing(qapp, monkeypatch):
    from Observatum.src.views.mapping import view3d
    monkeypatch.setitem(sys.modules, "PySide6.QtGraphsWidgets", None)
    # heights and drape are made before the scene (Round 16), so give it some
    g = np.linspace(0, 80, 20 * 40, dtype=np.float32).reshape(20, 40)
    ext = (440000.0, 120000.0, 450000.0, 125000.0)
    monkeypatch.setattr(terrain, "heights_for_extent", lambda *a, **k: terrain.Heights(
        g, ext, 25.0, "OS Terrain 50, test", np.zeros_like(g, bool)))
    w = view3d.View3DWindow(FakeMap(), ext)
    assert not w.export_btn.isEnabled() and not w.ex_slider.isEnabled()
    from PySide6.QtWidgets import QLabel
    texts = [lab.text() for lab in w.findChildren(QLabel)]
    assert any("not available" in t for t in texts)


def test_window_says_when_no_heights(qapp, monkeypatch, tmp_path):
    from Observatum.src.views.mapping import view3d
    monkeypatch.setattr(terrain, "DEFAULT_SOURCE", tmp_path / "none")
    monkeypatch.setattr(terrain, "LIDAR_DIR", tmp_path / "none")
    w = view3d.View3DWindow(FakeMap(), (440000, 120000, 450000, 125000))
    from PySide6.QtWidgets import QLabel
    assert any("Terrain 50" in lab.text() for lab in w.findChildren(QLabel))


def test_window_builds_with_fake_heights():
    """Builds real Qt Quick widgets: run in a child process (tests/_view3d_quick_checks.py)."""
    from _view3d_quick_checks import run_in_child
    out = run_in_child('window_builds_with_fake_heights')
    assert "OK window_builds_with_fake_heights" in out, out


