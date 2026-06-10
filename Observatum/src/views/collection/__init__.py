"""
Insect Collection tab components.
"""

from .insect_collection_tab import InsectCollectionTab
from .collection_filters import CollectionFilterBar
from .collection_header import CollectionHeader
from .collection_toolbar import CollectionToolbar
from .specimen_table_model import SpecimenTableModel

# Re-export dialogs from centralized location for backwards compatibility
from ..dialogs import RecordDetailDialog, AddSpecimenDialog

# Backwards compatible alias
SpecimenDetailDialog = RecordDetailDialog

__all__ = [
    'InsectCollectionTab',
    'CollectionFilterBar',
    'CollectionHeader',
    'CollectionToolbar',
    'SpecimenTableModel',
    # Dialogs (re-exported from src.views.dialogs)
    'SpecimenDetailDialog',
    'RecordDetailDialog',
    'AddSpecimenDialog',
]
