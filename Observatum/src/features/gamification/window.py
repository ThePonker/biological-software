"""
Observatum V2 Gamification Window
==================================
Main achievement window with dark Victorian naturalist theme.

6 Tabs:
- Overview: Tier rank + progress + stats
- Tiers: All 20 progression tiers
- Records: Daily/Annual records by group
- Vice Counties: VC badges + regional crowns
- Families: Ribbons + medals
- Rare Species: Pins + rosettes
"""

from typing import Dict, Any, Optional

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTabWidget, QMessageBox, QCheckBox
)
from PySide6.QtCore import Qt

from .calculator import GamificationCalculator
from .setup import ensure_gamification_db
from .renderer import AchievementRenderer
from .styles import get_dark_stylesheet, get_light_stylesheet
from .theme import TEXT, get_stage_colours

# Import tab classes
from .tabs import (
    OverviewTab, TiersTab, RecordsTab,
    VCsTab, FamiliesTab, RareTab
)


class GamificationWindow(QDialog):
    """
    Main gamification achievements window.
    Dark Victorian naturalist theme with 6 tabs.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowTitle("Observatum V2 - Achievements")
        self.setMinimumSize(900, 700)
        
        # Theme state
        self.dark_mode = True
        self.setStyleSheet(get_dark_stylesheet())
        
        # Ensure database exists
        if not ensure_gamification_db():
            QMessageBox.warning(
                self, "Warning",
                "Could not initialize gamification database.\n"
                "Some features may not work correctly."
            )
        
        # Initialize calculator and renderer
        self.calculator = GamificationCalculator()
        self.renderer = AchievementRenderer()
        
        # Initialize tab instances
        self.overview_tab = OverviewTab(self.renderer)
        self.tiers_tab = TiersTab(self.renderer)
        self.records_tab = RecordsTab(self.renderer)
        self.vcs_tab = VCsTab(self.renderer)
        self.families_tab = FamiliesTab(self.renderer)
        self.rare_tab = RareTab(self.renderer)
        
        # Setup UI
        self._setup_ui()
        
        # Load data
        self._load_data()
    
    def showEvent(self, event):
        """Override to open maximized."""
        super().showEvent(event)
        if not hasattr(self, '_shown_once'):
            self._shown_once = True
            self.showMaximized()
    
    def _setup_ui(self):
        """Setup the user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(20)
        
        # Header
        header = self._create_header()
        main_layout.addWidget(header)
        
        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.addTab(self.overview_tab.create(), "Overview")
        self.tabs.addTab(self.tiers_tab.create(), "Tiers")
        self.tabs.addTab(self.records_tab.create(), "Records")
        self.tabs.addTab(self.vcs_tab.create(), "Vice Counties")
        self.tabs.addTab(self.families_tab.create(), "Families")
        self.tabs.addTab(self.rare_tab.create(), "Rare Species")
        
        main_layout.addWidget(self.tabs, 1)
    
    def _create_header(self) -> QWidget:
        """Create the window header."""
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Title
        title = QLabel("Achievements")
        title.setObjectName("title")
        layout.addWidget(title)
        
        layout.addStretch()
        
        # Theme toggle
        theme_check = QCheckBox("Dark Mode")
        theme_check.setChecked(self.dark_mode)
        theme_check.stateChanged.connect(self._toggle_theme)
        layout.addWidget(theme_check)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.setObjectName("secondary")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
        
        return header
    
    def _toggle_theme(self, state):
        """Toggle between dark and light themes."""
        self.dark_mode = state == Qt.CheckState.Checked.value
        if self.dark_mode:
            self.setStyleSheet(get_dark_stylesheet())
        else:
            self.setStyleSheet(get_light_stylesheet())
    
    def _load_data(self):
        """Load and display all data."""
        try:
            # Load overview and get tier data for tiers tab
            tier_data = self.overview_tab.load(self.calculator, get_stage_colours)
            
            # Load other tabs
            self.tiers_tab.load(tier_data["tier_number"])
            self.records_tab.load(self.calculator)
            self.vcs_tab.load(self.calculator)
            self.families_tab.load(self.calculator)
            self.rare_tab.load(self.calculator)
            
        except Exception as e:
            print(f"[Gamification] Error loading data: {e}")
            import traceback
            traceback.print_exc()
