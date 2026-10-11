"""Mapping tab, round 3 (11 Oct 2026): R9-4 reversed dates, R9-5 VC labels / selected VC
outline, R9-6 atlas footer in view (agents/ROUND9_ITEMS.md).

Pure parts on made-up data; the tab on the data copies (read-only), offscreen.
"""
import os

import pytest

import paths

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HAVE_DATA = paths.OBSERVATUM_DB.exists() and paths.UKSI_DB.exists()
HAVE_VC = paths.VC_GEOJSON.exists()
needs_data = pytest.mark.skipif(not HAVE_DATA, reason="needs data/observatum.db and uksi.db")
needs_vc = pytest.mark.skipif(not HAVE_VC, reason="needs the vice-county geojson")

RUTPELA = {"kind": "taxon", "tvk": "NHMSYS0020109270", "scientific_name": "Rutpela maculata",
           "rank": "species"}


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def settings_sandbox(qapp):
    from PySide6.QtCore import QCoreApplication, QSettings
    org = QCoreApplication.organizationName()
    QCoreApplication.setOrganizationName("ObservatumTests_mapping_r9")
    QSettings().clear()
    yield
    QSettings().clear()
    QCoreApplication.setOrganizationName(org)


@pytest.fixture(scope="module")
def tab(settings_sandbox):
    if not HAVE_DATA:
        pytest.skip("needs data copies")
    from src.views.mapping.mapping_tab import MappingTab
    t = MappingTab()
    t.resize(1600, 1000)
    t.show()
    yield t
    t.close()


# ---------------------------------------------------------------- R9-4: reversed dates

def test_date_problems_pure():
    from src.views.mapping.date_check import date_problems
    bad, b, rev = date_problems("2021", "2019")
    assert rev and b == {"From": "2021-01-01", "To": "2019-12-31"}
    assert bad == ["From (2021) is after To (2019): swap them or change one."]
    assert date_problems("2019", "2019")[2] is False            # one year, both ends
    assert date_problems("06/2020", "05/2020")[2] is True
    assert date_problems("2020", "")[0] == []
    bad, _b, rev = date_problems("20x0", "2019")
    assert not rev and "not understood" in bad[0]


def test_reversed_flagged_at_once_and_generate_blocked(qapp, settings_sandbox):
    if not HAVE_DATA:
        pytest.skip("needs data copies")
    from src.views.mapping.filter_panel import MapFilterPanel
    fp = MapFilterPanel()
    fp.date_from.setText("2021")
    assert fp.generate_btn.isEnabled() and not fp.date_error.text()   # one date: nothing yet
    fp.date_to.setText("2019")                                        # both set: flagged now
    assert "From (2021) is after To (2019)" in fp.date_error.text()
    assert not fp.date_error.isHidden() and not fp.generate_btn.isEnabled()
    assert fp.dates_reversed()
    fp.date_to.setText("2023")                                        # valid: gone at once
    assert not fp.date_error.text() and fp.date_error.isHidden() and fp.generate_btn.isEnabled()
    fp.date_to.setText("2019")
    fp.date_to.clear()                                                # emptied: gone too
    assert not fp.date_error.text() and fp.generate_btn.isEnabled()
    fp.date_to.setText("2019")
    fp.clear_all()                                                    # Clear all: button back
    assert fp.generate_btn.isEnabled() and not fp.date_error.text()
    fp.date_from.setText("bad")                       # not understood still waits for Generate
    assert not fp.date_error.text() and fp.generate_btn.isEnabled()


@needs_data
def test_reversed_dates_take_the_old_map_off(tab):
    fp = tab.filter_panel
    fp.clear_all()
    fp.selection_box.add(RUTPELA)
    assert tab._squares
    fp.date_from.setText("2021")
    fp.date_to.setText("2019")
    fp.date_to.returnPressed.emit()                   # Enter still asks for a map: refused
    assert not tab._squares and not tab.map_widget._squares
    assert tab.map_widget._message.startswith("Map not made. From (2021) is after To (2019)")
    assert "Rutpela" in tab.map_header.title.text()   # the chosen taxon is still named
    fp.date_to.setText("2025")
    tab._generate_map()
    assert tab._squares
    fp.clear_all()


