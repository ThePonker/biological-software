"""
Collection Header Component.

Displays collection name and statistics at the top of the Insect Collection tab.
"""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel

from ...core.config import TabColors
from ...themes import theme


class CollectionHeader(QFrame):
    """Header showing collection statistics."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        t = theme()
        
        self.setStyleSheet(f"""
            CollectionHeader {{
                background-color: {TabColors.COLLECTION_LIGHT};
                border-bottom: 1px solid {t.get('border')};
            }}
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        
        # Collection name
        name_layout = QHBoxLayout()
        name_layout.setSpacing(12)
        
        self.collection_name = QLabel("Insect Collection")
        self.collection_name.setStyleSheet(f"font-weight: bold; color: {TabColors.COLLECTION}; font-size: 14px;")
        name_layout.addWidget(self.collection_name)
        
        self.collection_desc = QLabel("Personal specimen database")
        self.collection_desc.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 12px;")
        name_layout.addWidget(self.collection_desc)
        
        layout.addLayout(name_layout)
        layout.addStretch()
        
        # Stats
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(16)
        
        self.species_label = QLabel("<b>0</b> species")
        self.species_label.setStyleSheet(f"color: {TabColors.COLLECTION}; font-size: 12px;")
        stats_layout.addWidget(self.species_label)
        
        self.specimens_label = QLabel("<b>0</b> specimens")
        self.specimens_label.setStyleSheet(f"color: {TabColors.COLLECTION}; font-size: 12px;")
        stats_layout.addWidget(self.specimens_label)
        
        layout.addLayout(stats_layout)
    
    def set_stats(self, species_count: int, specimen_count: int):
        """Update the statistics display."""
        self.species_label.setText(f"<b>{species_count}</b> species")
        self.specimens_label.setText(f"<b>{specimen_count}</b> specimens")
    
    def apply_theme(self):
        """Apply the current theme."""
        t = theme()
        
        self.setStyleSheet(f"""
            CollectionHeader {{
                background-color: {TabColors.COLLECTION_LIGHT};
                border-bottom: 1px solid {t.get('border')};
            }}
        """)
        self.collection_name.setStyleSheet(f"font-weight: bold; color: {TabColors.COLLECTION}; font-size: 14px;")
        self.collection_desc.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 12px;")
        self.species_label.setStyleSheet(f"color: {TabColors.COLLECTION}; font-size: 12px;")
        self.specimens_label.setStyleSheet(f"color: {TabColors.COLLECTION}; font-size: 12px;")
