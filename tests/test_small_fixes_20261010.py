"""Small fixes Wil found testing on 10 Oct 2026.

  1  Species lookup phenology: a month click opens that month's records (the bar's
     count); the shared month chart shows a hand cursor only where a click does something
  2  filter bars: Clear All at the left, beside the Species box
  3  toolbar Clear Filters and the bar's Clear All clear everything (bar, wizard, saved
     filter) with one reload, on every record tab
  4  Codex Species Search: a genus / family / order lists its species with a status
  5  Recording Scheme bar: Subfamily greyed out while the column is empty
"""
import gc
import os
import sqlite3
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import paths  # noqa: E402

needs_obs = pytest.mark.skipif(not paths.OBSERVATUM_DB.exists(), reason="needs data/observatum.db")
needs_uksi = pytest.mark.skipif(not paths.UKSI_DB.exists(), reason="needs data/uksi.db")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _tidy_widgets(qapp):
    """Delete the widgets each test made: whole record tabs left alive slowed later
    timing tests in the same run (test_species_search_20261010::test_speed)."""
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication
    before = set(map(id, QApplication.topLevelWidgets()))
    yield
    for w in QApplication.topLevelWidgets():
        if id(w) not in before:
            w.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    gc.collect()


def _wait(ms):
    from PySide6.QtWidgets import QApplication
    end = time.perf_counter() + ms / 1000
    while time.perf_counter() < end:
        QApplication.processEvents()


# ---------------------------------------------------------------- 1 phenology clicks

def test_month_chart_hand_cursor_only_when_connected(qapp):
    from PySide6.QtCore import Qt
    from src.views.stats.stat_widgets import MonthlyActivityChart
    plain = MonthlyActivityChart("Records Over Time")
    plain.set_data([1] * 12)
    assert not plain.is_clickable()
    assert all(w.cursor().shape() != Qt.CursorShape.PointingHandCursor
               for w in plain._bar_containers + plain._month_labels)

    clicked = MonthlyActivityChart("Phenology")
    clicked.set_data([1] * 12)
    got = []
    clicked.month_clicked.connect(got.append)      # connected after the bars exist
    assert clicked.is_clickable()
    assert all(w.cursor().shape() == Qt.CursorShape.PointingHandCursor
               for w in clicked._bar_containers + clicked._month_labels)
    clicked.set_data([2] * 12)                      # rebuilt bars keep it
    assert all(w.cursor().shape() == Qt.CursorShape.PointingHandCursor
               for w in clicked._bar_containers)
    clicked._bar_containers[4].mousePressEvent(None)
    assert got == [5]


@needs_obs
@needs_uksi
def test_phenology_month_records_equal_the_bar(qapp, monkeypatch):
    """Grammoptera ruficornis has observations and scheme records: each month's dialog
    lists exactly the records its bar counts, and the dashboard opens it on a click."""
    from types import SimpleNamespace
    from src.views.stats import species_dashboard as sd
    from src.views.stats.month_records_dialog import MonthRecordsDialog, month_records
    conn = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    class Db:
        def execute_main(self, sql, params=()):
            return conn.execute(sql, params).fetchall()

    d = sd.SpeciesDashboard()
    d._db = Db()
    r = SimpleNamespace(scientific_name="Grammoptera ruficornis", tvk="NHMSYS0020152218",
                        common_name="", family="Cerambycidae", order_name="Coleoptera",
                        old_name=None, match_type="exact")
    d._search_results = [r]
    d._on_completer_activated(d._display(r))
    pheno = d._selected_species["phenology"]
    assert sum(pheno) > 1000
    for m in range(1, 13):
        rows = month_records(d._db.execute_main, d._by_species, r.scientific_name, m)
        assert len(rows) == pheno[m - 1], m
    june = month_records(d._db.execute_main, d._by_species, r.scientific_name, 6)
    assert {x['source'] for x in june} == {"Observation", "Recording Scheme"}

    opened = []
    monkeypatch.setattr(MonthRecordsDialog, "exec",
                        lambda self: opened.append((self.windowTitle(), self.table.rowCount())))
    assert d._phenology_chart.is_clickable()
    d._phenology_chart.month_clicked.emit(6)
    assert opened == [("Records for Grammoptera ruficornis in June", pheno[5])]
    dlg = MonthRecordsDialog(r.scientific_name, 6, june, db=d._db)
    dlg.table.sortItems(1)                          # sorted: the row still knows its record
    table, rid = dlg.record_key_at(0)
    assert table in ("observations", "recording_scheme") and isinstance(rid, int)
    conn.close()


