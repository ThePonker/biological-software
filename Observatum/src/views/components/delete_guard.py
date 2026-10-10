"""One rule for every delete in Observatum: a kept backup of observatum.db first.

Same as Observation Data's Delete Selected since the 9 Oct fix (OBS-01): a named
"pre-delete" copy via shared.backup_service.backup_main_only, and if that fails
nothing is deleted. Used by the single-record deletes in the detail dialogs
(observation, specimen, scheme record -- review OBS-04).
"""
from PySide6.QtWidgets import QMessageBox


def backup_before_delete(parent, title: str = "Delete") -> bool:
    """True when the pre-delete backup was written; otherwise says so and returns False."""
    try:
        from shared.backup_service import backup_main_only
        ok = backup_main_only("pre-delete")
    except Exception as e:
        print(f"[delete] pre-delete backup unavailable: {e}")
        ok = False
    if not ok:
        QMessageBox.critical(parent, title,
                             "The backup before deleting failed, so nothing has been deleted.")
    return ok
