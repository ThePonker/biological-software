"""Filtering speed, all record tabs (speed review, 10 Oct 2026).

  * typing in a filter box reloads once the typing pauses, not per key; Enter and text set by
    the program apply at once (views/components/filter_debounce.py);
  * Clear All and a saved filter reload once (they reloaded once per widget: 58 s on the
    Recording Scheme tab);
  * the scheme loader no longer emits its 110,510 records through a Qt signal (7 of 9 s),
    and a load replaced by a newer filter is cancelled, not waited for;
  * the Insect Collection model is filled in one reset; Observation rows are built without
    re-reading the dataclass fields per row.
Counts are the same as before, checked against hand SQL on a copy of data/observatum.db.
"""
import os
import sqlite3
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import paths  # noqa: E402

DB = paths.OBSERVATUM_DB


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def db_copy(tmp_path_factory):
    if not os.path.exists(DB):
        pytest.skip("no data/observatum.db")
    dst = tmp_path_factory.mktemp("speed") / "observatum.db"
    src = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    out = sqlite3.connect(dst)
    src.backup(out)
    out.close()
    src.close()
    return str(dst)


@pytest.fixture
def settings_isolated(qapp):
    from PySide6.QtCore import QCoreApplication, QSettings
    org, app = QCoreApplication.organizationName(), QCoreApplication.applicationName()
    QCoreApplication.setOrganizationName("ObservatumTests")
    QCoreApplication.setApplicationName("speed_20261010")
    QSettings().clear()
    yield
    QCoreApplication.setOrganizationName(org)
    QCoreApplication.setApplicationName(app)


def _hand(db, sql, params=()):
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return c.execute(sql, params).fetchone()[0]
    finally:
        c.close()


class _Count:
    def __init__(self, signal):
        self.n = 0
        signal.connect(self)

    def __call__(self, *a):
        self.n += 1


def _wait(ms):
    """Process events for ms. (Not QTest.qWait: it keeps Python's lock while it waits, so
    a loader thread barely runs -- the app's own event loop lets it.)"""
    from PySide6.QtWidgets import QApplication
    end = time.perf_counter() + ms / 1000
    while time.perf_counter() < end:
        QApplication.processEvents()
        time.sleep(0.005)


# ── the debounce helper ───────────────────────────────────────────────────────

def test_typing_waits_for_a_pause_enter_and_program_apply_at_once(qapp):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QLineEdit
    from src.views.components.filter_debounce import DEBOUNCE_MS, debounce_text
    e = QLineEdit()
    calls = []
    debounce_text(e, lambda: calls.append(e.text()))
    e.show()
    QTest.keyClicks(e, "rhag mor")
    assert calls == []                                  # nothing per key
    _wait(DEBOUNCE_MS + 200)
    assert calls == ["rhag mor"]                        # one reload after the pause
    QTest.keyClicks(e, "d")
    QTest.keyClick(e, Qt.Key.Key_Return)
    assert calls[-1] == "rhag mord" and len(calls) == 2   # Enter: at once
    _wait(DEBOUNCE_MS + 200)
    assert len(calls) == 2                              # ... and not again
    e.setText("Rhagium mordax")                         # navigation / saved filter
    assert calls[-1] == "Rhagium mordax" and len(calls) == 3
    QTest.keyClick(e, Qt.Key.Key_Return)                # Enter with nothing pending
    assert len(calls) == 3


# ── one reload for Clear All and for a saved filter, every bar ──────────────────

def _scheme_bar():
    from src.views.scheme.scheme_filter_bar import SchemeFilterBar
    b = SchemeFilterBar()
    b.vc_combo.addItem("23 - Oxon", 23)
    return b


def test_scheme_bar_clear_and_saved_filter_reload_once(qapp, settings_isolated):
    from PySide6.QtCore import QDate
    b = _scheme_bar()
    b.species_edit.setText("rhag mor")
    b.location_edit.setText("wood")
    b.recorder_edit.setText("Heeney")
    b.date_from_edit.setDate(QDate(2000, 1, 1))
    b.vc_combo.setCurrentIndex(1)
    b.status_combo.setCurrentIndex(1)
    n = _Count(b.filters_changed)
    b.clear_filters()
    assert n.n == 1
    f = b.get_filters()
    assert not f["species"] and not f["location"] and not f["recorder"]
    assert f["date_from"] is None and f["vice_county"] in (None, "") and f["status"] is None
    b._apply_saved_filter({"species": "Rhagium mordax", "location": "wood", "vice_county": 23,
                           "date_from": "2001-02-03"})
    assert n.n == 2
    f = b.get_filters()
    assert (f["species"], f["location"], f["vice_county"], f["date_from"]) == \
        ("Rhagium mordax", "wood", 23, "2001-02-03")
    _wait(500)
    assert n.n == 2                                     # nothing left pending


