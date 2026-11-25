"""Observation Data: "Make specimens..." for the ticked records (25 Nov 2026).

Opens the same review screen as Data Entry (shared/make_specimens_dialog.py). The specimens are
linked to their records (specimens.observation_id) when they are made.
"""
from PySide6.QtWidgets import QMessageBox


def open_for_tab(tab):
    """Review and make specimens from the ticked records. Returns the dialog (None when it could
    not open) so a test can look at it."""
    from shared import make_specimens as ms
    from shared.db_open import connect_ro
    from shared.make_specimens_dialog import MakeSpecimensDialog
    from ...models.database import get_database
    ids = [o.get("id") for o in tab.table_model.get_checked_observations() if o.get("id")]
    if not ids:
        QMessageBox.information(tab, "Make specimens", "Tick the records you keep as specimens first.")
        return None
    db_path = str(getattr(get_database(), "main_db_path", "") or "")
    if not db_path:
        QMessageBox.warning(tab, "Make specimens", "The database is not ready.")
        return None
    conn = connect_ro(db_path)
    try:
        cands = ms.load_records(conn, ids)
    finally:
        conn.close()
    dlg = MakeSpecimensDialog(cands, db_path, linked=True, parent=tab)
    dlg.exec()
    if dlg.result_info:
        tab.records_changed.emit()          # the collection and stats refresh as after a delete
    return dlg
