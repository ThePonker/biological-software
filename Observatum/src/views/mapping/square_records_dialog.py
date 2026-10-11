"""The records in one map square, shown when it is clicked on the Mapping tab (backlog H4).
Open in iRecord (R9-3): for the selected row, when that record holds an iRecord ID."""
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout)

from ...themes import theme
from ..components.irecord_button import IRecordButton

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
        self._irecord = _irecord_ids(rows)
        for i, r in enumerate(rows):
            for j, (_c, key) in enumerate(_COLUMNS):
                self.table.setItem(i, j, QTableWidgetItem(str(r.get(key) or "")))
            self.table.item(i, 0).setData(Qt.ItemDataRole.UserRole, (r.get("table"), r.get("id")))
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hdr.setStretchLastSection(True)
        self.table.setSortingEnabled(True)
        lay.addWidget(self.table, 1)

        row = QHBoxLayout()
        row.addStretch()
        self.irecord_btn = IRecordButton(None, self)
        self.irecord_btn.setVisible(bool(self._irecord))      # no button when none has an ID
        self.table.itemSelectionChanged.connect(self._on_selection)
        row.addWidget(self.irecord_btn)
        close = QPushButton("Close")
        close.setStyleSheet(t.button_cancel_style())
        close.clicked.connect(self.accept)
        row.addWidget(close)
        lay.addLayout(row)

    def selected_irecord_id(self) -> Optional[int]:
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return None
        key = self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        return self._irecord.get(tuple(key)) if key else None

    def _on_selection(self):
        self.irecord_btn.set_irecord_id(self.selected_irecord_id())


def _irecord_ids(records: List[dict]) -> Dict[Tuple[str, int], int]:
    """{(table, id): iRecord ID} for the listed records that hold one, read from the app's
    database (the map's rows don't carry the ID). Empty if the database can't be read."""
    from shared.irecord_links import irecord_ids
    by_table: Dict[str, list] = {}
    for r in records:
        if r.get("table") and r.get("id") is not None:
            by_table.setdefault(r["table"], []).append(r["id"])
    if not by_table:
        return {}
    try:
        from shared.db_open import connect_ro
        from shared.species_counting import default_db
        conn = connect_ro(default_db())
    except Exception:
        return {}
    try:
        return {(t, rid): n for t, ids in by_table.items()
                for rid, n in irecord_ids(conn, t, ids).items()}
    except Exception:
        return {}
    finally:
        conn.close()
