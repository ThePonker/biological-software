"""
Curator — Settings Dialog

Persists: default font, font size, and my-specimens-only toggle.
Stored in Curator/settings.json.
"""

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QSpinBox, QCheckBox, QPushButton, QFrame, QFormLayout,
)

SETTINGS_PATH = Path(__file__).parent / "settings.json"

DEFAULTS = {
    "font_family": "Libre Baskerville",
    "font_size": 11,
    "my_specimens_only": False,
    "show_my_specimens": False,
    "show_my_species": False,
    "show_fauna": False,
}


def _get_fonts():
    from .planner_fonts import get_available_fonts
    return get_available_fonts()


def load_settings() -> dict:
    """Load settings from JSON, falling back to defaults."""
    settings = dict(DEFAULTS)
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            settings.update(saved)
        except Exception:
            pass
    return settings


def save_settings(settings: dict):
    """Save settings to JSON."""
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)


class SettingsDialog(QDialog):
    """Settings dialog for Curator defaults."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Curator Settings")
        self.setFixedWidth(340)
        self._settings = load_settings()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Default Settings")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title)

        info = QLabel("These apply when Curator starts.")
        info.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(info)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #ddd;")
        layout.addWidget(sep)

        form = QFormLayout()
        form.setSpacing(10)

        self.font_combo = QComboBox()
        fonts = _get_fonts()
        self.font_combo.addItems(fonts)
        idx = fonts.index(self._settings["font_family"]) if self._settings["font_family"] in fonts else 0
        self.font_combo.setCurrentIndex(idx)
        form.addRow("Font:", self.font_combo)

        self.size_spin = QSpinBox()
        self.size_spin.setRange(6, 24)
        self.size_spin.setValue(self._settings["font_size"])
        self.size_spin.setSuffix(" pt")
        form.addRow("Font size:", self.size_spin)

        self.my_specimens_cb = QCheckBox("My specimens only on startup")
        self.my_specimens_cb.setChecked(self._settings["my_specimens_only"])
        form.addRow("", self.my_specimens_cb)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: #ddd;")
        form.addRow(sep2)

        form.addRow(QLabel("Default count toggles:"))

        self.show_my_specimens_cb = QCheckBox("My specimen numbers")
        self.show_my_specimens_cb.setChecked(self._settings["show_my_specimens"])
        form.addRow("", self.show_my_specimens_cb)

        self.show_my_species_cb = QCheckBox("My species numbers")
        self.show_my_species_cb.setChecked(self._settings["show_my_species"])
        form.addRow("", self.show_my_species_cb)

        self.show_fauna_cb = QCheckBox("GB fauna species numbers")
        self.show_fauna_cb.setChecked(self._settings["show_fauna"])
        form.addRow("", self.show_fauna_cb)

        layout.addLayout(form)
        layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(
            "padding: 6px 16px; border: 1px solid #8b8178; "
            "border-radius: 4px; color: #8b8178;"
        )
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(
            "padding: 6px 16px; background-color: #4a7c59; color: white; "
            "border: none; border-radius: 4px; font-weight: bold;"
        )
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

    def _save(self):
        self._settings["font_family"] = self.font_combo.currentText()
        self._settings["font_size"] = self.size_spin.value()
        self._settings["my_specimens_only"] = self.my_specimens_cb.isChecked()
        self._settings["show_my_specimens"] = self.show_my_specimens_cb.isChecked()
        self._settings["show_my_species"] = self.show_my_species_cb.isChecked()
        self._settings["show_fauna"] = self.show_fauna_cb.isChecked()
        save_settings(self._settings)
        self.accept()

    def get_settings(self) -> dict:
        return dict(self._settings)
