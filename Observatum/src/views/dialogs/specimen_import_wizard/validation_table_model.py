"""
Validation Table Model for Specimen Import Wizard.

Uses QAbstractTableModel for efficient rendering of large datasets.
Only visible rows are rendered - instant population regardless of row count.
"""

from typing import List, Optional, Any
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QColor

from .validation_worker import ImportRow, RowStatus


class ValidationTableModel(QAbstractTableModel):
    """
    Model for validation results table.
    
    Wraps a list of ImportRow objects and provides data on-demand.
    Qt only requests data for visible cells, making this instant
    even for thousands of rows.
    """
    
    COLUMNS = ["Status", "Row", "Species", "Date", "Grid Ref", "VC", "Location", "Message"]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: List[ImportRow] = []
        self._theme_colors = {}
    
    def set_theme_colors(self, success: str, warning: str, error: str):
        """Set theme colors for status display."""
        self._theme_colors = {
            "success": QColor(success),
            "warning": QColor(warning),
            "error": QColor(error),
        }
    
    def set_data(self, rows: List[ImportRow]):
        """Set the data - this is instant, no matter how many rows."""
        self.beginResetModel()
        self._data = rows
        self.endResetModel()
    
    def get_row(self, row_idx: int) -> Optional[ImportRow]:
        """Get ImportRow at index."""
        if 0 <= row_idx < len(self._data):
            return self._data[row_idx]
        return None
    
    def get_all_rows(self) -> List[ImportRow]:
        """Get all ImportRow objects."""
        return self._data
    
    def update_row(self, row_idx: int, row: ImportRow):
        """Update a single row and notify view."""
        if 0 <= row_idx < len(self._data):
            self._data[row_idx] = row
            # Notify view that this row changed
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
        
        if role == Qt.DisplayRole:
            return self._get_display_value(row, col_idx)
        
        elif role == Qt.ForegroundRole:
            # Only color the status column
            if col_idx == 0:
                return self._get_status_color(row)
        
        elif role == Qt.ToolTipRole:
            if col_idx == 7:  # Message column
                return self._get_display_value(row, col_idx)
        
        return None
    
    def _get_display_value(self, row: ImportRow, col: int) -> str:
        if col == 0:  # Status
            if row.status == RowStatus.VALID:
                return "[OK]"
            elif row.status == RowStatus.WARNING:
                return "[!]"
            else:
                return "[X]"
        elif col == 1:  # Row number
            return str(row.row_number)
        elif col == 2:  # Species
            return row.species_name or ""
        elif col == 3:  # Date
            return row.date_collected or ""
        elif col == 4:  # Grid Ref
            return row.grid_ref or ""
        elif col == 5:  # VC
            return f"VC{row.vc_number}" if row.vc_number else ""
        elif col == 6:  # Location
            return row.site_name or ""
        elif col == 7:  # Message
            if row.status == RowStatus.ERROR:
                return row.error_message or ""
            else:
                return "; ".join(row.warnings) if row.warnings else ""
        return ""
    
    def _get_status_color(self, row: ImportRow) -> QColor:
        if row.status == RowStatus.VALID:
            return self._theme_colors.get("success", QColor("green"))
        elif row.status == RowStatus.WARNING:
            return self._theme_colors.get("warning", QColor("orange"))
        else:
            return self._theme_colors.get("error", QColor("red"))
    
    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.NoItemFlags
        
        # Make editable columns editable (Date, Grid Ref, Location)
        col = index.column()
        if col in [3, 4, 6]:  # Date, Grid Ref, Location
            return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable
        
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable
