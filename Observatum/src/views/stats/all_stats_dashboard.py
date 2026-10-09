"""
All Stats Dashboard Component.

Dashboard showing all observation statistics (personal + commercial).
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
from ...themes import theme
from ...services.observation_stats_service import get_observation_stats, get_observation_exclusion_clause




class AllStatsDashboard(QScrollArea):
    """Dashboard showing all observation statistics (personal + commercial)."""

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

        self.total_species_card = StatCard("Total Species", "0", "all data", t.get('success'))
        cards_layout.addWidget(self.total_species_card)

        self.total_records_card = StatCard("Total Records", "0", "all data", t.get('success'))
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
            total_species = stats.get('total_species', 0)
            total_records = stats.get('total_records', 0)
            hectads = stats.get('hectads_count', 0)
            tetrads = stats.get('tetrads_count', 0)
            vice_counties = stats.get('unique_vice_counties', 0)

            self.total_species_card.set_value(f"{total_species:,}", "all data")
            self.total_records_card.set_value(f"{total_records:,}", "all data")
            self.hectads_card.set_value(f"{hectads:,}", "10km squares")
            self.tetrads_card.set_value(f"{tetrads:,}", "2km squares")
            self.vc_card.set_value(f"{vice_counties:,}", "of 112")

            # Monthly charts
            monthly_counts = stats.get('monthly_counts', [])
            if monthly_counts and len(monthly_counts) == 12:
                self.monthly_chart.set_data(monthly_counts)

            monthly_species = stats.get('monthly_species_counts', [])
            if monthly_species and len(monthly_species) == 12:
                self.monthly_species_chart.set_data(monthly_species)

            # Order table (all)
            species_by_order = stats.get('species_by_order', [])
            if species_by_order:
                self.order_table.set_data(species_by_order, 'label')

            # Family table
            species_by_family = stats.get('species_by_family', [])
            if species_by_family:
                self.family_table.set_data(species_by_family, 'family')

            # Accumulation curve
            accumulation = stats.get('accumulation_curve', [])
            if accumulation:
                self.accumulation_chart.set_data(accumulation)

            # Order accumulation curves
            self._populate_order_curves()

            # Year by year
            yearly_stats = stats.get('yearly_stats', {})
            if yearly_stats:
                self.year_table.set_data(yearly_stats)

            # Recent species
            recent_species = stats.get('recent_new_species', [])
            if recent_species:
                self.recent_species.set_data(recent_species)

            self._dashboard_refreshed = True

        except Exception as e:
            print(f"[AllStatsDashboard] Error refreshing: {e}")
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

    def _show_species_for_group(self, field: str, value: str, dialog_title: str):
        """Show species list dialog for a taxonomic group (order or family)."""
        from ..dialogs.species_list_dialog import SpeciesListDialog
        try:
            from ...models.database import get_database
            db = get_database()
            exclusion = get_observation_exclusion_clause()
            if db is None:
                return
            query = f"""
                SELECT species_name,
                       MIN(date) as first_date,
                       MAX(date) as last_date
                FROM observations
                WHERE {field} = ?
                AND species_name IS NOT NULL AND species_name != ''
                {exclusion}
                GROUP BY species_name
                ORDER BY species_name
            """
            results = db.execute_main(query, (value,))
            species_list = []
            for r in results:
                sp_name = r['species_name'] or r[0]
                first = r['first_date'] or ''
                last = r['last_date'] or ''
                if sp_name:
                    species_list.append({
                        'species_name': sp_name,
                        'first_date': str(first)[:10] if first else '',
                        'last_date': str(last)[:10] if last else ''
                    })
            if not species_list:
                return
            title = f"{dialog_title} ({len(species_list)} species)"
            dlg = SpeciesListDialog(title, species_list, parent=self)
            dlg.exec()
        except Exception as e:
            print(f"Error showing species for {field}={value}: {e}")

    def _show_species_for_month(self, month: int):
        """Show a dialog listing unique species for a given month (all years)."""
        from ..dialogs.species_list_dialog import SpeciesListDialog
        MONTH_NAMES = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                       'July', 'August', 'September', 'October', 'November', 'December']
        month_name = MONTH_NAMES[month] if 1 <= month <= 12 else str(month)

        try:
            from ...models.database import get_database
            db = get_database()
            exclusion = get_observation_exclusion_clause()
            if db is None:
                return
            query = f"""
                SELECT species_name,
                       MIN(date) as first_date,
                       MAX(date) as last_date
                FROM observations
                WHERE date IS NOT NULL
                AND species_name IS NOT NULL AND species_name != ''
                AND CAST(strftime('%m', date) AS INTEGER) = ?
                {exclusion}
                GROUP BY species_name
                ORDER BY species_name
            """
            results = db.execute_main(query, (month,))
            species_list = []
            for r in results:
                name = r['species_name'] or r[0]
                first = r['first_date'] or ''
                last = r['last_date'] or ''
                if name:
                    species_list.append({
                        'species_name': name,
                        'first_date': str(first)[:10] if first else '',
                        'last_date': str(last)[:10] if last else ''
                    })

            if not species_list:
                return

            title = f"Species Recorded in {month_name} ({len(species_list)} species, all years)"
            dlg = SpeciesListDialog(title, species_list, parent=self)
            dlg.exec()
        except Exception as e:
            print(f"Error showing species for month: {e}")

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
            exclusion = get_observation_exclusion_clause()
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
                    accent_color='#6e8898',
                    accent_light='#e8eef2',
                    accent_dark='#4a6070'
                )
                dlg.navigate_to_observations.connect(self.navigate_to_species.emit)
                dlg.profile_requested.connect(self._on_profile_requested)
                self._current_detail_dialog = dlg
                dlg.exec()
                self._current_detail_dialog = None
        except Exception as e:
            print(f"Error showing species detail for {species_name}: {e}")

    def _show_species_for_year(self, year: int):
        """Show species list dialog for a given year."""
        from ..dialogs.species_list_dialog import SpeciesListDialog
        try:
            from ...models.database import get_database
            db = get_database()
            exclusion = get_observation_exclusion_clause()
            if db is None:
                return
            result = db.execute_main(f"""
                SELECT species_name, MIN(date) as first_date, MAX(date) as last_date
                FROM observations
                WHERE strftime('%Y', date) = ?
                AND species_name IS NOT NULL AND species_name != ''
                {exclusion}
                GROUP BY species_name ORDER BY species_name
            """, (str(year),))
            species_list = []
            for r in (result or []):
                sp_name = r['species_name'] or r[0]
                first = r['first_date'] or ''
                last = r['last_date'] or ''
                if sp_name:
                    species_list.append({
                        'species_name': sp_name,
                        'first_date': str(first)[:10] if first else '',
                        'last_date': str(last)[:10] if last else ''
                    })
            if not species_list:
                return
            title = f"Species Recorded in {year} ({len(species_list)} species)"
            dlg = SpeciesListDialog(title, species_list, parent=self)
            dlg.exec()
        except Exception as e:
            print(f"Error showing species for year {year}: {e}")

    def _show_new_species_for_year(self, year: int):
        """Show new species (first records) for a given year."""
        from ..dialogs.species_list_dialog import SpeciesListDialog
        try:
            from ...models.database import get_database
            db = get_database()
            exclusion = get_observation_exclusion_clause()
            if db is None:
                return
            result = db.execute_main(f"""
                SELECT species_name, MIN(date) as first_date
                FROM observations
                WHERE species_name IS NOT NULL AND species_name != '' AND date IS NOT NULL
                {exclusion}
                GROUP BY species_name
                HAVING strftime('%Y', MIN(date)) = ?
                ORDER BY first_date
            """, (str(year),))
            species_list = []
            for r in (result or []):
                sp_name = r['species_name'] or r[0]
                first = r['first_date'] or ''
                if sp_name:
                    species_list.append({
                        'species_name': sp_name,
                        'first_date': str(first)[:10] if first else '',
                        'last_date': str(first)[:10] if first else ''
                    })
            if not species_list:
                return
            title = f"New Species in {year} (+{len(species_list)})"
            dlg = SpeciesListDialog(title, species_list, parent=self)
            dlg.exec()
        except Exception as e:
            print(f"Error showing new species for year {year}: {e}")

    def _populate_order_curves(self, force=False):
        """Populate species accumulation curves grouped by taxon_group from stats cache."""
        if not force and getattr(self, "_order_curves_populated", False):
            return
        try:
            from ...services.observation_stats_service import get_observation_stats
            stats = get_observation_stats()
            raw = stats.get("order_curve_raw", {})

            if not raw:
                return

            LABEL_MAP = {
                'insect - beetle (Coleoptera)': 'Beetles (Coleoptera)',
                'insect - moth': 'Moths (Lepidoptera)',
                'insect - butterfly': 'Butterflies (Lepidoptera)',
                'flowering plant': 'Flowering Plants (Angiospermae)',
                'fern': 'Ferns (Polypodiopsida)',
                'conifer': 'Conifers (Pinopsida)',
                'horsetail': 'Horsetails (Equisetopsida)',
                'insect - true fly (Diptera)': 'True Flies (Diptera)',
                'bird': 'Birds (Aves)',
                'insect - hymenopteran': 'Bees, Wasps & Ants (Hymenoptera)',
                'spider (Araneae)': 'Spiders (Araneae)',
                'fungus': 'Fungi',
                'slime mould': 'Slime Moulds (Mycetozoa)',
                'insect - true bug (Hemiptera)': 'True Bugs (Hemiptera)',
                'terrestrial mammal': 'Land Mammals (Mammalia)',
                'marine mammal': 'Marine Mammals (Mammalia)',
                'mollusc': 'Molluscs (Mollusca)',
                'insect - dragonfly (Odonata)': 'Dragonflies (Odonata)',
                'harvestman (Opiliones)': 'Harvestmen (Opiliones)',
                'crustacean': 'Crustaceans (Crustacea)',
                'annelid': 'Annelids (Annelida)',
                'insect - orthopteran': 'Grasshoppers & Crickets (Orthoptera)',
                'millipede': 'Millipedes (Diplopoda)',
                'amphibian': 'Amphibians (Amphibia)',
                'false scorpion (Pseudoscorpiones)': 'False Scorpions (Pseudoscorpiones)',
                'centipede': 'Centipedes (Chilopoda)',
                'reptile': 'Reptiles (Reptilia)',
                'bony fish (Actinopterygii)': 'Fish (Actinopterygii)',
                'insect - scorpion fly (Mecoptera)': 'Scorpion Flies (Mecoptera)',
                'moss': 'Mosses (Bryophyta)',
                'springtail (Collembola)': 'Springtails (Collembola)',
                'acarine (Acari)': 'Mites (Acari)',
                'chromist': 'Chromists (Chromista)',
                'coelenterate (=cnidarian)': 'Cnidarians (Cnidaria)',
                'insect - caddis fly (Trichoptera)': 'Caddisflies (Trichoptera)',
                'insect - earwig (Dermaptera)': 'Earwigs (Dermaptera)',
                'insect - snakefly (Raphidioptera)': 'Snakeflies (Raphidioptera)',
                'insect - thrips (Thysanoptera)': 'Thrips (Thysanoptera)',
                'insect - flea (Siphonaptera)': 'Fleas (Siphonaptera)',
                'insect - lacewing (Neuroptera)': 'Lacewings (Neuroptera)',
                'alga': 'Algae',
                'lichen': 'Lichens',
                'flatworm (Turbellaria)': 'Flatworms (Turbellaria)',
                'scorpion': 'Scorpions (Scorpiones)',
            }

            MERGE_GROUPS = {
                'Plants (Plantae)': ['flowering plant', 'fern', 'conifer', 'horsetail'],
                'Fungi': ['fungus', 'slime mould'],
                'Mammals (Mammalia)': ['terrestrial mammal', 'marine mammal'],
            }

            merged_into = {}
            for merge_label, members in MERGE_GROUPS.items():
                for m in members:
                    merged_into[m] = merge_label

            # Group raw data by display label
            label_data = {}  # label -> {'species_count': N, 'yearly_new': {year: count}}
            label_groups = {}  # label -> [taxon_group values]
            for tg, info in raw.items():
                if tg in merged_into:
                    label = merged_into[tg]
                else:
                    label = LABEL_MAP.get(tg, tg.title())
                if label not in label_data:
                    label_data[label] = {'species_count': 0, 'yearly_new': {}}
                    label_groups[label] = []
                label_groups[label].append(tg)
                label_data[label]['species_count'] += info['species_count']
                for yr, cnt in info['yearly_new'].items():
                    label_data[label]['yearly_new'][yr] = label_data[label]['yearly_new'].get(yr, 0) + cnt

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

    def _show_species_for_order_curve(self, group_label: str):
        """Show species list dialog when a group chart is clicked."""
        group_values = getattr(self, '_group_label_map', {}).get(group_label)
        if group_values:
            self._show_species_for_taxon_groups(group_values, group_label)
        else:
            self._show_species_for_group('order_name', group_label, f"Species in {group_label}")

    def _show_species_for_taxon_groups(self, group_values: list, label: str):
        """Show species list dialog with family breakdown for taxon_group values."""
        from ..dialogs.species_list_dialog import SpeciesListDialog
        try:
            from ...models.database import get_database
            db = get_database()
            exclusion = get_observation_exclusion_clause()
            if db is None:
                return
            placeholders = ','.join(['?' for _ in group_values])

            # Get species with family info
            query = f"""
                SELECT species_name, family,
                       MIN(date) as first_date,
                       MAX(date) as last_date
                FROM observations
                WHERE taxon_group IN ({placeholders})
                AND species_name IS NOT NULL AND species_name != ''
                {exclusion}
                GROUP BY species_name
                ORDER BY species_name
            """
            results = db.execute_main(query, tuple(group_values))
            species_list = []
            for r in results:
                sp_name = r['species_name'] or r[0]
                first = r['first_date'] or ''
                last = r['last_date'] or ''
                family = r['family'] or 'Unknown'
                if sp_name:
                    species_list.append({
                        'species_name': sp_name,
                        'family': family,
                        'first_date': str(first)[:10] if first else '',
                        'last_date': str(last)[:10] if last else ''
                    })
            if not species_list:
                return
            title = f"Species in {label} ({len(species_list)} species)"
            dlg = SpeciesListDialog(title, species_list, parent=self, show_families=True)
            dlg.exec()
        except Exception as e:
            print(f"Error showing species for {label}: {e}")

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
