"""
Tiers Tab for Gamification Window.

Displays all 20 progression tiers with locked/unlocked states.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QGridLayout
)
from PySide6.QtCore import QByteArray
from PySide6.QtSvgWidgets import QSvgWidget

from ..theme import TEXT, TIERS, get_stage_colours


class TiersTab:
    """
    Tiers tab showing all 20 progression tiers.
    
    Usage:
        tab = TiersTab(renderer)
        widget = tab.create()
        tab.load(current_tier)
    """
    
    def __init__(self, renderer):
        """Initialize the tiers tab."""
        self.renderer = renderer
        self.tiers_container = None
        self.tiers_grid = None
    
    def create(self) -> QWidget:
        """Create and return the tiers tab widget."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        self.tiers_container = QWidget()
        self.tiers_container.setStyleSheet("background-color: transparent;")
        self.tiers_grid = QGridLayout(self.tiers_container)
        self.tiers_grid.setSpacing(15)
        
        scroll.setWidget(self.tiers_container)
        layout.addWidget(scroll)
        
        return tab
    
    def load(self, current_tier: int):
        """
        Load tier cards with locked state for future tiers.
        
        Args:
            current_tier: The user's current tier number (1-20)
        """
        # Clear existing cards
        while self.tiers_grid.count():
            item = self.tiers_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        for i, tier_info in enumerate(TIERS):
            tier_num = tier_info["tier"]
            is_locked = tier_num > current_tier
            is_current = tier_num == current_tier
            
            card = self._create_tier_card(tier_info, is_locked, is_current)
            row = i // 2
            col = i % 2
            self.tiers_grid.addWidget(card, row, col)
    
    def _create_tier_card(self, tier_info: dict, is_locked: bool = False, is_current: bool = False) -> QFrame:
        """Create a single tier card."""
        card = QFrame()
        card.setObjectName("card")
        layout = QHBoxLayout(card)
        layout.setSpacing(15)
        
        # Shield
        badge = QSvgWidget()
        badge.setFixedSize(50, 63)
        
        if is_locked:
            svg = self.renderer.render_locked_shield("small")
        else:
            svg = self.renderer.render_shield(tier_info["tier"], tier_info["stage"], "small")
        
        badge.renderer().load(QByteArray(svg.encode()))
        layout.addWidget(badge)
        
        # Info
        info_layout = QVBoxLayout()
        
        if is_locked:
            name = QLabel("???")
            name.setStyleSheet(f"font-size: 14px; font-weight: bold; color: #666666;")
            info_layout.addWidget(name)
            
            range_lbl = QLabel("Locked")
            range_lbl.setStyleSheet(f"font-size: 11px; color: #555555;")
            info_layout.addWidget(range_lbl)
        else:
            colours = get_stage_colours(tier_info["stage"])
            name = QLabel(tier_info["name"])
            
            if is_current:
                name.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {TEXT['accent']};")
            else:
                name.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {colours['highlight']};")
            
            info_layout.addWidget(name)
            
            if tier_info["max_species"]:
                range_text = f"{tier_info['min_species']:,} - {tier_info['max_species']:,} species"
            else:
                range_text = f"{tier_info['min_species']:,}+ species"
            
            range_lbl = QLabel(range_text)
            range_lbl.setStyleSheet(f"font-size: 11px; color: {TEXT['secondary']};")
            info_layout.addWidget(range_lbl)
        
        layout.addLayout(info_layout, 1)
        
        return card
