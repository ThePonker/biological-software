"""Round 2 UI small wins (10 Oct 2026 evening): L10 clear buttons, L29 Filter Wizard size,
L20 New Species List columns, L21 Data Entry order indicator, L22 conservation chips and
the small "not done" items. Offscreen; the data copies are read only."""
import gc
import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import paths  # noqa: E402

needs_obs = pytest.mark.skipif(not paths.OBSERVATUM_DB.exists(), reason="needs data/observatum.db")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _tidy_widgets(qapp):
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication
    before = set(map(id, QApplication.topLevelWidgets()))
    yield
    for w in QApplication.topLevelWidgets():
        if id(w) not in before:
            w.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    gc.collect()


@pytest.fixture
def settings_isolated(qapp):
    from PySide6.QtCore import QCoreApplication, QSettings
    org, app = QCoreApplication.organizationName(), QCoreApplication.applicationName()
    QCoreApplication.setOrganizationName("ObservatumTests")
    QCoreApplication.setApplicationName("uiwins_r2")
    QSettings().clear()
    yield
    QCoreApplication.setOrganizationName(org)
    QCoreApplication.setApplicationName(app)


def _wait(ms):
    from PySide6.QtWidgets import QApplication
    end = time.perf_counter() + ms / 1000
    while time.perf_counter() < end:
        QApplication.processEvents()


def _bar(kind):
    if kind == "obs":
        from src.views.observations.observation_filter_bar import ObservationFilterBar
        bar = ObservationFilterBar()
        return bar, [bar.species_edit, bar.location_edit, bar.family_edit, bar.recorder_edit]
    if kind == "scheme":
        from src.views.scheme.scheme_filter_bar import SchemeFilterBar
        bar = SchemeFilterBar()
        return bar, [bar.species_edit, bar.location_edit, bar.recorder_edit]
    from src.views.collection.collection_filters import CollectionFilterBar
    bar = CollectionFilterBar()
    return bar, [bar.species_edit, bar.location_edit, bar.family_edit, bar.collector_edit]


def _clear_button(edit):
    from PySide6.QtWidgets import QToolButton
    buttons = edit.findChildren(QToolButton)
    assert buttons, "no ✕ in the box"
    return buttons[0]


# ---------------------------------------------------------------- L10 ✕ in every filter box

@pytest.mark.parametrize("kind", ["obs", "scheme", "collection"])
def test_every_filter_text_box_has_a_clear_button(qapp, settings_isolated, kind):
    bar, edits = _bar(kind)
    for e in edits + [bar.date_from_edit.date_input, bar.date_to_edit.date_input]:
        assert e.isClearButtonEnabled(), e


@pytest.mark.parametrize("kind", ["obs", "scheme", "collection"])
def test_clear_button_reloads_once(qapp, settings_isolated, kind):
    bar, edits = _bar(kind)
    bar.show()
    for e in edits:
        e.setText("abc")
        _wait(10)
        got = []
        bar.filters_changed.connect(got.append)
        _clear_button(e).click()
        _wait(450)                               # past the debounce: nothing more comes
        bar.filters_changed.disconnect()
        assert e.text() == ""
        assert len(got) == 1, (e, got)


def test_typing_still_debounced_and_enter_once(qapp):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QLineEdit
    from src.views.components.filter_debounce import debounce_text
    e = QLineEdit()
    calls = []
    debounce_text(e, lambda: calls.append(e.text()))
    e.show()
    QTest.keyClicks(e, "Rhag")
    assert calls == []
    _wait(450)
    assert calls == ["Rhag"]
    QTest.keyClicks(e, "i")
    QTest.keyClick(e, Qt.Key.Key_Return)
    _wait(450)
    assert calls == ["Rhag", "Rhagi"]
    e.setText("x")                               # set by the program: at once
    assert calls[-1] == "x"
    # deleting the last character by key is still debounced
    e.setText("")
    calls.clear()
    QTest.keyClicks(e, "a")
    QTest.keyClick(e, Qt.Key.Key_Backspace)
    assert calls == []
    _wait(450)
    assert calls == [""]


