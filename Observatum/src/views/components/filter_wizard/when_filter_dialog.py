"""
When Filter Dialog.

Filter by date range, specific year, or quick presets.
Uses consistent checkbox styling matching Home tab.
"""

from typing import Dict, Any, List
from datetime import datetime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QDateEdit, QComboBox, QRadioButton,
    QButtonGroup, QWidget
)
from PySide6.QtCore import Qt, QDate

from ....themes import theme
from ....core.config import ButtonColors


class WhenFilterDialog(QDialog):
    """
    Dialog for filtering by date/time.
    
    Options:
    - Date range (from/to)
    - Specific year
    - Quick presets (This year, Last year, etc.)
    """
    
    def __init__(
        self,
        accent_color: str = None,
        current_values: Dict[str, Any] = None,
        year_list: List[int] = None,
        parent=None
    ):
        super().__init__(parent)
        self._accent_color = accent_color or "#5f8575"
        self._current = current_values or {}
        
        # Build year list (last 30 years)
        current_year = datetime.now().year
        self._year_list = year_list or list(range(current_year, current_year - 30, -1))
        
        self.setWindowTitle("Filter by When")
        self.setMinimumWidth(450)
        self.setMinimumHeight(400)
        self.setModal(True)
        
        self._setup_ui()
        self._load_current_values()
    
    def _setup_ui(self):
        """Set up the dialog UI."""
        t = theme()
        
        self.setStyleSheet(f"background-color: {t.get('background')};")
        
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Header
        header = QLabel("📅 When to Include")
        header.setStyleSheet(f"""
            QLabel {{
                font-size: 18px;
                font-weight: 600;
                color: {self._accent_color};
                background: transparent;
            }}
        """)
        layout.addWidget(header)
        
        desc = QLabel("Filter by date range or specific year")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 12px; background: transparent;")
        layout.addWidget(desc)
        
        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {t.get('border')};")
        sep.setFixedHeight(1)
        layout.addWidget(sep)
        
        # Radio button group
        self._mode_group = QButtonGroup(self)
        
        # === DATE RANGE OPTION ===
        self._date_range_radio = QRadioButton("Date range")
        self._date_range_radio.setChecked(True)
        self._style_radio(self._date_range_radio)
        self._mode_group.addButton(self._date_range_radio, 0)
        layout.addWidget(self._date_range_radio)
        
        # Date range inputs
        date_range_widget = QWidget()
        date_range_widget.setStyleSheet("background: transparent;")
        date_range_layout = QHBoxLayout(date_range_widget)
        date_range_layout.setContentsMargins(24, 0, 0, 0)
        date_range_layout.setSpacing(16)
        
        # From date
        from_label = QLabel("From:")
        from_label.setStyleSheet(f"color: {t.get('text_primary')}; background: transparent;")
        date_range_layout.addWidget(from_label)
        
        self._from_date = QDateEdit()
        self._from_date.setCalendarPopup(True)
        self._from_date.calendarWidget().setMinimumWidth(280)
        self._from_date.setKeyboardTracking(True)
        self._from_date.setDate(QDate.currentDate().addYears(-1))
        self._from_date.setDisplayFormat("dd/MM/yyyy")
        self._style_date_edit(self._from_date)
        date_range_layout.addWidget(self._from_date)
        
        # To date
        to_label = QLabel("To:")
        to_label.setStyleSheet(f"color: {t.get('text_primary')}; background: transparent;")
        date_range_layout.addWidget(to_label)
        
        self._to_date = QDateEdit()
        self._to_date.setCalendarPopup(True)
        self._to_date.calendarWidget().setMinimumWidth(280)
        self._to_date.setKeyboardTracking(True)
        self._to_date.setDate(QDate.currentDate())
        self._to_date.setDisplayFormat("dd/MM/yyyy")
        self._style_date_edit(self._to_date)
        date_range_layout.addWidget(self._to_date)
        
        date_range_layout.addStretch()
        layout.addWidget(date_range_widget)
        
        # === SPECIFIC YEAR OPTION ===
        self._year_radio = QRadioButton("Specific year")
        self._style_radio(self._year_radio)
        self._mode_group.addButton(self._year_radio, 1)
        layout.addWidget(self._year_radio)
        
        # Year dropdown
        year_widget = QWidget()
        year_widget.setStyleSheet("background: transparent;")
        year_layout = QHBoxLayout(year_widget)
        year_layout.setContentsMargins(24, 0, 0, 0)
        year_layout.setSpacing(16)
        
        year_label = QLabel("Year:")
        year_label.setStyleSheet(f"color: {t.get('text_primary')}; background: transparent;")
        year_layout.addWidget(year_label)
        
        self._year_combo = QComboBox()
        self._year_combo.setMinimumWidth(100)
        for year in self._year_list:
            self._year_combo.addItem(str(year), year)
        self._style_combo(self._year_combo)
        year_layout.addWidget(self._year_combo)
        
        year_layout.addStretch()
        layout.addWidget(year_widget)
        
        # === QUICK PRESETS ===
        layout.addSpacing(8)
        
        presets_label = QLabel("Quick presets:")
        presets_label.setStyleSheet(f"font-weight: 500; color: {t.get('text_primary')}; background: transparent;")
        layout.addWidget(presets_label)
        
        presets_layout = QHBoxLayout()
        presets_layout.setSpacing(8)
        
        presets = [
            ("This year", self._set_this_year),
            ("Last year", self._set_last_year),
            ("Last 30 days", self._set_last_30_days),
            ("Last 12 months", self._set_last_12_months),
        ]
        
        for label, callback in presets:
            btn = QPushButton(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(callback)
            self._style_preset_button(btn)
            presets_layout.addWidget(btn)
        
        presets_layout.addStretch()
        layout.addLayout(presets_layout)
        
        layout.addStretch()
        
        # === BUTTON ROW ===
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        
        # Clear button
        clear_btn = QPushButton("Clear")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self._clear_all)
        clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {t.get('text_secondary')};
                border: 1px solid {t.get('border')};
                border-radius: 4px;
                padding: 10px 20px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {t.get('hover')};
            }}
        """)
        button_layout.addWidget(clear_btn)
        
        button_layout.addStretch()
        
        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {t.get('text_secondary')};
                border: 1px solid {t.get('border')};
                border-radius: 4px;
                padding: 10px 24px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {t.get('hover')};
            }}
        """)
        button_layout.addWidget(cancel_btn)
        
        # Apply button
        apply_btn = QPushButton("Apply Filters")
        apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_btn.clicked.connect(self.accept)
        apply_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ButtonColors.PRIMARY};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 24px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {self._darken_color(ButtonColors.PRIMARY)};
            }}
        """)
        button_layout.addWidget(apply_btn)
        
        layout.addLayout(button_layout)
        
        # Connect radio buttons to enable/disable inputs
        self._mode_group.buttonClicked.connect(self._on_mode_changed)
    
    def _on_mode_changed(self):
        """Handle mode change between date range and specific year."""
        is_date_range = self._date_range_radio.isChecked()
        self._from_date.setEnabled(is_date_range)
        self._to_date.setEnabled(is_date_range)
        self._year_combo.setEnabled(not is_date_range)
    
    def _set_this_year(self):
        """Set date range to this year."""
        self._date_range_radio.setChecked(True)
        self._on_mode_changed()
        
        today = QDate.currentDate()
        self._from_date.setDate(QDate(today.year(), 1, 1))
        self._to_date.setDate(today)
    
    def _set_last_year(self):
        """Set date range to last year."""
        self._date_range_radio.setChecked(True)
        self._on_mode_changed()
        
        today = QDate.currentDate()
        last_year = today.year() - 1
        self._from_date.setDate(QDate(last_year, 1, 1))
        self._to_date.setDate(QDate(last_year, 12, 31))
    
    def _set_last_30_days(self):
        """Set date range to last 30 days."""
        self._date_range_radio.setChecked(True)
        self._on_mode_changed()
        
        today = QDate.currentDate()
        self._from_date.setDate(today.addDays(-30))
        self._to_date.setDate(today)
    
    def _set_last_12_months(self):
        """Set date range to last 12 months."""
        self._date_range_radio.setChecked(True)
        self._on_mode_changed()
        
        today = QDate.currentDate()
        self._from_date.setDate(today.addMonths(-12))
        self._to_date.setDate(today)
    
    def _clear_all(self):
        """Clear all selections."""
        self._date_range_radio.setChecked(True)
        self._on_mode_changed()
        self._from_date.setDate(QDate.currentDate().addYears(-1))
        self._to_date.setDate(QDate.currentDate())
        self._year_combo.setCurrentIndex(0)
    
    def _load_current_values(self):
        """Load existing filter values."""
        if not self._current:
            return
        
        if 'year' in self._current and self._current['year']:
            self._year_radio.setChecked(True)
            year = self._current['year']
            idx = self._year_combo.findData(year)
            if idx >= 0:
                self._year_combo.setCurrentIndex(idx)
        else:
            if 'date_from' in self._current:
                date_from = self._current['date_from']
                if isinstance(date_from, str):
                    self._from_date.setDate(QDate.fromString(date_from, "yyyy-MM-dd"))
            
            if 'date_to' in self._current:
                date_to = self._current['date_to']
                if isinstance(date_to, str):
                    self._to_date.setDate(QDate.fromString(date_to, "yyyy-MM-dd"))
        
        self._on_mode_changed()
    
    def get_values(self) -> Dict[str, Any]:
        """Get the filter values."""
        result = {}
        
        if self._year_radio.isChecked():
            result['year'] = self._year_combo.currentData()
        else:
            result['date_from'] = self._from_date.date().toString("yyyy-MM-dd")
            result['date_to'] = self._to_date.date().toString("yyyy-MM-dd")
        
        return result
    
    def _style_radio(self, radio: QRadioButton):
        """Style radio buttons to match Home tab checkboxes."""
        t = theme()
        radio.setStyleSheet(f"""
            QRadioButton {{
                color: {t.get('text_primary')};
                font-size: 13px;
                font-weight: 500;
                spacing: 10px;
                background: transparent;
            }}
            QRadioButton::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 9px;
                border: 2px solid {t.get('border')};
                background-color: {t.get('surface')};
            }}
            QRadioButton::indicator:hover {{
                border-color: {self._accent_color};
            }}
            QRadioButton::indicator:checked {{
                background-color: {self._accent_color};
                border-color: {self._accent_color};
            }}
        """)
    
    def _style_date_edit(self, widget: QDateEdit):
        """Style date edit widget."""
        t = theme()
        widget.setStyleSheet(f"""
            QDateEdit {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 13px;
                color: {t.get('text_primary')};
                min-width: 110px;
            }}
            QDateEdit:focus {{
                border-color: {self._accent_color};
            }}
            QDateEdit::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: right center;
                width: 20px;
                border: none;
            }}
        """)
    
    def _style_combo(self, widget: QComboBox):
        """Style combo box."""
        t = theme()
        widget.setStyleSheet(f"""
            QComboBox {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 13px;
                color: {t.get('text_primary')};
            }}
            QComboBox:focus {{
                border-color: {self._accent_color};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                selection-background-color: {self._accent_color};
            }}
        """)
    
    def _style_preset_button(self, btn: QPushButton):
        """Style preset buttons."""
        t = theme()
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.get('surface')};
                color: {t.get('text_primary')};
                border: 1px solid {t.get('border')};
                border-radius: 4px;
                padding: 8px 14px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {t.get('hover')};
                border-color: {self._accent_color};
            }}
        """)
    
    def _darken_color(self, hex_color: str, factor: float = 0.85) -> str:
        """Darken a hex color."""
        hex_color = hex_color.lstrip('#')
        r = int(int(hex_color[0:2], 16) * factor)
        g = int(int(hex_color[2:4], 16) * factor)
        b = int(int(hex_color[4:6], 16) * factor)
        return f"#{r:02x}{g:02x}{b:02x}"

