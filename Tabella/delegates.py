"""
Field Entry App - Table Cell Delegates.

Custom delegates for species autocomplete, combo boxes, and validation.
"""

from PySide6.QtWidgets import (
    QStyledItemDelegate, QLineEdit, QComboBox, QCompleter,
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt, QStringListModel, QTimer
from typing import List, Optional, TYPE_CHECKING

from .constants import COLORS

if TYPE_CHECKING:
    from .uksi_lookup import UKSILookup


class SpeciesSearchDialog(QDialog):
    """Dialog for selecting from multiple species matches."""
    
    def __init__(self, matches: List[str], search_term: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Species")
        self.setMinimumWidth(550)
        self.setMinimumHeight(350)
        self.selected: Optional[str] = None
        
        self._setup_ui(matches, search_term)
    
    def _setup_ui(self, matches: List[str], search_term: str):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        
        label = QLabel(f"Multiple matches for '<b>{search_term}</b>':")
        layout.addWidget(label)
        
        # Results table
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
        
        # Populate table
        for i, match in enumerate(matches):
            if '(' in match and match.endswith(')'):
                scientific = match.split('(')[0].strip()
                common = match[match.index('(') + 1:-1]
            else:
                scientific = match
                common = ''
            
            self.table.setItem(i, 0, QTableWidgetItem(scientific))
            self.table.setItem(i, 1, QTableWidgetItem(common))
        
        self.table.selectRow(0)
        layout.addWidget(self.table)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        select_btn = QPushButton("Select")
        select_btn.setDefault(True)
        select_btn.clicked.connect(self._on_select)
        select_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['accent']};
                color: white;
                padding: 6px 20px;
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['accent_hover']};
            }}
        """)
        btn_layout.addWidget(select_btn)
        
        layout.addLayout(btn_layout)
    
    def _on_double_click(self, index):
        """Handle double-click on row."""
        row = index.row()
        item = self.table.item(row, 0)
        if item:
            self.selected = item.text()
            self.accept()
    
    def _on_select(self):
        """Handle Select button click."""
        row = self.table.currentRow()
        if row >= 0:
            item = self.table.item(row, 0)
            if item:
                self.selected = item.text()
                self.accept()


class SpeciesDelegate(QStyledItemDelegate):
    """
    Delegate for the Species column.
    
    Provides autocomplete from UKSI database and handles species lookup
    when editing is complete.
    """
    
    def __init__(self, uksi: 'UKSILookup', parent=None):
        super().__init__(parent)
        self._uksi = uksi
        self._completer_model = QStringListModel()
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(200)  # Debounce 200ms
        self._current_editor: Optional[QLineEdit] = None
    
    def createEditor(self, parent, option, index):
        """Create editor with autocomplete."""
        editor = QLineEdit(parent)
        editor.setFrame(False)
        
        # Set up completer
        completer = QCompleter(editor)
        completer.setModel(self._completer_model)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        editor.setCompleter(completer)
        
        # Connect text change to search
        self._current_editor = editor
        editor.textChanged.connect(self._on_text_changed)
        self._search_timer.timeout.connect(self._do_search)
        
        return editor
    
    def _on_text_changed(self, text: str):
        """Handle text change - debounce search."""
        self._search_timer.start()
    
    def _do_search(self):
        """Perform the actual search."""
        if self._current_editor:
            text = self._current_editor.text()
            if len(text) >= 2:
                matches = self._uksi.search(text, limit=15)
                self._completer_model.setStringList(matches)
    
    def setEditorData(self, editor, index):
        """Set editor data from model."""
        value = index.data(Qt.ItemDataRole.EditRole) or ''
        editor.setText(value)
    
    def setModelData(self, editor, model, index):
        """
        Commit editor data to model.
        
        Handles species lookup and validation.
        """
        from PySide6.QtWidgets import QMessageBox
        
        text = editor.text().strip()
        
        if not text:
            model.setData(index, '', Qt.ItemDataRole.EditRole)
            return
        
        # Extract scientific name if in "Scientific (Common)" format
        scientific_name = self._uksi.extract_scientific_name(text)
        
        # Search for matches
        matches = self._uksi.search(scientific_name, limit=20)
        
        if not matches:
            # No matches - warn but keep the text
            model.setData(index, text, Qt.ItemDataRole.EditRole)
            QMessageBox.warning(
                editor, "Species Not Found",
                f"No species found matching '{text}'.\n\n"
                "The text has been kept - you can edit it later."
            )
            return
        
        # Check for exact match
        exact = None
        for m in matches:
            sci = self._uksi.extract_scientific_name(m)
            if sci.lower() == scientific_name.lower():
                exact = m
                break
        
        if exact:
            selected = exact
        elif len(matches) == 1:
            selected = matches[0]
        else:
            # Multiple matches - show dialog
            dialog = SpeciesSearchDialog(matches, scientific_name, editor)
            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected:
                selected = dialog.selected
            else:
                # User cancelled - keep original text
                model.setData(index, text, Qt.ItemDataRole.EditRole)
                return
        
        # Extract final scientific name
        final_name = self._uksi.extract_scientific_name(selected)
        model.setData(index, final_name, Qt.ItemDataRole.EditRole)
        
        # Signal that we have a valid species selected
        # The table will handle the auto-population of other columns
    
    def destroyEditor(self, editor, index):
        """Clean up when editor is destroyed."""
        self._search_timer.stop()
        self._current_editor = None
        super().destroyEditor(editor, index)


class ComboDelegate(QStyledItemDelegate):
    """Delegate that shows a combo box for columns with dropdown options."""
    
    def __init__(self, options: List[str], parent=None):
        super().__init__(parent)
        self.options = options
    
    def createEditor(self, parent, option, index):
        """Create combo box editor."""
        combo = QComboBox(parent)
        combo.addItems(self.options)
        combo.setFrame(False)
        return combo
    
    def setEditorData(self, editor, index):
        """Set current selection from model."""
        value = index.data(Qt.ItemDataRole.EditRole) or ''
        idx = editor.findText(value)
        editor.setCurrentIndex(idx if idx >= 0 else 0)
    
    def setModelData(self, editor, model, index):
        """Commit selection to model."""
        model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)


class DateDelegate(QStyledItemDelegate):
    """Delegate for date column with format hints."""
    
    def createEditor(self, parent, option, index):
        """Create date editor."""
        editor = QLineEdit(parent)
        editor.setFrame(False)
        editor.setPlaceholderText("YYYY-MM-DD")
        return editor
    
    def setEditorData(self, editor, index):
        """Set editor value."""
        value = index.data(Qt.ItemDataRole.EditRole) or ''
        editor.setText(value)
    
    def setModelData(self, editor, model, index):
        """Commit and normalize date."""
        text = editor.text().strip()
        
        # Try to normalize common date formats
        if text:
            # Simple validation - just check it's not obviously wrong
            # More complex validation happens elsewhere
            pass
        
        model.setData(index, text, Qt.ItemDataRole.EditRole)


class QuantityDelegate(QStyledItemDelegate):
    """Delegate for quantity column - numbers only."""
    
    def createEditor(self, parent, option, index):
        """Create editor."""
        editor = QLineEdit(parent)
        editor.setFrame(False)
        return editor
    
    def setEditorData(self, editor, index):
        """Set editor value."""
        value = index.data(Qt.ItemDataRole.EditRole) or ''
        editor.setText(value)
    
    def setModelData(self, editor, model, index):
        """Commit and validate as number."""
        text = editor.text().strip()
        
        # Try to convert to int, default to 1 if invalid
        try:
            qty = int(text) if text else 1
            if qty < 1:
                qty = 1
            text = str(qty)
        except ValueError:
            text = '1'
        
        model.setData(index, text, Qt.ItemDataRole.EditRole)
