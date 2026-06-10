"""
Observation Import Wizard for Observatum V2.

A multi-step wizard for importing observation data from:
- iRecord CSV downloads (sync existing records)
- Personal CSV templates (new records)

Features:
- Mode selection (iRecord Sync vs Personal Upload)
- Auto-detection of iRecord format
- Column mapping with auto-match
- Live validation with progress counters
- Inline editing for Personal uploads
- Duplicate detection and handling
- "Never upload to iRecord" batch flag
- Confirmation dialog with import preview
- Auto-refresh of Observation tab after import

Usage:
    from src.views.dialogs.observation_import_wizard import ObservationImportWizard
    
    wizard = ObservationImportWizard(parent, uksi_model, vc_service, db, observation_model)
    wizard.import_completed.connect(on_import_done)
    if wizard.exec() == QDialog.Accepted:
        print(f"Imported {wizard.imported_count} records")
"""

from .observation_import_wizard import ObservationImportWizard
from .validation_worker import (
    ObservationImportRow,
    ObservationValidationWorker,
    RowStatus,
    ImportMode
)

__all__ = [
    'ObservationImportWizard',
    'ObservationImportRow',
    'ObservationValidationWorker',
    'RowStatus',
    'ImportMode',
]
