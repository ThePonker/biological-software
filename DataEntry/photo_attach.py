"""photo_attach -- attach bench photos from the capture folder to a Data Entry row.

The photos are MOVED (never copied) into the holding folder Media/Photos/_Bench and renamed
'<Genus species> [sex] [view] [D.roman.YY] [n]'; a link to the staging row is stored. At commit
they go to the species' Specimen folder and become the record's (shared/bench_photos.py).
"""
from __future__ import annotations

import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QSettings, QSize
from PySide6.QtGui import QIcon, QImageReader, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QFileDialog, QHBoxLayout, QInputDialog, QLabel,
    QListView, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout,
)

from DataEntry import date_utils, theme
from shared import bench_photos, photo_files, photo_links
from shared.photo_names import IMAGE_EXTS, specimen_photo_stem

KEY_FOLDER = "DataEntry/captureFolder"
KEY_VIEWS = "DataEntry/photoViews"
DEFAULT_VIEWS = ["head", "gen"]
THUMB = 160
NO_VIEW = "(none)"
ADD_VIEW = "Add view…"


def _settings() -> QSettings:
    return QSettings("Flauna", "Observatum")


def capture_folder() -> Path:
    v = _settings().value(KEY_FOLDER, "", type=str)
    return Path(v) if v else Path.home() / "Desktop" / "image"


def photo_views() -> list:
    v = _settings().value(KEY_VIEWS, None)
    if v is None or v == "":
        return list(DEFAULT_VIEWS)
    return [str(x) for x in ([v] if isinstance(v, str) else v)]


def name_for(row: dict, view: str = "") -> str:
    """The stem a photo of this row gets (no number, no extension). The date part is used only
    when the row's date is a full day."""
    date = row.get("date")
    iso = (date_utils.start_iso(date) or "") if date_utils.date_type(date) == "D" else ""
    species = photo_files.folder_name(row.get("species_name") or "")   # no subgenus brackets
    return specimen_photo_stem(species, row.get("sex") or "", view or "", iso)


