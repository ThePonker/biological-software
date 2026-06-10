"""
Section Toggle Component.

Toggle buttons for switching between stats sections.
"""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton
from PySide6.QtCore import Qt, Signal

from ...themes import theme
from ...core.config import TabColors


class SectionToggle(QFrame):
    """Toggle buttons for switching between stats sections."""

    section_changed = Signal(str)

    # Section definitions: (id, label, accent_color, bg_color, text_color)
    SECTIONS = [
        ('personal', 'Personal Stats', TabColors.PERSONAL, TabColors.PERSONAL_LIGHT, TabColors.PERSONAL_DARK),
        ('commercial_stats', 'Commercial Stats', TabColors.COMMERCIAL, TabColors.COMMERCIAL_LIGHT, TabColors.COMMERCIAL_DARK),
        ('all_stats', 'All Stats', TabColors.OBSERVATION, TabColors.OBSERVATION_LIGHT, TabColors.OBSERVATION_DARK),
        ('commercial_reports', 'Commercial Reports', TabColors.COMMERCIAL, TabColors.COMMERCIAL_LIGHT, TabColors.COMMERCIAL_DARK),
        ('scheme', 'Recording Scheme', TabColors.RECORDING_SCHEME, TabColors.RECORDING_SCHEME_LIGHT, TabColors.RECORDING_SCHEME_DARK),
        ('collection', 'Insect Collection', TabColors.COLLECTION, TabColors.COLLECTION_LIGHT, TabColors.COLLECTION_DARK),
        ('species', 'Species', TabColors.SPECIES, TabColors.SPECIES_LIGHT, TabColors.SPECIES_DARK),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current = 'personal'
        self._buttons = {}
        self._setup_ui()

    def _setup_ui(self):
        t = theme()
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border-bottom: 1px solid {t.get('border')};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(8)

        for section_id, label, _, bg_color, text_color in self.SECTIONS:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(section_id == 'personal')
            btn.setProperty('section_id', section_id)
            btn.setProperty('colors', (bg_color, text_color))
            btn.clicked.connect(lambda checked, sid=section_id: self._on_clicked(sid))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._buttons[section_id] = btn
            layout.addWidget(btn)

        layout.addStretch()
        self._update_styles()

    def _on_clicked(self, section_id: str):
        """Handle section button click."""
        if section_id == self._current:
            self._buttons[section_id].setChecked(True)
            return

        self._current = section_id
        for sid, btn in self._buttons.items():
            btn.setChecked(sid == section_id)
        self._update_styles()
        self.section_changed.emit(section_id)

    def _update_styles(self):
        """Update button styles based on selection."""
        t = theme()

        for section_id, btn in self._buttons.items():
            bg_color, text_color = btn.property('colors')
            if btn.isChecked():
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {bg_color};
                        color: {text_color};
                        border: none;
                        border-radius: {t.get('radius_sm')};
                        padding: 8px 16px;
                        font-size: {t.font_size('base')};
                        font-weight: 600;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        color: {t.get('text_secondary')};
                        border: none;
                        border-radius: {t.get('radius_sm')};
                        padding: 8px 16px;
                        font-size: {t.font_size('base')};
                    }}
                    QPushButton:hover {{ background-color: {t.get('hover')}; }}
                """)

    def apply_theme(self):
        """Apply the current theme."""
        t = theme()
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border-bottom: 1px solid {t.get('border')};
            }}
        """)
        self._update_styles()
