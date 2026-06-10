"""
Map Header component for Observatum V2.

Displays current map configuration including species name,
view mode, grid size, data source, and grid count.
"""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel

from ...themes import theme
from ...core.config import TabColors


class MapHeader(QFrame):
    """Header showing current map configuration."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        t = theme()
        self._accent = TabColors.MAPPING
        self._accent_light = TabColors.MAPPING_LIGHT
        self._accent_dark = TabColors.MAPPING_DARK
        
        # Tab header style: light background with accent border
        self.setStyleSheet(f"""
            background-color: {self._accent_light}; 
            border-bottom: 1px solid {t.get('border')};
            border-left: 4px solid {self._accent};
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        
        # Title section
        title_section = QVBoxLayout()
        
        self.title = QLabel("All Species")
        self.title.setStyleSheet(f"font-weight: 600; color: {self._accent_dark}; font-size: 14px;")
        title_section.addWidget(self.title)
        
        self.subtitle = QLabel("National distribution • 10km grid • Personal records")
        self.subtitle.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 11px;")
        title_section.addWidget(self.subtitle)
        
        layout.addLayout(title_section)
        layout.addStretch()
        
        self.grid_count = QLabel("0 grid squares")
        self.grid_count.setStyleSheet(f"color: {t.get('text_heading')}; font-size: 12px;")
        layout.addWidget(self.grid_count)
    
    def set_species(self, species: dict = None):
        """Update the displayed species."""
        t = theme()
        if species:
            name = f"<i>{species.get('scientific_name', species.get('name', 'Unknown'))}</i>"
            common = species.get('common_name', species.get('common', ''))
            if common:
                name += f" <span style='color: {t.get('text_secondary')}; font-weight: normal;'>({common})</span>"
            self.title.setText(name)
        else:
            self.title.setText("All Species")
    
    def set_config(self, view: str, grid: str, data: str):
        """Update the configuration subtitle."""
        view_text = "National distribution" if view == 'national' else "County distribution"
        data_text = {
            'personal': 'Personal records',
            'scheme': 'Recording Scheme',
            'all': 'All records'
        }.get(data, 'Personal records')
        
        self.subtitle.setText(f"{view_text} • {grid} grid • {data_text}")
    
    def set_grid_count(self, count: int):
        """Update the grid count."""
        self.grid_count.setText(f"{count} grid squares")
