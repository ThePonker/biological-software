"""Small dialog for Specimens to check > Change date of whole visit (14 Oct 2026).

Shows the selected specimens and asks for the new date; nothing is written here.
"""
from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QAbstractItemView, QDateEdit, QDialog, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)

from ...themes import theme


def _show(iso: str) -> str:
    d = QDate.fromString(iso, "yyyy-MM-dd")
    return d.toString("dd/MM/yyyy") if d.isValid() else iso


def describe_change(rows: List[dict], iso: str) -> str:
    """'Change 3 specimens from 01/06/2025 to 02/06/2025'."""
    olds = sorted({str(r.get("date_collected") or "no date") for r in rows})
    n = len(rows)
    return (f"Change {n} specimen{'s' if n != 1 else ''} from "
            f"{', '.join(_show(d) for d in olds)} to {_show(iso)}")


class VisitDateDialog(QDialog):
    def __init__(self, rows: List[dict], parent=None):
        super().__init__(parent)
        self._rows = rows
        self.setWindowTitle("Change date of whole visit")
        self.resize(640, 420)
        v = QVBoxLayout(self)
        t = QTableWidget(len(rows), 4)
        t.setHorizontalHeaderLabels(["Specimen", "Species", "Date", "Site"])
        t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        t.verticalHeader().setVisible(False)
        for i, r in enumerate(rows):
            for c, k in enumerate(("specimen_code", "species_name", "date_collected", "site_name")):
                v = str(r.get(k) or "")
                t.setItem(i, c, QTableWidgetItem(_show(v) if k == "date_collected" and v else v))
        t.horizontalHeader().setStretchLastSection(True)
        v.addWidget(t, 1)
        row = QHBoxLayout()
        row.addWidget(QLabel("New date:"))
        self.date_edit = QDateEdit()
        self.date_edit.setDisplayFormat("dd/MM/yyyy")
        self.date_edit.setCalendarPopup(True)
        first = QDate.fromString(str(rows[0].get("date_collected") or "")[:10], "yyyy-MM-dd")
        self.date_edit.setDate(first if first.isValid() else QDate.currentDate())
        self.date_edit.dateChanged.connect(self._preview)
        row.addWidget(self.date_edit)
        row.addStretch(1)
        v.addLayout(row)
        self.preview = QLabel("")
        v.addWidget(self.preview)
        btns = QHBoxLayout()
        btns.addStretch(1)
        ok = QPushButton("Change…")
        ok.setStyleSheet(theme().button_primary_style())
        ok.clicked.connect(self.accept)
        cancel = QPushButton("Cancel")
        cancel.setStyleSheet(theme().button_cancel_style())
        cancel.clicked.connect(self.reject)
        btns.addWidget(ok)
        btns.addWidget(cancel)
        v.addLayout(btns)
        self._preview()

    def new_iso(self) -> str:
        return self.date_edit.date().toString("yyyy-MM-dd")

    def preview_text(self) -> str:
        return describe_change(self._rows, self.new_iso())

    def _preview(self, *_):
        self.preview.setText(self.preview_text())

    def chosen(self) -> Optional[str]:
        return self.new_iso() if self.result() else None
