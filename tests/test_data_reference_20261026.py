"""The Reference column (data_reference), 26 Oct 2026: migration, the app with and without the
column, suggestions, the import wizards' stamping, the Observations and Mapping filters,
and import_contributed --reference. Small purpose-made databases only."""
import os
import sqlite3
import shutil
import subprocess
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import paths  # noqa: E402
from shared import data_reference as dr  # noqa: E402

import pathlib  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, os.path.join(str(ROOT), "scripts"))
import add_data_reference as mig  # noqa: E402


def _link_or_copy(src, dst):
    """A symlink to the real uksi.db; a copy where Windows refuses a symlink without the
    privilege (WinError 1314)."""
    try:
        os.symlink(str(src), str(dst))
    except OSError:
        shutil.copy2(str(src), str(dst))


OBS_COLS = ("id INTEGER PRIMARY KEY, species_name TEXT, species_tvk TEXT, date TEXT, grid_ref TEXT, "
            "site_name TEXT, recorder TEXT, record_type TEXT, quantity INTEGER, "
            "created_at TEXT, embargo_status TEXT, embargo_until TEXT, project_name TEXT, irecord_id INTEGER")


def make_db(path, with_column=False):
    c = sqlite3.connect(path)
    extra = ", data_reference TEXT" if with_column else ""
    for t in dr.TABLES:
        c.execute(f"CREATE TABLE {t} ({OBS_COLS}{extra})")
    rows = [("Aaa bbb", "T1", "2020-01-01", "SP1010", "A", "x", "Personal", 1, "2024-01-01"),
            ("Ccc ddd", "T2", "2021-01-01", "SP2020", "B", "y", "Personal", 1, "2024-02-01"),
            ("Eee fff", "T3", "2022-01-01", "SP3030", "C", "z", "Personal", 2, "2024-03-01")]
    for t in dr.TABLES:
        for r in rows:
            c.execute(f"INSERT INTO {t} (species_name, species_tvk, date, grid_ref, site_name, "
                      f"recorder, record_type, quantity, created_at) VALUES (?,?,?,?,?,?,?,?,?)", r)
    c.commit()
    c.close()
    return path


def set_refs(path, table, refs_by_id):
    c = sqlite3.connect(path)
    for i, ref in refs_by_id.items():
        c.execute(f"UPDATE {table} SET data_reference = ?, created_at = ? WHERE id = ?",
                  (ref[0], ref[1], i))
    c.commit()
    c.close()


@pytest.fixture(autouse=True)
def fresh_cache():
    dr.clear_cache()
    yield
    dr.clear_cache()


@pytest.fixture
def db_without(tmp_path):
    return str(make_db(tmp_path / "without.db"))


@pytest.fixture
def db_with(tmp_path):
    p = str(make_db(tmp_path / "with.db", with_column=True))
    set_refs(p, "observations", {1: ("Joe Bloggs, data to 1990", "2024-05-01"),
                                 2: ("Joe Bloggs, data to 1990", "2024-05-02")})
    set_refs(p, "recording_scheme", {1: ("Jane Smith, Kent records", "2024-06-01")})
    set_refs(p, "contributed_observations", {1: ("joe bloggs 1991-1993", "2024-04-01")})
    return p


class FakeDb:
    """Just enough of the app's database manager for the code under test."""

    def __init__(self, path):
        self.path = path

    def main_connection(self):
        import contextlib

        @contextlib.contextmanager
        def cm():
            c = sqlite3.connect(self.path)
            c.row_factory = sqlite3.Row
            try:
                yield c
            finally:
                c.close()
        return cm()

    def execute_main(self, q, p=()):
        with self.main_connection() as c:
            return c.execute(q, p).fetchall()

    def execute_main_write(self, q, p=()):
        c = sqlite3.connect(self.path)
        try:
            n = c.execute(q, p).lastrowid
            c.commit()
            return n
        finally:
            c.close()

    def execute_main_many(self, q, plist):
        c = sqlite3.connect(self.path)
        try:
            c.executemany(q, plist)
            c.commit()
            return len(plist)
        finally:
            c.close()


def counts(path):
    c = sqlite3.connect(path)
    try:
        return {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in dr.TABLES}
    finally:
        c.close()


