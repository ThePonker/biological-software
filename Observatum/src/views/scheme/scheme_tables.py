"""
Scheme Table Widgets.

Table widgets for Recording Scheme tab:
- CountyListWidget: County species lists
- CountyFirstsWidget: County firsts
- RecordingGapsWidget: Recording gaps

Note: RecordsTableWidget has been replaced by SchemeRecordModel + QTableView
for consistency with Observation Data and Insect Collection tabs.
"""

from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView,
    QLabel, QPushButton,
    QAbstractItemView
)
from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QColor

from ...themes import theme
from ...core.config import TabColors
from ...utils.date_utils import format_date_display


class CountyListWidget(QTableWidget):
    """Table widget for county species lists view."""
    
    SETTINGS_KEY = "scheme_county_list_columns"
    COLUMNS = ['vc', 'county_name', 'species', 'records', 'last_record', 'actions']
    DEFAULT_WIDTHS = [50, 150, 80, 80, 100, 100]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = []
        self._setup_ui()
        self._load_column_widths()
        self.horizontalHeader().sectionResized.connect(self._save_column_widths)
    
    def _load_column_widths(self):
        """Load saved column widths from settings."""
        settings = QSettings()
        for i, (key, default_width) in enumerate(zip(self.COLUMNS, self.DEFAULT_WIDTHS)):
            saved_width = settings.value(f"{self.SETTINGS_KEY}/{key}", default_width, type=int)
            if saved_width > 0:
                self.setColumnWidth(i, saved_width)
    
    def _save_column_widths(self, logical_index, old_size, new_size):
        """Save column widths when resized."""
        settings = QSettings()
        if 0 <= logical_index < len(self.COLUMNS):
            key = self.COLUMNS[logical_index]
            settings.setValue(f"{self.SETTINGS_KEY}/{key}", new_size)
    
    def _setup_ui(self):
        t = theme()
        
        self.setColumnCount(6)
        self.setHorizontalHeaderLabels(['VC', 'County', 'Species', 'Records', 'Last Record', ''])
        
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.setColumnWidth(0, 50)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.setColumnWidth(1, 150)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.setColumnWidth(2, 80)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.setColumnWidth(3, 80)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        self.setColumnWidth(4, 100)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)
        self.setColumnWidth(5, 100)
        header.setStretchLastSection(True)
        
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        
        self._apply_style()
    
    def _apply_style(self):
        """Apply table styling using theme tokens."""
        t = theme()
        self.setStyleSheet(f"""
            QTableWidget {{
                border: none;
                background-color: {t.get('surface')};
                gridline-color: {t.get('border')};
                alternate-background-color: {t.get('surface_alt')};
            }}
            QTableWidget::item {{
                padding: 8px;
            }}
            QTableWidget::item:hover {{
                background-color: {TabColors.RECORDING_SCHEME_LIGHT};
            }}
            QTableWidget::item:selected {{
                background-color: {TabColors.RECORDING_SCHEME_LIGHT};
                color: {t.get('text_primary')};
            }}
            QHeaderView::section {{
                background-color: {t.get('surface_alt')};
                padding: 8px;
                border: none;
                border-bottom: 1px solid {t.get('border')};
                font-weight: 600;
            }}
        """)
    
    def set_data(self, counties: list):
        """Set county list data."""
        t = theme()
        self._data = counties
        self.setRowCount(len(counties))
        
        for row, county in enumerate(counties):
            # VC number
            vc_item = QTableWidgetItem(str(county.get('vc', '')))
            vc_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(row, 0, vc_item)
            
            # County name
            self.setItem(row, 1, QTableWidgetItem(county.get('name', '')))
            
            # Species count (bold warning color)
            species_item = QTableWidgetItem(str(county.get('species', 0)))
            species_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            species_item.setForeground(QColor(t.get('warning_text')))
            font = species_item.font()
            font.setBold(True)
            species_item.setFont(font)
            self.setItem(row, 2, species_item)
            
            records_item = QTableWidgetItem(str(county.get('records', 0)))
            records_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(row, 3, records_item)
            
            self.setItem(row, 4, QTableWidgetItem(county.get('lastRecord', '')))
            
            # View button
            view_btn = QPushButton("View List →")
            view_btn.setStyleSheet(f"color: {t.get('primary')}; border: none; font-size: {t.font_size('base')};")
            self.setCellWidget(row, 5, view_btn)
    
    def apply_theme(self):
        """Apply the current theme."""
        self._apply_style()
        # Re-render data to apply new colors
        if self._data:
            self.set_data(self._data)


