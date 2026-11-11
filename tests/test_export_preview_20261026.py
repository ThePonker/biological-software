"""Map export preview (26 Oct 2026): shared/maps/map_stats.py, the page's extras panel and the
export preview dialog. Small made-up records; nothing from Wil's data."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from shared.maps import grid_squares as gs  # noqa: E402
from shared.maps import map_stats  # noqa: E402


def rec(ref, date="", species="sp:a", person="", vc=None, date_type=None, **kw):
    r = {"grid_ref": ref, "date": date, "species": species, "person": person, "vc": vc,
         "year": int(date[:4]) if date[:4].isdigit() else None}
    if date_type:
        r["date_type"] = date_type
    r.update(kw)
    return r


def square_up(records):
    from src.services import map_square_service as svc
    squares, _c, _u = svc.squares_for(records, gs.HECTAD, lambda y: "recent")
    return squares


def sample():
    return [
        rec("SP4020", "1898-05-12", "sp:a", "A. Smith", 23),
        rec("SP4021", "1950-07-01", "sp:b", " A. Smith ", 23),          # same hectad SP42, recorder trimmed
        rec("SU5010", "1949-12-31", "sp:a", "b jones", 22),
        rec("SU5011", "2025-07-03", "sp:c", "B Jones", 22),
        rec("SU5012", "2025-07", "sp:c", "", None),                     # month only (text)
        rec("SU5013", "2021-06-01", "sp:c", "  ", 24, date_type="Y"),   # vague: year only
        rec("SU5014", "", None, "C. Day", None),                        # no date, no species
        rec("NT2070", "2010-02-02", "sp:a", "C. Day", 83, date_type="D"),
    ]


def test_parse_when_vague_dates():
    p = map_stats.parse_when
    assert p("1898-05-12") == (1898, 5, 12)
    assert p("1898-05-12", "D") == (1898, 5, 12)
    assert p("1956-06-01", "O") == (1956, 6, None)
    assert p("1956-06-01", "Y") == (1956, None, None)
    assert p("1956-06-01", "DD") == (1956, None, None)
    assert p("1956-06") == (1956, 6, None)
    assert p("1956") == (1956, None, None)
    assert p("1956-13-40") == (1956, None, None)
    assert p("1956-02-30") == (1956, 2, None)
    assert p("") is None and p("n/a") is None and p("0500-01-01") is None


def test_every_stat():
    recs = sample()
    squares = square_up(recs)
    st = map_stats.compute(recs, squares)
    assert st.records == 8
    assert st.species == 3                       # sp:a, sp:b, sp:c; the unnamed one not counted
    assert st.squares == len(squares) == 3       # SP42, SU51, NT27
    assert st.vice_counties == 4                 # 23, 22, 24, 83 (None not counted)
    assert st.recorders == 3                     # a. smith, b jones (any case), c. day; blanks not
    assert st.first == (1898, 5, 12)
    assert st.last == (2025, 7, 3)
    assert dict(st.decades) == {"pre-1950": 2, "1950–79": 1, "1980–99": 0,
                                "2000–09": 0, "2010–19": 1, "2020–": 3}
    assert st.undated == 1
    # months: single days only -> 1898 May, 1950 Jul, 1949 Dec, 2025 Jul 3, 2010 Feb
    assert st.months == [0, 1, 0, 0, 1, 0, 2, 0, 0, 0, 0, 1]
    assert sum(st.months) + st.no_month == st.records
    assert st.no_month == 3                      # month-only, year-only and undated


def test_last_prefers_the_later_day_and_vague_sorts_first():
    recs = [rec("SP4020", "2025-07-03"), rec("SP4021", "2025-07", date_type="O"),
            rec("SP4022", "2025", date_type="Y")]
    square_up(recs)
    st = map_stats.compute(recs, None)
    assert st.last == (2025, 7, 3) and st.first == (2025, None, None)
    assert map_stats.when_text(st.first) == "2025"
    assert map_stats.when_text((1956, 6, None)) == "Jun 1956"


def test_wording():
    recs = sample()
    squares = square_up(recs)
    st = map_stats.compute(recs, squares)
    assert map_stats.first_last_line(st) == "First record 12 May 1898 · Last record 3 Jul 2025"
    assert map_stats.first_last_line(st, True).endswith("(in view)")
    assert map_stats.counts_line(st, "10 km") == (
        "Records 8 · Species 3 · Squares 3 (10 km) · Vice counties 4 · Recorders 3")
    assert map_stats.month_note(st) == "n = 5; 3 records not dated to a single day"
    big = map_stats.MapStats(records=1234)
    assert map_stats.counts_line(big).startswith("Records 1,234 ·")
    assert "pre-1950 2" in map_stats.decades_line(st) and "undated 1" in map_stats.decades_line(st)
    assert map_stats.first_last_line(map_stats.MapStats()) == "No dated records"


def test_unsquared_records_are_not_counted():
    recs = sample() + [rec("", "1800-01-01", "sp:z", "Z")]
    squares = square_up(recs)
    assert recs[-1]["square"] is None
    st = map_stats.compute(recs, squares)
    assert st.records == 8 and st.first == (1898, 5, 12)


def test_restriction_to_shown_squares():
    recs = sample()
    squares = square_up(recs)
    keep = {r["square"] for r in recs if r["grid_ref"].startswith("SP")}
    st = map_stats.compute(recs, keep)
    assert st.records == 2 and st.squares == 1 and st.species == 2
    assert st.last == (1950, 7, 1) and st.vice_counties == 1 and st.recorders == 1
    assert map_stats.compute(recs, set()).records == 0
    assert map_stats.compute(recs, squares).records == 8


def test_duplicate_species_names_as_the_tab_counts():
    # two records, different names but one species key (the tab's r["species"]) count once
    recs = [rec("SP4020", "2000-01-01", "TVK1", species_name="Aus bus"),
            rec("SP4021", "2000-01-02", "TVK1", species_name="Aus bus var. c"),
            rec("SP4022", "2000-01-03", None, species_name="Aus")]
    square_up(recs)
    assert map_stats.compute(recs, None).species == 1


# ---------------------------------------------------------------- the page and dialog

@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def sandbox(qapp):
    from PySide6.QtCore import QCoreApplication, QSettings
    org = QCoreApplication.organizationName()
    QCoreApplication.setOrganizationName("ObservatumTests_export_preview")
    QSettings().clear()
    yield
    QSettings().clear()
    QCoreApplication.setOrganizationName(org)


def make_host(qapp, records=None):
    from types import SimpleNamespace

    from PySide6.QtWidgets import QComboBox, QLabel, QWidget
    from src.views.mapping.atlas_export import AtlasExportMixin

    from shared.maps.grid_map import GridMap

    class Host(QWidget, AtlasExportMixin):
        def _grid_size(self):
            return gs.HECTAD

    h = Host()
    h._records = records if records is not None else sample()
    h._squares = square_up(h._records)
    for sq in h._squares.values():
        sq["fill"] = "#4a7c59"
    h._mapped_selection = []
    h._legend = [("#4a7c59", "Records")]
    combo = QComboBox()
    combo.addItem("Full extent", "full")
    combo.addItem("Current view", "current")
    h.toolbar = SimpleNamespace(export_extent=lambda: combo.currentData(), extent_combo=combo)
    h.map_header = SimpleNamespace(subtitle=QLabel("Test subtitle"))
    h.map_widget = GridMap()
    h.map_widget.resize(800, 800)
    h.map_widget.set_squares(h._squares, gs.HECTAD)
    return h


ALL = {"counts": True, "first_last": True, "phenology": True, "decades": True}
NONE = {"counts": False, "first_last": False, "phenology": False, "decades": False}


def test_page_identical_with_no_extras(qapp):
    h = make_host(qapp)
    for opts in (None, NONE):
        again = h.render_atlas("full", opts, dpi=100)
        ref = h.map_widget.render_sheet(h._title(), "Test subtitle", legend=h._legend,
                                        footer=h.atlas_footer("full", h.map_widget.sheet_view(
                                            "full", dpi=100, legend=h._legend)[1]), dpi=100)
        assert again == ref


def test_page_renders_with_each_extra(qapp):
    h = make_host(qapp)
    base = h.render_atlas("full", NONE, dpi=100)
    for key in NONE:
        img = h.render_atlas("full", {**NONE, key: True}, dpi=100)
        assert img.size() == base.size() and img != base
    full = h.render_atlas("full", ALL, dpi=100)
    assert full != base


def test_extras_shrink_the_map_little(qapp):
    h = make_host(qapp)
    _e, shown0 = h.map_widget.sheet_view("full", dpi=100, legend=h._legend)
    ex = h.export_extras(ALL, "full", shown0)
    _e, shown1 = h.map_widget.sheet_view("full", dpi=100, legend=h._legend, extras=ex)
    assert (shown1[3] - shown1[1]) >= 0.85 * (shown0[3] - shown0[1]) - 1   # portrait A4


def test_figures_match_the_footer(qapp):
    h = make_host(qapp)
    _e, shown = h.map_widget.sheet_view("full", legend=h._legend)
    st = h.export_stats("full", shown)
    foot = h.atlas_footer("full", shown)
    assert foot == f"{st.squares:,} hectads, {st.records:,} records, {st.species:,} species."
    ex = h.export_extras(ALL, "full", shown)
    assert ex.lines[0].startswith(f"Records {st.records:,} · Species {st.species:,} · "
                                  f"Squares {st.squares:,} (10 km)")
    assert ex.months == tuple(st.months) and ex.chart_title == "Records by month"


def test_current_view_restricts_and_says_so(qapp):
    from PySide6.QtCore import QPointF
    h = make_host(qapp)
    mw = h.map_widget
    mw._zoom, mw._pan = 4.0, QPointF(-1600, -2300)
    _e, shown = mw.sheet_view("current", legend=h._legend)
    inside = set(mw.squares_in(shown))
    assert 0 < len(inside) < len(h._squares)
    st = h.export_stats("current", shown)
    foot = h.atlas_footer("current", shown)
    assert foot == f"{st.squares:,} hectads, {st.records:,} records, {st.species:,} species (in view)."
    ex = h.export_extras(ALL, "current", shown)
    assert all(line.endswith("(in view)") for line in ex.lines)
    assert ex.chart_title == "Records by month (in view)"
    assert h.render_atlas("current", ALL, dpi=100).width() > 0


def test_dialog_remembers_ticks_and_exports(qapp, sandbox, tmp_path, monkeypatch):
    from PySide6.QtCore import QSettings
    from PySide6.QtGui import QImage
    from src.views.mapping import atlas_export
    from src.views.mapping.export_preview import ExportPreviewDialog

    h = make_host(qapp)
    d = ExportPreviewDialog(h, h)
    assert d.options() == {**NONE, "layer_legend": True, "grid": False}   # only the layer legend is on by default
    d.checks["decades"].setChecked(True)
    d.checks["counts"].setChecked(True)
    d.refresh_now()
    assert not d._pix.isNull()
    assert QSettings().value("mapping/export/decades", type=bool) is True
    d2 = ExportPreviewDialog(h, h)
    assert d2.options() == {"counts": True, "first_last": False, "phenology": False,
                            "decades": True, "layer_legend": True, "grid": False}
    out = tmp_path / "page"
    monkeypatch.setattr(atlas_export.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: (str(out), "")))
    monkeypatch.setattr(atlas_export.QMessageBox, "information", staticmethod(lambda *a, **k: 0))
    d2._export()
    img = QImage(str(tmp_path / "page.png"))
    assert not img.isNull() and img.width() == 2480 and img.height() == 3508
    # cancelled file dialog: nothing saved, dialog stays open
    monkeypatch.setattr(atlas_export.QFileDialog, "getSaveFileName",
                        staticmethod(lambda *a, **k: ("", "")))
    assert h._export_png("full", d2.options(), d2) is False


def test_export_asks_to_generate_first(qapp, monkeypatch):
    from src.views.mapping import atlas_export
    h = make_host(qapp)
    h._squares = {}
    said = []
    monkeypatch.setattr(atlas_export.QMessageBox, "information",
                        staticmethod(lambda *a, **k: said.append(a[2])))
    h._on_export()
    assert said == ["Generate a map first."]


def test_recorders_split_and_distinct():
    assert map_stats.recorder_names("Graeme Lyons;Alice  Parfitt; Shaun Pryor") == [
        "Graeme Lyons", "Alice Parfitt", "Shaun Pryor"]
    assert map_stats.recorder_names("A. Smith & B. Jones") == ["A. Smith", "B. Jones"]
    assert map_stats.recorder_names("Anderson and Sandy") == ["Anderson", "Sandy"]   # whole word
    assert map_stats.recorder_names(" ; ") == [] and map_stats.recorder_names(None) == []
    recs = [rec("SP4020", "2000-01-01", person="Graeme Lyons;Alice Parfitt"),
            rec("SP4021", "2000-01-02", person="alice parfitt & Shaun Pryor"),
            rec("SP4022", "2000-01-03", person="Lyons, G."),
            rec("SP4023", "2000-01-04", person="")]
    square_up(recs)
    assert map_stats.compute(recs, None).recorders == 3   # Lyons, G. is Graeme Lyons


def test_ranges_and_before_after_stay_out_of_first_last_and_decades():
    recs = [rec("SP4020", "2001-05-05", date_type="D"),
            rec("SP4021", "1990-01-01", date_type="YY"),     # range of years: first day stored
            rec("SP4022", "2030-01-01", date_type="-Y"),     # before 2030
            rec("SP4023", "1800-01-01", date_type="Y-"),     # after 1800
            rec("SP4024", "1700-03-01", date_type="DD"),
            rec("SP4025", "1700-03-01", date_type="OO"),
            rec("SP4026", "1990", date_type="Y")]
    square_up(recs)
    st = map_stats.compute(recs, None)
    assert st.records == 7 and st.ranged == 5
    assert st.first == (1990, None, None) and st.last == (2001, 5, 5)
    assert sum(n for _l, n in st.decades) == 2
    assert sum(st.months) == 1 and sum(st.months) + st.no_month == 7
    assert map_stats.range_note(st) == (
        "5 records with a date range or 'before/after' date are not in first/last or decades")
    assert map_stats.range_note(map_stats.compute([], None)) == ""


def test_range_note_on_the_page(qapp):
    recs = sample() + [rec("SP4020", "1990-01-01", date_type="YY")]
    h = make_host(qapp, recs)
    _e, shown = h.map_widget.sheet_view("full", legend=h._legend)
    ex = h.export_extras({**NONE, "first_last": True}, "full", shown)
    assert ex.lines[-1].startswith("1 record with a date range") and "is not in" in ex.lines[-1]
    assert h.export_extras({**NONE, "counts": True}, "full", shown).lines[-1].startswith("Records")


def test_preview_and_export_say_the_same_for_a_zoomed_view(qapp):
    from PySide6.QtCore import QPointF
    h = make_host(qapp)
    mw = h.map_widget
    mw._zoom, mw._pan = 4.0, QPointF(-1600, -2300)
    seen = {}
    real = mw.render_sheet

    def spy(*a, **kw):
        seen[kw["dpi"]] = (kw["footer"], kw["extras"])
        return real(*a, **kw)
    mw.render_sheet = spy
    try:
        h.render_atlas("current", ALL, dpi=100)
        h.render_atlas("current", ALL, dpi=300)
    finally:
        del mw.render_sheet
    assert seen[100] == seen[300]
    assert seen[100][0].endswith("(in view).") and seen[100][1].lines[0].endswith("(in view)")
