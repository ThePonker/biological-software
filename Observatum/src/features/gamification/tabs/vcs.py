"""
Vice Counties Tab for Gamification Window.

Displays interactive UK VC map with regional crown completion.
"""

from pathlib import Path
from typing import Dict, List, Set

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QGraphicsOpacityEffect, QSplitter
)
from PySide6.QtCore import Qt, QByteArray
from PySide6.QtSvgWidgets import QSvgWidget

from ..theme import TEXT, BACKGROUND


class VCsTab:
    """
    Vice Counties tab showing interactive map and regional crowns.
    
    Usage:
        tab = VCsTab(renderer)
        widget = tab.create()
        tab.load(calculator)
    """
    
    # Colours for map
    VC_UNEARNED = "#3d3d3d"
    VC_EARNED = "#4a7c59"
    VC_STROKE = "#555555"
    VC_EARNED_STROKE = "#6a9c79"
    
    def __init__(self, renderer):
        """Initialize the VCs tab."""
        self.renderer = renderer
        
        # Widget references
        self.vc_summary = None
        self.crown_widgets = {}
        self.map_widget = None
        self.map_svg_path = Path(__file__).parent.parent / "assets" / "maps" / "uk_vice_counties.svg"
    
    def create(self) -> QWidget:
        """Create and return the VCs tab widget."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Summary
        self.vc_summary = QLabel("Loading...")
        self.vc_summary.setObjectName("sectionTitle")
        layout.addWidget(self.vc_summary)
        
        # Main content: Map on left, Crowns + Legend on right
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)
        
        # Map section (takes most space)
        map_frame = QFrame()
        map_frame.setObjectName("card")
        map_layout = QVBoxLayout(map_frame)
        map_layout.setContentsMargins(10, 10, 10, 10)
        
        map_label = QLabel("Vice County Coverage")
        map_label.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {TEXT['accent']};")
        map_layout.addWidget(map_label)
        
        # SVG Map widget
        self.map_widget = QSvgWidget()
        self.map_widget.setMinimumSize(350, 500)
        map_layout.addWidget(self.map_widget, 1)
        
        content_layout.addWidget(map_frame, 2)
        
        # Right panel: Crowns + Legend
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(20)
        
        # Crowns section
        crown_frame = QFrame()
        crown_frame.setObjectName("card")
        crown_layout = QVBoxLayout(crown_frame)
        
        crown_label = QLabel("Regional Completion")
        crown_label.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {TEXT['accent']};")
        crown_layout.addWidget(crown_label)
        
        # Crown grid
        crown_grid = QHBoxLayout()
        crown_grid.setAlignment(Qt.AlignmentFlag.AlignCenter)
        crown_grid.setSpacing(15)
        
        self.crown_widgets = {}
        crown_configs = [
            ("england", "England"),
            ("wales", "Wales"),
            ("scotland", "Scotland"),
            ("uk", "UK Complete"),
        ]
        
        for region_key, region_name in crown_configs:
            crown_container = QWidget()
            crown_container_layout = QVBoxLayout(crown_container)
            crown_container_layout.setContentsMargins(0, 0, 0, 0)
            crown_container_layout.setSpacing(4)
            crown_container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            crown = QSvgWidget()
            crown.setFixedSize(50, 56)
            region_param = None if region_key == "uk" else region_key
            svg = self.renderer.render_crown(region_param, "medium")
            crown.renderer().load(QByteArray(svg.encode()))
            
            # Start dimmed
            opacity = QGraphicsOpacityEffect(crown)
            opacity.setOpacity(0.3)
            crown.setGraphicsEffect(opacity)
            
            self.crown_widgets[region_key] = crown
            crown_container_layout.addWidget(crown, alignment=Qt.AlignmentFlag.AlignCenter)
            
            name_label = QLabel(region_name)
            name_label.setStyleSheet(f"font-size: 9px; color: {TEXT['secondary']};")
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            crown_container_layout.addWidget(name_label)
            
            crown_grid.addWidget(crown_container)
        
        crown_layout.addLayout(crown_grid)
        right_layout.addWidget(crown_frame)
        
        # Legend
        legend_frame = QFrame()
        legend_frame.setObjectName("card")
        legend_layout = QVBoxLayout(legend_frame)
        
        legend_title = QLabel("Legend")
        legend_title.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {TEXT['accent']};")
        legend_layout.addWidget(legend_title)
        
        # Visited
        visited_row = QHBoxLayout()
        visited_box = QFrame()
        visited_box.setFixedSize(20, 14)
        visited_box.setStyleSheet(f"background-color: {self.VC_EARNED}; border-radius: 2px;")
        visited_row.addWidget(visited_box)
        visited_label = QLabel("Visited")
        visited_label.setStyleSheet(f"font-size: 11px; color: {TEXT['primary']};")
        visited_row.addWidget(visited_label)
        visited_row.addStretch()
        legend_layout.addLayout(visited_row)
        
        # Not visited
        unvisited_row = QHBoxLayout()
        unvisited_box = QFrame()
        unvisited_box.setFixedSize(20, 14)
        unvisited_box.setStyleSheet(f"background-color: {self.VC_UNEARNED}; border-radius: 2px;")
        unvisited_row.addWidget(unvisited_box)
        unvisited_label = QLabel("Not yet visited")
        unvisited_label.setStyleSheet(f"font-size: 11px; color: {TEXT['primary']};")
        unvisited_row.addWidget(unvisited_label)
        unvisited_row.addStretch()
        legend_layout.addLayout(unvisited_row)
        
        right_layout.addWidget(legend_frame)
        
        # Regional stats
        self.stats_frame = QFrame()
        self.stats_frame.setObjectName("card")
        self.stats_layout = QVBoxLayout(self.stats_frame)
        
        stats_title = QLabel("Regional Progress")
        stats_title.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {TEXT['accent']};")
        self.stats_layout.addWidget(stats_title)
        
        self.england_stat = QLabel("England: 0 / 0")
        self.england_stat.setStyleSheet(f"font-size: 11px; color: {TEXT['secondary']};")
        self.stats_layout.addWidget(self.england_stat)
        
        self.wales_stat = QLabel("Wales: 0 / 0")
        self.wales_stat.setStyleSheet(f"font-size: 11px; color: {TEXT['secondary']};")
        self.stats_layout.addWidget(self.wales_stat)
        
        self.scotland_stat = QLabel("Scotland: 0 / 0")
        self.scotland_stat.setStyleSheet(f"font-size: 11px; color: {TEXT['secondary']};")
        self.stats_layout.addWidget(self.scotland_stat)
        
        right_layout.addWidget(self.stats_frame)
        
        right_layout.addStretch()
        content_layout.addWidget(right_panel, 1)
        
        layout.addLayout(content_layout, 1)
        
        return tab
    
    def load(self, calculator):
        """
        Load VCs data.
        
        Args:
            calculator: GamificationCalculator instance
        """
        badges = calculator.calculate_vice_county_badges()
        earned_vcs = set(b["vc_number"] for b in badges if b["earned"])
        total_badges = len(badges)
        earned_count = len(earned_vcs)
        
        self.vc_summary.setText(f"{earned_count} / {total_badges} Vice Counties Visited")
        
        # Update map with earned VCs
        self._update_map(earned_vcs)
        
        # Update crown completion status
        coverage = calculator.get_vice_county_coverage()
        
        for region_key, crown_widget in self.crown_widgets.items():
            if region_key == "uk":
                all_complete = all(
                    data["covered"] >= data["total"] and data["total"] > 0
                    for data in coverage["regions"].values()
                )
                is_complete = all_complete
            else:
                region_data = coverage["regions"].get(region_key, {})
                is_complete = (
                    region_data.get("covered", 0) >= region_data.get("total", 1) 
                    and region_data.get("total", 0) > 0
                )
            
            effect = crown_widget.graphicsEffect()
            if effect:
                effect.setOpacity(1.0 if is_complete else 0.3)
        
        # Update regional stats
        regions = coverage.get("regions", {})
        england = regions.get("england", {"covered": 0, "total": 0})
        wales = regions.get("wales", {"covered": 0, "total": 0})
        scotland = regions.get("scotland", {"covered": 0, "total": 0})
        
        self.england_stat.setText(f"England: {england['covered']} / {england['total']}")
        self.wales_stat.setText(f"Wales: {wales['covered']} / {wales['total']}")
        self.scotland_stat.setText(f"Scotland: {scotland['covered']} / {scotland['total']}")
    
    def _update_map(self, earned_vcs: Set[int]):
        """Update the SVG map with earned VC highlighting."""
        try:
            # Read base SVG
            if not self.map_svg_path.exists():
                print(f"[Gamification] Map not found: {self.map_svg_path}")
                return
            
            svg_content = self.map_svg_path.read_text(encoding="utf-8")
            
            # For each earned VC, add the "earned" class
            for vc_num in earned_vcs:
                # Replace class="vc" with class="vc earned" for matching VC
                old_pattern = f'id="vc{vc_num}" class="vc"'
                new_pattern = f'id="vc{vc_num}" class="vc earned"'
                svg_content = svg_content.replace(old_pattern, new_pattern)
            
            # Load modified SVG into widget
            self.map_widget.renderer().load(QByteArray(svg_content.encode()))
            
        except Exception as e:
            print(f"[Gamification] Error updating map: {e}")
