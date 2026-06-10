"""
Field Entry App - Find & Replace Dialog.

Dialog for finding and replacing text in the table.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QCheckBox, QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut

from .constants import COLORS


class FindReplaceDialog(QDialog):
    """
    Find and Replace dialog with options for case sensitivity and whole word matching.
    """
    
    find_next = Signal(str, str, bool, bool)  # find_text, replace_text, case_sensitive, whole_word
    find_previous = Signal(str, str, bool, bool)
    replace_one = Signal(str, str, bool, bool)
    replace_all = Signal(str, str, bool, bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowTitle("Find & Replace")
        self.setFixedSize(420, 200)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        
        self._setup_ui()
        self._setup_shortcuts()
    
    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Find/Replace fields
        grid = QGridLayout()
        grid.setSpacing(8)
        
        grid.addWidget(QLabel("Find:"), 0, 0)
        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText("Text to find...")
        self.find_edit.textChanged.connect(self._on_text_changed)
        grid.addWidget(self.find_edit, 0, 1)
        
        grid.addWidget(QLabel("Replace:"), 1, 0)
        self.replace_edit = QLineEdit()
        self.replace_edit.setPlaceholderText("Replace with...")
        grid.addWidget(self.replace_edit, 1, 1)
        
        layout.addLayout(grid)
        
        # Options
        options_layout = QHBoxLayout()
        
        self.case_check = QCheckBox("Case sensitive")
        options_layout.addWidget(self.case_check)
        
        self.whole_word_check = QCheckBox("Whole word")
        options_layout.addWidget(self.whole_word_check)
        
        options_layout.addStretch()
        layout.addLayout(options_layout)
        
        # Status
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        layout.addWidget(self.status_label)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        self.find_prev_btn = QPushButton("◀ Previous")
        self.find_prev_btn.clicked.connect(self._on_find_previous)
        btn_layout.addWidget(self.find_prev_btn)
        
        self.find_next_btn = QPushButton("Next ▶")
        self.find_next_btn.clicked.connect(self._on_find_next)
        self.find_next_btn.setDefault(True)
        btn_layout.addWidget(self.find_next_btn)
        
        btn_layout.addSpacing(20)
        
        self.replace_btn = QPushButton("Replace")
        self.replace_btn.clicked.connect(self._on_replace_one)
        btn_layout.addWidget(self.replace_btn)
        
        self.replace_all_btn = QPushButton("Replace All")
        self.replace_all_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['accent']};
                color: white;
                padding: 6px 12px;
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['accent_hover']};
            }}
        """)
        self.replace_all_btn.clicked.connect(self._on_replace_all)
        btn_layout.addWidget(self.replace_all_btn)
        
        layout.addLayout(btn_layout)
        
        # Style
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['surface']};
            }}
            QLineEdit {{
                padding: 6px;
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                background: white;
            }}
            QLineEdit:focus {{
                border-color: {COLORS['accent']};
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
    
    def _setup_shortcuts(self):
        """Set up keyboard shortcuts."""
        QShortcut(QKeySequence("Return"), self, self._on_find_next)
        QShortcut(QKeySequence("Shift+Return"), self, self._on_find_previous)
        QShortcut(QKeySequence("Escape"), self, self.close)
    
    def _on_text_changed(self):
        """Clear status when text changes."""
        self.status_label.setText("")
    
    def _get_options(self):
        """Get current search options."""
        return (
            self.find_edit.text(),
            self.replace_edit.text(),
            self.case_check.isChecked(),
            self.whole_word_check.isChecked()
        )
    
    def _on_find_next(self):
        """Handle find next button."""
        if self.find_edit.text():
            self.find_next.emit(*self._get_options())
    
    def _on_find_previous(self):
        """Handle find previous button."""
        if self.find_edit.text():
            self.find_previous.emit(*self._get_options())
    
    def _on_replace_one(self):
        """Handle replace button."""
        if self.find_edit.text():
            self.replace_one.emit(*self._get_options())
    
    def _on_replace_all(self):
        """Handle replace all button."""
        if self.find_edit.text():
            self.replace_all.emit(*self._get_options())
    
    def set_status(self, message: str, is_error: bool = False):
        """Set status message."""
        color = COLORS['error_text'] if is_error else COLORS['text_secondary']
        self.status_label.setStyleSheet(f"color: {color};")
        self.status_label.setText(message)
    
    def showEvent(self, event):
        """Focus find field when shown."""
        super().showEvent(event)
        self.find_edit.setFocus()
        self.find_edit.selectAll()
