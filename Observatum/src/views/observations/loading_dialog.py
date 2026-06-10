"""
Loading Dialog Helper for Observatum V2.
Provides a simple loading dialog with progress bar for long operations.
Styled to match the current theme.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QProgressBar, QApplication
)
from PySide6.QtCore import Qt

from ...themes import theme
from ...core.config import TabColors


class LoadingDialog(QDialog):
    """Simple loading dialog styled to match current theme."""

    def __init__(self, message: str = "Loading...", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Observatum")
        self.setModal(True)
        self.setFixedSize(380, 100)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.CustomizeWindowHint
        )
        self._setup_ui(message)

    def _setup_ui(self, message: str):
        """Setup the UI with current theme."""
        t = theme()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Message label
        self.message_label = QLabel(message)
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.message_label.setStyleSheet(f"""
            font-family: 'Segoe UI', sans-serif;
            font-size: 12px;
            color: {t.get('text_primary')};
            background: transparent;
        """)
        layout.addWidget(self.message_label)

        # Progress bar - use Observation accent color
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # Indeterminate mode
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                border-radius: 0px;
                background-color: {t.get('surface_alt')};
            }}
            QProgressBar::chunk {{
                background-color: {TabColors.OBSERVATION};
            }}
        """)
        layout.addWidget(self.progress)

        layout.addStretch()

        # Dialog background
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
            }}
        """)

    def set_message(self, message: str):
        """Update the loading message."""
        self.message_label.setText(message)
        QApplication.processEvents()

    def show_and_process(self):
        """Show dialog and process events to ensure it displays."""
        self.show()
        QApplication.processEvents()
