"""
Gamification Window Tabs.

Each tab is encapsulated in its own class with create() and load() methods.
"""

from .overview import OverviewTab
from .tiers import TiersTab
from .records import RecordsTab
from .vcs import VCsTab
from .families import FamiliesTab
from .rare import RareTab

__all__ = [
    'OverviewTab',
    'TiersTab',
    'RecordsTab',
    'VCsTab',
    'FamiliesTab',
    'RareTab',
]