# ---------------------------------------------------------------- R9-5: VC labels, outline

def test_interior_point_stays_inside_a_c_shape():
    from shared.maps.vc_labels import _inside, interior_point
    c_shape = [(0, 0), (100, 0), (100, 20), (20, 20), (20, 80), (100, 80), (100, 100),
               (0, 100), (0, 0)]
    e, n = interior_point(c_shape)
    assert _inside(e, n, c_shape)
    square = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
    assert interior_point(square) == pytest.approx((5, 5))


@needs_vc
def test_vc_names_and_label_points(qapp):
    from shared.maps.vc_labels import label_points
    from shared.maps.vc_map import load_vc_polygons, vc_names
    rings, _b = load_vc_polygons(str(paths.VC_GEOJSON))
    names = vc_names(str(paths.VC_GEOJSON))
    assert names[23] == "Oxfordshire" and names[112] == "Shetland" and names[45] == "Pembrokeshire"
    pts = label_points(rings)
    assert {vc for vc, _p, _a in pts} == set(rings)               # every VC, 112 included
    assert pts[0][2] >= pts[-1][2]                                # biggest placed first


def test_selected_vc_label_placed_first(qapp):
    """Two labels on the same spot: the bigger VC wins, unless the smaller one is selected."""
    from PySide6.QtGui import QImage, QPainter
    from shared.maps.vc_labels import draw_labels

    class Fit:
        def to_px(self, e, n):
            return e, n

    pts = [(1, (100.0, 100.0), 500.0), (2, (102.0, 101.0), 10.0)]   # biggest first
    for bold, shown, hidden in ((None, "1", "2"), (2, "2", "1")):
        img = QImage(200, 200, QImage.Format.Format_ARGB32)
        p = QPainter(img)
        texts = {t for _vc, t, _r, _s in draw_labels(p, Fit(), pts, {}, span_m=1e6, bold_vc=bold)}
        p.end()
        assert shown in texts and hidden not in texts


def _grid_map():
    from shared.maps.grid_map import GridMap
    m = GridMap(geojson_path=str(paths.VC_GEOJSON), maps_dir=str(paths.MAPS_DIR))
    m.resize(600, 800)
    return m


@needs_vc
def test_labels_and_outline_change_the_page_and_respect_the_switch(qapp):
    m = _grid_map()
    m.set_vc_labels(False)
    plain = m.render_sheet("T", dpi=60)
    m.set_vc_labels(True)
    labelled = m.render_sheet("T", dpi=60)
    assert labelled != plain                                       # labels printed
    m.set_vc_labels(False)
    assert m.render_sheet("T", dpi=60) == plain                    # switch off: none
    m.set_extent(m.vc_extent(23))
    no_outline = m.render_sheet("T", dpi=60)
    m.set_outlined_vc(23)
    assert m.render_sheet("T", dpi=60) != no_outline              # the border is printed
    m.set_outlined_vc(None)
    assert m.render_sheet("T", dpi=60) == no_outline              # none when no VC chosen


@needs_vc
def test_numbers_at_national_scale_names_zoomed(qapp, monkeypatch):
    import shared.maps.grid_map as gm
    seen = []
    real = gm.draw_labels

    def spy(p, fit, points, names, span, **kw):
        seen.append(span)
        return real(p, fit, points, names, span, **kw)
    monkeypatch.setattr(gm, "draw_labels", spy)
    from shared.maps.vc_labels import NAMES_SPAN_M
    m = _grid_map()
    m.grab()
    assert seen[-1] > NAMES_SPAN_M                                  # GB: numbers
    m.set_extent(m.vc_extent(23))
    m.grab()
    assert seen[-1] <= NAMES_SPAN_M                                 # County view: names
    m.render_sheet("T", dpi=60)
    assert seen[-1] <= NAMES_SPAN_M                                 # and on its page


