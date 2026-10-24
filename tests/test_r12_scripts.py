"""Round 12: the Codex rebuild's keep / compare / swap steps, prune_backups, reset_database,
seed_codex. Small purpose-made databases in tmp_path; backups go to a temporary root."""
import importlib.util
import os
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "Observatum"), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _load(name):
    spec = importlib.util.spec_from_file_location(f"r12_{name}", ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def backup_root(tmp_path, monkeypatch):
    from shared import backup_service
    root = tmp_path / "backups"
    root.mkdir()
    monkeypatch.setattr(backup_service, "BACKUP_ROOT", str(root))
    monkeypatch.setenv("BIOSOFT_BACKUP_ROOT", str(root))
    return root


def _kept_db(path, manual=2, reviews=1, profiles=1, sqs_manual=1):
    c = sqlite3.connect(path)
    c.executescript("""
        CREATE TABLE manual_entries (id INTEGER PRIMARY KEY, tvk TEXT, species_name TEXT,
            status_track TEXT, status_value TEXT, status_detail TEXT, source_review TEXT,
            date_added TEXT, added_by TEXT, notes TEXT, review_id INTEGER);
        CREATE TABLE sqs_scores (tvk TEXT PRIMARY KEY, sqs INTEGER, source TEXT);
        CREATE TABLE reviews (id INTEGER PRIMARY KEY, review_name TEXT, author TEXT,
            taxon_group TEXT, status_track TEXT, date_published TEXT, date_imported TEXT,
            source_file TEXT, species_count INTEGER, supersedes_id INTEGER, notes TEXT, licence TEXT);
        CREATE TABLE species_profiles (id INTEGER PRIMARY KEY, tvk TEXT, review_id INTEGER,
            species_name TEXT, profile_text TEXT, source TEXT, date_added TEXT,
            date_updated TEXT, added_by TEXT);
    """)
    for i in range(manual):
        c.execute("INSERT INTO manual_entries (tvk, species_name, status_track, status_value) "
                  "VALUES (?, 'x', 't', 'v')", (f"T{i}",))
    for i in range(reviews):
        c.execute("INSERT INTO reviews (review_name) VALUES (?)", (f"r{i}",))
    for i in range(profiles):
        c.execute("INSERT INTO species_profiles (tvk, review_id, profile_text) VALUES (?, 1, 'p')",
                  (f"P{i}",))
    for i in range(sqs_manual):
        c.execute("INSERT INTO sqs_scores VALUES (?, 8, 'manual')", (f"S{i}",))
    c.execute("INSERT INTO sqs_scores VALUES ('PAN', 4, 'pantheon')")
    c.commit()
    c.close()


@pytest.fixture(scope="module")
def bcd():
    return _load("build_codex_db")


# ---------------- build_codex_db: keep / compare / swap ----------------

def test_keep_step_aborts_on_a_locked_database_and_changes_nothing(tmp_path, bcd):
    db = tmp_path / "codex.db"
    _kept_db(db)
    before = db.read_bytes()
    other = sqlite3.connect(db, isolation_level=None)
    other.execute("BEGIN EXCLUSIVE")
    try:
        with pytest.raises(bcd.KeptReadError):
            bcd.read_kept(str(db), timeout=0.2)
    finally:
        other.execute("ROLLBACK")
        other.close()
    assert db.read_bytes() == before


def test_keep_step_reads_everything_and_missing_tables_are_fine(tmp_path, bcd):
    db = tmp_path / "codex.db"
    _kept_db(db, manual=3, reviews=2, profiles=4, sqs_manual=2)
    man, sqs, rev, prof = bcd.read_kept(str(db))
    assert (len(man), len(sqs), len(rev), len(prof)) == (3, 2, 2, 4)
    empty = tmp_path / "empty.db"
    sqlite3.connect(empty).close()
    assert bcd.read_kept(str(empty)) == ([], [], [], [])


def test_keep_step_reads_an_older_schema_without_status_detail(tmp_path, bcd):
    db = tmp_path / "codex.db"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE manual_entries (tvk TEXT, species_name TEXT, status_track TEXT, "
              "status_value TEXT, source_review TEXT, date_added TEXT, added_by TEXT, notes TEXT)")
    c.execute("INSERT INTO manual_entries VALUES ('T','n','t','v',NULL,NULL,NULL,NULL)")
    c.commit()
    c.close()
    man = bcd.read_kept(str(db))[0]
    assert len(man) == 1 and man[0][4] is None


def test_count_mismatch_is_reported_and_match_passes(tmp_path, bcd):
    new = tmp_path / "codex_new.db"
    _kept_db(new, manual=2, reviews=1, profiles=1, sqs_manual=1)
    conn = sqlite3.connect(new)
    kept = {"manual_entries": 2, "sqs_scores (manual)": 1, "reviews": 1, "species_profiles": 1}
    rows, ok = bcd.compare_kept(kept, conn)
    assert ok
    kept["manual_entries"] = 3
    rows, ok = bcd.compare_kept(kept, conn)
    assert not ok
    assert [r for r in rows if r[1] != r[2]] == [("manual_entries", 3, 2)]
    conn.close()


def test_swap_moves_the_old_file_and_never_deletes_it(tmp_path, backup_root, bcd):
    codex, new = tmp_path / "codex.db", tmp_path / "codex_new.db"
    _kept_db(codex, manual=5)
    _kept_db(new, manual=1)
    old_bytes = codex.read_bytes()
    replaced = bcd.swap_in(str(new), str(codex))
    assert replaced and Path(replaced).parent == backup_root / "reference"
    assert Path(replaced).name.startswith("codex_replaced_")
    assert Path(replaced).read_bytes() == old_bytes
    assert not new.exists()
    assert sqlite3.connect(codex).execute("SELECT COUNT(*) FROM manual_entries").fetchone()[0] == 1


def test_swap_with_no_old_file_just_puts_the_new_one_in_place(tmp_path, backup_root, bcd):
    codex, new = tmp_path / "codex.db", tmp_path / "codex_new.db"
    _kept_db(new)
    assert bcd.swap_in(str(new), str(codex)) is None
    assert codex.exists() and not new.exists()


def test_stale_codex_new_is_moved_aside_not_deleted(tmp_path, bcd):
    new = tmp_path / "codex_new.db"
    new.write_bytes(b"left over")
    aside = bcd.move_aside_stale(str(new))
    assert not new.exists()
    assert Path(aside).name.startswith("codex_new_failed_") and Path(aside).read_bytes() == b"left over"
    assert bcd.move_aside_stale(str(new)) is None


# ---------------- prune_backups ----------------

def _touch(folder, name, data=b"x"):
    (folder / name).write_bytes(data)


def test_prune_dry_run_moves_nothing_and_apply_keeps_newest_per_label(tmp_path, backup_root, capsys):
    pb = _load("prune_backups")
    ref = backup_root / "reference"
    ref.mkdir()
    pb.CODEX_KEEP = set()
    names = [
        "observatum_pre_import_20261001_100000.db", "observatum_pre_import_20261002_100000.db",
        "observatum_pre_import_20261003_100000.db",
        "observatum_pre_merge_20261001_100000.db",
        "codex_pre_review_20261001_100000.db", "codex_pre_review_20261005_100000.db",
        "codex_pre_other_20260901_100000.db",
        "codex.db", "uksi.db",
    ]
    for n in names:
        _touch(ref, n)
    assert pb.label_of("observatum_pre_import_20261001_100000.db") == "observatum_pre_import.db"

    assert pb.main([]) == 0
    out = capsys.readouterr().out
    assert out.rstrip().endswith("Nothing has been changed.")
    assert sorted(os.listdir(ref)) == sorted(names)
    assert not (ref / "_expired").exists()

    assert pb.main(["--apply"]) == 0
    left = set(os.listdir(ref)) - {"_expired"}
    assert left == {
        "observatum_pre_import_20261002_100000.db", "observatum_pre_import_20261003_100000.db",
        "observatum_pre_merge_20261001_100000.db",
        "codex_pre_review_20261005_100000.db", "codex_pre_other_20260901_100000.db",
        "codex.db", "uksi.db"}
    assert set(os.listdir(ref / "_expired")) == {
        "observatum_pre_import_20261001_100000.db", "codex_pre_review_20261001_100000.db"}


def test_prune_keeps_the_hard_coded_milestones(tmp_path, backup_root):
    pb = _load("prune_backups")
    ref = backup_root / "reference"
    ref.mkdir()
    for n in pb.CODEX_KEEP:
        _touch(ref, n)
    _touch(ref, "codex_pre_x_20261001_100000.db")
    _touch(ref, "codex_pre_x_20261002_100000.db")
    _, keep, move = pb.plan(str(ref))
    assert pb.CODEX_KEEP <= keep
    assert move == ["codex_pre_x_20261001_100000.db"]


# ---------------- reset_database ----------------

@pytest.fixture(scope="module")
def rdb():
    return _load("reset_database")


def test_reset_database_refuses_an_existing_out_and_the_data_folder(tmp_path, rdb):
    import paths
    existing = tmp_path / "there.db"
    existing.write_bytes(b"keep me")
    assert "already exists" in rdb.refusal_reason(existing)
    assert existing.read_bytes() == b"keep me"
    assert "data folder" in rdb.refusal_reason(Path(paths.DATA_DIR) / "new_one.db")
    assert "data folder" in rdb.refusal_reason(Path(paths.DATA_DIR) / "sub" / "x" / "new.db")
    assert rdb.refusal_reason(Path(paths.OBSERVATUM_DB))
    assert rdb.refusal_reason(tmp_path / "fresh" / "ok.db") == ""


def test_reset_database_main_refuses_without_touching_anything(tmp_path, rdb, monkeypatch):
    existing = tmp_path / "there.db"
    existing.write_bytes(b"keep me")
    monkeypatch.setattr(sys, "argv", ["reset_database.py", "--out", str(existing)])
    with pytest.raises(SystemExit) as e:
        rdb.main()
    assert e.value.code == 1
    assert existing.read_bytes() == b"keep me"
    assert os.listdir(tmp_path) == ["there.db"]


def test_reset_database_builds_a_current_empty_database(tmp_path, rdb):
    out = tmp_path / "new" / "observatum.db"
    assert rdb.build_new_database(out) is True
    assert sorted(os.listdir(out.parent)) == ["observatum.db"]       # no gamification.db
    c = sqlite3.connect(out)
    tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"observations", "specimens", "recording_scheme", "entry_staging", "photo_links",
            "staging_specimens", "family_notes", "species_aliases", "settings"} <= tables
    cols = lambda t: {r[1] for r in c.execute(f"PRAGMA table_info({t})")}
    assert {"irecord_exported_on", "hidden_at", "local_edited_at", "subfamily"} <= cols("observations")
    assert "duplicate_of" in cols("recording_scheme")
    assert {"check_flag", "check_note"} <= cols("entry_staging")
    assert "staging_id" in cols("photo_links")
    assert "site_name_local" in cols("specimens")
    assert c.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 0
    assert c.execute("SELECT COUNT(*) FROM settings").fetchone()[0] == len(rdb.DEFAULT_SETTINGS)
    c.close()


