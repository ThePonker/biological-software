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

# Which designations count in which jurisdiction is decided in ONE place --
# CodexRepository, the same functions _classify uses for the key-species count.
# The tab calls them rather than keeping its own list, so the display can never
# disagree with the number above it.
try:
    from shared.repositories.codex_repository import (
        _priority_applies, _legal_applies, StatusEntry)
except ImportError:  # pragma: no cover -- degrade to "everything applies"
    _priority_applies = None
    _legal_applies = None
    StatusEntry = None


def _priority_ok(value, jurisdiction):
    if _priority_applies is None:
        return True
    return _priority_applies(value, jurisdiction)


def _legal_ok(text, jurisdiction):
    # KeySpeciesEntry.legal holds (detail or value); rebuild a StatusEntry so
    # _legal_applies sees exactly what _classify saw.
    if _legal_applies is None or StatusEntry is None:
        return True
    return _legal_applies(StatusEntry(value=text, detail=text), jurisdiction)

BG = "#f5f5f4"; SURFACE = "#ffffff"; TEXT_PRIMARY = "#1f2937"; TEXT_HEADING = "#4b5563"
TEXT_SECONDARY = "#6b7280"; TEXT_MUTED = "#9ca3af"; BORDER = "#d1d5db"; SEPARATOR = "#e5e7eb"
MOSS_GREEN = "#4a7c59"; ACCENT_DARK = "#5a4d78"; RED_STATUS = "#a63d40"; AMBER = "#c2956e"
# Designations from another jurisdiction: shown for completeness, greyed because
# they do not count towards key species here.
NA_TEXT = TEXT_MUTED; NA_BAR = "#d9dce1"

# Status categories in display order.
# Threat and rarity codes are fixed vocabularies. Priority jurisdictions and
# legal instruments are open sets -- whatever Codex holds is shown -- so they
# are handled separately below rather than listed here.
CATEGORIES = [
    ("Threat status (GB, 2001 IUCN)", [
        ("CR", "Critically Endangered", RED_STATUS),
        ("EN", "Endangered", RED_STATUS),
        ("VU", "Vulnerable", "#d97706"),
        ("NT", "Near Threatened", AMBER),
        ("DD", "Data Deficient", AMBER),
    ]),
    ("Threat status (pre-2001)", [
        ("RDB1", "Red Data Book 1", RED_STATUS),
        ("RDB2", "Red Data Book 2", RED_STATUS),
        ("RDB3", "Red Data Book 3", AMBER),
        ("RDBK", "Red Data Book K", AMBER),
    ]),
    ("Rarity (current)", [
        ("NR", "Nationally Rare", RED_STATUS),
        ("NS", "Nationally Scarce", AMBER),
    ]),
    ("Rarity (legacy)", [
        ("Na", "Notable A", AMBER),
        ("Nb", "Notable B", "#92774e"),
        ("Notable", "Notable", "#92774e"),
    ]),
]

PRIORITY_GROUP = "Priority listings"
LEGAL_GROUP = "Legal protection"

