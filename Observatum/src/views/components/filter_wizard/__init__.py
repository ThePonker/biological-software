"""
Filter Wizard Package.

Visual filter builder with card-based interface and multi-select support.

Components:
- FilterWizard: Main widget with card grid
- FilterCard/FilterCardGrid: Clickable filter category cards
- ChipDisplay: Applied filter chips with removal
- Dialog classes for each filter category
"""

from .filter_wizard import FilterWizard
from .filter_cards import FilterCard, FilterCardGrid
from .chip_display import ChipDisplay, FilterChip
from .what_filter_dialog import WhatFilterDialog
from .where_filter_dialog import WhereFilterDialog
from .when_filter_dialog import WhenFilterDialog
from .who_filter_dialog import WhoFilterDialog
from .how_filter_dialog import HowFilterDialog
from .status_filter_dialog import StatusFilterDialog

__all__ = [
    'FilterWizard',
    'FilterCard',
    'FilterCardGrid',
    'ChipDisplay',
    'FilterChip',
    'WhatFilterDialog',
    'WhereFilterDialog',
    'WhenFilterDialog',
    'WhoFilterDialog',
    'HowFilterDialog',
    'StatusFilterDialog',
]
