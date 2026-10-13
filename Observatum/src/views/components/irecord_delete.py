"""Deleting an observation that is also in iRecord (F72, agreed with Wil 12 Oct 2026, late).

A record Observatum deleted used to come straight back with the next iRecord download. So
for a record with an iRecord ID, Delete shows one box:

    This record is also in iRecord. Delete it there first, or the next download brings it
    back.      [Open in iRecord]  [Deleted in iRecord -- remove here]  [Cancel]

"Remove here" HIDES the record (observations.hidden_at, shared/hidden_records.py) and
remembers its iRecord ID, so a download that brings it again keeps it hidden and the
cleaning report lists it under "Came back from iRecord -- check". Nothing is deleted.
Records with no iRecord ID are deleted as before. Used by the record detail dialog and the
Observation tab's Delete Selected.
"""
from __future__ import annotations

from typing import Iterable, List, Optional

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox

from shared.irecord_links import irecord_id_of, irecord_url

from ...themes import theme

OPEN, HIDE, CANCEL = "open", "hide", "cancel"
TITLE = "Also in iRecord"
MESSAGE_ONE = ("This record is also in iRecord. Delete it there first, or the next download "
               "brings it back.")
MESSAGE_MANY = ("{n} of these records are also in iRecord. Delete them there first, or the next "
                "download brings them back.")
EDIT_NOTE = ("Change this in iRecord; the change comes back with the next download. An edit "
             "here is kept until then, and the download replaces it.")
SCHEMA_MISSING = ("The database is not ready for this yet: run "
                  "scripts\\add_hidden_at_column.py (dry run, then --apply) and try again.")
MAX_OPEN = 10                                   # pages opened at once from the batch box

open_url = QDesktopServices.openUrl             # replaceable in tests


def with_irecord(records: Iterable[dict]) -> List[dict]:
    """The records (dicts) that hold an iRecord ID."""
    return [r for r in records if irecord_id_of(r.get("irecord_id"))]


def ask(parent, count: int = 1) -> str:
    """The box; returns OPEN, HIDE or CANCEL."""
    t = theme()
    box = QMessageBox(parent)
    box.setWindowTitle(TITLE)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setText(MESSAGE_ONE if count == 1 else MESSAGE_MANY.format(n=count))
    b_open = box.addButton("Open in iRecord", QMessageBox.ButtonRole.ActionRole)
    b_hide = box.addButton("Deleted in iRecord — remove here", QMessageBox.ButtonRole.DestructiveRole)
    b_cancel = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
    b_open.setStyleSheet(t.button_secondary_style())
    b_hide.setStyleSheet(t.button_delete_style())
    b_cancel.setStyleSheet(t.button_cancel_style())
    b_hide.setToolTip("Hides the record here (it is kept, not deleted) and remembers its "
                      "iRecord ID so a download cannot bring it back.")
    box.setDefaultButton(b_cancel)
    box.setEscapeButton(b_cancel)
    box.exec()
    clicked = box.clickedButton()
    if clicked is b_open:
        return OPEN
    if clicked is b_hide:
        return HIDE
    return CANCEL


def open_pages(records: Iterable[dict]) -> int:
    """Open each record's iRecord page (the first MAX_OPEN); returns how many opened."""
    n = 0
    for r in records:
        url = irecord_url(r.get("irecord_id"))
        if url and n < MAX_OPEN:
            open_url(QUrl(url))
            n += 1
    return n


def hide_records(parent, records: Iterable[dict], db=None, title: str = "Delete") -> Optional[int]:
    """Back up, then hide every record given (one transaction each; ids and species kept).
    Returns the number hidden, or None when nothing was done (backup failed, schema missing)."""
    from shared.hidden_records import hide, schema_present
    from .delete_guard import backup_before_delete
    from ...models.database import get_database

    records = [r for r in records if r.get("id") and irecord_id_of(r.get("irecord_id"))]
    if not records:
        return 0
    db = db or get_database()
    with db.main_connection() as conn:
        if not schema_present(conn):
            QMessageBox.warning(parent, title, SCHEMA_MISSING)
            return None
    if not backup_before_delete(parent, title):
        return None
    n = 0
    with db.main_connection() as conn:
        for r in records:
            if hide(conn, r["id"], r["irecord_id"], r.get("species_name") or ""):
                n += 1
    print(f"[irecord_delete] hidden {n} record(s): ids {[r['id'] for r in records][:20]}")
    return n


def schema_ready(db=None) -> bool:
    """True when hidden_at and hidden_irecord_ids are in the open database."""
    from shared.hidden_records import schema_present
    from ...models.database import get_database
    try:
        db = db or get_database()
        with db.main_connection() as conn:
            return schema_present(conn)
    except Exception:
        return False


__all__ = ["OPEN", "HIDE", "CANCEL", "EDIT_NOTE", "ask", "open_pages", "hide_records",
           "with_irecord", "schema_ready"]
