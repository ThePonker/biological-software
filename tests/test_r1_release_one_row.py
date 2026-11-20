"""Round 1, item 2: Release touches one row (project, client, year), embargoed records only."""
import sqlite3
from datetime import date
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QPushButton
from PySide6.QtWidgets import QMessageBox

from src.views.stats import commercial_reports_dashboard as crd
from tests.test_dataentry_r3 import qapp  # noqa: F401


@pytest.fixture
def world(qapp, tmp_path, monkeypatch):  # noqa: F811
    db = tmp_path / "obs.db"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE observations (record_type TEXT, project_name TEXT, client TEXT, "
              "embargo_status TEXT, embargo_until TEXT, species_tvk TEXT, date TEXT, site_name TEXT)")
    rows = [("Commercial", "Kent", "NNR", "Active", "2099-01-03", f"t{i}", "2024-05-01") for i in range(5)]
    rows += [("Commercial", "Kent", "NNR", "Expired", "2020-01-03", "e1", "2024-05-02")]
    rows += [("Commercial", "Kent", "NNR", None, None, f"u{i}", "2024-04-16") for i in range(2)]
    rows += [("Commercial", "Kent", "NNR", "", None, "u9", "2024-04-17")]
    rows += [("Commercial", "Kent", "NNR", "Active", "2099-01-03", "k25", "2025-05-01")]
    rows += [("Commercial", "Kent", "Other", "Active", "2099-01-03", "o1", "2024-05-01")]
    rows += [("Commercial", "Kent", "NNR", "Released", None, "r1", "2024-05-03")]
    rows += [("Surveyor", "Kent", "NNR", "Active", "2099-01-03", "s1", "2024-05-01")]
    c.executemany("INSERT INTO observations VALUES (?,?,?,?,?,?,?,NULL)", rows)
    c.commit()
    c.close()
    monkeypatch.setattr(crd, "get_database", lambda: SimpleNamespace(get_main_path=lambda: str(db)))
    monkeypatch.setattr(crd, "species_count_sql", lambda path, prefix="": "COUNT(DISTINCT species_tvk)")
    w = crd.CommercialReportsDashboard()
    w.refresh()
    return w, db


def _status(db):
    c = sqlite3.connect(db)
    out = c.execute("SELECT project_name, client, substr(date,1,4), COALESCE(embargo_status,'<null>'), "
                    "record_type, COUNT(*) FROM observations GROUP BY 1,2,3,4,5").fetchall()
    c.close()
    return {(a, b, y, s, t): n for a, b, y, s, t, n in out}


def test_count_and_release_only_the_row_and_embargoed(world):
    w, db = world
    c = sqlite3.connect(db)
    assert crd.count_embargoed(c, "Kent", "NNR", "2024") == 6     # 5 Active + 1 Expired
    assert crd.release_embargoed(c, "Kent", "NNR", "2024") == 6
    c.commit()
    c.close()
    st = _status(db)
    assert st[("Kent", "NNR", "2024", "Released", "Commercial")] == 7   # 6 + the one already released
    assert st[("Kent", "NNR", "2024", "<null>", "Commercial")] == 2
    assert st[("Kent", "NNR", "2024", "", "Commercial")] == 1
    assert st[("Kent", "NNR", "2025", "Active", "Commercial")] == 1
    assert st[("Kent", "Other", "2024", "Active", "Commercial")] == 1
    assert st[("Kent", "NNR", "2024", "Active", "Surveyor")] == 1


def test_button_flow_asks_with_count_and_reports_real_count(world, monkeypatch):
    w, db = world
    asked, told = [], []
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: asked.append(a[2]) or QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: told.append(a[2]))
    import shared.backup_service as bs
    monkeypatch.setattr(bs, "backup_main_only", lambda label: True)
    w._release_project("Kent", "NNR", "2024")
    assert "Mark the 6 embargoed records of 'Kent' (NNR, 2024) as Released" in asked[0]
    assert "cleared for upload to iRecord" in asked[0]
    # 5 of the 6 are Active with an embargo ending 2099-01-03; the Expired one is not live
    assert "(5 of them are still under embargo until 03/01/2099.)" in asked[0]
    assert told[-1].startswith("6 records")
    # nothing left: says so, does not ask again
    asked.clear()
    w._release_project("Kent", "NNR", "2024")
    assert not asked and "no embargoed records" in told[-1]


def test_no_year_is_refused(world, monkeypatch):
    w, db = world
    warned = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warned.append(a[2]))
    before = _status(db)
    w._release_project("Kent", "NNR", "")
    assert warned and "no survey year" in warned[0]
    assert _status(db) == before