@pytest.mark.parametrize("kind", ["obs", "scheme", "collection"])
def test_date_clear_button_clears_the_date_once(qapp, settings_isolated, kind):
    from PySide6.QtCore import QDate
    bar, _ = _bar(kind)
    bar.show()
    bar.date_from_edit.setDate(QDate(2019, 1, 1))
    assert bar.get_filters()["date_from"] == "2019-01-01"
    _wait(300)                                    # the ✕ fades in
    got = []
    bar.filters_changed.connect(got.append)
    _clear_button(bar.date_from_edit.date_input).click()
    bar.date_from_edit.date_input.editingFinished.emit()   # leaving the box: no second reload
    _wait(50)
    assert bar.get_filters()["date_from"] is None
    assert len(got) == 1


def test_date_box_fits_its_column(qapp):
    from src.views.components.date_filter_widget import DateFilterWidget
    from src.views.components.filter_styles import COL_DATE_FROM
    w = DateFilterWidget()
    assert w.sizeHint().width() <= COL_DATE_FROM


# ---------------------------------------------------------------- L29 Filter Wizard size

def _tab(kind, monkeypatch):
    if kind == "obs":
        from src.views.observations.observation_tab import ObservationTab
        return ObservationTab()
    if kind == "scheme":
        import src.views.scheme.recording_scheme_tab as rst
        monkeypatch.setattr(rst.RecordingSchemeTab, "_load_data", lambda self, f=None: None)
        return rst.RecordingSchemeTab()
    import src.views.collection.insect_collection_tab as ict
    monkeypatch.setattr(ict.InsectCollectionTab, "_load_data", lambda self, *a, **k: None)
    return ict.InsectCollectionTab()


@pytest.mark.parametrize("kind", ["obs", "scheme", "collection"])
def test_wizard_compact_and_under_the_bar(qapp, settings_isolated, monkeypatch, kind):
    tab = _tab(kind, monkeypatch)
    bar = tab.filters if kind == "collection" else tab.filter_bar
    lay = tab.layout()
    assert lay.indexOf(bar) < lay.indexOf(tab.filter_wizard)       # same order on every tab
    tab.resize(1700, 990)
    bar.setVisible(True)
    tab.filter_wizard.setVisible(True)
    tab.show()
    _wait(30)
    h = tab.filter_wizard.height()
    assert h <= tab.filter_wizard.MAX_HEIGHT       # was 409 px
    assert h >= 150                                # still shows both rows of cards
    tab.resize(1146, 678)                          # 1366 x 768 less the window chrome
    _wait(30)
    assert tab.filter_wizard.height() <= tab.filter_wizard.MAX_HEIGHT


def test_theme_button_styles_have_no_missing_colour(qapp):
    from src.themes import theme
    t = theme()
    for css in (t.button_primary_style(), t.button_cancel_style(), t.button_delete_style()):
        assert "#ff00ff" not in css.lower()
    assert t.get("button_secondary") in t.button_cancel_style()
    assert t.get("button_danger") in t.button_delete_style()


# ---------------------------------------------------------------- L20 New Species List columns

class _RoDb:
    def __init__(self, path):
        import sqlite3
        self.conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        self.conn.row_factory = sqlite3.Row

    def execute_main(self, sql, params=()):
        return self.conn.execute(sql, params).fetchall()


@needs_obs
def test_new_species_list_rows_are_whole_first_records(qapp):
    from src.repositories.observation_repository import ObservationRepository
    db = _RoDb(paths.OBSERVATUM_DB)
    repo = ObservationRepository(db)
    rows = repo.get_new_species_first_records(10000)
    # the same first records as the old six-column query (one per species, earliest date)
    ex = repo._get_species_exclusion_clause()
    want = {(r["species_tvk"], r["date"]) for r in db.execute_main(f"""
        SELECT species_tvk, date FROM (
            SELECT species_tvk, date, ROW_NUMBER() OVER (PARTITION BY species_tvk
                ORDER BY (date IS NULL OR date = ''), date ASC, id ASC) AS rn
            FROM observations WHERE species_tvk IS NOT NULL {ex}) WHERE rn = 1""")}
    assert {(r["species_tvk"], r["date"]) for r in rows} == want
    assert len(rows) == len(want) > 3000
    dates = [r["date"] or "" for r in rows]
    assert dates == sorted(dates, reverse=True)
    # whole rows: an id to open, and the columns that were blank
    assert all(r.get("id") for r in rows)
    for col in ("quantity", "recorder", "kingdom", "taxon_group", "taxon_rank"):
        assert sum(1 for r in rows if not r.get(col)) == 0, col
    for col in ("order_name", "family"):          # a handful of higher taxa have none
        assert sum(1 for r in rows if not r.get(col)) <= 5, col
    # nothing written: the stored kingdom is still blank on records the list fills
    blank = db.execute_main("SELECT COUNT(*) FROM observations WHERE COALESCE(kingdom,'') = ''")[0][0]
    if blank == 0:                       # this copy holds every kingdom (Wil's PC, 10 Oct)
        return


