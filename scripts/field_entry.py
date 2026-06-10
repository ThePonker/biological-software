#!/usr/bin/env python3
"""
Field Entry Tool for Observatum V2
Rapid post-visit data entry with UKSI species autocomplete.
Excel-like interface for efficient bulk entry.

Run: python scripts/field_entry.py
"""

import sys
import csv
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QLineEdit, QComboBox, QSpinBox,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QCompleter, QFrame, QFileDialog, QMessageBox, QMenu,
    QAbstractItemView, QStyledItemDelegate, QDialog, QListWidget
)
from PySide6.QtCore import Qt, QStringListModel, Signal, QEvent
from PySide6.QtGui import QFont, QColor, QKeySequence, QAction, QShortcut


# =============================================================================
# CONSTANTS
# =============================================================================

SEX_OPTIONS = ['', 'Female', 'Male', 'Mixed', 'Not recorded']
STAGE_OPTIONS = ['', 'Adult', 'Larva', 'Pupa', 'Egg', 'Nymph', 'Teneral', 'Not recorded']
CERTAINTY_OPTIONS = ['', 'Certain', 'Likely', 'Uncertain']
SAMPLE_METHOD_OPTIONS = [
    '', 'Hand search', 'Sweep-net', 'Beating', 'Light trap', 'Pitfall trap',
    'Malaise trap', 'Flight interception trap', 'Pheromone trap', 'Window trap',
    'Emergence trap', 'Water trap', 'Suction trap', 'Reared', 'Photography',
    'Sound recording', 'Casual observation', 'Other'
]
OBSERVATION_TYPE_OPTIONS = [
    '', 'Field sighting', 'Field record', 'Specimen collected', 
    'Photograph', 'Literature record', 'Museum specimen', 'Other'
]

# Column definitions: (name, width, editable, combo_options)
COLUMNS = [
    ('Species', 200, True, None),
    ('TVK', 120, False, None),
    ('Common Name', 140, False, None),
    ('Family', 100, False, None),
    ('Order', 100, False, None),
    ('Date', 90, True, None),
    ('Location', 140, True, None),
    ('Grid Ref', 80, True, None),
    ('Qty', 45, True, None),
    ('Sex', 70, True, SEX_OPTIONS),
    ('Stage', 75, True, STAGE_OPTIONS),
    ('Method', 100, True, SAMPLE_METHOD_OPTIONS),
    ('Type', 100, True, OBSERVATION_TYPE_OPTIONS),
    ('Certainty', 80, True, CERTAINTY_OPTIONS),
    ('Recorder', 100, True, None),
    ('Determiner', 100, True, None),
    ('Comment', 150, True, None),
]

COLORS = {
    'bg': '#f8f8f8',
    'surface': '#ffffff',
    'border': '#d0d0d0',
    'header_bg': '#e8e4dc',
    'header_text': '#4a4a4a',
    'readonly_bg': '#f5f5f0',
    'accent': '#4a7c59',
    'text': '#333333',
    'grid': '#e0e0e0',
}


# =============================================================================
# UKSI DATABASE
# =============================================================================

