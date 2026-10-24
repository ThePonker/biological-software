"""Layers > Colours...: one colour per background layer switch that has one to choose (all but
Relief, which is grey), remembered (QSettings mapping/layers/<key>/colour; layers.py). The map,
the atlas pages and the batch maps all draw with them. "Reset colours" goes back to the theme's."""
from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QColorDialog, QDialog, QGridLayout, QHBoxLayout, QLabel,
                               QPushButton, QVBoxLayout)

from shared.maps import layers

from ...themes import theme


class LayerColoursDialog(QDialog):
    """A row per Layers switch: its name and a swatch button that opens the colour chooser."""

    colours_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        t = theme()
        self.setWindowTitle("Layer colours")
        lay = QVBoxLayout(self)
        note = QLabel("Colours of the background layers, on the map, the atlas PNG and the "
                      "batch maps. Remembered.")
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {t.get('text_primary')}; font-size: 12px;")
        lay.addWidget(note)
        grid = QGridLayout()
        self.swatches = {}
        for i, tg in enumerate(t for t in layers.TOGGLES if t.colour):
            lab = QLabel(tg.label)
            lab.setStyleSheet(f"color: {t.get('text_heading')}; font-size: 12px;")
            grid.addWidget(lab, i, 0)
            btn = QPushButton()
            btn.setFixedSize(56, 22)
            btn.setToolTip(f"Choose the colour of {tg.label.lower()}")
            btn.setAccessibleName(f"{tg.label} colour")
            btn.clicked.connect(lambda _c=False, key=tg.key: self.choose(key))
            grid.addWidget(btn, i, 1)
            self.swatches[tg.key] = btn
        lay.addLayout(grid)
        row = QHBoxLayout()
        self.reset_button = QPushButton("Reset colours")
        self.reset_button.setStyleSheet(t.button_cancel_style())
        self.reset_button.clicked.connect(self.reset)
        row.addWidget(self.reset_button)
        row.addStretch()
        close = QPushButton("Close")
        close.setStyleSheet(t.button_cancel_style())
        close.clicked.connect(self.accept)
        row.addWidget(close)
        lay.addLayout(row)
        self.refresh()

    def colour(self, key: str) -> QColor:
        """The colour in force for a switch: the remembered one, else the default."""
        return layers.saved_colour(key) or layers.default_colour(key)

    def refresh(self):
        t = theme()
        for key, btn in self.swatches.items():
            btn.setStyleSheet(f"background-color: {self.colour(key).name()}; "
                              f"border: 1px solid {t.get('border_strong')}; border-radius: 3px;")

    def choose(self, key: str):
        c = QColorDialog.getColor(self.colour(key), self, "Choose a colour")
        if c.isValid():
            self.set_colour(key, c)

    def set_colour(self, key: str, colour):
        layers.set_colour(key, colour)
        self.refresh()
        self.colours_changed.emit()

    def reset(self):
        layers.reset_colours()
        self.refresh()
        self.colours_changed.emit()
