"""
Gamification Launcher Widget for Observatum V2.

A button/card widget that can be added to any tab to launch the gamification window.
Designed to be dropped into the home tab.

Dark Victorian theme compatible.

Usage:
    from src.features.gamification import GamificationLauncher

    # In your tab's layout:
    launcher = GamificationLauncher(parent=self)
    layout.addWidget(launcher)
"""

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
)
from PySide6.QtCore import Qt, QTimer



class GamificationLauncher(QFrame):
    """
    A card widget with a button to launch the gamification window.

    Displays current tier and a button to view achievements.
    """

    def __init__(self, parent=None, show_stats: bool = True):
        """
        Initialize the launcher.

        Args:
            parent: Parent widget
            show_stats: If True, shows current tier info. If False, just shows button.
        """
        super().__init__(parent)
        self._window = None
        self._show_stats = show_stats
        self._stats_loaded = False

        self._setup_ui()

        if show_stats:
            QTimer.singleShot(500, self._load_quick_stats)

    def _setup_ui(self):
        """Setup the widget UI."""
        self.setStyleSheet("""
            QFrame {
                background-color: #f0f7f4;
                border: 1px solid #5f8575;
                border-radius: 8px;
                padding: 12px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)

        # Icon
        icon_label = QLabel("🏆")
        icon_label.setStyleSheet("font-size: 32px; background: transparent; border: none;")
        layout.addWidget(icon_label)

        # Text content
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)

        title = QLabel("Achievements")
        title.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #4a6b5c;
            background: transparent;
            border: none;
        """)
        text_layout.addWidget(title)

        if self._show_stats:
            self.tier_label = QLabel("Track your naturalist progress")
            self.tier_label.setStyleSheet("""
                font-size: 12px;
                color: #6b7280;
                background: transparent;
                border: none;
            """)
            text_layout.addWidget(self.tier_label)

        layout.addLayout(text_layout, 1)

        # Launch button
        self.launch_btn = QPushButton("View Progress")
        self.launch_btn.setStyleSheet("""
            QPushButton {
                background-color: #5f8575;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #4a6b5c;
            }
        """)
        self.launch_btn.clicked.connect(self._launch_window)
        layout.addWidget(self.launch_btn)

    def _load_quick_stats(self):
        """Load quick tier stats for display."""
        if self._stats_loaded:
            return

        try:
            from .calculator import GamificationCalculator
            from .setup import ensure_gamification_db

            ensure_gamification_db()

            calc = GamificationCalculator()
            tier = calc.calculate_current_tier()

            self.tier_label.setText(
                f"Tier {tier['tier_number']}: {tier['tier_name']} • "
                f"{tier['unique_species']:,} species"
            )
            self._stats_loaded = True
        except Exception as e:
            if hasattr(self, 'tier_label'):
                self.tier_label.setText("Track your naturalist progress")

    def refresh_stats(self):
        """Refresh the stats display. Call after observations change."""
        self._stats_loaded = False
        self._load_quick_stats()

    def _launch_window(self):
        """Launch the gamification window."""
        try:
            from .window import GamificationWindow

            if self._window is None or not self._window.isVisible():
                self._window = GamificationWindow(self.window())
                self._window.show()
            else:
                self._window.raise_()
                self._window.activateWindow()

        except Exception as e:
            print(f"[Gamification] Error launching window: {e}")
            import traceback
            traceback.print_exc()

            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Error",
                f"Could not open achievements window:\n{e}"
            )


class GamificationButton(QPushButton):
    """
    A simple button to launch the gamification window.

    Use this instead of GamificationLauncher if you just want a button.
    """

    def __init__(self, text: str = "🏆 Achievements", parent=None):
        super().__init__(text, parent)
        self._window = None

        self.setStyleSheet("""
            QPushButton {
                background-color: #5f8575;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 500;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #4a6b5c;
            }
        """)

        self.clicked.connect(self._launch_window)

    def _launch_window(self):
        """Launch the gamification window."""
        try:
            from .window import GamificationWindow
            from .setup import ensure_gamification_db

            ensure_gamification_db()

            if self._window is None or not self._window.isVisible():
                self._window = GamificationWindow(self.window())
                self._window.show()
            else:
                self._window.raise_()
                self._window.activateWindow()

        except Exception as e:
            print(f"[Gamification] Error launching window: {e}")
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Error",
                f"Could not open achievements window:\n{e}"
            )


