"""
Stats/Reports Tab View for Observatum V2.

Provides statistics dashboards and report generation for:
- Personal recording statistics
- Commercial statistics
- All combined statistics
- Commercial reports (placeholder)
- Recording scheme analysis
- Insect collection statistics
- Species lookup across all databases

This is a thin orchestrator that imports and manages the separate dashboard components.
"""


from PySide6.QtWidgets import QWidget, QVBoxLayout, QStackedWidget
from PySide6.QtCore import Signal

from ...models.database import get_database
from ...models.observation import ObservationModel

# Import dashboard components from separate modules
from .section_toggle import SectionToggle
from .personal_dashboard import PersonalStatsDashboard
from .commercial_dashboard import CommercialStatsDashboard
from .all_stats_dashboard import AllStatsDashboard
from .commercial_reports_dashboard import CommercialReportsDashboard
from .scheme_dashboard import SchemeDashboard
from .collection_dashboard import CollectionStatsDashboard
from .species_dashboard import SpeciesDashboard


class StatsReportsTab(QWidget):
    """Stats/Reports tab combining all dashboards."""

    navigate_to_observations = Signal(str)  # Request to switch to Observation Data tab (with optional species filter)
    navigate_to_order = Signal(str)  # Request to switch to Observation Data tab filtered by order
    navigate_to_month = Signal(int)
    navigate_to_family = Signal(str)  # Request to switch to Observation Data tab filtered by family
    navigate_to_year = Signal(int)  # Request to switch to Observation Data tab filtered by year
    navigate_to_collection = Signal(str)
    show_specimen_detail = Signal(int)  # specimen id    # Request to switch to Insect Collection tab (with optional species filter)
    filter_collection_by_order = Signal(str)   # Filter Insect Collection by order
    filter_collection_by_family = Signal(str)  # Filter Insect Collection by family
    filter_collection_by_year = Signal(str)    # Filter Insect Collection by year
    filter_collection_by_condition = Signal(str)   # Filter by condition
    filter_collection_by_prep_type = Signal(str)   # Filter by preparation type
    filter_collection_by_storage = Signal(str)     # Filter by storage location
    navigate_to_scheme = Signal(str)  # Request to switch to Recording Scheme tab with species filter
    navigate_to_scheme_vc = Signal(str, int)  # Request to switch with species and VC filter
    navigate_to_scheme_record = Signal(int)  # Request to switch to Recording Scheme tab and show specific record

    def __init__(self, parent=None):
        super().__init__(parent)
        self._observation_model = None
        self._db = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Section toggle
        self.section_toggle = SectionToggle()
        self.section_toggle.section_changed.connect(self._on_section_changed)
        layout.addWidget(self.section_toggle)

        # Stacked widget for sections
        self.stack = QStackedWidget()

        # Personal Stats (index 0)
        self.personal_dashboard = PersonalStatsDashboard()
        self.personal_dashboard.view_all_species_requested.connect(self._on_view_all_new_species)
        self.personal_dashboard.navigate_to_order.connect(self.navigate_to_order.emit)
        self.personal_dashboard.navigate_to_month.connect(self.navigate_to_month.emit)
        self.personal_dashboard.navigate_to_family.connect(self.navigate_to_family.emit)
        self.personal_dashboard.navigate_to_year.connect(self.navigate_to_year.emit)
        self.personal_dashboard.navigate_to_species.connect(self.navigate_to_observations.emit)
        self.stack.addWidget(self.personal_dashboard)

        # Commercial Stats (index 1)
        self.commercial_stats_dashboard = CommercialStatsDashboard()
        self.commercial_stats_dashboard.view_all_species_requested.connect(self._on_view_all_new_species)
        self.commercial_stats_dashboard.navigate_to_order.connect(self.navigate_to_order.emit)
        self.commercial_stats_dashboard.navigate_to_month.connect(self.navigate_to_month.emit)
        self.commercial_stats_dashboard.navigate_to_family.connect(self.navigate_to_family.emit)
        self.commercial_stats_dashboard.navigate_to_year.connect(self.navigate_to_year.emit)
        self.commercial_stats_dashboard.navigate_to_species.connect(self.navigate_to_observations.emit)
        self.stack.addWidget(self.commercial_stats_dashboard)

        # All Stats (index 2)
        self.all_stats_dashboard = AllStatsDashboard()
        self.all_stats_dashboard.view_all_species_requested.connect(self._on_view_all_new_species)
        self.all_stats_dashboard.navigate_to_order.connect(self.navigate_to_order.emit)
        self.all_stats_dashboard.navigate_to_month.connect(self.navigate_to_month.emit)
        self.all_stats_dashboard.navigate_to_family.connect(self.navigate_to_family.emit)
        self.all_stats_dashboard.navigate_to_year.connect(self.navigate_to_year.emit)
        self.all_stats_dashboard.navigate_to_species.connect(self.navigate_to_observations.emit)
        self.stack.addWidget(self.all_stats_dashboard)

        # Commercial Reports (index 3) - NEW placeholder
        self.commercial_reports_dashboard = CommercialReportsDashboard()
        self.stack.addWidget(self.commercial_reports_dashboard)

        # Recording Scheme (index 4)
        self.scheme_dashboard = SchemeDashboard()
        self.scheme_dashboard.species_selected.connect(self._on_scheme_species_selected)
        self.scheme_dashboard.species_vc_selected.connect(self._on_scheme_species_vc_selected)
        self.scheme_dashboard.record_selected.connect(self._on_scheme_record_selected)
        self.stack.addWidget(self.scheme_dashboard)

        # Insect Collection (index 5)
        self.collection_dashboard = CollectionStatsDashboard()
        self.collection_dashboard.view_all_specimens_requested.connect(self._on_view_all_specimens)
        self.collection_dashboard.filter_by_order_requested.connect(self.filter_collection_by_order.emit)
        self.collection_dashboard.filter_by_family_requested.connect(self.filter_collection_by_family.emit)
        self.collection_dashboard.filter_by_year_requested.connect(self.filter_collection_by_year.emit)
        self.collection_dashboard.filter_by_condition_requested.connect(self.filter_collection_by_condition.emit)
        self.collection_dashboard.filter_by_prep_type_requested.connect(self.filter_collection_by_prep_type.emit)
        self.collection_dashboard.filter_by_storage_requested.connect(self.filter_collection_by_storage.emit)
        self.collection_dashboard.specimen_detail_requested.connect(self.show_specimen_detail.emit)
        self.stack.addWidget(self.collection_dashboard)

        # Species Lookup (index 6)
        self.species_dashboard = SpeciesDashboard()
        self.species_dashboard.navigate_to_observations.connect(self.navigate_to_observations.emit)
        self.species_dashboard.navigate_to_collection.connect(self.navigate_to_collection.emit)
        self.stack.addWidget(self.species_dashboard)

        layout.addWidget(self.stack, 1)

    def initialize(self, main_db_path: str = None, uksi_db_path: str = None):
        """Initialize all dashboards with database connections."""
        try:
            self._db = get_database()

            if main_db_path:
                self._db.set_main_path(main_db_path)
            if uksi_db_path:
                self._db.set_uksi_path(uksi_db_path)

            # Create observation model
            self._observation_model = ObservationModel(self._db)

            # Initialize Species Dashboard with UKSI
            self.species_dashboard.initialize(main_db_path, uksi_db_path)

            # Initialize Collection Dashboard with database
            self.collection_dashboard.initialize(self._db)

            # Refresh current dashboard
            self._refresh_current_dashboard()

        except Exception as e:
            print(f"[StatsReportsTab] Error initializing dashboards: {e}")
            import traceback
            traceback.print_exc()

    def _on_section_changed(self, section_id: str):
        """Handle section change."""
        index_map = {
            'personal': 0,
            'commercial_stats': 1,
            'all_stats': 2,
            'commercial_reports': 3,
            'scheme': 4,
            'collection': 5,
            'species': 6
        }
        self.stack.setCurrentIndex(index_map.get(section_id, 0))
        self._refresh_current_dashboard()

    def _refresh_current_dashboard(self):
        """Refresh the currently visible dashboard."""
        current_index = self.stack.currentIndex()

        # Dashboards now use stats services - no model dependency needed
        if current_index == 0:
            self.personal_dashboard.refresh()
        elif current_index == 1:
            self.commercial_stats_dashboard.refresh()
        elif current_index == 2:
            self.all_stats_dashboard.refresh()
        elif current_index == 3:
            self.commercial_reports_dashboard.refresh()
        elif current_index == 4:
            self.scheme_dashboard.refresh()
        elif current_index == 5:
            self.collection_dashboard.refresh()
        elif current_index == 6 and self._observation_model:
            # Species dashboard still uses observation_model
            self.species_dashboard.refresh(self._observation_model)


    def _on_view_all_specimens(self):
        """Handle request to view new collection species - navigate to IC tab with new collections list."""
        self.navigate_to_collection.emit("__new_collections_list__")

    def _on_view_all_new_species(self):
        """Handle request to view all new species - navigate to Observation Data tab with new species filter."""
        self.navigate_to_observations.emit("")  # Empty string triggers new species list

    def refresh(self):
        """Refresh all dashboards."""
        self._refresh_current_dashboard()

    def mark_stale(self):
        """Records changed elsewhere: the next visit to each dashboard re-reads.

        Personal / Commercial / All load once and then skip refresh() (the
        _dashboard_refreshed guard), so after a delete, edit, commit or drawer save
        they kept the old figures until restart (review OBS-10). The caller
        invalidates the stats services; this clears the guards and refreshes the
        dashboard on screen.
        """
        for d in (self.personal_dashboard, self.commercial_stats_dashboard,
                  self.all_stats_dashboard):
            d._dashboard_refreshed = False
        if self.isVisible():
            self._refresh_current_dashboard()

    def _on_scheme_species_selected(self, species_name: str):
        """Forward species selection from scheme dashboard to main window."""
        self.navigate_to_scheme.emit(species_name)

    def _on_scheme_species_vc_selected(self, species_name: str, vc_number: int):
        """Forward species+VC selection from scheme dashboard to main window."""
        self.navigate_to_scheme_vc.emit(species_name, vc_number)

    def _on_scheme_record_selected(self, record_id: int):
        """Forward record selection from scheme dashboard to main window."""
        self.navigate_to_scheme_record.emit(record_id)

    def apply_theme(self):
        """Apply the current theme to all components."""
        self.section_toggle.apply_theme()
        self.personal_dashboard.apply_theme()
        self.commercial_stats_dashboard.apply_theme()
        self.all_stats_dashboard.apply_theme()
        self.commercial_reports_dashboard.apply_theme()
        self.scheme_dashboard.apply_theme()
        self.collection_dashboard.apply_theme()
        self.species_dashboard.apply_theme()
