"""
Home: a Quick Stats card for one kind of observation -- Personal or Commercial.

L16 / backlog F (10 Oct): the Home tab's single "Observation Data" block became two
cards, one per record type, above the Recording Scheme / Insect Collection card and
the Achievements card. The figures come from ObservationRepository.get_quick_stats
(record_type=...), the same call the old block used, so any change to how species are
counted there reaches both cards.
"""

from typing import Any, Dict

from PySide6.QtWidgets import QVBoxLayout

from .card import Card
from .quick_stats import QuickStatsPanel
from ...core.config import TabColors

# (stats key, label) in the order the old Observation Data block showed them
ROWS = (
    ('total_species', "Total Species"),
    ('total_records', "Total Records"),
    ('this_year_species', "This Year Species"),
    ('this_year_records', "This Year Records"),
    ('last_month_records', "Last Month Records"),
)


class ObservationStatsCard(Card):
    """Quick Stats for observations of one record type ('Personal' / 'Commercial')."""

    # The row look and theme handling are QuickStatsPanel's, shared as-is
    _create_stat_row = QuickStatsPanel._create_stat_row
    _reset_style = QuickStatsPanel._reset_style
    apply_theme = QuickStatsPanel.apply_theme

    def __init__(self, record_type: str, parent=None):
        super().__init__(f"Quick Stats: {record_type}", parent)
        self.record_type = record_type
        self._stat_rows = []
        self.stats_layout = QVBoxLayout()
        self.stats_layout.setSpacing(4)
        self.rows = {key: self._create_stat_row(label, "0", TabColors.OBSERVATION)
                     for key, label in ROWS}
        self.add_layout(self.stats_layout)

    def update_stats(self, stats: Dict[str, Any]):
        for key, row in self.rows.items():
            row['value'].setText(f"{int(stats.get(key, 0) or 0):,}")

    def value(self, key: str) -> str:
        """The figure shown for a stats key (tests and diagnostics)."""
        return self.rows[key]['value'].text()
