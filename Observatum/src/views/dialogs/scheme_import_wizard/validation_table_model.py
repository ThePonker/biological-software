"""
Validation Table Model for Recording Scheme Import Wizard.

Uses QAbstractTableModel for efficient rendering of large datasets.
Only visible rows are rendered - instant population regardless of row count.
"""

from typing import List, Optional
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QColor

from .validation_worker import SchemeImportRow, RowStatus


class SchemeValidationTableModel(QAbstractTableModel):
    """
    Model for validation results table.
    
    Wraps a list of SchemeImportRow objects and provides data on-demand.
    Qt only requests data for visible cells, making this instant
    even for thousands of rows.
    """
    
    COLUMNS = ["Status", "Row", "Species", "Date", "Grid Ref", "Site", "Message"]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: List[SchemeImportRow] = []
        self._theme_colors = {}
    
    def set_theme_colors(self, success: str, warning: str, error: str):
        """Set theme colors for status display."""
        self._theme_colors = {
            "success": QColor(success),
            "warning": QColor(warning),
            "error": QColor(error),
        }
    
    def set_data(self, rows: List[SchemeImportRow]):
        """Set the data - this is instant, no matter how many rows."""
        self.beginResetModel()
        self._data = rows
        self.endResetModel()
    
    def clear(self):
        """Clear all data."""
        self.beginResetModel()
        self._data = []
        self.endResetModel()
    
    def pre_allocate(self, count: int):
        """Pre-allocate rows for incremental population."""
        self.beginResetModel()
        self._data = [None] * count
        self.endResetModel()
    
    def set_row(self, row_idx: int, row: SchemeImportRow):
        """Set a single row during incremental population."""
        if 0 <= row_idx < len(self._data):
            self._data[row_idx] = row
            top_left = self.index(row_idx, 0)
            bottom_right = self.index(row_idx, len(self.COLUMNS) - 1)
            self.dataChanged.emit(top_left, bottom_right)
    
    def get_row(self, row_idx: int) -> Optional[SchemeImportRow]:
        """Get SchemeImportRow at index."""
        if 0 <= row_idx < len(self._data):
            return self._data[row_idx]
        return None
    
    def get_all_rows(self) -> List[SchemeImportRow]:
        """Get all SchemeImportRow objects."""
        return [r for r in self._data if r is not None]
    
    def update_row(self, row_idx: int, row: SchemeImportRow):
        """Update a single row and notify view."""
        if 0 <= row_idx < len(self._data):
            self._data[row_idx] = row
            top_left = self.index(row_idx, 0)
            bottom_right = self.index(row_idx, len(self.COLUMNS) - 1)
            self.dataChanged.emit(top_left, bottom_right)
    
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
        
        row_idx = index.row()
        col_idx = index.column()
        
        if row_idx < 0 or row_idx >= len(self._data):
            return None
        
        row = self._data[row_idx]
        
        if row is None:
            if role == Qt.DisplayRole:
                return "..." if col_idx == 0 else ""
            return None
        
        if role == Qt.DisplayRole:
            return self._get_display_value(row, col_idx)
        
        elif role == Qt.ForegroundRole:
            if col_idx == 0:
                return self._get_status_color(row)
            if col_idx == 6:
                return self._get_status_color(row)
        
        elif role == Qt.ToolTipRole:
            if col_idx == 6:
                return self._get_display_value(row, col_idx)
        
        return None
    
    def _get_display_value(self, row: SchemeImportRow, col: int) -> str:
        if col == 0:
            if row.status == RowStatus.VALID:
                return "✓"
            elif row.status == RowStatus.WARNING:
                return "⚠"
            elif row.status == RowStatus.PENDING:
                return "..."
            else:
                return "✗"
        elif col == 1:
            return str(row.row_number)
        elif col == 2:
            return row.species_name or ""
        elif col == 3:
            return row.date or ""
        elif col == 4:
            return row.grid_ref or ""
        elif col == 5:
            return row.site_name or ""
        elif col == 6:
            message = row.error_message or ""
            if row.import_notes:
                if message:
                    message += " | "
                message += row.import_notes
            return message
        return ""
    
    def _get_status_color(self, row: SchemeImportRow) -> QColor:
        if row.status == RowStatus.VALID:
            return self._theme_colors.get("success", QColor("green"))
        elif row.status == RowStatus.WARNING:
            return self._theme_colors.get("warning", QColor("orange"))
        else:
            return self._theme_colors.get("error", QColor("red"))
    
    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.NoItemFlags
        
        col = index.column()
        if col in [2, 3, 4, 5]:
            return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable
        
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable
