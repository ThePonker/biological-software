"""
Card Base Widget.

Base card widget with consistent styling used across Home tab panels.
"""

from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel

from ...themes import theme


class Card(QFrame):
    """Base card widget with consistent styling."""
    
    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self._title = title
        self._header_label = None
        self._header_layout = None
        self._setup_base_style()
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(16, 12, 16, 16)
        self._main_layout.setSpacing(12)
        
        if title:
            self._add_header(title)
    
    def _setup_base_style(self):
        """Set up the base card style."""
        t = theme()
        self.setAutoFillBackground(True)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_lg')};
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)
    
    def _add_header(self, title: str):
        """Add a header label to the card."""
        t = theme()
        
        self._header_layout = QHBoxLayout()
        self._header_layout.setContentsMargins(0, 0, 0, 0)
        
        self._header_label = QLabel(title.upper())
        self._header_label.setStyleSheet(f"""
            font-weight: 600;
            color: {t.get('text_heading')};
            font-size: {t.font_size('sm')};
            letter-spacing: 1px;
            border: none;
            background: transparent;
        """)
        self._header_layout.addWidget(self._header_label)
        self._header_layout.addStretch()
        
        self._main_layout.addLayout(self._header_layout)
    
    def add_header_widget(self, widget):
        """Add a widget to the header row (right side)."""
        if self._header_layout:
            self._header_layout.addWidget(widget)
    
    def add_widget(self, widget):
        """Add a widget to the card layout."""
        self._main_layout.addWidget(widget)
    
    def add_layout(self, layout):
        """Add a layout to the card layout."""
        self._main_layout.addLayout(layout)
    
    def add_stretch(self):
        """Add stretch to the card layout."""
        self._main_layout.addStretch()
    
    def apply_theme(self):
        """Apply the current theme to the card."""
        t = theme()
        
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_lg')};
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        
        if self._header_label:
            self._header_label.setStyleSheet(f"""
                font-weight: 600;
                color: {t.get('text_heading')};
                font-size: {t.font_size('sm')};
                letter-spacing: 1px;
                border: none;
                background: transparent;
            """)
