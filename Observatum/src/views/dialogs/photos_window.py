"""
Photos window -- every photo of a species, this record's photos first (photos B3).

A separate, non-modal window opened from the record detail dialog.
- This record's photos come first, each with a "THIS RECORD" band painted on the thumbnail.
- Then, for a specimen, the other specimen photos ('Specimen' folder) before the field photos;
  for an observation, field photos before specimen photos.
- Every thumbnail has its file name underneath (the date is in the name).
- Double-click a photo: it opens large in the photo viewer (arrow keys step through).
- "Link to this record" / "Not this record" change which photos belong to the record (only
  the link is changed; the photo file is never touched).
Thumbnails are loaded a few at a time on a timer, so big JPEGs never block the window.
"""
import os
import sqlite3

from PySide6.QtCore import QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QIcon, QImageReader, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QListView, QListWidget, QListWidgetItem,
    QPushButton, QStackedLayout, QVBoxLayout, QWidget,
)

from shared import photo_files
from shared import photo_links

from ...core.config import ButtonColors
from ...themes import theme

THUMB = 180
BATCH = 4          # thumbnails per timer tick: keeps the window responsive
BAND = "THIS RECORD"
EMPTY_TEXT = "No photos of this species in the photo library yet."


def _is_specimen_photo(stored: str) -> bool:
    return f"/{photo_files.SPECIMEN.casefold()}/" in stored.casefold()


