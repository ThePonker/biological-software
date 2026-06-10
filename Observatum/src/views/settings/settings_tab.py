"""Settings Tab - Orchestrator"""
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QFrame, QStackedWidget
from PySide6.QtCore import Signal

from ...themes import theme
from .sidebar import SettingsSidebar
from .general_panel import GeneralSettingsPanel
from .database_panel import DatabaseSettingsPanel
from .export_panel import ExportSettingsPanel
from .sync_panel import SyncSettingsPanel


class SettingsTab(QWidget):
    settings_changed = Signal()
    database_changed = Signal()
    
    def __init__(self, parent=None, db_manager=None):
        super().__init__(parent)
        self._db_manager = db_manager
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        t = theme()

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {t.get('background')};
            }}
            QGroupBox {{
                font-weight: 600;
                font-size: {t.font_size('base')};
                color: {t.get('text_primary')};
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_md')};
                margin-top: 12px;
                padding: 16px 12px 12px 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 0 6px;
                background-color: {t.get('background')};
                color: {t.get('text_primary')};
            }}
            QCheckBox {{
                spacing: 8px;
                color: {t.get('text_primary')};
                font-size: {t.font_size('base')};
                padding: 4px 0;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {t.get('border_strong')};
                border-radius: 3px;
                background-color: {t.get('surface')};
            }}
            QCheckBox::indicator:hover {{
                border-color: {t.get('primary')};
            }}
            QCheckBox::indicator:checked {{
                background-color: {t.get('primary')};
                border-color: {t.get('primary')};
            }}
            QCheckBox::indicator:checked:hover {{
                background-color: {t.get('primary_hover')};
                border-color: {t.get('primary_hover')};
            }}
            QLabel {{
                color: {t.get('text_primary')};
            }}
            QLineEdit {{
                border: 1px solid {t.get('input_border')};
                border-radius: {t.get('radius_sm')};
                padding: 6px 8px;
                background-color: {t.get('surface')};
                color: {t.get('text_primary')};
            }}
            QLineEdit:focus {{
                border-color: {t.get('input_focus_border')};
            }}
            QComboBox {{
                border: 1px solid {t.get('input_border')};
                border-radius: {t.get('radius_sm')};
                padding: 6px 8px;
                background-color: {t.get('surface')};
                color: {t.get('text_primary')};
            }}
            QComboBox:hover {{
                border-color: {t.get('input_border_hover')};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.sidebar = SettingsSidebar()
        layout.addWidget(self.sidebar)
        
        content = QFrame()
        content.setStyleSheet(f"background-color: {t.get('background')};")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 16, 16, 16)
        
        self.panel_stack = QStackedWidget()
        
        self.general_panel = GeneralSettingsPanel()
        self.panel_stack.addWidget(self.general_panel)
        
        self.database_panel = DatabaseSettingsPanel(self._db_manager)
        self.panel_stack.addWidget(self.database_panel)
        
        self.export_panel = ExportSettingsPanel()
        self.panel_stack.addWidget(self.export_panel)
        
        self.sync_panel = SyncSettingsPanel()
        self.panel_stack.addWidget(self.sync_panel)
        
        content_layout.addWidget(self.panel_stack)
        layout.addWidget(content, 1)
    
    def _connect_signals(self):
        self.sidebar.section_changed.connect(self._on_panel_selected)
        self.general_panel.settings_changed.connect(self._on_settings_saved)
        self.database_panel.database_changed.connect(self._on_database_changed)
    
    def _on_panel_selected(self, panel):
        idx = {
            'general': 0,
            'database': 1,
            'export': 2,
            'sync': 3
        }.get(panel, 0)
        self.panel_stack.setCurrentIndex(idx)
    
    def _on_settings_saved(self):
        self.settings_changed.emit()
    
    def _on_database_changed(self):
        self.database_changed.emit()
        self.database_panel.refresh()

    def initialize(self):
        """Initialize all panels by loading their settings."""
        try:
            self.general_panel.load_settings()
            self.database_panel.load_settings()
            self.database_panel.refresh()
            self.export_panel.load_settings()
            self.sync_panel.load_settings()
        except Exception as e:
            print(f"Error initializing settings: {e}")
    
    def refresh(self):
        """Refresh settings display."""
        self.initialize()
    
    def apply_theme(self):
        """Apply the current theme to all components."""
        t = theme()

        # Reapply the full stylesheet
        self._setup_ui  # stylesheet is set in __init__, just re-call setStyleSheet
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {t.get('background')};
            }}
            QGroupBox {{
                font-weight: 600;
                font-size: {t.font_size('base')};
                color: {t.get('text_primary')};
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_md')};
                margin-top: 12px;
                padding: 16px 12px 12px 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 0 6px;
                background-color: {t.get('background')};
                color: {t.get('text_primary')};
            }}
            QCheckBox {{
                spacing: 8px;
                color: {t.get('text_primary')};
                font-size: {t.font_size('base')};
                padding: 4px 0;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {t.get('border_strong')};
                border-radius: 3px;
                background-color: {t.get('surface')};
            }}
            QCheckBox::indicator:hover {{
                border-color: {t.get('primary')};
            }}
            QCheckBox::indicator:checked {{
                background-color: {t.get('primary')};
                border-color: {t.get('primary')};
            }}
            QCheckBox::indicator:checked:hover {{
                background-color: {t.get('primary_hover')};
                border-color: {t.get('primary_hover')};
            }}
            QLabel {{
                color: {t.get('text_primary')};
            }}
            QLineEdit {{
                border: 1px solid {t.get('input_border')};
                border-radius: {t.get('radius_sm')};
                padding: 6px 8px;
                background-color: {t.get('surface')};
                color: {t.get('text_primary')};
            }}
            QLineEdit:focus {{
                border-color: {t.get('input_focus_border')};
            }}
            QComboBox {{
                border: 1px solid {t.get('input_border')};
                border-radius: {t.get('radius_sm')};
                padding: 6px 8px;
                background-color: {t.get('surface')};
                color: {t.get('text_primary')};
            }}
            QComboBox:hover {{
                border-color: {t.get('input_border_hover')};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
        """)

        # Apply to sidebar
        if hasattr(self.sidebar, 'apply_theme'):
            self.sidebar.apply_theme()

        # Apply to all panels
        for panel in [self.general_panel, self.database_panel,
                       self.export_panel, self.sync_panel]:
            if hasattr(panel, 'apply_theme'):
                panel.apply_theme()
