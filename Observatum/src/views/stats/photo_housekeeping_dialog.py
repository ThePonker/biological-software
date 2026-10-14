"""Cleaning report > Photos… (bench photos take 2, 14 Oct 2026): the photo library's loose ends,
one tab each, from shared/photo_housekeeping.py. Read-only except "Move to _archive" on the
empty-folders tab, which moves (never deletes) the empty folders after Wil confirms.
"""
from __future__ import annotations

import os
import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from shared import photo_files as pf
from shared import photo_housekeeping as ph
from ...themes import theme

TABS = (("empty", "Empty species folders"), ("bench", "Waiting in _Bench"),
        ("missing", "Links to missing files"), ("dead", "Links to deleted records"),
        ("names", "Names not to the standard"))
HELP = {
    "empty": "Folders in Photos\\Life with no photo inside (a re-determination or rename can "
             "leave one). “Move to _archive” moves them out of the library; nothing is deleted.",
    "bench": "Bench photos from Data Entry still in Photos\\_Bench. They go to the species' folder "
             "when their row is committed with a species picked from the list. A photo on a record "
             "goes with \u201cFile with its record\u201d once the record's species is picked from the "
             "list. Photos linked to nothing can go back to the capture folder or to _archive "
             "(links are checked in this database only).",
    "missing": "A record or specimen is linked to a photo that is not there (moved or renamed "
               "outside the apps). Put the file back, or unlink it in the record's Photos window.",
    "dead": "A photo is still linked to a record, specimen or Data Entry row that was deleted some "
            "other way than the apps' delete. The photos themselves are fine. To remove these links "
            "(dry run first, then --apply; Observatum closed): py -3.14 scripts\\tidy_bench_links.py",
    "names": "Specimen photos not yet named to the standard. "
             "Run: py -3.14 scripts\\standardise_specimen_names.py",
}


