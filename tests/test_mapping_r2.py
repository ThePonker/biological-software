"""Mapping tab, round 2 (10 Oct 2026 evening): items L8, L9, L11, L13/L31, L14/L32, L30, L33,
L34 and decisions 10 and 13 (agents/ITEMS_37.md, DECISIONS_38.md).

Pure parts on made-up data; the tab on the data copies (read-only), offscreen, at 1920 x 1080.
"""
import json
import os

import pytest

import paths

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HAVE_DATA = paths.OBSERVATUM_DB.exists() and paths.UKSI_DB.exists()
needs_data = pytest.mark.skipif(not HAVE_DATA, reason="needs data/observatum.db and uksi.db")

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
    QCoreApplication.setOrganizationName("ObservatumTests_mapping_r2")
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
    t.resize(1920, 1040)
    t.show()
    yield t
    t.close()


def _pump():
    from PySide6.QtWidgets import QApplication
    for _ in range(3):
        QApplication.processEvents()


# ---------------------------------------------------------------- L8: sources as tick boxes

def test_normalise_sources_and_labels():
    from src.services.map_selection import BASE_SOURCES, normalise_sources
    from src.views.mapping.source_picker import sources_label
    assert normalise_sources("all") == BASE_SOURCES
    assert normalise_sources(["contributed", "personal"]) == ("personal", "contributed")
    assert normalise_sources("nonsense") == ("personal",)          # as the old fallback
    assert normalise_sources([]) == ()
    assert sources_label("personal") == "Personal records"
    assert sources_label(["scheme"]) == "Recording Scheme"
    assert sources_label(["personal", "contributed"]) == "Personal + Contributed records"
    assert sources_label(list(BASE_SOURCES)) == "All records"


def test_source_picker_all_box(qapp):
    from src.views.mapping.source_picker import MapSourcePicker
    p = MapSourcePicker()
    seen = []
    p.sources_changed.connect(seen.append)
    assert p.sources() == ["personal"] and not p.all_box.isChecked()
    p.boxes["contributed"].setChecked(True)
    assert seen[-1] == ["personal", "contributed"]
    p.all_box.click()                                   # All = every box
    assert len(p.sources()) == 5 and p.all_box.isChecked()
    p.boxes["scheme"].setChecked(False)                 # one off: All goes off
    assert not p.all_box.isChecked()
    p.all_box.click()
    p.all_box.click()                                   # All off: back to Personal
    assert p.sources() == ["personal"]


@needs_data
def test_several_sources_each_record_once():
    """Personal + Insect Collection: a specimen with its own Personal observation is shown as
    that observation (as 'All' does); five ticked == 'all' exactly."""
    from src.services import map_selection as ms
    per = ms.fetch([], "personal")
    col = ms.fetch([], "collection")
    both = ms.fetch([], ["personal", "collection"])
    keys = {(r["table"], r["id"]) for r in both.records}
    assert len(keys) == len(both.records)
    n_spec = sum(1 for r in both.records if r["table"] == "specimens")
    assert sum(1 for r in both.records if r["table"] == "observations") == len(per.records)
    assert n_spec + both.merged == len(col.records)            # every specimen accounted for
    assert both.embargoed == col.embargoed
    a = ms.fetch([], "all")
    five = ms.fetch([], list(ms.BASE_SOURCES))
    assert sorted((r["table"], r["id"]) for r in a.records) == \
        sorted((r["table"], r["id"]) for r in five.records)
    assert (a.embargoed, a.merged) == (five.embargoed, five.merged)
    pc = ms.fetch([], ["personal", "contributed"])
    assert len(pc.records) == len(per.records) + len(ms.fetch([], "contributed").records)


@needs_data
def test_tab_sources_drive_map_and_subtitle(tab):
    fp = tab.filter_panel
    fp.clear_all()
    fp.source_picker.set_sources(["personal", "contributed"])
    fp.selection_box.add(dict(RUTPELA))
    assert {r["source"] for r in tab._records} <= {"Personal", "Contributed"}
    assert "Personal + Contributed records" in tab.map_header.subtitle.text()
    assert not fp.project_combo.isEnabled() and not fp.embargo_check.isEnabled()
    fp.source_picker.boxes["commercial"].setChecked(True)
    assert fp.project_combo.isEnabled() and fp.embargo_check.isEnabled()
    assert not hasattr(tab.toolbar, "data_combo")
    fp.clear_all()


# ---------------------------------------------------------------- L9: stale date error