# ---------------------------------------------------------------- migration
def test_dry_run_changes_nothing(db_without, capsys):
    before = open(db_without, "rb").read()
    assert mig.main(["--db", db_without]) == 0
    out = capsys.readouterr().out
    assert open(db_without, "rb").read() == before
    assert "ALTER TABLE observations ADD COLUMN data_reference TEXT" in out
    assert "idx_recording_scheme_data_reference" in out
    assert out.strip().endswith("Run with --apply to write.") and "Nothing has been changed." in out


def test_apply_adds_column_and_index_once(db_without, tmp_path, capsys):
    bdir = str(tmp_path / "backups")
    before = counts(db_without)
    assert mig.main(["--db", db_without, "--apply", "--backup-dir", bdir]) == 0
    c = sqlite3.connect(db_without)
    for t in dr.TABLES:
        assert dr.COLUMN in {r[1] for r in c.execute(f"PRAGMA table_info({t})")}
        assert c.execute("SELECT 1 FROM sqlite_master WHERE type='index' AND name=?",
                         (dr.INDEX_FMT.format(table=t),)).fetchone()
        assert c.execute(f"SELECT COUNT(*) FROM {t} WHERE data_reference IS NOT NULL").fetchone()[0] == 0
    c.close()
    assert counts(db_without) == before
    backups = os.listdir(bdir)
    assert len(backups) == 1 and "pre_add_data_reference" in backups[0]
    assert counts(os.path.join(bdir, backups[0])) == before          # the backup is the old file
    # a second --apply is a no-op: no new backup, nothing changed
    snap = open(db_without, "rb").read()
    assert mig.main(["--db", db_without, "--apply", "--backup-dir", bdir]) == 0
    assert "nothing to do" in capsys.readouterr().out
    assert len(os.listdir(bdir)) == 1 and open(db_without, "rb").read() == snap


def test_apply_refuses_on_an_away_machine(db_without, tmp_path, monkeypatch):
    import shared.away_mode as am
    monkeypatch.setattr(am, "away_active", lambda: True)
    before = open(db_without, "rb").read()
    with pytest.raises(SystemExit):
        mig.main(["--db", db_without, "--apply", "--backup-dir", str(tmp_path / "b")])
    assert open(db_without, "rb").read() == before


# ---------------------------------------------------------------- app with / without the column
def test_has_column_with_and_without(db_without, db_with):
    for path, expect in ((db_without, False), (db_with, True)):
        c = sqlite3.connect(path)
        assert all(dr.has_column(c, t) is expect for t in dr.TABLES)
        c.close()
    assert dr.db_has_column(None, "observations") is False


def test_suggestions_without_column_is_empty_not_a_crash(db_without):
    c = sqlite3.connect(db_without)
    assert dr.suggestions(c, "joe") == []
    c.close()


def test_field_disabled_with_tooltip_when_column_missing(db_without, db_with):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from src.views.components.reference_field import ReferenceField
    f = ReferenceField(FakeDb(db_without), "observations")
    assert not f.isEnabled() and f.toolTip() == "Run scripts\\add_data_reference.py to add the Reference column"
    assert f.reference() is None
    g = ReferenceField(FakeDb(db_with), "observations")
    assert g.isEnabled() and "iRecord/NBN" in g.toolTip()
    assert g.placeholderText() == "e.g. Joe Bloggs, data to 1990"
    g.setText("  Joe  ")
    assert g.reference() == "Joe"


# ---------------------------------------------------------------- suggestions
def test_suggestions_contains_case_insensitive_recent_first(db_with):
    c = sqlite3.connect(db_with)
    assert dr.suggestions(c, "JOE") == ["Joe Bloggs, data to 1990", "joe bloggs 1991-1993"]
    assert dr.suggestions(c, "bloggs, data") == ["Joe Bloggs, data to 1990"]
    assert dr.suggestions(c, "kent") == ["Jane Smith, Kent records"]
    assert dr.suggestions(c, "nobody") == []
    assert dr.suggestions(c, "") == ["Jane Smith, Kent records", "Joe Bloggs, data to 1990",
                                     "joe bloggs 1991-1993"]
    c.close()


