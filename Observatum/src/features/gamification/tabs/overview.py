"""
Overview Tab for Gamification Window.

Displays current tier, progress, and summary statistics.
"""

from typing import Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QProgressBar, QGridLayout
)
from PySide6.QtCore import Qt, QByteArray
from PySide6.QtSvgWidgets import QSvgWidget

from ..theme import BACKGROUND, TEXT, SEAL_COLOURS
from ..theme_bridge import get_color


class OverviewTab:
    """
    Overview tab showing tier progress and achievement summaries.
    
    Usage:
        tab = OverviewTab(renderer)
        widget = tab.create()
        tab.load(calculator)
    """
    
    def __init__(self, renderer):
        """
        Initialize the overview tab.
        
        Args:
            renderer: AchievementRenderer instance for SVG rendering
        """
        self.renderer = renderer
        
        # Widget references (set during create)
        self.tier_badge = None
        self.tier_name_label = None
        self.tier_subtitle = None
        self.tier_progress = None
        self.tier_count_label = None
        self.species_stat = None
        self.obs_stat = None
        self.records_earned_label = None
        self.best_daily_card = None
        self.best_annual_card = None
        self.rare_summary_card = None
        self.group_record_boxes = {}
        self.achievements_stat = None
        self.vc_stat = None
        self.family_stat = None
        self.medal_stat = None
    
    def create(self) -> QWidget:
        """Create and return the overview tab widget."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Tier card
        tier_card = QFrame()
        tier_card.setObjectName("tierCard")
        tier_layout = QHBoxLayout(tier_card)
        tier_layout.setSpacing(24)
        
        # Shield badge
        self.tier_badge = QSvgWidget()
        self.tier_badge.setFixedSize(100, 125)
        tier_layout.addWidget(self.tier_badge)
        
        # Tier info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(8)
        
        self.tier_name_label = QLabel("Loading...")
        self.tier_name_label.setObjectName("tierName")
        info_layout.addWidget(self.tier_name_label)
        
        self.tier_subtitle = QLabel("Tier 1 of 20")
        self.tier_subtitle.setStyleSheet(f"font-size: 12px; color: {TEXT['secondary']};")
        info_layout.addWidget(self.tier_subtitle)
        
        self.tier_progress = QProgressBar()
        self.tier_progress.setFixedHeight(14)
        info_layout.addWidget(self.tier_progress)
        
        self.tier_count_label = QLabel("0 / 500 species")
        self.tier_count_label.setStyleSheet(f"font-size: 11px; color: {TEXT['secondary']};")
        info_layout.addWidget(self.tier_count_label)
        
        tier_layout.addLayout(info_layout, 1)
        
        # Stats column
        stats_layout = QVBoxLayout()
        stats_layout.setSpacing(12)
        
        self.species_stat = self._create_stat_widget("Species", "0")
        self.obs_stat = self._create_stat_widget("Observations", "0")
        
        stats_layout.addWidget(self.species_stat)
        stats_layout.addWidget(self.obs_stat)
        
        tier_layout.addLayout(stats_layout)
        layout.addWidget(tier_card)
        
        # Records summary section
        records_section = QFrame()
        records_section.setObjectName("card")
        records_layout = QVBoxLayout(records_section)
        records_layout.setSpacing(10)
        
        records_header = QHBoxLayout()
        records_title = QLabel("Personal Records")
        records_title.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {TEXT['accent']};")
        records_header.addWidget(records_title)
        records_header.addStretch()
        
        self.records_earned_label = QLabel("0 / 95 earned")
        self.records_earned_label.setStyleSheet(f"font-size: 11px; color: {TEXT['secondary']};")
        records_header.addWidget(self.records_earned_label)
        records_layout.addLayout(records_header)
        
        # Best records row
        best_records_row = QHBoxLayout()
        best_records_row.setSpacing(20)
        
        self.best_daily_card = self._create_best_record_card("Best Day", "—", "No records yet")
        best_records_row.addWidget(self.best_daily_card)
        
        self.best_annual_card = self._create_best_record_card("Best Year", "—", "No records yet")
        best_records_row.addWidget(self.best_annual_card)
        
        self.rare_summary_card = self._create_best_record_card("Rare Species", "0", "None observed")
        best_records_row.addWidget(self.rare_summary_card)
        
        records_layout.addLayout(best_records_row)
        layout.addWidget(records_section)
        
        # Records by Group section
        groups_section = QFrame()
        groups_section.setObjectName("card")
        groups_layout = QVBoxLayout(groups_section)
        groups_layout.setSpacing(12)
        groups_layout.setContentsMargins(12, 10, 12, 14)
        
        groups_title = QLabel("Records by Group")
        groups_title.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {TEXT['accent']};")
        groups_layout.addWidget(groups_title)
        
        # 11 boxes in 2 rows (6 + 5 centered)
        self.group_record_boxes = {}
        
        row1_configs = [
            ("general", "General", SEAL_COLOURS["general"], 
             "Daily & annual species count records across all taxa"),
            ("birds", "Birds", SEAL_COLOURS["birds"],
             "Daily & annual records for bird species (Aves)"),
            ("butterflies", "Butterflies", SEAL_COLOURS["butterflies"],
             "Daily & annual records for butterfly species (Lepidoptera: Rhopalocera)"),
            ("moths", "Moths", SEAL_COLOURS["moths"],
             "Daily & annual records for moth species (Lepidoptera: Heterocera)"),
            ("dragonflies", "Dragonflies", SEAL_COLOURS["dragonflies"],
             "Daily & annual records for dragonflies & damselflies (Odonata)"),
            ("plants", "Plants", SEAL_COLOURS["plants"],
             "Daily & annual records for vascular plants (Tracheophyta)"),
        ]
        
        row2_configs = [
            ("hoverflies", "Hoverflies", SEAL_COLOURS["hoverflies"],
             "Daily & annual records for hoverflies (Syrphidae)"),
            ("beetles", "Beetles", SEAL_COLOURS["beetles"],
             "Daily & annual records for beetles (Coleoptera)"),
            ("aculeates", "Aculeates", SEAL_COLOURS["aculeates"],
             "Daily & annual records for bees, wasps & ants (Aculeata)"),
            ("spiders", "Spiders", SEAL_COLOURS["spiders"],
             "Daily & annual records for spiders (Araneae)"),
            ("fungi", "Fungi", SEAL_COLOURS["fungi"],
             "Daily & annual records for fungi & lichens"),
        ]
        
        # Row 1
        row1_layout = QHBoxLayout()
        row1_layout.setSpacing(10)
        row1_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        for key, name, colour, tooltip in row1_configs:
            box = self._create_group_record_box(key, name, colour, tooltip)
            self.group_record_boxes[key] = box
            row1_layout.addWidget(box)
        
        groups_layout.addLayout(row1_layout)
        
        # Row 2 (centered)
        row2_layout = QHBoxLayout()
        row2_layout.setSpacing(10)
        row2_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        for key, name, colour, tooltip in row2_configs:
            box = self._create_group_record_box(key, name, colour, tooltip)
            self.group_record_boxes[key] = box
            row2_layout.addWidget(box)
        
        groups_layout.addLayout(row2_layout)
        layout.addWidget(groups_section)
        
        # Quick stats row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(15)
        
        self.achievements_stat = self._create_stat_card("Achievements", "0 / 0")
        self.vc_stat = self._create_stat_card("Vice Counties", "0 / 112")
        self.family_stat = self._create_stat_card("Families", "0")
        self.medal_stat = self._create_stat_card("Medals", "0")
        
        stats_row.addWidget(self.achievements_stat)
        stats_row.addWidget(self.vc_stat)
        stats_row.addWidget(self.family_stat)
        stats_row.addWidget(self.medal_stat)
        
        layout.addLayout(stats_row)
        layout.addStretch()
        
        return tab
    
    def load(self, calculator, get_stage_colours) -> Dict[str, Any]:
        """
        Load data into the overview tab.
        
        Args:
            calculator: GamificationCalculator instance
            get_stage_colours: Function to get stage colours
        
        Returns:
            tier_data dict for use by other tabs
        """
        tier_data = calculator.calculate_current_tier()
        coverage = calculator.get_vice_county_coverage()
        family_data = calculator.get_family_achievements()
        
        # Update tier badge
        svg = self.renderer.render_shield(
            tier_data["tier_number"],
            tier_data["stage"],
            "large"
        )
        self.tier_badge.renderer().load(QByteArray(svg.encode()))
        
        # Update tier info
        colours = get_stage_colours(tier_data["stage"])
        self.tier_name_label.setText(tier_data["tier_name"])
        self.tier_name_label.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {colours['highlight']};")
        
        self.tier_subtitle.setText(f"Tier {tier_data['tier_number']} of 20")
        
        # Progress bar with stage colour
        self.tier_progress.setValue(int(tier_data["progress_percent"]))
        self.tier_progress.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                border-radius: 6px;
                background-color: {BACKGROUND['border']};
                height: 14px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {colours['shadow']},
                    stop:1 {colours['highlight']}
                );
                border-radius: 6px;
            }}
        """)
        
        self.tier_count_label.setText(
            f"{tier_data['unique_species']:,} / {tier_data['next_threshold']:,} species"
        )
        
        # Stats
        self.species_stat.value_label.setText(f"{tier_data['unique_species']:,}")
        self.obs_stat.value_label.setText(f"{tier_data['total_observations']:,}")
        
        # Quick stats
        total_achievements = calculator.get_total_achievements_summary()
        self.achievements_stat.value_label.setText(
            f"{total_achievements['total_earned']} / {total_achievements['total_possible']}"
        )
        
        self.vc_stat.value_label.setText(f"{coverage['covered_vice_counties']} / {coverage['total_vice_counties']}")
        self.family_stat.value_label.setText(str(family_data["total_families"]))
        self.medal_stat.value_label.setText(str(len(family_data["medals"])))
        
        # Records summary
        records_summary = calculator.get_one_time_achievements_summary()
        self.records_earned_label.setText(f"{records_summary['earned']} / {records_summary['total']} earned")
        
        # Update Records by Group boxes
        self._load_group_boxes(calculator)
        
        # Update best records cards
        self._load_best_records(calculator)
        
        # Update rare species card
        self._load_rare_summary(calculator)
        
        return tier_data
    
    def _load_group_boxes(self, calculator):
        """Load data into group record boxes."""
        try:
            all_records = calculator.calculate_one_time_achievements()
            
            group_counts = {}
            for record in all_records:
                group = record["group"]
                if group not in group_counts:
                    group_counts[group] = {"earned": 0, "total": 0}
                group_counts[group]["total"] += 1
                if record["earned"]:
                    group_counts[group]["earned"] += 1
            
            for group_key, box in self.group_record_boxes.items():
                counts = group_counts.get(group_key, {"earned": 0, "total": 0})
                earned = counts["earned"]
                total = counts["total"]
                
                box.count_label.setText(f"{earned} / {total}")
                
                if hasattr(box, 'progress_bar') and total > 0:
                    percent = int((earned / total) * 100)
                    box.progress_bar.setValue(percent)
                
                colour = box.theme_colour
                if hasattr(box, 'accent_bar'):
                    if earned == 0:
                        box.accent_bar.setStyleSheet(f"background-color: {BACKGROUND['border']}; border-radius: 2px;")
                    else:
                        box.accent_bar.setStyleSheet(f"background-color: {colour}; border-radius: 2px;")
                
                if earned == total and total > 0:
                    box.setStyleSheet(f"""
                        QFrame {{
                            background-color: {BACKGROUND['secondary']};
                            border: 1px solid {colour};
                            border-radius: 6px;
                        }}
                    """)
                elif earned > 0:
                    box.setStyleSheet(f"""
                        QFrame {{
                            background-color: {BACKGROUND['surface']};
                            border: 1px solid {BACKGROUND['border']};
                            border-radius: 6px;
                        }}
                    """)
                else:
                    box.setStyleSheet(f"""
                        QFrame {{
                            background-color: {BACKGROUND['surface']};
                            border: 1px solid {BACKGROUND['border']};
                            border-radius: 6px;
                        }}
                    """)
                    box.count_label.setStyleSheet(f"font-size: 12px; color: {TEXT['muted']};")
                    
        except Exception as e:
            print(f"[Gamification] Error updating group boxes: {e}")
    
    def _load_best_records(self, calculator):
        """Load best daily/annual records."""
        try:
            all_records = calculator.calculate_one_time_achievements()
            
            daily_records = [r for r in all_records if r["period"] == "daily" and r["group"] == "general"]
            if daily_records and any(r["best_count"] > 0 for r in daily_records):
                best_daily = max((r for r in daily_records if r["best_count"] > 0), 
                               key=lambda x: x["best_count"], default=None)
                if best_daily:
                    self.best_daily_card.value_label.setText(f"{best_daily['best_count']}")
                    if best_daily.get("best_date"):
                        self.best_daily_card.subtitle_label.setText(f"species on {best_daily['best_date']}")
                    else:
                        self.best_daily_card.subtitle_label.setText("species in one day")
            
            annual_records = [r for r in all_records if r["period"] == "annual" and r["group"] == "general"]
            if annual_records and any(r["best_count"] > 0 for r in annual_records):
                best_annual = max((r for r in annual_records if r["best_count"] > 0),
                                key=lambda x: x["best_count"], default=None)
                if best_annual:
                    self.best_annual_card.value_label.setText(f"{best_annual['best_count']}")
                    if best_annual.get("best_date"):
                        self.best_annual_card.subtitle_label.setText(f"species in {best_annual['best_date']}")
                    else:
                        self.best_annual_card.subtitle_label.setText("species in one year")
        except Exception as e:
            print(f"[Gamification] Error loading best records: {e}")
    
    def _load_rare_summary(self, calculator):
        """Load rare species summary."""
        try:
            rare_summary = calculator.get_rare_species_summary()
            self.rare_summary_card.value_label.setText(f"{rare_summary['total']}")
            if rare_summary['total'] > 0:
                tier_parts = []
                for tier_key, count in rare_summary['by_tier'].items():
                    if count > 0:
                        tier_parts.append(f"{count} {tier_key.replace('_', ' ')}")
                if tier_parts:
                    self.rare_summary_card.subtitle_label.setText(", ".join(tier_parts[:2]))
                else:
                    self.rare_summary_card.subtitle_label.setText("observed")
            else:
                self.rare_summary_card.subtitle_label.setText("None observed yet")
        except Exception as e:
            print(f"[Gamification] Error loading rare summary: {e}")
    
    # =========================================================================
    # HELPER WIDGET CREATION
    # =========================================================================
    
    def _create_stat_widget(self, label: str, value: str) -> QWidget:
        """Create a simple stat display."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        value_lbl = QLabel(value)
        value_lbl.setObjectName("statValue")
        value_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        label_lbl = QLabel(label)
        label_lbl.setObjectName("statLabel")
        label_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(value_lbl)
        layout.addWidget(label_lbl)
        
        widget.value_label = value_lbl
        return widget
    
    def _create_stat_card(self, title: str, value: str) -> QFrame:
        """Create a stat card."""
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        value_lbl = QLabel(value)
        value_lbl.setStyleSheet(f"font-size: 24px; color: {TEXT['accent']};")
        value_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"font-size: 11px; color: {TEXT['secondary']};")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(value_lbl)
        layout.addWidget(title_lbl)
        
        card.value_label = value_lbl
        return card
    
    def _create_best_record_card(self, title: str, value: str, subtitle: str) -> QFrame:
        """Create a card showing best record info."""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {BACKGROUND['surface']};
                border: 1px solid {BACKGROUND['border']};
                border-radius: 6px;
                padding: 8px;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)
        
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"font-size: 10px; color: {TEXT['muted']};")
        layout.addWidget(title_lbl)
        
        value_lbl = QLabel(value)
        value_lbl.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {TEXT['accent']};")
        layout.addWidget(value_lbl)
        
        subtitle_lbl = QLabel(subtitle)
        subtitle_lbl.setStyleSheet(f"font-size: 10px; color: {TEXT['secondary']};")
        layout.addWidget(subtitle_lbl)
        
        card.value_label = value_lbl
        card.subtitle_label = subtitle_lbl
        return card
    
    def _create_group_record_box(self, key: str, name: str, colour: str, tooltip: str = "") -> QFrame:
        """Create a themed box for a record group with accent styling."""
        box = QFrame()
        box.setFixedSize(105, 58)
        
        if tooltip:
            box.setToolTip(tooltip)
        
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 6)
        layout.setSpacing(3)
        
        # Top accent bar
        accent_bar = QFrame()
        accent_bar.setFixedHeight(4)
        accent_bar.setStyleSheet(f"background-color: {colour}; border-radius: 2px;")
        layout.addWidget(accent_bar)
        
        # Content area
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(6, 2, 6, 0)
        content_layout.setSpacing(1)
        
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(f"font-size: 10px; font-weight: bold; color: {colour};")
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(name_lbl)
        
        count_lbl = QLabel("0 / 0")
        count_lbl.setStyleSheet(f"font-size: 12px; color: {TEXT['primary']};")
        count_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(count_lbl)
        
        # Mini progress bar
        from PySide6.QtWidgets import QProgressBar
        progress_bar = QProgressBar()
        progress_bar.setFixedHeight(3)
        progress_bar.setTextVisible(False)
        progress_bar.setValue(0)
        progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                border-radius: 1px;
                background-color: {BACKGROUND['border']};
            }}
            QProgressBar::chunk {{
                background-color: {colour};
                border-radius: 1px;
            }}
        """)
        content_layout.addWidget(progress_bar)
        
        layout.addWidget(content)
        
        box.setStyleSheet(f"""
            QFrame {{
                background-color: {BACKGROUND['surface']};
                border: 1px solid {BACKGROUND['border']};
                border-radius: 6px;
            }}
        """)
        
        box.count_label = count_lbl
        box.progress_bar = progress_bar
        box.accent_bar = accent_bar
        box.theme_colour = colour
        return box
