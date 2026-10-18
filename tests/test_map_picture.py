"""Mapping tab map, round 10 (18 Oct 2026): the kept static picture (shared/maps/map_picture.py),
the zoom preview, the 40x zoom limit and the background warm-up (map_warmup.py). Small purpose-made
layer files in tmp_path; nothing from Wil's data.
"""
import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from shared.maps import coast, layers, vc_topology  # noqa: E402
from shared.maps import grid_squares as gs  # noqa: E402

BOX = (400000, 170000, 500000, 270000)          # 100 km round hectad SP52 (450-460 km E, 220-230 km N)
RED = "#a63d40"


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


class _Wheel:
    """The bit of a QWheelEvent the zoom code reads."""

    def __init__(self, notches, x=150.0, y=150.0):
        from PySide6.QtCore import QPoint, QPointF
        self._d, self._p = QPoint(0, int(120 * notches)), QPointF(x, y)

    def angleDelta(self):
        return self._d

    def position(self):
        return self._p


def _write(maps_dir, key, lod, features, kind="polygon"):
    d = maps_dir / "layers"
    d.mkdir(exist_ok=True)
    (d / f"{key}_{lod}.json").write_text(json.dumps(
        {"layer": key, "lod": lod, "kind": kind, "features": features}), encoding="utf-8")


def _sq(e0, n0, e1, n1):
    return {"bbox": [e0, n0, e1, n1], "rings": [[[e0, n0], [e1, n0], [e1, n1], [e0, n1], [e0, n0]]]}


def _map(tmp_path, zoom=1.0):
    from PySide6.QtCore import QPointF
    from shared.maps.grid_map import GridMap
    for lod in ("county", "gb"):
        _write(tmp_path, "land", lod, [_sq(0, 0, 700000, 1300000)])
        _write(tmp_path, "woodland", lod, [_sq(440000, 210000, 470000, 240000)])
    m = GridMap(geojson_path=None, maps_dir=str(tmp_path))
    m.resize(300, 300)
    m.set_extent(BOX)
    m.set_layers({"woodland"})
    m.set_squares({"SP52": {"count": 1, "fill": RED}}, 10000)
    if zoom > 1:
        m._zoom = zoom
        m._pan = QPointF(-100.0 * zoom, -100.0 * zoom)
        m._clamp_pan()
    return m


def _pan(m, dx, dy):
    from PySide6.QtCore import QPointF
    m._pan = QPointF(m._pan.x() + dx, m._pan.y() + dy)
    m._clamp_pan()


# ---------------------------------------------------------------- panning

def test_a_pan_step_blits_the_kept_picture_without_rendering(qapp, tmp_path):
    m = _map(tmp_path, zoom=4.0)
    m.grab()
    assert m.picture_renders == 1
    for _ in range(5):
        _pan(m, -20, -20)           # 100 px in all; the margin is 150 px
        m.grab()
    assert m.picture_renders == 1


def test_a_blit_shows_the_same_map_as_a_fresh_render(qapp, tmp_path):
    m = _map(tmp_path, zoom=4.0)
    m.grab()
    _pan(m, -60, -45)
    blit = m.grab().toImage()
    assert m.picture_renders == 1
    m._pic = None                    # now drawn again at this pan
    fresh = m.grab().toImage()
    assert m.picture_renders == 2
    worst = max(abs(blit.pixelColor(x, y).red() - fresh.pixelColor(x, y).red())
                for x in range(10, 290, 7) for y in range(10, 290, 7))
    assert worst <= 8


def test_leaving_the_margin_renders_once(qapp, tmp_path):
    m = _map(tmp_path, zoom=4.0)
    m.grab()
    _pan(m, -151, 0)                 # past the 150 px margin
    m.grab()
    assert m.picture_renders == 2
    _pan(m, -10, -10)
    m.grab()
    m.grab()
    assert m.picture_renders == 2    # the new picture is centred on the new pan


def test_at_1x_there_is_no_margin_and_nothing_to_pan(qapp, tmp_path):
    m = _map(tmp_path)
    m.grab()
    assert (m._pic.mx, m._pic.my) == (0, 0)
    m.grab()
    assert m.picture_renders == 1


# ---------------------------------------------------------------- zoom

