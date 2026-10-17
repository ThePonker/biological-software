"""The Export for checking dialog (logic in check_export.py): which rows, which columns, which
folder; then the counts and an Open folder button. Nothing is written to the database."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Sequence

from PySide6.QtCore import QSettings, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QRadioButton, QVBoxLayout,
)

from DataEntry import check_export as ce
from DataEntry import theme

COLUMNS_KEY = "DataEntry/checkExportColumns"
FOLDER_KEY = "DataEntry/checkExportFolder"


def remembered_columns() -> List[str]:
    """The ticked column labels from last time (the defaults the first time)."""
    try:
        raw = QSettings().value(COLUMNS_KEY, None)
    except Exception:
        raw = None
    if raw is None:
        return list(ce.DEFAULT_COLUMNS)
    if isinstance(raw, str):
        raw = [raw] if raw else []
    return [c for c in raw if c in dict(ce.CHECK_COLUMNS)]


def remembered_folder() -> Path:
    try:
        v = QSettings().value(FOLDER_KEY, "", type=str)
    except Exception:
        v = ""
    return Path(v) if v else ce.default_out_root()


class CheckExportDialog(QDialog):
    def __init__(self, conn, job: Dict, selected_ids: Sequence[int], flagged_ids: Sequence[int],
                 parent=None):
        super().__init__(parent)
        self._conn, self._job = conn, job
        self._selected, self._flagged = list(selected_ids), list(flagged_ids)
        self._folder = remembered_folder()
        self.outcome: Dict = {}
        self.setWindowTitle("Export for checking")
        self.setMinimumWidth(420)
        self.setStyleSheet(theme.input_qss())
        v = QVBoxLayout(self)
        intro = QLabel("Writes a spreadsheet and a folder of copies of the rows' photos, to send "
                       "to someone to check. Nothing in Data Entry is changed.")
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {theme.INK}; font-size: 13px;")
        v.addWidget(intro)

        self.rb_flagged = QRadioButton(f"Rows marked To check ({len(self._flagged)})")
        self.rb_selected = QRadioButton(f"Selected rows ({len(self._selected)})")
        grp = QButtonGroup(self)
        for rb in (self.rb_flagged, self.rb_selected):
            grp.addButton(rb)
            v.addWidget(rb)
        (self.rb_flagged if self._flagged else self.rb_selected).setChecked(True)

        cols_lbl = QLabel("Columns to include:")
        cols_lbl.setStyleSheet(f"color: {theme.MUTED}; font-size: 12px;")
        v.addWidget(cols_lbl)
        ticked = set(remembered_columns())
        self.boxes: Dict[str, QCheckBox] = {}
        for label, _key in ce.CHECK_COLUMNS:
            cb = QCheckBox(label)
            cb.setChecked(label in ticked)
            cb.setStyleSheet(theme.checkbox_qss())
            self.boxes[label] = cb
            v.addWidget(cb)

        row = QHBoxLayout()
        self._folder_lbl = QLabel()
        self._folder_lbl.setWordWrap(True)
        self._folder_lbl.setStyleSheet(f"color: {theme.INK}; font-size: 12px;")
        row.addWidget(self._folder_lbl, 1)
        change = QPushButton("Change…")
        change.setStyleSheet(theme.button_secondary_qss(compact=True))
        change.clicked.connect(self._change_folder)
        row.addWidget(change)
        v.addLayout(row)
        self._show_folder()

        self._msg = QLabel("")
        self._msg.setWordWrap(True)
        self._msg.setStyleSheet(f"color: {theme.INK}; font-size: 12px;")
        v.addWidget(self._msg)

        btns = QHBoxLayout()
        btns.addStretch(1)
        self.open_btn = QPushButton("Open folder")
        self.open_btn.setStyleSheet(theme.button_secondary_qss())
        self.open_btn.clicked.connect(self._open_folder)
        self.open_btn.setVisible(False)
        btns.addWidget(self.open_btn)
        self.go_btn = QPushButton("Export")
        self.go_btn.setStyleSheet(theme.button_primary_qss())
        self.go_btn.clicked.connect(self._export)
        btns.addWidget(self.go_btn)
        close = QPushButton("Close")
        close.setStyleSheet(theme.button_secondary_qss())
        close.clicked.connect(self.accept)
        btns.addWidget(close)
        v.addLayout(btns)

    def _show_folder(self):
        self._folder_lbl.setText(f"Save in: {self._folder}")

    def _change_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Folder for the export", str(self._folder))
        if d:
            self._folder = Path(d)
            self._show_folder()

    def chosen_columns(self) -> List[str]:
        return [label for label, _k in ce.CHECK_COLUMNS if self.boxes[label].isChecked()]

    def chosen_ids(self) -> List[int]:
        return self._flagged if self.rb_flagged.isChecked() else self._selected

    def _export(self):
        ids = self.chosen_ids()
        if not ids:
            QMessageBox.information(self, "Export for checking",
                                    "No rows to export: mark rows To check, or select some rows.")
            return
        cols = self.chosen_columns()
        try:
            s = QSettings()
            s.setValue(COLUMNS_KEY, cols)
            s.setValue(FOLDER_KEY, str(self._folder))
        except Exception:
            pass
        try:
            self.outcome = ce.export_for_checking(self._conn, self._job, ids, cols, self._folder)
        except Exception as e:
            QMessageBox.warning(self, "Export for checking", f"Nothing was exported.\n\n{e}")
            return
        r = self.outcome
        text = (f"Wrote {r['rows']} row(s) and copied {r['photos_copied']} photo(s) to:\n"
                f"{r['folder']}")
        if r["photos_missing"]:
            text += f"\n{r['photos_missing']} photo(s) could not be found and were not copied."
        self._msg.setText(text)
        self.open_btn.setVisible(True)

    def _open_folder(self):
        if self.outcome.get("folder"):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.outcome["folder"]))
