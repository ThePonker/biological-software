"""Photo viewer (14 Oct 2026) -- a photo large inside Observatum, opened from the Photos window.

Fits the window by default; "Actual size" shows it 1:1 with scroll bars. Left / right arrow keys
(or Previous / Next) step through the Photos window's photos; "Open in Windows" hands the file
to the system viewer as before. Read only: nothing is moved or changed.
"""
import os

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QImageReader, QPixmap
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout,
)

from ...themes import theme


class PhotoViewer(QDialog):
    def __init__(self, paths, start: int = 0, parent=None):
        super().__init__(parent)
        self.setModal(False)
        self.paths = [p for p in paths]
        self.index = max(0, min(start, len(self.paths) - 1)) if self.paths else 0
        self.fit = True
        self._pix = QPixmap()
        self.resize(1100, 800)
        t = theme()
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12)
        self.title = QLabel()
        self.title.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {t.get('text_primary')};")
        v.addWidget(self.title)
        self.area = QScrollArea()
        self.area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.area.setStyleSheet(f"QScrollArea {{ background: {t.get('surface_alt')}; border: none; }}")
        self.image = QLabel()
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.area.setWidget(self.image)
        v.addWidget(self.area, 1)
        row = QHBoxLayout()
        self.prev_btn = QPushButton("← Previous")
        self.next_btn = QPushButton("Next →")
        self.size_btn = QPushButton("Actual size")
        self.open_btn = QPushButton("Open in Windows")
        close = QPushButton("Close")
        for b, slot in ((self.prev_btn, lambda: self.step(-1)), (self.next_btn, lambda: self.step(1)),
                        (self.size_btn, self.toggle_size), (self.open_btn, self.open_external),
                        (close, self.close)):
            b.setStyleSheet(t.button_secondary_style() if b is not close else t.button_cancel_style())
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)          # arrows always step photos
            b.clicked.connect(slot)
        row.addWidget(self.prev_btn)
        row.addWidget(self.next_btn)
        row.addStretch()
        row.addWidget(self.size_btn)
        row.addWidget(self.open_btn)
        row.addWidget(close)
        v.addLayout(row)
        self.show_photo()

    # -- showing ------------------------------------------------------------------------------
    def show_photo(self):
        if not self.paths:
            self.title.setText("No photo")
            return
        path = str(self.paths[self.index])
        rd = QImageReader(path)
        rd.setAutoTransform(True)              # phone photos the right way up
        img = rd.read()
        self._pix = QPixmap.fromImage(img) if not img.isNull() else QPixmap()
        name = os.path.basename(path)
        self.title.setText(f"{name}    ({self.index + 1} of {len(self.paths)})"
                           + ("" if not self._pix.isNull() else "  -- cannot be shown"))
        self.prev_btn.setEnabled(self.index > 0)
        self.next_btn.setEnabled(self.index < len(self.paths) - 1)
        self._render()

    def _render(self):
        if self._pix.isNull():
            self.image.clear()
            return
        if self.fit:
            self.area.setWidgetResizable(True)
            vp = self.area.viewport().size()
            self.image.setPixmap(self._pix.scaled(vp, Qt.AspectRatioMode.KeepAspectRatio,
                                                  Qt.TransformationMode.SmoothTransformation))
        else:
            self.area.setWidgetResizable(False)
            self.image.setPixmap(self._pix)
            self.image.resize(self._pix.size())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.fit:
            self._render()

    # -- actions ------------------------------------------------------------------------------
    def step(self, d: int):
        j = self.index + d
        if 0 <= j < len(self.paths):
            self.index = j
            self.show_photo()

    def toggle_size(self):
        self.fit = not self.fit
        self.size_btn.setText("Fit to window" if not self.fit else "Actual size")
        self._render()

    def open_external(self):
        if self.paths:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.paths[self.index])))

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Up):
            self.step(-1)
        elif event.key() in (Qt.Key.Key_Right, Qt.Key.Key_Down, Qt.Key.Key_Space):
            self.step(1)
        else:
            super().keyPressEvent(event)
