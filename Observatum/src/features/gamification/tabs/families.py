"""
Families Tab for Gamification Window.

Displays family ribbons and depth medals.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QGridLayout
)
from PySide6.QtCore import Qt, QByteArray
from PySide6.QtSvgWidgets import QSvgWidget

from ..theme import TEXT


class FamiliesTab:
    """
    Families tab showing ribbons (first) and medals (depth).
    
    Usage:
        tab = FamiliesTab(renderer)
        widget = tab.create()
        tab.load(calculator)
    """
    
    def __init__(self, renderer):
        """Initialize the families tab."""
        self.renderer = renderer
        
        # Widget references
        self.family_summary = None
        self.ribbon_layout = None
        self.medal_grid = None
    
    def create(self) -> QWidget:
        """Create and return the families tab widget."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Summary
        self.family_summary = QLabel("Loading...")
        self.family_summary.setObjectName("sectionTitle")
        layout.addWidget(self.family_summary)
        
        # Ribbons section
        ribbons_label = QLabel("Family First (Ribbons)")
        ribbons_label.setStyleSheet(f"font-size: 14px; color: {TEXT['secondary']};")
        layout.addWidget(ribbons_label)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(200)
        
        ribbon_container = QWidget()
        ribbon_container.setStyleSheet("background-color: transparent;")
        self.ribbon_layout = QHBoxLayout(ribbon_container)
        self.ribbon_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.ribbon_layout.setSpacing(10)
        
        scroll.setWidget(ribbon_container)
        layout.addWidget(scroll)
        
        # Medals section
        medals_label = QLabel("Family Depth (Medals)")
        medals_label.setStyleSheet(f"font-size: 14px; color: {TEXT['secondary']}; margin-top: 10px;")
        layout.addWidget(medals_label)
        
        medal_scroll = QScrollArea()
        medal_scroll.setWidgetResizable(True)
        
        medal_container = QWidget()
        medal_container.setStyleSheet("background-color: transparent;")
        self.medal_grid = QGridLayout(medal_container)
        self.medal_grid.setSpacing(10)
        
        medal_scroll.setWidget(medal_container)
        layout.addWidget(medal_scroll)
        
        return tab
    
    def load(self, calculator):
        """
        Load families data.
        
        Args:
            calculator: GamificationCalculator instance
        """
        data = calculator.get_family_achievements()
        
        self.family_summary.setText(f"{data['total_families']} Families Recorded")
        
        # Clear ribbons
        while self.ribbon_layout.count():
            item = self.ribbon_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Add ribbons (first 20)
        for ribbon in data["ribbons"][:20]:
            widget = QSvgWidget()
            widget.setFixedSize(45, 75)
            svg = self.renderer.render_ribbon(ribbon["family"], ribbon["group"], "small")
            widget.renderer().load(QByteArray(svg.encode()))
            count = ribbon.get("species_count", 1)
            widget.setToolTip(f"{ribbon['family']} - {count} species recorded")
            self.ribbon_layout.addWidget(widget)
        
        # Clear medals
        while self.medal_grid.count():
            item = self.medal_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Add medals (first 20)
        for i, medal in enumerate(data["medals"][:20]):
            widget = QSvgWidget()
            widget.setFixedSize(60, 75)
            svg = self.renderer.render_medal(medal["trophy_tier"], "medium")
            widget.renderer().load(QByteArray(svg.encode()))
            count = medal.get("species_count", 0)
            widget.setToolTip(f"{medal['family']} ({medal['trophy_tier'].title()}) - {count} species recorded")
            
            row = i // 5
            col = i % 5
            self.medal_grid.addWidget(widget, row, col)