class UKSILookup:
    """UKSI database interface for species autocomplete."""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
    
    def connect(self) -> bool:
        if not self.db_path.exists():
            return False
        try:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            return True
        except Exception as e:
            print(f"DB connect error: {e}")
            return False
    
    def search(self, term: str, limit: int = 15) -> List[str]:
        """Fuzzy search species by scientific name OR common name."""
        if not self._conn or len(term) < 2:
            return []
        try:
            terms = term.strip().split()
            search_pattern = f"%{term}%"
            
            if len(terms) == 1:
                # Single term - search scientific name and common name
                cursor = self._conn.execute("""
                    SELECT t.scientific_name, c.common_name, 
                           CASE WHEN t.scientific_name LIKE ? THEN 0 
                                WHEN c.common_name LIKE ? THEN 1
                                ELSE 2 END as priority
                    FROM taxa t
                    LEFT JOIN common_names c ON t.tvk = c.tvk
                    WHERE t.rank = 'Species' 
                      AND (t.scientific_name LIKE ? OR c.common_name LIKE ?)
                    ORDER BY priority, t.scientific_name
                    LIMIT ?
                """, (f"{term}%", f"{term}%", search_pattern, search_pattern, limit))
            else:
                # Multi-term - require both parts for better matching
                # For common names: "mute swan" should match "Mute Swan"
                combined_scientific = f"%{terms[0]}%{terms[1]}%"
                combined_common = f"%{terms[0]}%{terms[1]}%"
                
                cursor = self._conn.execute("""
                    SELECT t.scientific_name, c.common_name,
                           CASE WHEN t.scientific_name LIKE ? THEN 0 
                                WHEN c.common_name LIKE ? THEN 1
                                ELSE 2 END as priority
                    FROM taxa t
                    LEFT JOIN common_names c ON t.tvk = c.tvk
                    WHERE t.rank = 'Species' 
                      AND (t.scientific_name LIKE ? OR c.common_name LIKE ?)
                    ORDER BY priority, t.scientific_name
                    LIMIT ?
                """, (combined_scientific, combined_common, combined_scientific, combined_common, limit))
            
            # Return "Scientific Name (Common Name)" or just "Scientific Name"
            seen = set()
            results = []
            for row in cursor.fetchall():
                scientific = row[0]
                common = row[1]
                if scientific not in seen:
                    seen.add(scientific)
                    if common:
                        results.append(f"{scientific} ({common})")
                    else:
                        results.append(scientific)
            
            return results
        except Exception as e:
            print(f"Search error: {e}")
            return []
    
    def lookup(self, name: str) -> Optional[Dict[str, str]]:
        """Get full species details by exact name, walking hierarchy for family/order."""
        if not self._conn or not name:
            return None
        try:
            cursor = self._conn.execute("""
                SELECT tvk, scientific_name, rank, parent_tvk
                FROM taxa WHERE scientific_name = ? AND rank = 'Species'
            """, (name.strip(),))
            row = cursor.fetchone()
            if not row:
                return None
            
            species_tvk = row['tvk']
            
            # Get common name
            common = self._conn.execute(
                "SELECT common_name FROM common_names WHERE tvk = ? LIMIT 1",
                (species_tvk,)
            ).fetchone()
            
            # Walk up hierarchy to find Family and Order
            family = ''
            order = ''
            parent_tvk = row['parent_tvk']
            
            for _ in range(10):  # Max 10 levels up
                if not parent_tvk:
                    break
                parent = self._conn.execute("""
                    SELECT scientific_name, rank, parent_tvk
                    FROM taxa WHERE tvk = ?
                """, (parent_tvk,)).fetchone()
                
                if not parent:
                    break
                
                if parent['rank'] == 'Family' and not family:
                    family = parent['scientific_name']
                elif parent['rank'] == 'Order' and not order:
                    order = parent['scientific_name']
                
                # Stop if we have both
                if family and order:
                    break
                
                parent_tvk = parent['parent_tvk']
            
            result = {
                'tvk': species_tvk or '',
                'scientific_name': row['scientific_name'] or '',
                'family': family,
                'order': order,
                'common_name': common['common_name'] if common else '',
            }
            return result
        except Exception as e:
            print(f"Lookup error: {e}")
            return None
    
    def close(self):
        if self._conn:
            self._conn.close()


# =============================================================================
# CUSTOM TABLE DELEGATES
# =============================================================================

