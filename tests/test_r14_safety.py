"""Round 14 safety fixes (25 Oct 2026): nothing deleted, backups before changes, errors shown.
Small purpose-made databases and temp folders only; backups go to a temporary root."""
import ast
import importlib.util
import json
import os
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "Observatum"), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


@pytest.fixture
def backup_root(tmp_path, monkeypatch):
    from shared import backup_service
    root = tmp_path / "backups"
    root.mkdir()
    monkeypatch.setattr(backup_service, "BACKUP_ROOT", str(root))
    monkeypatch.setenv("BIOSOFT_BACKUP_ROOT", str(root))
    return root


def _load_script(name):
    spec = importlib.util.spec_from_file_location(f"r14_{name}", ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _tables(path):
    c = sqlite3.connect(path)
    try:
        return {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        c.close()


# --- 1. Munia migration ------------------------------------------------------------------

def _old_munia(path):
    c = sqlite3.connect(path)
    c.executescript("""
        CREATE TABLE projects (id INTEGER PRIMARY KEY, year INTEGER, project_name TEXT);
        CREATE INDEX idx_projects_years ON projects(year);
        CREATE TABLE capacity (year INTEGER, month INTEGER);
        INSERT INTO projects VALUES (1, 2024, 'Old job');
    """)
    c.commit()
    c.close()


def test_munia_migration_backs_up_and_renames(tmp_path, backup_root):
    from Munia import munia_data
    db = tmp_path / "munia.db"
    _old_munia(str(db))
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    munia_data.ensure_schema(conn)
    conn.close()
    tabs = _tables(str(db))
    old = [t for t in tabs if t.startswith("projects_old_")]
    assert old, tabs
    assert any(t.startswith("capacity_old_") for t in tabs)
    c = sqlite3.connect(str(db))
    assert c.execute(f"SELECT project_name FROM {old[0]}").fetchone()[0] == "Old job"
    assert "start_year" in [r[1] for r in c.execute("PRAGMA table_info(projects)")]
    c.close()
    kept = list((backup_root / "kept").glob("munia_pre-munia-migrate_*.db"))
    assert len(kept) == 1
    k = sqlite3.connect(str(kept[0]))          # the backup holds the old tables as they were
    assert k.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 1
    k.close()


def test_munia_migration_refused_when_backup_fails(tmp_path, backup_root, monkeypatch):
    from Munia import munia_data
    from shared import backup_service
    monkeypatch.setattr(backup_service, "write_kept_copy", lambda *a, **k: None)
    db = tmp_path / "munia.db"
    _old_munia(str(db))
    conn = sqlite3.connect(str(db))
    with pytest.raises(RuntimeError):
        munia_data.ensure_schema(conn)
    conn.close()
    assert _tables(str(db)) == {"projects", "capacity"}


# --- 6. saved filters --------------------------------------------------------------------

def test_saved_filters_not_overwritten_after_failed_load(tmp_path):
    from src.services.saved_filters_service import SavedFiltersService
    f = tmp_path / "saved_filters.json"
    f.write_text("{ not json", encoding="utf-8")
    svc = SavedFiltersService(f)
    assert svc.load_error
    assert svc.save_filter("Wood", {"a": 1}) is False
    assert f.read_text(encoding="utf-8") == "{ not json"


def test_saved_filters_save_is_atomic_and_reports_result(tmp_path):
    from src.services.saved_filters_service import SavedFiltersService
    f = tmp_path / "saved_filters.json"
    svc = SavedFiltersService(f)
    assert svc.load_error is None
    assert svc.save_filter("Wood", {"a": 1}) is True
    assert json.loads(f.read_text(encoding="utf-8"))["filters"]["observations/Wood"]["config"] == {"a": 1}
    assert not (tmp_path / "saved_filters.json.tmp").exists()


# --- 7. restore_database -----------------------------------------------------------------

def _make_db(path, rows):
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE observations (id INTEGER)")
    c.execute("CREATE TABLE specimens (id INTEGER)")
    c.executemany("INSERT INTO observations VALUES (?)", [(i,) for i in range(rows)])
    c.commit()
    c.close()


def _calls(path, names):
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    found = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            f = n.func
            nm = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
            if nm in names:
                found.append((nm, n.lineno))
    return found


@pytest.mark.parametrize("script", ["restore_database", "organise_reviews", "prepare_ne_reviews",
                                    "build_uksi_from_release"])
def test_changed_scripts_never_delete(script):
    assert _calls(ROOT / "scripts" / f"{script}.py", {"remove", "unlink", "rmtree", "rmdir"}) == []


def test_restore_moves_side_files_aside_and_in_use_creates_nothing(tmp_path, backup_root, monkeypatch):
    import paths
    live, src = tmp_path / "observatum.db", tmp_path / "backup.db"
    _make_db(str(live), 1)
    _make_db(str(src), 5)
    (tmp_path / "observatum.db-wal").write_bytes(b"")
    (tmp_path / "observatum.db-shm").write_bytes(b"")
    monkeypatch.setattr(paths, "OBSERVATUM_DB", str(live))
    rd = _load_script("restore_database")
    # in_use on a missing file must not create it
    assert rd.in_use(str(tmp_path / "nothing.db")) is False
    assert not (tmp_path / "nothing.db").exists()
    monkeypatch.setattr(sys, "argv", ["restore_database.py", str(src)])
    monkeypatch.setattr("builtins.input", lambda *_: "y")
    assert rd.main() == 0
    c = sqlite3.connect(str(live))
    assert c.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 5
    c.close()
    assert not (tmp_path / "observatum.db.restoring").exists()
    moved = [p.name for p in (backup_root / "_expired").iterdir()]
    assert any(n.endswith("observatum.db-wal") for n in moved)
    assert any(n.endswith("observatum.db-shm") for n in moved)


# --- 9. organise / prepare move originals ---------------------------------------------------

@pytest.mark.parametrize("script", ["organise_reviews", "prepare_ne_reviews"])
def test_file_away_moves_original_beside_it(script, tmp_path):
    tree = ast.parse((ROOT / "scripts" / f"{script}.py").read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "file_away")
    ns = {"os": os}
    exec(compile(ast.Module([fn], []), script, "exec"), ns)
    a = tmp_path / "review.pdf"
    a.write_bytes(b"x")
    dest = ns["file_away"](str(a))
    assert not a.exists() and Path(dest).read_bytes() == b"x"
    assert Path(dest).parent == tmp_path / "_filed"
    b = tmp_path / "review.pdf"                       # same name again: nothing overwritten
    b.write_bytes(b"y")
    dest2 = ns["file_away"](str(b))
    assert dest2 != dest and Path(dest).read_bytes() == b"x" and Path(dest2).read_bytes() == b"y"


# --- 8. build_uksi moves aside, never removes -----------------------------------------------

def test_build_uksi_moves_existing_output_to_expired():
    src = (ROOT / "scripts" / "build_uksi_from_release.py").read_text(encoding="utf-8")
    assert "backup_service._retire(OUT" in src
    assert "os.remove" not in src


def test_retire_moves_file_into_expired(tmp_path, backup_root):
    from shared import backup_service
    f = tmp_path / "uksi_2025.db"
    f.write_bytes(b"data")
    backup_service._retire(str(f), "uksi_2025-replaced")
    assert not f.exists()
    assert [p.read_bytes() for p in (backup_root / "_expired").iterdir()] == [b"data"]


# --- 4. species account delete by id ---------------------------------------------------------

class _FakeDb:
    def __init__(self, path):
        self.path, self.writes = path, []

    def execute_main(self, q, p=()):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        try:
            return c.execute(q, p).fetchall()
        finally:
            c.close()

    def execute_main_write(self, q, p=()):
        self.writes.append((q, p))
        c = sqlite3.connect(self.path)
        c.execute(q, p)
        c.commit()
        c.close()


def test_species_account_delete_is_by_row_id(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from src.views.components import delete_guard
    from src.views.home import species_profile_dialog as spd
    path = str(tmp_path / "o.db")
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE species_profiles (id INTEGER PRIMARY KEY, species_tvk TEXT, species_name TEXT)")
    c.executemany("INSERT INTO species_profiles VALUES (?,?,?)",
                  [(1, "T1", "Foo bar"), (2, "T2", "Foo bar")])
    c.commit()
    c.close()
    db = _FakeDb(path)
    monkeypatch.setattr(spd, "get_database", lambda: db)
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    backed = []
    monkeypatch.setattr(delete_guard, "backup_before_delete", lambda *a, **k: backed.append(1) or True)
    emitted = []
    fake = SimpleNamespace(_tvk="", _species_name="Foo bar", profile_deleted=SimpleNamespace(
        emit=lambda: emitted.append(1)), accept=lambda: None)
    spd.SpeciesProfileDialog._on_delete(fake)
    assert backed and emitted
    assert db.writes and all("WHERE id = ?" in q for q, _ in db.writes)
    assert [tuple(p) for _, p in db.writes] == [(1,), (2,)]


# --- 2. mark as commercial takes a backup -------------------------------------------------------

def _mark_commercial(monkeypatch, backup_ok, away=False):
    from PySide6.QtWidgets import QDialog, QMessageBox
    from shared import away_mode, backup_service
    from src.models import database
    from src.views.dialogs import mark_commercial_dialog as mcd
    from src.views.observations.observation_tab import ObservationTab

    class FakeDialog:
        def __init__(self, n, parent=None):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

        def get_commercial_data(self):
            return {"record_type": "Commercial"}

    class FakeDb:
        writes = []

        def execute_main_write(self, q, p=()):
            self.writes.append((q, p))

    labels, shown = [], []
    fdb = FakeDb()
    monkeypatch.setattr(mcd, "MarkCommercialDialog", FakeDialog)
    monkeypatch.setattr(database, "get_database", lambda: fdb)
    monkeypatch.setattr(backup_service, "backup_main_only", lambda label="": labels.append(label) or backup_ok)
    monkeypatch.setattr(away_mode, "away_active", lambda: away)
    for kind in ("critical", "warning"):
        monkeypatch.setattr(QMessageBox, kind, staticmethod(lambda *a, **k: shown.append(a[1])))
    fake = SimpleNamespace(table_model=SimpleNamespace(get_checked_ids=lambda: [3, 4]),
                           _load_data=lambda: None, records_changed=SimpleNamespace(emit=lambda: None))
    ObservationTab._mark_as_commercial(fake)
    return fdb.writes, labels, shown


def test_mark_commercial_takes_backup_first(monkeypatch):
    writes, labels, shown = _mark_commercial(monkeypatch, backup_ok=True)
    assert labels == ["pre-mark-commercial"] and len(writes) == 1 and not shown


def test_mark_commercial_refused_if_backup_fails(monkeypatch):
    writes, labels, shown = _mark_commercial(monkeypatch, backup_ok=False)
    assert labels == ["pre-mark-commercial"] and writes == [] and shown


def test_mark_commercial_refused_in_away_mode(monkeypatch):
    writes, labels, shown = _mark_commercial(monkeypatch, backup_ok=True, away=True)
    assert writes == [] and labels == [] and shown


def _deadline_munia(path):
    """The intermediate schema: deadlines still on `projects`, children with ON DELETE CASCADE."""
    c = sqlite3.connect(path)
    c.executescript("""
    CREATE TABLE projects (id INTEGER PRIMARY KEY AUTOINCREMENT, start_year INTEGER NOT NULL,
     end_year INTEGER NOT NULL, project_name TEXT NOT NULL, client TEXT DEFAULT '',
     status TEXT DEFAULT 'quoted', quote_value REAL DEFAULT 0,
     created_at TEXT DEFAULT (datetime('now')), id_deadline TEXT, UNIQUE(start_year, project_name));
    CREATE TABLE project_annual_days (project_id INTEGER NOT NULL REFERENCES projects(id)
     ON DELETE CASCADE, year INTEGER NOT NULL, micro_days REAL DEFAULT 0,
     report_days REAL DEFAULT 0, PRIMARY KEY (project_id, year));
    CREATE TABLE project_field_months (project_id INTEGER NOT NULL REFERENCES projects(id)
     ON DELETE CASCADE, year INTEGER NOT NULL, month INTEGER NOT NULL,
     field_days REAL DEFAULT 0, PRIMARY KEY (project_id, year, month));
    INSERT INTO projects (id,start_year,end_year,project_name) VALUES (1,2025,2025,'A');
    INSERT INTO project_annual_days VALUES (1,2025,3,4);
    INSERT INTO project_field_months VALUES (1,2025,5,2);
    """)
    c.commit()
    c.close()


def test_munia_deadline_migration_keeps_child_rows_and_backs_up(tmp_path, backup_root):
    """Review 25 Oct: DROP TABLE projects with foreign keys on cascaded into the child tables."""
    from Munia import munia_data
    db = tmp_path / "munia.db"
    _deadline_munia(str(db))
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    munia_data.ensure_schema(conn)
    assert conn.execute("SELECT COUNT(*) FROM project_annual_days").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM project_field_months").fetchone()[0] == 1
    cols = [r[1] for r in conn.execute("PRAGMA table_info(projects)")]
    assert "id_deadline" not in cols and "start_year" in cols
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    conn.close()
    assert list((backup_root / "kept").glob("munia_pre-munia-migrate_*.db"))


def test_munia_retire_is_all_or_nothing(tmp_path, backup_root):
    """A failure half way through renaming puts every table back as it was."""
    from Munia import munia_data
    db = tmp_path / "munia.db"
    _old_munia(str(db))
    before = _tables(str(db))
    conn = sqlite3.connect(str(db))
    original = conn.execute

    class Boom:
        def __init__(self, c):
            self.c = c

        def __getattr__(self, name):
            return getattr(self.c, name)

        def execute(self, sql, *a):
            if "RENAME TO" in sql and '"projects"' in sql:   # after capacity was renamed
                raise sqlite3.OperationalError("database is locked")
            return original(sql, *a)

    with pytest.raises(sqlite3.OperationalError):
        munia_data._retire_old_schema(Boom(conn))
    conn.close()
    assert _tables(str(db)) == before


def test_restore_in_use_ignores_shm_left_by_a_closed_reader(tmp_path):
    """Review 25 Oct: a closed read-only look at a WAL database leaves a -shm; that is not 'in use'."""
    rd = _load_script("restore_database")
    db = tmp_path / "observatum.db"
    c = sqlite3.connect(str(db))
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("CREATE TABLE t (x)")
    c.commit()
    c.close()
    r = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    r.execute("SELECT COUNT(*) FROM t").fetchone()
    r.close()
    assert not rd.in_use(str(db))
    holder = sqlite3.connect(str(db))
    holder.execute("BEGIN IMMEDIATE")
    holder.execute("INSERT INTO t VALUES (1)")
    try:
        assert rd.in_use(str(db))
    finally:
        holder.rollback()
        holder.close()
