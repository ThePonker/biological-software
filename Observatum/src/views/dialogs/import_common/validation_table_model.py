"""The validation-results table behind the specimen and scheme import wizards (C4, 9 Oct 2026).

Each wizard had its own copy of this model; they differed only in their columns. A wizard
subclasses it, names its COLUMNS and says what each cell shows (_get_display_value).

Uses QAbstractTableModel: Qt asks only for the visible cells, so filling it is instant
whatever the number of rows.
"""
from typing import List, Optional

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QColor

from ..row_status import RowStatus


class ImportValidationTableModel(QAbstractTableModel):
    COLUMNS: List[str] = []
    MESSAGE_COLUMN: Optional[int] = None        # shown in full as a tooltip
    COLOURED_COLUMNS = (0,)                     # drawn in the row's status colour
    EDITABLE_COLUMNS = ()
    EDIT_FIELDS: dict = {}                      # {column: row attribute} an edit writes to

    # (row index, attribute, new text) -- a cell the user edited. The row is marked as edited
    # and keeps its old status until it is revalidated.
    row_edited = Signal(int, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: list = []
        self._theme_colors = {}
        self.editable = True                    # a wizard turns editing off where it can't be used

    def set_theme_colors(self, success: str, warning: str, error: str):
        """Set theme colors for status display."""
        self._theme_colors = {
            "success": QColor(success),
            "warning": QColor(warning),
            "error": QColor(error),
        }

    def set_data(self, rows: list):
        """Set the data - this is instant, no matter how many rows."""
        self.beginResetModel()
        self._data = rows
        self.endResetModel()

    def clear(self):
        self.beginResetModel()
        self._data = []
        self.endResetModel()

    def pre_allocate(self, count: int):
        """Empty rows ('...') to be filled one by one with set_row."""
        self.beginResetModel()
        self._data = [None] * count
        self.endResetModel()

    def update_row(self, row_idx: int, row):
        """Replace a single row and notify the view."""
        if 0 <= row_idx < len(self._data):
            self._data[row_idx] = row
            self.dataChanged.emit(self.index(row_idx, 0), self.index(row_idx, len(self.COLUMNS) - 1))

    set_row = update_row

    def get_row(self, row_idx: int):
        if 0 <= row_idx < len(self._data):
            return self._data[row_idx]
        return None

    def get_all_rows(self) -> list:
        return [r for r in self._data if r is not None]

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._data)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            if 0 <= section < len(self.COLUMNS):
                return self.COLUMNS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        row_idx, col_idx = index.row(), index.column()
        if row_idx < 0 or row_idx >= len(self._data):
            return None
        row = self._data[row_idx]
        if row is None:                                   # not yet filled (pre_allocate)
            if role == Qt.DisplayRole:
                return "..." if col_idx == 0 else ""
            return None
        if role in (Qt.DisplayRole, Qt.EditRole):
            return self._get_display_value(row, col_idx)
        if role == Qt.ForegroundRole:
            if col_idx in self.COLOURED_COLUMNS:
                return self._get_status_color(row)
        elif role == Qt.ToolTipRole:
            if col_idx == self.MESSAGE_COLUMN:
                return self._get_display_value(row, col_idx)
        return None

    def _get_display_value(self, row, col: int) -> str:
        raise NotImplementedError

    def _get_status_color(self, row) -> QColor:
        if row.status == RowStatus.VALID:
            return self._theme_colors.get("success", QColor("green"))
        elif row.status == RowStatus.WARNING:
            return self._theme_colors.get("warning", QColor("orange"))
        else:
            return self._theme_colors.get("error", QColor("red"))

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.NoItemFlags
        if self.editable and index.column() in self.EDITABLE_COLUMNS:
            return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def setData(self, index: QModelIndex, value, role: int = Qt.EditRole) -> bool:
        """Keep an inline edit (IMP-6, 10 Oct 2026). The model had no setData, so Qt threw
        every edit of Date, Grid Ref or Site away the moment the cell closed."""
        if role != Qt.EditRole or not index.isValid() or not self.editable:
            return False
        attr = self.EDIT_FIELDS.get(index.column())
        row = self.get_row(index.row())
        if not attr or row is None:
            return False
        text = "" if value is None else str(value).strip()
        if attr == "grid_ref":
            text = text.upper().replace(" ", "")
        if text == (getattr(row, attr, "") or ""):
            return False
        setattr(row, attr, text)
        self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
        self.row_edited.emit(index.row(), attr, text)
        return True
