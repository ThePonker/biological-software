"""
Field Entry App - Find Dialog.

Search dialog for finding text in the table.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QFrame
)
from PySide6.QtCore import Qt, Signal

from .constants import COLORS


class FindDialog(QDialog):
    """
    Find dialog for searching table content.
    
    Signals:
        find_next: Emitted when Find Next is clicked
        find_previous: Emitted when Find Previous is clicked
        find_all: Emitted to highlight all matches
    """
    
    find_next = Signal(str, bool, bool)  # search_text, case_sensitive, whole_word
    find_previous = Signal(str, bool, bool)
    find_all = Signal(str, bool, bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Find")
        self.setFixedWidth(400)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Search input
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("Find:"))
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter search text...")
        self.search_input.setMinimumHeight(28)
        self.search_input.returnPressed.connect(self._on_find_next)
        input_layout.addWidget(self.search_input, 1)
        
        layout.addLayout(input_layout)
        
        # Options
        options_layout = QHBoxLayout()
        
        self.case_sensitive_cb = QCheckBox("Case sensitive")
        options_layout.addWidget(self.case_sensitive_cb)
        
        self.whole_word_cb = QCheckBox("Whole word")
        options_layout.addWidget(self.whole_word_cb)
        
        options_layout.addStretch()
        layout.addLayout(options_layout)
        
        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        layout.addWidget(self.status_label)
        
        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {COLORS['border']};")
        layout.addWidget(sep)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        
        self.find_all_btn = QPushButton("Highlight All")
        self.find_all_btn.clicked.connect(self._on_find_all)
        button_layout.addWidget(self.find_all_btn)
        
        button_layout.addStretch()
        
        self.find_prev_btn = QPushButton("◀ Previous")
        self.find_prev_btn.clicked.connect(self._on_find_previous)
        button_layout.addWidget(self.find_prev_btn)
        
        self.find_next_btn = QPushButton("Next ▶")
        self.find_next_btn.setDefault(True)
        self.find_next_btn.clicked.connect(self._on_find_next)
        button_layout.addWidget(self.find_next_btn)
        
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.close)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
        
        # Apply styling
        self._apply_styling()
    
    def _apply_styling(self):
        """Apply visual styling."""
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['surface']};
            }}
            QLineEdit {{
                padding: 6px 10px;
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                background-color: {COLORS['surface']};
            }}
            QLineEdit:focus {{
                border: 2px solid {COLORS['accent']};
            }}
            QPushButton {{
                padding: 6px 16px;
                border: 1px solid {COLORS['border_strong']};
                border-radius: 4px;
                background-color: {COLORS['surface']};
                min-height: 28px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_alt']};
            }}
            QPushButton:default {{
                background-color: {COLORS['accent']};
                color: white;
                border: none;
            }}
            QPushButton:default:hover {{
                background-color: {COLORS['accent_hover']};
            }}
            QCheckBox {{
                spacing: 6px;
            }}
        """)
    
    def _on_find_next(self):
        """Handle Find Next button."""
        text = self.search_input.text()
        if text:
            self.find_next.emit(
                text,
                self.case_sensitive_cb.isChecked(),
                self.whole_word_cb.isChecked()
            )
    
    def _on_find_previous(self):
        """Handle Find Previous button."""
        text = self.search_input.text()
        if text:
            self.find_previous.emit(
                text,
                self.case_sensitive_cb.isChecked(),
                self.whole_word_cb.isChecked()
            )
    
    def _on_find_all(self):
        """Handle Find All button."""
        text = self.search_input.text()
        if text:
            self.find_all.emit(
                text,
                self.case_sensitive_cb.isChecked(),
                self.whole_word_cb.isChecked()
            )
    
    def set_status(self, message: str, is_error: bool = False):
        """Set the status message."""
        color = COLORS['error_text'] if is_error else COLORS['text_secondary']
        self.status_label.setStyleSheet(f"color: {color}; font-size: 11px;")
        self.status_label.setText(message)
    
    def get_search_text(self) -> str:
        """Get the current search text."""
        return self.search_input.text()
    
    def set_search_text(self, text: str):
        """Set the search text."""
        self.search_input.setText(text)
        self.search_input.selectAll()
    
    def showEvent(self, event):
        """Focus the search input when shown."""
        super().showEvent(event)
        self.search_input.setFocus()
        self.search_input.selectAll()
