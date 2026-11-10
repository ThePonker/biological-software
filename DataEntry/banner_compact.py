"""Compact banner for Data Entry (B11 / Q54, 10 Nov 2026).

On a short laptop screen (1280x720) the cards above the grid leave about 7 rows. The
"Fold" link on the readout card folds every card into this one line -- an "Unfold" button and
the selected record's species -- and the choice is remembered in settings. Default: unfolded.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget

from DataEntry import theme

SETTING_KEY = "DataEntry/bannerCompact"
STRIP_HEIGHT = 30


def link_button(text: str, tip: str) -> QPushButton:
    """A small flat button in the muted text colour, used for both the Fold and Unfold links."""
    b = QPushButton(text)
    b.setFlat(True)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setToolTip(tip)
    b.setStyleSheet(f"QPushButton {{ color: {theme.SLATE}; font-size: 11px; border: none;"
                    f" background: transparent; padding: 0 4px; }}"
                    f"QPushButton:hover {{ color: {theme.INK}; text-decoration: underline; }}")
    return b


class CompactStrip(QWidget):
    """The one-line banner: Unfold button + the current record's species."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(theme.card_qss())
        self.setFixedHeight(STRIP_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 0, 8, 0)
        lay.setSpacing(10)
        self.unfold_btn = link_button("▾ Unfold banner",
                                      "Show the cards again (species, maps, entry controls, legend).")
        lay.addWidget(self.unfold_btn)
        self.label = QLabel("")
        self.label.setStyleSheet(f"color: {theme.INK}; font-size: 12px; font-weight: 600;"
                                 " border: none; background: transparent;")
        self.label.setMinimumWidth(0)
        self.label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        lay.addWidget(self.label, 1)
        self.setMinimumWidth(0)

    def set_text(self, text: str):
        self.label.setText(text)
        self.label.setToolTip(text)