def test_check_fresh_schema_finds_a_difference_and_ignores_column_order(tmp_path, rdb):
    cfs = _load("check_fresh_schema")
    a, b = tmp_path / "a.db", tmp_path / "b.db"
    rdb.build_new_database(a)
    rdb.build_new_database(b)
    ca, cb = sqlite3.connect(a), sqlite3.connect(b)
    assert cfs.differences(ca, cb) == []
    cb.execute("ALTER TABLE specimens ADD COLUMN extra_col TEXT")
    cb.execute("CREATE INDEX idx_extra ON specimens(extra_col)")
    diffs = cfs.differences(ca, cb)
    assert any("specimens.extra_col" in d for d in diffs)
    assert any("idx_extra" in d for d in diffs)
    ca.close()
    cb.close()


# ---------------- seed_codex ----------------

def _seed_db(path):
    c = sqlite3.connect(path)
    c.executescript("""
        CREATE TABLE sqs_scores (tvk TEXT PRIMARY KEY, sqs INTEGER, source TEXT);
        CREATE TABLE status_summary (tvk TEXT, status_track TEXT, status_value TEXT,
            status_detail TEXT, origin TEXT);
        CREATE TABLE designations (tvk TEXT, category TEXT);
        CREATE TABLE manual_entries (id INTEGER);
        CREATE TABLE species_profiles (id INTEGER);
        INSERT INTO sqs_scores VALUES ('A', 8, 'pantheon'), ('B', 4, 'derived');
    """)
    c.commit()
    c.close()


