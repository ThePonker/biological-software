"""
Export Settings Panel Component.

Export location settings.
"""

from PySide6.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QGroupBox, QFrame, QFileDialog
)
from PySide6.QtCore import QSettings

from ...themes import theme
from ...core.config import Settings


class ExportSettingsPanel(QScrollArea):
    """Export settings panel."""

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

        # Export location group
        location_group = QGroupBox("Default Export Location")
        location_layout = QVBoxLayout(location_group)

        location_desc = QLabel("Set the default folder for CSV exports.")
        location_desc.setStyleSheet(f"color: {t.get('text_secondary')};")
        location_layout.addWidget(location_desc)

        path_layout = QHBoxLayout()
        self.export_path = QLineEdit()
        self.export_path.setPlaceholderText("No default location set")
        self.export_path.setStyleSheet(f"""
            QLineEdit {{
                font-family: monospace;
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_sm')};
                padding: 8px;
            }}
        """)
        self.export_path.setMinimumHeight(36)
        path_layout.addWidget(self.export_path, 1)

        browse_btn = QPushButton("Browse...")
        browse_btn.setMinimumHeight(36)
        browse_btn.clicked.connect(self._browse_export_location)
        path_layout.addWidget(browse_btn)

        location_layout.addLayout(path_layout)
        layout.addWidget(location_group)

        layout.addStretch()
        self.setWidget(content)

    def load_settings(self):
        """Public method to load settings. Called by settings_tab.py."""
        self._load_settings()

    def _load_settings(self):
        """Load settings from QSettings."""
        settings = QSettings()
        self.export_path.setText(settings.value(Settings.EXPORT_DEFAULT_PATH, ""))

    def _browse_export_location(self):
        """Browse for export location."""
        path = QFileDialog.getExistingDirectory(self, "Select Export Location")
        if path:
            self.export_path.setText(path)
            self.save_settings()

    def save_settings(self):
        """Save settings to QSettings."""
        settings = QSettings()
        settings.setValue(Settings.EXPORT_DEFAULT_PATH, self.export_path.text())

    def apply_theme(self):
        """Apply the current theme to all components."""
        pass
