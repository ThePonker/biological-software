"""Mapping tab, Round 4 (11 Oct 2026): VC labels drawn in device pixels (garbled when zoomed on
Windows), labels nudged off recorded squares, VC boundary lines with a remembered switch.

Code-path tests, not font metrics (offscreen Qt on Windows has no fonts).
"""
import os

import pytest

import paths

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HAVE_VC = paths.VC_GEOJSON.exists()
needs_vc = pytest.mark.skipif(not HAVE_VC, reason="needs the vice-county geojson")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def settings_sandbox(qapp):
    from PySide6.QtCore import QCoreApplication, QSettings
    org = QCoreApplication.organizationName()
    QCoreApplication.setOrganizationName("ObservatumTests_mapping_r4")
    QSettings().clear()
    yield
    QSettings().clear()
    QCoreApplication.setOrganizationName(org)


class Fit:
    def to_px(self, e, n):
        return e, n


def _recording_painter(img):
    """A QPainter that records the transform in force for every label stroke / fill and
    refuses drawText (labels are paths now)."""
    from PySide6.QtGui import QPainter

    class Rec(QPainter):
        def __init__(self, dev):
            super().__init__(dev)
            self.calls = []

        def strokePath(self, path, pen):
            self.calls.append(("stroke", self.transform().isIdentity(), path))
            return super().strokePath(path, pen)

        def fillPath(self, path, brush):
            self.calls.append(("fill", self.transform().isIdentity(), path))
            return super().fillPath(path, brush)

        def drawText(self, *a):
            raise AssertionError("VC labels must not use drawText")
    return Rec(img)


# ---------------------------------------------------------------- 1: device-pixel labels

def test_screen_labels_drawn_unscaled_in_device_pixels(qapp):
    """Under a 5x zoom transform the label is laid out where its point lands on the device,
    at the same pixel size as unzoomed, drawn with the transform reset, and the halo and the
    letters are the same path."""
    from PySide6.QtGui import QImage
    from shared.maps.vc_labels import draw_labels
    out = {}
    for zoom in (1.0, 5.0):
        img = QImage(1200, 1200, QImage.Format.Format_ARGB32)
        p = _recording_painter(img)
        p.scale(zoom, zoom)
        shown = draw_labels(p, Fit(), [(56, (100.0, 100.0), 1.0)], {56: "Nottinghamshire"}, 1000)
        calls = p.calls
        p.end()
        (_vc, text, rect, _strong), = shown
        assert text == "Nottinghamshire (VC56)"
        assert rect.center().x() == pytest.approx(100 * zoom) and \
            rect.center().y() == pytest.approx(100 * zoom)          # device coordinates
        assert [c[0] for c in calls] == ["stroke", "fill"]
        assert all(identity for _k, identity, _p in calls)          # drawn unscaled
        assert calls[0][2] == calls[1][2]                           # halo == letters' path
        out[zoom] = (rect.width(), rect.height())
    assert out[1.0] == out[5.0]                                     # size ignores the zoom


def test_label_font_is_a_whole_pixel_size_for_the_device(qapp):
    from PySide6.QtGui import QImage
    from shared.maps import grid_squares as gs
    from shared.maps.vc_labels import NAME_PT, label_font
    screen = QImage(10, 10, QImage.Format.Format_ARGB32)
    screen.setDotsPerMeterX(gs.dots_per_metre(96))
    screen.setDotsPerMeterY(gs.dots_per_metre(96))
    page = QImage(10, 10, QImage.Format.Format_ARGB32)
    page.setDotsPerMeterX(gs.dots_per_metre(300))
    page.setDotsPerMeterY(gs.dots_per_metre(300))
    f96, f300 = label_font(NAME_PT, False, screen), label_font(NAME_PT, False, page)
    assert f96.pixelSize() == round(NAME_PT * 96 / 72)              # 11 px, no fractional pt
    assert f300.pixelSize() == round(NAME_PT * 300 / 72)            # the page as before
    assert f96.pointSizeF() == -1                                   # set in pixels, not points