class CountyFirstsWidget(QTableWidget):
    """Table widget for county firsts view."""
    
    SETTINGS_KEY = "scheme_county_firsts_columns"
    COLUMNS = ['species', 'vice_county', 'date', 'recorder', 'grid_ref']
    DEFAULT_WIDTHS = [180, 150, 90, 100, 90]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = []
        self._setup_ui()
        self._load_column_widths()
        self.horizontalHeader().sectionResized.connect(self._save_column_widths)
    
    def _load_column_widths(self):
        """Load saved column widths from settings."""
        settings = QSettings()
        for i, (key, default_width) in enumerate(zip(self.COLUMNS, self.DEFAULT_WIDTHS)):
            saved_width = settings.value(f"{self.SETTINGS_KEY}/{key}", default_width, type=int)
            if saved_width > 0:
                self.setColumnWidth(i, saved_width)
    
    def _save_column_widths(self, logical_index, old_size, new_size):
        """Save column widths when resized."""
        settings = QSettings()
        if 0 <= logical_index < len(self.COLUMNS):
            key = self.COLUMNS[logical_index]
            settings.setValue(f"{self.SETTINGS_KEY}/{key}", new_size)
    
    def _setup_ui(self):
        self.setColumnCount(5)
        self.setHorizontalHeaderLabels(['Species', 'Vice County', 'Date', 'Recorder', 'Grid Ref'])
        
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.setColumnWidth(0, 180)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.setColumnWidth(1, 150)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.setColumnWidth(2, 90)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.setColumnWidth(3, 100)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        self.setColumnWidth(4, 90)
        header.setStretchLastSection(True)
        
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        
        self._apply_style()
    
    def _apply_style(self):
        """Apply table styling using theme tokens."""
        t = theme()
        self.setStyleSheet(f"""
            QTableWidget {{
                border: none;
                background-color: {t.get('surface')};
                gridline-color: {t.get('border')};
                alternate-background-color: {t.get('surface_alt')};
            }}
            QTableWidget::item {{
                padding: 8px;
            }}
            QTableWidget::item:hover {{
                background-color: {TabColors.RECORDING_SCHEME_LIGHT};
            }}
            QTableWidget::item:selected {{
                background-color: {TabColors.RECORDING_SCHEME_LIGHT};
                color: {t.get('text_primary')};
            }}
            QHeaderView::section {{
                background-color: {t.get('surface_alt')};
                padding: 8px;
                border: none;
                border-bottom: 1px solid {t.get('border')};
                font-weight: 600;
            }}
        """)
    
    def refresh_date_format(self):
        """Refresh date format by rebuilding table with current data."""
        if self._data:
            self.set_data(self._data)
    
    def set_data(self, data: list):
        """Set county firsts data."""
        self._data = data
        self.setRowCount(len(data))
        
        for row, record in enumerate(data):
            species_item = QTableWidgetItem(record.get('species', ''))
            font = species_item.font()
            font.setItalic(True)
            species_item.setFont(font)
            self.setItem(row, 0, species_item)
            
            vc_text = f"{record.get('vc', '')} - {record.get('vcName', '')}"
            self.setItem(row, 1, QTableWidgetItem(vc_text))
            
            # Format date using user's preferred format
            date_value = record.get('date', '')
            if date_value:
                date_value = format_date_display(str(date_value), "user")
            self.setItem(row, 2, QTableWidgetItem(date_value))
            
            self.setItem(row, 3, QTableWidgetItem(record.get('recorder', '')))
            
            grid_item = QTableWidgetItem(record.get('gridRef', ''))
            self.setItem(row, 4, grid_item)
    
    def apply_theme(self):
        """Apply the current theme."""
        self._apply_style()
        # Re-render data to apply new colors
        if self._data:
            self.set_data(self._data)


