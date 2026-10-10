"""
Date Filter Widget Component.

Shared date filter widget with text input, calendar popup, and day increment buttons.
Used across Observation, Recording Scheme, and Collection filter bars.

Usage:
    from src.views.components.date_filter_widget import DateFilterWidget
    
    date_widget = DateFilterWidget(accent_color=TabColors.OBSERVATION)
    date_widget.dateChanged.connect(self._on_date_changed)
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, 
    QPushButton, QCalendarWidget
)
from PySide6.QtCore import Signal, QDate, Qt

from ...themes import theme

# Earliest year a date box accepts. Was 1900; scheme records go back to 1500 (OBS-14)
MIN_YEAR = 1000


class DateFilterWidget(QWidget):
    """Custom date filter with text input, calendar popup, and day increment buttons.
    
    Features:
    - Text input for manual date entry (dd/mm/yyyy format)
    - Calendar popup button for visual date selection
    - Up/down buttons for incrementing/decrementing by one day
    - Configurable accent color for theming
    - Smart calendar navigation to relevant dates
    
    Signals:
        dateChanged(QDate): Emitted when the date changes
    """
    
    dateChanged = Signal(QDate)
    
    def __init__(self, accent_color: str = None, parent=None):
        """Initialize the date filter widget.
        
        Args:
            accent_color: Hex color for focus/hover states. If None, uses theme primary.
            parent: Parent widget
        """
        super().__init__(parent)
        t = theme()
        self._accent_color = accent_color or t.get('primary')
        self._navigate_to_date = None
        self._current_date = None  # None means empty/no date selected
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the date filter UI."""
        t = theme()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        # Date text input - styled like other QLineEdits
        self.date_input = QLineEdit()
        self.date_input.setPlaceholderText("dd/mm/yyyy")
        self.date_input.setFixedHeight(26)
        self.date_input.setFixedWidth(95)
        self.date_input.setStyleSheet(f"""
            QLineEdit {{
                padding: 4px 6px;
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_sm')};
                background-color: {t.get('surface')};
                font-size: {t.font_size('base')};
            }}
            QLineEdit:hover {{
                border: 1px solid {t.get('border_hover')};
            }}
            QLineEdit:focus {{
                border: 1px solid {self._accent_color};
            }}
        """)
        self.date_input.editingFinished.connect(self._on_text_edited)
        layout.addWidget(self.date_input)
        
        # Calendar popup button
        self.cal_btn = QPushButton("📅")
        self.cal_btn.setFixedSize(26, 26)
        self.cal_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cal_btn.setToolTip("Open calendar")
        self.cal_btn.setStyleSheet(f"""
            QPushButton {{
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_sm')};
                background-color: {t.get('surface')};
                font-size: 12px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {self._accent_color};
                border-color: {self._accent_color};
            }}
            QPushButton:pressed {{
                background-color: {self._accent_color};
            }}
        """)
        self.cal_btn.clicked.connect(self._show_calendar)
        layout.addWidget(self.cal_btn)
        
        # Stacked up/down buttons container
        arrow_container = QWidget()
        arrow_container.setFixedSize(20, 26)
        arrow_layout = QVBoxLayout(arrow_container)
        arrow_layout.setContentsMargins(0, 0, 0, 0)
        arrow_layout.setSpacing(0)
        
        # Up button (+1 day)
        self.up_btn = QPushButton("▲")
        self.up_btn.setFixedSize(20, 13)
        self.up_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.up_btn.setToolTip("+1 day")
        self.up_btn.setStyleSheet(f"""
            QPushButton {{
                border: 1px solid {t.get('border')};
                border-bottom: none;
                border-top-left-radius: {t.get('radius_sm')};
                border-top-right-radius: {t.get('radius_sm')};
                background-color: {t.get('surface_alt')};
                font-size: 8px;
                color: {t.get('text_secondary')};
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {self._accent_color};
                border-color: {self._accent_color};
                color: white;
            }}
        """)
        self.up_btn.clicked.connect(self._increment_day)
        arrow_layout.addWidget(self.up_btn)
        
        # Down button (-1 day)
        self.down_btn = QPushButton("▼")
        self.down_btn.setFixedSize(20, 13)
        self.down_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.down_btn.setToolTip("-1 day")
        self.down_btn.setStyleSheet(f"""
            QPushButton {{
                border: 1px solid {t.get('border')};
                border-bottom-left-radius: {t.get('radius_sm')};
                border-bottom-right-radius: {t.get('radius_sm')};
                background-color: {t.get('surface_alt')};
                font-size: 8px;
                color: {t.get('text_secondary')};
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {self._accent_color};
                border-color: {self._accent_color};
                color: white;
            }}
        """)
        self.down_btn.clicked.connect(self._decrement_day)
        arrow_layout.addWidget(self.down_btn)
        
        layout.addWidget(arrow_container)
        
        # Create calendar widget for popup
        self._calendar = QCalendarWidget()
        self._calendar.setMinimumDate(QDate(MIN_YEAR, 1, 1))
        self._calendar.setWindowFlags(Qt.WindowType.Popup)
        self._calendar.clicked.connect(self._on_calendar_clicked)
        self._style_calendar()
    
    def _style_calendar(self):
        """Style the calendar popup."""
        t = theme()
        self._calendar.setStyleSheet(f"""
            QCalendarWidget {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_sm')};
            }}
            QCalendarWidget QToolButton {{
                color: {t.get('text_primary')};
                background-color: {t.get('surface')};
                font-weight: bold;
                padding: 4px 8px;
                border: none;
            }}
            QCalendarWidget QToolButton:hover {{
                background-color: {t.get('hover')};
                border-radius: {t.get('radius_sm')};
            }}
            QCalendarWidget QMenu {{
                background-color: {t.get('surface')};
                color: {t.get('text_primary')};
            }}
            QCalendarWidget QSpinBox {{
                color: {t.get('text_primary')};
                background-color: {t.get('surface')};
                font-weight: bold;
                selection-background-color: {self._accent_color};
                selection-color: white;
            }}
            QCalendarWidget QWidget#qt_calendar_navigationbar {{
                background-color: {t.get('surface')};
                padding: 4px;
                border-bottom: 1px solid {t.get('border')};
            }}
            QCalendarWidget QTableView {{
                background-color: {t.get('surface')};
                selection-background-color: {self._accent_color};
                selection-color: white;
                outline: none;
            }}
            QCalendarWidget QTableView::item:hover {{
                background-color: {t.get('hover')};
            }}
            QCalendarWidget QHeaderView::section {{
                background-color: {t.get('surface')};
                color: {t.get('text_secondary')};
                font-weight: bold;
                border: none;
                padding: 4px;
            }}
        """)
    
    def _show_calendar(self):
        """Show the calendar popup."""
        # Position calendar below the widget
        pos = self.mapToGlobal(self.rect().bottomLeft())
        self._calendar.move(pos)
        
        # Navigate to appropriate date
        if self._current_date:
            self._calendar.setSelectedDate(self._current_date)
        elif self._navigate_to_date:
            self._calendar.setCurrentPage(
                self._navigate_to_date.year(),
                self._navigate_to_date.month()
            )
            self._calendar.setSelectedDate(self._navigate_to_date)
        
        self._calendar.show()
    
    def _on_calendar_clicked(self, date: QDate):
        """Handle calendar date selection."""
        self._calendar.hide()
        self._set_date(date)
    
    def _on_text_edited(self):
        """Handle manual text entry."""
        text = self.date_input.text().strip()
        if not text:
            self._current_date = None
            self.dateChanged.emit(QDate())
            return
        
        # Try to parse the date
        date = QDate.fromString(text, "dd/MM/yyyy")
        if date.isValid() and date.year() >= MIN_YEAR:
            self._current_date = date
            self.dateChanged.emit(date)
        else:
            # Invalid date - reset to previous or clear
            if self._current_date:
                self.date_input.setText(self._current_date.toString("dd/MM/yyyy"))
            else:
                self.date_input.clear()
    
    def _increment_day(self):
        """Add one day to the current date."""
        if self._current_date:
            self._set_date(self._current_date.addDays(1))
        elif self._navigate_to_date:
            self._set_date(self._navigate_to_date)
        else:
            self._set_date(QDate.currentDate())
    
    def _decrement_day(self):
        """Subtract one day from the current date."""
        if self._current_date:
            new_date = self._current_date.addDays(-1)
            if new_date.year() >= MIN_YEAR:
                self._set_date(new_date)
        elif self._navigate_to_date:
            self._set_date(self._navigate_to_date)
        else:
            self._set_date(QDate.currentDate())
    
    def _set_date(self, date: QDate):
        """Set the current date and update display."""
        self._current_date = date
        self.date_input.setText(date.toString("dd/MM/yyyy"))
        self.dateChanged.emit(date)
    
    def set_navigate_date(self, date: QDate):
        """Set the date to navigate to when calendar opens on empty field.
        
        This is useful for setting smart defaults like the earliest or latest
        date in a dataset.
        
        Args:
            date: The date to navigate to when the calendar opens
        """
        self._navigate_to_date = date
    
    def date(self) -> QDate:
        """Get the current date.
        
        Returns:
            The current QDate, or an invalid QDate if no date is set
        """
        return self._current_date if self._current_date else QDate()
    
    def setDate(self, date: QDate):
        """Set the current date.
        
        Args:
            date: The date to set. If invalid or before MIN_YEAR, clears the field.
        """
        if date.isValid() and date.year() >= MIN_YEAR:
            self._set_date(date)
        else:
            self._current_date = None
            self.date_input.clear()
    
    def setIsoDate(self, text):
        """Set from 'yyyy-MM-dd' text (a saved filter); empty or unreadable clears."""
        self.setDate(QDate.fromString(str(text or ''), "yyyy-MM-dd"))

    def clear(self):
        """Clear the date."""
        self._current_date = None
        self.date_input.clear()
    
    def apply_theme(self):
        """Reapply the current theme (call after theme changes)."""
        t = theme()
        # Update date input style
        self.date_input.setStyleSheet(f"""
            QLineEdit {{
                padding: 4px 6px;
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_sm')};
                background-color: {t.get('surface')};
                color: {t.get('text_primary')};
                font-size: {t.font_size('sm')};
            }}
            QLineEdit:focus {{
                border-color: {self._accent_color};
            }}
        """)
        self._style_calendar()