@needs_vc
def test_grid_map_screen_and_page_use_the_device_path(qapp, monkeypatch):
    """GridMap.draw passes no text scale: the label size comes from the device, the same at
    every zoom on screen."""
    import shared.maps.grid_map as gm
    from PySide6.QtCore import QPointF
    seen = []
    real = gm.draw_labels

    def spy(p, fit, points, names, span, **kw):
        assert "text_scale" not in kw and "k" not in kw
        res = real(p, fit, points, names, span, **kw)
        seen.append({t: (round(r.width()), round(r.height())) for _v, t, r, _s in res})
        return res
    monkeypatch.setattr(gm, "draw_labels", spy)
    m = gm.GridMap(geojson_path=str(paths.VC_GEOJSON), maps_dir=str(paths.MAPS_DIR))
    m.resize(600, 800)
    m.set_extent(m.vc_extent(23))
    m.grab()
    m._zoom, m._pan = 2.0, QPointF(-300, -400)
    m.grab()
    both = set(seen[0]) & set(seen[1])
    assert both                                                     # some label in both
    assert all(seen[0][t] == seen[1][t] for t in both)


# ---------------------------------------------------------------- 2: off recorded squares

def _place(occupied, inside=None):
    from PySide6.QtGui import QImage, QPainter
    from shared.maps.vc_labels import draw_labels
    img = QImage(400, 400, QImage.Format.Format_ARGB32)
    p = QPainter(img)
    shown = draw_labels(p, Fit(), [(23, (200.0, 200.0), 1.0)], {}, 1e6,
                        occupied=occupied, inside=inside)
    p.end()
    return shown


def test_label_nudged_off_a_recorded_square_when_it_can(qapp):
    from PySide6.QtCore import QRectF
    square = QRectF(185, 185, 30, 30)                    # a recorded square under the label
    (_vc, _t, rect, strong), = _place(lambda r: r.intersects(square))
    assert not rect.intersects(square) and not strong
    assert abs(rect.center().x() - 200) + abs(rect.center().y() - 200) < 80   # nearby


def test_label_stays_inside_its_vc_else_keeps_its_place_with_a_strong_halo(qapp):
    from PySide6.QtCore import QRectF
    square = QRectF(185, 185, 30, 30)
    (_vc, _t, rect, strong), = _place(lambda r: r.intersects(square), inside=lambda vc, c: False)
    assert rect.center().x() == pytest.approx(200) and strong       # nowhere in its VC
    (_vc, _t, rect, strong), = _place(lambda r: True)                # squares everywhere
    assert rect.center().x() == pytest.approx(200) and strong
    (_vc, _t, rect, strong), = _place(lambda r: False)               # free: unmoved, normal
    assert rect.center().x() == pytest.approx(200) and not strong


@needs_vc
def test_grid_map_label_tests_see_squares_and_vcs(qapp):
    """GridMap's occupied / inside callbacks (device coordinates through the painter)."""
    from PySide6.QtCore import QPointF, QRectF
    from PySide6.QtGui import QImage, QPainter
    from shared.maps import grid_squares as gs
    from shared.maps.grid_map import GridMap
    m = GridMap(geojson_path=str(paths.VC_GEOJSON), maps_dir=str(paths.MAPS_DIR))
    m.resize(600, 800)
    m.set_extent(m.vc_extent(23))
    m.set_squares({"SP50": {"count": 1, "fill": "#000000"}}, gs.HECTAD)
    img = QImage(600, 800, QImage.Format.Format_ARGB32)
    p = QPainter(img)
    p.scale(2.0, 2.0)                                               # a zoomed screen
    fit = m.fit()
    occupied, inside = m._label_tests(p, fit)
    x, y = fit.to_px(455000, 205000)                                # in SP50, Oxford
    dev = p.transform().map(QPointF(x, y))
    assert occupied(QRectF(dev.x() - 2, dev.y() - 2, 4, 4))
    x2, y2 = fit.to_px(435000, 225000)                              # SP32, not recorded
    dev2 = p.transform().map(QPointF(x2, y2))
    assert not occupied(QRectF(dev2.x() - 2, dev2.y() - 2, 4, 4))
    assert inside(23, dev) and not inside(22, dev)
    p.end()


# ---------------------------------------------------------------- 3: VC boundaries

