"""Round 16 C3: DatabaseManager keeps one read connection per thread; never stale."""
import os
import sqlite3
import sys
import threading

import pytest

from Observatum.src.models.database import DatabaseManager


def _db(path, rows=("a",)):
    c = sqlite3.connect(path)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("CREATE TABLE t (name TEXT)")
    c.executemany("INSERT INTO t VALUES (?)", [(r,) for r in rows])
    c.commit()
    c.close()
    return str(path)


def _dm(tmp_path, **kw):
    dm = DatabaseManager()
    dm.set_main_path(_db(tmp_path / "main.db", **kw))
    return dm


def test_reads_reuse_one_connection_and_see_later_writes(tmp_path, monkeypatch):
    dm = _dm(tmp_path)
    opened = []
    real = DatabaseManager._open
    monkeypatch.setattr(DatabaseManager, "_open", staticmethod(
        lambda *a, **k: (opened.append(a) if k.get("check_same_thread") is False else None,
                         real(*a, **k))[1]))
    for _ in range(5):
        assert [r["name"] for r in dm.execute_main("SELECT name FROM t")] == ["a"]
    assert len(opened) == 1
    dm.execute_main_write("INSERT INTO t VALUES ('b')")           # own write connection
    assert len(dm.execute_main("SELECT name FROM t")) == 2          # no stale snapshot
    other = sqlite3.connect(str(dm.main_db_path))
    other.execute("INSERT INTO t VALUES ('c')")
    other.commit()
    other.close()
    assert len(dm.execute_main("SELECT name FROM t")) == 3
    assert len(opened) == 1


def test_write_sent_through_read_call_is_not_left_open(tmp_path):
    dm = _dm(tmp_path)
    dm.execute_main("INSERT INTO t VALUES ('x')")                   # never committed
    assert len(dm.execute_main("SELECT name FROM t")) == 1
    entry = dm._local.entries["main"]
    assert not entry.conn.in_transaction


def test_wal_pragma_runs_once_not_per_query(tmp_path, monkeypatch):
    dm = _dm(tmp_path)
    seen = []
    real = sqlite3.connect

    class Spy:
        def __init__(self, c):
            self._c = c

        def execute(self, sql, *a):
            seen.append(sql)
            return self._c.execute(sql, *a)

        def __getattr__(self, n):
            return getattr(self._c, n)

        def __setattr__(self, n, v):
            if n == "_c":
                object.__setattr__(self, n, v)
            else:
                setattr(self._c, n, v)
    monkeypatch.setattr(sqlite3, "connect", lambda *a, **k: Spy(real(*a, **k)))
    for _ in range(4):
        dm.execute_main("SELECT 1")
    assert sum("journal_mode" in s for s in seen) == 1


def _replace_main(dm, tmp_path, rows):
    fresh = _db(tmp_path / "fresh.db", rows=rows)
    for suffix in ("-wal", "-shm"):
        if os.path.exists(str(dm.main_db_path) + suffix):
            os.replace(str(dm.main_db_path) + suffix, str(tmp_path / ("old" + suffix)))
    os.replace(fresh, dm.main_db_path)


def test_path_change_never_uses_stale_connection(tmp_path):
    dm = _dm(tmp_path)
    assert len(dm.execute_main("SELECT * FROM t")) == 1
    dm.set_main_path(_db(tmp_path / "second.db", rows=("p", "q")))   # path swapped
    assert len(dm.execute_main("SELECT * FROM t")) == 2
    # attribute swap (as the test fixtures do) without going through set_main_path
    dm._main_db_path = tmp_path / "main.db"
    assert len(dm.execute_main("SELECT * FROM t")) == 1


def test_replacing_the_file_after_close_connections_reopens(tmp_path):
    """The rule: any in-process replace of a database calls close_connections() first."""
    dm = _dm(tmp_path)
    assert len(dm.execute_main("SELECT * FROM t")) == 1
    dm.close_connections()
    _replace_main(dm, tmp_path, ("1", "2", "3"))
    assert len(dm.execute_main("SELECT * FROM t")) == 3


@pytest.mark.skipif(sys.platform == "win32", reason="Windows refuses to replace an open database")
def test_replacing_the_file_under_an_open_connection_is_noticed(tmp_path):
    dm = _dm(tmp_path)
    assert len(dm.execute_main("SELECT * FROM t")) == 1
    _replace_main(dm, tmp_path, ("1", "2", "3"))
    assert len(dm.execute_main("SELECT * FROM t")) == 3


def test_threads_have_their_own_connection_and_close_connections_works(tmp_path):
    dm = _dm(tmp_path)
    dm.execute_main("SELECT 1")
    box = {}

    def work():
        box["rows"] = len(dm.execute_main("SELECT * FROM t"))
        box["conn"] = dm._local.entries["main"].conn
    th = threading.Thread(target=work)
    th.start()
    th.join()
    assert box["rows"] == 1 and box["conn"] is not dm._local.entries["main"].conn
    dm.close_connections()
    assert dm._local.entries["main"].conn is None
    assert len(dm.execute_main("SELECT * FROM t")) == 1             # reopens cleanly


def test_uksi_reads_are_pooled_read_only(tmp_path):
    dm = DatabaseManager()
    dm.set_uksi_path(_db(tmp_path / "uksi.db"))
    assert dm.execute_uksi("SELECT name FROM t")[0]["name"] == "a"
    c = dm._local.entries["uksi"].conn
    dm.execute_uksi("SELECT 1")
    assert dm._local.entries["uksi"].conn is c