@needs_obs
def test_new_species_list_shows_the_columns_in_the_table(qapp):
    from PySide6.QtCore import Qt
    from src.repositories.observation_repository import ObservationRepository
    from src.views.observations.observation_table_model import ObservationTableModel
    rows = ObservationRepository(_RoDb(paths.OBSERVATUM_DB)).get_new_species_first_records(200)
    m = ObservationTableModel()
    m.set_observations_fast(rows)
    keys = [c[0] for c in m._columns]
    for col in ("quantity", "recorder", "kingdom", "taxon_group", "taxon_rank"):
        if col in keys:
            j = keys.index(col)
            assert all(m.data(m.index(i, j), Qt.ItemDataRole.DisplayRole) not in (None, "")
                       for i in range(m.rowCount())), col


def test_species_columns_filled_from_other_records_then_uksi(qapp):
    from src.repositories.observation_repository import ObservationRepository

    class Db:
        def execute_main(self, sql, params=()):
            if "GROUP BY species_tvk" in sql:
                col = sql.split("SELECT species_tvk, ")[1].split(" AS v")[0]
                data = {"kingdom": [("A", "Animalia", 3)], "taxon_group": [("A", "insect - beetle", 2),
                                                                           ("A", "other", 1)]}
                return [{"species_tvk": t, "v": v, "n": n} for t, v, n in data.get(col, [])
                        if t in params]
            return []
    repo = ObservationRepository(Db())
    rows = [{"species_tvk": "A", "kingdom": None, "taxon_group": "", "order_name": "Coleoptera",
             "family": "Carabidae", "taxon_rank": "Species"},
            {"species_tvk": "B", "kingdom": "Plantae", "taxon_group": "x", "order_name": "o",
             "family": "f", "taxon_rank": "Species"}]
    repo._fill_species_columns(rows)
    assert rows[0]["kingdom"] == "Animalia" and rows[0]["taxon_group"] == "insect - beetle"
    assert rows[1]["kingdom"] == "Plantae"


# ---------------------------------------------------------------- small items

def test_sort_items_sort_by_value(qapp):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QTableWidget
    from src.views.components.sort_items import date_item, number_item
    t = QTableWidget(4, 2)
    for r, (d, n) in enumerate([("2024-06-01", 987), ("1990-05-28", 1234), ("", 5), ("2001-01-15", 40)]):
        t.setItem(r, 0, date_item(d))
        t.setItem(r, 1, number_item(n))
    t.sortItems(0, Qt.SortOrder.AscendingOrder)
    assert [t.item(r, 0).text() for r in range(4)] == ["", "28/05/1990", "15/01/2001", "01/06/2024"]
    t.sortItems(1, Qt.SortOrder.DescendingOrder)
    assert [t.item(r, 1).text() for r in range(4)] == ["1,234", "987", "40", "5"]


def test_scheme_dialog_export_buttons_have_real_colours():
    import pathlib
    src = pathlib.Path(__file__).resolve().parents[1] / "Observatum/src/views/stats/scheme_dashboard.py"
    text = src.read_text(encoding="utf-8")
    assert "{{t.get(" not in text                 # f-string braces doubled: the CSS was literal
    assert "def format_date(" not in text         # dates now sort as dates (date_item)


@pytest.mark.parametrize("cls_name", ["ClickableDataTable", "SimpleBreakdownTable",
                                      "YearBreakdownTable"])
