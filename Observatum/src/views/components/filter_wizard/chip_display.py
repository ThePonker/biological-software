"""
Chip Display Component.

Shows applied filters as removable chips/tags.
Chips stack vertically in a scrollable list.
"""

from typing import List, Dict
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSizePolicy
)
from PySide6.QtCore import Signal, Qt

from ....themes import theme


class FilterChip(QFrame):
    """
    A single removable chip representing an applied filter.
    
    Shows label text with an × button to remove.
    """
    
    removed = Signal(str, str)  # (category, value)
    
    def __init__(
        self,
        category: str,
        value: str,
        display_text: str = None,
        accent_color: str = None,
        parent=None
    ):
        super().__init__(parent)
        self._category = category
        self._value = value
        self._display = display_text or value
        self._accent_color = accent_color or "#4a7c59"
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the chip UI."""
        t = theme()
        
        self.setFixedHeight(32)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 8, 4)
        layout.setSpacing(8)
        
        # Label
        label = QLabel(self._display)
        label.setStyleSheet(f"""
            QLabel {{
                color: {t.get('text_primary')};
                font-size: 12px;
                background: transparent;
            }}
        """)
        layout.addWidget(label)
        
        layout.addStretch()
        
        # Remove button
        remove_btn = QPushButton("×")
        remove_btn.setFixedSize(20, 20)
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.clicked.connect(self._on_remove)
        remove_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {t.get('text_secondary')};
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {t.get('hover')};
                color: {t.get('text_primary')};
            }}
        """)
        layout.addWidget(remove_btn)
        
        # Frame styling with lightened accent color
        light_color = self._lighten_color(self._accent_color, 0.9)
        self.setStyleSheet(f"""
            FilterChip {{
                background-color: {light_color};
                border: 1px solid {self._accent_color};
                border-radius: 4px;
            }}
        """)
    
    def _on_remove(self):
        """Handle remove button click."""
        self.removed.emit(self._category, self._value)
    
    def get_category(self) -> str:
        return self._category
    
    def get_value(self) -> str:
        return self._value
    
    def _lighten_color(self, hex_color: str, factor: float = 0.9) -> str:
        """Lighten a hex color by mixing with white."""
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        
        r = int(r + (255 - r) * factor)
        g = int(g + (255 - g) * factor)
        b = int(b + (255 - b) * factor)
        
        return f"#{r:02x}{g:02x}{b:02x}"


class ChipDisplay(QWidget):
    """
    Container widget for displaying filter chips.
    
    Shows chips in a vertical list with scrolling.
    """
    
    chips_changed = Signal()
    
    def __init__(self, accent_color: str = None, parent=None):
        super().__init__(parent)
        self._accent_color = accent_color or "#4a7c59"
        self._chips: Dict[str, List[FilterChip]] = {}
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the display UI."""
        t = theme()
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Header
        header_layout = QHBoxLayout()
        
        self._title = QLabel("No filters applied")
        self._title.setStyleSheet(f"""
            QLabel {{
                font-weight: 500;
                font-size: 12px;
                color: {t.get('text_secondary')};
            }}
        """)
        header_layout.addWidget(self._title)
        
        header_layout.addStretch()
        
        # Clear all button
        self._clear_btn = QPushButton("Clear All")
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.clicked.connect(self.clear_all)
        self._clear_btn.setVisible(False)
        self._clear_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {self._accent_color};
                font-size: 11px;
                padding: 2px 6px;
            }}
            QPushButton:hover {{
                text-decoration: underline;
            }}
        """)
        header_layout.addWidget(self._clear_btn)
        
        layout.addLayout(header_layout)
        
        # Scrollable chip area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setMaximumHeight(150)
        scroll.setMinimumHeight(60)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: 6px;
            }}
            QScrollBar:vertical {{
                width: 8px;
            }}
        """)
        
        # Container with vertical layout for chips
        self._chip_container = QWidget()
        self._chip_container.setStyleSheet(f"background-color: {t.get('surface')};")
        self._chip_layout = QVBoxLayout(self._chip_container)
        self._chip_layout.setContentsMargins(8, 8, 8, 8)
        self._chip_layout.setSpacing(6)
        self._chip_layout.addStretch()  # Push chips to top
        
        scroll.setWidget(self._chip_container)
        layout.addWidget(scroll)
    
    def add_chip(self, category: str, value: str, display_text: str = None):
        """Add a chip for the given category and value."""
        # Check for duplicate
        if category in self._chips:
            for chip in self._chips[category]:
                if chip.get_value() == value:
                    return
        
        # Create chip
        chip = FilterChip(
            category=category,
            value=value,
            display_text=display_text,
            accent_color=self._accent_color
        )
        chip.removed.connect(self._on_chip_removed)
        
        # Add to tracking
        if category not in self._chips:
            self._chips[category] = []
        self._chips[category].append(chip)
        
        # Insert before stretch
        self._chip_layout.insertWidget(self._chip_layout.count() - 1, chip)
        
        self._update_visibility()
        self.chips_changed.emit()
    
    def remove_chip(self, category: str, value: str):
        """Remove a specific chip."""
        if category not in self._chips:
            return
        
        for chip in self._chips[category]:
            if chip.get_value() == value:
                self._chips[category].remove(chip)
                self._chip_layout.removeWidget(chip)
                chip.deleteLater()
                break
        
        if not self._chips[category]:
            del self._chips[category]
        
        self._update_visibility()
        self.chips_changed.emit()
    
    def _on_chip_removed(self, category: str, value: str):
        """Handle chip removal signal."""
        self.remove_chip(category, value)
    
    def clear_all(self):
        """Remove all chips."""
        for category, chips in list(self._chips.items()):
            for chip in chips:
                self._chip_layout.removeWidget(chip)
                chip.deleteLater()
        
        self._chips.clear()
        self._update_visibility()
        self.chips_changed.emit()
    
    def clear_category(self, category: str):
        """Remove all chips in a category."""
        if category not in self._chips:
            return
        
        for chip in self._chips[category]:
            self._chip_layout.removeWidget(chip)
            chip.deleteLater()
        
        del self._chips[category]
        self._update_visibility()
        self.chips_changed.emit()
    
    def get_values(self, category: str) -> List[str]:
        """Get all values for a category."""
        if category not in self._chips:
            return []
        return [chip.get_value() for chip in self._chips[category]]
    
    def get_all_values(self) -> Dict[str, List[str]]:
        """Get all values organized by category."""
        return {
            category: [chip.get_value() for chip in chips]
            for category, chips in self._chips.items()
        }
    
    def has_chips(self) -> bool:
        """Check if there are any chips."""
        return bool(self._chips)
    
    def chip_count(self) -> int:
        """Get total number of chips."""
        return sum(len(chips) for chips in self._chips.values())
    
    def _update_visibility(self):
        """Update visibility of header elements."""
        has_chips = self.has_chips()
        self._clear_btn.setVisible(has_chips)
        
        if has_chips:
            count = self.chip_count()
            self._title.setText(f"Applied Filters ({count}):")
        else:
            self._title.setText("No filters applied")