def test_suggestions_at_most_15(tmp_path):
    p = str(make_db(tmp_path / "many.db", with_column=True))
    c = sqlite3.connect(p)
    for i in range(30):
        c.execute("INSERT INTO observations (species_name, data_reference, created_at) VALUES "
                  "('s', ?, ?)", (f"Source {i:02d}", f"2024-01-{i + 1:02d}"))
    c.commit()
    got = dr.suggestions(c)
    assert len(got) == 15 and got[0] == "Source 29"
    c.close()
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from src.views.components.reference_field import ReferenceField
    f = ReferenceField(FakeDb(p), "observations")
    assert len(f.refresh_suggestions("source")) == 15 and len(f.suggestions()) == 15


# ---------------------------------------------------------------- import stamping
def test_stamp_records_only_with_reference_and_column(db_without, db_with):
    recs = [{"species_name": "a"}, {"species_name": "b"}]
    assert dr.stamp_records(FakeDb(db_with), "observations", recs, " Joe Bloggs, data to 1990 ") == 2
    assert all(r["data_reference"] == "Joe Bloggs, data to 1990" for r in recs)
    for db, ref in ((FakeDb(db_without), "x"), (FakeDb(db_with), "  "), (FakeDb(db_with), None)):
        plain = [{"species_name": "a"}]
        assert dr.stamp_records(db, "observations", plain, ref) == 0 and "data_reference" not in plain[0]


class _Field:
    def __init__(self, v):
        self.v = v

    def reference(self):
        return self.v


def test_observation_wizard_batch_writes_reference_on_every_row(db_with):
    from src.views.dialogs.observation_import_wizard.wizard_import_mixin import WizardImportMixin

    class W(WizardImportMixin):
        pass
    w = W()
    w.db = FakeDb(db_with)
    w.reference_edit = _Field("Sam Jones, 2025 beetles")
    n = w._batch_insert_observations([{"species_name": "p", "date": "2025-01-01"},
                                      {"species_name": "q", "date": "2025-01-02"}])
    assert n == 2
    c = sqlite3.connect(db_with)
    assert c.execute("SELECT COUNT(*) FROM observations WHERE data_reference = 'Sam Jones, 2025 beetles'"
                     ).fetchone()[0] == 2
    c.close()


def test_scheme_wizard_batch_writes_reference_on_every_row(db_with):
    from src.views.dialogs.scheme_import_wizard.wizard_import_mixin import WizardImportMixin

    class W(WizardImportMixin):
        pass
    w = W()
    w.db = FakeDb(db_with)
    w.reference_edit = _Field("NBN extract, private")
    assert w._batch_insert_records([{"species_name": "p"}, {"species_name": "q"}]) == 2
    c = sqlite3.connect(db_with)
    assert c.execute("SELECT COUNT(*) FROM recording_scheme WHERE data_reference = 'NBN extract, private'"
                     ).fetchone()[0] == 2
    c.close()


def test_wizard_import_without_column_still_works(db_without):
    from src.views.dialogs.observation_import_wizard.wizard_import_mixin import WizardImportMixin

    class W(WizardImportMixin):
        pass
    w = W()
    w.db = FakeDb(db_without)
    w.reference_edit = _Field("ignored")
    assert w._batch_insert_observations([{"species_name": "p", "date": "2025-01-01"}]) == 1


def test_wizard_pages_have_a_reference_line(db_with):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from PySide6.QtWidgets import QStackedWidget
    from src.views.dialogs.observation_import_wizard.wizard_pages_mixin import WizardPagesMixin as OP
    from src.views.dialogs.scheme_import_wizard.wizard_pages_mixin import WizardPagesMixin as SP

    for cls, table in ((OP, "observations"), (SP, "recording_scheme")):
        class P(cls):
            pass
        p = P()
        p.db = FakeDb(db_with)
        p.stack = QStackedWidget()
        p._accent = p._accent_dark = "#4a7c59"
        p._browse_file = lambda: None
        p._create_file_selection_page()
        assert p.reference_edit.isEnabled() and p.reference_edit.available
        assert p.reference_edit.placeholderText() == "e.g. Joe Bloggs, data to 1990"
        p.reference_edit.setText("joe")
        p.reference_edit.refresh_suggestions("joe")
        assert p.reference_edit.suggestions() == ["Joe Bloggs, data to 1990", "joe bloggs 1991-1993"]


