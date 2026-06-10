"""
Settings Sidebar Component.

Left sidebar for settings navigation.
"""

from PySide6.QtWidgets import QFrame, QVBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Qt, Signal

from ...themes import theme


class SettingsSidebar(QFrame):
    """Left sidebar for settings navigation."""
    
    section_changed = Signal(str)
    
    # FIXED: Changed 'databases' to 'database' to match settings_tab.py
    SECTIONS = [
        ('general', '⚙️ General'),
        ('database', '🗄️ Databases'),
        ('sync', '🔄 iRecord Sync'),
        ('export', '📤 Export Settings'),
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._buttons = {}
        self._setup_ui()
        
    def _setup_ui(self):
        t = theme()
        
        self.setFixedWidth(230)
        self.setStyleSheet(f"""
            SettingsSidebar {{
                background-color: {t.get('surface')};
                border-right: 1px solid {t.get('border')};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(4)
        
        # Header
        header = QLabel("SETTINGS")
        header.setStyleSheet(f"""
            font-weight: bold; 
            font-size: {t.font_size('sm')}; 
            color: {t.get('text_secondary')}; 
            letter-spacing: 1px;
        """)
        layout.addWidget(header)
        layout.addSpacing(12)
        
        # Section buttons
        for section_id, label in self.SECTIONS:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setStyleSheet(self._get_button_style())
            btn.clicked.connect(lambda checked, sid=section_id: self._on_section_clicked(sid))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            layout.addWidget(btn)
            self._buttons[section_id] = btn
        
        layout.addStretch()
        
        # Select first section by default
        self._buttons['general'].setChecked(True)
    
    def _get_button_style(self) -> str:
        """Get the button style using current theme."""
        t = theme()
        return f"""
            QPushButton {{
                text-align: left;
                padding: 10px 12px;
                border: none;
                border-radius: {t.get('radius_md')};
                background: transparent;
                color: {t.get('text_secondary')};
                font-size: {t.font_size('base')};
            }}
            QPushButton:hover {{
                background-color: {t.get('hover')};
            }}
            QPushButton:checked {{
                background-color: {t.get('success_bg_light')};
                color: {t.get('success')};
                font-weight: 600;
            }}
        """
    
    def _on_section_clicked(self, section_id: str):
        """Handle section button click."""
        for sid, btn in self._buttons.items():
            btn.setChecked(sid == section_id)
        self.section_changed.emit(section_id)
    
    def apply_theme(self):
        """Apply the current theme to all components."""
        t = theme()
        
        self.setStyleSheet(f"""
            SettingsSidebar {{
                background-color: {t.get('surface')};
                border-right: 1px solid {t.get('border')};
            }}
        """)
        
        # Update header
        header = self.findChild(QLabel)
        if header:
            header.setStyleSheet(f"""
                font-weight: bold; 
                font-size: {t.font_size('sm')}; 
                color: {t.get('text_secondary')}; 
                letter-spacing: 1px;
            """)
        
        # Update buttons
        button_style = self._get_button_style()
        for btn in self._buttons.values():
            btn.setStyleSheet(button_style)