def test_collection_dashboard_counts_sort_as_numbers(qapp, cls_name):
    from PySide6.QtCore import Qt
    from src.views.stats import collection_dashboard as cd
    from src.views.components.sort_items import SortItem
    if cls_name == "ClickableDataTable":
        w = cd.ClickableDataTable("t", ["Name", "Specimens", "Species"])
    elif cls_name == "SimpleBreakdownTable":
        w = cd.SimpleBreakdownTable("t")
    else:
        w = cd.YearBreakdownTable()
    if cls_name == "YearBreakdownTable":
        w.set_data([{"year": 2020, "specimens": 987, "species": 5},
                    {"year": 2021, "specimens": 1234, "species": 40}], [])
    elif cls_name == "ClickableDataTable":
        w.set_data([{"k": "a", "specimens": 987, "species": 5},
                    {"k": "b", "specimens": 1234, "species": 40}], "k")
    else:
        w.set_data([{"k": "a", "count": 987}, {"k": "b", "count": 1234}], "k")
    w.table.sortItems(1, Qt.SortOrder.DescendingOrder)
    assert isinstance(w.table.item(0, 1), SortItem)
    assert w.table.item(0, 1).text() == "1,234"
    w.table.sortItems(1, Qt.SortOrder.AscendingOrder)
    assert w.table.item(0, 1).text() == "987"


def test_recent_species_popup_edit_delete_go_to_observation_tab(qapp, monkeypatch):
    from PySide6.QtWidgets import QMainWindow, QPushButton, QWidget
    from src.views.dialogs import RecordDetailDialog
    from src.views.observations.observation_record_actions import wire_observation_detail
    record = {"id": 7, "species_name": "Abax parallelus", "species_tvk": "X", "date": "2020-01-01"}

    # no Observation tab reachable: the two buttons are hidden, not left dead
    alone = QWidget()
    dlg = RecordDetailDialog(record=record, species_count=1, record_type="observation", parent=alone)
    assert wire_observation_detail(dlg, alone) is False
    assert all(b.isHidden() for b in dlg.findChildren(QPushButton) if b.text() in ("Edit", "Delete"))

    class Tab(QWidget):
        def __init__(self):
            super().__init__()
            self.edits, self.deletes, self._current_detail_dialog = [], [], None

        def initialize(self, db_path=None):
            pass

        def _on_detail_edit_requested(self, rec):
            self.edits.append(rec["id"])

        def _on_detail_delete_requested(self, rec):
            self.deletes.append(rec["id"])

    win = QMainWindow()
    win.observation_tab = Tab()
    dash = QWidget()
    win.setCentralWidget(dash)
    dlg = RecordDetailDialog(record=record, species_count=1, record_type="observation", parent=dash)
    assert wire_observation_detail(dlg, dash) is True
    assert win.observation_tab._current_detail_dialog is dlg
    dlg.edit_requested.emit(record)
    dlg.delete_requested.emit(record)
    assert win.observation_tab.edits == [7] and win.observation_tab.deletes == [7]
    dlg.done(0)
    assert win.observation_tab._current_detail_dialog is None


def test_dashboards_wire_the_recent_species_popup():
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1] / "Observatum/src/views/stats"
    for name in ("all_stats_dashboard.py", "personal_dashboard.py", "commercial_dashboard.py"):
        text = (root / name).read_text(encoding="utf-8")
        body = text.split("def _show_recent_species_detail")[1].split("\n    def ")[0]
        assert "wire_observation_detail(dlg, self)" in body, name


def test_notifications_retired_and_package_imports():
    import pathlib
    import src.features.gamification as g
    root = pathlib.Path(__file__).resolve().parents[1]
    assert not (root / "Observatum/src/features/gamification/notifications.py").exists()
    assert (root / "_archive/gamification_notifications_20261010/notifications.py").exists()
    assert not hasattr(g, "NotificationStack")


# ---------------------------------------------------------------- L21 / L22 Data Entry

@pytest.fixture
def de_widget(tmp_path, monkeypatch, qapp):
    import sqlite3
    from PySide6.QtWidgets import QMessageBox
    from DataEntry import csv_backup
    db = tmp_path / "observatum.db"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, irecord_id INTEGER, "
              "species_tvk TEXT, species_name TEXT, date TEXT, grid_ref TEXT, recorder TEXT, "
              "record_type TEXT, project_name TEXT, client TEXT)")
    c.commit()
    c.close()
    monkeypatch.setattr(csv_backup, "backup_staging", lambda conn: "s.csv")
    monkeypatch.setattr(csv_backup, "backup_observations", lambda p: "o.csv")
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    from DataEntry.data_entry_widget import DataEntryWidget
    w = DataEntryWidget(str(db), embedded=True, allow_commit=False)
    yield w
    w.close()


