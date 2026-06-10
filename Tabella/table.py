"""
Field Entry App - Custom Table Widget.

Excel-like table with species autocomplete, validation highlighting,
copy/paste, undo/redo, and other Excel features.
"""

from typing import List, Optional, Set, Tuple, TYPE_CHECKING
import re

from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QMenu
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QKeySequence, QShortcut

from .constants import (
    COLUMNS, COLORS, AUTO_POPULATED_COLS, COL_SPECIES, COL_QTY, COL_GRID_REF
)
from .delegates import SpeciesDelegate, ComboDelegate, DateDelegate, QuantityDelegate
from .undo_manager import UndoManager, ActionType
from .table_operations_mixin import TableOperationsMixin

if TYPE_CHECKING:
    from .uksi_lookup import UKSILookup
    from .vc_lookup import VCLookup


class FieldEntryTable(TableOperationsMixin, QTableWidget):
    """
    Excel-like table for field data entry.
    
    Features:
    - Species autocomplete from UKSI
    - Auto-population of taxonomy fields
    - Grid reference validation with highlighting
    - Vice county auto-lookup
    - Copy/paste/cut, Undo/redo
    - Column sorting and resizing
    - Find functionality
    """
    
    row_count_changed = Signal(int, int)  # (total_rows, data_rows)
    status_message = Signal(str)
    
    def __init__(self, uksi: 'UKSILookup', vc_lookup: 'VCLookup', parent=None):
        super().__init__(parent)
        
        self._uksi = uksi
        self._vc_lookup = vc_lookup
        self._undo_manager = UndoManager()
        self._highlighted_cells: Set[Tuple[int, int]] = set()
        self._sort_column = -1
        self._sort_order = Qt.SortOrder.AscendingOrder
        
        self._setup_table()
        self._setup_delegates()
        self._setup_shortcuts()
        self._connect_signals()
    
    def _setup_table(self):
        """Configure table appearance and behavior."""
        self.setColumnCount(len(COLUMNS))
        self.setHorizontalHeaderLabels([c[0] for c in COLUMNS])
        
        for i, (_, width, _, _, _, _) in enumerate(COLUMNS):
            self.setColumnWidth(i, width)
        
        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        header.setSectionsMovable(False)
        header.sectionDoubleClicked.connect(self._auto_fit_column)
        header.sectionClicked.connect(self._on_header_clicked)
        
        self.verticalHeader().setDefaultSectionSize(26)
        self.verticalHeader().setVisible(True)
        
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked |
            QAbstractItemView.EditTrigger.EditKeyPressed |
            QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        
        self.setAlternatingRowColors(True)
        self.setShowGrid(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        
        self.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLORS['surface']};
                gridline-color: {COLORS['grid']};
                font-size: 11px;
                border: 1px solid {COLORS['border']};
            }}
            QTableWidget::item {{ padding: 2px 6px; }}
            QTableWidget::item:selected {{
                background-color: {COLORS['selected_bg']};
                color: black;
            }}
            QHeaderView::section {{
                background-color: {COLORS['header_bg']};
                color: {COLORS['header_text']};
                font-weight: bold;
                font-size: 10px;
                padding: 5px;
                border: none;
                border-right: 1px solid {COLORS['border']};
                border-bottom: 1px solid {COLORS['border']};
            }}
            QHeaderView::section:hover {{ background-color: {COLORS['surface_alt']}; }}
        """)
    
    def _setup_delegates(self):
        """Set up cell delegates for special columns."""
        self.setItemDelegateForColumn(COL_SPECIES, SpeciesDelegate(self._uksi, self))
        self.setItemDelegateForColumn(5, DateDelegate(self))  # COL_DATE
        self.setItemDelegateForColumn(COL_QTY, QuantityDelegate(self))
        
        for i, (_, _, _, _, options, _) in enumerate(COLUMNS):
            if options:
                self.setItemDelegateForColumn(i, ComboDelegate(options, self))
    
    def _setup_shortcuts(self):
        """Set up keyboard shortcuts."""
        QShortcut(QKeySequence.StandardKey.Undo, self, self._undo)
        QShortcut(QKeySequence.StandardKey.Redo, self, self._redo)
        QShortcut(QKeySequence.StandardKey.Copy, self, self._copy)
        QShortcut(QKeySequence.StandardKey.Cut, self, self._cut)
        QShortcut(QKeySequence.StandardKey.Paste, self, self._paste)
        QShortcut(QKeySequence.StandardKey.Delete, self, self._delete_selection)
        QShortcut(QKeySequence("Backspace"), self, self._delete_selection)
        QShortcut(QKeySequence.StandardKey.SelectAll, self, self.selectAll)
        QShortcut(QKeySequence("Ctrl+D"), self, self._fill_down)
        QShortcut(QKeySequence("Ctrl+Shift+D"), self, self._duplicate_row)
        QShortcut(QKeySequence("Ctrl+I"), self, self._insert_row_below)
        QShortcut(QKeySequence("Ctrl+Shift+Delete"), self, self._delete_selected_rows)
        QShortcut(QKeySequence("F2"), self, self._edit_current_cell)
    
    def _connect_signals(self):
        """Connect internal signals."""
        self.cellChanged.connect(self._on_cell_changed)
    
    # =========================================================================
    # Sorting
    # =========================================================================
    
    def _on_header_clicked(self, col: int):
        """Handle header click for sorting."""
        if self._sort_column == col:
            self._sort_order = (Qt.SortOrder.DescendingOrder 
                               if self._sort_order == Qt.SortOrder.AscendingOrder 
                               else Qt.SortOrder.AscendingOrder)
        else:
            self._sort_column = col
            self._sort_order = Qt.SortOrder.AscendingOrder
        
        self.sortItems(col, self._sort_order)
        direction = "↑" if self._sort_order == Qt.SortOrder.AscendingOrder else "↓"
        self.status_message.emit(f"Sorted by {COLUMNS[col][0]} {direction}")
    
    def _auto_fit_column(self, col: int):
        """Auto-fit column width to content."""
        self.resizeColumnToContents(col)
    
    # =========================================================================
    # Find
    # =========================================================================
    
    def find_next(self, text: str, case_sensitive: bool, whole_word: bool) -> bool:
        """Find next occurrence of text."""
        if not text:
            return False
        
        current = self.currentIndex()
        start_row = current.row() if current.isValid() else 0
        start_col = current.column() + 1 if current.isValid() else 0
        
        for row in range(self.rowCount()):
            actual_row = (start_row + row) % self.rowCount()
            col_start = start_col if row == 0 else 0
            
            for col in range(col_start, self.columnCount()):
                if self._cell_matches(actual_row, col, text, case_sensitive, whole_word):
                    self.setCurrentCell(actual_row, col)
                    return True
        return False
    
    def find_previous(self, text: str, case_sensitive: bool, whole_word: bool) -> bool:
        """Find previous occurrence."""
        if not text:
            return False
        
        current = self.currentIndex()
        start_row = current.row() if current.isValid() else self.rowCount() - 1
        start_col = current.column() - 1 if current.isValid() else self.columnCount() - 1
        
        for row in range(self.rowCount()):
            actual_row = (start_row - row) % self.rowCount()
            col_start = start_col if row == 0 else self.columnCount() - 1
            
            for col in range(col_start, -1, -1):
                if self._cell_matches(actual_row, col, text, case_sensitive, whole_word):
                    self.setCurrentCell(actual_row, col)
                    return True
        return False
    
    def find_all(self, text: str, case_sensitive: bool, whole_word: bool) -> int:
        """Highlight all occurrences. Returns count."""
        self._clear_highlights()
        if not text:
            return 0
        
        count = 0
        for row in range(self.rowCount()):
            for col in range(self.columnCount()):
                if self._cell_matches(row, col, text, case_sensitive, whole_word):
                    self._highlight_cell(row, col)
                    count += 1
        return count
    
    def _cell_matches(self, row: int, col: int, text: str, case_sensitive: bool, whole_word: bool) -> bool:
        """Check if cell matches search criteria."""
        item = self.item(row, col)
        if not item:
            return False
        
        cell_text = item.text()
        search_text = text
        
        if not case_sensitive:
            cell_text = cell_text.lower()
            search_text = search_text.lower()
        
        if whole_word:
            return bool(re.search(r'\b' + re.escape(search_text) + r'\b', cell_text))
        return search_text in cell_text
    
    def _highlight_cell(self, row: int, col: int):
        """Highlight a cell as search result."""
        item = self.item(row, col)
        if item:
            item.setBackground(QColor('#ffff80'))
            self._highlighted_cells.add((row, col))
    
    def _clear_highlights(self):
        """Clear all search highlights."""
        for row, col in self._highlighted_cells:
            item = self.item(row, col)
            if item:
                bg = COLORS['readonly_bg'] if col in AUTO_POPULATED_COLS else COLORS['surface']
                item.setBackground(QColor(bg))
        self._highlighted_cells.clear()
    
    # =========================================================================
    # Replace
    # =========================================================================
    
    def replace_current(self, find_text: str, replace_text: str, 
                        case_sensitive: bool, whole_word: bool) -> bool:
        """
        Replace text in current cell if it matches.
        
        Returns:
            True if replacement was made
        """
        current = self.currentIndex()
        if not current.isValid():
            return False
        
        row, col = current.row(), current.column()
        
        # Don't replace in auto-populated columns
        if col in AUTO_POPULATED_COLS:
            return False
        
        item = self.item(row, col)
        if not item:
            return False
        
        if self._cell_matches(row, col, find_text, case_sensitive, whole_word):
            old_text = item.text()
            new_text = self._do_replace(old_text, find_text, replace_text, case_sensitive, whole_word)
            
            if old_text != new_text:
                self._undo_manager.begin_action(ActionType.CELL_EDIT, "Replace")
                self._undo_manager.record_cell_change(row, col, old_text, new_text)
                self._undo_manager.end_action()
                
                self.blockSignals(True)
                item.setText(new_text)
                self.blockSignals(False)
                return True
        
        return False
    
    def replace_all(self, find_text: str, replace_text: str,
                    case_sensitive: bool, whole_word: bool) -> int:
        """
        Replace all occurrences.
        
        Returns:
            Number of replacements made
        """
        if not find_text:
            return 0
        
        count = 0
        self._undo_manager.begin_action(ActionType.MULTI_CELL_EDIT, "Replace All")
        self.blockSignals(True)
        
        for row in range(self.rowCount()):
            for col in range(self.columnCount()):
                # Skip auto-populated columns
                if col in AUTO_POPULATED_COLS:
                    continue
                
                item = self.item(row, col)
                if not item:
                    continue
                
                if self._cell_matches(row, col, find_text, case_sensitive, whole_word):
                    old_text = item.text()
                    new_text = self._do_replace(old_text, find_text, replace_text, case_sensitive, whole_word)
                    
                    if old_text != new_text:
                        self._undo_manager.record_cell_change(row, col, old_text, new_text)
                        item.setText(new_text)
                        count += 1
        
        self.blockSignals(False)
        self._undo_manager.end_action()
        self._clear_highlights()
        
        return count
    
    def _do_replace(self, text: str, find: str, replace: str,
                    case_sensitive: bool, whole_word: bool) -> str:
        """Perform the actual text replacement."""
        if whole_word:
            if case_sensitive:
                pattern = r'\b' + re.escape(find) + r'\b'
                return re.sub(pattern, replace, text)
            else:
                pattern = r'\b' + re.escape(find) + r'\b'
                return re.sub(pattern, replace, text, flags=re.IGNORECASE)
        else:
            if case_sensitive:
                return text.replace(find, replace)
            else:
                # Case-insensitive replace
                pattern = re.escape(find)
                return re.sub(pattern, replace, text, flags=re.IGNORECASE)
    
    # =========================================================================
    # Context Menu
    # =========================================================================
    
    def _show_context_menu(self, pos):
        """Show right-click context menu."""
        menu = QMenu(self)
        menu.addAction("Insert Row Above", self._insert_row_above)
        menu.addAction("Insert Row Below", self._insert_row_below)
        menu.addSeparator()
        menu.addAction("Duplicate Row (Ctrl+Shift+D)", self._duplicate_row)
        menu.addAction("Delete Row(s) (Ctrl+Shift+Del)", self._delete_selected_rows)
        menu.addSeparator()
        menu.addAction("Copy (Ctrl+C)", self._copy)
        menu.addAction("Cut (Ctrl+X)", self._cut)
        menu.addAction("Paste (Ctrl+V)", self._paste)
        menu.addSeparator()
        menu.addAction("Fill Down (Ctrl+D)", self._fill_down)
        menu.addSeparator()
        menu.addAction("Re-lookup Species", self._relookup_species)
        menu.exec(self.viewport().mapToGlobal(pos))
    
    def _relookup_species(self):
        """Re-lookup species for selected rows."""
        rows = set(idx.row() for idx in self.selectedIndexes())
        for row in rows:
            species_item = self.item(row, COL_SPECIES)
            if species_item and species_item.text():
                self._lookup_species(row, species_item.text())
            
            gr_item = self.item(row, COL_GRID_REF)
            if gr_item and gr_item.text():
                self._validate_and_lookup_vc(row, gr_item.text())
        
        self.status_message.emit(f"Re-looked up {len(rows)} row(s)")
    
    # =========================================================================
    # Data Access
    # =========================================================================
    
    def get_all_rows(self) -> List[List[str]]:
        """Get all row data as list of lists."""
        return [self._get_row_data(row) for row in range(self.rowCount())]
    
    def set_rows(self, rows: List[List[str]]):
        """Set table data from list of rows."""
        self.setRowCount(0)
        self._undo_manager.clear()
        
        for row_data in rows:
            row = self.rowCount()
            self.insertRow(row)
            
            self.blockSignals(True)
            for col, value in enumerate(row_data):
                if col < self.columnCount():
                    item = QTableWidgetItem(str(value) if value else '')
                    if col in AUTO_POPULATED_COLS:
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                        item.setBackground(QColor(COLORS['readonly_bg']))
                    self.setItem(row, col, item)
            self.blockSignals(False)
            
            gr_item = self.item(row, COL_GRID_REF)
            if gr_item and gr_item.text():
                self._validate_and_lookup_vc(row, gr_item.text())
        
        self._emit_row_count()
    
    def clear_all(self):
        """Clear all rows."""
        from PySide6.QtWidgets import QMessageBox
        if self.rowCount() == 0:
            return
        
        reply = QMessageBox.question(
            self, "Clear All", f"Delete all {self.rowCount()} rows?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.setRowCount(0)
            self._undo_manager.clear()
            self._emit_row_count()
    
    def _emit_row_count(self):
        """Emit row count signal."""
        total = self.rowCount()
        data_rows = sum(
            1 for row in range(total)
            if self.item(row, COL_SPECIES) and self.item(row, COL_SPECIES).text().strip()
        )
        self.row_count_changed.emit(total, data_rows)
    
    def apply_sticky_defaults(self, defaults: dict):
        """Apply sticky defaults to selected empty cells."""
        selection = self.selectedIndexes()
        
        self._undo_manager.begin_action(ActionType.MULTI_CELL_EDIT, "Apply defaults")
        self.blockSignals(True)
        
        for idx in selection:
            col = idx.column()
            if col in defaults and col not in AUTO_POPULATED_COLS:
                item = self.item(idx.row(), idx.column())
                if item and not item.text():
                    old_val = item.text()
                    new_val = str(defaults[col])
                    if old_val != new_val:
                        self._undo_manager.record_cell_change(idx.row(), col, old_val, new_val)
                        item.setText(new_val)
        
        self.blockSignals(False)
        self._undo_manager.end_action()
