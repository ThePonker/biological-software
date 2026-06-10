"""
Codex Manager — Main Window

Four-tab interface for managing conservation status data:
  1. Reviews — browse loaded reviews
  2. Import — import new reviews from CSV
  3. Species — search and view species statuses
  4. Unresolved — manage species that failed UKSI resolution
"""

from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout, QLabel, QHBoxLayout,
    QStatusBar
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from . import theme
from .reviews_tab import ReviewsTab
from .import_tab import ImportTab
from .species_tab import SpeciesTab
from .unresolved_tab import UnresolvedTab


class CodexManager(QMainWindow):
    """Main Codex Manager window."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Codex — Conservation Status Manager")
        self.setMinimumSize(900, 620)
        self._setup_ui()
        self.showMaximized()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setStyleSheet(
            f"background-color: {theme.ACCENT};"
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 12, 20, 12)

        title = QLabel("CODEX")
        title.setFont(QFont("", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: white; letter-spacing: 3px;")
        header_layout.addWidget(title)

        subtitle = QLabel("Conservation Status Manager")
        subtitle.setStyleSheet(f"color: {theme.ACCENT_LIGHT}; font-size: 12px;")
        header_layout.addWidget(subtitle)
        header_layout.addStretch()

        layout.addWidget(header)

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                background-color: {theme.SURFACE};
            }}
            QTabBar::tab {{
                padding: 10px 24px;
                font-size: 12px;
                font-weight: 600;
                color: {theme.TEXT_SECONDARY};
                border: none;
                border-bottom: 3px solid transparent;
                background-color: {theme.SURFACE};
            }}
            QTabBar::tab:selected {{
                color: {theme.ACCENT};
                border-bottom: 3px solid {theme.ACCENT};
            }}
            QTabBar::tab:hover {{
                color: {theme.TEXT_PRIMARY};
                background-color: {theme.HOVER};
            }}
        """)

        self.reviews_tab = ReviewsTab()
        self.import_tab = ImportTab()
        self.species_tab = SpeciesTab()
        self.unresolved_tab = UnresolvedTab()

        self.tabs.addTab(self.reviews_tab, "Reviews")
        self.tabs.addTab(self.import_tab, "Import Review")
        self.tabs.addTab(self.species_tab, "Species Search")
        self.tabs.addTab(self.unresolved_tab, "Unresolved")

        # Refresh data when switching tabs
        self.tabs.currentChanged.connect(self._on_tab_changed)

        # Signal: import completed → refresh reviews + species
        self.import_tab.import_completed.connect(self._on_import_completed)

        layout.addWidget(self.tabs, 1)

        # Status bar
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet(
            f"background-color: {theme.SURFACE_ALT}; "
            f"color: {theme.TEXT_SECONDARY}; font-size: 11px;"
        )
        self.setStatusBar(self.status_bar)
        self._update_status()

    def _on_tab_changed(self, index):
        if index == 0:
            self.reviews_tab.refresh()
        elif index == 2:
            pass  # species tab searches on demand
        elif index == 3:
            self.unresolved_tab.refresh()

    def _on_import_completed(self):
        self.reviews_tab.refresh()
        self._update_status()
        self.tabs.setCurrentIndex(0)  # Switch to reviews tab

    def _update_status(self):
        try:
            from shared.repositories.codex_repository import CodexRepository
            repo = CodexRepository()
            count = repo.get_species_count()
            reviews = repo.get_reviews()
            repo.close()
            self.status_bar.showMessage(
                f"Codex: {count:,} species  |  {len(reviews)} reviews loaded"
            )
        except Exception as e:
            self.status_bar.showMessage(f"Codex: {e}")