class PhotoHousekeepingDialog(QDialog):
    def __init__(self, main_db: str, parent=None):
        super().__init__(parent)
        self._main_db = main_db
        self.setWindowTitle("Cleaning report — photos")
        self.resize(900, 560)
        v = QVBoxLayout(self)
        self.lbl_root = QLabel(f"Photo library: {pf.media_root()}")
        v.addWidget(self.lbl_root)
        self.tabs = QTabWidget()
        v.addWidget(self.tabs, 1)
        self.tables = {}
        self._labels = {}
        for key, label in TABS:
            page = QWidget()
            pv = QVBoxLayout(page)
            note = QLabel(HELP[key])
            note.setWordWrap(True)
            pv.addWidget(note)
            t = QTableWidget(0, 2)
            t.setHorizontalHeaderLabels(["Photo / folder", "Note"])
            t.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            t.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            pv.addWidget(t, 1)
            if key == "bench":
                t.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
                t.itemSelectionChanged.connect(self._bench_buttons)
                t.doubleClicked.connect(lambda _i: self.view_bench())
                row = QHBoxLayout()
                self.btn_bench_folder = QPushButton("Open folder")
                self.btn_bench_folder.setStyleSheet(theme().button_secondary_style())
                self.btn_bench_folder.clicked.connect(self.open_bench_folder)
                row.addWidget(self.btn_bench_folder)
                row.addStretch(1)
                self.btn_bench_file = QPushButton("File with its record")
                self.btn_bench_file.setStyleSheet(theme().button_primary_style())
                self.btn_bench_file.setToolTip("Move photos that are on a record into that record's "
                                               "species folder (its species must be picked from the list).")
                self.btn_bench_file.clicked.connect(self.bench_file)
                row.addWidget(self.btn_bench_file)
                self.btn_bench_back = QPushButton("Back to capture folder")
                self.btn_bench_archive = QPushButton("Move to _archive")
                for b, slot in ((self.btn_bench_back, self.bench_back), (self.btn_bench_archive, self.bench_archive)):
                    b.setStyleSheet(theme().button_secondary_style())
                    b.clicked.connect(slot)
                    b.setToolTip("Only photos linked to nothing can be moved; a photo still on a row "
                                 "or a record stays where it is.")
                    row.addWidget(b)
                pv.addLayout(row)
            if key == "empty":
                row = QHBoxLayout()
                row.addStretch(1)
                self.btn_archive = QPushButton("Move to _archive")
                self.btn_archive.setStyleSheet(theme().button_primary_style())
                self.btn_archive.clicked.connect(self.archive_empty)
                row.addWidget(self.btn_archive)
                pv.addLayout(row)
            self.tables[key] = t
            self._labels[key] = label
            self.tabs.addTab(page, label)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setStyleSheet(theme().button_secondary_style())
        self.btn_refresh.clicked.connect(self.refresh)
        bottom.addWidget(self.btn_refresh)
        close = QPushButton("Close")
        close.setStyleSheet(theme().button_cancel_style())
        close.clicked.connect(self.accept)
        bottom.addWidget(close)
        v.addLayout(bottom)
        self.confirm = lambda text: QMessageBox.question(          # replaceable in tests
            self, "Move to _archive", text) == QMessageBox.StandardButton.Yes
        self.refresh()

    def _fill(self, key: str, rows, data=None) -> None:
        t = self.tables[key]
        t.setRowCount(len(rows))
        for i, (a, b) in enumerate(rows):
            item = QTableWidgetItem(str(a))
            if data is not None:
                item.setData(Qt.ItemDataRole.UserRole, data[i])
            t.setItem(i, 0, item)
            t.setItem(i, 1, QTableWidgetItem(str(b)))
        self.tabs.setTabText([k for k, _ in TABS].index(key), f"{self._labels[key]} ({len(rows)})")

    def refresh(self) -> None:
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            pf.refresh()
            try:
                conn = sqlite3.connect(f"file:{self._main_db}?mode=ro", uri=True)
            except sqlite3.Error:
                conn = None
            try:
                self._empty = ph.empty_folders()
                self._fill("empty", [(f, "") for f in self._empty])
                bench = ph.bench_waiting(conn)
                self._bench_why = dict(bench)
                self._fill("bench", [(os.path.basename(p), why) for p, why in bench], [p for p, _w in bench])
                self._fill("missing", ph.missing_files(conn))
                self._fill("dead", ph.dead_links(conn))
                life = pf.life_root()
                self._fill("names", [(os.path.relpath(s, life), d.name) for s, d in ph.nonstandard_names()])
            finally:
                if conn is not None:
                    conn.close()
        finally:
            QApplication.restoreOverrideCursor()
        self.btn_archive.setEnabled(bool(self._empty))
        self._bench_buttons()

    # -- Waiting in _Bench (14 Oct 2026) -----------------------------------------------------
    def selected_bench(self) -> list:
        t = self.tables["bench"]
        rows = sorted({i.row() for i in t.selectedIndexes()})
        return [t.item(r, 0).data(Qt.ItemDataRole.UserRole) for r in rows if t.item(r, 0)]

    def _bench_buttons(self) -> None:
        sel = self.selected_bench()
        free = bool(sel) and all(getattr(self, "_bench_why", {}).get(p) == ph.UNLINKED for p in sel)
        self.btn_bench_back.setEnabled(free)
        self.btn_bench_archive.setEnabled(free)
        self.btn_bench_file.setEnabled(bool(sel) and any(
            getattr(self, "_bench_why", {}).get(p) == ph.ON_RECORD for p in sel))
        self.btn_bench_folder.setEnabled(bool(getattr(self, "_bench_why", None)))

    def _move_bench(self, to_folder, title: str) -> None:
        sel = self.selected_bench()
        if not sel:
            return
        try:
            conn = sqlite3.connect(f"file:{self._main_db}?mode=ro", uri=True) if self._main_db else None
        except sqlite3.Error:
            conn = None
        try:
            moved, notes = ph.move_bench_photos(conn, sel, to_folder)
        finally:
            if conn is not None:
                conn.close()
        msg = f"Moved {len(moved)} photo(s) to {to_folder}."
        if notes:
            msg += "\n\n" + "\n".join(notes[:20])
        QMessageBox.information(self, title, msg)
        self.refresh()

    def bench_file(self) -> None:
        """Photos on a record go to that record's species folder (its species has a TVK)."""
        sel = [p for p in self.selected_bench() if self._bench_why.get(p) == ph.ON_RECORD]
        if not sel or not self._main_db:
            return
        from shared import bench_photos, photo_links
        conn = sqlite3.connect(self._main_db)
        try:
            oids, sids = set(), set()
            for p in sel:
                for sid, oid in conn.execute(f"SELECT specimen_id, observation_id FROM {photo_links.TABLE} "
                                             "WHERE photo_path = ?", (p,)):
                    (sids if sid is not None else oids).add(sid if sid is not None else oid)
            moved, notes = bench_photos.file_record_photos(conn, sorted(oids), sorted(sids), only_paths=sel)
        finally:
            conn.close()
        left = len(sel) - len(moved)
        msg = f"Filed {len(moved)} photo(s) in their species' folders."
        if left:
            msg += (f"\n\n{left} left: their record's species is not picked from the list yet -- open "
                    "the record, pick the species, save, and they are filed then.")
        if notes:
            msg += "\n\n" + "\n".join(notes[:20])
        QMessageBox.information(self, "File with its record", msg)
        self.refresh()

    def bench_back(self) -> None:
        from DataEntry.photo_attach import capture_folder
        self._move_bench(capture_folder(), "Back to capture folder")

    def bench_archive(self) -> None:
        self._move_bench(ph.bench_archive_folder(), "Move to _archive")

    def open_bench_folder(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from shared import bench_photos
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(bench_photos.bench_root())))

    def view_bench(self) -> None:
        sel = self.selected_bench()
        allp = [self.tables["bench"].item(r, 0).data(Qt.ItemDataRole.UserRole)
                for r in range(self.tables["bench"].rowCount())]
        if not allp:
            return
        from ..dialogs.photo_viewer import PhotoViewer
        start = allp.index(sel[0]) if sel and sel[0] in allp else 0
        self._viewer = PhotoViewer([pf.absolute(p) for p in allp], start, parent=self)
        self._viewer.show()

    def archive_empty(self) -> None:
        if not self._empty:
            return
        if not self.confirm(f"Move {len(self._empty)} empty folder(s) out of the photo library into "
                            "_archive\\empty_folders_<today>?\n\nNothing is deleted; each move is logged "
                            "in data\\photo_moves."):
            return
        moved, notes, log = ph.archive_empty_folders(self._empty)
        msg = f"Moved {len(moved)} folder(s). Log: {log}"
        if notes:
            msg += "\n\n" + "\n".join(notes[:20])
        QMessageBox.information(self, "Move to _archive", msg)
        self.refresh()
