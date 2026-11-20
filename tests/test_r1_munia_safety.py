"""Round 1, item 3: Munia delete keeps a backup first and rolls back; per-year days save as one."""
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


def _project(conn, name="A", year=2026):
    from Munia import munia_data as db
    pid = db.add_project(conn, {"start_year": year, "end_year": year, "project_name": name,
                                "status": "accepted", "quote_value": 100})
    db.set_project_field_months(conn, pid, year, [{"month": 5, "field_days": 3}])
    db.set_project_annual_days(conn, pid, year, {"micro_days": 1, "report_days": 2})
    return pid


def _counts(conn):
    return tuple(conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                 for t in ("projects", "project_field_months", "project_annual_days"))


def test_delete_project_rolls_back_on_failure(conn):
    from Munia import munia_data as db
    pid = _project(conn)
    conn.commit()
    conn.execute("CREATE TRIGGER nodel BEFORE DELETE ON projects "
                 "BEGIN SELECT RAISE(ABORT, 'refused'); END")
    before = _counts(conn)
    with pytest.raises(sqlite3.Error):
        db.delete_project(conn, pid)
    assert _counts(conn) == before == (1, 1, 1)


def test_delete_project_works(conn):
    from Munia import munia_data as db
    pid = _project(conn)
    db.delete_project(conn, pid)
    assert _counts(conn) == (0, 0, 0)


@pytest.fixture
def win(qapp, conn, monkeypatch):
    from Munia import munia_data as db
    from Munia import munia_ui
    monkeypatch.setattr(db, "get_connection", lambda: conn)
    monkeypatch.setattr(db, "current_biz_year", lambda: 2026)
    monkeypatch.setattr(munia_ui.MuniaWindow, "closeEvent", lambda self, e: None)
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    warned = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warned.append(a[2]))
    return munia_ui.MuniaWindow(), warned


def test_delete_refused_when_backup_fails(win, conn, monkeypatch):
    w, warned = win
    pid = _project(conn)
    import shared.backup_service as bs
    monkeypatch.setattr(bs, "backup_file_written", lambda p, label: False)
    w._on_delete(pid)
    assert _counts(conn) == (1, 1, 1)
    assert warned and "backup failed" in warned[0]


def test_delete_takes_backup_first_then_deletes(win, conn, monkeypatch):
    w, warned = win
    pid = _project(conn)
    import shared.backup_service as bs
    calls = []

    def backup(p, label):
        calls.append(("backup", _counts(conn)))      # the data is still there when it is taken
        return True
    monkeypatch.setattr(bs, "backup_file_written", backup)
    w._on_delete(pid)
    assert calls == [("backup", (1, 1, 1))]
    assert _counts(conn) == (0, 0, 0) and not warned


def test_delete_failure_is_said_and_rolled_back(win, conn, monkeypatch):
    w, warned = win
    pid = _project(conn)
    conn.commit()
    conn.execute("CREATE TRIGGER nodel BEFORE DELETE ON projects "
                 "BEGIN SELECT RAISE(ABORT, 'refused'); END")
    import shared.backup_service as bs
    monkeypatch.setattr(bs, "backup_file_written", lambda p, label: True)
    w._on_delete(pid)
    assert _counts(conn) == (1, 1, 1)
    assert warned and "nothing was changed" in warned[0]


def test_form_year_days_are_one_transaction(qapp, conn, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from Munia import munia_data as db
    from Munia.project_form import ProjectForm
    warned = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warned.append(a[2]))
    pid = _project(conn)
    conn.commit()
    form = ProjectForm(conn)
    form.set_year(2026)
    form.load_project([p for p in db.get_projects_for_year(conn, 2026) if p["id"] == pid][0])
    blank = {"micro": 0, "report": 0, "id_deadline": "", "report_deadline": "", "notes": ""}
    form._alloc_cache[2027] = {**blank, "field_months": [{"month": 5, "field_days": 9}]}
    form._alloc_cache[2028] = {**blank, "field_months": []}
    real = db.set_project_annual_days

    def flaky(c, p, yr, data, commit=True):
        if yr == 2028:
            raise sqlite3.OperationalError("database is locked")
        return real(c, p, yr, data, commit=commit)
    monkeypatch.setattr(db, "set_project_annual_days", flaky)
    form._on_save()
    assert warned and "planned days could not be" in warned[0]
    # 2027's field days (written before the failure) were rolled back with the rest
    assert db.get_project_field_months(conn, pid, 2027) == []
    assert form._editing_id == pid


def test_failed_days_save_keeps_the_year_and_edit_state_through_the_windows_refresh(win, conn, monkeypatch):
    """Step to 2027, make the planned-days write fail, retry: 2026's days stay untouched and the
    2027 grid is saved under 2027 (the window's refresh calls form.set_year after `saved`)."""
    from Munia import munia_data as db
    w, warned = win
    form = w.form
    form.name_edit.setText("Two-year job")
    form.start_year_spin.setValue(2026)
    form.end_year_spin.setValue(2027)
    form.status_combo.setCurrentIndex(form.status_combo.findData("accepted"))
    form.field_grid.item(0, 1).setText("2")                 # 2026: 2 field days in May
    form._on_field_changed(0, 1)
    form._next_alloc_year()
    assert form._alloc_year == 2027
    form.field_grid.item(0, 1).setText("7")                 # 2027: 7 field days in May
    form._on_field_changed(0, 1)
    real = db.set_project_annual_days
    state = {"fail": True}

    def flaky(c, p, yr, data, commit=True):
        if state["fail"] and yr == 2027:
            raise sqlite3.OperationalError("database is locked")
        return real(c, p, yr, data, commit=commit)
    monkeypatch.setattr(db, "set_project_annual_days", flaky)
    form._on_save()
    assert warned and "planned days could not be" in warned[0]
    pid = form._editing_id
    assert pid and db.get_project_field_months(conn, pid, 2026) == []      # rolled back, none kept
    assert db.get_project_field_months(conn, pid, 2027) == []
    # the form is in edit state, on the year it was showing
    assert form._alloc_year == 2027 and form.alloc_year_lbl.text() == "2027/2028"
    assert form._title.text() == "Edit: Two-year job" and form.save_btn.text() == "Update"
    assert not form.del_btn.isHidden()
    state["fail"] = False
    form._on_save()                                          # the retry
    assert [m["field_days"] for m in db.get_project_field_months(conn, pid, 2026)] == [2]
    assert [m["field_days"] for m in db.get_project_field_months(conn, pid, 2027)] == [7]
