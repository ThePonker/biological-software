"""Compact banner for Data Entry (B11 / Q54, 10 Nov 2026).

On a short laptop screen (1280x720) the cards above the grid leave about 7 rows. The
"Fold banner" button at the right-hand end of the job's top line (R17: it used to be a small
link inside the species card) folds every card into this one line -- the selected record's
species; the same button then reads "Unfold banner" -- and the choice is remembered in settings. Default: unfolded.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget

from DataEntry import theme
from shared.text_sizes import font_css

SETTING_KEY = "DataEntry/bannerCompact"
STRIP_HEIGHT = 30


def link_button(text: str, tip: str) -> QPushButton:
    """A small flat button in the muted text colour, used for both the Fold and Unfold links."""
    b = QPushButton(text)
    b.setFlat(True)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setToolTip(tip)
    b.setStyleSheet(f"QPushButton {{ color: {theme.SLATE}; font-size: {font_css('caption')}; border: none;"
                    f" background: transparent; padding: 0 4px; }}"
                    f"QPushButton:hover {{ color: {theme.INK}; text-decoration: underline; }}")
    return b


FOLD_TEXT = "\u25B4 Fold banner"
UNFOLD_TEXT = "\u25BE Unfold banner"


def fold_button_text(compact: bool) -> str:
    """The top-line button says what a click does: fold when unfolded, unfold when folded."""
    return UNFOLD_TEXT if compact else FOLD_TEXT


def make_fold_button(info_panel) -> QPushButton:
    """The button for the right-hand end of the job's top line, tied to `info_panel`
    (InfoPanel.set_compact / is_compact / compact_changed)."""
    from DataEntry.theme import button_secondary_qss
    b = QPushButton(fold_button_text(info_panel.is_compact()))
    b.setStyleSheet(button_secondary_qss())
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setToolTip("Fold the banner to one line (more grid rows on a short screen), or unfold it "
                 "again. Remembered.")
    b.clicked.connect(lambda: info_panel.set_compact(not info_panel.is_compact()))
    info_panel.compact_changed.connect(lambda on: b.setText(fold_button_text(on)))
    return b


class CompactStrip(QWidget):
    """The one-line banner: the current record's species. (R18: no Unfold button of its own; the
    job's top line has the one, make_fold_button.)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(theme.card_qss())
        self.setFixedHeight(STRIP_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 0, 8, 0)
        lay.setSpacing(10)
        self.label = QLabel("")
        self.label.setStyleSheet(f"color: {theme.INK}; font-size: {font_css('small')}; font-weight: 600;"
                                 " border: none; background: transparent;")
        self.label.setMinimumWidth(0)
        self.label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        lay.addWidget(self.label, 1)
        self.setMinimumWidth(0)

    def set_text(self, text: str):
        self.label.setText(text)
        self.label.setToolTip(text)
