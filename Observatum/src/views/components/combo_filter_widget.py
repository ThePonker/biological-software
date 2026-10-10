"""
Combo Filter Widget Component.

Custom combo box with text display and dropdown button for filter bars.
Shared across Observation, Collection, and Recording Scheme filter bars.
"""

from ...core.config import TabColors
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton, QMenu
from PySide6.QtCore import Signal, Qt

from ...themes import theme


class ComboFilterWidget(QWidget):
    """Custom combo filter with text display and separate dropdown button."""
    
    currentTextChanged = Signal(str)
    
    def __init__(self, accent_color: str = None, parent=None):
        super().__init__(parent)
        self._accent_color = accent_color or TabColors.OBSERVATION  # Default sage green
        self._items = []  # Stores tuples: (text, data)
        self._current_index = 0
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the combo filter UI."""
        t = theme()
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        # Text display - styled like QLineEdit but read-only
        self.display = QLineEdit()
        self.display.setReadOnly(True)
        self.display.setFixedHeight(26)
        self._apply_display_style()
        self.display.mousePressEvent = lambda e: self._show_menu()
        layout.addWidget(self.display)
        
        # Dropdown button
        self.dropdown_btn = QPushButton("▼")
        self.dropdown_btn.setFixedSize(26, 26)
        self.dropdown_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dropdown_btn.setToolTip("Select option")
        self._apply_button_style()
        self.dropdown_btn.clicked.connect(self._show_menu)
        layout.addWidget(self.dropdown_btn)
        
        # Create menu for dropdown
        self._menu = QMenu(self)
        self._apply_menu_style()
    
    def _apply_display_style(self):
        """Apply style to display field."""
        t = theme()
        self.display.setStyleSheet(f"""
            QLineEdit {{
                padding: 4px 6px;
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_sm')};
                background-color: {t.get('surface')};
                font-size: 13px;
                color: {t.get('text_primary')};
            }}
            QLineEdit:hover {{
                border: 1px solid {t.get('border_hover')};
            }}
            QLineEdit:focus {{
                border: 1px solid {self._accent_color};
            }}
            QLineEdit:disabled {{
                background-color: {t.get('surface_alt')};
                color: {t.get('text_muted')};
            }}
        """)
    
    def _apply_button_style(self):
        """Apply style to dropdown button."""
        t = theme()
        self.dropdown_btn.setStyleSheet(f"""
            QPushButton {{
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_sm')};
                background-color: {t.get('surface')};
                font-size: 10px;
                color: {t.get('text_secondary')};
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {self._accent_color};
                border-color: {self._accent_color};
                color: white;
            }}
            QPushButton:pressed {{
                background-color: {self._accent_color};
                color: white;
            }}
            QPushButton:disabled {{
                background-color: {t.get('surface_alt')};
                color: {t.get('text_muted')};
            }}
        """)
    
    def _apply_menu_style(self):
        """Apply style to dropdown menu."""
        t = theme()
        self._menu.setStyleSheet(f"""
            QMenu {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_sm')};
                padding: 4px 0px;
            }}
            QMenu::item {{
                padding: 6px 12px;
                color: {t.get('text_primary')};
            }}
            QMenu::item:selected {{
                background-color: {self._accent_color};
                color: white;
            }}
        """)
    
    def _show_menu(self):
        """Show the dropdown menu."""
        self._menu.clear()
        for text, data in self._items:
            action = self._menu.addAction(text)
            action.triggered.connect(lambda checked, t=text: self._select_item(t))
        
        # Position menu below the widget
        pos = self.mapToGlobal(self.rect().bottomLeft())
        self._menu.setMinimumWidth(self.width())
        self._menu.exec(pos)
    
    def _select_item(self, text: str):
        """Handle item selection."""
        self.display.setText(text)
        for i, (t, d) in enumerate(self._items):
            if t == text:
                self._current_index = i
                break
        self.currentTextChanged.emit(text)
    
    def addItem(self, text: str, data=None):
        """Add an item to the combo with optional data."""
        self._items.append((text, data))
        if len(self._items) == 1:
            self.display.setText(text)
    
    def addItems(self, items: list):
        """Add multiple items (text only, data will be None)."""
        for item in items:
            self.addItem(item, None)
    
    def clear(self):
        """Clear all items and reset."""
        self._items = []
        self._current_index = 0
        self.display.clear()
    
    def setCurrentText(self, text: str):
        """Set the current text."""
        self.display.setText(text)
        for i, (t, d) in enumerate(self._items):
            if t == text:
                self._current_index = i
                break
        self.currentTextChanged.emit(text)
    
    def setCurrentIndex(self, index: int):
        """Set the current index."""
        if 0 <= index < len(self._items):
            self._current_index = index
            text, data = self._items[index]
            self.display.setText(text)
            self.currentTextChanged.emit(text)
    
    def currentText(self) -> str:
        """Get the current text."""
        return self.display.text()
    
    def currentIndex(self) -> int:
        """Get the current index."""
        return self._current_index
    
    def count(self) -> int:
        """Get the number of items."""
        return len(self._items)
    
    def itemText(self, index: int) -> str:
        """Get the text at the given index."""
        if 0 <= index < len(self._items):
            return self._items[index][0]
        return ""
    
    def itemData(self, index: int):
        """Get the data at the given index."""
        if 0 <= index < len(self._items):
            return self._items[index][1]
        return None
    
    def setPlaceholderText(self, text: str):
        """Set placeholder text."""
        self.display.setPlaceholderText(text)
    
    def resetToFirst(self):
        """Reset to the first item (typically 'All')."""
        if self._items:
            self.setCurrentIndex(0)
    
    def findText(self, text: str) -> int:
        """Find the index of an item by text. Returns -1 if not found."""
        for i, (t, d) in enumerate(self._items):
            if t == text:
                return i
        return -1
    
    def findData(self, data) -> int:
        """Find the index of an item by data. Returns -1 if not found."""
        for i, (t, d) in enumerate(self._items):
            if d == data:
                return i
        return -1
    
    def currentData(self):
        """Get the data for the current item."""
        if 0 <= self._current_index < len(self._items):
            return self._items[self._current_index][1]
        return None
    
    def set_unavailable(self, reason: str = ""):
        """Grey the filter out and say why (reason ""): enable it again. A disabled
        widget looked exactly like an enabled one -- the styles had no :disabled rule
        (Wil 10 Oct: scheme Subfamily showed "All" as if active)."""
        self.setEnabled(not reason)
        self.setToolTip(reason)
        self.display.setToolTip(reason)
        self.dropdown_btn.setToolTip(reason or "Select option")

    def setAccentColor(self, color: str):
        """Update the accent color and refresh styles."""
        self._accent_color = color
        self._apply_display_style()
        self._apply_button_style()
        self._apply_menu_style()
    
    def apply_theme(self):
        """Apply the current theme."""
        self._apply_display_style()
        self._apply_button_style()
        self._apply_menu_style()
