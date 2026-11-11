"""R18 B1: the maps zoom down to about 1 km across, from any starting extent (shared/maps/panzoom.py)."""
import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from shared.maps import grid_squares as gs  # noqa: E402
from shared.maps.panzoom import zoom_limit  # noqa: E402
from tests.test_map_picture import RED, _map, _Wheel  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_zoom_limit_rule():
    assert zoom_limit((0, 0, 641000, 1206000), floor=8) == 641.0       # GB: 1 km across
    # with the widget's size: the fit decides (a 300 x 360 widget is limited by its height)
    z = zoom_limit((0, 0, 641000, 1206000), 8, (300, 360))
    assert 999 < 300 / (350 / 1206000) / z < 1100
    assert zoom_limit((0, 0, 60000, 90000), floor=8) == 60.0           # a vice-county
    assert zoom_limit((0, 0, 3000, 5000), floor=8) == 8.0              # small: the floor
    assert zoom_limit((0, 0, 20000, 20000), floor=40) == 40.0          # the widget's own floor stays
    assert zoom_limit(None, floor=8) == 8.0


def test_gb_view_reaches_one_km_across(qapp, tmp_path):
    m = _map(tmp_path)
    m.set_extent(gs.GB_LAND)
    for _ in range(80):
        m.wheelEvent(_Wheel(1))
    assert m._zoom == pytest.approx(m._zoom_limit()) and m._zoom > 600
    e0, n0, e1, n1 = m.visible_extent()
    assert 900 < min(e1 - e0, n1 - n0) <= 1100


def test_county_view_reaches_about_one_km(qapp, tmp_path):
    m = _map(tmp_path)                                    # BOX: 100 km across
    for _ in range(60):
        m.wheelEvent(_Wheel(1))
    assert m._zoom == pytest.approx(m._zoom_limit()) and m._zoom > 90
    e0, n0, e1, n1 = m.visible_extent()
    assert 900 < min(e1 - e0, n1 - n0) <= 1100


def test_pan_stays_clamped_at_full_zoom(qapp, tmp_path):
    m = _map(tmp_path)
    for _ in range(60):
        m.wheelEvent(_Wheel(1, 10, 10))
    from PySide6.QtCore import QPointF
    m._pan = QPointF(1e9, -1e9)
    m._clamp_pan()
    z, w, h = m._zoom, m.width(), m.height()
    assert m._pan.x() == 0.0 and m._pan.y() == pytest.approx(h - z * h)
    m._pan = QPointF(-1e9, 1e9)
    m._clamp_pan()
    assert m._pan.x() == pytest.approx(w - z * w) and m._pan.y() == 0.0


def test_squares_and_layers_draw_at_full_zoom_and_paint_time(qapp, tmp_path):
    from PySide6.QtCore import QPointF
    m = _map(tmp_path)
    m.set_extent(gs.GB_LAND)
    m._vc_rings = {1: [[(440000, 210000), (470000, 210000), (470000, 240000), (440000, 240000),
                        (440000, 210000)]]}
    m._vc_names = {1: "Testshire"}
    m._geojson = "zoom-r18-test"
    m.set_squares({"SP5522": {"count": 1, "fill": RED}}, 1000)
    z = m._zoom_limit()
    m._zoom = z
    x, y = m.fit().to_px(455500, 222500)                 # the middle of the monad SP5522
    m._pan = QPointF(150 - x * z, 150 - y * z)
    m._clamp_pan()
    t0 = time.perf_counter()
    m.grab()
    dt = time.perf_counter() - t0
    print(f"R18 paint at {z:.0f}x: {dt:.3f}s")
    assert dt < 10
    e0, n0, e1, n1 = m.visible_extent()
    assert 900 < min(e1 - e0, n1 - n0) <= 1100            # about a kilometre across
    img = m._pic.pm.toImage()
    cx, cy = int(150 + m._pic.mx), int(150 + m._pic.my) + 30
    assert img.pixelColor(cx, cy).name() == RED           # the monad fills the view
    (key,) = [c for c in m._layer_cache if c[0] == "woodland"]
    assert key[1] == "county"
    # a second paint with the same view uses the kept picture: no re-render
    n = m.picture_renders
    m.grab()
    assert m.picture_renders == n


def test_mini_maps_use_the_same_rule(qapp):
    from shared.maps.raster_map import RasterMiniMap
    from shared.maps.species_dist_map import DistributionMiniMap
    d = DistributionMiniMap(None, resizable=True)
    d.resize(300, 300)
    assert d._zoom_limit() == pytest.approx(zoom_limit(d._extent, 8, (300, d.height())))
    for _ in range(80):
        d.wheelEvent(_Wheel(1))
    assert d._zoom == pytest.approx(d._zoom_limit()) and d._zoom > 8
    r = RasterMiniMap(None, resizable=True, window_m=20000)
    assert 20.0 <= r._zoom_limit() < 22.0
