"""Pages shared by the observation and scheme import wizards (C4, 9 Oct 2026; each had its
own identical copy): the confirmation page's stat cards, the import-progress page and the
summary page. Needs self.stack and self._accent from the wizard."""
from PySide6.QtWidgets import QFrame, QLabel, QProgressBar, QVBoxLayout, QWidget
from PySide6.QtCore import Qt

from src.themes import theme


class ImportProgressPagesMixin:
    """_create_stat_card, _create_import_page, _create_summary_page."""

    def _create_stat_card(self, label: str, value: str, color: str) -> QFrame:
        """Create a stat card for confirmation page."""
        t = theme()

        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface_alt')};
                border-radius: {t.get('radius_md')};
                padding: 12px 20px;
            }}
        """)

        layout = QVBoxLayout(frame)
        layout.setSpacing(4)
        layout.setContentsMargins(0, 0, 0, 0)

        value_label = QLabel(value)
        value_label.setStyleSheet(f"font-size: 24px; font-weight: 700; color: {color};")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_label.setObjectName("value_label")
        layout.addWidget(value_label)

        name_label = QLabel(label)
        name_label.setStyleSheet(f"font-size: 12px; color: {t.get('text_secondary')};")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_label)

        return frame

    def _create_import_page(self):
        """Step 6: Import progress."""
        t = theme()

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)

        layout.addStretch()

        # Status label
        self.import_status_label = QLabel("Preparing import...")
        self.import_status_label.setStyleSheet(f"font-size: 16px; color: {t.get('text_primary')};")
        self.import_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.import_status_label)

        # Progress bar
        self.import_progress = QProgressBar()
        self.import_progress.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_md')};
                background-color: {t.get('surface_alt')};
                text-align: center;
                height: 28px;
                font-weight: 600;
            }}
            QProgressBar::chunk {{
                background-color: {self._accent};
                border-radius: {t.get('radius_sm')};
            }}
        """)
        self.import_progress.setMinimum(0)
        self.import_progress.setMaximum(100)
        layout.addWidget(self.import_progress)

        # Counts during import
        self.import_counts_label = QLabel("")
        self.import_counts_label.setStyleSheet(f"color: {t.get('text_secondary')};")
        self.import_counts_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.import_counts_label)

        layout.addStretch()

        self.stack.addWidget(page)

    def _create_summary_page(self):
        """Step 7: Import summary."""
        t = theme()

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)

        layout.addStretch()

        # Icon
        self.summary_icon = QLabel("✓")
        self.summary_icon.setStyleSheet(f"font-size: 64px; color: {t.get('success')};")
        self.summary_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.summary_icon)

        # Title
        self.summary_title = QLabel("Import Complete!")
        self.summary_title.setStyleSheet(f"font-size: 20px; font-weight: 600; color: {t.get('text_primary')};")
        self.summary_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.summary_title)

        # Stats
        self.summary_stats = QLabel("")
        self.summary_stats.setStyleSheet(f"font-size: 14px; color: {t.get('text_secondary')};")
        self.summary_stats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.summary_stats)

        layout.addStretch()

        self.stack.addWidget(page)
