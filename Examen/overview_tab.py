"""
Examen — Overview Tab (redesigned)

Clean summary: hero SQI card, headline numbers, one-line assessment.
Detailed breakdowns moved to Habitats/Assemblages/Species/Conservation tabs.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

BG = "#f5f5f4"; SURFACE = "#ffffff"; TEXT_PRIMARY = "#1f2937"
TEXT_SECONDARY = "#6b7280"; TEXT_MUTED = "#9ca3af"; BORDER = "#d1d5db"
MOSS_GREEN = "#4a7c59"; ACCENT = "#7c6c9f"; ACCENT_LIGHT = "#f0edf5"
ACCENT_DARK = "#5a4d78"; RED_STATUS = "#a63d40"; AMBER = "#c2956e"


class OverviewTab(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 20, 16, 16)
        layout.setSpacing(16)

        # Row 1: Hero SQI + key numbers
        top_row = QHBoxLayout()
        top_row.setSpacing(16)

        # Hero SQI card (larger, prominent)
        self.sqi_card = self._hero_card("SQI", "-", "", ACCENT_DARK)
        top_row.addWidget(self.sqi_card)

        # Key species card
        self.key_card = self._hero_card("Key species", "-", "", RED_STATUS)
        top_row.addWidget(self.key_card)

        # Total species card
        self.total_card = self._hero_card("Species", "-", "", TEXT_PRIMARY)
        top_row.addWidget(self.total_card)

        layout.addLayout(top_row)

        # Row 2: Summary sentence
        self.summary_sentence = QLabel("")
        self.summary_sentence.setWordWrap(True)
        self.summary_sentence.setFont(QFont("Georgia", 12))
        self.summary_sentence.setStyleSheet(
            "color: " + TEXT_PRIMARY + "; padding: 12px 16px; "
            "background: " + SURFACE + "; border: 1px solid " + BORDER + "; "
            "border-radius: 8px; line-height: 1.6;")
        layout.addWidget(self.summary_sentence)

        # Row 3: Tier breakdown (compact horizontal)
        tier_frame = QFrame()
        tier_frame.setStyleSheet(
            "QFrame { background: " + SURFACE + "; border: 1px solid "
            + BORDER + "; border-radius: 8px; }")
        tier_layout = QHBoxLayout(tier_frame)
        tier_layout.setContentsMargins(20, 12, 20, 12)
        tier_layout.setSpacing(32)

        self.rare_label = self._tier_item("Rare", "0", RED_STATUS)
        tier_layout.addWidget(self.rare_label)
        self.scarce_label = self._tier_item("Scarce", "0", AMBER)
        tier_layout.addWidget(self.scarce_label)
        self.priority_label = self._tier_item("Priority", "0", MOSS_GREEN)
        tier_layout.addWidget(self.priority_label)

        tier_layout.addStretch()

        self.pantheon_label = QLabel("")
        self.pantheon_label.setStyleSheet(
            "color: " + TEXT_MUTED + "; font-size: 11px;")
        tier_layout.addWidget(self.pantheon_label)

        layout.addWidget(tier_frame)

        # Row 4: Quick habitat snapshot (top 3 biotopes as simple chips)
        self.habitat_snapshot = QLabel("")
        self.habitat_snapshot.setWordWrap(True)
        self.habitat_snapshot.setStyleSheet(
            "color: " + TEXT_SECONDARY + "; font-size: 12px; padding: 4px 0;")
        layout.addWidget(self.habitat_snapshot)

        layout.addStretch()

    def set_result(self, result, detail=None, visits=0):
        sqi = result.overall_sqi
        sqi_val = str(int(sqi.sqi)) if sqi and sqi.sqi else "-"
        sqi_reliable = sqi and sqi.reliable

        # Hero cards
        self._update_hero(self.sqi_card, sqi_val,
                          "Reliable" if sqi_reliable else "< 15 scoring spp",
                          self._sqi_colour(sqi.sqi if sqi else 0))
        self._update_hero(self.key_card,
                          str(result.key_species_count),
                          f"{result.key_species_pct}% of Pantheon species",
                          RED_STATUS if result.key_species_count > 0 else TEXT_MUTED)
        self._update_hero(self.total_card,
                          str(result.total_species),
                          f"{result.species_in_pantheon} in Pantheon",
                          TEXT_PRIMARY)

        # Summary sentence
        parts = []
        parts.append(f"{result.total_species} species recorded")
        if visits: parts.append(f"across {visits} visits")
        parts.append(f"{result.key_species_count} key species ({result.key_species_pct}%)")
        sqi_text = f"SQI {sqi_val}"
        if sqi_reliable:
            sqi_text += " (reliable)"
        else:
            sqi_text += " (fewer than 15 scoring species — treat with caution)"
        parts.append(sqi_text)

        # SQI interpretation
        if sqi and sqi.sqi:
            if sqi.sqi >= 200: parts.append("This indicates a site of national importance.")
            elif sqi.sqi >= 150: parts.append("This indicates a site of regional importance.")
            elif sqi.sqi >= 125: parts.append("This indicates a site of some conservation value.")
            elif sqi.sqi >= 100: parts.append("No significant concentration of rare species.")
        self.summary_sentence.setText(". ".join(parts) + ".")

        # Tier breakdown
        self._update_tier(self.rare_label, str(result.rare_count))
        self._update_tier(self.scarce_label, str(result.scarce_count))
        self._update_tier(self.priority_label, str(result.priority_count))
        scoring = sqi.species_with_sqs if sqi else 0
        self.pantheon_label.setText(
            f"{result.species_in_pantheon} species in Pantheon  |  "
            f"{scoring} with SQS scores  |  {visits} visits")

        # Habitat snapshot — top biotopes only
        if result.biotope_counts:
            top = sorted(result.biotope_counts.items(), key=lambda x: -x[1])[:4]
            chips = [f"{name} ({count})" for name, count in top]
            self.habitat_snapshot.setText(
                "Dominant biotopes: " + "  \u2022  ".join(chips)
                + "     \u2192 see Habitats tab for full breakdown")
        else:
            self.habitat_snapshot.setText("")

    def _hero_card(self, title, value, subtitle, colour):
        card = QFrame()
        card.setStyleSheet(
            "QFrame { background: " + SURFACE + "; border: 1px solid "
            + BORDER + "; border-radius: 10px; }")
        card.setMinimumHeight(110)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        t = QLabel(title)
        t.setFont(QFont("Segoe UI", 11))
        t.setStyleSheet("color: " + TEXT_MUTED + "; border: none; background: none;")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(t)

        v = QLabel(value)
        v.setObjectName("hero_value")
        v.setFont(QFont("Georgia", 32, QFont.Weight.Bold))
        v.setStyleSheet("color: " + colour + "; border: none; background: none;")
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(v)

        s = QLabel(subtitle)
        s.setObjectName("hero_sub")
        s.setFont(QFont("Segoe UI", 10))
        s.setStyleSheet("color: " + TEXT_MUTED + "; border: none; background: none;")
        s.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(s)

        return card

    def _update_hero(self, card, value, subtitle, colour):
        v = card.findChild(QLabel, "hero_value")
        if v:
            v.setText(value)
            v.setStyleSheet("color: " + colour + "; border: none; background: none;")
        s = card.findChild(QLabel, "hero_sub")
        if s:
            s.setText(subtitle)

    def _tier_item(self, label, value, colour):
        w = QWidget()
        w.setStyleSheet("border: none; background: none;")
        layout = QHBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        dot = QLabel("\u25CF")
        dot.setStyleSheet(f"color: {colour}; font-size: 14px; border: none; background: none;")
        layout.addWidget(dot)
        name = QLabel(label)
        name.setStyleSheet("color: " + TEXT_SECONDARY + "; font-size: 12px; border: none; background: none;")
        layout.addWidget(name)
        val = QLabel(value)
        val.setObjectName("tier_val")
        val.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        val.setStyleSheet(f"color: {colour}; border: none; background: none;")
        layout.addWidget(val)
        return w

    def _update_tier(self, widget, value):
        v = widget.findChild(QLabel, "tier_val")
        if v: v.setText(value)

    def _sqi_colour(self, sqi):
        if sqi >= 150: return MOSS_GREEN
        if sqi >= 125: return AMBER
        if sqi > 0: return ACCENT_DARK
        return TEXT_MUTED