def test_scheme_bar_clear_drops_a_pending_keystroke_reload(qapp, settings_isolated):
    from PySide6.QtTest import QTest
    from src.views.components.filter_debounce import DEBOUNCE_MS
    b = _scheme_bar()
    b.show()
    n = _Count(b.filters_changed)
    QTest.keyClicks(b.species_edit, "rhag")
    b.clear_filters()
    _wait(DEBOUNCE_MS + 200)
    assert n.n == 1 and b.get_filters()["species"] == ""


def test_observation_bar_clear_saved_and_navigation_reload_once(qapp, settings_isolated):
    from src.views.observations.observation_filter_bar import ObservationFilterBar
    b = ObservationFilterBar()
    b.species_edit.setText("rhag")
    b.location_edit.setText("wood")
    b.family_edit.setText("Cerambycidae")
    n = _Count(b.filters_changed)
    b.clear_filters()
    assert n.n == 1
    b._apply_saved_filter({"species": "Rhagium mordax", "location": "wood",
                           "family": "Cerambycidae"})
    assert n.n == 2
    f = b.get_filters()
    assert (f["species"], f["location"], f["family"]) == ("Rhagium mordax", "wood", "Cerambycidae")
    b.set_species_filter("Rutpela maculata")             # used to reload twice
    assert n.n == 3
    f = b.get_filters()
    assert f["species"] == "Rutpela maculata" and not f["location"] and not f["family"]


def test_observation_bar_enter_applies_once(qapp, settings_isolated):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from src.views.components.filter_debounce import DEBOUNCE_MS
    from src.views.observations.observation_filter_bar import ObservationFilterBar
    b = ObservationFilterBar()
    b.show()
    n = _Count(b.filters_changed)
    QTest.keyClicks(b.species_edit, "rhag mor")
    assert n.n == 0
    QTest.keyClick(b.species_edit, Qt.Key.Key_Return)
    assert n.n == 1
    _wait(DEBOUNCE_MS + 200)
    assert n.n == 1


def test_collection_bar_clear_and_saved_filter_reload_once(qapp, settings_isolated):
    from src.views.collection.collection_filters import CollectionFilterBar
    b = CollectionFilterBar()
    b.species_edit.setText("rhag")
    b.location_edit.setText("wood")
    b.collector_edit.setText("Heeney")
    b.family_edit.setText("Cerambycidae")
    n = _Count(b.filters_changed)
    b.clear_filters()
    assert n.n == 1
    assert not any(b.get_filters()[k] for k in ("species", "location", "collector", "family"))
    b._apply_saved_filter({"species": "Rhagium mordax", "collector": "Heeney"})
    assert n.n == 2
    b.set_species_filter("Rutpela maculata")             # applied once (its callers reloaded
    assert n.n == 3 and b.get_filters()["species"] == "Rutpela maculata"   # a second time)


# ── the scheme loader ─────────────────────────────────────────────────────────

def _scheme_rows(db, filters):
    from src.views.scheme.scheme_data_worker import SchemeDataWorker
    w = SchemeDataWorker(db, filters)
    w.run()
    assert w.error_message is None
    return len(w.results[0])


def test_scheme_counts_unchanged(qapp, db_copy, settings_isolated):
    """The loader's counts, against hand SQL (figures as on 9 Oct's copy in the comments)."""
    h = lambda sql: _hand(db_copy, sql)  # noqa: E731
    mordax = h("SELECT COUNT(*) FROM recording_scheme WHERE species_name = 'Rhagium mordax'")
    assert mordax == 4628
    for text in ("rhag mor", "Rhagium mordx", "Rhagium mordax"):
        assert _scheme_rows(db_copy, {"species": text}) == mordax
    assert _scheme_rows(db_copy, {"location": "wood"}) == h(
        "SELECT COUNT(*) FROM recording_scheme WHERE site_name LIKE '%wood%'")       # 16,645
    assert _scheme_rows(db_copy, {"vice_county": 23}) == h(
        "SELECT COUNT(*) FROM recording_scheme WHERE vc_number = 23")
    assert _scheme_rows(db_copy, {"location": "wood", "status": "Accepted"}) == h(
        "SELECT COUNT(*) FROM recording_scheme WHERE site_name LIKE '%wood%' "
        "AND verification_status LIKE 'Accepted%'")
    assert _scheme_rows(db_copy, None) == h("SELECT COUNT(*) FROM recording_scheme")  # 110,510


def test_scheme_worker_cancelled_gives_no_results_and_no_error(qapp, db_copy):
    from src.views.scheme.scheme_data_worker import SchemeDataWorker
    w = SchemeDataWorker(db_copy, None)
    errors = []
    w.error.connect(errors.append)
    w.cancel()
    w.run()
    assert w.results_ready.is_set() and w.results is None and w.error_message is None
    assert errors == []