class SpeciesSearchDialog(QDialog):
    """Dialog for selecting from multiple species matches."""
    
    def __init__(self, matches: List[str], search_term: str, uksi: 'UKSILookup', parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Species")
        self.setMinimumWidth(500)
        self.setMinimumHeight(300)
        self.selected = None
        self._uksi = uksi
        
        layout = QVBoxLayout(self)
        
        label = QLabel(f"Multiple matches for '{search_term}':")
        layout.addWidget(label)
        
        # Use a table to show scientific name + common name
        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
        
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Scientific Name", "Common Name"])
        self.table.setRowCount(len(matches))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self._on_double_click)
        
        # Populate with matches - parse "Scientific (Common)" format
        for i, match in enumerate(matches):
            if '(' in match and match.endswith(')'):
                # Format: "Scientific Name (Common Name)"
                scientific = match.split('(')[0].strip()
                common = match[match.index('(')+1:-1]
            else:
                scientific = match
                common = ''
            self.table.setItem(i, 0, QTableWidgetItem(scientific))
            self.table.setItem(i, 1, QTableWidgetItem(common))
        
        self.table.selectRow(0)
        layout.addWidget(self.table)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        select_btn = QPushButton("Select")
        select_btn.setDefault(True)
        select_btn.clicked.connect(self._on_select)
        btn_layout.addWidget(select_btn)
        
        layout.addLayout(btn_layout)
    
    def _on_double_click(self, index):
        row = index.row()
        item = self.table.item(row, 0)
        if item:
            self.selected = item.text()
            self.accept()
    
    def _on_select(self):
        row = self.table.currentRow()
        if row >= 0:
            item = self.table.item(row, 0)
            if item:
                self.selected = item.text()
                self.accept()


class SpeciesDelegate(QStyledItemDelegate):
    """Delegate for species column - lookup on commit."""
    
    def __init__(self, uksi: UKSILookup, table: QTableWidget, parent=None):
        super().__init__(parent)
        self._uksi = uksi
        self._table = table
    
    def _extract_scientific_name(self, text: str) -> str:
        """Extract scientific name from 'Scientific Name (Common Name)' format."""
        if '(' in text and text.endswith(')'):
            return text.split('(')[0].strip()
        return text.strip()
    
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setFrame(False)
        return editor
    
    def setEditorData(self, editor, index):
        value = index.data(Qt.ItemDataRole.EditRole) or ''
        editor.setText(value)
    
    def setModelData(self, editor, model, index):
        text = editor.text().strip()
        
        if not text:
            model.setData(index, '', Qt.ItemDataRole.EditRole)
            return
        
        # Search for matches
        matches = self._uksi.search(text, limit=20)
        
        if not matches:
            # No matches - keep the text but warn
            model.setData(index, text, Qt.ItemDataRole.EditRole)
            QMessageBox.warning(
                self._table, "Species Not Found",
                f"No species found matching '{text}'.\n\nThe text has been kept - you can edit it."
            )
            return
        
        # Check for exact match first (compare scientific names only)
        exact = None
        for m in matches:
            scientific = self._extract_scientific_name(m)
            if scientific.lower() == text.lower():
                exact = m
                break
        
        if exact:
            # Exact match - use it
            selected = exact
        elif len(matches) == 1:
            # Only one match - use it
            selected = matches[0]
        else:
            # Multiple matches - show dialog
            dialog = SpeciesSearchDialog(matches, text, self._uksi, self._table)
            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected:
                selected = dialog.selected
            else:
                # User cancelled - keep original text
                model.setData(index, text, Qt.ItemDataRole.EditRole)
                return
        
        # Extract scientific name (remove common name suffix if present)
        scientific_name = self._extract_scientific_name(selected)
        
        # Set the scientific name in the cell
        model.setData(index, scientific_name, Qt.ItemDataRole.EditRole)
        
        # Lookup full details and populate other columns
        row = index.row()
        info = self._uksi.lookup(scientific_name)
        if info:
            self._table.item(row, 1).setText(info['tvk'])
            self._table.item(row, 2).setText(info['common_name'])
            self._table.item(row, 3).setText(info['family'])
            self._table.item(row, 4).setText(info['order'])


class ComboDelegate(QStyledItemDelegate):
    """Delegate that shows combo box for columns with options."""
    
    def __init__(self, options: List[str], parent=None):
        super().__init__(parent)
        self.options = options
    
    def createEditor(self, parent, option, index):
        combo = QComboBox(parent)
        combo.addItems(self.options)
        combo.setFrame(False)
        return combo
    
    def setEditorData(self, editor, index):
        value = index.data(Qt.ItemDataRole.EditRole) or ''
        idx = editor.findText(value)
        editor.setCurrentIndex(idx if idx >= 0 else 0)
    
    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)


