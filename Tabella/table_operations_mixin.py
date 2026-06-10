"""
Field Entry App - Table Operations Mixin.

Extracted row/cell operations, clipboard, and undo/redo functionality.
"""

from typing import List, Set, Tuple, TYPE_CHECKING
import re

from PySide6.QtWidgets import QTableWidgetItem, QApplication, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from .constants import (
    COLORS, AUTO_POPULATED_COLS,
    COL_SPECIES, COL_TVK, COL_COMMON_NAME, COL_FAMILY, COL_ORDER,
    COL_GRID_REF, COL_VICE_COUNTY
)
from .undo_manager import ActionType
from .grid_ref import GridRefValidator


class TableOperationsMixin:
    """Mixin providing row/cell operations for FieldEntryTable."""
    
    # =========================================================================
    # Row Management
    # =========================================================================
    
    def add_rows(self, count: int = 1, with_defaults: bool = False, defaults: dict = None):
        """
        Add new empty rows at the TOP of the table.
        
        Args:
            count: Number of rows to add
            with_defaults: Whether to apply sticky defaults (default False for empty rows)
            defaults: Dict of column index -> value for defaults
        """
        self._undo_manager.begin_action(ActionType.ROW_INSERT, f"Add {count} row(s)")
        
        # Insert at top (row 0)
        for i in range(count):
            self.insertRow(0)
            self._init_row(0, defaults if with_defaults else None)
            self._undo_manager.set_insert_row(0)
        
        self._undo_manager.end_action()
        self._emit_row_count()
        
        # Select first cell of first new row
        if self.rowCount() > 0:
            self.setCurrentCell(0, 0)
    
    def add_startup_rows(self, count: int = 1000):
        """
        Add empty rows at startup (at the bottom/end of table).
        
        Args:
            count: Number of rows to add
        """
        start_row = self.rowCount()
        
        for i in range(count):
            row = start_row + i
            self.insertRow(row)
            self._init_row(row, None)
        
        self._emit_row_count()
        
        # Select first cell
        if self.rowCount() > 0:
            self.setCurrentCell(0, 0)
    
    def _init_row(self, row: int, defaults: dict = None):
        """Initialize a row with empty cells and optional defaults."""
        self.blockSignals(True)
        
        for col in range(self.columnCount()):
            item = QTableWidgetItem('')
            
            # Set read-only for auto-populated columns
            if col in AUTO_POPULATED_COLS:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setBackground(QColor(COLORS['readonly_bg']))
            
            # Apply default if provided
            if defaults and col in defaults:
                item.setText(str(defaults[col]))
            
            self.setItem(row, col, item)
        
        self.blockSignals(False)
    
    def _duplicate_row(self):
        """Duplicate the current row."""
        row = self.currentRow()
        if row < 0:
            return
        
        self._undo_manager.begin_action(ActionType.ROW_DUPLICATE, "Duplicate row")
        
        row_data = self._get_row_data(row)
        self.insertRow(row + 1)
        
        self.blockSignals(True)
        for col, value in enumerate(row_data):
            item = QTableWidgetItem(value)
            if col in AUTO_POPULATED_COLS:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setBackground(QColor(COLORS['readonly_bg']))
            self.setItem(row + 1, col, item)
        self.blockSignals(False)
        
        self._undo_manager.set_insert_row(row + 1)
        self._undo_manager.end_action()
        self._emit_row_count()
    
    def _insert_row_above(self):
        """Insert row above current."""
        row = self.currentRow()
        if row >= 0:
            self._undo_manager.begin_action(ActionType.ROW_INSERT, "Insert row above")
            self.insertRow(row)
            self._init_row(row)
            self._undo_manager.set_insert_row(row)
            self._undo_manager.end_action()
            self._emit_row_count()
    
    def _insert_row_below(self):
        """Insert row below current."""
        row = self.currentRow()
        if row >= 0:
            self._undo_manager.begin_action(ActionType.ROW_INSERT, "Insert row below")
            self.insertRow(row + 1)
            self._init_row(row + 1)
            self._undo_manager.set_insert_row(row + 1)
            self._undo_manager.end_action()
            self._emit_row_count()
        else:
            self.add_rows(1)
    
    def _delete_selected_rows(self):
        """Delete selected rows."""
        rows = sorted(set(idx.row() for idx in self.selectedIndexes()), reverse=True)
        if not rows:
            return
        
        self._undo_manager.begin_action(ActionType.ROW_DELETE, f"Delete {len(rows)} row(s)")
        
        for row in rows:
            self._undo_manager.record_row_data(row, self._get_row_data(row))
            self.removeRow(row)
        
        self._undo_manager.end_action()
        self._emit_row_count()
    
    def _get_row_data(self, row: int) -> List[str]:
        """Get all cell values for a row."""
        return [
            self.item(row, col).text() if self.item(row, col) else ''
            for col in range(self.columnCount())
        ]
    
    # =========================================================================
    # Cell Operations
    # =========================================================================
    
    def _on_cell_changed(self, row: int, col: int):
        """Handle cell value change."""
        item = self.item(row, col)
        if not item:
            return
        
        text = item.text()
        
        # Species column - trigger lookup
        if col == COL_SPECIES and text:
            self._lookup_species(row, text)
        
        # Grid ref column - validate and lookup VC
        elif col == COL_GRID_REF:
            self._validate_and_lookup_vc(row, text)
    
    def _lookup_species(self, row: int, species_name: str):
        """Look up species and populate taxonomy columns."""
        info = self._uksi.lookup(species_name)
        
        if info:
            self.blockSignals(True)
            self._set_cell(row, COL_TVK, info.get('tvk', ''))
            self._set_cell(row, COL_COMMON_NAME, info.get('common_name', ''))
            self._set_cell(row, COL_FAMILY, info.get('family', ''))
            self._set_cell(row, COL_ORDER, info.get('order', ''))
            self.blockSignals(False)
    
    def _validate_and_lookup_vc(self, row: int, grid_ref: str):
        """Validate grid ref and look up vice county."""
        item = self.item(row, COL_GRID_REF)
        vc_item = self.item(row, COL_VICE_COUNTY)
        
        if not grid_ref:
            if item:
                item.setBackground(QColor(COLORS['surface']))
            if vc_item:
                self.blockSignals(True)
                vc_item.setText('')
                self.blockSignals(False)
            return
        
        is_valid, message = GridRefValidator.validate(grid_ref)
        
        if is_valid:
            if item:
                item.setBackground(QColor(COLORS['surface']))
            
            vc_result = self._vc_lookup.get_vice_county(grid_ref)
            
            self.blockSignals(True)
            if vc_result:
                vc_num, vc_name = vc_result
                vc_item.setText(f"VC{vc_num}: {vc_name}")
                vc_item.setForeground(QColor(COLORS['text']))
            else:
                vc_item.setText("Unknown")
                vc_item.setForeground(QColor(COLORS['error_text']))
            self.blockSignals(False)
        else:
            if item:
                item.setBackground(QColor(COLORS['error_bg']))
            if vc_item:
                self.blockSignals(True)
                vc_item.setText('')
                self.blockSignals(False)
    
    def _set_cell(self, row: int, col: int, value: str):
        """Set cell value, creating item if needed."""
        item = self.item(row, col)
        if item:
            item.setText(value)
        else:
            item = QTableWidgetItem(value)
            if col in AUTO_POPULATED_COLS:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setBackground(QColor(COLORS['readonly_bg']))
            self.setItem(row, col, item)
    
    def _edit_current_cell(self):
        """Start editing the current cell (F2 behavior)."""
        current = self.currentItem()
        if current and current.flags() & Qt.ItemFlag.ItemIsEditable:
            self.editItem(current)
    
    # =========================================================================
    # Copy/Paste/Cut
    # =========================================================================
    
    def _copy(self):
        """Copy selected cells to clipboard."""
        selection = self.selectedIndexes()
        if not selection:
            return
        
        rows = sorted(set(idx.row() for idx in selection))
        cols = sorted(set(idx.column() for idx in selection))
        
        lines = []
        for row in rows:
            row_data = []
            for col in cols:
                item = self.item(row, col)
                row_data.append(item.text() if item else '')
            lines.append('\t'.join(row_data))
        
        text = '\n'.join(lines)
        QApplication.clipboard().setText(text)
        self.status_message.emit(f"Copied {len(selection)} cell(s)")
    
    def _cut(self):
        """Cut selected cells."""
        self._copy()
        self._delete_selection()
    
    def _paste(self):
        """
        Paste from clipboard.
        
        Behavior:
        - Single cell copied + multiple cells selected = paste into all selected
        - Multi-cell copied = paste starting from current cell
        """
        text = QApplication.clipboard().text()
        if not text:
            return
        
        selection = self.selectedIndexes()
        current = self.currentIndex()
        if not current.isValid():
            return
        
        lines = text.rstrip('\n').split('\n')
        is_single_value = len(lines) == 1 and '\t' not in lines[0]
        
        self._undo_manager.begin_action(ActionType.PASTE, "Paste")
        self.blockSignals(True)
        
        cells_changed = 0
        
        if is_single_value and len(selection) > 1:
            # Single value -> paste into all selected cells
            value = lines[0]
            for idx in selection:
                row, col = idx.row(), idx.column()
                if col not in AUTO_POPULATED_COLS:
                    item = self.item(row, col)
                    if item:
                        old_val = item.text()
                        item.setText(value)
                        self._undo_manager.record_cell_change(row, col, old_val, value)
                        cells_changed += 1
        else:
            # Multi-cell paste starting from current position
            start_row = current.row()
            start_col = current.column()
            
            for r, line in enumerate(lines):
                row = start_row + r
                
                while row >= self.rowCount():
                    self.insertRow(self.rowCount())
                    self._init_row(self.rowCount() - 1)
                
                cells = line.split('\t')
                for c, value in enumerate(cells):
                    col = start_col + c
                    if col < self.columnCount() and col not in AUTO_POPULATED_COLS:
                        item = self.item(row, col)
                        if item:
                            old_val = item.text()
                            item.setText(value)
                            self._undo_manager.record_cell_change(row, col, old_val, value)
                            cells_changed += 1
        
        self.blockSignals(False)
        self._undo_manager.end_action()
        
        # Trigger lookups for affected rows
        affected_rows = set()
        if is_single_value and len(selection) > 1:
            affected_rows = set(idx.row() for idx in selection)
        else:
            affected_rows = set(range(current.row(), current.row() + len(lines)))
        
        for row in affected_rows:
            if row < self.rowCount():
                species_item = self.item(row, COL_SPECIES)
                if species_item and species_item.text():
                    self._lookup_species(row, species_item.text())
                
                gr_item = self.item(row, COL_GRID_REF)
                if gr_item:
                    self._validate_and_lookup_vc(row, gr_item.text())
        
        self._emit_row_count()
        self.status_message.emit(f"Pasted into {cells_changed} cell(s)")
    
    def _delete_selection(self):
        """Clear selected cells."""
        selection = self.selectedIndexes()
        if not selection:
            return
        
        self._undo_manager.begin_action(ActionType.CLEAR, "Clear cells")
        self.blockSignals(True)
        
        for idx in selection:
            item = self.item(idx.row(), idx.column())
            if item and item.flags() & Qt.ItemFlag.ItemIsEditable:
                old_val = item.text()
                if old_val:
                    self._undo_manager.record_cell_change(idx.row(), idx.column(), old_val, '')
                    item.setText('')
        
        self.blockSignals(False)
        self._undo_manager.end_action()
    
    def _fill_down(self):
        """Fill selected cells with value from top cell (Ctrl+D)."""
        selection = self.selectedIndexes()
        if len(selection) < 2:
            return
        
        cols = {}
        for idx in selection:
            if idx.column() not in cols:
                cols[idx.column()] = []
            cols[idx.column()].append(idx.row())
        
        self._undo_manager.begin_action(ActionType.FILL_DOWN, "Fill down")
        self.blockSignals(True)
        
        for col, rows in cols.items():
            if col in AUTO_POPULATED_COLS:
                continue
            
            rows.sort()
            if len(rows) < 2:
                continue
            
            source_item = self.item(rows[0], col)
            fill_value = source_item.text() if source_item else ''
            
            for row in rows[1:]:
                item = self.item(row, col)
                if item:
                    old_val = item.text()
                    if old_val != fill_value:
                        self._undo_manager.record_cell_change(row, col, old_val, fill_value)
                        item.setText(fill_value)
        
        self.blockSignals(False)
        self._undo_manager.end_action()
    
    # =========================================================================
    # Undo/Redo
    # =========================================================================
    
    def _undo(self):
        """Undo last action."""
        action = self._undo_manager.undo()
        if not action:
            self.status_message.emit("Nothing to undo")
            return
        
        self.blockSignals(True)
        
        if action.action_type == ActionType.ROW_INSERT:
            if action.insert_row is not None:
                self.removeRow(action.insert_row)
        
        elif action.action_type == ActionType.ROW_DELETE:
            if action.row_data:
                for rd in sorted(action.row_data, key=lambda x: x.row):
                    self.insertRow(rd.row)
                    for col, value in enumerate(rd.values):
                        item = QTableWidgetItem(value)
                        if col in AUTO_POPULATED_COLS:
                            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                            item.setBackground(QColor(COLORS['readonly_bg']))
                        self.setItem(rd.row, col, item)
        
        elif action.cell_changes:
            for change in action.cell_changes:
                item = self.item(change.row, change.col)
                if item:
                    item.setText(change.old_value)
        
        self.blockSignals(False)
        self._emit_row_count()
        self.status_message.emit(f"Undo: {action.description}")
    
    def _redo(self):
        """Redo last undone action."""
        action = self._undo_manager.redo()
        if not action:
            self.status_message.emit("Nothing to redo")
            return
        
        self.blockSignals(True)
        
        if action.action_type == ActionType.ROW_INSERT:
            if action.insert_row is not None:
                self.insertRow(action.insert_row)
                self._init_row(action.insert_row)
        
        elif action.action_type == ActionType.ROW_DELETE:
            if action.row_data:
                for rd in sorted(action.row_data, key=lambda x: x.row, reverse=True):
                    self.removeRow(rd.row)
        
        elif action.cell_changes:
            for change in action.cell_changes:
                item = self.item(change.row, change.col)
                if item:
                    item.setText(change.new_value)
        
        self.blockSignals(False)
        self._emit_row_count()
        self.status_message.emit(f"Redo: {action.description}")