def test_date_error_goes_when_dates_put_right(qapp, settings_sandbox):
    if not HAVE_DATA:
        pytest.skip("needs data copies")
    from src.views.mapping.filter_panel import MapFilterPanel
    fp = MapFilterPanel()
    fp.date_from.setText("20x0")
    f, err = fp.filters()
    assert f is None and fp.date_error.text()
    fp.date_from.setText("2020")                       # put right: gone at once
    assert not fp.date_error.text() and fp.date_error.isHidden()
    fp.date_from.setText("2021")
    fp.date_to.setText("2019")
    assert fp.filters()[0] is None and "after the To date" in fp.date_error.text()
    fp.date_to.clear()                                  # emptied: gone too
    assert not fp.date_error.text() and fp.date_error.isHidden()
    fp.date_from.setText("bad")                         # a new error waits for Generate
    assert not fp.date_error.text()


# ---------------------------------------------------------------- L11 / L30: layout

@needs_data
def test_divider_and_panel_never_scrolls_sideways(tab):
    from PySide6.QtWidgets import QLabel
    fp = tab.filter_panel
    assert tab.splitter.widget(0) is fp and fp.minimumWidth() == fp.MIN_WIDTH
    fp.project_combo.addItem("A very long Commercial project name, phase two, 2026 survey "
                             "season for testing the panel width")
    for w in (fp.site_edit, fp.project_combo, fp.vc_combo):
        w.setFocus()
        _pump()
    for width in (fp.MIN_WIDTH, 340, 520):
        tab.splitter.setSizes([width, 1920 - width])
        _pump()
        bar = fp.scroll.horizontalScrollBar()
        assert bar.maximum() == 0 and bar.value() == 0
        assert fp.scroll.widget().width() <= fp.scroll.viewport().width()
        vc = next(lab for lab in fp.findChildren(QLabel) if lab.text() == "Vice County")
        assert vc.mapTo(fp, vc.rect().topLeft()).x() == 16           # not cut on the left
    fp.project_combo.removeItem(fp.project_combo.count() - 1)


@needs_data
def test_divider_remembered(tab, settings_sandbox):
    from PySide6.QtCore import QSettings
    from src.views.mapping.mapping_tab import SPLITTER_SETTING, MappingTab
    tab.splitter.setSizes([450, 1470])
    _pump()
    tab._save_splitter()
    assert QSettings().value(SPLITTER_SETTING)
    t2 = MappingTab()
    t2.resize(1920, 1040)
    t2.show()
    _pump()
    assert abs(t2.splitter.sizes()[0] - tab.splitter.sizes()[0]) <= 2
    t2.close()


@needs_data
def test_long_legend_does_not_widen_the_map_side(tab):
    side = tab.splitter.widget(1)
    before = side.minimumSizeHint().width()
    tab.display_bar.set_legend([("#123456", f"Agapanthia villosoviridescens {i}")
                                for i in range(12)])
    _pump()
    assert side.minimumSizeHint().width() == before
    assert "Agapanthia villosoviridescens 11" in tab.display_bar.legend_box.toolTip()
    tab.display_bar.set_legend(tab._legend)


# ---------------------------------------------------------------- L13/31, L14/32: export

def _grid_map():
    from shared.maps.grid_map import GridMap
    from shared.maps import grid_squares as gs
    m = GridMap(geojson_path=None, maps_dir=None)
    m.resize(600, 800)
    m.set_squares({"SP46": {"count": 3, "fill": "#9a7555"},
                   "TQ37": {"count": 1, "fill": "#9a7555"}}, gs.HECTAD)
    return m


def test_selected_outline_never_printed(qapp):
    m = _grid_map()
    plain = m.render_sheet("T", dpi=60)
    m.set_selected("SP46")
    assert m.render_sheet("T", dpi=60) == plain
    m.set_squares({"TQ37": {"count": 1, "fill": "#9a7555"}}, 10000)   # its square gone
    assert m._selected is None


def test_export_full_extent_whatever_the_zoom(qapp):
    from PySide6.QtCore import QPointF
    m = _grid_map()
    full = m.render_sheet("T", dpi=60)                 # default: full extent
    m._zoom, m._pan = 4.0, QPointF(-600, -1200)
    assert m.render_sheet("T", dpi=60, extent="full") == full
    assert m.render_sheet("T", dpi=60) == full
    assert m.render_sheet("T", dpi=60, extent="current") != full
    assert m.full_extent() == m._extent