class ConservationTab(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 12, 8, 8)
        self._layout.setSpacing(12)
        self._widgets = []
        self._juris = "England"

    def set_result(self, result, detail=None):
        for w in self._widgets:
            w.deleteLater()
        self._widgets.clear()

        # Counts come from the structured tracks on each key species, not from
        # parsing a display string. Priority jurisdictions and legal instruments
        # are counted under their own names.
        status_counts = {}
        priority_counts = {}
        legal_counts = {}
        for k in result.key_species:
            for code in (getattr(k, "rarity", ""), getattr(k, "threat", ""),
                         getattr(k, "threat_legacy", "")):
                if code:
                    status_counts[code] = status_counts.get(code, 0) + 1
            for j in getattr(k, "priority", None) or []:
                priority_counts[j] = priority_counts.get(j, 0) + 1
            for inst in getattr(k, "legal", None) or []:
                legal_counts[inst] = legal_counts.get(inst, 0) + 1

        juris = getattr(result, "jurisdiction", None) or "England"
        self._juris = juris

        total_key = result.key_species_count
        total_species = result.total_species

        hdr = QLabel(f"{total_key} key species of {total_species} total "
                      f"({result.key_species_pct}%)")
        hdr.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        hdr.setStyleSheet("color: " + ACCENT_DARK + ";")
        self._layout.insertWidget(self._layout.count(), hdr)
        self._widgets.append(hdr)

        for group_name, statuses in CATEGORIES:
            rows = [(code, label, colour, status_counts.get(code, 0))
                    for code, label, colour in statuses]
            rows = [r for r in rows if r[3] > 0]
            if rows:
                self._add_group(group_name, rows)

        # Open-set groups. Designations that apply in this jurisdiction first,
        # most frequent first; other jurisdictions' designations after, greyed.
        if priority_counts:
            rows = [(self._abbrev(j), j, MOSS_GREEN, n, _priority_ok(j, juris))
                    for j, n in priority_counts.items()]
            rows.sort(key=lambda r: (not r[4], -r[3]))
            self._add_group(PRIORITY_GROUP, rows)
        if legal_counts:
            rows = [("", inst, ACCENT_DARK, n, _legal_ok(inst, juris))
                    for inst, n in legal_counts.items()]
            rows.sort(key=lambda r: (not r[4], -r[3]))
            self._add_group(LEGAL_GROUP, rows)

        self._add_guilds(result)

    @staticmethod
    def _abbrev(jurisdiction):
        """Short code for a priority jurisdiction, for the left-hand column."""
        j = (jurisdiction or "").lower()
        if "s.41" in j or "s41" in j or "section 41" in j:
            return "S41"
        if "wales" in j or "s7" in j:
            return "S7"
        if "scottish" in j:
            return "SBL"
        if "northern ireland" in j or j.startswith("ni "):
            return "NI"
        if "bap" in j:
            return "BAP"
        return ""

    def _add_group(self, group_name, rows):
        grp = QFrame()
        grp.setStyleSheet("QFrame { background: " + SURFACE + "; border: 1px solid "
                           + BORDER + "; border-radius: 6px; }")
        gl = QVBoxLayout(grp); gl.setContentsMargins(12, 10, 12, 10); gl.setSpacing(6)

        title = QLabel(group_name)
        title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        title.setStyleSheet("color: " + TEXT_HEADING + "; border: none;")
        gl.addWidget(title)

        # Bars are scaled against the largest count in this group, so the
        # lengths mean something. Previously count * 40 capped at 200, which
        # filled the bar for anything over five species.
        peak = max(r[3] for r in rows) or 1

        any_na = False
        for r in rows:
            code, label, colour, count = r[:4]
            applies = r[4] if len(r) > 4 else True
            bar_colour = colour
            if not applies:
                any_na = True
                colour, bar_colour = NA_TEXT, NA_BAR
                label = f"{label} \u2014 not applicable in {self._juris}"
            row = QHBoxLayout(); row.setSpacing(8)

            code_lbl = QLabel(code)
            code_lbl.setFixedWidth(50)
            code_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            code_lbl.setStyleSheet(f"color: {colour}; border: none;")
            row.addWidget(code_lbl)

            desc_lbl = QLabel(label)
            desc_lbl.setFixedWidth(200)
            desc_lbl.setWordWrap(True)
            desc_lbl.setStyleSheet("color: " + (TEXT_SECONDARY if applies else NA_TEXT)
                                   + "; font-size: 11px; border: none;"
                                   + ("" if applies else " font-style: italic;"))
            row.addWidget(desc_lbl)

            bar_container = QFrame()
            bar_container.setFixedHeight(18)
            bar_container.setStyleSheet("background: " + BG + "; border-radius: 3px; border: none;")
            bar = QFrame(bar_container)
            bar.setFixedSize(max(6, int(200 * count / peak)), 18)
            bar.setStyleSheet(f"background: {bar_colour}; border-radius: 3px;")
            row.addWidget(bar_container, 1)

            count_lbl = QLabel(str(count))
            count_lbl.setFixedWidth(30)
            count_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            count_lbl.setStyleSheet(f"color: {colour}; border: none;")
            count_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            row.addWidget(count_lbl)

            gl.addLayout(row)

        if any_na:
            note = QLabel("Greyed designations apply in another jurisdiction. "
                          "They are shown for completeness and do not count "
                          f"towards key species under {self._juris}.")
            note.setWordWrap(True)
            note.setStyleSheet("color: " + NA_TEXT + "; font-size: 10px; "
                               "font-style: italic; border: none;")
            gl.addWidget(note)

        self._layout.insertWidget(self._layout.count(), grp)
        self._widgets.append(grp)

    def _add_guilds(self, result):
        if not (result.larval_guild_counts or result.adult_guild_counts):
            return
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