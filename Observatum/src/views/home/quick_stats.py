"""
Quick Stats Panel Component.

Displays quick statistics from all data sources with tab-themed colors.
- Observation Data (sage green)
- Recording Scheme (dusty purple)
- Insect Collection (warm gold)
"""

from typing import Dict, Any

from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QFrame, QWidget
from PySide6.QtCore import QTimer, Qt

from .card import Card
from ...themes import theme
from ...core.config import TabColors


class QuickStatsPanel(Card):
    """Panel showing quick statistics from all data sources."""
    
    def __init__(self, parent=None):
        super().__init__("Quick Stats", parent)
        self._db = None
        self._stat_rows = []  # Track all stat rows for theme updates
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the panel UI with sections for each data source."""
        t = theme()
        
        # Main stats layout
        self.stats_layout = QVBoxLayout()
        self.stats_layout.setSpacing(4)
        
        # === Observation Data Section ===
        self._add_section_header("Observation Data", TabColors.OBSERVATION)
        self.obs_total_species = self._create_stat_row(
            "Total Species", "0", TabColors.OBSERVATION
        )
        self.obs_total_records = self._create_stat_row(
            "Total Records", "0", TabColors.OBSERVATION
        )
        self.obs_this_year_species = self._create_stat_row(
            "This Year Species", "0", TabColors.OBSERVATION
        )
        self.obs_this_year_records = self._create_stat_row(
            "This Year Records", "0", TabColors.OBSERVATION
        )
        self.obs_last_month = self._create_stat_row(
            "Last Month Records", "0", TabColors.OBSERVATION
        )
        
        # Separator
        self._add_separator()
        
        # === Recording Scheme Section ===
        self._add_section_header("Recording Scheme", TabColors.RECORDING_SCHEME)
        self.scheme_total_species = self._create_stat_row(
            "Total Species", "0", TabColors.RECORDING_SCHEME
        )
        self.scheme_total_records = self._create_stat_row(
            "Total Records", "0", TabColors.RECORDING_SCHEME
        )
        
        # Separator
        self._add_separator()
        
        # === Insect Collection Section ===
        self._add_section_header("Insect Collection", TabColors.COLLECTION)
        
        # Total Species + top 3 by species count
        self.coll_total_species = self._create_stat_row(
            "Total Species", "0", TabColors.COLLECTION
        )
        self.coll_species_order_1 = self._create_stat_row(
            "", "0", TabColors.COLLECTION, indent=True
        )
        self.coll_species_order_2 = self._create_stat_row(
            "", "0", TabColors.COLLECTION, indent=True
        )
        self.coll_species_order_3 = self._create_stat_row(
            "", "0", TabColors.COLLECTION, indent=True
        )
        
        # Total Specimens + top 3 by specimen count
        self.coll_total_specimens = self._create_stat_row(
            "Total Specimens", "0", TabColors.COLLECTION
        )
        self.coll_specimen_order_1 = self._create_stat_row(
            "", "0", TabColors.COLLECTION, indent=True
        )
        self.coll_specimen_order_2 = self._create_stat_row(
            "", "0", TabColors.COLLECTION, indent=True
        )
        self.coll_specimen_order_3 = self._create_stat_row(
            "", "0", TabColors.COLLECTION, indent=True
        )
        
        # Hide all order rows initially
        for row in [self.coll_species_order_1, self.coll_species_order_2, self.coll_species_order_3,
                    self.coll_specimen_order_1, self.coll_specimen_order_2, self.coll_specimen_order_3]:
            row['container'].hide()
        
        self.add_layout(self.stats_layout)
        self.add_stretch()
    
    def _add_section_header(self, title: str, color: str):
        """Add a section header with colored accent."""
        t = theme()
        
        header = QLabel(title)
        header.setStyleSheet(f"""
            font-weight: 600;
            font-size: {t.font_size('sm')};
            color: {color};
            border: none;
            background: transparent;
            padding-top: 4px;
        """)
        self.stats_layout.addWidget(header)
    
    def _add_separator(self):
        """Add a subtle separator line."""
        t = theme()
        
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {t.get('separator')}; border: none;")
        self.stats_layout.addWidget(sep)
    
    def _create_stat_row(
        self, 
        label: str, 
        value: str, 
        color: str,
        indent: bool = False
    ) -> dict:
        """Create a stat row with label and colored value. All rows same size."""
        t = theme()
        
        # Create container widget for the row (allows show/hide)
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        row = QHBoxLayout(container)
        row.setSpacing(0)
        row.setContentsMargins(12 if indent else 0, 0, 0, 0)
        
        label_widget = QLabel(label)
        label_widget.setStyleSheet(f"""
            color: {t.get('text_secondary')};
            font-size: {t.font_size('base')};
            border: none;
            background: transparent;
        """)
        row.addWidget(label_widget)
        
        # Dotted separator
        dots_widget = QLabel("." * 80)
        dots_widget.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        dots_widget.setStyleSheet(f"""
            color: {t.get('border')};
            font-size: {t.font_size('sm')};
            background: transparent;
            border: none;
        """)
        row.addWidget(dots_widget, 1)
        
        value_widget = QLabel(value)
        value_widget.setStyleSheet(f"""
            font-weight: 600;
            font-size: {t.font_size('base')};
            color: {color};
            border: none;
            background: transparent;
        """)
        row.addWidget(value_widget)
        
        self.stats_layout.addWidget(container)
        
        row_data = {
            'container': container,
            'label': label_widget,
            'value': value_widget,
            'color': color,
            'indent': indent
        }
        self._stat_rows.append(row_data)
        
        return row_data
    
    def set_database(self, db):
        """Set database reference for querying stats."""
        self._db = db
    
    def update_stats(self, obs_stats: Dict[str, Any]):
        """Update observation statistics (called from home_tab for backwards compatibility)."""
        self.obs_total_species['value'].setText(f"{obs_stats.get('total_species', 0):,}")
        self.obs_total_records['value'].setText(f"{obs_stats.get('total_records', 0):,}")
        self.obs_this_year_species['value'].setText(f"{obs_stats.get('this_year_species', 0):,}")
        self.obs_this_year_records['value'].setText(f"{obs_stats.get('this_year_records', 0):,}")
        self.obs_last_month['value'].setText(f"{obs_stats.get('last_month_records', 0):,}")
    
    def update_scheme_stats(self, stats: Dict[str, Any]):
        """Update recording scheme statistics."""
        self.scheme_total_species['value'].setText(f"{stats.get('total_species', 0):,}")
        self.scheme_total_records['value'].setText(f"{stats.get('total_records', 0):,}")
    
    def update_collection_stats(self, stats: Dict[str, Any]):
        """Update insect collection statistics."""
        self.coll_total_species['value'].setText(f"{stats.get('total_species', 0):,}")
        self.coll_total_specimens['value'].setText(f"{stats.get('total_specimens', 0):,}")
        
        # Update top orders by species count - show/hide based on data
        top_species_orders = stats.get('top_orders_by_species', [])
        species_rows = [self.coll_species_order_1, self.coll_species_order_2, self.coll_species_order_3]
        
        for i, row in enumerate(species_rows):
            if i < len(top_species_orders):
                order_name, count = top_species_orders[i]
                row['label'].setText(order_name)
                row['value'].setText(f"{count:,}")
                row['container'].show()
            else:
                # Hide row if no data
                row['container'].hide()
        
        # Update top orders by specimen count - show/hide based on data
        top_specimen_orders = stats.get('top_orders_by_specimens', [])
        specimen_rows = [self.coll_specimen_order_1, self.coll_specimen_order_2, self.coll_specimen_order_3]
        
        for i, row in enumerate(specimen_rows):
            if i < len(top_specimen_orders):
                order_name, count = top_specimen_orders[i]
                row['label'].setText(order_name)
                row['value'].setText(f"{count:,}")
                row['container'].show()
            else:
                # Hide row if no data
                row['container'].hide()
    
    def refresh_all_stats(self):
        """Refresh all statistics from database."""
        if not self._db:
            return
        
        # Refresh Recording Scheme stats
        try:
            result = self._db.execute_main(
                "SELECT COUNT(DISTINCT species_name) as species, COUNT(*) as records FROM recording_scheme"
            )
            if result:
                self.update_scheme_stats({
                    'total_species': result[0]['species'] or result[0][0] or 0,
                    'total_records': result[0]['records'] or result[0][1] or 0
                })
        except Exception as e:
            print(f"[QuickStats] Error loading scheme stats: {e}")
        
        # Refresh Insect Collection stats
        try:
            # Total species and specimens
            result = self._db.execute_main(
                "SELECT COUNT(DISTINCT species_name) as species, COUNT(*) as specimens FROM specimens"
            )
            total_species = 0
            total_specimens = 0
            if result:
                total_species = result[0]['species'] or result[0][0] or 0
                total_specimens = result[0]['specimens'] or result[0][1] or 0
            
            # Top 3 orders by species count
            result = self._db.execute_main("""
                SELECT order_name, COUNT(DISTINCT species_name) as count 
                FROM specimens 
                WHERE order_name IS NOT NULL AND order_name != ''
                GROUP BY order_name 
                ORDER BY count DESC 
                LIMIT 3
            """)
            top_orders_by_species = []
            if result:
                for row in result:
                    order_name = row['order_name'] or row[0]
                    count = row['count'] or row[1]
                    if order_name:
                        top_orders_by_species.append((order_name, count))
            
            # Top 3 orders by specimen count
            result = self._db.execute_main("""
                SELECT order_name, COUNT(*) as count 
                FROM specimens 
                WHERE order_name IS NOT NULL AND order_name != ''
                GROUP BY order_name 
                ORDER BY count DESC 
                LIMIT 3
            """)
            top_orders_by_specimens = []
            if result:
                for row in result:
                    order_name = row['order_name'] or row[0]
                    count = row['count'] or row[1]
                    if order_name:
                        top_orders_by_specimens.append((order_name, count))
            
            self.update_collection_stats({
                'total_species': total_species,
                'total_specimens': total_specimens,
                'top_orders_by_species': top_orders_by_species,
                'top_orders_by_specimens': top_orders_by_specimens
            })
        except Exception as e:
            print(f"[QuickStats] Error loading collection stats: {e}")
    
    def flash_success(self):
        """Flash the panel green to indicate successful save."""
        t = theme()
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('success_bg')};
                border: 1px solid {t.get('success')};
                border-radius: {t.get('radius_lg')};
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        QTimer.singleShot(500, self._reset_style)
    
    def _reset_style(self):
        """Reset to normal card style."""
        t = theme()
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_lg')};
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)
    
    def apply_theme(self):
        """Apply the current theme."""
        t = theme()
        
        # Update all stat row styles - uniform size for all rows
        for row_data in self._stat_rows:
            color = row_data['color']
            
            row_data['label'].setStyleSheet(f"""
                color: {t.get('text_secondary')};
                font-size: {t.font_size('base')};
                border: none;
                background: transparent;
            """)
            
            row_data['value'].setStyleSheet(f"""
                font-weight: 600;
                font-size: {t.font_size('base')};
                color: {color};
                border: none;
                background: transparent;
            """)
        
        # Reset card style
        self._reset_style()
