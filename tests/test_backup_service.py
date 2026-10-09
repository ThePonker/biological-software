"""shared/backup_service: verify before rotate (INF2), kept copies (INF3 / IMP-17).

Everything runs in a temporary BACKUP_ROOT against small throwaway databases.
"""
import os
import sqlite3

import pytest

import paths
from shared import backup_service as bs


def _make_db(path, value):
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")            # as observatum.db is
    conn.execute("CREATE TABLE t (v TEXT)")
    conn.execute("INSERT INTO t VALUES (?)", (value,))
    conn.commit()
    conn.close()


def _value(path):
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return conn.execute("SELECT v FROM t").fetchone()[0]
    finally:
        conn.close()


@pytest.fixture
def env(tmp_path, monkeypatch):
    root = tmp_path / "backups"
    monkeypatch.setattr(bs, "BACKUP_ROOT", str(root))
    src = tmp_path / "observatum.db"
    _make_db(str(src), "first")
    monkeypatch.setattr(paths, "OBSERVATUM_DB", src)
    return root, src


def _set(src, value):
    conn = sqlite3.connect(str(src))
    conn.execute("UPDATE t SET v = ?", (value,))
    conn.commit()
    conn.close()


def test_verify_copy(tmp_path):
    good = tmp_path / "g.db"
    _make_db(str(good), "x")
    assert bs.verify_copy(str(good)) is None
    empty = tmp_path / "e.db"
    empty.write_bytes(b"")
    assert "empty" in bs.verify_copy(str(empty))
    junk = tmp_path / "j.db"
    junk.write_bytes(b"this is not a database at all" * 100)
    assert bs.verify_copy(str(junk)) is not None
    assert bs.verify_copy(str(tmp_path / "missing.db")) == "missing"


def test_rotation_keeps_two_generations(env):
    root, src = env
    assert bs.backup_databases(("OBSERVATUM_DB",), "on close")
    _set(src, "second")
    assert bs.backup_databases(("OBSERVATUM_DB",), "on close")
    assert _value(root / "current" / "observatum.db") == "second"
    assert _value(root / "previous" / "observatum.db") == "first"
    assert not (root / "kept").exists()          # close backups are not kept copies


def test_inf2_failed_backup_never_loses_last_good_copy(env, monkeypatch):
    """INF2 reproduced: a failed copy, then a good one, used to rotate a 0-byte file
    over the last good 'previous'."""
    root, src = env
    assert bs.backup_databases(("OBSERVATUM_DB",), "on close")      # current = first
    _set(src, "second")
    assert bs.backup_databases(("OBSERVATUM_DB",), "on close")      # previous = first

    # The copy fails part-way (as the old code did, leaving an empty file)
    real_copy = bs.copy_database

    def failing_copy(s, d):
        open(d, "wb").close()
        return False
    monkeypatch.setattr(bs, "copy_database", failing_copy)
    assert not bs.backup_databases(("OBSERVATUM_DB",), "on close")
    assert _value(root / "current" / "observatum.db") == "second"   # untouched
    assert _value(root / "previous" / "observatum.db") == "first"   # untouched
    assert not [f for f in os.listdir(root / "current") if f.endswith(".partial")]

    # A copy that "succeeds" but is not a database is refused too
    def junk_copy(s, d):
        with open(d, "wb") as f:
            f.write(b"garbage" * 500)
        return True
    monkeypatch.setattr(bs, "copy_database", junk_copy)
    assert not bs.backup_databases(("OBSERVATUM_DB",), "on close")
    assert _value(root / "current" / "observatum.db") == "second"
    assert _value(root / "previous" / "observatum.db") == "first"

    # The next good backup rotates the good current over previous
    monkeypatch.setattr(bs, "copy_database", real_copy)
    _set(src, "third")
    assert bs.backup_databases(("OBSERVATUM_DB",), "on close")
    assert _value(root / "current" / "observatum.db") == "third"
    assert _value(root / "previous" / "observatum.db") == "second"
    # failed partials were moved aside, not deleted
    assert len(os.listdir(root / "_expired")) == 2


def test_bad_current_is_not_rotated_over_previous(env):
    root, src = env
    assert bs.backup_databases(("OBSERVATUM_DB",), "on close")
    _set(src, "second")
    assert bs.backup_databases(("OBSERVATUM_DB",), "on close")
    # A 0-byte current left by the old code
    (root / "current" / "observatum.db").write_bytes(b"")
    _set(src, "third")
    assert bs.backup_databases(("OBSERVATUM_DB",), "on close")
    assert _value(root / "current" / "observatum.db") == "third"
    assert _value(root / "previous" / "observatum.db") == "first"   # good previous kept
    assert any("bad-current" in f for f in os.listdir(root / "_expired"))


def test_backup_main_only_writes_named_kept_copy(env):
    root, src = env
    assert bs.backup_main_only("pre-import")
    kept = os.listdir(root / "kept")
    assert len(kept) == 1                        # and no -wal / -shm / .partial left over
    assert not [f for f in os.listdir(root / "current") if f != "observatum.db"]
    assert not [f for f in kept if not f.endswith(".db")]
    assert bs._kept_pattern("observatum.db", "pre-import").match(kept[0])
    assert _value(root / "kept" / kept[0]) == "first"
    # the rotation still happens too
    assert _value(root / "current" / "observatum.db") == "first"


def test_labelled_pre_backup_keeps_copy(env):
    root, src = env
    assert bs.backup_databases(("OBSERVATUM_DB",), "pre-commit")
    assert len(os.listdir(root / "kept")) == 1


def test_kept_copies_pruned_by_moving_not_deleting(env, monkeypatch):
    root, src = env
    import itertools
    counter = itertools.count()
    monkeypatch.setattr(bs, "_stamp", lambda: f"20261009_{next(counter):06d}")
    n = bs.KEEP_PER_LABEL + 3
    made = [os.path.basename(bs.write_kept_copy(str(src), "pre-delete")) for _ in range(n)]
    kept_dir = root / "kept"
    live = sorted(f for f in os.listdir(kept_dir) if f.endswith(".db"))
    assert live == sorted(made)[3:]                                   # newest KEEP_PER_LABEL stay
    expired = sorted(os.listdir(kept_dir / "_expired"))
    assert expired == sorted(made)[:3]                                # oldest 3 moved, not deleted


def test_prune_is_per_label(env, monkeypatch):
    root, src = env
    for i in range(3):
        bs.write_kept_copy(str(src), "pre-import")
    bs.write_kept_copy(str(src), "pre-import-notes")
    assert bs.prune_kept("observatum.db", "pre-import", keep=1) == 2
    live = [f for f in os.listdir(root / "kept") if f.endswith(".db")]
    assert sum("pre-import-notes" in f for f in live) == 1
    assert len(live) == 2


def test_kept_name_sanitises_label():
    assert bs.kept_name("observatum.db", "on close / x", "20261009_101010") == \
        "observatum_on-close-x_20261009_101010.db"
