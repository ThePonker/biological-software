"""Edit and Delete for one Recording Scheme record (review OBS-04).

SchemeRecordDetailDialog emitted edit_requested / delete_requested and nothing listened,
so Edit did nothing and Delete asked "Are you sure?" and then did nothing. The
Recording Scheme tab and the scheme dashboard connect them through wire_scheme_detail().

Edit uses the same dialog as an observation (EditObservationDialog) with date and grid
ref optional (1,984 scheme records are undated). A changed grid ref re-derives VC and
lat/long exactly as an observation edit does (OBS-03). Delete takes the pre-delete
backup first (components.delete_guard), then removes that one row by id.
"""
from typing import Callable, Dict, Optional

from PySide6.QtWidgets import QMessageBox

from ..components.delete_guard import backup_before_delete

# Columns an edit may write (all exist in recording_scheme)
EDITABLE = ('species_name', 'species_tvk', 'common_name', 'family', 'order_name', 'date',
            'site_name', 'grid_ref', 'vice_county', 'vc_number', 'latitude', 'longitude',
            'geodetic_datum', 'recorder', 'determiner', 'comment')


def _vc_service():
    try:
        from ...services.vc_lookup_service import VCLookupService
        return VCLookupService()
    except Exception as e:
        print(f"[Scheme] VC lookup unavailable: {e}")
        return None


def scheme_updates(edited: Dict, record: Dict, vc_service) -> tuple:
    """(column -> value, boundary note) for an edited scheme record."""
    from ..observations.observation_detail_mixin import ObservationDetailMixin
    edited = dict(edited)
    derived, note = ObservationDetailMixin._derive_location_fields(
        edited.get('grid_ref'), record.get('grid_ref'), vc_service)
    if not derived:                       # grid ref unchanged: keep its VC and position
        for k in ('vice_county', 'vc_number'):
            edited.pop(k, None)
    updates = {k: v for k, v in edited.items() if k in EDITABLE and v is not None}
    updates.update(derived)
    return updates, note


def edit_scheme_record(parent, record: Dict, db, uksi_model=None) -> bool:
    """Open the editor for one scheme record and write the changes. True if saved."""
    from ..dialogs.edit_observation_dialog import EditObservationDialog
    record_id = record.get('id')
    if not record_id:
        return False
    # The full stored row, not the table's copy: a field the table didn't load would
    # otherwise be written back blank
    rows = db.execute_main("SELECT * FROM recording_scheme WHERE id = ?", (record_id,))
    if not rows:
        return False
    record = dict(rows[0])
    vc = _vc_service()
    dlg = EditObservationDialog(parent=parent, uksi_model=uksi_model, vc_service=vc,
                                observation=record, db=db, require_date_and_grid=False)
    dlg.setWindowTitle("Edit Scheme Record")
    if not dlg.exec():
        return False
    updates, note = scheme_updates(dlg.get_observation_data(), record, vc)
    if not updates:
        return False
    cols = list(updates)
    db.execute_main_write(
        f"UPDATE recording_scheme SET {', '.join(c + ' = ?' for c in cols)}, "
        "updated_at = datetime('now') WHERE id = ?",
        tuple(updates[c] for c in cols) + (record_id,))
    if note:
        QMessageBox.information(parent, "Vice-county", note)
    return True


def delete_scheme_record(parent, record: Dict, db) -> bool:
    """Delete one scheme record by id after the pre-delete backup. True if deleted.

    The detail dialog has already asked "Are you sure?".
    """
    record_id = record.get('id')
    if not record_id or not backup_before_delete(parent, "Delete Scheme Record"):
        return False
    n = db.execute_main_write("DELETE FROM recording_scheme WHERE id = ?", (record_id,))
    print(f"[Scheme] Deleted record id {record_id} ({record.get('species_name')}): {n} row")
    return bool(n)


def wire_scheme_detail(dialog, parent, on_changed: Callable[[], None],
                       uksi_model=None, db_getter: Optional[Callable] = None) -> None:
    """Connect a SchemeRecordDetailDialog's Edit and Delete to the functions above."""
    def _db():
        if db_getter is not None:
            return db_getter()
        from ...models.database import get_database
        return get_database()

    def on_edit(record):
        dialog.accept()
        try:
            if edit_scheme_record(parent, record, _db(), uksi_model):
                on_changed()
        except Exception as e:
            QMessageBox.critical(parent, "Edit Scheme Record", f"Could not save the record:\n{e}")

    def on_delete(record):
        try:
            if delete_scheme_record(parent, record, _db()):
                on_changed()
        except Exception as e:
            QMessageBox.critical(parent, "Delete Scheme Record", f"Could not delete the record:\n{e}")

    dialog.edit_requested.connect(on_edit)
    dialog.delete_requested.connect(on_delete)
