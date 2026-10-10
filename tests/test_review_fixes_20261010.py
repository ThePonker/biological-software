"""Fixes for the independent review of the 10 Oct 2026 merged work.

  2  species filter never finds fewer records than the old name match (except where the
     text is exactly a UKSI name: N. vespillo still leaves out N. vespilloides)
  3  "X agg." selects the aggregate, not the species
  1  record dialogs open the record of the clicked row after sorting
  4  Atrium: no Data Entry tile; a launch that fails at once is reported
  5  Stats Species Lookup count = what the Observations tab shows
  6  Data Entry VC "0" flagged
  7  import dates: a time part is ignored; a range is refused only if it starts after today
  8  backfill_taxon_groups dry run: per column, samples, blanks only
"""
import os
import sqlite3

import pytest

import paths

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

needs_uksi = pytest.mark.skipif(not paths.UKSI_DB.exists(), reason="needs data/uksi.db")
needs_obs = pytest.mark.skipif(not paths.OBSERVATUM_DB.exists(), reason="needs data/observatum.db")

VESPILLO = "NBNSYS0000023039"
OLIGIA_AGG = "NHMSYS0001703675"
OLIGIA_STRIGILIS = "NBNSYS0000006435"


def _count(conn, table, text):
    from shared.species_filter import species_filter, table_tvks
    f = species_filter(text, table_tvks(lambda s: conn.execute(s).fetchall(), table))
    clause, params = f.sql()
    n_sql = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {clause}", params).fetchone()[0]
    n_mem = sum(1 for r in conn.execute(
        f"SELECT species_tvk, species_name, common_name FROM {table}") if f.matches(*r))
    assert n_sql == n_mem, (table, text, n_sql, n_mem)
    return n_sql


@pytest.fixture()
def small(tmp_path):
    """A tiny record table: a TVK'd record whose common name UKSI doesn't hold, N. vespillo
    and N. vespilloides, the Oligia aggregate and species, and a name-only record."""
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("CREATE TABLE recs (id INTEGER PRIMARY KEY, species_tvk TEXT, "
                 "species_name TEXT, common_name TEXT)")
    from shared.species_search import get_index
    vespilloides = get_index().tvk_for_name("Nicrophorus vespilloides")
    rows = [
        (VESPILLO, "Nicrophorus vespillo", None),
        (vespilloides, "Nicrophorus vespilloides", None),
        ("NBNSYS0000011004", "Rhagium mordax", "Golden-bloomed Grey Longhorn"),
        (OLIGIA_AGG, "Oligia strigilis agg.", None),
        (OLIGIA_STRIGILIS, "Oligia strigilis", None),
        (None, "Cantharis nigra (=thoracica) red scutellum", None),
    ]
    conn.executemany("INSERT INTO recs (species_tvk, species_name, common_name) VALUES (?,?,?)",
                     rows)
    return conn


@needs_uksi
def test_text_uksi_lacks_is_matched_by_name(small):
    assert _count(small, "recs", "Golden-bloomed Grey Longhorn") == 1
    assert _count(small, "recs", "red scutellum") == 1
    assert _count(small, "recs", "agg") == 1


@needs_uksi
def test_exact_name_keeps_precision(small):
    assert _count(small, "recs", "Nicrophorus vespillo") == 1        # not vespilloides


@needs_uksi
def test_partial_text_never_fewer_than_old(small):
    assert _count(small, "recs", "vespillo") == 2                    # as the old filter


@needs_uksi
def test_aggregate_typed_selects_aggregate(small):
    from shared.species_filter import choose_taxa
    assert [r["tvk"] for r in choose_taxa("Oligia strigilis agg.")] == [OLIGIA_AGG]
    assert [r["tvk"] for r in choose_taxa("Oligia strigilis AGG")] == [OLIGIA_AGG]
    assert [r["tvk"] for r in choose_taxa("Oligia strigilis")] == [OLIGIA_STRIGILIS]
    assert _count(small, "recs", "Oligia strigilis agg.") == 1
    assert _count(small, "recs", "Oligia strigilis") == 1


@needs_uksi
@needs_obs
def test_real_figures():
    conn = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
    old = {  # the review's losses come back
        ("recording_scheme", "Golden-bloomed Grey Longhorn"): 40,
        ("recording_scheme", "Tawny Longhorn Beetle"): 13,
        ("recording_scheme", "agg"): 120,
        ("observations", "Oligia strigilis agg."): 5,
        # the earlier agent's figures hold
        ("recording_scheme", "Spotted Longhorn"): 282,
        ("recording_scheme", "rhag mor"): 4628,
        ("recording_scheme", "Rhagium mordx"): 4628,
        ("observations", "Nicrophorus vespillo"): 8,
        ("specimens", "Nicrophorus vespillo"): 4,
        ("recording_scheme", "Strangalia maculata"): 19976,
    }
    for (table, text), n in old.items():
        assert _count(conn, table, text) == n, (table, text)
    n = conn.execute("SELECT COUNT(*) FROM observations WHERE species_name = "
                     "'Cantharis nigra (=thoracica) red scutellum'").fetchone()[0]
    assert _count(conn, "observations", "Cantharis nigra (=thoracica) red scutellum") >= n > 0