def test_wheel_zoom_previews_then_renders_once_after_the_timer(qapp, tmp_path):
    from PySide6.QtTest import QTest
    m = _map(tmp_path, zoom=2.0)
    m.grab()
    assert m.picture_renders == 1
    for _ in range(3):
        m.wheelEvent(_Wheel(1))
        assert m._zoom_timer.isActive()
        m.grab()                     # a soft preview of the saved picture
    assert m.picture_renders == 1 and m._pic.zoom == 2.0 and m._zoom > 2.0
    QTest.qWait(320)                 # the timer fires (update(); this widget is not shown)
    assert not m._zoom_timer.isActive()
    m.grab()
    assert m.picture_renders == 2 and m._pic.zoom == m._zoom
    m.grab()
    assert m.picture_renders == 2


def test_the_preview_is_the_saved_picture_scaled_about_the_cursor(qapp, tmp_path):
    m = _map(tmp_path, zoom=2.0)
    before = m.grab().toImage()
    m.wheelEvent(_Wheel(1, 150, 150))
    prev = m.grab().toImage()
    assert m.picture_renders == 1 and prev != before
    # the point under the cursor stays put, so its colour does
    assert prev.pixelColor(150, 150).name() == before.pixelColor(150, 150).name()


def test_zoom_limits_per_widget(qapp):
    from shared.maps.grid_map import GridMap
    from shared.maps.raster_map import RasterMiniMap
    from shared.maps.species_dist_map import DistributionMiniMap
    m = GridMap(geojson_path=None, maps_dir=None)
    m.resize(300, 300)
    for _ in range(40):
        m.wheelEvent(_Wheel(1))
    assert m._zoom == 40.0 and m._zoom_max == 40.0
    d = DistributionMiniMap(None, resizable=True)
    d.resize(300, 300)
    r = RasterMiniMap(None, resizable=True)
    r.resize(300, 300)
    for w in (d, r):
        for _ in range(40):
            w.wheelEvent(_Wheel(1))
        assert w._zoom == 8.0 and w._zoom_max == 8.0


def test_forty_times_on_the_gb_view_draws_squares_labels_and_snapped_layers(qapp, tmp_path):
    from PySide6.QtCore import QPointF
    from shared.maps.map_layers import SNAP
    m = _map(tmp_path)
    m.set_extent(gs.GB_LAND)
    m._vc_rings = {1: [[(440000, 210000), (470000, 210000), (470000, 240000), (440000, 240000),
                        (440000, 210000)]]}
    m._vc_names = {1: "Testshire"}
    m._geojson = "zoom40-test"
    m._zoom = 40.0
    x, y = m.fit().to_px(455000, 225000)             # the middle of SP52
    m._pan = QPointF(150 - x * 40, 150 - y * 40)
    m._clamp_pan()
    e0, n0, e1, n1 = m.visible_extent()
    assert 15000 < max(e1 - e0, n1 - n0) < 35000      # about 25 km across
    m.grab()
    assert m.picture_renders == 1
    (key,) = [c for c in m._layer_cache if c[0] == "woodland"]
    assert key[1] == "county" and all(v % SNAP == 0 for v in key[2])
    assert key[2][2] - key[2][0] <= 6 * SNAP          # a small area round the view, not the GB
    img = m._pic.pm.toImage()
    cx, cy = int(150 + m._pic.mx), int(150 + m._pic.my) + 30   # below the label
    assert img.pixelColor(cx, cy).name() == RED       # the square (its VC label is at the centre)
    m.set_vc_labels(False)
    off = m.grab().toImage()
    m.set_vc_labels(True)
    on = m.grab().toImage()
    assert m.picture_renders == 3 and on != off       # the label is in the picture


# ---------------------------------------------------------------- what is in the picture

def test_squares_are_in_the_picture_the_clicked_outline_is_drawn_live(qapp, tmp_path):
    m = _map(tmp_path)
    m.grab()
    n = m.picture_renders
    inside = m._pic.pm.toImage()
    fit = m.fit()
    x, y = fit.to_px(455000, 225000)
    assert inside.pixelColor(int(x), int(y)).name() == RED     # the square is in the picture
    m.set_selected("SP52")
    live = m.grab().toImage()
    assert m.picture_renders == n                     # selecting does not draw the picture again
    ex, ey = fit.to_px(450000, 225000)                # the square's left edge: the outline
    assert live.pixelColor(int(ex) - 1, int(ey)) != inside.pixelColor(int(ex) - 1, int(ey))
    assert m._pic.pm.toImage() == inside              # ... and it never gets into the picture
    m.set_selected(None)
    m.grab()
    assert m.picture_renders == n
    m.set_square_opacity(50)                          # the squares' opacity is in the picture
    m.grab()
    assert m.picture_renders == n + 1


