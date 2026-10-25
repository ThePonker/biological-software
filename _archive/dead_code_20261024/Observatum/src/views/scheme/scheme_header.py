"""
Scheme Header Component.

Header showing current recording scheme info and stats.
"""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel

from ...core.config import TabColors
from ...themes import theme


class SchemeHeader(QFrame):
    """Header showing current recording scheme info."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        t = theme()
        
        self.setStyleSheet(f"""
            SchemeHeader {{
                background-color: {TabColors.RECORDING_SCHEME_LIGHT};
                border-bottom: 1px solid {t.get('border')};
            }}
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        
        # Scheme name
        name_layout = QHBoxLayout()
        name_layout.setSpacing(12)
        
        self.scheme_name = QLabel("Longhorn Beetle Recording Scheme")
        self.scheme_name.setStyleSheet(f"font-weight: bold; color: {TabColors.RECORDING_SCHEME}; font-size: 14px;")
        name_layout.addWidget(self.scheme_name)
        
        self.scheme_family = QLabel("(Cerambycidae)")
        self.scheme_family.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 12px;")
        name_layout.addWidget(self.scheme_family)
        
        layout.addLayout(name_layout)
        layout.addStretch()
        
        # Stats
        self.stats_label = QLabel("0 records • 0 species")
        self.stats_label.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 12px;")
        layout.addWidget(self.stats_label)
    
    def set_scheme(self, name: str, family: str):
        """Set scheme name and family."""
        self.scheme_name.setText(name)
        self.scheme_family.setText(f"({family})")
    
    def set_stats(self, records: int, species: int):
        """Set record and species counts."""
        self.stats_label.setText(f"{records} records • {species} species")
    
    def apply_theme(self):
        """Apply the current theme."""
        t = theme()
        
        self.setStyleSheet(f"""
            SchemeHeader {{
                background-color: {TabColors.RECORDING_SCHEME_LIGHT};
                border-bottom: 1px solid {t.get('border')};
            }}
        """)
        self.scheme_name.setStyleSheet(f"font-weight: bold; color: {TabColors.RECORDING_SCHEME}; font-size: 14px;")
        self.scheme_family.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 12px;")
        self.stats_label.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 12px;")