def test_scheme_tab_newer_filter_replaces_running_load_without_waiting(
        qapp, db_copy, settings_isolated, monkeypatch):
    import src.views.scheme.recording_scheme_tab as rst
    from src.models.database import get_database
    db = get_database()
    old = (db._main_db_path, db._uksi_db_path)
    db.set_main_path(db_copy)
    try:
        tab = rst.RecordingSchemeTab()
        tab._main_db_path = db_copy
        tab._db = db
        tab._initialized = True
        loads = []
        orig = tab._on_data_loaded
        monkeypatch.setattr(tab, "_on_data_loaded",
                            lambda recs, n: (loads.append(len(recs)), orig(recs, n)))
        t = time.perf_counter()
        tab._load_data(None)                             # all 110,510: still running ...
        first = tab._data_worker
        tab._load_data({"species": "Rhagium mordax"})    # ... when the filter changes
        assert time.perf_counter() - t < 1.0             # no 2 s wait on the old load
        assert first.cancelled
        deadline = time.perf_counter() + 60
        while not loads and time.perf_counter() < deadline:
            _wait(50)
        _wait(300)
        assert loads == [4628]                           # only the newer filter is shown
        assert tab.table_model.rowCount() == 4628
        first.wait(10000)
    finally:
        db._main_db_path, db._uksi_db_path = old


def test_scheme_worker_emits_no_record_signal():
    """Emitting 110,510 dicts through Signal(list, int) took 7 s and ~0.9 GB."""
    import inspect
    from src.views.scheme import scheme_data_worker
    assert "finished.emit(" not in inspect.getsource(scheme_data_worker)


# ── Observation rows, Insect Collection model ─────────────────────────────────

def test_row_to_observation_same_as_before(qapp, db_copy):
    from dataclasses import asdict, fields
    from src.models.observation import Observation
    from src.repositories.observation_repository import ObservationRepository

    def old(row):                                        # the code before 10 Oct
        keys = row.keys()
        kw = {f.name: row[f.name] for f in fields(Observation) if f.name in keys}
        return Observation(**kw)

    c = sqlite3.connect(f"file:{db_copy}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    rows = c.execute("SELECT * FROM observations ORDER BY id LIMIT 300").fetchall()
    some = c.execute("SELECT id, species_name, date FROM observations LIMIT 5").fetchall()
    c.close()
    repo = ObservationRepository.__new__(ObservationRepository)
    for r in list(rows) + list(some):                    # two column sets
        assert asdict(repo._row_to_observation(r)) == asdict(old(r))


def test_specimen_model_one_reset_same_sorted_rows(qapp, settings_isolated):
    from PySide6.QtCore import QSortFilterProxyModel, Qt
    from src.views.collection.specimen_table_model import SpecimenTableModel
    specimens = [{"id": i, "species_name": n, "date_collected": d, "site_name": s}
                 for i, (n, d, s) in enumerate([
                     ("Rhagium mordax", "2020-05-01", "Wytham Wood"),
                     ("Agapanthia villosoviridescens", "2019-06-02", "Otmoor"),
                     ("Rutpela maculata", "2021-07-03", "Bernwood"),
                     ("Leptura quadrifasciata", "2018-08-04", "Wychwood")])]

    def shown(m, fill_quietly):
        p = QSortFilterProxyModel()
        p.setSourceModel(m)
        p.setDynamicSortFilter(True)
        col = [c[0] for c in m.get_columns()].index("species_name")
        p.sort(col, Qt.SortOrder.AscendingOrder)
        resets = []
        m.modelReset.connect(lambda: resets.append(1))
        if fill_quietly:
            m.set_specimens(list(specimens))
        else:
            m._fill_rows(list(specimens))                # row by row, as before
        out = [p.index(r, col).data() for r in range(p.rowCount())]
        return out, len(resets)

    new, resets = shown(SpecimenTableModel(), True)
    before, _ = shown(SpecimenTableModel(), False)
    assert new == before == sorted(s["species_name"] for s in specimens)
    assert resets == 1


# ── the index script ──────────────────────────────────────────────────────────

def test_add_filter_indexes_dry_run_changes_nothing(tmp_path, capsys):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "add_filter_indexes", os.path.join(paths.ROOT, "scripts", "add_filter_indexes.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    db = tmp_path / "o.db"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE recording_scheme (id INTEGER PRIMARY KEY, species_tvk TEXT, "
              "species_name TEXT, vc_number INTEGER, date TEXT, family TEXT)")
    c.executemany("INSERT INTO recording_scheme VALUES (?,?,?,?,?,?)",
                  [(1, "T1", "Rhagium mordax", 23, "2020-01-01", "Cerambycidae"),
                   (2, "T1", "Rhagium mordax", 23, "2019-01-01", "Cerambycidae"),
                   (3, "T2", "Rutpela maculata", 22, "2021-01-01", "Cerambycidae")])
    c.commit()
    c.close()
    assert mod.main(["--db", str(db)]) == 0
    out = capsys.readouterr().out
    assert "Nothing has been changed" in out and "identical to before: True" in out
    c = sqlite3.connect(db)
    names = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    c.close()
    assert "idx_scheme_tvk_vc_date" not in names
    assert mod.main(["--db", str(db), "--apply", "--backup-dir", str(tmp_path / "bk")]) == 0
    c = sqlite3.connect(db)
    names = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    c.close()
    assert "idx_scheme_tvk_vc_date" in names and len(os.listdir(tmp_path / "bk")) == 1
