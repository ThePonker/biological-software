"""
Sync Settings Panel Component.

iRecord synchronisation settings.
"""

from PySide6.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGroupBox, QFrame
)
from PySide6.QtCore import QSettings

from ...themes import theme
from ...core.config import Settings


class SyncSettingsPanel(QScrollArea):
    """iRecord sync settings panel."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self):
        t = theme()
        
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 20, 20)
        layout.setSpacing(24)
        
        # Info banner
        self._setup_info_banner(layout)
        
        # Sync settings group
        # Protected fields group
        self._setup_protected_fields(layout)
        
        # Conflict resolution group
        
        layout.addStretch()
        self.setWidget(content)
    
    def _setup_info_banner(self, layout):
        """Set up info banner with sync status."""
        t = theme()

        info_frame = QFrame()
        info_frame.setStyleSheet(f"background-color: {t.get('info_bg_light')}; border: 1px solid {t.get('info_border')}; border-radius: 6px; padding: 12px;")
        info_layout = QVBoxLayout(info_frame)

        info_title = QLabel("ℹ️ One-way sync: iRecord → Observatum")
        info_title.setStyleSheet(f"font-weight: bold; color: {t.get('info')};")
        info_layout.addWidget(info_title)

        info_text = QLabel("iRecord is the authoritative source. Changes made on iRecord will update local records during sync. Local changes do not overwrite iRecord data.")
        info_text.setStyleSheet(f"color: {t.get('info')}; font-size: 12px;")
        info_text.setWordWrap(True)
        info_layout.addWidget(info_text)

        # Sync status row
        sync_status_layout = QHBoxLayout()
        sync_status_layout.setContentsMargins(0, 8, 0, 0)
        
        sync_method_label = QLabel("Sync Method: Manual (CSV download)")
        sync_method_label.setStyleSheet(f"color: {t.get('info')}; font-size: 12px;")
        sync_status_layout.addWidget(sync_method_label)
        
        sync_status_layout.addStretch()
        
        self.last_sync_label = QLabel("Last Sync: Never")
        self.last_sync_label.setStyleSheet(f"color: {t.get('info')}; font-size: 12px;")
        sync_status_layout.addWidget(self.last_sync_label)
        
        info_layout.addLayout(sync_status_layout)

        layout.addWidget(info_frame)

    def _setup_protected_fields(self, layout):
        """Set up protected fields group."""
        t = theme()
        
        protected_group = QGroupBox("Protected Local Fields")
        protected_layout = QVBoxLayout(protected_group)
        
        protected_desc = QLabel("These fields are never overwritten during iRecord sync:")
        protected_desc.setStyleSheet(f"color: {t.get('text_secondary')}; margin-bottom: 8px;")
        protected_layout.addWidget(protected_desc)
        
        for field in ["Site name (local)", "Internal notes", "Specimen links", "Embargo status"]:
            field_lbl = QLabel(f"✔ {field}")
            field_lbl.setStyleSheet(f"color: {t.get('success')};")
            protected_layout.addWidget(field_lbl)
        
        layout.addWidget(protected_group)
    
    def load_settings(self):
        """Public method to load settings. Called by settings_tab.py."""
        self._load_settings()
    
    def _load_settings(self):
        """Load settings from QSettings."""
        settings = QSettings()
        last_sync = settings.value(Settings.SYNC_LAST_SYNC, "Never")
        self.last_sync_label.setText(f"Last Sync: {last_sync}")

    def apply_theme(self):
        """Apply the current theme to all components."""
        # Would need to store frame references for full theme update
        pass