def test_backup_failure_changes_nothing(world, monkeypatch):
    w, db = world
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    import shared.backup_service as bs
    monkeypatch.setattr(bs, "backup_main_only", lambda label: False)
    before = _status(db)
    w._release_project("Kent", "NNR", "2024")
    assert _status(db) == before


def test_detail_panel_uses_local_date_param(world, monkeypatch):
    w, db = world
    class D(date):
        @classmethod
        def today(cls):
            return date(2099, 6, 1)      # after the 2099-01-03 embargo end
    monkeypatch.setattr(crd, "date", D)
    w._show_project("Kent", "NNR")
    assert w._selected_project[2] == ""   # all embargoes have ended by the (local) date passed in


@pytest.fixture
def null_world(qapp, tmp_path, monkeypatch):  # noqa: F811
    db = tmp_path / "obs.db"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE observations (record_type TEXT, project_name TEXT, client TEXT, "
              "embargo_status TEXT, embargo_until TEXT, species_tvk TEXT, date TEXT, site_name TEXT)")
    rows = [("Commercial", "NullClient", None, "Active", "2020-01-01", "a", "2024-05-01"),
            ("Commercial", "NullClient", "", "Active", "2020-01-01", "b", "2024-05-01"),
            ("Commercial", None, "Acme", "Active", "2020-01-01", "c", "2024-05-01"),
            ("Commercial", None, "Acme", "Active", "2020-01-01", "d", "2024-05-02"),
            ("Commercial", "Other", "Acme", "Active", "2020-01-01", "e", "2024-05-01")]
    c.executemany("INSERT INTO observations VALUES (?,?,?,?,?,?,?,NULL)", rows)
    c.commit()
    c.close()
    monkeypatch.setattr(crd, "get_database", lambda: SimpleNamespace(get_main_path=lambda: str(db)))
    monkeypatch.setattr(crd, "species_count_sql", lambda path, prefix="": "COUNT(DISTINCT species_tvk)")
    w = crd.CommercialReportsDashboard()
    w.refresh()
    import shared.backup_service as bs
    monkeypatch.setattr(bs, "backup_main_only", lambda label: True)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    return w, db


def _click(w, label, client_text):
    t = w._table
    for r in range(t.rowCount()):
        if t.item(r, 0).text() == label and t.item(r, 1).text() == client_text:
            t.cellWidget(r, 6).findChild(QPushButton).click()
            return
    raise AssertionError(f"no row {label!r}/{client_text!r}")


def _released(db, where):
    c = sqlite3.connect(db)
    n = c.execute(f"SELECT COUNT(*) FROM observations WHERE embargo_status='Released' AND {where}").fetchone()[0]
    c.close()
    return n


def test_null_client_row_can_be_released_through_the_button(null_world):
    w, db = null_world
    _click(w, "NullClient", "")          # two rows show this text: the NULL one and the '' one
    _click(w, "NullClient", "")
    assert _released(db, "project_name='NullClient'") == 2


def test_null_client_release_touches_only_the_null_row(null_world):
    w, db = null_world
    t = w._table
    rows = [r for r in range(t.rowCount()) if t.item(r, 0).text() == "NullClient"]
    assert len(rows) == 2
    from PySide6.QtCore import Qt
    null_row = [r for r in rows if t.item(r, 0).data(Qt.ItemDataRole.UserRole)[1] is None][0]
    t.cellWidget(null_row, 6).findChild(QPushButton).click()
    assert _released(db, "project_name='NullClient' AND client IS NULL") == 1
    assert _released(db, "project_name='NullClient' AND client = ''") == 0


def test_null_project_row_can_be_released_through_the_button(null_world):
    w, db = null_world
    _click(w, "(no project)", "Acme")
    assert _released(db, "project_name IS NULL") == 2
    assert _released(db, "project_name = 'Other'") == 0


def test_scope_uses_is_null():
    where, params = crd.release_scope(None, None, "2024")
    assert "project_name IS NULL" in where and "client IS NULL" in where and params == ["2024"]


def test_release_button_keeps_its_size_and_project_column_stretches():
    """The Action column is not the stretched one, so Release stays a button, not a full-width bar."""
    from PySide6.QtWidgets import QHeaderView
    import inspect
    from src.views.stats import commercial_reports_dashboard as m
    src = inspect.getsource(m)
    assert "setStretchLastSection(False)" in src
    assert "setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)" in src
    holder = m._centred(QPushButton("Release"))
    assert holder.findChild(QPushButton) is not None
    assert QHeaderView  # imported for clarity
