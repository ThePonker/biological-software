"""Munia: Complete counts with Accepted (MUN-1); deadlines hold any date and a
re-save never erases one (MUN-2). On an in-memory database."""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def conn():
    from Munia import munia_data as db
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    db.ensure_schema(c)
    return c


def _project(conn, name, status, value, year=2026, field=0.0, micro=0.0, report=0.0):
    from Munia import munia_data as db
    pid = db.add_project(conn, {"start_year": year, "end_year": year, "project_name": name,
                                "status": status, "quote_value": value})
    db.set_project_field_months(conn, pid, year, [{"month": 5, "field_days": field}])
    db.set_project_annual_days(conn, pid, year, {"micro_days": micro, "report_days": report})
    return pid


def test_complete_counts_with_accepted(conn):
    from Munia import munia_data as db
    _project(conn, "A", "accepted", 1000, field=3, micro=1, report=2)
    _project(conn, "C", "complete", 500, field=2, micro=4, report=1)
    _project(conn, "Q", "quoted", 200, field=5)
    _project(conn, "D", "declined", 300)
    s = db.summarise_pipeline(db.get_projects_for_year(conn, 2026))
    assert s["confirmed"] == 1500                      # was 1000: complete dropped out
    assert s["counts"]["complete"] == 1 and s["counts"]["quoted"] == 1   # not counted as quoted
    assert s["lost"] == 300 and s["total"] == 4
    assert sum(s["counts"].values()) == s["total"]
    assert db.get_accepted_field_total(conn, 2026) == 5
    assert db.get_annual_totals(conn, 2026, db.COMMITTED_STATUSES) == {"micro": 5, "report": 3}
    assert db.get_field_totals_by_month(conn, 2026, db.COMMITTED_STATUSES)[5] == 5


def test_summary_card_shows_complete_row(qapp, conn, monkeypatch):
    from Munia import munia_data as db
    from Munia import munia_ui
    _project(conn, "A", "accepted", 1000, field=3)
    _project(conn, "C", "complete", 500, field=2)
    monkeypatch.setattr(db, "get_connection", lambda: conn)
    monkeypatch.setattr(db, "current_biz_year", lambda: 2026)
    monkeypatch.setattr(munia_ui.MuniaWindow, "closeEvent", lambda self, e: None)
    w = munia_ui.MuniaWindow()
    assert w.won_lbl.text() == "£1,500"
    assert w.r_complete["count"].text() == "1"
    assert "Complete" in w.r_complete["label"].text() and "500" in w.r_complete["label"].text()
    assert w.r_quoted["count"].text() == "0"
    assert w.d_field.text() == "5"


def test_deadline_edit_any_date_and_not_set(qapp):
    from Munia.deadline_edit import DeadlineEdit
    d = DeadlineEdit()
    assert d.value() == "" and not d.is_set()
    d.set_value("2019-03-15")                          # well before the current season
    assert d.value() == "2019-03-15"
    d.set_value("")
    assert d.value() == ""
    d.set_value("end of May")                          # not a date: kept, not erased
    assert d.value() == "end of May"
    from PySide6.QtCore import QDate
    d.date_edit.setDate(QDate(2027, 1, 31))            # the user picks a date
    assert d.value() == "2027-01-31"
    d.clear()
    assert d.value() == ""


def test_resave_keeps_early_deadline(qapp, conn):
    """A deadline before 1 Jan of the season shown used to come back as 'Not set'
    and be saved as ''."""
    from Munia import munia_data as db
    from Munia.project_form import ProjectForm
    pid = _project(conn, "Old job", "accepted", 100, year=2026)
    db.set_project_annual_days(conn, pid, 2026, {"micro_days": 1, "report_days": 1,
                                                  "id_deadline": "2025-11-30",
                                                  "report_deadline": "2026-02-01",
                                                  "notes": "n"})
    form = ProjectForm(conn)
    form.set_year(2026)
    project = [p for p in db.get_projects_for_year(conn, 2026) if p["id"] == pid][0]
    form.load_project(project)
    assert form.id_deadline.value() == "2025-11-30"
    form._on_save()
    ad = db.get_project_annual_days(conn, pid, 2026)
    assert ad["id_deadline"] == "2025-11-30"
    assert ad["report_deadline"] == "2026-02-01"
