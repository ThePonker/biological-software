"""The cleaning report's record list (split from cleaning_dashboard.py, F71, 13 Oct 2026).

CleaningRowModel holds one problem's rows (UserRole gives the CleaningRow). The iRecord ID
cell is drawn as a link (link colour, underlined, hand cursor) when the record holds one,
so it is plain which records "Open in iRecord" works for; CleaningTableView shows the hand
cursor over such a cell and a plain arrow elsewhere.
"""
from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableView

from shared.irecord_links import irecord_url

from ...services.cleaning_report import CleaningRow
from ..components.natural_sort_proxy import NaturalSortProxy
from ...themes import theme

COLUMNS = ["Species", "Rank", "Date", "Grid ref", "Site", "Recorder", "Problem", "iRecord ID",
           "Source"]
_FIELDS = ["species", "rank", "date", "grid_ref", "site", "recorder", "detail", "irecord_id",
           "dataset"]
IRECORD_COLUMN = _FIELDS.index("irecord_id")
_WIDTHS = (200, 110, 90, 140, 190, 150, 240, 90, 260)


def link_colour() -> str:
    """The link colour: the theme's own 'link' token, else its primary (Moss Green)."""
    t = theme()
    return t.get("link", t.get("primary"))


class CleaningRowModel(QAbstractTableModel):
    """The rows of one problem; UserRole gives the CleaningRow."""

    def __init__(self, rows: Optional[List[CleaningRow]] = None, parent=None):
        super().__init__(parent)
        self._rows = rows or []

    def set_rows(self, rows: List[CleaningRow]):
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return COLUMNS[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        r = self._rows[index.row()]
        if role == Qt.ItemDataRole.UserRole:
            return r
        value = getattr(r, _FIELDS[index.column()])
        if role == Qt.ItemDataRole.DisplayRole:
            return "" if value is None else str(value)
        if role == Qt.ItemDataRole.EditRole:            # sort key: iRecord IDs as numbers
            return value
        if index.column() == IRECORD_COLUMN and irecord_url(value):
            if role == Qt.ItemDataRole.ForegroundRole:
                return QColor(link_colour())
            if role == Qt.ItemDataRole.FontRole:
                f = QFont()
                f.setUnderline(True)
                return f
            if role == Qt.ItemDataRole.ToolTipRole:
                return f"Open in iRecord\n{irecord_url(value)}"
        return None


class CleaningTableView(QTableView):
    """One problem's list: sortable, single row selection, hand cursor over an iRecord link."""

    def __init__(self, model: CleaningRowModel, parent=None):
        super().__init__(parent)
        self.proxy = NaturalSortProxy(self)
        self.proxy.setSourceModel(model)
        self.proxy.setSortRole(Qt.ItemDataRole.EditRole)
        self.setModel(self.proxy)
        self.setSortingEnabled(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.horizontalHeader().setStretchLastSection(True)
        for col, w in enumerate(_WIDTHS):
            self.setColumnWidth(col, w)
        self.setMouseTracking(True)

    def current_row(self) -> Optional[CleaningRow]:
        idx = self.currentIndex()
        return idx.data(Qt.ItemDataRole.UserRole) if idx.isValid() else None

    def is_link(self, index) -> bool:
        """True over an iRecord ID cell that holds a link."""
        if not index.isValid() or index.column() != IRECORD_COLUMN:
            return False
        row = index.data(Qt.ItemDataRole.UserRole)
        return bool(row is not None and irecord_url(row.irecord_id))

    def mouseMoveEvent(self, event):
        self.setCursor(Qt.CursorShape.PointingHandCursor if self.is_link(self.indexAt(event.pos()))
                       else Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(event)