@needs_data
def test_tab_outlines_the_chosen_vc_and_remembers_the_label_switch(tab):
    from PySide6.QtCore import QSettings
    fp = tab.filter_panel
    fp.clear_all()
    assert tab.map_widget._vc_outline is None
    fp.vc_combo.setCurrentIndex(fp.vc_combo.findData(23))
    assert tab.map_widget._vc_outline == 23 and tab.toolbar.get_view() == "county"
    fp.vc_combo.setCurrentIndex(fp.vc_combo.findData(45))
    assert tab.map_widget._vc_outline == 45
    assert tab.map_widget.vc_extent(45)[0] < 160000                 # The Smalls kept (L34)
    fp.vc_combo.setCurrentIndex(0)
    assert tab.map_widget._vc_outline is None
    fp.vc_combo.setCurrentIndex(fp.vc_combo.findData(23))
    fp.clear_all()                                                  # Clear all: outline goes
    assert tab.map_widget._vc_outline is None
    assert tab.display_bar.vc_labels() and tab.map_widget._vc_labels_on    # default on
    tab.display_bar.vc_labels_check.setChecked(False)
    assert not tab.map_widget._vc_labels_on
    QSettings().sync()
    assert QSettings().value("mapping/vc_labels", True, type=bool) is False
    tab.display_bar.vc_labels_check.setChecked(True)


@needs_data
def test_vc_list_holds_only_vcs_with_records():
    """VC112 (Shetland) is the one VC no record holds on the data copy, so it is not in the
    list (MAP8: one entry per VC held by the records) -- not a fault in the list."""
    from src.services.map_selection import vc_choices
    nums = [n for n, _t in vc_choices()]
    assert 45 in nums and 23 in nums
    assert 112 not in nums


# ---------------------------------------------------------------- R9-6: footer in view

def test_squares_in_box(qapp):
    from shared.maps.grid_map import GridMap
    m = GridMap()
    m.set_squares({"SP40": {"count": 3, "fill": "#000"}, "SU99": {"count": 2, "fill": "#000"},
                   "NT27": {"count": 1, "fill": "#000"}}, 10000)
    assert set(m.squares_in((440000, 190000, 460000, 215000))) == {"SP40"}
    assert set(m.squares_in((0, 0, 700000, 1300000))) == {"SP40", "SU99", "NT27"}


@needs_data
def test_footer_counts_in_view_on_a_current_view_page(tab):
    from PySide6.QtCore import QPointF
    fp = tab.filter_panel
    fp.clear_all()
    fp.selection_box.add(RUTPELA)
    whole = tab.atlas_footer("full", tab.map_widget.sheet_view("full")[1])
    n = len(tab._squares)
    assert whole.startswith(f"{n:,} hectads") and "(in view)" not in whole
    # not zoomed: "current" is the whole map, same wording
    assert tab.atlas_footer("current", tab.map_widget.sheet_view("current")[1]) == whole
    mw = tab.map_widget
    mw._zoom, mw._pan = 4.0, QPointF(-1600, -2300)               # the south midlands / Wales
    _ext, shown = mw.sheet_view("current")
    inside = mw.squares_in(shown)
    assert 0 < len(inside) < n
    foot = tab.atlas_footer("current", shown)
    recs = sum(tab._squares[s]["count"] for s in inside)
    assert foot.startswith(f"{len(inside):,} hectads, {recs:,} records") and foot.endswith(
        "(in view).")
    seen = {}
    real = mw.render_sheet

    def spy(*a, **kw):
        seen.update(kw)
        return real(*a, **kw)
    mw.render_sheet = spy
    try:
        tab.render_atlas("current")
    finally:
        del mw.render_sheet
    assert seen["footer"] == foot and seen["extent"] == "current"
    mw._zoom, mw._pan = 1.0, QPointF(0, 0)
    fp.clear_all()
