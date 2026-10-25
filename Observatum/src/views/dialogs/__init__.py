"""
Dialogs Package.

Various dialog components for Observatum V2.
"""

from .record_detail_dialog import RecordDetailDialog
from .scheme_record_detail_dialog import SchemeRecordDetailDialog
from .add_specimen_dialog import AddSpecimenDialog
from .observation_import_wizard.observation_import_wizard import ObservationImportWizard
from .scheme_import_wizard.scheme_import_wizard import SchemeImportWizard
from .specimen_import_wizard.specimen_import_wizard import SpecimenImportWizard

__all__ = [
    'RecordDetailDialog',
    'SchemeRecordDetailDialog',
    'AddSpecimenDialog',
    'ObservationImportWizard',
    'SchemeImportWizard',
    'SpecimenImportWizard',
]

from .species_list_dialog import SpeciesListDialog