class GamificationSummaryCard(QFrame):
    """
    A wider summary card for the home screen showing multiple achievement stats.
    
    Displays:
    - Current tier with progress bar
    - Vice Counties visited
    - Families recorded
    - Rare species found
    - Records earned
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._window = None
        self._stats_loaded = False
        
        self._setup_ui()
        QTimer.singleShot(500, self._load_stats)
    
    def _setup_ui(self):
        """Setup the widget UI."""
        self.setStyleSheet("""
            QFrame#summaryCard {
                background-color: #f0f7f4;
                border: 1px solid #5f8575;
                border-radius: 8px;
            }
        """)
        self.setObjectName("summaryCard")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(12)
        
        # Header row
        header = QHBoxLayout()
        header.setSpacing(12)
        
        icon_label = QLabel("🏆")
        icon_label.setStyleSheet("font-size: 28px; background: transparent; border: none;")
        header.addWidget(icon_label)
        
        title = QLabel("Naturalist Achievements")
        title.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #4a6b5c;
            background: transparent;
            border: none;
        """)
        header.addWidget(title)
        header.addStretch()
        
        self.launch_btn = QPushButton("View All")
        self.launch_btn.setStyleSheet("""
            QPushButton {
                background-color: #5f8575;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 500;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #4a6b5c;
            }
        """)
        self.launch_btn.clicked.connect(self._launch_window)
        header.addWidget(self.launch_btn)
        
        main_layout.addLayout(header)
        
        # Tier info row
        tier_row = QHBoxLayout()
        tier_row.setSpacing(12)
        
        self.tier_label = QLabel("Loading...")
        self.tier_label.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #2d5a4a;
            background: transparent;
            border: none;
        """)
        tier_row.addWidget(self.tier_label)
        
        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet("""
            font-size: 12px;
            color: #6b7280;
            background: transparent;
            border: none;
        """)
        tier_row.addWidget(self.progress_label)
        tier_row.addStretch()
        
        main_layout.addLayout(tier_row)
        
        # Stats grid
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(8)
        
        self.stat_widgets = {}
        stat_configs = [
            ("species", "Species", "🦋"),
            ("vcs", "Vice Counties", "📍"),
            ("families", "Families", "🏷️"),
            ("rare", "Rare Species", "⭐"),
            ("records", "Records", "🎖️"),
        ]
        
        for key, label, icon in stat_configs:
            widget = self._create_stat_box(icon, "0", label)
            self.stat_widgets[key] = widget
            stats_layout.addWidget(widget)
        
        main_layout.addLayout(stats_layout)
    
    def _create_stat_box(self, icon: str, value: str, label: str) -> QFrame:
        """Create a small stat display box."""
        box = QFrame()
        box.setStyleSheet("""
            QFrame {
                background-color: #e8f4ed;
                border: 1px solid #c8ddd0;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        
        layout = QVBoxLayout(box)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Icon + Value row
        top_row = QHBoxLayout()
        top_row.setSpacing(4)
        top_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size: 14px; background: transparent; border: none;")
        top_row.addWidget(icon_lbl)
        
        value_lbl = QLabel(value)
        value_lbl.setObjectName("value")
        value_lbl.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #2d5a4a;
            background: transparent;
            border: none;
        """)
        top_row.addWidget(value_lbl)
        
        layout.addLayout(top_row)
        
        # Label
        label_lbl = QLabel(label)
        label_lbl.setStyleSheet("""
            font-size: 10px;
            color: #6b7280;
            background: transparent;
            border: none;
        """)
        label_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label_lbl)
        
        return box
    
    def _update_stat(self, key: str, value: str):
        """Update a stat widget's value."""
        if key in self.stat_widgets:
            value_label = self.stat_widgets[key].findChild(QLabel, "value")
            if value_label:
                value_label.setText(value)
    
    def _load_stats(self):
        """Load achievement stats."""
        if self._stats_loaded:
            return
        
        try:
            from .calculator import GamificationCalculator
            from .setup import ensure_gamification_db
            
            ensure_gamification_db()
            
            calc = GamificationCalculator()
            
            # Get tier info
            tier = calc.calculate_current_tier()
            self.tier_label.setText(f"Tier {tier['tier_number']}: {tier['tier_name']}")
            
            if tier['next_tier']:
                progress = f"{tier['unique_species']:,} / {tier['next_threshold']:,} species"
            else:
                progress = f"{tier['unique_species']:,} species (Max tier!)"
            self.progress_label.setText(progress)
            
            # Update species stat
            self._update_stat("species", f"{tier['unique_species']:,}")
            
            # Get VC info
            try:
                vc_coverage = calc.get_vice_county_coverage()
                total_vcs = sum(r["covered"] for r in vc_coverage["regions"].values())
                self._update_stat("vcs", str(total_vcs))
            except:
                self._update_stat("vcs", "0")
            
            # Get family info
            try:
                family_data = calc.get_family_achievements()
                self._update_stat("families", str(family_data["total_families"]))
            except:
                self._update_stat("families", "0")
            
            # Get rare species info
            try:
                rare_summary = calc.get_rare_species_summary()
                self._update_stat("rare", str(rare_summary["total"]))
            except:
                self._update_stat("rare", "0")
            
            # Get records info
            try:
                records_summary = calc.get_one_time_achievements_summary()
                self._update_stat("records", f"{records_summary['earned']}")
            except:
                self._update_stat("records", "0")
            
            self._stats_loaded = True
            
        except Exception as e:
            print(f"[Gamification] Error loading stats: {e}")
            self.tier_label.setText("Achievements")
            self.progress_label.setText("Track your naturalist progress")
    
    def refresh_stats(self):
        """Refresh the stats display."""
        self._stats_loaded = False
        self._load_stats()
    
    def _launch_window(self):
        """Launch the gamification window."""
        try:
            from .window import GamificationWindow
            
            if self._window is None or not self._window.isVisible():
                self._window = GamificationWindow(self.window())
                self._window.show()
            else:
                self._window.raise_()
                self._window.activateWindow()
        except Exception as e:
            print(f"[Gamification] Error launching window: {e}")
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Error", f"Could not open achievements:\n{e}")