def test_boundaries_switch_default_on_remembered_and_next_to_labels(settings_sandbox):
    from PySide6.QtCore import QSettings
    from src.views.mapping.display_bar import VC_BOUNDS_SETTING, MapDisplayBar
    bar = MapDisplayBar()
    assert bar.vc_boundaries() is True                              # default on
    lay = bar.layout()
    assert lay.indexOf(bar.vc_bounds_check) == lay.indexOf(bar.vc_labels_check) + 1
    assert bar.vc_bounds_check.text() == "VC boundaries"
    got = []
    bar.vc_boundaries_changed.connect(got.append)
    bar.vc_bounds_check.setChecked(False)
    assert got == [False]
    QSettings().sync()
    assert QSettings().value(VC_BOUNDS_SETTING, True, type=bool) is False
    assert MapDisplayBar().vc_boundaries() is False                 # remembered
    bar.vc_bounds_check.setChecked(True)
    assert MapDisplayBar().vc_boundaries() is True


@needs_vc
def test_boundaries_drawn_below_the_selected_outline_and_switchable(qapp, monkeypatch):
    import shared.maps.grid_map as gm
    order = []
    rb, ro = gm.draw_boundaries, gm.draw_outline
    monkeypatch.setattr(gm, "draw_boundaries", lambda *a, **k: (order.append("bounds"), rb(*a, **k)))
    monkeypatch.setattr(gm, "draw_outline", lambda *a, **k: (order.append("outline"), ro(*a, **k)))
    m = gm.GridMap(geojson_path=str(paths.VC_GEOJSON), maps_dir=str(paths.MAPS_DIR))
    m.resize(600, 800)
    m.set_vc_labels(False)
    m.set_extent(m.vc_extent(23))
    m.set_outlined_vc(23)
    with_lines = m.render_sheet("T", dpi=60)
    assert order == ["bounds", "outline"]                           # green outline on top
    m.set_vc_boundaries(False)
    order.clear()
    without = m.render_sheet("T", dpi=60)
    assert order == ["outline"] and without != with_lines


def test_boundary_colour_comes_from_the_theme(qapp, monkeypatch):
    import shared.maps.vc_labels as vl

    class T:
        SLATE, CARD = "#000000", "#ffffff"
    monkeypatch.setattr(vl, "theme", T)
    c = vl.boundary_colour()
    assert (c.red(), c.green(), c.blue()) == (84, 84, 84)           # a third towards the card


@needs_vc
def test_tab_wires_the_boundaries_switch(settings_sandbox):
    """The display bar's switch reaches the map (the tab connects it at start-up)."""
    if not (paths.OBSERVATUM_DB.exists() and paths.UKSI_DB.exists()):
        pytest.skip("needs the data copies")
    from src.views.mapping.mapping_tab import MappingTab
    tab = MappingTab()
    assert tab.map_widget._vc_bounds_on is tab.display_bar.vc_boundaries()
    tab.display_bar.vc_bounds_check.setChecked(False)
    assert tab.map_widget._vc_bounds_on is False
    tab.display_bar.vc_bounds_check.setChecked(True)
    assert tab.map_widget._vc_bounds_on is True
    assert tab.display_bar.districts_check.isEnabled() == tab.map_widget.has_districts()
    tab.display_bar.districts_check.setChecked(True)
    assert tab.map_widget._districts_on is True
    tab.display_bar.districts_check.setChecked(False)
    tab.close()


# ---------------------------------------------------------------- 4: the thin lines

def test_coast_leaves_out_borders_shared_by_two_land_rings(qapp):
    """Two neighbouring 'VCs' (10 km squares side by side): their shared border is inland,
    so the coast is only the outside, never the line between them."""
    from shared.maps.coast import coast_chains
    west = [(100000, 100000), (100000, 110000), (110000, 110000), (110000, 100000),
            (100000, 100000)]
    east = [(110000, 100000), (110000, 110000), (120000, 110000), (120000, 100000),
            (110000, 100000)]
    chains = coast_chains([west, east])
    segs = {tuple(sorted((c[i], c[i + 1]))) for c in chains for i in range(len(c) - 1)}
    shared = tuple(sorted(((110000, 100000), (110000, 110000))))
    assert shared not in segs
    assert len(segs) == 6                                           # the six outer edges


