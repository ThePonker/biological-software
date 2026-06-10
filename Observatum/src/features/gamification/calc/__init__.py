"""
Gamification Calculator Modules.

Split calculation logic into domain-specific modules.
"""

from .records import RecordsCalculator
from .rare import RareCalculator

__all__ = ['RecordsCalculator', 'RareCalculator']