# ---------------------------------------------------------------- 1 sorted record dialogs

@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_scheme_vc_records_dialog_opens_clicked_record_after_sort(qapp, monkeypatch):
    """The records dialog is sorted by Location, row 0 double-clicked: the detail dialog
    (which now has Edit / Delete) gets that row's record, not results[0]."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QDialog, QTableWidget
    import src.services.recording_scheme_stats_service as rss
    import src.views.dialogs as dlgs
    import src.views.scheme.scheme_record_actions as sra
    from src.views.stats.scheme_dashboard import SchemeDashboard

    rows = [{"id": 11, "date": "2024-06-01", "site_name": "Zeal Wood", "grid_ref": "SU1",
             "recorder": "A", "determiner": "", "verification_status": "", "source": ""},
            {"id": 22, "date": "2023-06-01", "site_name": "Ashen Bank", "grid_ref": "TQ1",
             "recorder": "B", "determiner": "", "verification_status": "", "source": ""},
            {"id": 33, "date": "2022-06-01", "site_name": "Moor Copse", "grid_ref": "SU2",
             "recorder": "C", "determiner": "", "verification_status": "", "source": ""}]

    class FakeDb:
        def execute_main(self, sql, params=()):
            if "WHERE id = ?" in sql:
                return [dict(r, species_name="Rutpela maculata") for r in rows
                        if r["id"] == params[0]]
            return rows

    class FakeService:
        _db = FakeDb()

        def initialize(self, _db):
            pass

    opened = []

    class FakeDetail(QDialog):
        def __init__(self, record, parent=None, **_k):
            super().__init__(parent)
            opened.append(record)

        def exec(self):
            return 0

    monkeypatch.setattr(rss, "get_recording_scheme_stats", lambda: FakeService())
    monkeypatch.setattr(dlgs, "SchemeRecordDetailDialog", FakeDetail)
    monkeypatch.setattr(sra, "wire_scheme_detail", lambda *a, **k: None)
    shown = []

    def fake_exec(self):
        t = self.findChild(QTableWidget)
        if t is not None and t.rowCount() == 3:
            t.sortByColumn(1, Qt.SortOrder.AscendingOrder)       # Location header
            shown.append(t.item(0, 1).text())
            t.doubleClicked.emit(t.model().index(0, 0))
        return 0

    monkeypatch.setattr(QDialog, "exec", fake_exec)
    sd = SchemeDashboard()
    sd._show_species_vc_records_dialog("Rutpela maculata", 23)
    assert shown == ["Ashen Bank"]
    assert [r["id"] for r in opened] == [22]          # was 11 (the first row loaded)


def test_collection_dashboard_refill_after_sort_keeps_rows_together(qapp):
    from PySide6.QtCore import Qt
    from src.views.stats.collection_dashboard import SimpleBreakdownTable
    t = SimpleBreakdownTable("Storage", filter_type="storage")
    data = [{"k": "Cabinet C", "count": 3}, {"k": "Box A", "count": 1}, {"k": "Drawer B", "count": 2}]
    t.set_data(data, "k")
    t.table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
    t.set_data(data, "k")                       # a refresh with the table sorted
    got = {t.table.item(r, 0).text(): t.table.item(r, 1).text() for r in range(3)}
    assert got == {"Cabinet C": "3", "Box A": "1", "Drawer B": "2"}


# ---------------------------------------------------------------- 4 Atrium

def test_atrium_has_no_data_entry_and_reports_a_failed_start(qapp, monkeypatch):
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtWidgets import QMessageBox
    import time
    from Atrium import atrium_ui, process_manager as pm
    assert "Data Entry" not in [a.name for a in pm.APPS]
    assert "Data Entry" not in [b._app.name for b in atrium_ui.AtriumPanel()._buttons]

    class Proc:
        def __init__(self, code):
            self.code = code

        def poll(self):
            return self.code

    app = next(a for a in pm.APPS if a.name == "Examen")
    said = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: said.append(a[2]))
    monkeypatch.setattr(atrium_ui, "_POLL_MS", 10)

    def run(proc):
        monkeypatch.setattr(app, "process", proc)
        atrium_ui.watch_start(app, None, polls=5)
        end = time.time() + 0.5
        while time.time() < end:
            QCoreApplication.processEvents()

    run(Proc(2))                                   # ended at once with an error
    assert len(said) == 1 and "exit code 2" in said[0] and "Examen" in said[0]
    run(Proc(None))                                # still running: nothing said
    run(Proc(0))                                   # closed normally: nothing said
    assert len(said) == 1
    assert pm.early_exit_code(app) is None


# ---------------------------------------------------------------- 5 Species Lookup

@needs_uksi
def test_species_lookup_counts_match_the_tab(qapp, tmp_path):
    """Corvus corone: the species and its subspecies (the tab's filter) = 106 on Wil's
    data; here 3 + 1 personal, 2 commercial. The button counts what the tab shows."""
    from PySide6.QtWidgets import QPushButton
    from types import SimpleNamespace
    from src.views.stats.species_dashboard import SpeciesDashboard
    conn = sqlite3.connect(tmp_path / "o.db")
    for t in ("observations", "specimens", "recording_scheme"):
        conn.execute(f"CREATE TABLE {t} (id INTEGER PRIMARY KEY, species_tvk TEXT, "
                     "species_name TEXT, common_name TEXT, record_type TEXT, date TEXT)")
    rows = [("NHMSYS0000530315", "Corvus corone", "Personal")] * 3 + [
        ("NHMSYS0000533191", "Corvus corone corone", "Personal"),
        ("NHMSYS0000530315", "Corvus corone", "Commercial"),
        ("NHMSYS0000530315", "Corvus corone", "Commercial")]
    conn.executemany("INSERT INTO observations (species_tvk, species_name, record_type, date) "
                     "VALUES (?, ?, ?, '2024-05-01')", rows)

    class Db:
        def execute_main(self, sql, params=()):
            return conn.execute(sql, params).fetchall()

    d = SpeciesDashboard()
    d._db = Db()
    d._search_results = [SimpleNamespace(
        scientific_name="Corvus corone", tvk="NHMSYS0000530315", common_name="Carrion Crow",
        family="Corvidae", order_name="Passeriformes", old_name=None, match_type="exact")]
    d._on_completer_activated(d._display(d._search_results[0]))
    sp = d._selected_species
    assert (sp["personalRecords"], sp["commercialRecords"], sp["observationRecords"]) == (4, 2, 6)
    assert sum(sp["phenology"]) == 6
    buttons = [b.text() for b in d.detail_container.findChildren(QPushButton)
               if b.text().startswith("View")]
    assert buttons == ["View 6 Records"]


# ---------------------------------------------------------------- 6 Data Entry VC No.

@pytest.mark.parametrize("typed, want", [
    ("", (True, None)), (None, (True, None)), ("41", (True, 41)), (41, (True, 41)),
    ("41.0", (True, 41)), ("113", (True, 113)),
    ("0", (False, None)), (0, (False, None)), ("41a", (False, None)), ("200", (False, None)),
    ("-3", (False, None)), ("4.5", (False, None))])
def test_read_vc(typed, want):
    from DataEntry.commit_service import read_vc
    assert read_vc(typed) == want


def test_vc_zero_is_flagged_and_stays_in_staging(qapp, tmp_path):
    from PySide6.QtCore import Qt
    from DataEntry import staging_repo as repo
    from DataEntry.commit_service import commit_job, precommit_issues
    from DataEntry.entry_grid import COLIDX, StagingTableModel
    conn = sqlite3.connect(tmp_path / "s.db")
    conn.row_factory = sqlite3.Row
    repo.ensure_schema(conn)
    pid = repo.ensure_personal_job(conn)
    repo.insert_row(conn, pid, {"species_name": "Carabus nemoralis", "date": "2024-05-01",
                                "site_name": "Wood", "grid_ref": "SP4030", "recorder": "W"})
    m = StagingTableModel(conn, pid, None)
    idx = m.index(0, COLIDX["vc_number"])
    m.setData(idx, "0", Qt.ItemDataRole.EditRole)
    assert m.data(idx, Qt.ItemDataRole.BackgroundRole) is not None          # flagged
    assert "VC number" in m.data(idx, Qt.ItemDataRole.ToolTipRole)
    rows = repo.fetch_rows(conn, pid)
    assert precommit_issues(rows)["unreadable VC No."] == [1]
    created = []

    class Model:
        def create(self, obs):
            created.append(obs)
            return len(created)

    class Obs:
        def __init__(self, **kw):
            self.kw = kw

    s = commit_job(None, Model(), conn, repo.get_job(conn, pid), observation_cls=Obs, taxonomy={})
    assert s["committed"] == 0 and s["skipped_bad_vc"] == 1 and s["remaining"] == 1
    m.setData(idx, "38", Qt.ItemDataRole.EditRole)
    assert m.data(idx, Qt.ItemDataRole.BackgroundRole) is None
    assert m.data(idx, Qt.ItemDataRole.DisplayRole) == "38"


# ---------------------------------------------------------------- 7 import dates

@pytest.mark.parametrize("text, want", [
    ("01/06/2024 00:00", ("2024-06-01", "D")),
    ("01/06/2024 10:30:00", ("2024-06-01", "D")),
    ("2024-06-01T10:30:00+01:00", ("2024-06-01", "D")),
    ("2024-06-01T10:30:00Z", ("2024-06-01", "D")),
    ("1/6/2024 10:30 pm", ("2024-06-01", "D")),
    ("01/06/2024 10:30 - 02/06/2024 11:00", ("2024-06-01", "DD")),
    ("2025-2026", ("2025-01-01", "YY")),           # runs on past today: kept
])
def test_import_dates_time_ignored_and_ranges(text, want):
    import datetime as dt
    from shared.import_core import parse_record_date
    p = parse_record_date(text, today=dt.date(2026, 10, 10))
    assert (p.date, p.date_type, p.error) == (*want, "")


def test_import_dates_still_refused_and_two_digit_year_shown():
    import datetime as dt
    from shared.import_core import date_bounds, parse_record_date
    today = dt.date(2026, 10, 10)
    assert parse_record_date("11/10/2026 09:00", today=today).error.startswith("Date is in the future")
    assert parse_record_date("2027-2028", today=today).error.startswith("Date is in the future")
    assert parse_record_date("10:30", today=today).error.startswith("Unreadable date")
    p = parse_record_date("24/06/01", today=today)
    assert p.date == "2001-06-24" and "24/06/2001" in p.note
    assert date_bounds("01/06/2024 00:00", today) == ("2024-06-01", "2024-06-01")


def test_personal_import_warns_with_the_full_date():
    import test_imports_20261010 as ti
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    got = ti._obs([dict(ti.OBS, Date="24/06/01"), dict(ti.OBS, Date="01/06/2024 10:30")])
    assert got[0].status.name == "WARNING" and "24/06/2001" in got[0].error_message
    assert got[0].date == "2001-06-24" and got[0].import_notes == ""
    assert (got[1].status.name, got[1].date) == ("VALID", "2024-06-01")


# ---------------------------------------------------------------- 8 backfill dry run

from test_taxon_groups_20261010 import dbs  # noqa: E402,F401  (the small DB pair fixture)


def test_backfill_dry_run_per_column_samples_and_odd_keys(dbs, capsys):  # noqa: F811
    import importlib.util
    o, uksi, tmp = dbs
    o.execute("UPDATE observations SET taxonomic_sort_key = '000204010603030U01' WHERE id = 2")
    o.commit()
    o.close()
    spec = importlib.util.spec_from_file_location(
        "backfill_taxon_groups", os.path.join(os.path.dirname(paths.__file__), "scripts",
                                              "backfill_taxon_groups.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    db = str(tmp / "observatum.db")
    before = sqlite3.connect(db).execute("SELECT * FROM observations ORDER BY id").fetchall()
    assert m.main(["--db", db, "--uksi", uksi]) == 0
    out = capsys.readouterr().out
    assert "taxonomic_sort_key   fill       1   kept       3" in out
    assert "NULL -> 19018000" in out
    assert "not in our number format: 1" in out and "'000204010603030U01'" in out
    assert "Nothing has been changed" in out
    assert sqlite3.connect(db).execute("SELECT * FROM observations ORDER BY id").fetchall() == before


# ---------------------------------------------------------------- 3 the tab shows an asked-for aggregate

def test_observations_tab_shows_aggregate_asked_for_by_name(qapp, monkeypatch):
    """With "exclude incomplete species" on (the default), aggregates are hidden -- unless the
    species box names one ('Oligia strigilis agg.'): navigating there showed an empty table."""
    from types import SimpleNamespace
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QLineEdit
    from src.views.observations.observation_filter_mixin import ObservationFilterMixin
    monkeypatch.setattr(QSettings, "value", lambda self, key, default=None, type=None: True)
    tab = ObservationFilterMixin()
    edit = QLineEdit()
    tab.filter_bar = SimpleNamespace(species_edit=edit)
    obs = [{"species_tvk": OLIGIA_AGG, "species_name": "Oligia strigilis agg."},
           {"species_tvk": OLIGIA_STRIGILIS, "species_name": "Oligia strigilis"}]
    edit.setText("Oligia")
    assert len(tab._apply_record_exclusion(obs)) == 1          # the setting, as before
    edit.setText("Oligia strigilis agg.")
    assert len(tab._apply_record_exclusion(obs)) == 2
    assert tab._count_species_with_exclusion(obs[:1]) == 1