class PhotoAttachDialog(QDialog):
    def __init__(self, conn, row: dict, parent=None):
        super().__init__(parent)
        self._conn, self._row = conn, row
        self.attached = 0
        self.setWindowTitle("Attach photos")
        self.resize(1100, 820)            # larger by default (14 Oct 2026); then the size Wil leaves it
        v = QVBoxLayout(self)

        bits = [row.get("species_name") or "no species", row.get("sex") or "",
                date_utils.to_display(row.get("date"))]
        self._summary = QLabel(" · ".join(b for b in bits if b))
        self._summary.setStyleSheet(f"color: {theme.INK}; font-size: 14px; font-weight: 600;")
        v.addWidget(self._summary)

        top = QHBoxLayout()
        self._folder_lbl = QLabel()
        self._folder_lbl.setStyleSheet(f"color: {theme.MUTED}; font-size: 12px;")
        self._folder_lbl.setWordWrap(True)
        top.addWidget(self._folder_lbl, 1)
        self._change_btn = QPushButton("Change folder…")
        self._change_btn.setStyleSheet(theme.button_secondary_qss(compact=True))
        self._change_btn.clicked.connect(self._change_folder)
        top.addWidget(self._change_btn)
        v.addLayout(top)

        self._msg = QLabel()
        self._msg.setStyleSheet(f"color: {theme.MUTED}; font-size: 12px;")
        self._msg.setWordWrap(True)
        v.addWidget(self._msg)

        self.list = QListWidget()
        self.list.setViewMode(QListView.ViewMode.IconMode)
        self.list.setResizeMode(QListView.ResizeMode.Adjust)
        self.list.setMovement(QListView.Movement.Static)
        self.list.setIconSize(QSize(THUMB, THUMB))
        self.list.setGridSize(QSize(THUMB + 24, THUMB + 40))
        self.list.setWordWrap(True)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list.itemSelectionChanged.connect(self._update_preview)
        v.addWidget(self.list, 1)

        vrow = QHBoxLayout()
        vrow.addWidget(QLabel("View:"))
        self.view_box = QComboBox()
        self.view_box.activated.connect(self._view_activated)
        vrow.addWidget(self.view_box)
        vrow.addStretch(1)
        v.addLayout(vrow)
        self._fill_views()

        self._preview = QLabel()
        self._preview.setStyleSheet(f"color: {theme.INK}; font-size: 12px;")
        v.addWidget(self._preview)

        # the row's own photos: a wrong one (or wrong view) goes back to the capture folder,
        # to attach again (14 Oct 2026)
        self._row_lbl = QLabel()
        self._row_lbl.setStyleSheet(f"color: {theme.INK}; font-size: 12px; font-weight: 600;")
        v.addWidget(self._row_lbl)
        self.row_list = QListWidget()
        self.row_list.setViewMode(QListView.ViewMode.IconMode)
        self.row_list.setMovement(QListView.Movement.Static)
        self.row_list.setIconSize(QSize(90, 90))
        self.row_list.setGridSize(QSize(170, 120))
        self.row_list.setFixedHeight(140)
        self.row_list.setWordWrap(True)
        self.row_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.row_list.itemSelectionChanged.connect(
            lambda: self.detach_btn.setEnabled(bool(self.row_list.selectedItems())))
        v.addWidget(self.row_list)
        drow = QHBoxLayout()
        drow.addStretch(1)
        self.detach_btn = QPushButton("Take off this row (back to capture folder)")
        self.detach_btn.setStyleSheet(theme.button_secondary_qss(compact=True))
        self.detach_btn.setEnabled(False)
        self.detach_btn.clicked.connect(self._detach)
        drow.addWidget(self.detach_btn)
        v.addLayout(drow)

        btns = QHBoxLayout()
        btns.addStretch(1)
        self.attach_btn = QPushButton("Attach")
        self.attach_btn.setStyleSheet(theme.button_primary_qss(compact=True))
        self.attach_btn.clicked.connect(self._attach)
        btns.addWidget(self.attach_btn)
        close = QPushButton("Close")
        close.setStyleSheet(theme.button_secondary_qss(compact=True))
        close.clicked.connect(self.accept)
        btns.addWidget(close)
        v.addLayout(btns)

        self._files: dict = {}
        self._load()

    # -- views ------------------------------------------------------------------------------
    def _fill_views(self, select: str = "") -> None:
        self.view_box.blockSignals(True)
        self.view_box.clear()
        self.view_box.addItem(NO_VIEW)
        self.view_box.addItems(photo_views())
        self.view_box.addItem(ADD_VIEW)
        i = self.view_box.findText(select) if select else 0
        self.view_box.setCurrentIndex(max(i, 0))
        self.view_box.blockSignals(False)

    def _view_activated(self, _i: int) -> None:
        if self.view_box.currentText() == ADD_VIEW:
            word, ok = QInputDialog.getText(self, "Add view", "View (one word, e.g. head):")
            word = word.strip().lower() if ok else ""
            if word:
                views = photo_views()
                if word not in views:
                    views.append(word)
                    _settings().setValue(KEY_VIEWS, views)
            self._fill_views(word)
        self._update_preview()

    def current_view(self) -> str:
        t = self.view_box.currentText()
        return "" if t in (NO_VIEW, ADD_VIEW) else t

    # -- the capture folder -----------------------------------------------------------------
    def _change_folder(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Capture folder", str(capture_folder()))
        if d:
            _settings().setValue(KEY_FOLDER, d)
            self._load()

    def _load(self, note: str = "") -> None:
        folder = capture_folder()
        self._folder_lbl.setText(f"Capture folder: {folder}")
        self.list.clear()
        self._files = {}
        problem = ""
        if not folder.is_dir():
            problem = f"The capture folder {folder} does not exist."
        else:
            found = []
            for f in folder.iterdir():
                if f.is_file() and f.suffix.lower() in IMAGE_EXTS:
                    try:
                        found.append((f.stat().st_mtime, f))
                    except OSError:
                        pass
            found.sort(key=lambda t: t[0], reverse=True)
            for mtime, f in found:
                when = datetime.datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M:%S")
                it = QListWidgetItem(QIcon(self._thumb(f)), f.name)
                it.setToolTip(f"{f.name}\n{when}")
                it.setData(Qt.ItemDataRole.UserRole, str(f))
                self.list.addItem(it)
                self._files[str(f)] = mtime
            if not found:
                problem = f"No photos in {folder}."
        self._msg.setText(note or problem)
        self.attach_btn.setEnabled(not problem)
        self._update_preview()
        self._load_row()

    def _load_row(self) -> None:
        self.row_list.clear()
        try:
            mine = photo_links.photos_for_staging(self._conn, self._row["id"])
        except Exception:
            mine = []
        self._row_lbl.setText(f"On this row: {len(mine)} photo{'s' if len(mine) != 1 else ''}"
                              if mine else "On this row: no photos yet")
        for p in mine:
            f = photo_files.absolute(p)
            it = QListWidgetItem(QIcon(self._thumb(f)) if f.is_file() else QIcon(), f.name)
            it.setToolTip(p)
            it.setData(Qt.ItemDataRole.UserRole, p)
            self.row_list.addItem(it)
        self.row_list.setVisible(bool(mine))
        self.detach_btn.setVisible(bool(mine))
        self.detach_btn.setEnabled(bool(self.row_list.selectedItems()))

    def _detach(self) -> None:
        done, failed = 0, []
        for it in self.row_list.selectedItems():
            p = it.data(Qt.ItemDataRole.UserRole)
            try:
                bench_photos.detach(self._conn, self._row["id"], p, capture_folder())
                done += 1
            except Exception as e:
                failed.append(f"{Path(p).name}: {e}")
        if failed:
            QMessageBox.warning(self, "Take off this row", "\n".join(failed))
        self.attached -= done
        self._load(f"Took {done} photo(s) off this row -- back in the capture folder")

    @staticmethod
    def _thumb(path: Path) -> QPixmap:
        rd = QImageReader(str(path))
        rd.setAutoTransform(True)
        size = rd.size()
        if size.isValid():
            rd.setScaledSize(size.scaled(THUMB, THUMB, Qt.AspectRatioMode.KeepAspectRatio))
        img = rd.read()
        return QPixmap.fromImage(img) if not img.isNull() else QPixmap()

    def _selected(self) -> list:
        """Selected files, oldest first (numbering follows capture order)."""
        paths = [it.data(Qt.ItemDataRole.UserRole) for it in self.list.selectedItems()]
        return sorted(paths, key=lambda p: (self._files.get(p, 0), p))

    def _update_preview(self) -> None:
        sel = self._selected()
        if not sel:
            self._preview.setText("Select photos to attach.")
            return
        stem = name_for(self._row, self.current_view())
        self._preview.setText(f"First photo will be named: {stem}{Path(sel[0]).suffix.lower()}")

    # -- attach -----------------------------------------------------------------------------
    def _attach(self) -> None:
        species = (self._row.get("species_name") or "").strip()
        if not species:
            QMessageBox.information(self, "Attach photos", "Enter the species first.")
            return
        sel = self._selected()
        if not sel:
            return
        stem = name_for(self._row, self.current_view())
        if not photo_links.has_staging_column(self._conn):
            QMessageBox.warning(self, "Attach photos",
                                "The photo links table is not ready for Data Entry yet. Run once "
                                "(Observatum closed):\npy -3.14 scripts\\add_photo_links_table.py --apply")
            return
        done, failed = 0, []
        for p in sel:
            src = Path(p)
            try:
                bench_photos.attach(self._conn, src, self._row["id"], stem)
                done += 1
            except OSError as e:
                why = str(e)
                if getattr(e, "winerror", None) == 17 or getattr(e, "errno", None) == 18:
                    why = ("the capture folder is on a different drive from the photo library -- "
                           "choose a capture folder on the same drive (e.g. inside OneDrive)")
                failed.append(f"{src.name}: {why}")
        self.attached += done
        if failed:
            QMessageBox.warning(self, "Attach photos",
                                "These photos could not be moved and were left where they are:\n\n"
                                + "\n".join(failed))
        k = len(photo_links.photos_for_staging(self._conn, self._row["id"]))
        self._load(f"Attached {done} photo(s) — now {k} on this row")


def ask_about_photos(parent, conn, staging_ids, what: str):
    """Before staging rows are deleted (`what`: 'Delete rows', 'Discard job', ...): if any have
    bench photos, ask where the photos go. Returns None when Wil cancels (delete nothing), else a
    function to call once the rows are deleted: it sends the photos of the rows really deleted
    back to the capture folder, if he chose that. The photo files are never deleted; left ones
    stay in _Bench, unlinked (the delete itself drops the links)."""
    nothing = (lambda: None)
    try:
        ids = [i for i in staging_ids if i is not None]
        by_row = bench_photos.photos_by_row(conn, ids)
        n = bench_photos.count_for_rows(conn, ids)
    except Exception:
        return nothing
    if not n:
        return nothing
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle(what)
    it = "them" if n != 1 else "it"
    box.setText(f"{n} photo{'s are' if n != 1 else ' is'} attached to {'these rows' if len(ids) != 1 else 'this row'}."
                f"\n\nPhotos are never deleted. Send {it} back to the capture folder "
                f"({capture_folder()}), or leave {it} in {bench_photos.BENCH_REL} "
                "(listed in the cleaning report)?")
    back = box.addButton("Back to capture folder", QMessageBox.ButtonRole.AcceptRole)
    leave = box.addButton("Leave in _Bench", QMessageBox.ButtonRole.AcceptRole)
    box.addButton(QMessageBox.StandardButton.Cancel)
    box.setDefaultButton(back)
    box.exec()
    if box.clickedButton() is leave:
        return nothing
    if box.clickedButton() is not back:
        return None

    def after():
        try:
            _sent, notes = bench_photos.send_back(conn, by_row, capture_folder())
        except Exception as e:
            notes = [f"photos not sent back: {e}"]
        if notes:
            QMessageBox.warning(parent, what, "\n".join(notes[:20]))
    return after
