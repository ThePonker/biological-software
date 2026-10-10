"""The Mapping tab's display bar, under the map header: how the squares are coloured
(Style, Period) and the on-screen legend that says what each colour means (backlog item 4,
review SRCH18: "Period" used to sit with the filters although it only recolours).
"""
from typing import List, Tuple

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QWidget

from ...services.map_square_service import BAND_PRESET_LABELS
from ...themes import theme
from .square_style import STYLES


def swatch_css(colour) -> str:
    """CSS background for a swatch: a colour, or a tuple of colours as hard-edged diagonal
    bands (the map's split square)."""
    if not isinstance(colour, (tuple, list)):
        return str(colour)
    cols = list(colour) or ["#999999"]
    n = len(cols)
    stops = []
    for i, c in enumerate(cols):
        stops += [f"stop:{i / n:.3f} {c}", f"stop:{min(1.0, (i + 1) / n - 0.001):.3f} {c}"]
    return "qlineargradient(x1:0, y1:0, x2:1, y2:1, " + ", ".join(stops) + ")"


class MapDisplayBar(QFrame):
    """Style + Period + legend. style_changed / period_changed carry the new key."""

    style_changed = Signal(str)
    period_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        t = theme()
        self.setObjectName("mapDisplayBar")
        self.setStyleSheet(f"QFrame#mapDisplayBar {{ background-color: {t.get('surface')}; border: none; "
                           f"border-bottom: 1px solid {t.get('border')}; }}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 6, 16, 6)
        lay.setSpacing(8)
        lab_style = f"color: {t.get('text_heading')}; font-size: 12px; border: none;"

        lab = QLabel("Style:")
        lab.setStyleSheet(lab_style)
        lay.addWidget(lab)
        self.style_combo = QComboBox()
        for key, text in STYLES:
            self.style_combo.addItem(text, key)
        self.style_combo.setToolTip("Species richness: squares coloured by the number of "
                                    "different species among the chosen taxa")
        self.style_combo.currentIndexChanged.connect(
            lambda _i: self._on_style())
        lay.addWidget(self.style_combo)

        self.period_label = QLabel("Period:")
        self.period_label.setStyleSheet(lab_style)
        lay.addWidget(self.period_label)
        self.period_combo = QComboBox()
        for key, text in BAND_PRESET_LABELS.items():
            self.period_combo.addItem(text, key)
        self.period_combo.currentIndexChanged.connect(
            lambda _i: self.period_changed.emit(self.period()))
        lay.addWidget(self.period_combo)

        lay.addSpacing(12)
        self.legend_box = QWidget()
        self.legend_box.setStyleSheet("border: none;")
        self.legend_layout = QHBoxLayout(self.legend_box)
        self.legend_layout.setContentsMargins(0, 0, 0, 0)
        self.legend_layout.setSpacing(10)
        lay.addWidget(self.legend_box, 1)
        self._on_style(emit=False)

    def style(self) -> str:
        return self.style_combo.currentData() or "presence"

    def set_style(self, key: str, emit: bool = True):
        """Choose a style by key (the tab does this when a second taxon is added)."""
        i = self.style_combo.findData(key)
        if i < 0 or i == self.style_combo.currentIndex():
            return
        self.style_combo.blockSignals(True)
        self.style_combo.setCurrentIndex(i)
        self.style_combo.blockSignals(False)
        self._on_style(emit=emit)

    def period(self) -> str:
        return self.period_combo.currentData() or "default"

    def _on_style(self, emit: bool = True):
        dated = self.style() == "date"
        self.period_label.setEnabled(dated)
        self.period_combo.setEnabled(dated)
        self.period_combo.setToolTip("" if dated else "Used by the Date classes style")
        if emit:
            self.style_changed.emit(self.style())

    def set_legend(self, legend: List[Tuple[str, str]]):
        """Show [(colour, label)] as swatches; a tuple of colours is a split (overlap) swatch."""
        t = theme()
        while self.legend_layout.count():
            item = self.legend_layout.takeAt(0)
            if item.widget():
                item.widget().hide()          # gone now, not at the next event loop
                item.widget().deleteLater()
        for colour, label in legend:
            sw = QLabel()
            sw.setFixedSize(14, 14)
            sw.setStyleSheet(f"background: {swatch_css(colour)}; border: 1px solid {t.get('border_strong')};")
            self.legend_layout.addWidget(sw)
            tx = QLabel(label)
            tx.setStyleSheet(f"color: {t.get('text_primary')}; font-size: 11px; border: none;")
            self.legend_layout.addWidget(tx)
        self.legend_layout.addStretch()

    def legend_labels(self) -> List[str]:
        """The legend's labels as shown (for tests)."""
        out = []
        for i in range(self.legend_layout.count()):
            w = self.legend_layout.itemAt(i).widget()
            if isinstance(w, QLabel) and w.text():
                out.append(w.text())
        return out
