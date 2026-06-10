"""
Gamification Widgets for Observatum V2.

Reusable widget components for the gamification window.
"""

from typing import Dict, Any

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QWidget
)
from PySide6.QtCore import Qt

from .gamification_styles import get_colors


class StatCard(QFrame):
    """A card displaying a statistic with label."""
    
    def __init__(self, label: str, value: str, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(4)
        
        self.value_label = QLabel(value)
        self.value_label.setObjectName("statValue")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        text_label = QLabel(label)
        text_label.setObjectName("statLabel")
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(self.value_label)
        layout.addWidget(text_label)
    
    def set_value(self, value: str):
        """Update the displayed value."""
        self.value_label.setText(value)


class BadgeWidget(QFrame):
    """A widget displaying a badge with optional progress."""
    
    def __init__(self, name: str, earned: bool, progress: float = 0, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setFixedHeight(80)
        
        colors = get_colors()
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)
        
        name_label = QLabel(name)
        name_label.setWordWrap(True)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        if earned:
            name_label.setStyleSheet(f"color: {colors['primary']}; font-weight: bold;")
            self.setStyleSheet(f"""
                QFrame#card {{
                    background-color: {colors['primary_light']};
                    border: 2px solid {colors['primary']};
                }}
            """)
        else:
            name_label.setStyleSheet(f"color: {colors['text_secondary']};")
        
        layout.addWidget(name_label)
        
        if not earned and progress > 0:
            progress_bar = QProgressBar()
            progress_bar.setValue(int(progress))
            progress_bar.setTextVisible(False)
            progress_bar.setFixedHeight(6)
            layout.addWidget(progress_bar)


class TrophyWidget(QFrame):
    """A widget displaying a trophy with description and progress."""
    
    def __init__(self, name: str, description: str, earned: bool,
                 date_earned: str = None, progress: float = 0, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        
        colors = get_colors()
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        
        # Icon
        icon_label = QLabel("🏆" if earned else "🔒")
        icon_label.setStyleSheet("font-size: 24px;")
        icon_label.setFixedWidth(40)
        
        # Text content
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        
        name_label = QLabel(name)
        name_label.setStyleSheet(f"""
            font-weight: bold;
            color: {colors['primary'] if earned else colors['text_secondary']};
        """)
        
        desc_label = QLabel(description)
        desc_label.setStyleSheet(f"font-size: 11px; color: {colors['text_secondary']};")
        
        text_layout.addWidget(name_label)
        text_layout.addWidget(desc_label)
        
        if earned and date_earned:
            date_label = QLabel(f"Earned: {date_earned}")
            date_label.setStyleSheet(f"font-size: 10px; color: {colors['text_secondary']};")
            text_layout.addWidget(date_label)
        elif not earned and progress > 0:
            progress_label = QLabel(f"{progress:.1f}% complete")
            progress_label.setStyleSheet(f"font-size: 10px; color: {colors['warning']};")
            text_layout.addWidget(progress_label)
        
        layout.addWidget(icon_label)
        layout.addLayout(text_layout, 1)
        
        if earned:
            self.setStyleSheet(f"""
                QFrame#card {{
                    background-color: {colors['primary_light']};
                    border: 2px solid {colors['primary']};
                }}
            """)


class ViceCountyGrid(QFrame):
    """A grid showing vice county coverage statistics."""
    
    def __init__(self, coverage_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        
        colors = get_colors()
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Title
        title = QLabel("Vice County Coverage")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        
        # Stats row
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(24)
        
        covered = coverage_data.get("covered_vice_counties", 0)
        total = coverage_data.get("total_vice_counties", 112)
        percentage = coverage_data.get("coverage_percentage", 0)
        
        stats = [
            ("Counties", f"{covered}/{total}"),
            ("Coverage", f"{percentage}%"),
        ]
        
        # Add regional stats
        regions = coverage_data.get("regions", {})
        for region in ["England", "Scotland", "Wales"]:
            if region in regions:
                r = regions[region]
                stats.append((region, f"{r['covered']}/{r['total']}"))
        
        for label, value in stats:
            stat_widget = self._create_stat_widget(label, value, colors)
            stats_layout.addWidget(stat_widget)
        
        stats_layout.addStretch()
        layout.addLayout(stats_layout)
        
        # Progress bar
        progress = QProgressBar()
        progress.setValue(int(percentage))
        progress.setFormat(f"{percentage}%")
        progress.setFixedHeight(12)
        layout.addWidget(progress)
    
    def _create_stat_widget(self, label: str, value: str, colors: dict) -> QWidget:
        """Create a single stat display widget."""
        stat_widget = QWidget()
        stat_layout = QVBoxLayout(stat_widget)
        stat_layout.setContentsMargins(0, 0, 0, 0)
        stat_layout.setSpacing(2)
        
        value_label = QLabel(value)
        value_label.setStyleSheet(
            f"font-size: 18px; font-weight: bold; color: {colors['primary']};"
        )
        
        text_label = QLabel(label)
        text_label.setStyleSheet(
            f"font-size: 11px; color: {colors['text_secondary']};"
        )
        
        stat_layout.addWidget(value_label)
        stat_layout.addWidget(text_label)
        
        return stat_widget
