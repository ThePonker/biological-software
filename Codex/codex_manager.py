"""
Codex Manager — Main Window

Two tabs:
  1. Reviews — browse loaded reviews
  2. Species — search and view species statuses

Reviews are loaded by scripts/import_status_review.py (dry run, backup, then
--apply), never from this window. The Import Review tab (preview-only since F9,
with its own drifted resolution rules) and the Unresolved tab (read a CSV only
that importer wrote, so it could never fill) were retired 10 Oct 2026 (CDX-3):
_archive/codex_tabs_20261010/.
"""

from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout, QLabel, QHBoxLayout,
    QStatusBar
)
from PySide6.QtGui import QFont

from . import theme
from .reviews_tab import ReviewsTab
from .species_tab import SpeciesTab

# Where reviews come from now (CDX-3): shown under the tabs.
IMPORT_NOTE = ("New reviews are loaded with scripts\\import_status_review.py "
               "(dry run first, then --apply; it backs up codex.db), not from this window.")


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
        self.species_tab = SpeciesTab()

        self.tabs.addTab(self.reviews_tab, "Reviews")
        self.tabs.addTab(self.species_tab, "Species Search")

        # Refresh data when switching tabs
        self.tabs.currentChanged.connect(self._on_tab_changed)

        layout.addWidget(self.tabs, 1)

        note = QLabel(IMPORT_NOTE)
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; font-size: 11px; padding: 4px 20px;")
        layout.addWidget(note)

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
        # index 1: the species tab searches on demand

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
