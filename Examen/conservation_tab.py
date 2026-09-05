"""
Examen — Conservation Tab

Conservation status breakdown by category. Shows counts for each
status level (NR, NS, Na, Nb, CR, EN, VU, NT, S41, etc.) with
visual bars.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QGridLayout,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

BG = "#f5f5f4"; SURFACE = "#ffffff"; TEXT_PRIMARY = "#1f2937"; TEXT_HEADING = "#4b5563"
TEXT_SECONDARY = "#6b7280"; TEXT_MUTED = "#9ca3af"; BORDER = "#d1d5db"; SEPARATOR = "#e5e7eb"
MOSS_GREEN = "#4a7c59"; ACCENT_DARK = "#5a4d78"; RED_STATUS = "#a63d40"; AMBER = "#c2956e"

# Status categories in display order
CATEGORIES = [
    ("Threat status", [
        ("CR", "Critically Endangered", RED_STATUS),
        ("EN", "Endangered", RED_STATUS),
        ("VU", "Vulnerable", "#d97706"),
        ("NT", "Near Threatened", AMBER),
    ]),
    ("Rarity (current)", [
        ("NR", "Nationally Rare", RED_STATUS),
        ("NS", "Nationally Scarce", AMBER),
    ]),
    ("Rarity (legacy)", [
        ("RDB1", "Red Data Book 1", RED_STATUS),
        ("RDB2", "Red Data Book 2", RED_STATUS),
        ("RDB3", "Red Data Book 3", AMBER),
        ("RDBK", "Red Data Book K", AMBER),
        ("Na", "Notable A", AMBER),
        ("Nb", "Notable B", "#92774e"),
        ("Notable", "Notable", "#92774e"),
    ]),
    ("Policy", [
        ("S41", "Section 41", MOSS_GREEN),
        ("WCA", "Legal protection", ACCENT_DARK),
    ]),
]


class ConservationTab(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 12, 8, 8)
        self._layout.setSpacing(12)
        self._widgets = []

    def set_result(self, result, detail=None):
        for w in self._widgets:
            w.deleteLater()
        self._widgets.clear()

        # Count statuses from key species
        status_counts = {}
        for k in result.key_species:
            for code in self._parse_status(k.short_status, k.tier):
                status_counts[code] = status_counts.get(code, 0) + 1

        total_key = result.key_species_count
        total_species = result.total_species

        # Header
        hdr = QLabel(f"{total_key} key species of {total_species} total "
                      f"({result.key_species_pct}%)")
        hdr.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        hdr.setStyleSheet("color: " + ACCENT_DARK + ";")
        self._layout.insertWidget(self._layout.count(), hdr)
        self._widgets.append(hdr)

        for group_name, statuses in CATEGORIES:
            group_counts = [(code, label, colour, status_counts.get(code, 0))
                            for code, label, colour in statuses]
            if not any(c[3] > 0 for c in group_counts):
                continue

            grp = QFrame()
            grp.setStyleSheet("QFrame { background: " + SURFACE + "; border: 1px solid "
                               + BORDER + "; border-radius: 6px; }")
            gl = QVBoxLayout(grp); gl.setContentsMargins(12, 10, 12, 10); gl.setSpacing(6)

            title = QLabel(group_name)
            title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            title.setStyleSheet("color: " + TEXT_HEADING + "; border: none;")
            gl.addWidget(title)

            for code, label, colour, count in group_counts:
                if count == 0:
                    continue
                row = QHBoxLayout(); row.setSpacing(8)

                code_lbl = QLabel(code)
                code_lbl.setFixedWidth(50)
                code_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
                code_lbl.setStyleSheet(f"color: {colour}; border: none;")
                row.addWidget(code_lbl)

                desc_lbl = QLabel(label)
                desc_lbl.setFixedWidth(160)
                desc_lbl.setStyleSheet("color: " + TEXT_SECONDARY + "; font-size: 11px; border: none;")
                row.addWidget(desc_lbl)

                # Visual bar
                bar_container = QFrame()
                bar_container.setFixedHeight(18)
                bar_container.setStyleSheet("background: " + BG + "; border-radius: 3px; border: none;")
                bar_width = min(200, max(20, count * 40))
                bar = QFrame(bar_container)
                bar.setFixedSize(bar_width, 18)
                bar.setStyleSheet(f"background: {colour}; border-radius: 3px; opacity: 0.7;")
                row.addWidget(bar_container, 1)

                count_lbl = QLabel(str(count))
                count_lbl.setFixedWidth(30)
                count_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
                count_lbl.setStyleSheet(f"color: {colour}; border: none;")
                count_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
                row.addWidget(count_lbl)

                gl.addLayout(row)

            self._layout.insertWidget(self._layout.count(), grp)
            self._widgets.append(grp)

        # Guild summary
        if result.larval_guild_counts or result.adult_guild_counts:
            guild_frame = QFrame()
            guild_frame.setStyleSheet("QFrame { background: " + SURFACE + "; border: 1px solid "
                                       + BORDER + "; border-radius: 6px; }")
            gfl = QVBoxLayout(guild_frame); gfl.setContentsMargins(12, 10, 12, 10); gfl.setSpacing(4)
            gt = QLabel("Feeding guilds")
            gt.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            gt.setStyleSheet("color: " + TEXT_HEADING + "; border: none;")
            gfl.addWidget(gt)

            for label, counts in [("Larval", result.larval_guild_counts),
                                   ("Adult", result.adult_guild_counts)]:
                if counts:
                    top = sorted(counts.items(), key=lambda x: -x[1])[:6]
                    text = f"{label}: " + ", ".join(f"{k} ({v})" for k, v in top)
                    gl_lbl = QLabel(text)
                    gl_lbl.setWordWrap(True)
                    gl_lbl.setStyleSheet("color: " + TEXT_SECONDARY + "; font-size: 11px; border: none;")
                    gfl.addWidget(gl_lbl)

            self._layout.insertWidget(self._layout.count(), guild_frame)
            self._widgets.append(guild_frame)

    def _parse_status(self, short_status, tier):
        """Extract status codes from the short_status string."""
        codes = set()
        if not short_status:
            if tier == "Priority": codes.add("S41")
            return codes
        for token in short_status.replace(",", " ").split():
            token = token.strip()
            if token in ("NR", "NS", "Na", "Nb", "Notable", "CR", "EN", "VU", "NT",
                         "RDB1", "RDB2", "RDB3", "RDBK"):
                codes.add(token)
            elif token == "S41" or "S41" in short_status:
                codes.add("S41")
        if not codes:
            if tier == "Rare": codes.add("NR")
            elif tier == "Scarce": codes.add("NS")
            elif tier == "Priority": codes.add("S41")
        return codes
