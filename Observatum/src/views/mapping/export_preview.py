"""The map export preview (26 Oct 2026): opened by the Mapping tab's Export button. A live,
scaled render of the atlas page on the left; on the right what goes on it (counts, first and
last record, phenology chart, records by decade) and Full extent / Current view. A tick re-renders
the preview after a short pause. "Export PNG..." saves the page at 300 dpi through the tab's
usual file dialog and naming; the ticks are remembered (QSettings "mapping/export/<name>")."""
from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QGroupBox, QHBoxLayout, QLabel,
                               QPushButton, QSizePolicy, QVBoxLayout)

from .atlas_export import EXPORT_DEFAULTS, EXPORT_OPTIONS

PREVIEW_DPI = 100
DEBOUNCE_MS = 250


def saved_options() -> dict:
    """The remembered ticks (defaults where nothing is saved)."""
    s = QSettings()
    out = {}
    for key, _t in EXPORT_OPTIONS:
        v = s.value(f"mapping/export/{key}", EXPORT_DEFAULTS[key])
        out[key] = v if isinstance(v, bool) else str(v).lower() == "true"
    return out


class ExportPreviewDialog(QDialog):
    def __init__(self, tab, parent=None):
        super().__init__(parent)
        self.tab = tab
        self.setWindowTitle("Map export preview")
        self.resize(1020, 780)
        self._pix = QPixmap()
        self.preview = QLabel("Rendering…")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(360, 480)
        self.preview.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)

        side = QVBoxLayout()
        box = QGroupBox("On the page")
        bl = QVBoxLayout(box)
        saved = saved_options()
        self.checks = {}
        for key, text in EXPORT_OPTIONS:
            c = QCheckBox(text)
            c.setChecked(saved[key])
            c.toggled.connect(self._changed)
            bl.addWidget(c)
            self.checks[key] = c
        side.addWidget(box)
        side.addWidget(QLabel("Extent"))
        self.extent = QComboBox()
        combo = tab.toolbar.extent_combo
        for i in range(combo.count()):
            self.extent.addItem(combo.itemText(i), combo.itemData(i))
        i = self.extent.findData(tab.toolbar.export_extent())
        self.extent.setCurrentIndex(max(i, 0))
        self.extent.currentIndexChanged.connect(self._changed)
        side.addWidget(self.extent)
        side.addStretch(1)
        self.export_btn = QPushButton("Export PNG…")
        self.export_btn.setDefault(True)
        self.export_btn.clicked.connect(self._export)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        row = QHBoxLayout()
        row.addWidget(self.export_btn)
        row.addWidget(self.cancel_btn)
        side.addLayout(row)

        lay = QHBoxLayout(self)
        lay.addWidget(self.preview, 1)
        lay.addLayout(side)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(DEBOUNCE_MS)
        self._timer.timeout.connect(self.refresh_now)
        self._timer.start()

    def options(self) -> dict:
        return {k: c.isChecked() for k, c in self.checks.items()}

    def extent_choice(self) -> str:
        return self.extent.currentData() or "full"

    def _changed(self, *_a):
        self._remember()
        self._timer.start()             # debounced: several ticks in a row render once

    def _remember(self):
        s = QSettings()
        for k, v in self.options().items():
            s.setValue(f"mapping/export/{k}", v)

    def refresh_now(self):
        """Render the page (at preview resolution) and show it."""
        self._timer.stop()
        img = self.tab.render_atlas(self.extent_choice(), self.options(), dpi=PREVIEW_DPI)
        self._pix = QPixmap.fromImage(img)
        self._fit()

    def _fit(self):
        if not self._pix.isNull():
            self.preview.setPixmap(self._pix.scaled(
                self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._fit()

    def _export(self):
        self._remember()
        if self.tab._export_png(self.extent_choice(), self.options(), parent=self):
            self.accept()
