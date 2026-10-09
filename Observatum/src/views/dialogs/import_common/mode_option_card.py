"""The clickable mode card on the first page of the observation and scheme import wizards
(C4, 9 Oct 2026; each wizard had its own identical copy).

The class must keep the name ModeOptionCard: its style sheet selects on it."""
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout
from PySide6.QtCore import Qt

from src.themes import theme


class ModeOptionCard(QFrame):
    """A clickable card for mode selection."""

    def __init__(self, title: str, description: str, mode_id: str, accent_color: str, parent=None):
        super().__init__(parent)
        self.accent_color = accent_color
        self.mode_id = mode_id
        self._selected = False
        self._on_clicked = None

        t = theme()

        self.setObjectName("modeCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_style(False)

        layout = QHBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)

        # Custom radio indicator
        self.indicator = QLabel()
        self.indicator.setFixedSize(20, 20)
        self._update_indicator(False)
        layout.addWidget(self.indicator)

        # Text content
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"""
            font-weight: 600;
            font-size: 14px;
            color: {t.get('text_primary')};
            background: transparent;
            border: none;
        """)
        text_layout.addWidget(self.title_label)

        self.desc_label = QLabel(description)
        self.desc_label.setStyleSheet(f"""
            color: {t.get('text_secondary')};
            font-size: 12px;
            background: transparent;
            border: none;
        """)
        self.desc_label.setWordWrap(True)
        text_layout.addWidget(self.desc_label)

        layout.addLayout(text_layout, 1)

    def _update_style(self, selected: bool):
        """Update card border and background."""
        t = theme()
        border_color = self.accent_color if selected else t.get('border')
        bg_color = t.get('surface')

        self.setStyleSheet(f"""
            ModeOptionCard {{
                background-color: {bg_color};
                border: 2px solid {border_color};
                border-radius: {t.get('radius_lg')};
            }}
            ModeOptionCard:hover {{
                border-color: {self.accent_color};
            }}
        """)

    def _update_indicator(self, selected: bool):
        """Update the radio indicator circle."""
        t = theme()

        if selected:
            self.indicator.setStyleSheet(f"""
                background-color: {self.accent_color};
                border: 2px solid {self.accent_color};
                border-radius: 6px;
            """)
        else:
            self.indicator.setStyleSheet(f"""
                background-color: {t.get('surface')};
                border: 2px solid {t.get('border_strong')};
                border-radius: 6px;
            """)

    def setSelected(self, selected: bool):
        """Set the selection state."""
        self._selected = selected
        self._update_style(selected)
        self._update_indicator(selected)

    def isSelected(self) -> bool:
        return self._selected

    def mousePressEvent(self, event):
        """Handle click to select."""
        if self._on_clicked:
            self._on_clicked()
        super().mousePressEvent(event)

    def setClickCallback(self, callback):
        """Set callback for when card is clicked."""
        self._on_clicked = callback
