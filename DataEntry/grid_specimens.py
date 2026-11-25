"""Make specimens from the Keep-ticked rows of a Data Entry job (25 Nov 2026).

The grid's "Make specimens..." button calls open_for_grid(page). The work is in
shared/make_specimens.py; the review screen is shared/make_specimens_dialog.py.
"""
from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from DataEntry import staging_repo as repo


def main_db_path(conn):
    """The file behind a connection ('' for an in-memory database)."""
    for _seq, name, path in conn.execute("PRAGMA database_list"):
        if name == "main":
            return path or ""
    return ""


def open_for_grid(page):
    """Open the review screen for the job's Keep-ticked rows. Returns the dialog (None when it
    could not open), so a test can look at it; the caller has nothing else to do."""
    from shared import make_specimens as ms
    from shared.make_specimens_dialog import MakeSpecimensDialog
    job = repo.get_job(page._conn, page._job_id) or page._job
    if repo.is_test_copy(job):
        QMessageBox.information(page, "Make specimens", "This is a test copy of a job: specimens "
                                "cannot be made from it. Discard it when you have finished with it.")
        return None
    model = page._model
    if not model.has_keep_column():
        QMessageBox.information(page, "Make specimens", "The Keep column is not in this database yet.")
        return None
    ids = model.kept_ids()
    if not ids:
        QMessageBox.information(page, "Make specimens", "Tick Keep on the rows you keep as specimens "
                                "first (Space, double-click or type x in the Keep column).")
        return None
    db_path = main_db_path(page._conn)
    if not db_path:
        QMessageBox.information(page, "Make specimens", "This job is not in a database file.")
        return None
    cands = ms.load_rows(page._conn, ids, job, vc_service=getattr(page, "_vc_service", None))
    dlg = MakeSpecimensDialog(cands, db_path, linked=ms.is_linked_job(job), parent=page)
    dlg.exec()
    if dlg.result_info:                              # made: those rows are done with
        model.clear_keep([i for (kind, i) in dlg.result_info["by_source"] if kind == "row"])
        model.refresh_made_counts()                  # those rows now show "made N"
        page._check_changed()
    return dlg