# ---------------------------------------------------------------- 2, 3 Clear All / Clear Filters

@pytest.fixture
def settings_isolated(qapp):
    from PySide6.QtCore import QCoreApplication, QSettings
    org, app = QCoreApplication.organizationName(), QCoreApplication.applicationName()
    QCoreApplication.setOrganizationName("ObservatumTests")
    QCoreApplication.setApplicationName("small_fixes_20261010")
    QSettings().clear()
    yield
    QCoreApplication.setOrganizationName(org)
    QCoreApplication.setApplicationName(app)


def _tab(kind, monkeypatch):
    """A record tab, its filter bar and toolbar; loads are not run (counted by the bar)."""
    if kind == "obs":
        from src.views.observations.observation_tab import ObservationTab
        tab = ObservationTab()
        return tab, tab.filter_bar
    if kind == "scheme":
        import src.views.scheme.recording_scheme_tab as rst
        monkeypatch.setattr(rst.RecordingSchemeTab, "_load_data", lambda self, f=None: None)
        tab = rst.RecordingSchemeTab()
        tab._initialized = True
        return tab, tab.filter_bar
    from src.views.collection.insect_collection_tab import InsectCollectionTab
    monkeypatch.setattr(InsectCollectionTab, "_load_data", lambda self, *a, **k: None)
    tab = InsectCollectionTab()
    return tab, tab.filters


@pytest.mark.parametrize("kind", ["obs", "scheme", "collection"])
def test_clear_all_sits_left_of_species(qapp, settings_isolated, monkeypatch, kind):
    _, bar = _tab(kind, monkeypatch)
    from PySide6.QtWidgets import QHBoxLayout
    row = next(lay for lay in bar.findChildren(QHBoxLayout) if lay.indexOf(bar.clear_btn) >= 0)
    widgets = [row.itemAt(i).widget() for i in range(row.count()) if row.itemAt(i).widget()]
    assert widgets[0] is bar.clear_btn
    assert widgets[1] is bar.species_edit.parentWidget()
    assert bar.clear_btn.text() == "Clear All"


@pytest.mark.parametrize("kind", ["obs", "scheme", "collection"])
@pytest.mark.parametrize("button", ["toolbar", "bar"])
def test_clear_filters_clears_bar_wizard_and_saved_once(qapp, settings_isolated, monkeypatch,
                                                        kind, button):
    tab, bar = _tab(kind, monkeypatch)
    bar.species_edit.setText("Rhagium mordax")
    bar.location_edit.setText("wood")
    tab.filter_wizard.set_filters({"year": 2019})          # a wizard filter, applied
    tab._wizard_filters = {"year": 2019}
    assert tab.filter_wizard.get_all_filters() == {"year": 2019}
    if kind == "obs":
        tab._wizard_ids = {1, 2}
    emitted = []
    bar.filters_changed.connect(lambda f: emitted.append(f))
    btn = tab.toolbar.clear_filters_btn if button == "toolbar" else bar.clear_btn
    btn.click()
    _wait(450)                                   # nothing pending from the debounce either
    assert len(emitted) == 1                     # one reload
    f = bar.get_filters()
    assert not f["species"] and not f["location"]
    assert tab._wizard_filters == {}
    assert bar.saved_combo.currentIndex() == 0
    if kind == "obs":
        assert tab._wizard_ids is None
    assert tab.filter_wizard.get_all_filters() == {}