def test_atlas_page_is_exact_and_never_uses_the_picture(qapp, tmp_path):
    m = _map(tmp_path)
    first = m.render_sheet("T", dpi=60, extent=BOX)
    assert m.picture_renders == 0 and not m._fast_fill
    m.grab()                                          # a screen picture (fills not antialiased)
    m._zoom = 3.0
    m.grab()
    m._zoom = 1.0
    second = m.render_sheet("T", dpi=60, extent=BOX)
    assert first == second                            # byte for byte, whatever the screen did
    ext, view = m.sheet_view(BOX, dpi=60)
    box = m._sheet_box(first.width(), first.height(), 60)
    fx = box.x() + box.width() * (455000 - view[0]) / (view[2] - view[0])
    fy = box.y() + box.height() * (view[3] - 235000) / (view[3] - view[1])
    wood = layers.style("woodland")[0]                # (455 km, 235 km): wood, not under the square
    got = first.pixelColor(int(fx), int(fy))
    assert abs(got.red() - wood.red()) <= 3 and abs(got.green() - wood.green()) <= 3


# ---------------------------------------------------------------- warm-up

def _two_vcs(m, key):
    a = [(10000, 10000), (50000, 10000), (50000, 60000), (10000, 60000), (10000, 10000)]
    b = [(50000, 10000), (90000, 10000), (90000, 60000), (50000, 60000), (50000, 10000)]
    m._vc_rings = {1: [a], 2: [b]}
    m._vc_names = {1: "One", 2: "Two"}
    m._geojson = key


def _wait_for(qapp, warm, seconds=20):
    import time
    end = time.time() + seconds
    while not warm.done and time.time() < end:
        qapp.processEvents()
        time.sleep(0.005)
    assert warm.done


def test_warm_up_fills_the_caches_in_the_background(qapp, tmp_path):
    m = _map(tmp_path)
    m.set_extent(gs.GB_LAND)
    _two_vcs(m, "warm-test-a")
    key = ("vc_topo", "warm-test-a", 300.0, "r5")
    assert not coast.has_split(key)
    m.show()
    qapp.processEvents()
    assert m._warm is not None
    _wait_for(qapp, m._warm)
    assert coast.has_split(key)
    assert ("vc", "warm-test-a", 300.0) in vc_topology._SNAP_CACHE
    assert any(c[0] == "land" and c[1] == "gb" for c in m._layer_cache)   # GB-level layer path
    m.close()


def test_painting_before_the_warm_up_finishes_gives_the_same_map(qapp, tmp_path):
    m = _map(tmp_path)
    _two_vcs(m, "warm-test-b")
    m.show()
    early = m.grab().toImage()                        # before the warm-up has run a step
    _wait_for(qapp, m._warm)
    m._pic = None
    late = m.grab().toImage()
    assert early == late
    topo = [r for rs in m._topo().values() for r in rs]
    plain = coast.split_edges(topo, lines=vc_topology.unique_chains(topo))
    assert coast._SPLIT_CACHE[("vc_topo", "warm-test-b", 300.0, "r5")] == plain
    m.close()


def test_ten_km_grid_appears_when_zoomed_in_on_the_gb_view():
    """18 Oct: at 40x on the GB view the 10 km lines show, as in the county view."""
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from unittest import mock
    from shared.maps.grid_map import GridMap
    m = GridMap(geojson_path=None, maps_dir=None)
    m.resize(400, 400)
    fit = m.fit()
    drawn = []
    p = mock.MagicMock()
    p.setPen.side_effect = lambda pen: drawn.append(round(pen.widthF(), 2))
    m._layer_view = fit.extent                      # whole GB on screen: 100 km only
    m._draw_grid(p, fit, 1.0)
    assert 0.3 not in drawn
    drawn.clear()
    e0, n0 = fit.extent[0], fit.extent[1]
    m._layer_view = (e0, n0, e0 + 25000, n0 + 25000)  # 25 km across, as at 40x
    m._draw_grid(p, fit, 1.0)
    assert 0.3 in drawn
