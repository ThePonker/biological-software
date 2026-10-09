"""
Examen — Overview Tab (redesigned)

Clean summary: hero SQI card, headline numbers, one-line assessment.
Detailed breakdowns moved to Habitats/Assemblages/Species/Conservation tabs.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

try:
    from Examen.presentation import SQI_CAPTION, SQI_TOOLTIP
    from Examen.figure_table import figure_block
except ImportError:  # pragma: no cover
    from presentation import SQI_CAPTION, SQI_TOOLTIP
    from figure_table import figure_block

BG = "#f5f5f4"; SURFACE = "#ffffff"; TEXT_PRIMARY = "#1f2937"
TEXT_SECONDARY = "#6b7280"; TEXT_MUTED = "#9ca3af"; BORDER = "#d1d5db"
MOSS_GREEN = "#4a7c59"; ACCENT = "#7c6c9f"; ACCENT_LIGHT = "#f0edf5"
ACCENT_DARK = "#5a4d78"; RED_STATUS = "#a63d40"; AMBER = "#c2956e"


class OverviewTab(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        # Scrolls once the compartment table makes the content taller than the tab.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.viewport().setAutoFillBackground(False)
        inner = QWidget()
        inner.setAutoFillBackground(False)
        scroll.setWidget(inner)
        outer.addWidget(scroll)
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(16, 20, 16, 16)
        layout.setSpacing(16)

        # Row 1: Hero SQI + key numbers
        top_row = QHBoxLayout()
        top_row.setSpacing(16)

        # Hero SQI card (larger, prominent)
        self.sqi_card = self._hero_card("SQI", "-", "", ACCENT_DARK)
        self.sqi_card.setToolTip(SQI_TOOLTIP)        # what the number means (E8)
        top_row.addWidget(self.sqi_card)

        # Key species card
        self.key_card = self._hero_card("Key species", "-", "", RED_STATUS)
        top_row.addWidget(self.key_card)

        # Total species card
        self.total_card = self._hero_card("Species", "-", "", TEXT_PRIMARY)
        top_row.addWidget(self.total_card)

        layout.addLayout(top_row)

        # The SQI scale, stated where the figure is shown (backlog E8)
        self.sqi_caption = QLabel(SQI_CAPTION)
        self.sqi_caption.setToolTip(SQI_TOOLTIP)
        self.sqi_caption.setStyleSheet("color: " + TEXT_MUTED + "; font-size: 11px;")
        layout.addWidget(self.sqi_caption)

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

        # Row 3b: saproxylic indices (backlog E7) -- shown only when listed species occur
        self.sap_label = QLabel("")
        self.sap_label.setWordWrap(True)
        self.sap_label.setStyleSheet(
            "color: " + TEXT_PRIMARY + "; font-size: 12px; padding: 10px 16px; "
            "background: " + ACCENT_LIGHT + "; border: 1px solid " + BORDER + "; border-radius: 8px;")
        self.sap_label.setVisible(False)
        layout.addWidget(self.sap_label)

        # Row 4: Quick habitat snapshot (top 3 biotopes as simple chips)
        self.habitat_snapshot = QLabel("")
        self.habitat_snapshot.setWordWrap(True)
        self.habitat_snapshot.setStyleSheet(
            "color: " + TEXT_SECONDARY + "; font-size: 12px; padding: 4px 0;")
        layout.addWidget(self.habitat_snapshot)

        # Row 5: compartments (backlog E6) -- only when the records name 2+ of them
        self._compartment_block = None
        self._layout = layout

        layout.addStretch()

    def set_result(self, result, detail=None, visits=0):
        sqi = result.overall_sqi
        sqi_val = str(int(sqi.sqi)) if sqi and sqi.sqi else "-"
        sqi_reliable = sqi and sqi.reliable

        # The second basis (backlog E20): when any score was derived from current
        # status, the workbook gives both SQIs -- so does the screen.
        pub = getattr(result, "overall_sqi_published", None)
        pub_val = (str(int(pub.sqi)) if pub is not None and pub.sqi
                   and getattr(result, "derived_sqs_tvks", None) else "")

        # Hero cards. Below 15 scoring species Pantheon flags the SQI with a red
        # triangle; the figure is still shown, with the flag (backlog E9).
        sub = "Reliable" if sqi_reliable else "\u25b2 fewer than 15 scoring species"
        if pub_val:
            sub += f"\nPantheon scores only: {pub_val}"
        self._update_hero(self.sqi_card, sqi_val, sub,
                          self._sqi_colour(sqi.sqi if sqi else 0))
        hs = self.sqi_card.findChild(QLabel, "hero_sub")
        if hs:
            hs.setStyleSheet("color: " + (TEXT_MUTED if sqi_reliable else RED_STATUS)
                             + "; border: none; background: none;")
        self._update_hero(self.key_card,
                          str(result.key_species_count),
                          f"{result.key_species_pct}% of species recorded",
                          RED_STATUS if result.key_species_count > 0 else TEXT_MUTED)
        # "Analysed": the SQI's divisor -- the workbook's figure (EXA5).
        analysed = getattr(result, "species_analysed", 0) or result.species_in_pantheon
        self._update_hero(self.total_card,
                          str(result.total_species),
                          f"{analysed} analysed",
                          TEXT_PRIMARY)

        # Summary sentence. Built as whole sentences, then joined -- the old
        # version joined clauses with ". ", which split "across 4 visits" into
        # a sentence of its own and doubled the final full stop.
        first = f"{result.total_species} species recorded"
        if visits:
            first += f" across {visits} visit{'s' if visits != 1 else ''}"
        sentences = [
            first,
            f"{result.key_species_count} key species "
            f"({result.key_species_pct}% of species recorded)",
        ]
        sqi_text = f"SQI {sqi_val}"
        if sqi_reliable:
            sqi_text += (f" (reliable; {pub_val} on Pantheon's published scores only)"
                         if pub_val else " (reliable)")
        else:
            sqi_text += " (fewer than 15 scoring species \u2014 treat with caution)"
        sentences.append(sqi_text)

        # No verdict on site importance. The 200/150/125 bands it used had no
        # published source, and Pantheon states that SQI benchmarks have not been
        # produced (docs/39_Research_Notes.md section 1). Removed 8 Oct 2026 by
        # decision (backlog E16): the figures are reported, the author judges.
        self.summary_sentence.setText(". ".join(sentences) + ".")

        # Tier breakdown
        self._update_tier(self.rare_label, str(result.rare_count))
        self._update_tier(self.scarce_label, str(result.scarce_count))
        self._update_tier(self.priority_label, str(result.priority_count))
        scoring = sqi.species_with_sqs if sqi else 0
        held = result.species_in_pantheon
        extra = analysed - held
        self.pantheon_label.setText(
            f"{analysed} species analysed"
            + (f" ({held} held by Pantheon, {extra} scored from current status)"
               if extra > 0 else " (held by Pantheon)")
            + f"  |  {scoring} with SQS scores  |  {visits} visits")
        self.pantheon_label.setToolTip(
            "Species analysed: those Pantheon holds (ecology or a published score, through "
            "the TVK bridge), plus any Pantheon lacks that carry a score derived from current "
            "status. The SQI divides by this figure.")

        # Saproxylic SQI and IEC (backlog E7): figures and thresholds side by side, no verdict
        try:
            try:
                from Examen.saproxylic import assess, band_text
            except ImportError:  # pragma: no cover
                from saproxylic import assess, band_text
            sap = assess(getattr(detail, "species_list", None) or [])
            if sap.n_scored:
                self.sap_label.setText(
                    f"<b>Saproxylic SQI {sap.sqi:g}</b> from {sap.n_scored} listed species"
                    + ("" if sap.reliable else
                       f" <span style='color:{RED_STATUS}'>▲ fewer than {sap.min_species}</span>")
                    + f" &nbsp;|&nbsp; <b>IEC {sap.iec}</b> from {sap.n_iec} species"
                    + f"<br><span style='color:{TEXT_SECONDARY}'>{band_text(sap)}</span>")
                self.sap_label.setVisible(True)
            else:
                self.sap_label.setVisible(False)
        except Exception as e:  # never let the extra figure break the Overview
            print(f"[Examen] saproxylic indices: {e}")
            self.sap_label.setVisible(False)

        self._show_compartments(detail)

        # Habitat snapshot — top biotopes only
        if result.biotope_counts:
            top = sorted(result.biotope_counts.items(), key=lambda x: -x[1])[:4]
            chips = [f"{name} ({count})" for name, count in top]
            self.habitat_snapshot.setText(
                "Dominant biotopes: " + "  \u2022  ".join(chips)
                + "     \u2192 see Habitats tab for full breakdown")
        else:
            self.habitat_snapshot.setText("")

    def _show_compartments(self, detail):
        """The compartment table computed by Examen.compartments (cached on the detail)."""
        if self._compartment_block is not None:
            self._compartment_block.deleteLater()
            self._compartment_block = None
        res = getattr(detail, "compartments", None)
        if res is None or not res.shown:
            return
        try:
            from Examen.compartments import COMBINED
        except ImportError:  # pragma: no cover
            from compartments import COMBINED
        heads, rows, notes = res.table()
        self._compartment_block = figure_block(
            f"Compartments ({len(res.rows)}; threshold {res.threshold_pct:g}% of records)",
            (heads, rows, notes), bold_rows=(COMBINED,), flag_col=len(heads) - 1,
            head_tips={"SQI": SQI_TOOLTIP})
        self._layout.insertWidget(self._layout.count() - 1, self._compartment_block)

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
