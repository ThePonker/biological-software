"""The two Personal-job dialogs (DE7, 9 Oct 2026): Export for iRecord (from the grid) and
Check iRecord return (from the Jobs page). Logic in irecord_export.py."""
from __future__ import annotations

from PySide6.QtWidgets import QFileDialog, QMessageBox

from DataEntry import date_utils
from DataEntry import irecord_export as ie
from DataEntry import staging_repo as repo


def export_for_irecord(parent, conn, job) -> bool:
    """Ask for a file, write the iRecord CSV and mark the job awaiting. True when done."""
    rows = repo.fetch_rows(conn, job["id"])
    bad = ie.blocking_rows(rows)
    if bad:
        more = " …" if len(bad) > 20 else ""
        QMessageBox.warning(
            parent, "Export for iRecord",
            f"{len(bad)} row(s) have a species but no date or No. iRecord can read: rows "
            f"{', '.join(str(n) for n in bad[:20])}{more}.\n\n"
            "Type a date (dd/mm/yyyy, mm/yyyy or a year) and a whole-number No., "
            "or clear the row, then export.")
        return False
    n = sum(1 for r in rows if (r.get("species_name") or "").strip())
    if not n:
        QMessageBox.information(parent, "Export for iRecord", "Nothing to export yet.")
        return False
    default = f"{(job.get('name') or 'Personal').replace(' ', '_')}_iRecord.csv"
    path, _ = QFileDialog.getSaveFileName(parent, "Export for iRecord", default, "CSV files (*.csv)")
    if not path:
        return False
    try:
        res = ie.export_job(conn, job, path)
    except Exception as e:
        QMessageBox.warning(parent, "Export for iRecord", f"Nothing was exported.\n\n{e}")
        return False
    QMessageBox.information(
        parent, "Exported for iRecord",
        f"Wrote {res['written']} record(s) to:\n{path}\n\nTVKs {res['tvk_check']}.\n\n"
        "Import the file into iRecord. The job is kept, marked “exported – awaiting "
        "iRecord”. After the next iRecord sync, select it on the Jobs page and choose "
        "“Check iRecord return” to confirm every record came back, then close it.")
    return True


def _row_text(n, r) -> str:
    return (f"row {n}: {r.get('species_name') or ''}, {date_utils.to_display(r.get('date'))}, "
            f"{r.get('grid_ref') or 'no grid ref'}, {r.get('recorder') or 'no recorder'}")


def check_return(parent, conn, job_id) -> bool:
    """Show how many of the job's records are back from iRecord; offer to close the job
    when all are. True when it was closed."""
    job = repo.get_job(conn, job_id)
    if not job:
        return False
    try:
        res = ie.check_return(conn, job)
    except Exception as e:
        QMessageBox.warning(parent, "Check iRecord return", f"The check could not run.\n\n{e}")
        return False
    back = len(res["matched"]) + len(res["matched_loose"])
    total = res["total"]
    lines = [f"{back} of {total} record(s) are back from iRecord."]
    if res["matched_loose"]:
        lines.append(f"{len(res['matched_loose'])} of them match on species, date and grid ref "
                     "but the recorder is written differently.")
    box = QMessageBox(parent)
    box.setWindowTitle("Check iRecord return")
    if res["missing"]:
        box.setIcon(QMessageBox.Icon.Information)
        shown = [_row_text(n, r) for n, r in res["missing"][:25]]
        more = len(res["missing"]) - len(shown)
        box.setText("\n".join(lines) + f"\n\nNot back yet ({len(res['missing'])}):")
        box.setInformativeText("\n".join(shown) + (f"\n… and {more} more" if more > 0 else "")
                               + "\n\nRun the iRecord sync in Observatum, then check again. A "
                               "record iRecord holds with a different date, grid ref or name "
                               "will not match.")
        box.addButton(QMessageBox.StandardButton.Ok)
        box.exec()
        return False
    if not total:
        box.setText("This job has no records to check.")
        box.addButton(QMessageBox.StandardButton.Ok)
        box.exec()
        return False
    box.setIcon(QMessageBox.Icon.Question)
    box.setText("\n".join(lines) + "\n\nAll are back. Close the job?")
    box.setInformativeText("Closing keeps the job and its rows (tick “Show finished jobs” to "
                           "see it) but no longer counts them as staged.")
    close = box.addButton("Close job", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("Not now", QMessageBox.ButtonRole.RejectRole)
    box.exec()
    if box.clickedButton() is not close:
        return False
    ie.close_job(conn, job)
    return True