# ---------------------------------------------------------------- Observations filter
def _repo(path):
    from src.repositories.observation_repository import ObservationRepository
    return ObservationRepository(FakeDb(path))


def test_observations_repository_filter(db_with, db_without):
    repo = _repo(db_with)
    allrows = repo.search(limit=999)
    assert repo.search(data_reference="", limit=999) and len(repo.search(data_reference=None, limit=999)) == len(allrows) == 3
    got = repo.search(data_reference="BLOGGS", limit=999)
    assert sorted(o.id for o in got) == [1, 2]
    assert all(o.data_reference == "Joe Bloggs, data to 1990" for o in got)
    assert repo.search(data_reference="100%_", limit=999) == []        # % and _ are not wildcards
    # without the column: the filter is left out, nothing crashes, counts unchanged
    assert len(_repo(db_without).search(data_reference="bloggs", limit=999)) == 3


def test_observations_tab_client_filter_and_empty_filter_changes_nothing(db_with):
    from src.views.observations.observation_filter_mixin import ObservationFilterMixin
    rows = [{"id": 1, "data_reference": "Joe Bloggs, data to 1990"}, {"id": 2, "data_reference": None},
            {"id": 3, "data_reference": "Other"}]
    m = ObservationFilterMixin()
    assert [r["id"] for r in m._apply_filters(rows, {"data_reference": "joe"})] == [1]
    assert len(m._apply_filters(rows, {"data_reference": ""})) == 3
    assert len(m._apply_filters(rows, {})) == 3


def test_observation_filter_bar_holds_the_reference(db_with, db_without):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from src.views.observations.observation_filter_bar import ObservationFilterBar
    bar = ObservationFilterBar()
    assert bar.get_filters()["data_reference"] == ""
    assert not bar.reference_edit.isEnabled()                       # not bound yet
    bar.reference_edit.bind(FakeDb(db_without), "observations")
    assert not bar.reference_edit.isEnabled()
    bar.reference_edit.bind(FakeDb(db_with), "observations")
    assert bar.reference_edit.isEnabled()
    bar._set_saved_values({"data_reference": "joe bloggs"})         # a saved filter holds it
    assert bar.get_filters()["data_reference"] == "joe bloggs"
    bar._reset_widgets()
    assert bar.get_filters()["data_reference"] == ""


# ---------------------------------------------------------------- Mapping filter
def _map_ids(path, table, filters):
    from src.services import map_selection as ms
    where, params = ms.build_query(table, [], "all", filters, None, today="2000-01-01")
    c = sqlite3.connect(path)
    try:
        return sorted(r[0] for r in c.execute(f"SELECT id FROM {table} WHERE {where}", params))
    finally:
        c.close()


def test_mapping_reference_filter(db_with):
    from src.services.map_selection import MapFilters
    assert _map_ids(db_with, "observations", MapFilters(data_reference="bloggs")) == [1, 2]
    assert _map_ids(db_with, "recording_scheme", MapFilters(data_reference="KENT")) == [1]
    assert _map_ids(db_with, "contributed_observations", MapFilters(data_reference="joe")) == [1]
    for t in dr.TABLES:                                   # empty filter: the same rows as before
        assert _map_ids(db_with, t, MapFilters(data_reference="")) == \
            _map_ids(db_with, t, MapFilters()) == [1, 2, 3]
    assert "data_reference" not in " ".join(
        __import__("src.services.map_selection", fromlist=["x"]).build_query(
            "observations", [], "all", MapFilters(), None, today="2000-01-01")[0].split())


def test_mapping_panel_reference_box(db_with, db_without, monkeypatch):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from src.views.mapping.filter_panel import MapFilterPanel
    monkeypatch.setattr(paths, "OBSERVATUM_DB", __import__("pathlib").Path(db_without))
    monkeypatch.setattr("src.views.mapping.filter_panel.distinct_values", lambda k: [])
    monkeypatch.setattr("src.views.mapping.filter_panel.vc_choices", lambda: [])
    panel = MapFilterPanel()
    assert not panel.reference_edit.isEnabled()
    f, _ = panel.filters()
    assert f.data_reference == ""
    dr.clear_cache()
    monkeypatch.setattr(paths, "OBSERVATUM_DB", __import__("pathlib").Path(db_with))
    panel = MapFilterPanel()
    assert panel.reference_edit.isEnabled()
    panel.reference_edit.setText("joe")
    assert panel.filters()[0].data_reference == "joe"
    panel.clear_all()
    assert panel.reference_edit.text() == ""


