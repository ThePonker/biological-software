"""
Field Entry App - Column Management Dialog.

Dialog for showing/hiding columns.
"""

from typing import List

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QScrollArea, QWidget, QGridLayout
)
from PySide6.QtCore import Qt, Signal

from .constants import COLORS, COLUMNS, AUTO_POPULATED_COLS


class ColumnDialog(QDialog):
    """
    Dialog for managing column visibility.
    
    Features:
    - Toggle visibility of each column
    - Quick buttons to show all / hide auto-filled
    """
    
    columns_changed = Signal(list, list)  # (column_order, hidden_columns)
    
    def __init__(self, current_order: List[int], hidden_columns: List[int], parent=None):
        super().__init__(parent)
        
        self._hidden = set(hidden_columns) if hidden_columns else set()
        self._checkboxes = {}
        
        self.setWindowTitle("Show/Hide Columns")
        self.setFixedSize(300, 450)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Instructions
        instructions = QLabel("Check columns to show, uncheck to hide")
        instructions.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        layout.addWidget(instructions)
        
        # Scroll area for checkboxes
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                background: white;
            }}
        """)
        
        container = QWidget()
        grid = QGridLayout(container)
        grid.setSpacing(8)
        grid.setContentsMargins(10, 10, 10, 10)
        
        for i, col_def in enumerate(COLUMNS):
            col_name = col_def[0]
            is_auto = i in AUTO_POPULATED_COLS
            
            checkbox = QCheckBox(col_name)
            checkbox.setChecked(i not in self._hidden)
            
            if is_auto:
                checkbox.setStyleSheet(f"color: {COLORS['text_secondary']};")
                checkbox.setText(f"{col_name} (auto)")
            
            self._checkboxes[i] = checkbox
            grid.addWidget(checkbox, i, 0)
        
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)
        
        # Quick actions
        quick_layout = QHBoxLayout()
        
        show_all_btn = QPushButton("Show All")
        show_all_btn.clicked.connect(self._show_all)
        quick_layout.addWidget(show_all_btn)
        
        hide_auto_btn = QPushButton("Hide Auto-Filled")
        hide_auto_btn.setToolTip("Hide TVK, Common Name, Family, Order, Vice County")
        hide_auto_btn.clicked.connect(self._hide_auto_populated)
        quick_layout.addWidget(hide_auto_btn)
        
        layout.addLayout(quick_layout)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        apply_btn = QPushButton("Apply")
        apply_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['accent']};
                color: white;
                padding: 8px 20px;
                border: none;
                border-radius: 4px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {COLORS['accent_hover']};
            }}
        """)
        apply_btn.clicked.connect(self._apply)
        btn_layout.addWidget(apply_btn)
        
        layout.addLayout(btn_layout)
        
        # Style
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['surface']};
            }}
            QPushButton {{
                padding: 6px 12px;
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                background: {COLORS['surface']};
            }}
            QPushButton:hover {{
                background: {COLORS['surface_alt']};
            }}
        """)
    
    def _show_all(self):
        """Show all columns."""
        for checkbox in self._checkboxes.values():
            checkbox.setChecked(True)
    
    def _hide_auto_populated(self):
        """Hide auto-populated columns."""
        for col_idx, checkbox in self._checkboxes.items():
            if col_idx in AUTO_POPULATED_COLS:
                checkbox.setChecked(False)
    
    def _apply(self):
        """Apply changes and close."""
        hidden = []
        for col_idx, checkbox in self._checkboxes.items():
            if not checkbox.isChecked():
                hidden.append(col_idx)
        
        # Column order stays default (no reordering)
        order = list(range(len(COLUMNS)))
        self.columns_changed.emit(order, hidden)
        self.accept()
