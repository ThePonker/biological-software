"""R4B: deleting observations that specimens are linked to; bulk edits and deletes in batches."""
import sqlite3

import pytest

from shared import observation_delete as od
from src.models.database import DatabaseManager


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "o.db"
    c = sqlite3.connect(p)
    c.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, species_name TEXT, record_type TEXT)")
    c.execute("CREATE TABLE specimens (id INTEGER PRIMARY KEY, specimen_code TEXT, species_name TEXT, "
              "observation_id INTEGER REFERENCES observations(id))")
    c.executemany("INSERT INTO observations (id, species_name) VALUES (?, 'Amara aenea')",
                  [(i,) for i in range(1, 2301)])
    c.executemany("INSERT INTO specimens VALUES (?,?,?,?)",
                  [(1, "S-1", "Amara aenea", 5), (2, "S-2", "Amara aenea", 5),
                   (3, "S-3", "Amara aenea", 2000), (4, "S-4", "Amara aenea", None)])
    c.commit()
    c.close()
    m = DatabaseManager()
    m.set_main_path(str(p))
    return m, p


def _n(p, table):
    return sqlite3.connect(p).execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_linked_specimens_are_found(db):
    m, p = db
    c = sqlite3.connect(p)
    links = od.linked_specimens(c, [5, 2000, 7])
    assert [(k["id"], k["observation_id"]) for k in links] == [(1, 5), (2, 5), (3, 2000)]
    assert "S-1" in od.describe_links(links) and "observation 5" in od.describe_links(links)
    assert od.linked_specimens(c, [7]) == []


def test_delete_without_unlink_refuses_and_changes_nothing(db):
    m, p = db
    with pytest.raises(od.LinkedSpecimensError) as e:
        od.delete_observations(m, [5, 6])
    assert len(e.value.links) == 2
    assert _n(p, "observations") == 2300


def test_unlink_and_delete_together(db):
    m, p = db
    assert od.delete_observations(m, [5, 6], unlink=True) == 2
    c = sqlite3.connect(p)
    assert c.execute("SELECT COUNT(*) FROM observations WHERE id IN (5,6)").fetchone()[0] == 0
    assert c.execute("SELECT observation_id FROM specimens WHERE id IN (1,2)").fetchall() == [(None,), (None,)]
    assert c.execute("SELECT observation_id FROM specimens WHERE id=3").fetchone()[0] == 2000   # untouched


def test_failure_rolls_back_the_unlink(db):
    m, p = db
    c = sqlite3.connect(p)
    c.execute("CREATE TRIGGER nodel BEFORE DELETE ON observations WHEN OLD.id = 6 "
              "BEGIN SELECT RAISE(ABORT, 'no'); END")
    c.commit()
    c.close()
    with pytest.raises(sqlite3.Error):
        od.delete_observations(m, [5, 6], unlink=True)
    c = sqlite3.connect(p)
    assert c.execute("SELECT observation_id FROM specimens WHERE id=1").fetchone()[0] == 5   # still linked
    assert c.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 2300


def test_long_lists_go_in_batches_of_900(db):
    m, p = db
    assert [len(c) for c in od._chunks(range(2000))] == [900, 900, 200]
    ids = list(range(10, 2300))               # 2,290 ids, three batches; one holds a linked record
    assert od.delete_observations(m, ids, unlink=True) == 2290
    assert _n(p, "observations") == 10
    assert sqlite3.connect(p).execute("SELECT observation_id FROM specimens WHERE id=3").fetchone()[0] is None


def test_update_in_chunks(db):
    m, p = db
    n = od.update_in_chunks(m, "record_type = ?", ["Commercial"], list(range(1, 2301)))
    assert n == 2300
    assert sqlite3.connect(p).execute(
        "SELECT COUNT(*) FROM observations WHERE record_type='Commercial'").fetchone()[0] == 2300


def test_the_ask_reports_links_and_none_cancels(db, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from src.views.components import specimen_unlink_ask as ask
    m, p = db
    assert ask.ask(None, str(p), [7], "t") is False                       # nothing linked: no dialog
    seen = {}

    class Box:
        def __init__(self, parent=None):
            self.go = None

        def setIcon(self, *a): pass
        def setWindowTitle(self, *a): pass
        def setText(self, t): seen["text"] = t
        def addButton(self, b, role=None):
            if isinstance(b, str):
                self.go = object()
                return self.go
        def setDefaultButton(self, *a): pass
        def exec(self): pass
        def clickedButton(self): return self.go if seen.get("yes") else None

    monkeypatch.setattr(ask, "QMessageBox", Box)
    Box.Icon, Box.ButtonRole, Box.StandardButton = QMessageBox.Icon, QMessageBox.ButtonRole, QMessageBox.StandardButton
    assert ask.ask(None, str(p), [5], "t") is None and "S-1" in seen["text"]    # cancelled
    seen["yes"] = True
    assert ask.ask(None, str(p), [5], "t") is True