def test_bar_alone_clear_all_still_clears(qapp, settings_isolated):
    """A bar with no tab listening (tests, future use) clears itself."""
    from src.views.scheme.scheme_filter_bar import SchemeFilterBar
    b = SchemeFilterBar()
    b.species_edit.setText("x")
    b.clear_btn.click()
    assert b.get_filters()["species"] == ""


# ---------------------------------------------------------------- 5 Subfamily greyed out

class _ListDb:
    def __init__(self, conn, path):
        self.conn, self.main_db_path = conn, path

    def execute_main(self, sql, params=()):
        return self.conn.execute(sql, params).fetchall()


def _scheme_db(tmp_path, subfamilies):
    p = tmp_path / "o.db"
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE recording_scheme (id INTEGER PRIMARY KEY, species_name TEXT, "
                 "site_name TEXT, date TEXT, vc_number INTEGER, subfamily TEXT, "
                 "verification_status TEXT, recorder TEXT, method TEXT, source TEXT, "
                 "family TEXT, order_name TEXT, vice_county TEXT, determiner TEXT, "
                 "irecord_id TEXT, nbn_atlas_id TEXT, species_tvk TEXT, common_name TEXT, "
                 "comment TEXT, taxon_group TEXT, sex TEXT, stage TEXT, biotope TEXT, "
                 "grid_ref TEXT)")
    for sf in subfamilies:
        conn.execute("INSERT INTO recording_scheme (species_name, date, subfamily, "
                     "verification_status) VALUES ('Rhagium mordax', '2020-05-01', ?, "
                     "'Accepted - correct')", (sf,))
    conn.commit()
    return _ListDb(conn, p)


def test_subfamily_greyed_out_when_empty_and_back_when_values(qapp, tmp_path):
    from src.views.scheme.scheme_filter_bar import SchemeFilterBar
    b = SchemeFilterBar()
    b.initialize_with_database(_scheme_db(tmp_path, [None, "  "]))
    c = b.subfamily_combo
    assert not c.isEnabled()
    assert c.toolTip() == c.display.toolTip() == "No subfamily data on scheme records"
    assert ":disabled" in c.display.styleSheet()          # it looks greyed, not "All" active
    assert c.currentText() == "All" and b.get_filters()["subfamily"] is None
    b2 = SchemeFilterBar()
    b2.initialize_with_database(_scheme_db(tmp_path / "..", ["Lepturinae"]))
    assert b2.subfamily_combo.isEnabled() and b2.subfamily_combo.toolTip() == ""
    assert b2.subfamily_combo.count() == 2