# ---------------------------------------------------------------- records shown / edited
def test_detail_dialogs_show_reference_when_set():
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
    from src.views.dialogs.record_detail_dialog import RecordDetailDialog
    from src.views.dialogs.scheme_record_detail_dialog import SchemeRecordDetailDialog
    for cls, meth in ((RecordDetailDialog, "_add_observation_fields"),
                      (SchemeRecordDetailDialog, "_add_people_section")):
        for ref, shown in (("Joe Bloggs, data to 1990", True), ("", False)):
            seen = []

            class D(cls):
                def __init__(self):
                    self.record = {"data_reference": ref, "recorder": "r"}

                def _add_label_value_row(self, layout, label, value, mono=False):
                    seen.append((label, value))
            getattr(D(), meth)(QVBoxLayout(QWidget()))
            assert (("Reference", ref) in seen) is shown
    assert QLabel


def test_edit_dialog_reference_field(db_with, db_without):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from src.views.dialogs.edit_observation_dialog import EditObservationDialog
    rec = {"species_name": "Aaa bbb", "species_tvk": "T1", "data_reference": "Joe Bloggs, data to 1990"}
    d = EditObservationDialog(observation=rec, db=FakeDb(db_with))
    assert d.reference_edit.isEnabled() and d.reference_edit.text() == "Joe Bloggs, data to 1990"
    assert d.get_observation_data()["data_reference"] == "Joe Bloggs, data to 1990"
    d.reference_edit.setText("")
    assert d.get_observation_data()["data_reference"] is None
    d2 = EditObservationDialog(observation=rec, db=FakeDb(db_without))
    assert not d2.reference_edit.isEnabled()
    assert "data_reference" not in d2.get_observation_data()


# ---------------------------------------------------------------- scripts/import_contributed.py
def test_similar_references_contains_and_close_matches(db_with):
    c = sqlite3.connect(db_with)
    got = dr.similar_references(c, "Joe Bloggs data to 1990")           # close, not contained
    assert "Joe Bloggs, data to 1990" in got
    assert dr.similar_references(c, "bloggs")[0:2] == ["Joe Bloggs, data to 1990", "joe bloggs 1991-1993"]
    assert dr.similar_references(c, "Zebediah") == []
    c.close()


def test_import_contributed_reference(tmp_path):
    uksi = paths.UKSI_DB
    if not uksi.exists():
        pytest.skip("needs data/uksi.db")
    openpyxl = pytest.importorskip("openpyxl")
    root = tmp_path / "root"
    (root / "data").mkdir(parents=True)
    _link_or_copy(uksi, root / "data" / "uksi.db")
    db = str(root / "data" / "observatum.db")
    make_db(db, with_column=True)
    c = sqlite3.connect(db)
    for col in ("source_file", "contributor", "import_batch"):
        c.execute(f"ALTER TABLE contributed_observations ADD COLUMN {col} TEXT")
    c.execute("CREATE VIEW assessment_records AS SELECT species_name, 'x' origin, date, "
              "'' project_name FROM contributed_observations")
    c.commit()
    c.close()
    set_refs(db, "contributed_observations", {1: ("Joe Bloggs, data to 1990", "2024-04-01")})
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Species", "Date", "Grid"])
    ws.append(["Rhagium mordax", "2024-06-01", "SP094868"])
    ws.append(["Rhagium inquisitor", "2024-06-02", "SP094868"])
    xlsx = str(tmp_path / "joe.xlsx")
    wb.save(xlsx)
    env = dict(os.environ, BIOSOFT_ROOT=str(root), BIOSOFT_NO_AWAY_COPY="1")
    args = [sys.executable, str(ROOT / "scripts" / "import_contributed.py"), xlsx,
            "--contributor", "Bloggs, J.", "--project", "Test", "--site", "S",
            "--reference", "Joe Bloggs data to 1993"]
    r = subprocess.run(args, env=env, capture_output=True, text=True, cwd=str(tmp_path))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "Existing references that resemble it" in r.stdout and "'Joe Bloggs, data to 1990'" in r.stdout
    assert "DRY RUN" in r.stdout
    # no column: refuses to apply a reference
    plain = str(tmp_path / "root2" / "data")
    os.makedirs(plain)
    _link_or_copy(uksi, plain + "/uksi.db")
    make_db(plain + "/observatum.db", with_column=False)
    c = sqlite3.connect(plain + "/observatum.db")
    for col in ("source_file", "contributor", "import_batch"):
        c.execute(f"ALTER TABLE contributed_observations ADD COLUMN {col} TEXT")
    c.commit()
    c.close()
    env2 = dict(env, BIOSOFT_ROOT=str(tmp_path / "root2"))
    r2 = subprocess.run(args, env=env2, capture_output=True, text=True, cwd=str(tmp_path))
    assert "add_data_reference.py" in r2.stdout