@needs_data
def test_tab_outline_cleared_and_export_extent(tab, monkeypatch):
    fp = tab.filter_panel
    fp.clear_all()
    fp.selection_box.add(dict(RUTPELA))
    sq = next(iter(tab._squares))
    tab.map_widget.set_selected(sq)
    fp.selection_box.add({"kind": "taxon", "tvk": "NHMSYS0020151160",
                          "scientific_name": "Agapanthia villosoviridescens", "rank": "species"})
    assert tab.map_widget._selected is None            # the map was made again
    tab.map_widget.set_selected(next(iter(tab._squares)))
    fp.selection_box.remove(1)                         # its taxon removed
    assert tab.map_widget._selected is None
    assert tab.toolbar.export_extent() == "full"
    seen = {}
    real = tab.map_widget.render_sheet

    def spy(*a, **k):
        seen.update(k)
        return real(*a, **{**k, "dpi": 30})
    monkeypatch.setattr(tab.map_widget, "render_sheet", spy)
    tab.render_atlas(tab.toolbar.export_extent())
    assert seen["extent"] == "full"
    tab.toolbar.extent_combo.setCurrentIndex(1)
    tab.render_atlas(tab.toolbar.export_extent())
    assert seen["extent"] == "current"
    tab.toolbar.extent_combo.setCurrentIndex(0)
    fp.clear_all()


# ---------------------------------------------------------------- L33: Clear all, title

@needs_data
def test_clear_all_in_one_go(tab):
    from src.views.mapping.header import NO_TAXON_TITLE, selection_title
    fp = tab.filter_panel
    fp.source_picker.set_sources(["personal", "commercial"])
    fp.selection_box.add(dict(RUTPELA))
    fp.vc_combo.setCurrentIndex(fp.vc_combo.findData(23))
    fp.recorder_edit.setText("Heeney")
    fp.site_edit.setText("Wood")
    fp.date_from.setText("2020")
    fp.project_combo.setCurrentIndex(1)
    fp.embargo_check.setChecked(True)
    assert tab.toolbar.get_view() == "county"
    calls = []
    real = tab._generate_map
    tab._generate_map = lambda *a: (calls.append(1), real())
    try:
        fp.clear_all_btn.click()
    finally:
        del tab._generate_map
    assert calls == []                                 # no query per box
    assert fp.selection() == [] and fp.sources() == ["personal"]
    assert fp.vc_combo.currentIndex() == 0 and fp.project_combo.currentIndex() == 0
    assert not any(b.text() for b in (fp.recorder_edit, fp.site_edit, fp.date_from, fp.date_to))
    assert not fp.embargo_check.isChecked() and not fp.project_combo.isEnabled()
    assert tab.toolbar.get_view() == "national" and not tab._squares and tab._result is None
    assert tab.map_header.title.text() == NO_TAXON_TITLE == "All records (no taxon chosen)"
    assert selection_title([]) == NO_TAXON_TITLE
    tab._generate_map()                                # every record, no taxon
    assert tab._title() == NO_TAXON_TITLE
    fp.clear_all()


# ---------------------------------------------------------------- decision 13: embargo wording

def test_map_note_embargo_wording():
    from types import SimpleNamespace as NS
    from src.views.mapping.map_notes import map_note
    held = NS(include_embargoed=False)
    shown = NS(include_embargoed=True)
    assert map_note(NS(embargoed=12, merged=0), held) == "12 embargoed not shown"
    assert map_note(NS(embargoed=12, merged=0), shown) == "includes 12 embargoed records"
    assert map_note(NS(embargoed=0, merged=0), shown) == "embargoed records included (none here)"
    assert map_note(NS(embargoed=0, merged=3), held) == "3 duplicate records shown once"


@needs_data
def test_embargo_ticked_said_on_subtitle_and_png(tab, monkeypatch):
    fp = tab.filter_panel
    fp.clear_all()
    fp.source_picker.set_sources(["commercial"])
    tab._generate_map()
    assert "embargoed not shown" in tab.map_header.subtitle.text()
    n_held = len(tab._records)
    fp.embargo_check.setChecked(True)                  # maps again by itself
    assert len(tab._records) > n_held
    assert "includes" in tab.map_header.subtitle.text()
    seen = {}
    real = tab.map_widget.render_sheet
    monkeypatch.setattr(tab.map_widget, "render_sheet",
                        lambda *a, **k: (seen.update(k), real(*a, **{**k, "dpi": 30}))[1])
    tab.render_atlas()
    assert "embargoed records" in seen["subtitle"] and "includes" in seen["subtitle"]
    fp.clear_all()


# ---------------------------------------------------------------- decision 10: tetrads

def test_hold_tetrads_and_wording():
    from shared.maps.grid_squares import is_tetrad_ref
    from src.views.mapping.map_notes import hold_tetrads, left_out_text
    assert is_tetrad_ref("SP46Q") and is_tetrad_ref("sp 46 q")
    assert not is_tetrad_ref("SP46") and not is_tetrad_ref("SP4060") and not is_tetrad_ref("")
    recs = [{"grid_ref": "SP46Q"}, {"grid_ref": "SP4060"}]
    out, held = hold_tetrads(recs, include=False)
    assert held == 1 and out == [recs[1]] and recs[0]["square"] is None
    out, held = hold_tetrads(recs, include=True)
    assert held == 0 and len(out) == 2
    text = left_out_text(10, 0, 0, 1, "hectad")
    assert "1 with a 2 km (tetrad) grid ref" in text and "to map it" in text