# =============================================================================
# MAIN WINDOW
# =============================================================================

class FieldEntryWindow(QMainWindow):
    """Excel-like field entry window."""
    
    def __init__(self, uksi: UKSILookup):
        super().__init__()
        self._uksi = uksi
        self._sticky = {}  # Sticky default values
        self._completer_model = QStringListModel()
        
        self.setWindowTitle("Observatum Field Entry")
        self.setMinimumSize(1200, 700)
        self._setup_ui()
        self._setup_shortcuts()
        self._update_row_count()  # Show initial message
        self.showMaximized()  # Open maximized
    
    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        central.setStyleSheet(f"background-color: {COLORS['bg']};")
        
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        
        # Header bar with sticky defaults
        self._setup_header(layout)
        
        # Main table
        self._setup_table(layout)
        
        # Button bar
        self._setup_buttons(layout)
    
    def _setup_header(self, layout):
        """Compact sticky defaults bar."""
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{ 
                background: {COLORS['surface']}; 
                border: 1px solid {COLORS['border']}; 
                border-radius: 4px; 
            }}
            QLabel {{ font-size: 10px; color: {COLORS['header_text']}; }}
            QLineEdit, QComboBox {{ 
                font-size: 11px; 
                padding: 3px 5px; 
                border: 1px solid {COLORS['border']}; 
                border-radius: 2px;
                background: white;
            }}
        """)
        
        grid = QGridLayout(frame)
        grid.setContentsMargins(8, 6, 8, 6)
        grid.setSpacing(4)
        
        self._sticky_widgets = {}
        
        # Row 1: Text fields
        fields = [
            ('date', 'Date:', datetime.now().strftime('%Y-%m-%d'), 85),
            ('location', 'Location:', '', 120),
            ('grid_ref', 'Grid Ref:', '', 75),
            ('recorder', 'Recorder:', '', 100),
            ('determiner', 'Determiner:', '', 100),
        ]
        
        col = 0
        for key, label, default, width in fields:
            grid.addWidget(QLabel(label), 0, col)
            edit = QLineEdit(default)
            edit.setFixedWidth(width)
            edit.textChanged.connect(lambda t, k=key: self._sticky.__setitem__(k, t))
            self._sticky_widgets[key] = edit
            self._sticky[key] = default
            grid.addWidget(edit, 1, col)
            col += 1
        
        # Row 1 continued: Combo fields
        combos = [
            ('sex', 'Sex:', SEX_OPTIONS, 65),
            ('stage', 'Stage:', STAGE_OPTIONS, 70),
            ('method', 'Method:', SAMPLE_METHOD_OPTIONS, 90),
            ('obs_type', 'Type:', OBSERVATION_TYPE_OPTIONS, 90),
            ('certainty', 'Cert:', CERTAINTY_OPTIONS, 70),
        ]
        
        for key, label, options, width in combos:
            grid.addWidget(QLabel(label), 0, col)
            combo = QComboBox()
            combo.addItems(options)
            combo.setFixedWidth(width)
            combo.currentTextChanged.connect(lambda t, k=key: self._sticky.__setitem__(k, t))
            self._sticky_widgets[key] = combo
            self._sticky[key] = ''
            grid.addWidget(combo, 1, col)
            col += 1
        
        layout.addWidget(frame)
    
    def _setup_table(self, layout):
        """Setup Excel-like table."""
        self.table = QTableWidget()
        self.table.setColumnCount(len(COLUMNS))
        self.table.setHorizontalHeaderLabels([c[0] for c in COLUMNS])
        
        # Styling
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background: {COLORS['surface']};
                gridline-color: {COLORS['grid']};
                font-size: 11px;
                border: 1px solid {COLORS['border']};
            }}
            QTableWidget::item {{
                padding: 2px 4px;
            }}
            QTableWidget::item:selected {{
                background: #cce5ff;
                color: black;
            }}
            QHeaderView::section {{
                background: {COLORS['header_bg']};
                color: {COLORS['header_text']};
                font-weight: bold;
                font-size: 10px;
                padding: 4px;
                border: none;
                border-right: 1px solid {COLORS['border']};
                border-bottom: 1px solid {COLORS['border']};
            }}
        """)
        
        # Column widths
        for i, (_, width, _, _) in enumerate(COLUMNS):
            self.table.setColumnWidth(i, width)
        
        # Behavior
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.setAlternatingRowColors(True)
        
        # Context menu
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        
        # Cell change handler for species lookup
        self.table.cellChanged.connect(self._on_cell_changed)
        
        # Set species delegate for column 0 (lookup on commit)
        self.table.setItemDelegateForColumn(0, SpeciesDelegate(self._uksi, self.table, self.table))
        
        # Set combo delegates for dropdown columns
        for i, (_, _, _, options) in enumerate(COLUMNS):
            if options:
                self.table.setItemDelegateForColumn(i, ComboDelegate(options, self.table))
        
        # Install event filter for Enter key handling
        self.table.installEventFilter(self)
        
        layout.addWidget(self.table, 1)
    
    def eventFilter(self, obj, event):
        """Handle Enter key to jump to next row's Species column."""
        if obj == self.table and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                current_row = self.table.currentRow()
                
                # If no rows or at end, add one
                if self.table.rowCount() == 0:
                    self._add_rows(1)
                    next_row = 0
                else:
                    next_row = current_row + 1
                    if next_row >= self.table.rowCount():
                        self._add_rows(1)
                
                # Move to Species column (0) in next row
                self.table.setCurrentCell(next_row, 0)
                item = self.table.item(next_row, 0)
                if item:
                    self.table.editItem(item)
                return True  # Event handled
        
        return super().eventFilter(obj, event)
    
    def _setup_buttons(self, layout):
        """Bottom button bar."""
        bar = QHBoxLayout()
        bar.setSpacing(8)
        
        # Left side - row count
        self.row_count_label = QLabel("0 rows with data")
        self.row_count_label.setStyleSheet(f"color: {COLORS['header_text']}; font-size: 11px;")
        bar.addWidget(self.row_count_label)
        
        bar.addStretch()
        
        # Right side - buttons
        btn_style = f"""
            QPushButton {{
                font-size: 11px;
                padding: 6px 14px;
                border-radius: 3px;
            }}
        """
        
        add_btn = QPushButton("+ Add Rows")
        add_btn.setStyleSheet(btn_style + f"background: {COLORS['surface']}; border: 1px solid {COLORS['border']};")
        
        # Create menu for row count options
        add_menu = QMenu(add_btn)
        for count in [5, 10, 25, 50]:
            action = add_menu.addAction(f"Add {count} rows")
            action.triggered.connect(lambda checked, c=count: self._add_rows(c))
        add_btn.setMenu(add_menu)
        bar.addWidget(add_btn)
        
        clear_btn = QPushButton("Clear All")
        clear_btn.setStyleSheet(btn_style + f"background: {COLORS['surface']}; border: 1px solid {COLORS['border']};")
        clear_btn.clicked.connect(self._clear_all)
        bar.addWidget(clear_btn)
        
        export_btn = QPushButton("Export CSV")
        export_btn.setStyleSheet(btn_style + f"background: {COLORS['accent']}; color: white; border: none;")
        export_btn.clicked.connect(self._export_csv)
        bar.addWidget(export_btn)
        
        layout.addLayout(bar)
    
    def _setup_shortcuts(self):
        """Keyboard shortcuts."""
        # Ctrl+D = Delete selected rows
        del_shortcut = QShortcut(QKeySequence("Ctrl+D"), self)
        del_shortcut.activated.connect(self._delete_selected_rows)
        
        # Ctrl+Shift+D = Duplicate row
        dup_shortcut = QShortcut(QKeySequence("Ctrl+Shift+D"), self)
        dup_shortcut.activated.connect(self._duplicate_row)
        
        # Ctrl+Enter = Apply sticky values to selection
        apply_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        apply_shortcut.activated.connect(self._apply_sticky_to_selection)
    
    def _add_rows(self, count: int):
        """Add new rows with sticky defaults."""
        self.table.blockSignals(True)
        start = self.table.rowCount()
        self.table.setRowCount(start + count)
        
        for row in range(start, start + count):
            self._init_row(row)
        
        self.table.blockSignals(False)
        self._update_row_count()
    
    def _init_row(self, row: int):
        """Initialize a single row."""
        for col, (name, _, editable, options) in enumerate(COLUMNS):
            item = QTableWidgetItem()
            
            # Set default values from sticky
            if name == 'Date':
                item.setText(self._sticky.get('date', ''))
            elif name == 'Location':
                item.setText(self._sticky.get('location', ''))
            elif name == 'Grid Ref':
                item.setText(self._sticky.get('grid_ref', ''))
            elif name == 'Qty':
                item.setText('1')
            elif name == 'Sex':
                item.setText(self._sticky.get('sex', ''))
            elif name == 'Stage':
                item.setText(self._sticky.get('stage', ''))
            elif name == 'Method':
                item.setText(self._sticky.get('method', ''))
            elif name == 'Type':
                item.setText(self._sticky.get('obs_type', ''))
            elif name == 'Certainty':
                item.setText(self._sticky.get('certainty', ''))
            elif name == 'Recorder':
                item.setText(self._sticky.get('recorder', ''))
            elif name == 'Determiner':
                item.setText(self._sticky.get('determiner', ''))
            
            # Read-only columns
            if not editable:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setBackground(QColor(COLORS['readonly_bg']))
            
            self.table.setItem(row, col, item)
    
    def _on_cell_changed(self, row: int, col: int):
        """Handle cell changes."""
        if col == 0:
            # Species column - clear auto-populated fields if empty
            species_name = self.table.item(row, 0).text().strip()
            if not species_name:
                self.table.blockSignals(True)
                for c in [1, 2, 3, 4]:  # TVK, Common, Family, Order
                    item = self.table.item(row, c)
                    if item:
                        item.setText('')
                self.table.blockSignals(False)
        
        self._update_row_count()
    
    def _show_context_menu(self, pos):
        """Right-click context menu."""
        menu = QMenu(self)
        
        menu.addAction("Insert Row Above", self._insert_row_above)
        menu.addAction("Insert Row Below", self._insert_row_below)
        menu.addSeparator()
        menu.addAction("Duplicate Row (Ctrl+Shift+D)", self._duplicate_row)
        menu.addAction("Delete Row(s) (Ctrl+D)", self._delete_selected_rows)
        menu.addSeparator()
        menu.addAction("Apply Defaults to Selection (Ctrl+Enter)", self._apply_sticky_to_selection)
        menu.addSeparator()
        menu.addAction("Lookup Species", self._lookup_selected_species)
        
        menu.exec(self.table.viewport().mapToGlobal(pos))
    
    def _insert_row_above(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.insertRow(row)
            self._init_row(row)
    
    def _insert_row_below(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.insertRow(row + 1)
            self._init_row(row + 1)
    
    def _duplicate_row(self):
        """Duplicate the current row."""
        row = self.table.currentRow()
        if row < 0:
            return
        
        self.table.insertRow(row + 1)
        for col in range(self.table.columnCount()):
            orig = self.table.item(row, col)
            new_item = QTableWidgetItem(orig.text() if orig else '')
            if not COLUMNS[col][2]:  # Not editable
                new_item.setFlags(new_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                new_item.setBackground(QColor(COLORS['readonly_bg']))
            self.table.setItem(row + 1, col, new_item)
    
    def _delete_selected_rows(self):
        """Delete selected rows."""
        rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()), reverse=True)
        if not rows:
            return
        
        for row in rows:
            self.table.removeRow(row)
        
        self._update_row_count()
    
    def _apply_sticky_to_selection(self):
        """Apply sticky defaults to selected cells."""
        col_mapping = {
            5: 'date', 6: 'location', 7: 'grid_ref',
            9: 'sex', 10: 'stage', 11: 'method', 12: 'obs_type', 13: 'certainty',
            14: 'recorder', 15: 'determiner'
        }
        
        for idx in self.table.selectedIndexes():
            col = idx.column()
            if col in col_mapping:
                key = col_mapping[col]
                value = self._sticky.get(key, '')
                self.table.item(idx.row(), col).setText(value)
    
    def _lookup_selected_species(self):
        """Force lookup for selected species cells."""
        def extract_scientific(text):
            """Extract scientific name from 'Scientific (Common)' format."""
            if '(' in text and text.endswith(')'):
                return text.split('(')[0].strip()
            return text.strip()
        
        for idx in self.table.selectedIndexes():
            if idx.column() == 0:
                row = idx.row()
                species_name = self.table.item(row, 0).text().strip()
                if species_name:
                    # Search and populate
                    matches = self._uksi.search(species_name, limit=20)
                    if matches:
                        # Check for exact match (compare scientific names)
                        selected = None
                        for m in matches:
                            scientific = extract_scientific(m)
                            if scientific.lower() == species_name.lower():
                                selected = m
                                break
                        
                        if not selected:
                            if len(matches) == 1:
                                selected = matches[0]
                            else:
                                dialog = SpeciesSearchDialog(matches, species_name, self._uksi, self)
                                if dialog.exec() == QDialog.DialogCode.Accepted:
                                    selected = dialog.selected
                        
                        if selected:
                            scientific = extract_scientific(selected)
                            self.table.item(row, 0).setText(scientific)
                            info = self._uksi.lookup(scientific)
                            if info:
                                self.table.item(row, 1).setText(info['tvk'])
                                self.table.item(row, 2).setText(info['common_name'])
                                self.table.item(row, 3).setText(info['family'])
                                self.table.item(row, 4).setText(info['order'])
    
    def _update_row_count(self):
        """Update the row count label."""
        data_count = 0
        for row in range(self.table.rowCount()):
            species = self.table.item(row, 0)
            if species and species.text().strip():
                data_count += 1
        total = self.table.rowCount()
        if total == 0:
            self.row_count_label.setText("No rows - click '+ Add Rows' to start")
        else:
            self.row_count_label.setText(f"{data_count} of {total} rows with data")
    
    def _clear_all(self):
        if QMessageBox.question(self, "Clear All", "Delete all entries?") == QMessageBox.StandardButton.Yes:
            self.table.setRowCount(0)
            self._update_row_count()
    
    def _export_csv(self):
        """Export to CSV."""
        rows_data = []
        for row in range(self.table.rowCount()):
            species = self.table.item(row, 0)
            if not species or not species.text().strip():
                continue
            
            row_data = {}
            keys = ['species_name', 'tvk', 'common_name', 'family', 'order',
                    'date', 'location', 'grid_ref', 'quantity',
                    'sex', 'stage', 'sample_method', 'observation_type', 'certainty',
                    'recorder', 'determiner', 'comment']
            
            for col, key in enumerate(keys):
                item = self.table.item(row, col)
                row_data[key] = item.text() if item else ''
            
            rows_data.append(row_data)
        
        if not rows_data:
            QMessageBox.warning(self, "No Data", "No entries to export.")
            return
        
        filename = f"field_records_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath, _ = QFileDialog.getSaveFileName(self, "Export CSV", filename, "CSV (*.csv)")
        
        if filepath:
            try:
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=rows_data[0].keys())
                    writer.writeheader()
                    writer.writerows(rows_data)
                QMessageBox.information(self, "Done", f"Exported {len(rows_data)} records.")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))


# =============================================================================
# MAIN
# =============================================================================

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Find UKSI database
    paths = [Path('data/uksi.db'), Path('../data/uksi.db')]
    uksi_path = next((p for p in paths if p.exists()), None)
    
    if not uksi_path:
        QMessageBox.critical(None, "Error", "Could not find data/uksi.db")
        return 1
    
    uksi = UKSILookup(uksi_path)
    if not uksi.connect():
        QMessageBox.critical(None, "Error", f"Could not connect to {uksi_path}")
        return 1
    
    window = FieldEntryWindow(uksi)
    window.show()
    
    result = app.exec()
    uksi.close()
    return result


if __name__ == '__main__':
    sys.exit(main())