def test_seed_codex_dry_run_writes_nothing_and_apply_backs_up_first(tmp_path, backup_root,
                                                                    monkeypatch, capsys):
    sc = _load("seed_codex")
    db = tmp_path / "codex.db"
    _seed_db(db)
    monkeypatch.setattr(sc, "CODEX_PATH", str(db))
    count = lambda: sqlite3.connect(db).execute(
        "SELECT COUNT(*) FROM sqs_scores WHERE source='derived'").fetchone()[0]

    monkeypatch.setattr(sys, "argv", ["seed_codex.py"])
    sc.main()
    out = capsys.readouterr().out
    assert count() == 1 and "Nothing has been changed" in out
    assert not (backup_root / "kept").exists()

    monkeypatch.setattr(sys, "argv", ["seed_codex.py", "--apply"])
    sc.main()
    assert count() == 0
    assert len(list((backup_root / "kept").glob("codex_pre-seed-codex_*.db"))) == 1


def test_swap_puts_the_old_file_back_when_the_new_one_cannot_go_in(tmp_path, backup_root, bcd,
                                                                    monkeypatch):
    """Review 24 Oct: a failed final replace must never leave codex.db missing."""
    codex, new = tmp_path / "codex.db", tmp_path / "codex_new.db"
    _kept_db(codex, manual=5)
    _kept_db(new, manual=1)
    old_bytes = codex.read_bytes()

    def locked(*_a, **_k):
        raise PermissionError("in use")
    monkeypatch.setattr(bcd.os, "replace", locked)
    with pytest.raises(bcd.SwapError):
        bcd.swap_in(str(new), str(codex))
    assert codex.read_bytes() == old_bytes          # the old file is back
    assert new.exists()                             # the new build is left to inspect


def test_build_refuses_when_codex_db_is_missing(tmp_path, monkeypatch, bcd, capsys):
    monkeypatch.setattr(bcd, "CODEX_PATH", str(tmp_path / "codex.db"))
    monkeypatch.setattr(bcd.sys, "argv", ["build_codex_db.py"])
    monkeypatch.setattr(bcd, "_tvk_translator", lambda: ({}, set()))
    with pytest.raises(SystemExit) as e:
        bcd.build_codex()
    assert e.value.code == 1
    assert "--fresh" in capsys.readouterr().out
    assert not (tmp_path / "codex.db").exists()
