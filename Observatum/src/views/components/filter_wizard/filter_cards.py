"""
Filter Cards Component.

Card-based interface for the Filter Wizard.
Each card opens a specific filter dialog.
"""

from typing import List, Tuple, Dict, Optional
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QSizePolicy
)
from PySide6.QtCore import Signal, Qt

from ....themes import theme


class FilterCard(QFrame):
    """
    A clickable card representing a filter category.
    
    Shows an icon, title, and description.
    Emits clicked signal when pressed.
    """
    
    clicked = Signal(str)  # card_id
    
    def __init__(
        self,
        card_id: str,
        title: str,
        description: str,
        icon: str = "📋",
        accent_color: str = None,
        parent=None
    ):
        super().__init__(parent)
        self._card_id = card_id
        self._title = title
        self._description = description
        self._icon = icon
        self._accent_color = accent_color or "#5f8575"
        self._has_filters = False
        
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the card UI."""
        t = theme()
        
        # Make cards larger
        self.setMinimumSize(200, 90)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)
        
        # Icon
        self.icon_label = QLabel(self._icon)
        self.icon_label.setFixedSize(44, 44)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet(f"""
            QLabel {{
                font-size: 24px;
                background-color: {self._lighten_color(self._accent_color, 0.85)};
                border-radius: 8px;
            }}
        """)
        layout.addWidget(self.icon_label)
        
        # Text container
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        text_layout.setContentsMargins(0, 0, 0, 0)
        
        # Title
        self.title_label = QLabel(self._title)
        self.title_label.setStyleSheet(f"""
            QLabel {{
                font-size: 14px;
                font-weight: 600;
                color: {self._accent_color};
                background: transparent;
            }}
        """)
        text_layout.addWidget(self.title_label)
        
        # Description
        self.desc_label = QLabel(self._description)
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet(f"""
            QLabel {{
                font-size: 12px;
                color: {t.get('text_secondary')};
                background: transparent;
            }}
        """)
        text_layout.addWidget(self.desc_label)
        
        layout.addLayout(text_layout, 1)
        
        # Arrow indicator
        arrow = QLabel("›")
        arrow.setStyleSheet(f"""
            QLabel {{
                font-size: 20px;
                color: {t.get('text_muted')};
                background: transparent;
            }}
        """)
        layout.addWidget(arrow)
        
        # Apply base styling
        self._update_style()
    
    def _update_style(self):
        """Update card style based on state."""
        t = theme()
        
        if self._has_filters:
            # Has active filters - show accent border
            self.setStyleSheet(f"""
                FilterCard {{
                    background-color: {t.get('surface')};
                    border: 2px solid {self._accent_color};
                    border-radius: 8px;
                }}
                FilterCard:hover {{
                    background-color: {t.get('hover')};
                }}
            """)
        else:
            # No filters - default style
            self.setStyleSheet(f"""
                FilterCard {{
                    background-color: {t.get('surface')};
                    border: 1px solid {t.get('border')};
                    border-radius: 8px;
                }}
                FilterCard:hover {{
                    background-color: {t.get('hover')};
                    border-color: {self._accent_color};
                }}
            """)
    
    def mousePressEvent(self, event):
        """Handle mouse press."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._card_id)
        super().mousePressEvent(event)
    
    def set_has_filters(self, has_filters: bool):
        """Update visual state to show if filters are active."""
        self._has_filters = has_filters
        self._update_style()
    
    def apply_theme(self):
        """Re-apply theme colors."""
        self._update_style()
    
    def _lighten_color(self, hex_color: str, factor: float = 0.85) -> str:
        """Lighten a hex color."""
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        
        r = int(r + (255 - r) * factor)
        g = int(g + (255 - g) * factor)
        b = int(b + (255 - b) * factor)
        
        return f"#{r:02x}{g:02x}{b:02x}"


class FilterCardGrid(QWidget):
    """
    Grid layout of filter cards.
    
    Default cards: What, Where, When, Who, How, Status
    Emits signal when a card is clicked.
    """
    
    card_clicked = Signal(str)  # card_id
    
    # Default card definitions (id, title, description, icon)
    DEFAULT_CARDS = [
        ('what', 'What', 'Species, order, family or taxon group', '🦋'),
        ('where', 'Where', 'Vice county, grid reference or site', '📍'),
        ('when', 'When', 'Date range for records', '📅'),
        ('who', 'Who', 'Recorder or determiner', '👤'),
        ('how', 'How', 'Sample method used', '🔍'),  # Changed from 🔬 to 🔍
        ('status', 'Status', 'Verification status or record type', '✓'),
    ]
    
    def __init__(
        self,
        accent_color: str = None,
        columns: int = 3,
        cards: List[Tuple[str, str, str, str]] = None,
        parent=None
    ):
        super().__init__(parent)
        self._accent_color = accent_color or "#5f8575"
        self._columns = columns
        self._card_defs = cards or self.DEFAULT_CARDS
        self._cards: Dict[str, FilterCard] = {}
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the grid layout."""
        layout = QGridLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(0, 0, 0, 0)
        
        for i, (card_id, title, desc, icon) in enumerate(self._card_defs):
            row = i // self._columns
            col = i % self._columns
            
            card = FilterCard(
                card_id=card_id,
                title=title,
                description=desc,
                icon=icon,
                accent_color=self._accent_color
            )
            card.clicked.connect(self.card_clicked.emit)
            
            self._cards[card_id] = card
            layout.addWidget(card, row, col)
    
    def get_card(self, card_id: str) -> Optional[FilterCard]:
        """Get a card by ID."""
        return self._cards.get(card_id)
    
    def set_card_active(self, card_id: str, has_filters: bool):
        """Update a card's active state."""
        card = self._cards.get(card_id)
        if card:
            card.set_has_filters(has_filters)
    
    def apply_theme(self):
        """Apply theme to all cards."""
        for card in self._cards.values():
            card.apply_theme()