def test_tetrad_ref_on_hectad_and_tetrad_not_monad():
    """The rule once switched on (decision 10): as fine as its own ref or coarser only."""
    from shared.maps import grid_squares as gs
    from src.services import map_square_service as s
    recs = [{"grid_ref": "SP46Q", "year": 2020}]
    for size, mapped in ((gs.HECTAD, 1), (gs.TETRAD, 1), (gs.MONAD, 0)):
        squares, coarse, _u = s.squares_for([dict(r) for r in recs], size, lambda y: "x")
        assert len(squares) == mapped and coarse == 1 - mapped
    assert gs.square_for_ref("SP46Q", gs.TETRAD) == "SP46Q"


@needs_data
def test_tab_tetrad_switch(tab, settings_sandbox):
    from PySide6.QtCore import QSettings
    from src.views.mapping.filter_panel import TETRAD_SETTING
    from shared.maps.grid_squares import is_tetrad_ref
    fp = tab.filter_panel
    fp.clear_all()
    assert fp.tetrad_check.isChecked()                  # default on (mapped since 9 Oct)
    fp.tetrad_check.setChecked(False)
    fp.source_picker.set_sources(["scheme"])
    tab._generate_map()
    n_tet = sum(1 for r in tab._records if is_tetrad_ref(r["grid_ref"]))
    assert n_tet > 0                                    # 101 in the 9 Oct copy
    assert tab._tetrads_held == n_tet and "2 km (tetrad)" in tab.map_widget._message
    count_off = sum(sq["count"] for sq in tab._squares.values())
    fp.tetrad_check.setChecked(True)                    # maps again by itself
    assert QSettings().value(TETRAD_SETTING, type=bool) is True
    assert tab._tetrads_held == 0
    assert sum(sq["count"] for sq in tab._squares.values()) == count_off + n_tet
    fp.clear_all()


# ---------------------------------------------------------------- L34: tiny islets

def _geojson(tmp_path, geometry, vc=45):
    path = tmp_path / f"vc{vc}.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"VCNUMBER": vc}, "geometry": geometry}]}))
    return str(path)


def _ll(ring_en):
    from shared.osgb import osgb_en_to_wgs84
    return [list(osgb_en_to_wgs84(e, n)) for e, n in ring_en]


def _sq(e0, n0, size):            # clockwise = outer ring (the shapefile's rule)
    return [(e0, n0), (e0, n0 + size), (e0 + size, n0 + size), (e0 + size, n0), (e0, n0)]


@pytest.mark.parametrize("islet", [
    [(172000, 208000), (172300, 208100), (172000, 208000)],        # a 3-point ring
    [(172000, 208000), (172300, 208100)],                          # 2 points
    [(172000, 208000)],                                            # 1 point
])
def test_tiny_islet_kept_as_dot(tmp_path, islet):
    """The PC's older geojson stores The Smalls (VC45) as a 2-3 point ring inside one
    Polygon: it was dropped, so County view stopped ~13 km short on the west."""
    from shared.maps.vc_map import DOT_HALF, load_vc_polygons
    mainland = _sq(185000, 195000, 40000)
    geom = {"type": "Polygon", "coordinates": [_ll(mainland), _ll(islet)]}
    rings, bounds = load_vc_polygons(_geojson(tmp_path, geom))
    assert len(rings[45]) == 2
    minE = min(e for r in rings[45] for e, _n in r)
    assert minE == pytest.approx(172000 - DOT_HALF, abs=5)
    assert bounds[0] == pytest.approx(172000 - DOT_HALF, abs=5)
    from shared.maps.grid_map import GridMap
    ext = GridMap(geojson_path=_geojson(tmp_path, geom)).vc_extent(45)
    assert ext[0] < 172000                              # County view reaches the islet


def test_dot_islet_in_multipolygon_and_hole_still_dropped(tmp_path):
    from shared.maps.vc_map import load_vc_polygons
    mainland = _sq(185000, 195000, 40000)
    hole = _sq(195000, 205000, 5000)[::-1]              # anticlockwise = hole
    islet = [(172000, 208000), (172300, 208100), (172000, 208000)]
    geom = {"type": "MultiPolygon", "coordinates": [[_ll(mainland), _ll(hole)], [_ll(islet)]]}
    rings, _b = load_vc_polygons(_geojson(tmp_path, geom, vc=46))
    assert len(rings[46]) == 2                          # mainland + islet, no hole
    geom = {"type": "Polygon", "coordinates": [_ll(mainland), _ll(hole), _ll(islet)]}
    rings, _b = load_vc_polygons(_geojson(tmp_path, geom, vc=47))
    assert len(rings[47]) == 2