def _outline_dir(tmp_path):
    """A maps folder whose gb_outline.json is two neighbouring 'districts' (10 km squares)."""
    import json
    west = [[100000, 100000], [100000, 110000], [110000, 110000], [110000, 100000],
            [100000, 100000]]
    east = [[110000, 100000], [110000, 110000], [120000, 110000], [120000, 100000],
            [110000, 100000]]
    (tmp_path / "gb_outline.json").write_text(json.dumps(
        {"rings": [west, east], "bounds": [100000, 100000, 120000, 110000]}))
    return str(tmp_path)


def _segs(chains):
    return {tuple(sorted((tuple(c[i]), tuple(c[i + 1])))) for c in chains
            for i in range(len(c) - 1)}


@needs_vc
def test_with_gb_outline_coast_is_sea_edges_and_districts_switch(qapp, tmp_path, monkeypatch):
    """Wil's PC: gb_outline.json (ONS districts). The coast leaves out the district borders;
    "Districts (modern)" draws them, off by default; the page credits the coastline."""
    import shared.maps.grid_map as gm
    from shared.maps.atlas_sheet import COAST_CREDIT
    m = gm.GridMap(geojson_path=str(paths.VC_GEOJSON), maps_dir=_outline_dir(tmp_path))
    m.resize(300, 400)
    assert m.has_districts() and m._land_source[0] == "outline"
    shared = tuple(sorted(((110000.0, 100000.0), (110000.0, 110000.0))))
    assert shared not in _segs(m._chains("coast")) and len(_segs(m._chains("coast"))) == 6
    assert shared in _segs(m._chains("districts"))
    drawn = []
    real = m._lines
    monkeypatch.setattr(m, "_lines", lambda name, fit: (drawn.append(name), real(name, fit))[1])
    m.grab()
    assert "coast" in drawn and "districts" not in drawn               # default off
    drawn.clear()
    m.set_districts(True)
    m.grab()
    assert "districts" in drawn
    assert COAST_CREDIT in m.credit_line("x")


@needs_vc
def test_without_gb_outline_land_is_the_vcs_and_no_districts(qapp, tmp_path, monkeypatch):
    import shared.maps.grid_map as gm
    from shared.maps.atlas_sheet import COAST_CREDIT
    m = gm.GridMap(geojson_path=str(paths.VC_GEOJSON), maps_dir=str(tmp_path))   # no file
    m.resize(300, 400)
    assert not m.has_districts() and m._land_source[0] == "vc"
    drawn = []
    real = m._lines
    monkeypatch.setattr(m, "_lines", lambda name, fit: (drawn.append(name), real(name, fit))[1])
    m.set_districts(True)                                            # nothing to draw
    m.grab()
    assert "districts" not in drawn and {"coast", "vc_inland"} <= set(drawn)
    assert COAST_CREDIT not in m.credit_line()
    coast, inland = len(m._chains("coast")), len(m._chains("districts"))
    assert coast and inland                     # VC borders are inland: never drawn as coast


@pytest.mark.skipif(not (paths.MAPS_DIR / "gb_outline.json").exists(),
                    reason="needs data/maps/gb_outline.json")
def test_real_gb_outline_coast_leaves_out_most_district_edges(qapp):
    from shared.maps.coast import split_edges
    from shared.maps.species_dist_map import _load_gb_outline
    land, _b = _load_gb_outline(str(paths.MAPS_DIR))
    rings = land[0]
    coast, inland = split_edges(rings)
    n_coast = sum(len(c) - 1 for c in coast)
    n_inland = sum(len(c) - 1 for c in inland)
    assert n_coast + n_inland == sum(len(r) - 1 for r in rings)
    assert n_inland > 0.3 * (n_coast + n_inland)                   # districts: inland


def test_districts_switch_default_off_remembered_and_greyed_without_file(settings_sandbox):
    from PySide6.QtCore import QSettings
    from src.views.mapping.display_bar import DISTRICTS_SETTING, MapDisplayBar
    bar = MapDisplayBar()
    assert bar.districts() is False and bar.districts_check.text() == "Districts (modern)"
    lay = bar.layout()
    assert lay.indexOf(bar.districts_check) == lay.indexOf(bar.vc_bounds_check) + 1
    bar.districts_check.setChecked(True)
    QSettings().sync()
    assert QSettings().value(DISTRICTS_SETTING, False, type=bool) is True
    assert MapDisplayBar().districts() is True
    bar.districts_check.setChecked(False)
    bar.set_districts_available(False)
    assert not bar.districts_check.isEnabled()
