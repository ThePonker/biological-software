"""The records in one map square, shown when it is clicked on the Mapping tab (backlog H4)."""
from typing import List

from PySide6.QtWidgets import (QDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout)

from ...themes import theme

_COLUMNS = [("Source", "source"), ("Species", "species_name"), ("Date", "date"),
            ("Grid ref", "grid_ref"), ("Site", "site_name"), ("Recorder / collector", "person"),
            ("Count / code", "extra")]


class SquareRecordsDialog(QDialog):
    """Read-only table of the records that fall in a grid square."""

    def __init__(self, label: str, grid_text: str, records: List[dict], species_text: str = "",
                 parent=None):
        super().__init__(parent)
        t = theme()
        self.setWindowTitle(f"Records in {label}")
        self.resize(900, 460)
        lay = QVBoxLayout(self)
        n = len(records)
        head = QLabel(f"<b>{label}</b> ({grid_text}) — {n} record{'s' if n != 1 else ''}"
                      + (f" of <i>{species_text}</i>" if species_text else ""))
        head.setStyleSheet(f"color: {t.get('text_primary')}; font-size: 13px;")
        lay.addWidget(head)

        self.table = QTableWidget(n, len(_COLUMNS))
        self.table.setHorizontalHeaderLabels([c for c, _k in _COLUMNS])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        rows = sorted(records, key=lambda r: (r.get("date") or "", r.get("species_name") or ""),
                      reverse=True)
        for i, r in enumerate(rows):
            for j, (_c, key) in enumerate(_COLUMNS):
                self.table.setItem(i, j, QTableWidgetItem(str(r.get(key) or "")))
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hdr.setStretchLastSection(True)
        self.table.setSortingEnabled(True)
        lay.addWidget(self.table, 1)

        row = QHBoxLayout()
        row.addStretch()
        close = QPushButton("Close")
        close.setStyleSheet(t.button_cancel_style())
        close.clicked.connect(self.accept)
        row.addWidget(close)
        lay.addLayout(row)
