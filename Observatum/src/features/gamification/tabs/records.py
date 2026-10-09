"""
Records Tab for Gamification Window.

Displays one-time achievements (daily/annual records) by taxonomic group.
Uses vertical scrolling grid layout.
"""


from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QPushButton, QGridLayout
)
from PySide6.QtCore import Qt, QByteArray
from PySide6.QtSvgWidgets import QSvgWidget

from ..theme import BACKGROUND, TEXT

# Layout constants
CARD_WIDTH = 160
CARD_HEIGHT = 155
SEAL_SIZE = 64
GRID_COLUMNS = 8  # Number of columns in grid


class RecordsTab:
    """
    Records tab showing one-time achievements.
    
    Usage:
        tab = RecordsTab(renderer)
        widget = tab.create()
        tab.load(calculator)
    """
    
    def __init__(self, renderer):
        """Initialize the records tab."""
        self.renderer = renderer
        
        # Widget references
        self.records_summary = None
        self.record_filter_buttons = {}
        self.current_record_filter = "All"
        self.daily_grid = None
        self.annual_grid = None
        self.calculator = None  # Set during load
    
    def create(self) -> QWidget:
        """Create and return the records tab widget."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(10)
        
        # Top bar: Summary + Filters
        top_bar = QHBoxLayout()
        
        self.records_summary = QLabel("Loading...")
        self.records_summary.setObjectName("sectionTitle")
        top_bar.addWidget(self.records_summary)
        
        top_bar.addStretch()
        
        # Group filter buttons
        self.record_filter_buttons = {}
        groups = ["All", "General", "Birds", "Butterflies", "Moths", "Dragonflies", 
                  "Plants", "Hoverflies", "Beetles", "Aculeates", "Spiders", "Fungi"]
        
        for group_name in groups:
            btn = QPushButton(group_name)
            btn.setCheckable(True)
            btn.setFixedHeight(26)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {BACKGROUND['secondary']};
                    color: {TEXT['secondary']};
                    border: 1px solid {BACKGROUND['border']};
                    border-radius: 4px;
                    padding: 3px 10px;
                    font-size: 10px;
                }}
                QPushButton:checked {{
                    background-color: {TEXT['accent']};
                    color: {BACKGROUND['primary']};
                    border-color: {TEXT['accent']};
                }}
                QPushButton:hover:!checked {{
                    background-color: {BACKGROUND['surface']};
                }}
            """)
            btn.clicked.connect(lambda checked, g=group_name: self._filter_records(g))
            top_bar.addWidget(btn)
            self.record_filter_buttons[group_name] = btn
        
        # Set "All" as default
        self.record_filter_buttons["All"].setChecked(True)
        self.current_record_filter = "All"
        
        layout.addLayout(top_bar)
        
        # Vertical scroll area for all records
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background-color: transparent;")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(20)
        
        # Daily Records section
        daily_section = QWidget()
        daily_layout = QVBoxLayout(daily_section)
        daily_layout.setContentsMargins(0, 0, 0, 0)
        daily_layout.setSpacing(10)
        
        daily_label = QLabel("Daily Records")
        daily_label.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {TEXT['accent']};")
        daily_layout.addWidget(daily_label)
        
        daily_container = QWidget()
        daily_container.setStyleSheet("background-color: transparent;")
        self.daily_grid = QGridLayout(daily_container)
        self.daily_grid.setContentsMargins(0, 0, 0, 0)
        self.daily_grid.setSpacing(12)
        self.daily_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        daily_layout.addWidget(daily_container)
        scroll_layout.addWidget(daily_section)
        
        # Annual Records section
        annual_section = QWidget()
        annual_layout = QVBoxLayout(annual_section)
        annual_layout.setContentsMargins(0, 0, 0, 0)
        annual_layout.setSpacing(10)
        
        annual_label = QLabel("Annual Records")
        annual_label.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {TEXT['accent']};")
        annual_layout.addWidget(annual_label)
        
        annual_container = QWidget()
        annual_container.setStyleSheet("background-color: transparent;")
        self.annual_grid = QGridLayout(annual_container)
        self.annual_grid.setContentsMargins(0, 0, 0, 0)
        self.annual_grid.setSpacing(12)
        self.annual_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        annual_layout.addWidget(annual_container)
        scroll_layout.addWidget(annual_section)
        
        scroll_layout.addStretch()
        
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        return tab
    
    def load(self, calculator):
        """
        Load records data.
        
        Args:
            calculator: GamificationCalculator instance
        """
        self.calculator = calculator
        self._refresh_records()
    
    def _filter_records(self, group: str):
        """Filter records by taxonomic group."""
        for name, btn in self.record_filter_buttons.items():
            btn.setChecked(name == group)
        
        self.current_record_filter = group
        if self.calculator:
            self._refresh_records()
    
    def _refresh_records(self):
        """Refresh the records display."""
        if not self.calculator:
            return
        
        all_achievements = self.calculator.calculate_one_time_achievements()
        summary = self.calculator.get_one_time_achievements_summary()
        
        self.records_summary.setText(
            f"{summary['earned']} / {summary['total']} Records Achieved"
        )
        
        # Filter by current selection
        if self.current_record_filter == "All":
            filtered = all_achievements
        else:
            filter_group = self.current_record_filter.lower()
            filtered = [a for a in all_achievements if a["group"] == filter_group]
        
        # Split into daily and annual
        daily = [a for a in filtered if a["period"] == "daily"]
        annual = [a for a in filtered if a["period"] == "annual"]
        
        # Clear grids
        self._clear_grid(self.daily_grid)
        self._clear_grid(self.annual_grid)
        
        # Populate daily grid
        for i, achievement in enumerate(daily):
            card = self._create_record_card(achievement)
            row = i // GRID_COLUMNS
            col = i % GRID_COLUMNS
            self.daily_grid.addWidget(card, row, col)
        
        # Populate annual grid
        for i, achievement in enumerate(annual):
            card = self._create_record_card(achievement)
            row = i // GRID_COLUMNS
            col = i % GRID_COLUMNS
            self.annual_grid.addWidget(card, row, col)
    
    def _clear_grid(self, grid: QGridLayout):
        """Clear all widgets from a grid layout."""
        while grid.count():
            item = grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    
    def _create_record_card(self, achievement: dict) -> QFrame:
        """Create a card for a one-time achievement."""
        card = QFrame()
        card.setObjectName("card")
        card.setFixedSize(CARD_WIDTH, CARD_HEIGHT)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Seal (larger size)
        seal = QSvgWidget()
        seal.setFixedSize(SEAL_SIZE, SEAL_SIZE)
        svg = self.renderer.render_seal(
            colour=achievement["colour"],
            earned=achievement["earned"],
            period=achievement["period"],
            group=achievement["group"],
            size="medium"  # Use medium size for larger rendering
        )
        seal.renderer().load(QByteArray(svg.encode()))
        layout.addWidget(seal, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Name
        name = QLabel(achievement["name"])
        name.setWordWrap(True)
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setFixedHeight(36)
        if achievement["earned"]:
            name.setStyleSheet(f"font-size: 10px; font-weight: bold; color: {achievement['colour']};")
        else:
            name.setStyleSheet(f"font-size: 10px; color: {TEXT['muted']};")
        layout.addWidget(name)
        
        # Threshold vs Personal Best
        threshold = achievement["threshold"]
        best = achievement["best_value"]
        
        if achievement["earned"]:
            stats_text = f"✓ {best:,}/{threshold:,}"
            stats_colour = achievement["colour"]
        else:
            stats_text = f"{best:,}/{threshold:,}"
            stats_colour = TEXT["muted"]
        
        stats = QLabel(stats_text)
        stats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stats.setStyleSheet(f"font-size: 10px; color: {stats_colour};")
        layout.addWidget(stats)
        
        return card