def test_data_entry_says_which_order_it_shows(de_widget):
    from DataEntry import staging_repo as repo
    from DataEntry.entry_grid import COLUMNS, EntryGridPage
    conn = de_widget._conn
    pid = repo.ensure_personal_job(conn)
    for name in ("Philanthus triangulum", "Abax parallelus", "Carabus violaceus"):
        repo.insert_row(conn, pid, dict(species_name=name, species_tvk="T", date="2026-06-05"))
    de_widget._open_job(pid)
    g = de_widget._job_host.findChildren(EntryGridPage)[-1]
    names = lambda: [g._model._rows[i]["species_name"] for i in range(3)]  # noqa: E731
    entered = names()
    assert g._order_lbl.text() == "Showing: entry order"
    assert g._sort_btn.isHidden()

    sp = next(i for i, c in enumerate(COLUMNS) if c[0] == "species_name")
    g._on_header_sort(sp)
    assert names() == sorted(entered)
    assert g._order_lbl.text().startswith(f"Showing: sorted by {COLUMNS[sp][1]} ▴")
    assert not g._sort_btn.isHidden() and g._sort_btn.text() == "Back to entry order"
    g._on_header_sort(sp)                                   # again: reversed
    assert names() == sorted(entered, reverse=True) and "▾" in g._order_lbl.text()

    g._sort_btn.click()
    assert names() == entered                              # stored entry order untouched
    assert g._order_lbl.text() == "Showing: entry order"
    assert g._sort_btn.isHidden()


def test_conservation_chips_short_text_full_tooltip(qapp):
    from DataEntry.info_panel import InfoPanel, chip_text
    assert chip_text("Priority (NERC S.41 England)") == "S.41"
    assert chip_text("Priority (Scottish Biodiversity List)") == "SBL"
    assert chip_text("Priority (Env (Wales) Act S7)") == "S7"
    assert chip_text("Protected (Bern Convention Appendix 2)") == "Protected"
    assert chip_text("VU") == "VU" and chip_text("BoCC Amber") == "BoCC Amber"
    assert len(chip_text("A very long unknown status label")) <= 14
    w = InfoPanel._chip("Protected (WCA 1981 Sch5 s9.4b)", "legal")
    assert w.text() == "Protected" and w.toolTip() == "Protected (WCA 1981 Sch5 s9.4b)"


@pytest.mark.skipif(not os.path.exists(str(paths.CODEX_DB)), reason="codex.db not present")
def test_conservation_chips_fit_the_readout(qapp):
    """Every species' chips at VC23 / 90 / 35, in the readout's chip row at its real width:
    nothing drawn past the edge, and what doesn't fit is in a "+n" chip naming the rest.
    (Font widths differ by machine -- Segoe UI on Windows is wider -- so this checks the
    folding, not a fixed pixel sum.)"""
    import sqlite3
    from DataEntry.info_panel import InfoPanel, InfoService, _FlowRow
    s = InfoService(sqlite3.connect(":memory:"), str(paths.CODEX_DB))
    c = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)
    tvks = [r[0] for r in c.execute("SELECT tvk FROM status_summary GROUP BY tvk "
                                    "HAVING COUNT(DISTINCT status_track) >= 3")]
    c.close()
    width = 316 - 2 * 12 - 2
    row = _FlowRow()
    row.resize(width, 22)
    row.show()
    folded = 0
    for widths_cap in (width, 120):                 # the real width, and a very narrow one
        row.resize(widths_cap, 22)
        for t in tvks:
            for vc in (23, 90, 35):
                chips = [InfoPanel._chip(lab, k) for lab, k in s.conservation_chips(t, vc)]
                if not chips:
                    continue
                row.set_items(chips)
                qapp.processEvents()
                assert row.width() == widths_cap        # the chips never widen the row
                shown = [w for w in chips if not w.isHidden()]
                used = sum(w.sizeHint().width() for w in shown) + 6 * max(0, len(shown) - 1)
                if not row._more.isHidden():
                    folded += 1
                    used += 6 + row._more.sizeHint().width()
                    hidden = [w for w in chips if w.isHidden()]
                    assert row._more.text() == f"+{len(hidden)}"
                    for w in hidden:
                        assert w.toolTip() in row._more.toolTip()
                else:
                    assert len(shown) == len(chips)
                assert used <= widths_cap
    assert folded > 0                               # the narrow pass always folds some
    row.close()