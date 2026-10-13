"""The cleaning report's record detail dialog (split from cleaning_dashboard.py, 13 Oct 2026).

Double-click a row: the record's detail dialog. An ordinary Observation row keeps Edit /
Delete, wired to the Observation tab's own flows (observations/observation_record_actions:
the edit dialog; the backup before a delete; the "Also in iRecord" box). Hidden / returned,
Recording Scheme and Contributed rows are view only: those handlers write to `observations`
by id, so a row from another table must never reach them. The table is the one the rows on
screen came from, never the Data drop-down's (review, 13 Oct 2026).
"""
from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QPushButton

from shared.db_open import connect_ro


def find_record(main_db: str, source: str, record_id: int):
    """The row as a dict, or None (read-only)."""
    conn = connect_ro(main_db)
    try:
        conn.row_factory = sqlite3.Row
        found = conn.execute(f"SELECT * FROM {source} WHERE id = ?", (record_id,)).fetchone()
    finally:
        conn.close()
    return dict(found) if found is not None else None


def build_dialog(parent, record: dict, source: str, editable: bool):
    """The detail dialog for one record; Edit / Delete wired when `editable`, else hidden."""
    if source == "recording_scheme":
        from ..dialogs import SchemeRecordDetailDialog
        record.update(species=record.get("species_name", ""), common=record.get("common_name", ""),
                      location=record.get("site_name", ""), gridRef=record.get("grid_ref", ""),
                      vc=record.get("vc_number", ""),
                      verification=record.get("verification_status", ""))
        dlg = SchemeRecordDetailDialog(record, parent=parent)
    else:
        from ..dialogs import RecordDetailDialog
        dlg = RecordDetailDialog(record=record, record_type="observation", parent=parent)
    if editable and source == "observations":
        from ..observations import observation_record_actions as ora
        ora.wire_observation_detail(dlg, parent)
    else:
        for btn in dlg.findChildren(QPushButton):
            if btn.text().strip() in ("Edit", "Delete"):
                btn.hide()
    return dlg


def run_dialog(parent, dlg, editable: bool) -> bool:
    """Show the dialog; True when the Observation tab reported a change while it was open
    (an edit, a delete or a hide), so the report needs rebuilding -- not after a look."""
    from ..observations.observation_record_actions import observation_tab_for
    tab = observation_tab_for(parent) if editable else None
    changed = []

    def note(*_):
        changed.append(True)
    if tab is not None:
        tab.records_changed.connect(note)
    try:
        dlg.exec()
    finally:
        if tab is not None:
            tab.records_changed.disconnect(note)
    return bool(changed)


def reload_observation_tab(widget) -> None:
    """After Show again: the Observation tab lists the record again; stats marked stale."""
    from ..observations.observation_record_actions import observation_tab_for
    tab = observation_tab_for(widget)
    if tab is not None:
        tab._load_data()
        tab.records_changed.emit()
