"""
Map Header component for Observatum V2.

Displays current map configuration including species name,
view mode, grid size, data source, and grid count.
"""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel

from ...themes import theme
from ...core.config import TabColors
from .source_picker import sources_label

NO_TAXON_TITLE = "All records (no taxon chosen)"     # L33: was "All Species"


class MapHeader(QFrame):
    """Header showing current map configuration."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        t = theme()
        self._accent = TabColors.MAPPING
        self._accent_light = TabColors.MAPPING_LIGHT
        self._accent_dark = TabColors.MAPPING_DARK
        
        # Tab header style: light background with accent border
        self.setObjectName("mapHeader")          # the borders are the header's, not its labels'
        self.setStyleSheet(f"""
            QFrame#mapHeader {{
                background-color: {self._accent_light};
                border-bottom: 1px solid {t.get('border')};
                border-left: 4px solid {self._accent};
            }}
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        
        # Title section
        title_section = QVBoxLayout()
        
        self.title = QLabel(NO_TAXON_TITLE)
        self.title.setStyleSheet(f"font-weight: 600; color: {self._accent_dark}; font-size: 14px;")
        title_section.addWidget(self.title)
        
        self.subtitle = QLabel("National distribution • 10km grid • Personal records")
        self.subtitle.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 11px;")
        self.subtitle.setWordWrap(True)        # a long note wraps; it never widens the map (L30)
        title_section.addWidget(self.subtitle)
        
        layout.addLayout(title_section, 1)      # the wrapped subtitle gets the room
        
        self.grid_count = QLabel("0 grid squares")
        self.grid_count.setStyleSheet(f"color: {t.get('text_heading')}; font-size: 12px;")
        layout.addWidget(self.grid_count)
    
    def set_species(self, species: dict = None):
        """Update the displayed species (one chip; kept for callers of the old API)."""
        self.set_selection([species] if species else [])

    def set_selection(self, chips: list):
        """The title: the chosen taxa (or 'All records (no taxon chosen)')."""
        self.title.setText(selection_title(chips, html=True, muted=theme().get('text_secondary')))

    def set_config(self, view: str, grid: str, data, note: str = ""):
        """Update the configuration subtitle. data: a source key or a list of them (L8);
        note: what was held back or included, e.g. embargoed."""
        view_text = "National distribution" if view == 'national' else "County distribution"
        data_text = sources_label(data)
        self.subtitle.setText(f"{view_text} • {grid} grid • {data_text}" + (f" • {note}" if note else ""))

    def set_grid_count(self, count: int, records: int = None):
        """Update the grid count."""
        text = f"{count:,} grid square{'s' if count != 1 else ''}"
        if records is not None:
            text += f" · {records:,} record{'s' if records != 1 else ''}"
        self.grid_count.setText(text)


def selection_title(chips: list, html: bool = False, muted: str = "") -> str:
    """'Rutpela maculata (Spotted Longhorn)', 'Rhagium + Cerambycidae', or (nothing chosen:
    every record is mapped) 'All records (no taxon chosen)'."""
    if not chips:
        return NO_TAXON_TITLE
    names = []
    for c in chips[:3]:
        name = c.get('scientific_name') or c.get('label') or c.get('name') or '?'
        italic = html and c.get('kind') != 'group'
        names.append(f"<i>{name}</i>" if italic else name)
    text = " + ".join(names) + (f" + {len(chips) - 3} more" if len(chips) > 3 else "")
    common = chips[0].get('common_name') or chips[0].get('common') if len(chips) == 1 else ""
    if common:
        text += (f" <span style='color: {muted}; font-weight: normal;'>({common})</span>"
                 if html else f" ({common})")
    return text