# ---------------------------------------------------------------- review fixes (26 Oct 2026)
def test_migration_is_one_transaction(db_without, tmp_path, monkeypatch, capsys):
    real = dr.ensure_schema

    def fails_after_first_table(conn):
        conn.execute("ALTER TABLE observations ADD COLUMN data_reference TEXT")
        conn.execute("CREATE INDEX idx_observations_data_reference ON observations(data_reference)")
        raise RuntimeError("injected fault")
    monkeypatch.setattr(dr, "ensure_schema", fails_after_first_table)
    assert mig.main(["--db", db_without, "--apply", "--backup-dir", str(tmp_path / "b")]) == 1
    assert "Nothing has been changed" in capsys.readouterr().out
    c = sqlite3.connect(db_without)
    for t in dr.TABLES:
        assert dr.COLUMN not in {r[1] for r in c.execute(f"PRAGMA table_info({t})")}
    assert c.execute("SELECT COUNT(*) FROM sqlite_master WHERE name LIKE '%data_reference%'").fetchone()[0] == 0
    c.close()
    monkeypatch.setattr(dr, "ensure_schema", real)             # and it still works afterwards
    assert mig.main(["--db", db_without, "--apply", "--backup-dir", str(tmp_path / "b")]) == 0


def test_migration_locked_database_says_so(db_without, tmp_path, capsys):
    holder = sqlite3.connect(db_without, isolation_level=None)
    holder.execute("BEGIN IMMEDIATE")
    try:
        rc = mig.main(["--db", db_without, "--apply", "--backup-dir", str(tmp_path / "b")])
    finally:
        holder.execute("ROLLBACK")
        holder.close()
    out = capsys.readouterr().out
    assert rc == 1
    assert "Close Observatum (and anything else using observatum.db) and run it again. " \
           "Nothing has been changed." in out
    c = sqlite3.connect(db_without)
    assert dr.COLUMN not in {r[1] for r in c.execute("PRAGMA table_info(observations)")}
    c.close()


def test_mapping_reference_does_not_fold_scheme_duplicates(tmp_path):
    from src.services.map_selection import MapFilters, build_query
    p = str(make_db(tmp_path / "dups.db", with_column=True))
    c = sqlite3.connect(p)
    for t in ("observations", "recording_scheme"):
        c.execute(f"DELETE FROM {t}")
    for i in range(1, 21):
        c.execute("INSERT INTO observations (species_name, grid_ref, irecord_id, record_type, "
                  "created_at) VALUES ('s', 'SP1010', ?, 'Personal', '2024-01-01')", (i,))
        c.execute("INSERT INTO recording_scheme (species_name, grid_ref, irecord_id, data_reference, "
                  "created_at) VALUES ('s', 'SP1010', ?, 'Joe Bloggs', '2024-01-01')", (i,))
    c.commit()

    def ids(part, ref):
        where, params = build_query("recording_scheme", [], "all", MapFilters(data_reference=ref),
                                    None, part=part, today="2000-01-01")
        return len(c.execute(f"SELECT id FROM recording_scheme WHERE {where}", params).fetchall())
    assert ids("mapped", "") == 0 and ids("merged", "") == 20         # folded, as before
    assert ids("mapped", "joe") == 20 and ids("merged", "joe") == 0   # Reference: on their own
    c.close()