def test_subfamily_still_greyed_if_status_list_fails(qapp, tmp_path, monkeypatch):
    """The statuses query failing used to return before Subfamily was disabled."""
    import src.services.filter_builder as fb
    from src.views.scheme.scheme_filter_bar import SchemeFilterBar
    monkeypatch.setattr(fb, "tab_values", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    b = SchemeFilterBar()
    b.initialize_with_database(_scheme_db(tmp_path, [None]))
    assert not b.subfamily_combo.isEnabled()


@needs_obs
def test_subfamily_on_the_real_scheme_records(qapp):
    from src.views.scheme.scheme_filter_bar import SchemeFilterBar
    conn = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    n = conn.execute("SELECT COUNT(*) FROM recording_scheme "
                     "WHERE TRIM(COALESCE(subfamily, '')) <> ''").fetchone()[0]
    b = SchemeFilterBar()
    b.initialize_with_database(_ListDb(conn, paths.OBSERVATUM_DB))
    assert b.subfamily_combo.isEnabled() == bool(n)
    conn.close()


# ---------------------------------------------------------------- 4 Codex group view

needs_codex = pytest.mark.skipif(not (paths.CODEX_DB.exists() and paths.UKSI_DB.exists()),
                                 reason="needs data/codex.db and uksi.db")
CERAMBYCIDAE = "NHMSYS0020151623"
RHAGIUM = "NHMSYS0020153272"


def _codex_mtime():
    return os.stat(paths.CODEX_DB).st_mtime_ns


@needs_codex
def test_group_members_with_status_match_hand_sql():
    """Every Cerambycidae species/subspecies under the family in UKSI that has a
    status_summary row (none relies on an s.l. fallback here) -- 74 of 88 on the 9 Oct copy."""
    from shared.repositories.codex_repository import CodexRepository
    from Codex.group_statuses import is_group, member_taxa, species_with_status
    before = _codex_mtime()
    assert is_group(CERAMBYCIDAE) and is_group(RHAGIUM)
    assert not is_group("NBNSYS0000011004")                     # Rhagium mordax
    u = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)
    hand_members = {r[0] for r in u.execute("""
        WITH RECURSIVE d(tvk) AS (SELECT ? UNION SELECT t.tvk FROM taxa t JOIN d
                                  ON t.parent_tvk = d.tvk)
        SELECT t.tvk FROM taxa t JOIN d ON t.tvk = d.tvk WHERE t.tvk <> ?
          AND t.rank IN ('Species', 'Subspecies', 'Variety', 'Form', 'Species aggregate',
                         'Species sensu lato', 'Microspecies', 'Species pro parte',
                         'Species group')""", (CERAMBYCIDAE, CERAMBYCIDAE))}
    assert {t for t, _, _ in member_taxa(CERAMBYCIDAE)} == hand_members
    c = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)
    ph = ",".join("?" * len(hand_members))
    hand = {r[0] for r in c.execute(
        f"SELECT DISTINCT tvk FROM status_summary WHERE tvk IN ({ph})", list(hand_members))}
    repo = CodexRepository()
    found = species_with_status(CERAMBYCIDAE, repo)
    assert found["members"] == len(hand_members)
    assert {r[0] for r in found["rows"]} == hand
    names = [r[1] for r in found["rows"]]
    assert names == sorted(names, key=str.lower)
    mordax = next(r for r in found["rows"] if r[1] == "Rhagium mordax")
    st = repo.get_statuses_batch(["NBNSYS0000011004"])["NBNSYS0000011004"]
    assert mordax[3] and st.threat_iucn_2001.value in mordax[3]
    repo.close()
    assert _codex_mtime() == before                             # codex.db only read


@needs_codex
def test_codex_species_tab_family_lists_species_and_opens_one(qapp):
    from PySide6.QtWidgets import QPushButton
    from Codex.species_tab import SpeciesTab
    tab = SpeciesTab()
    tab._select_species(CERAMBYCIDAE, "Cerambycidae")
    texts = [w.text() for w in tab.profile_container.findChildren(type(tab.group_header))]
    assert not any("No conservation status recorded for this species" in t for t in texts)
    n = tab.group_table.rowCount()
    assert n > 0 and tab.group_header.text() == \
        f"<i>Cerambycidae</i> — {n:,} species with a conservation status"
    row = next(i for i in range(n) if tab.group_table.item(i, 0).text() == "Rhagium mordax")
    assert tab.group_table.item(row, 1).text()                  # statuses summarised
    tab.group_table.cellClicked.emit(row, 0)
    _wait(50)
    labels = [w.text() for w in tab.profile_container.findChildren(type(tab.group_header))]
    assert "<i>Rhagium mordax</i>" in labels                    # the species' own view
    back = [b for b in tab.profile_container.findChildren(QPushButton)
            if b.text().startswith("◂ Back to Cerambycidae")]
    assert back
    back[0].click()
    _wait(50)
    assert "species with a conservation status" in tab.group_header.text()
