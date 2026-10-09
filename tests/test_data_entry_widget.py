"""The Data Entry widget driven offscreen on a throwaway database (9 Oct 2026):
DE7 Export for iRecord / Check return, DE4 a part-failed commit, DE5 and DE8 backups."""
import os
import sqlite3

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from DataEntry import csv_backup  # noqa: E402
from DataEntry import staging_repo as repo  # noqa: E402

ROW = dict(species_name="Philanthus triangulum", species_tvk="T1", date="2026-06-05",
           site_name="Elmley", grid_ref="TQ9368", method="Sweep", stage="Adult",
           recorder="Heeney, W.J.", vc_number=15, vice_county="East Kent")


@pytest.fixture
def widget(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    db = tmp_path / "observatum.db"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, irecord_id INTEGER, "
              "species_tvk TEXT, species_name TEXT, date TEXT, grid_ref TEXT, recorder TEXT, "
              "record_type TEXT, project_name TEXT, client TEXT)")
    c.commit()
    c.close()
    calls = []
    # each staging copy records how many rows staging held at that moment
    monkeypatch.setattr(csv_backup, "backup_staging", lambda conn: calls.append(
        ("staging", conn.execute("SELECT COUNT(*) FROM entry_staging").fetchone()[0])) or "s.csv")
    monkeypatch.setattr(csv_backup, "backup_observations", lambda p: calls.append("obs") or "o.csv")
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    shown = []
    for name in ("information", "warning"):
        monkeypatch.setattr(QMessageBox, name, lambda *a, **k: shown.append(a[1:3]))
    from DataEntry.data_entry_widget import DataEntryWidget
    w = DataEntryWidget(str(db), embedded=True, allow_commit=False)
    w._calls, w._shown = calls, shown
    yield w
    w.close()


def _grid(w):
    from DataEntry.entry_grid import EntryGridPage
    return w._job_host.findChildren(EntryGridPage)[-1]      # older ones await deleteLater


def _open(w, job_id):
    w._open_job(job_id)
    return _grid(w)


def test_personal_job_exports_for_irecord_commercial_commits(widget):
    pid = repo.ensure_personal_job(widget._conn)
    assert _open(widget, pid)._commit_btn.text() == "Export for iRecord"
    cid = repo.create_job(widget._conn, "Glory Park", "Commercial", "BAM", "Glory Park")
    assert _open(widget, cid)._commit_btn.text() == "Commit to Observatum"


def test_export_for_irecord_then_check_return(widget, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    from DataEntry import irecord_export as ie
    from DataEntry import irecord_return_dialog as dlg
    conn = widget._conn
    pid = repo.ensure_personal_job(conn)
    repo.insert_row(conn, pid, ROW)
    out = tmp_path / "out.csv"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(out), ""))
    monkeypatch.setattr(ie, "accepted_tvks", lambda tvks, uksi_path=None: {"T1"})
    grid = _open(widget, pid)
    grid._commit_btn.click()
    assert out.exists()
    job = repo.get_job(conn, pid)
    assert job["status"] == repo.AWAITING_IRECORD and repo.row_count(conn, pid) == 1
    assert widget._stack.currentIndex() == 0                     # back on the jobs list
    jobs = widget._jobs
    jobs._select_job(pid)
    assert jobs.btn_check.isVisible() or not jobs.isVisible()
    assert jobs.btn_check.isEnabled()
    assert repo.STATUS_LABELS[repo.AWAITING_IRECORD] in [
        jobs.table.item(r, 4).text() for r in range(jobs.table.rowCount())]

    # not back yet: the missing row is listed and the job stays open
    boxes = []
    monkeypatch.setattr(dlg.QMessageBox, "exec", lambda self: boxes.append(self.text()) or 0)
    jobs._check_return()
    assert "0 of 1" in boxes[-1] and repo.get_job(conn, pid)["status"] == repo.AWAITING_IRECORD

    # back from iRecord: Close job
    conn.execute("INSERT INTO observations (irecord_id, species_tvk, species_name, date, grid_ref, "
                 "recorder) VALUES (9, 'T1', 'Philanthus triangulum', '2026-06-05', 'TQ 9368', "
                 "'Heeney, W.J.')")
    monkeypatch.setattr(dlg.QMessageBox, "clickedButton",
                        lambda self: next(b for b in self.buttons() if b.text() == "Close job"))
    jobs._check_return()
    assert "1 of 1" in boxes[-1]
    assert repo.get_job(conn, pid)["status"] == repo.RETURNED_IRECORD


def test_commit_signal_runs_the_observations_backup(widget):
    cid = repo.create_job(widget._conn, "Glory Park", "Commercial", "BAM", "Glory Park")
    _open(widget, cid).committed.emit(3)
    assert widget._calls[-2][0] == "staging" and widget._calls[-1] == "obs"


def test_discard_and_delete_take_the_staging_copy_first(widget):
    conn = widget._conn
    cid = repo.create_job(conn, "Glory Park", "Commercial", "BAM", "Glory Park")
    repo.insert_row(conn, cid, ROW)
    grid = _open(widget, cid)
    widget._calls.clear()
    grid._do_discard()
    assert widget._calls[0] == ("staging", 1) and repo.row_count(conn, cid) == 0   # copy came first
    cid2 = repo.create_job(conn, "Hook Farm", "Commercial", "BAM", "Hook Farm")
    widget._back_to_jobs()
    widget._jobs._select_job(cid2)
    widget._calls.clear()
    widget._jobs._delete_selected()
    assert widget._calls[:1] == [("staging", 0)] and repo.get_job(conn, cid2) is None


def test_failed_backup_asks_before_discard(widget, monkeypatch):
    conn = widget._conn
    cid = repo.create_job(conn, "Glory Park", "Commercial", "BAM", "Glory Park")
    repo.insert_row(conn, cid, ROW)
    grid = _open(widget, cid)
    grid.before_change = lambda: None
    answers = iter([QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No])
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: next(answers))
    grid._do_discard()                                       # Discard? yes; anyway? no
    assert repo.row_count(conn, cid) == 1


def test_part_failed_commit_says_how_many_and_refreshes(widget, monkeypatch):
    from DataEntry import entry_grid
    conn = widget._conn
    cid = repo.create_job(conn, "Glory Park", "Commercial", "BAM", "Glory Park")
    repo.insert_row(conn, cid, ROW)
    grid = _open(widget, cid)

    class _Embargo:
        def __init__(self, *a):
            pass

        def exec(self):
            return entry_grid.QDialog.DialogCode.Accepted

        def value(self):
            return None
    monkeypatch.setattr(entry_grid, "EmbargoDialog", _Embargo)
    grid._commit_cb = lambda job_id, embargo: {"committed": 4, "remaining": 2, "error": "disk full",
                                               "batch": "DataEntry batch X"}
    got = []
    grid.committed.connect(got.append)
    grid._do_commit()
    assert got == [4]
    title, text = widget._shown[-1]
    assert title == "Commit stopped" and "Committed 4" in text and "disk full" in text