class PhotosWindow(QDialog):
    """Non-modal window listing a species' photos (record photos first)."""

    links_changed = Signal(int)          # how many photos the record now has

    def __init__(self, species_name: str, record_paths: list, parent=None, accent: str = None,
                 record_kind: str = None, record_id: int = None, db_path: str = None):
        super().__init__(parent)
        self.setModal(False)
        self.species_name = species_name
        self.record_kind = record_kind               # 'specimen' / 'observation' / None
        self.record_id = record_id
        self.db_path = db_path
        self._accent = accent or theme().get('primary')
        self.setWindowTitle(f"Photos — {species_name}")
        self.resize(940, 660)
        photo_files.refresh()          # folders added by hand since the last look show up
        self._species = photo_files.species_photos(species_name)
        self._build_ui()
        self._timer = QTimer(self)
        self._timer.setInterval(0)
        self._timer.timeout.connect(self._load_batch)
        self._set_paths(record_paths)

    # -- order ----------------------------------------------------------------------------
    def _set_paths(self, record_paths):
        mine = list(dict.fromkeys(record_paths or []))
        rest = [p for p in self._species if p not in set(mine)]
        specimen_first = self.record_kind == 'specimen'
        rest.sort(key=lambda p: (_is_specimen_photo(p) != specimen_first, p.casefold()))
        self.paths = mine + rest
        self.record_count = len(mine)
        self._abs = [photo_files.absolute(p) for p in self.paths]
        self._next = 0
        text = f"{len(self.paths)} photos of {self.species_name}"
        if self.record_count:
            text += f" · {self.record_count} of this record (marked {BAND})"
        self.header.setText(text)
        self.list.clear()
        self._fill_items()
        self._stack.setCurrentWidget(self.list if self.paths else self.empty_label)
        self.folder_btn.setEnabled(bool(self.paths))
        self._update_link_buttons()
        if self.paths:
            self._timer.start()

    # -- layout ---------------------------------------------------------------------------
    def _build_ui(self):
        t = theme()
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        self.header = QLabel()
        self.header.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {t.get('text_primary')};")
        root.addWidget(self.header)

        self.list = QListWidget()
        self.list.setViewMode(QListView.ViewMode.IconMode)
        self.list.setIconSize(QSize(THUMB, THUMB))
        self.list.setGridSize(QSize(THUMB + 24, THUMB + 44))
        self.list.setResizeMode(QListView.ResizeMode.Adjust)
        self.list.setWrapping(True)
        self.list.setMovement(QListView.Movement.Static)
        self.list.setWordWrap(False)
        self.list.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.list.setStyleSheet(f"QListWidget {{ color: {t.get('text_primary')}; font-size: 11px; }}")
        self.list.itemDoubleClicked.connect(self._open_item)
        self.list.currentItemChanged.connect(lambda *_: self._update_link_buttons())

        self.empty_label = QLabel(EMPTY_TEXT)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet(f"font-size: 13px; color: {t.get('text_secondary')};")

        holder = QWidget()
        self._stack = QStackedLayout(holder)
        self._stack.addWidget(self.list)
        self._stack.addWidget(self.empty_label)
        root.addWidget(holder, 1)

        row = QHBoxLayout()
        self.folder_btn = self._button("Open folder", self._accent, self._open_folder)
        row.addWidget(self.folder_btn)
        self.link_btn = self._button("Link to this record", self._accent, self._link)
        self.unlink_btn = self._button("Not this record", self._accent, self._unlink)
        can_link = bool(self.record_kind and self.record_id is not None and self.db_path)
        for b in (self.link_btn, self.unlink_btn):
            b.setVisible(can_link)
            row.addWidget(b)
        row.addStretch()
        self.close_btn = self._button("Close", ButtonColors.SECONDARY, self.close)
        row.addWidget(self.close_btn)
        root.addLayout(row)

    def _button(self, text, colour, slot):
        t = theme()
        b = QPushButton(text)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent; color: {colour};
                border: 1px solid {colour}; border-radius: {t.get('radius_md')};
                padding: 8px 20px; font-size: 13px; font-weight: 500;
            }}
            QPushButton:hover {{ background-color: {t.get('surface_alt')}; }}
            QPushButton:disabled {{ color: {t.get('text_secondary')}; border-color: {t.get('border')}; }}
        """)
        b.clicked.connect(slot)
        return b

    # -- items ----------------------------------------------------------------------------
    def _fill_items(self):
        for i, (stored, path) in enumerate(zip(self.paths, self._abs)):
            name = os.path.basename(stored)
            if not path.is_file():
                name = f"file not found · {name}"
            item = QListWidgetItem(name)
            item.setToolTip(("This record's photo\n" if i < self.record_count else "") + stored)
            item.setData(Qt.ItemDataRole.UserRole, i)
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
            self.list.addItem(item)

    def _thumb(self, img, mine: bool) -> QPixmap:
        """The photo on a square canvas; a record photo gets a band and a frame in the accent."""
        canvas = QPixmap(THUMB, THUMB)
        canvas.fill(Qt.GlobalColor.transparent)
        p = QPainter(canvas)
        pix = QPixmap.fromImage(img)
        p.drawPixmap((THUMB - pix.width()) // 2, (THUMB - pix.height()) // 2, pix)
        if mine:
            accent = QColor(self._accent)
            p.setPen(QPen(accent, 6))
            p.drawRect(3, 3, THUMB - 6, THUMB - 6)
            p.fillRect(0, 0, THUMB, 24, accent)
            p.setPen(QColor(theme().get('surface')))
            f = QFont()
            f.setBold(True)
            f.setPointSize(9)
            p.setFont(f)
            p.drawText(0, 0, THUMB, 24, Qt.AlignmentFlag.AlignCenter, BAND)
        p.end()
        return canvas

    def _load_batch(self):
        end = min(self._next + BATCH, len(self.paths))
        for i in range(self._next, end):
            path = self._abs[i]
            if not path.is_file():
                continue
            reader = QImageReader(str(path))
            reader.setAutoTransform(True)
            size = reader.size()
            if size.isValid():
                reader.setScaledSize(size.scaled(THUMB, THUMB, Qt.AspectRatioMode.KeepAspectRatio))
            img = reader.read()
            if not img.isNull():
                self.list.item(i).setIcon(QIcon(self._thumb(img, i < self.record_count)))
        self._next = end
        if end >= len(self.paths):
            self._timer.stop()

    # -- linking --------------------------------------------------------------------------
    def _selected(self):
        item = self.list.currentItem()
        return None if item is None else item.data(Qt.ItemDataRole.UserRole)

    def _update_link_buttons(self):
        i = self._selected()
        self.link_btn.setEnabled(i is not None and i >= self.record_count)
        self.unlink_btn.setEnabled(i is not None and i < self.record_count)

    def _ids(self):
        return ((self.record_id, None) if self.record_kind == 'specimen' else (None, self.record_id))

    def _change_link(self, add: bool):
        i = self._selected()
        if i is None or not self.db_path:
            return
        stored = self.paths[i]
        sid, oid = self._ids()
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                photo_links.ensure_schema(conn)
                if add:
                    photo_links.add_link(conn, stored, specimen_id=sid, observation_id=oid,
                                         method=photo_links.BY_HAND)
                else:
                    photo_links.remove_link(conn, stored, specimen_id=sid, observation_id=oid)
            mine = (photo_links.photos_for_specimen(conn, self.record_id) if sid is not None
                    else photo_links.photos_for_observation(conn, self.record_id))
        finally:
            conn.close()
        self._set_paths(mine)
        if stored in self.paths:
            self.list.setCurrentRow(self.paths.index(stored))
        self.links_changed.emit(len(mine))

    def _link(self):
        self._change_link(True)

    def _unlink(self):
        self._change_link(False)

    # -- actions --------------------------------------------------------------------------
    def _open_item(self, item):
        """Double-click: the photo large in Observatum's viewer (14 Oct 2026), stepping through
        the photos that are there; "Open in Windows" in the viewer opens the system viewer."""
        i = item.data(Qt.ItemDataRole.UserRole)
        if not self._abs[i].is_file():
            return
        from .photo_viewer import PhotoViewer
        there = [j for j, p in enumerate(self._abs) if p.is_file()]
        self._viewer = PhotoViewer([self._abs[j] for j in there], there.index(i), parent=self)
        self._viewer.show()

    def _open_folder(self):
        if not self.paths:
            return
        i = self._selected()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._abs[i or 0].parent)))

    def closeEvent(self, event):
        self._timer.stop()
        super().closeEvent(event)
