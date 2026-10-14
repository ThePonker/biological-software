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
        ("missing", "Links to missing files"), ("names", "Names not to the standard"))
HELP = {
    "empty": "Folders in Photos\\Life with no photo inside (a re-determination or rename can "
             "leave one). “Move to _archive” moves them out of the library; nothing is deleted.",
    "bench": "Bench photos from Data Entry still in Photos\\_Bench. They go to the species' folder "
             "when their row is committed with a species picked from the list.",
    "missing": "A record or specimen is linked to a photo that is not there (moved or renamed "
               "outside the apps). Put the file back, or unlink it in the record's Photos window.",
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

    def _fill(self, key: str, rows) -> None:
        t = self.tables[key]
        t.setRowCount(len(rows))
        for i, (a, b) in enumerate(rows):
            t.setItem(i, 0, QTableWidgetItem(str(a)))
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
                self._fill("bench", [(os.path.basename(p), why) for p, why in ph.bench_waiting(conn)])
                self._fill("missing", ph.missing_files(conn))
                life = pf.life_root()
                self._fill("names", [(os.path.relpath(s, life), d.name) for s, d in ph.nonstandard_names()])
            finally:
                if conn is not None:
                    conn.close()
        finally:
            QApplication.restoreOverrideCursor()
        self.btn_archive.setEnabled(bool(self._empty))

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
