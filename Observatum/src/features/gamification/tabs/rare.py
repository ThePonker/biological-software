"""
Rare Species Tab for Gamification Window.

Displays rare species pins, milestones, and tier filtering.
"""

from typing import Dict, Any, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QGridLayout, QPushButton, QGraphicsOpacityEffect
)
from PySide6.QtCore import Qt, QByteArray
from PySide6.QtSvgWidgets import QSvgWidget

from ..theme import TEXT, RARITY_TIERS, PAPER


class RareTab:
    """
    Rare Species tab showing pins and milestones.
    
    Usage:
        tab = RareTab(renderer)
        widget = tab.create()
        tab.load(calculator)
    """
    
    def __init__(self, renderer):
        """Initialize the rare tab."""
        self.renderer = renderer
        
        # Widget references
        self.rare_summary_label = None
        self.rare_filter_buttons = {}
        self.rare_milestones_row = None
        self.rare_pins_layout = None
        
        # Data storage
        self._rare_pins_data: List[Dict] = []
        self._current_rare_filter = "all"
        self.calculator = None
    
    def create(self) -> QWidget:
        """Create and return the rare species tab widget."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)
        
        # Summary bar
        summary_bar = QHBoxLayout()
        summary_bar.setSpacing(20)
        
        self.rare_summary_label = QLabel("Loading rare species...")
        self.rare_summary_label.setStyleSheet(f"font-size: 13px; color: {TEXT['primary']};")
        summary_bar.addWidget(self.rare_summary_label)
        
        summary_bar.addStretch()
        
        # Tier filter buttons
        self.rare_filter_buttons = {}
        for tier_key, tier_name in [("all", "All"), ("protected", "Protected"), 
                                     ("critical", "Critical"), ("very_rare", "Very Rare"),
                                     ("rare", "Rare"), ("uncommon", "Uncommon")]:
            btn = QPushButton(tier_name)
            btn.setCheckable(True)
            btn.setChecked(tier_key == "all")
            btn.setFixedHeight(26)
            btn.setStyleSheet(f"""
                QPushButton {{
                    font-size: 10px;
                    padding: 4px 10px;
                    border: 1px solid {RARITY_TIERS.get(tier_key, {}).get('primary', TEXT['muted'])};
                    border-radius: 4px;
                    background: transparent;
                    color: {TEXT['primary']};
                }}
                QPushButton:checked {{
                    background: {RARITY_TIERS.get(tier_key, {}).get('primary', TEXT['accent'])};
                    color: white;
                }}
                QPushButton:hover {{
                    background: {RARITY_TIERS.get(tier_key, {}).get('vignette_light', PAPER['cream'])};
                }}
            """)
            btn.clicked.connect(lambda checked, t=tier_key: self._filter_rare_species(t))
            self.rare_filter_buttons[tier_key] = btn
            summary_bar.addWidget(btn)
        
        layout.addLayout(summary_bar)
        
        # Milestones section
        milestones_label = QLabel("Milestones")
        milestones_label.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {TEXT['accent']};")
        layout.addWidget(milestones_label)
        
        self.rare_milestones_row = QHBoxLayout()
        self.rare_milestones_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.rare_milestones_row.setSpacing(15)
        layout.addLayout(self.rare_milestones_row)
        
        # Pins section header
        pins_label = QLabel("Rare Species Observed")
        pins_label.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {TEXT['accent']}; margin-top: 10px;")
        layout.addWidget(pins_label)
        
        # Scrollable grid of pins
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            QScrollArea > QWidget > QWidget {{
                background: transparent;
            }}
        """)
        
        rare_pins_container = QWidget()
        self.rare_pins_layout = QGridLayout(rare_pins_container)
        self.rare_pins_layout.setSpacing(8)
        self.rare_pins_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        scroll.setWidget(rare_pins_container)
        layout.addWidget(scroll, 1)  # Takes remaining space
        
        return tab
    
    def load(self, calculator):
        """
        Load rare species data.
        
        Args:
            calculator: GamificationCalculator instance
        """
        self.calculator = calculator
        
        summary = calculator.get_rare_species_summary()
        pins = calculator.get_rare_species_pins()
        milestones = calculator.calculate_rare_milestones()
        
        # Store for filtering
        self._rare_pins_data = pins
        
        # Update summary
        tier_counts = summary["by_tier"]
        summary_parts = [f"{summary['total']} Rare Species:"]
        tier_labels = [
            ("protected", "Protected"),
            ("critical", "Critical"),
            ("very_rare", "Very Rare"),
            ("rare", "Rare"),
            ("uncommon", "Uncommon"),
        ]
        for key, label in tier_labels:
            if tier_counts.get(key, 0) > 0:
                summary_parts.append(f"{tier_counts[key]} {label}")
        
        self.rare_summary_label.setText(" • ".join(summary_parts))
        
        # Clear and populate milestones
        while self.rare_milestones_row.count():
            item = self.rare_milestones_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        for milestone in milestones:
            card = self._create_milestone_card(milestone)
            self.rare_milestones_row.addWidget(card)
        
        # Load pins with current filter
        self._render_rare_pins()
    
    def _filter_rare_species(self, tier_filter: str):
        """Filter rare species pins by tier."""
        self._current_rare_filter = tier_filter
        
        # Update button states
        for key, btn in self.rare_filter_buttons.items():
            btn.setChecked(key == tier_filter)
        
        self._render_rare_pins()
    
    def _render_rare_pins(self):
        """Render rare species pins with current filter."""
        # Clear existing
        while self.rare_pins_layout.count():
            item = self.rare_pins_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Filter pins
        if self._current_rare_filter == "all":
            filtered_pins = self._rare_pins_data
        else:
            filtered_pins = [p for p in self._rare_pins_data 
                           if p["rarity_tier"] == self._current_rare_filter]
        
        if not filtered_pins:
            empty_label = QLabel("No rare species in this category yet.")
            empty_label.setStyleSheet(f"color: {TEXT['muted']}; padding: 20px;")
            self.rare_pins_layout.addWidget(empty_label, 0, 0)
            return
        
        # Calculate columns (aim for ~100px per card)
        cols = 8
        
        for i, pin_data in enumerate(filtered_pins):
            card = self._create_rare_pin_card(pin_data)
            row = i // cols
            col = i % cols
            self.rare_pins_layout.addWidget(card, row, col)
    
    def _create_milestone_card(self, milestone: Dict[str, Any]) -> QWidget:
        """Create a card for a rare species milestone."""
        card = QFrame()
        card.setObjectName("card")
        card.setFixedSize(100, 110)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Rosette - always show correct tier colour
        rosette = QSvgWidget()
        rosette.setFixedSize(50, 62)
        svg = self.renderer.render_rosette(milestone["trophy_tier"], "medium")
        rosette.renderer().load(QByteArray(svg.encode()))
        
        # Dim if not earned using opacity effect
        if not milestone["earned"]:
            opacity = QGraphicsOpacityEffect(rosette)
            opacity.setOpacity(0.3)
            rosette.setGraphicsEffect(opacity)
        layout.addWidget(rosette, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Name
        name = QLabel(milestone["name"])
        name.setStyleSheet(f"""
            font-size: 9px;
            font-weight: bold;
            color: {TEXT['primary'] if milestone['earned'] else TEXT['muted']};
        """)
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name)
        
        # Progress
        progress = QLabel(f"{milestone['current_count']}/{milestone['threshold']}")
        progress.setStyleSheet(f"font-size: 8px; color: {TEXT['muted']};")
        progress.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(progress)
        
        return card
    
    def _create_rare_pin_card(self, pin_data: Dict[str, Any]) -> QWidget:
        """Create a card for a rare species pin."""
        card = QFrame()
        card.setObjectName("card")
        card.setFixedSize(95, 100)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Pin
        pin = QSvgWidget()
        pin.setFixedSize(40, 50)
        svg = self.renderer.render_pin(pin_data["rarity_tier"], "small")
        pin.renderer().load(QByteArray(svg.encode()))
        layout.addWidget(pin, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Common name (truncated)
        display_name = pin_data["common_name"] or pin_data["scientific_name"]
        if len(display_name) > 14:
            display_name = display_name[:12] + "..."
        name = QLabel(display_name)
        name.setStyleSheet(f"font-size: 8px; font-weight: bold; color: {TEXT['primary']};")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name)
        
        # Status
        status = QLabel(pin_data.get("status_text", "")[:15])
        status.setStyleSheet(f"font-size: 7px; color: {TEXT['muted']};")
        status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(status)
        
        # Tooltip with full info
        tooltip = f"{pin_data['common_name']}\n{pin_data['scientific_name']}"
        if pin_data.get("family"):
            tooltip += f"\n{pin_data['family']}"
        if pin_data.get("status_text"):
            tooltip += f"\n{pin_data['status_text']}"
        card.setToolTip(tooltip)
        
        return card