class RecordingGapsWidget(QTableWidget):
    """Table widget for recording gaps view."""
    
    SETTINGS_KEY = "scheme_recording_gaps_columns"
    COLUMNS = ['species', 'last_record', 'years_since', 'last_vc', 'last_recorder']
    DEFAULT_WIDTHS = [180, 100, 100, 120, 100]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = []
        self._setup_ui()
        self._load_column_widths()
        self.horizontalHeader().sectionResized.connect(self._save_column_widths)
    
    def _load_column_widths(self):
        """Load saved column widths from settings."""
        settings = QSettings()
        for i, (key, default_width) in enumerate(zip(self.COLUMNS, self.DEFAULT_WIDTHS)):
            saved_width = settings.value(f"{self.SETTINGS_KEY}/{key}", default_width, type=int)
            if saved_width > 0:
                self.setColumnWidth(i, saved_width)
    
    def _save_column_widths(self, logical_index, old_size, new_size):
        """Save column widths when resized."""
        settings = QSettings()
        if 0 <= logical_index < len(self.COLUMNS):
            key = self.COLUMNS[logical_index]
            settings.setValue(f"{self.SETTINGS_KEY}/{key}", new_size)
    
    def _setup_ui(self):
        self.setColumnCount(5)
        self.setHorizontalHeaderLabels(['Species', 'Last Record', 'Years Since', 'Last VC', 'Last Recorder'])
        
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.setColumnWidth(0, 180)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.setColumnWidth(1, 100)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.setColumnWidth(2, 100)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.setColumnWidth(3, 120)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        self.setColumnWidth(4, 100)
        header.setStretchLastSection(True)
        
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        
        self._apply_style()
    
    def _apply_style(self):
        """Apply table styling using theme tokens."""
        t = theme()
        self.setStyleSheet(f"""
            QTableWidget {{
                border: none;
                background-color: {t.get('surface')};
                gridline-color: {t.get('border')};
                alternate-background-color: {t.get('surface_alt')};
            }}
            QTableWidget::item {{
                padding: 8px;
            }}
            QTableWidget::item:hover {{
                background-color: {TabColors.RECORDING_SCHEME_LIGHT};
            }}
            QTableWidget::item:selected {{
                background-color: {TabColors.RECORDING_SCHEME_LIGHT};
                color: {t.get('text_primary')};
            }}
            QHeaderView::section {{
                background-color: {t.get('surface_alt')};
                padding: 8px;
                border: none;
                border-bottom: 1px solid {t.get('border')};
                font-weight: 600;
            }}
        """)
    
    def refresh_date_format(self):
        """Refresh date format by rebuilding table with current data."""
        if self._data:
            self.set_data(self._data)
    
    def set_data(self, data: list):
        """Set recording gaps data."""
        t = theme()
        self._data = data
        self.setRowCount(len(data))
        
        for row, record in enumerate(data):
            species_item = QTableWidgetItem(record.get('species', ''))
            font = species_item.font()
            font.setItalic(True)
            species_item.setFont(font)
            self.setItem(row, 0, species_item)
            
            # Format date using user's preferred format
            date_value = record.get('lastRecord', '')
            if date_value:
                date_value = format_date_display(str(date_value), "user")
            self.setItem(row, 1, QTableWidgetItem(date_value))
            
            # Years badge using theme tokens
            years = record.get('years', 0)
            years_badge = QLabel(f"{years} years")
            years_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if years >= 5:
                years_badge.setStyleSheet(f"background-color: {t.get('error_bg')}; color: {t.get('error')}; padding: 4px 8px; border-radius: {t.get('radius_sm')}; font-weight: bold;")
            else:
                years_badge.setStyleSheet(f"background-color: {t.get('warning_bg')}; color: {t.get('warning_text')}; padding: 4px 8px; border-radius: {t.get('radius_sm')}; font-weight: bold;")
            self.setCellWidget(row, 2, years_badge)
            
            self.setItem(row, 3, QTableWidgetItem(record.get('lastVc', '')))
            self.setItem(row, 4, QTableWidgetItem(record.get('lastRecorder', '')))
    
    def apply_theme(self):
        """Apply the current theme."""
        self._apply_style()
        # Re-render data to apply new colors (including year badges)
        if self._data:
            self.set_data(self._data)