def test_map_note_and_tooltip_say_specimens_are_left_out():
    from src.services.map_selection import REFERENCE_NO_SPECIMENS, MapFilters, MapResult
    from src.views.mapping.map_notes import map_note
    assert REFERENCE_NO_SPECIMENS == ("Insect Collection records have no Reference and are left out "
                                      "while the Reference filter is set.")
    assert "Insect Collection records have no Reference" in map_note(MapResult(), MapFilters(data_reference="x"))
    assert "Insect Collection" not in map_note(MapResult(), MapFilters())
    assert "duplicate records" not in map_note(MapResult(merged=0), MapFilters(data_reference="x"))


def test_mapping_panel_tooltip_mentions_specimens(db_with, monkeypatch):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from src.views.mapping.filter_panel import MapFilterPanel
    monkeypatch.setattr(paths, "OBSERVATUM_DB", pathlib.Path(db_with))
    monkeypatch.setattr("src.views.mapping.filter_panel.distinct_values", lambda k: [])
    monkeypatch.setattr("src.views.mapping.filter_panel.vc_choices", lambda: [])
    assert "Insect Collection records have no Reference" in MapFilterPanel().reference_edit.toolTip()


def test_saved_reference_is_ignored_where_the_column_is_missing(db_without, db_with):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from src.views.observations.observation_filter_bar import ObservationFilterBar
    from src.views.observations.observation_filter_mixin import ObservationFilterMixin
    bar = ObservationFilterBar()
    bar.reference_edit.bind(FakeDb(db_without), "observations")
    bar._set_saved_values({"data_reference": "bloggs"})
    assert bar.reference_edit.text() == "" and bar.get_filters()["data_reference"] == ""
    assert "(Reference ignored: column not added yet)" in bar.reference_edit.toolTip()

    class Tab(ObservationFilterMixin):
        filter_bar = bar
    rows = [{"id": 1, "data_reference": None}, {"id": 2}]
    assert len(Tab()._apply_filters(rows, {"data_reference": "bloggs"})) == 2     # list not emptied
    bar.reference_edit.bind(FakeDb(db_with), "observations")
    assert Tab()._apply_filters(rows, {"data_reference": "bloggs"}) == []


def test_import_contributed_replace_keeps_the_reference_or_asks(tmp_path):
    uksi = paths.UKSI_DB
    if not uksi.exists():
        pytest.skip("needs data/uksi.db")
    openpyxl = pytest.importorskip("openpyxl")
    root = tmp_path / "root"
    (root / "data").mkdir(parents=True)
    _link_or_copy(uksi, root / "data" / "uksi.db")
    db = str(root / "data" / "observatum.db")
    make_db(db, with_column=True)
    c = sqlite3.connect(db)
    for col in ("source_file", "contributor", "import_batch"):
        c.execute(f"ALTER TABLE contributed_observations ADD COLUMN {col} TEXT")
    c.execute("UPDATE contributed_observations SET source_file='joe.xlsx', contributor='Bloggs, J.', "
              "data_reference='Joe Bloggs, data to 1990', import_batch='b' WHERE id = 1")
    c.commit()
    c.close()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Species", "Date", "Grid"])
    ws.append(["Rhagium mordax", "2024-06-01", "SP094868"])
    xlsx = str(tmp_path / "joe.xlsx")
    wb.save(xlsx)
    env = dict(os.environ, BIOSOFT_ROOT=str(root), BIOSOFT_NO_AWAY_COPY="1")
    base = [sys.executable, str(ROOT / "scripts" / "import_contributed.py"), xlsx,
            "--contributor", "Bloggs, J.", "--project", "Test", "--site", "S", "--replace"]

    def run(*extra):
        return subprocess.run(base + list(extra), env=env, capture_output=True, text=True,
                              cwd=str(tmp_path)).stdout
    out = run()
    assert "carry the Reference: ['Joe Bloggs, data to 1990']" in out
    assert "x --replace would lose it" in out and "Fix the items marked x" in out
    assert "would lose it" not in run("--reference", "Joe Bloggs, data to 1990")
    assert "would lose it" not in run("--drop-reference")
