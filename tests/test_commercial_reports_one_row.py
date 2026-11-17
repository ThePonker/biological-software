"""Commercial Reports: one row per project, other embargo settings noted (17 Nov 2026)."""
import sqlite3
from types import SimpleNamespace

import pytest

from src.views.stats import commercial_reports_dashboard as crd
from tests.test_dataentry_r3 import qapp  # noqa: F401


@pytest.fixture
def dash(qapp, tmp_path, monkeypatch):  # noqa: F811
    db = tmp_path / "obs.db"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE observations (record_type TEXT, project_name TEXT, client TEXT, "
              "embargo_status TEXT, embargo_until TEXT, species_tvk TEXT, date TEXT)")
    rows = [("Commercial", "Kent Deadwood", "NNR", "Active", "2099-01-03", f"t{i}", "2024-05-01") for i in range(5)]
    rows += [("Commercial", "Kent Deadwood", "NNR", None, None, f"u{i}", "2024-04-16") for i in range(2)]
    rows += [("Commercial", "Coedely Park", "Richard Wilson", None, None, "c1", "2026-05-01")]
    rows += [("Commercial", "Graven Hill", "Watermans", None, None, f"g{i}", "2023-06-01") for i in range(3)]
    rows += [("Commercial", "Graven Hill", "Watermans", "Active", "2099-01-03", f"h{i}", "2025-06-01") for i in range(4)]
    c.executemany("INSERT INTO observations VALUES (?,?,?,?,?,?,?)", rows)
    c.commit(); c.close()
    monkeypatch.setattr(crd, "get_database", lambda: SimpleNamespace(get_main_path=lambda: str(db)))
    monkeypatch.setattr(crd, "species_count_sql", lambda path, prefix="": "COUNT(DISTINCT species_tvk)")
    w = crd.CommercialReportsDashboard()
    w.refresh()
    return w


def _rows(w):
    t = w._table
    return [[t.item(r, c).text() for c in range(6)] for r in range(t.rowCount())]


def test_each_project_is_listed_once(dash):
    rows = _rows(dash)
    assert [r[0] for r in rows] == ["Graven Hill (2025)", "Kent Deadwood", "Coedely Park", "Graven Hill (2023)"]


def test_mixed_project_totals_and_note(dash):
    kent = _rows(dash)[1]
    assert kent[2] == "7" and kent[3] == "7"
    assert kent[4] == "Under Embargo (2 not embargoed)"
    assert kent[5] == "2099-01-03"


def test_project_without_embargo(dash):
    coedely = _rows(dash)[2]
    assert coedely[4] == "No Embargo" and coedely[2] == "1"


def test_job_surveyed_in_two_years_stays_two_rows(dash):
    rows = {r[0]: r for r in _rows(dash)}
    assert rows["Graven Hill (2025)"][2:5] == ["4", "4", "Under Embargo"]
    assert rows["Graven Hill (2023)"][2:5] == ["3", "3", "No Embargo"]
    # the stored project name, not the label, is what the row carries
    from PySide6.QtCore import Qt
    t = dash._table
    names = [t.item(r, 0).data(Qt.ItemDataRole.UserRole) for r in range(t.rowCount())]
    assert ("Graven Hill", "Watermans") in names
