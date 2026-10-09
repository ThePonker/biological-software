"""
Examen - Main Window

Three-view species assessment tool replacing the Pantheon website.
Views: Species Database, Site Analysis, Assessment Archive.
Themed to match Observatum's Naturalist theme.

Instantiates shared CodexRepository, PantheonRepository, and
PantheonAnalysisService — passed to views for consistent data access.
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTabWidget, QStatusBar, QComboBox,
)
from PySide6.QtGui import QFont

from shared.repositories.codex_repository import CodexRepository, AnalysisMode
from shared.repositories.pantheon_repository import PantheonRepository
from shared.services.pantheon_analysis_service import PantheonAnalysisService
from shared.display_format import mode_label

from .species_database_view import SpeciesDatabaseView
from .site_analysis_view import SiteAnalysisView
from .assessment_archive_view import AssessmentArchiveView
from .snapshot_manager import SnapshotManager


# Naturalist palette
BG = "#f5f5f4"
SURFACE = "#ffffff"
TEXT_PRIMARY = "#1f2937"
TEXT_HEADING = "#4b5563"
TEXT_SECONDARY = "#6b7280"
TEXT_MUTED = "#9ca3af"
BORDER = "#d1d5db"
SEPARATOR = "#e5e7eb"
ACCENT = "#7c6c9f"
ACCENT_LIGHT = "#f0edf5"
ACCENT_DARK = "#5a4d78"


class ExamenWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Examen \u2014 Species Assessment Tool")
        self.setMinimumSize(1200, 700)
        self._mode = AnalysisMode.CODEX_FULL

        # Shared data layer
        self._codex_repo = CodexRepository()
        self._pantheon_repo = PantheonRepository()
        self._analysis_service = PantheonAnalysisService(
            self._pantheon_repo, self._codex_repo)
        self._snapshot_mgr = SnapshotManager()

        self._setup_ui()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header bar
        header = QWidget()
        header.setStyleSheet(
            "QWidget { background-color: " + ACCENT_LIGHT + "; "
            "border-bottom: 1px solid " + BORDER + "; }")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 10, 16, 10)

        title = QLabel("Examen")
        title.setFont(QFont("Georgia", 16, QFont.Weight.Bold))
        title.setStyleSheet(
            "color: " + ACCENT_DARK + "; border: none; background: none;")
        header_layout.addWidget(title)

        subtitle = QLabel("\u2014  Species Assessment Tool")
        subtitle.setFont(QFont("Georgia", 10))
        subtitle.setStyleSheet(
            "color: " + TEXT_SECONDARY + "; border: none; background: none;")
        header_layout.addWidget(subtitle)
        header_layout.addStretch()

        # Mode selector
        mode_label = QLabel("Analysis mode:")
        mode_label.setStyleSheet(
            "color: " + TEXT_SECONDARY + "; font-size: 11px; "
            "border: none; background: none;")
        header_layout.addWidget(mode_label)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Codex Full (enriched)", AnalysisMode.CODEX_FULL)
        self.mode_combo.addItem("Pantheon Only (strict)", AnalysisMode.PANTHEON_ONLY)
        self.mode_combo.setStyleSheet(
            "QComboBox { background: " + SURFACE + "; color: " + TEXT_PRIMARY + "; "
            "padding: 4px 8px; border: 1px solid " + BORDER + "; "
            "border-radius: 4px; min-width: 180px; font-size: 12px; }"
            "QComboBox::drop-down { border: none; }")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        header_layout.addWidget(self.mode_combo)

        layout.addWidget(header)

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            "QTabWidget::pane { border: none; background: " + BG + "; }"
            "QTabBar::tab { padding: 10px 24px; font-size: 12px; "
            "border: none; border-bottom: 3px solid transparent; "
            "color: " + TEXT_MUTED + "; background: none; }"
            "QTabBar::tab:selected { color: " + ACCENT_DARK + "; "
            "border-bottom: 3px solid " + ACCENT + "; font-weight: bold; }"
            "QTabBar::tab:hover:!selected { color: " + TEXT_SECONDARY + "; "
            "border-bottom: 3px solid " + SEPARATOR + "; }")

        self.species_view = SpeciesDatabaseView(
            self._codex_repo, self._pantheon_repo)
        self.analysis_view = SiteAnalysisView(
            self._analysis_service, self._snapshot_mgr)
        self.archive_view = AssessmentArchiveView(
            self._analysis_service, self._snapshot_mgr)

        self.tabs.addTab(self.species_view, "Species Database")
        self.tabs.addTab(self.analysis_view, "Site Analysis")
        self.tabs.addTab(self.archive_view, "Assessment Archive")

        layout.addWidget(self.tabs, 1)

        # Status bar
        self.status = QStatusBar()
        self.status.setStyleSheet(
            "font-size: 11px; color: " + TEXT_MUTED + "; "
            "background: " + SURFACE + "; "
            "border-top: 1px solid " + SEPARATOR + ";")
        self.setStatusBar(self.status)
        self._update_status()

    def _on_mode_changed(self, index):
        self._mode = self.mode_combo.currentData()
        self.analysis_view.set_mode(self._mode)
        self._update_status()

    def _update_status(self):
        self.status.showMessage(f"Mode: {mode_label(self._mode)}")

    def closeEvent(self, event):
        self._codex_repo.close()
        self._pantheon_repo.close()
        self._snapshot_mgr.close()
        super().closeEvent(event)
