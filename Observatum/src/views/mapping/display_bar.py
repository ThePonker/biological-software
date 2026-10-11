"""The Mapping tab's display bar, under the map header: how the squares are coloured
(Style, Period) and the on-screen legend that says what each colour means (backlog item 4,
review SRCH18: "Period" used to sit with the filters although it only recolours).

R9-5 (11 Oct 2026): a "VC labels" tick box (on by default, remembered) for the vice-county
numbers (national scale) / names (zoomed in) drawn on the map and on its atlas page.
R4: a "VC boundaries" tick box beside it (on by default, remembered) for the boundary lines,
and "Districts (modern)" (off by default, remembered) for gb_outline.json's district borders.
"""
from typing import List, Tuple

from PySide6.QtCore import QSettings, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QSizePolicy,
                               QWidget)

from ...services.map_square_service import BAND_PRESET_LABELS
from ...themes import theme
from .square_style import STYLES

VC_LABELS_SETTING = "mapping/vc_labels"      # R9-5: VC numbers / names on the map (default on)
VC_BOUNDS_SETTING = "mapping/vc_boundaries"  # R4: VC boundary lines on the map (default on)
DISTRICTS_SETTING = "mapping/districts"      # R4: modern district lines (default off)


def _saved(key: str, default: bool = True) -> bool:
    try:
        return QSettings().value(key, default, type=bool)
    except Exception:
        return default


def saved_vc_labels() -> bool:
    return _saved(VC_LABELS_SETTING)


def saved_vc_boundaries() -> bool:
    return _saved(VC_BOUNDS_SETTING)


def saved_districts() -> bool:
    return _saved(DISTRICTS_SETTING, False)


def _save(key: str, on: bool):
    try:
        QSettings().setValue(key, bool(on))
    except Exception as e:
        print(f"[MapDisplayBar] {key} not saved: {e}")


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
    vc_labels_changed = Signal(bool)
    vc_boundaries_changed = Signal(bool)
    districts_changed = Signal(bool)

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

        self.vc_labels_check = QCheckBox("VC labels")
        self.vc_labels_check.setStyleSheet(lab_style)
        self.vc_labels_check.setToolTip(
            "Vice-county numbers on the whole-country map, names when zoomed in or in County "
            "view; printed on the atlas PNG too. Remembered.")
        self.vc_labels_check.setChecked(saved_vc_labels())
        self.vc_labels_check.toggled.connect(self._on_vc_labels)
        lay.addWidget(self.vc_labels_check)

        self.vc_bounds_check = QCheckBox("VC boundaries")
        self.vc_bounds_check.setStyleSheet(lab_style)
        self.vc_bounds_check.setToolTip(
            "A line round every vice-county, on the map and on the atlas PNG. Remembered.")
        self.vc_bounds_check.setChecked(saved_vc_boundaries())
        self.vc_bounds_check.toggled.connect(self._on_vc_bounds)
        lay.addWidget(self.vc_bounds_check)

        self.districts_check = QCheckBox("Districts (modern)")
        self.districts_check.setStyleSheet(lab_style)
        self.districts_check.setToolTip(
            "Modern local-authority district borders (ONS 2013), as faint lines. Remembered.")
        self.districts_check.setChecked(saved_districts())
        self.districts_check.toggled.connect(self._on_districts)
        lay.addWidget(self.districts_check)

        lay.addSpacing(12)
        self.legend_box = QWidget()
        self.legend_box.setStyleSheet("border: none;")
        # L30: a long legend (many taxa) is cut at the right, with the whole of it in the
        # tooltip; it no longer widens the map side (which made the layout jump in full screen)
        self.legend_box.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
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

    def vc_labels(self) -> bool:
        return self.vc_labels_check.isChecked()

    def _on_vc_labels(self, on: bool):
        _save(VC_LABELS_SETTING, on)
        self.vc_labels_changed.emit(bool(on))

    def vc_boundaries(self) -> bool:
        return self.vc_bounds_check.isChecked()

    def _on_vc_bounds(self, on: bool):
        _save(VC_BOUNDS_SETTING, on)
        self.vc_boundaries_changed.emit(bool(on))

    def attach_map(self, m):
        """Wire the three map switches to the map (GridMap) and give it their saved state."""
        self.vc_labels_changed.connect(m.set_vc_labels)
        m.set_vc_labels(self.vc_labels())
        self.vc_boundaries_changed.connect(m.set_vc_boundaries)
        m.set_vc_boundaries(self.vc_boundaries())
        self.districts_changed.connect(m.set_districts)
        m.set_districts(self.districts())
        self.set_districts_available(m.has_districts())

    def districts(self) -> bool:
        return self.districts_check.isChecked()

    def set_districts_available(self, ok: bool):
        """Greyed out when the map has no district file (data/maps/gb_outline.json)."""
        self.districts_check.setEnabled(bool(ok))
        if not ok:
            self.districts_check.setToolTip("Needs data/maps/gb_outline.json (not found).")

    def _on_districts(self, on: bool):
        _save(DISTRICTS_SETTING, on)
        self.districts_changed.emit(bool(on))

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
        self.legend_box.setToolTip("\n".join(label for _c, label in legend))

    def legend_labels(self) -> List[str]:
        """The legend's labels as shown (for tests)."""
        out = []
        for i in range(self.legend_layout.count()):
            w = self.legend_layout.itemAt(i).widget()
            if isinstance(w, QLabel) and w.text():
                out.append(w.text())
        return out
