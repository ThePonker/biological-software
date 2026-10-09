"""Contributed tab data access (backlog K1, 9 Oct 2026).

Runs src.repositories.contributed_repository against an in-memory table built with the
same columns as observatum.db's contributed_observations. No real database is opened.
"""
import sqlite3

import pytest

from src.repositories.contributed_repository import (
    COLUMNS, TEXT_COLUMNS, fetch_records, has_table, list_groups,
)

# Same columns, types and defaults as observatum.db (PRAGMA table_info, 9 Oct 2026).
SCHEMA = """
CREATE TABLE contributed_observations (
    id INTEGER PRIMARY KEY, species_name TEXT NOT NULL, species_tvk TEXT,
    common_name TEXT, order_name TEXT, family TEXT, taxon_rank TEXT,
    date TEXT NOT NULL, date_type TEXT DEFAULT 'D', grid_ref TEXT, grid_precision INTEGER,
    vice_county TEXT, vc_number INTEGER, site_name TEXT, sub_location TEXT,
    trap_number TEXT, visit_number TEXT, recorder TEXT, determiner TEXT, sex TEXT,
    stage TEXT, quantity INTEGER DEFAULT 1, method TEXT, comment TEXT,
    record_type TEXT DEFAULT 'Commercial', project_name TEXT, client TEXT,
    contributor TEXT NOT NULL, source_file TEXT, received_date TEXT, permission TEXT,
    import_batch TEXT, import_notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""

B1 = "Contributed Moore, J. 2026-10-02T16:20:45"
B2 = "Contributed Moore, J. 2026-10-09T11:12:28"
B3 = "Contributed Smith, A. 2026-10-05T09:00:00"
ROWS = [
    # species, common, date, site, project, contributor, file, received, batch, qty
    ("Agelastica alni", "Alder Leaf Beetle", "2026-05-05", "Wheels Park", "Birmingham - Wheels Park",
     "Moore, J.", "Birmingham_Wheels.xlsx", "2026-10-02", B1, 1),
    ("Carabus violaceus", "Violet Ground Beetle", "2026-06-01", "Wheels Park",
     "Birmingham - Wheels Park", "Moore, J.", "Birmingham_Wheels.xlsx", "2026-10-02", B1, 3),
    ("Agelastica alni", "Alder Leaf Beetle", "2026-07-10", "Slade Green Marsh", "Slade Green",
     "Moore, J.", "Dartford_Jon_corrected.xlsx", "2026-10-09", B2, 2),
    ("Rutpela maculata", "Black-and-yellow Longhorn", "2026-06-20", "Somewhere_100%", None,
     "Smith, A.", "smith.csv", "2026-10-05", B3, 1),
]


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.execute(SCHEMA)
    c.executemany(
        "INSERT INTO contributed_observations (species_name, common_name, date, site_name, "
        "project_name, contributor, source_file, received_date, import_batch, quantity) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", ROWS)
    yield c
    c.close()


def test_columns_exist_in_table(conn):
    have = {r[1] for r in conn.execute("PRAGMA table_info(contributed_observations)")}
    assert {k for k, _ in COLUMNS} <= have
    assert set(TEXT_COLUMNS) <= have


def test_has_table(conn):
    assert has_table(conn)
    assert not has_table(sqlite3.connect(":memory:"))


def test_list_groups(conn):
    groups = list_groups(conn)
    assert [(g["contributor"], g["project_name"], g["import_batch"], g["n"]) for g in groups] == [
        ("Moore, J.", "Birmingham - Wheels Park", B1, 2),
        ("Moore, J.", "Slade Green", B2, 1),
        ("Smith, A.", None, B3, 1),
    ]
    assert groups[0]["source_file"] == "Birmingham_Wheels.xlsx"
    assert groups[0]["received_date"] == "2026-10-02"


def test_fetch_all_sorted(conn):
    rows = fetch_records(conn)
    assert len(rows) == 4
    assert [r["species_name"] for r in rows] == [
        "Agelastica alni", "Agelastica alni", "Carabus violaceus", "Rutpela maculata"]
    assert rows[0]["date"] < rows[1]["date"]


def test_fetch_by_contributor_project_batch(conn):
    assert len(fetch_records(conn, contributor="Moore, J.")) == 3
    assert len(fetch_records(conn, contributor="Moore, J.", project="Slade Green")) == 1
    assert len(fetch_records(conn, contributor="Moore, J.", project="Birmingham - Wheels Park",
                             batch=B1)) == 2
    assert fetch_records(conn, contributor="Moore, J.", batch=B3) == []


def test_fetch_no_project_means_null(conn):
    rows = fetch_records(conn, project=None)
    assert [r["contributor"] for r in rows] == ["Smith, A."]


def test_free_text(conn):
    assert len(fetch_records(conn, text="alni")) == 2
    assert len(fetch_records(conn, text="  VIOLET ")) == 1           # common name, any case
    assert len(fetch_records(conn, text="dartford")) == 1            # source file
    assert len(fetch_records(conn, contributor="Moore, J.", text="wheels")) == 2
    assert len(fetch_records(conn, text="_100%")) == 1               # wildcards are literal
    assert fetch_records(conn, text="%") == fetch_records(conn, text="Somewhere_100%")


def test_read_only_open(tmp_path):
    from src.repositories.contributed_repository import open_ro
    path = tmp_path / "obs.db"
    w = sqlite3.connect(path)
    w.execute(SCHEMA)
    w.commit()
    w.close()
    c = open_ro(path)
    try:
        assert has_table(c)
        with pytest.raises(sqlite3.OperationalError):
            c.execute("INSERT INTO contributed_observations (species_name, date, contributor) "
                      "VALUES ('x', '2026-01-01', 'y')")
    finally:
        c.close()


def test_tab_offscreen(tmp_path, monkeypatch):
    """The tab builds offscreen, fills its tree and table, and filters (no real database)."""
    pytest.importorskip("PySide6")
    import importlib.util
    import sys
    import types
    from types import SimpleNamespace
    from PySide6.QtWidgets import QApplication, QWidget
    # src.views imports the main window, whose Mapping tab needs WebEngine; stub it
    # where it is not installed (the Contributed tab itself does not use it).
    for name, attr in (("QtWebEngineWidgets", "QWebEngineView"), ("QtWebChannel", "QWebChannel")):
        if importlib.util.find_spec(f"PySide6.{name}") is None:
            stub = types.ModuleType(f"PySide6.{name}")
            setattr(stub, attr, QWidget)
            monkeypatch.setitem(sys.modules, f"PySide6.{name}", stub)
    app = QApplication.instance() or QApplication([])
    path = tmp_path / "obs.db"
    w = sqlite3.connect(path)
    w.execute(SCHEMA)
    w.executemany(
        "INSERT INTO contributed_observations (species_name, common_name, date, site_name, "
        "project_name, contributor, source_file, received_date, import_batch, quantity) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", ROWS)
    w.commit()
    w.close()
    from src.views.contributed import contributed_tab as mod
    monkeypatch.setattr(mod, "get_database", lambda: SimpleNamespace(main_db_path=path))
    tab = mod.ContributedTab()
    tab.initialize()
    assert tab.model.rowCount() == 4
    assert tab.count_label.text().startswith("4 records")
    root = tab.tree.topLevelItem(0)
    assert root.text(1) == "4" and root.childCount() == 2          # Moore, Smith
    moore = root.child(0)
    assert moore.text(0) == "Moore, J." and moore.text(1) == "3"
    tab.tree.setCurrentItem(moore.child(1))                          # Slade Green project
    assert tab.model.rowCount() == 1
    tab.tree.setCurrentItem(root)
    tab.search_edit.setText("alni")
    assert tab.model.rowCount() == 2
    assert app is not None
