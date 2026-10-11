"""
Personal Stats Dashboard Component.

Dashboard showing personal recording statistics.
Uses ObservationStatsService for centralized data.
"""

from PySide6.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QHBoxLayout
)
from PySide6.QtCore import Signal

try:
    from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis, QAreaSeries  # noqa: F401  (availability check / re-export)
    CHARTS_AVAILABLE = True
except ImportError:
    CHARTS_AVAILABLE = False

from .stat_widgets import (
    StatCard, MonthlyActivityChart,
    YearByYearTable, RecentSpeciesList,
    AccumulationCurveChart, DataTable
)
from .order_accumulation_grid import OrderAccumulationGrid
from .species_list_dialogs import SpeciesListsMixin
from ...themes import theme
from ...services.observation_stats_service import get_observation_stats
from shared.species_counting import counted_clause




class PersonalStatsDashboard(SpeciesListsMixin, QScrollArea):
    """Dashboard showing personal recording statistics."""

    LIST_RECORD_TYPE = 'Personal'          # species-list dialogs (species_list_dialogs.py)

    view_all_species_requested = Signal()
    navigate_to_order = Signal(str)  # Emits order name for filtering observations
    navigate_to_month = Signal(int)  # Emits month number (1-12) for date filtering
    navigate_to_family = Signal(str)  # Emits family name for filtering observations
    navigate_to_year = Signal(int)  # Emits year for date filtering
    navigate_to_species = Signal(str)  # Emits species name for filtering observations

    def __init__(self, parent=None):
        super().__init__(parent)
        t = theme()

        self.setWidgetResizable(True)
        self.setStyleSheet(f"QScrollArea {{ border: none; background-color: {t.get('background')}; }}")

        container = QWidget()
        self.setWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(24)

        # Row 1: Stat Cards
        self._setup_stats_cards(layout)

        # Row 2: Species by Order chart + Monthly records
        self._setup_charts_row(layout)

        # Row 3: Order table + Family table
        self._setup_tables_row(layout)

        # Row 4: Year by year + Recent new species
        self._setup_bottom_row(layout)

        # Row 5: Order accumulation curves
        self.order_curves = OrderAccumulationGrid()
        self.order_curves.order_clicked.connect(self._show_species_for_order_curve)
        layout.addWidget(self.order_curves)

        layout.addStretch()

    def _setup_stats_cards(self, layout):
        """Set up quick stats cards row."""
        t = theme()

        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(16)

        self.total_species_card = StatCard("Total Species", "0", "all-time", t.get('success'))
        cards_layout.addWidget(self.total_species_card)

        self.total_records_card = StatCard("Total Records", "0", "all-time", t.get('success'))
        cards_layout.addWidget(self.total_records_card)

        self.hectads_card = StatCard("Hectads", "0", "10km squares", t.get('success'))
        cards_layout.addWidget(self.hectads_card)

        self.tetrads_card = StatCard("Tetrads", "0", "2km squares", t.get('success'))
        cards_layout.addWidget(self.tetrads_card)

        self.vc_card = StatCard("Vice Counties", "0", "of 112", t.get('success'))
        cards_layout.addWidget(self.vc_card)

        layout.addLayout(cards_layout)

    def _setup_charts_row(self, layout):
        """Accumulation curve, monthly records, and species by month."""
        row = QHBoxLayout()
        row.setSpacing(24)

        t = theme()
        self.accumulation_chart = AccumulationCurveChart(
            "Species Accumulation Curve",
            accent_color=t.get('success')
        )
        row.addWidget(self.accumulation_chart, 1)

        self.monthly_chart = MonthlyActivityChart("Monthly Records")
        row.addWidget(self.monthly_chart, 1)

        self.monthly_species_chart = MonthlyActivityChart("Species by Month", value_label="species")
        row.addWidget(self.monthly_species_chart, 1)

        layout.addLayout(row)

    def _setup_tables_row(self, layout):
        """Order and Family tables."""
        row = QHBoxLayout()
        row.setSpacing(24)

        self.order_table = DataTable("Records & Species by Order", ["Order", "Species", "Records"])
        row.addWidget(self.order_table)

        self.family_table = DataTable("Records & Species by Family", ["Family", "Species", "Records"])
        row.addWidget(self.family_table)

        layout.addLayout(row)

    def _setup_bottom_row(self, layout):
        """Year by year and recent species - at bottom."""
        row = QHBoxLayout()
        row.setSpacing(24)

        self.year_table = YearByYearTable()
        self.year_table.year_clicked.connect(self.navigate_to_year.emit)
        self.year_table.year_species_clicked.connect(self._show_species_for_year)
        self.year_table.year_new_species_clicked.connect(self._show_new_species_for_year)
        from .year_export import wire_year_exports          # buttons were unconnected (OBS-19)
        wire_year_exports(self.year_table, 'Personal', "Personal", self)
        row.addWidget(self.year_table)

        self.recent_species = RecentSpeciesList()
        self.recent_species.view_more_clicked.connect(self.view_all_species_requested.emit)
        self.recent_species.species_clicked.connect(self._show_recent_species_detail)
        self.monthly_chart.month_clicked.connect(self.navigate_to_month.emit)
        self.monthly_species_chart.month_clicked.connect(self._show_species_for_month)
        self.order_table.cell_clicked.connect(self._on_order_table_clicked)
        self.family_table.cell_clicked.connect(self._on_family_table_clicked)
        row.addWidget(self.recent_species)

        layout.addLayout(row)

    def refresh(self, observation_model=None, force=False):
        """Refresh the dashboard with data from the stats service."""
        if not force and getattr(self, "_dashboard_refreshed", False):
            return
        try:
            stats = get_observation_stats()
            
            # Stat cards
            total_species = stats.get('personal_species', 0)
            total_records = stats.get('personal_records', 0)
            hectads = stats.get('personal_hectads_count', 0)
            tetrads = stats.get('personal_tetrads_count', 0)
            vice_counties = stats.get('personal_unique_vice_counties', 0)

            self.total_species_card.set_value(f"{total_species:,}", "all-time")
            self.total_records_card.set_value(f"{total_records:,}", "all-time")
            self.hectads_card.set_value(f"{hectads:,}", "10km squares")
            self.tetrads_card.set_value(f"{tetrads:,}", "2km squares")
            self.vc_card.set_value(f"{vice_counties:,}", "of 112")

            # Monthly charts
            monthly_counts = stats.get('personal_monthly_counts', [])
            if monthly_counts and len(monthly_counts) == 12:
                self.monthly_chart.set_data(monthly_counts)

            monthly_species = stats.get('personal_monthly_species_counts', [])
            if monthly_species and len(monthly_species) == 12:
                self.monthly_species_chart.set_data(monthly_species)

            # Order table (all)
            species_by_order = stats.get('personal_species_by_order', [])
            if species_by_order:
                self.order_table.set_data(species_by_order, 'label')

            # Family table
            species_by_family = stats.get('personal_species_by_family', [])
            if species_by_family:
                self.family_table.set_data(species_by_family, 'family')

            # Accumulation curve
            accumulation = stats.get('personal_accumulation_curve', [])
            if accumulation:
                self.accumulation_chart.set_data(accumulation)

            # Order accumulation curves
            self._populate_order_curves()

            # Year by year
            yearly_stats = stats.get('personal_yearly_stats', {})
            if yearly_stats:
                self.year_table.set_data(yearly_stats)

            # Recent species
            recent_species = stats.get('personal_recent_new_species', [])
            if recent_species:
                self.recent_species.set_data(recent_species)

            self._dashboard_refreshed = True

        except Exception as e:
            print(f"[PersonalStatsDashboard] Error refreshing: {e}")
            import traceback
            traceback.print_exc()

    def _on_order_table_clicked(self, row: int, col: int, name: str):
        """Handle click on order table. Col 0/2=navigate to order, col 1=show species dialog."""
        if col == 1:
            self._show_species_for_group('order_name', name, f"Species in {name}")
        else:
            self.navigate_to_order.emit(name)

    def _on_family_table_clicked(self, row: int, col: int, name: str):
        """Handle click on family table. Col 0/2=navigate to family, col 1=show species dialog."""
        if col == 1:
            self._show_species_for_group('family', name, f"Species in {name}")
        else:
            self.navigate_to_family.emit(name)

    def _on_profile_requested(self, record: dict):
        """Handle profile view/create request from detail dialog."""
        from ..home.species_profile_dialog import SpeciesProfileDialog
        species_data = {
            'scientific_name': record.get('species_name') or record.get('species'),
            'species_name': record.get('species_name') or record.get('species'),
            'tvk': record.get('species_tvk') or record.get('tvk'),
            'common_name': record.get('common_name') or record.get('common'),
        }
        profile_dialog = SpeciesProfileDialog(species_data, self)
        detail_dialog = getattr(self, '_current_detail_dialog', None)
        if detail_dialog and hasattr(detail_dialog, 'update_profile'):
            profile_dialog.profile_saved.connect(lambda text: detail_dialog.update_profile(text))
        profile_dialog.exec()

    def _show_recent_species_detail(self, species_name: str):
        """Show observation record detail for a species from Recent New Species."""
        try:
            from ...models.database import get_database
            from ..dialogs import RecordDetailDialog
            db = get_database()
            exclusion = counted_clause("observations")
            if db is None:
                return
            # Get the most recent observation for this species
            result = db.execute_main(f"""
                SELECT * FROM observations
                WHERE species_name = ?
                {exclusion}
                ORDER BY date DESC LIMIT 1
            """, (species_name,))
            if result:
                record = dict(result[0])
                # Get species count
                count_result = db.execute_main(
                    "SELECT COUNT(*) as cnt FROM observations WHERE species_name = ?",
                    (species_name,))
                species_count = count_result[0]['cnt'] if count_result else 0
                dlg = RecordDetailDialog(
                    record=record,
                    species_count=species_count,
                    record_type='observation',
                    parent=self,
                    accent_color='#7a9e7e',
                    accent_light='#e8f0ea',
                    accent_dark='#3d5e44'
                )
                dlg.navigate_to_observations.connect(self.navigate_to_species.emit)
                dlg.profile_requested.connect(self._on_profile_requested)
                # Edit / Delete go to the Observation tab's flows (they did nothing)
                from ..observations.observation_record_actions import wire_observation_detail
                wire_observation_detail(dlg, self)
                self._current_detail_dialog = dlg
                dlg.exec()
                self._current_detail_dialog = None
        except Exception as e:
            print(f"Error showing species detail for {species_name}: {e}")

    def _populate_order_curves(self, force=False):
        """Populate species accumulation curves grouped by taxon_group from stats cache."""
        if not force and getattr(self, "_order_curves_populated", False):
            return
        try:
            from ...services.observation_stats_service import get_observation_stats
            stats = get_observation_stats()
            raw = stats.get("personal_order_curve_raw", {})

            if not raw:
                return

            # Display labels and merges: shared/taxon_groups.py (one copy for the three
            # dashboards, 10 Oct 2026)
            from shared.taxon_groups import merge_curve_groups
            label_data, label_groups = merge_curve_groups(raw)

            self._group_label_map = label_groups

            order_data = []
            for label, info in label_data.items():
                if info['species_count'] == 0:
                    continue
                cumulative = 0
                accum_list = []
                for yr in sorted(info['yearly_new'].keys()):
                    cumulative += info['yearly_new'][yr]
                    accum_list.append({'year': yr, 'cumulative': cumulative})
                order_data.append({
                    'order': label,
                    'species_count': info['species_count'],
                    'accumulation': accum_list
                })

            order_data.sort(key=lambda x: x['species_count'], reverse=True)
            self.order_curves.set_data(order_data)
            self._order_curves_populated = True

        except Exception as e:
            print(f"Error populating group curves: {e}")
            import traceback
            traceback.print_exc()

    def apply_theme(self):
        """Apply the current theme to all components."""
        t = theme()
        self.setStyleSheet(f"QScrollArea {{ border: none; background-color: {t.get('background')}; }}")

        self.total_species_card.apply_theme()
        self.total_records_card.apply_theme()
        self.hectads_card.apply_theme()
        self.tetrads_card.apply_theme()
        self.vc_card.apply_theme()
        self.monthly_chart.apply_theme()
        self.monthly_species_chart.apply_theme()
        self.order_table.apply_theme()
        self.family_table.apply_theme()
        self.accumulation_chart.apply_theme()
        self.year_table.apply_theme()
        self.recent_species.apply_theme()
        self.order_curves.apply_theme()
