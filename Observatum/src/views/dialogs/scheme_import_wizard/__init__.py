"""
Recording Scheme Import Wizard for Observatum V2.

A multi-step wizard for importing recording scheme data from:
- iRecord CSV downloads
- NBN Atlas CSV downloads
- Generic CSV files

Features:
- Mode selection (iRecord / NBN Atlas / Generic CSV)
- Auto-detection of file format
- Column mapping with auto-match
- Live validation with progress counters
- Inline editing for generic mode
- Duplicate detection and handling
- Auto-refresh of Recording Scheme tab after import

Usage:
    from src.views.dialogs.scheme_import_wizard import SchemeImportWizard

    wizard = SchemeImportWizard(parent, uksi_model, vc_service, db)
    wizard.import_completed.connect(on_import_done)
    if wizard.exec() == QDialog.Accepted:
        print(f"Imported {wizard.imported_count} records")
"""

from .scheme_import_wizard import SchemeImportWizard
from .validation_worker import (
    SchemeImportRow,
    SchemeValidationWorker,
    RowStatus,
    SchemeImportMode,
)

__all__ = [
    'SchemeImportWizard',
    'SchemeImportRow',
    'SchemeValidationWorker',
    'RowStatus',
    'SchemeImportMode',
]
