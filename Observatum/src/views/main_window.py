"""
Main Application Window for Observatum V2.

Contains the tab container and orchestrates navigation between tabs.

UPDATED: Now uses TabColors from src.core.config
"""

from pathlib import Path

import time

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QTabWidget, QStatusBar, QLabel
)
from PySide6.QtCore import Qt

# Import from refactored packages
from .home import HomeTab
from .observations import ObservationTab
from .contributed import ContributedTab
from .scheme import RecordingSchemeTab
from .collection import InsectCollectionTab
from .stats import StatsReportsTab
from .mapping import MappingTab
from .settings import SettingsTab

from ..models.database import get_database
from ..models.uksi import UKSIModel
from ..services.observation_stats_service import get_observation_stats_service
from ..services.recording_scheme_stats_service import get_recording_scheme_stats
from ..services.specimen_stats_service import get_specimen_stats
from ..services.search_service import get_search_service
from ..themes import theme

# NEW: Import centralised config
from ..core.config import TabColors


class MainWindow(QMainWindow):
    """
    Main application window with tab-based navigation.

    Tabs:
    - Home: Quick entry form and recent activity
    - Observation Data: Personal and commercial records
    - Contributed: Records other people sent (read-only)
    - Recording Scheme: Cerambycidae recording scheme data
    - Insect Collection: Specimen database
    - Stats/Reports: Statistics and report generation
    - Mapping: Map visualization (future)
    - Settings: Application configuration
    """

    def __init__(self, main_db_path: str = None, uksi_db_path: str = None, splash=None):
        super().__init__()
        self.setWindowTitle("Observatum V2")
        self._main_db_path = main_db_path
        self._uksi_db_path = uksi_db_path
        self._splash = splash

        self._update_splash(35, "Building interface...")
        self._setup_ui()
        # Tab signal connected in showEvent to prevent eager loading

        self._update_splash(50, "Setting up status bar...")
        self._setup_statusbar()

        self._update_splash(55, "Initializing services...")
        self._initialize_services()

        self._update_splash(95, "Applying theme...")
        self.apply_theme()

        self._update_splash(100, "Ready!")
        # Reset lazy-load tracking - Qt may have fired tab events during init
        self._initialized_tabs = {0}
        self._ready = True  # Guard: only process tab changes after init complete

    def connect_tab_signal(self):
        """Connect tab change signal. Call after window is shown."""
        self._initialized_tabs = {0}
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _update_splash(self, progress: int, message: str):
        """Update splash screen if available."""
        if self._splash:
            self._splash.set_progress(progress, message)

    def _setup_ui(self):
        """Set up the main UI structure."""
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        layout.addWidget(self.tabs)

        # Add tabs
        self.home_tab = HomeTab()
        self.tabs.addTab(self.home_tab, "Home")

        # Data Entry tab -- PREVIEW by default (dev copy, commit disabled).
        # TO GO LIVE (commit into data\observatum.db):
        #   1) BACK UP data\observatum.db first,
        #   2) change go_live=False to go_live=True on the next line.
        try:
            from DataEntry.embed import make_data_entry_tab
            self.data_entry_tab = make_data_entry_tab(go_live=True)
            # Claude: defer Observation-Data refresh wiring until all tabs exist
            from PySide6.QtCore import QTimer as _QTimer
            _QTimer.singleShot(0, lambda: _claude_wire_obs_refresh(self))


            self.tabs.addTab(self.data_entry_tab, "Data Entry")
        except Exception as _de_err:
            print(f"[Observatum] Data Entry tab unavailable: {_de_err}")

        self.observation_tab = ObservationTab()
        self.tabs.addTab(self.observation_tab, "Observation Data")

        # Contributed records (other people's) -- read-only browse, backlog K1
        self.contributed_tab = ContributedTab()
        self.tabs.addTab(self.contributed_tab, "Contributed")

        self.recording_scheme_tab = RecordingSchemeTab()
        self.tabs.addTab(self.recording_scheme_tab, "Recording Scheme")

        self.insect_collection_tab = InsectCollectionTab()
        self.tabs.addTab(self.insect_collection_tab, "Insect Collection")

        self.stats_reports_tab = StatsReportsTab()
        self.tabs.addTab(self.stats_reports_tab, "Stats/Reports")

        self.mapping_tab = MappingTab()
        self.tabs.addTab(self.mapping_tab, "Mapping")

        self.settings_tab = SettingsTab(db_manager=get_database())
        self.settings_tab.database_changed.connect(self._on_database_changed)
        self.settings_tab.settings_changed.connect(self._on_settings_changed)
        self.tabs.addTab(self.settings_tab, "Settings")

        # Track initialized tabs for lazy loading
        self._initialized_tabs = set()
        self._initialized_tabs.add(0)  # Home tab is always ready
        # NOTE: currentChanged connected AFTER setup to prevent eager loading

        # Cross-tab signal connections
        # CSV backup flag — set when any data changes during session

        self._data_changed = False
        self._connect_cross_tab_signals()

    def _connect_cross_tab_signals(self):
        """Connect signals between tabs for data synchronization."""
        # When a record is saved on Home tab, refresh Observation tab
        self.home_tab.quick_entry.record_saved.connect(self._on_record_saved)

        # When "View more" is clicked on Stats tab, navigate to Observation Data
        self.stats_reports_tab.navigate_to_observations.connect(self._navigate_to_observation_tab)
        self.stats_reports_tab.navigate_to_order.connect(self._navigate_to_observation_tab_by_order)
        self.stats_reports_tab.navigate_to_month.connect(self._navigate_to_observation_tab_by_month)
        self.stats_reports_tab.navigate_to_family.connect(self._navigate_to_observation_tab_by_family)
        self.stats_reports_tab.navigate_to_year.connect(self._navigate_to_observation_tab_by_year)

        # When "View more" is clicked on Collection Stats, navigate to Insect Collection
        self.stats_reports_tab.navigate_to_collection.connect(self._navigate_to_collection_tab)
        self.stats_reports_tab.filter_collection_by_order.connect(self._filter_collection_by_order)
        self.stats_reports_tab.filter_collection_by_family.connect(self._filter_collection_by_family)
        self.stats_reports_tab.filter_collection_by_year.connect(self._filter_collection_by_year)
        self.stats_reports_tab.filter_collection_by_condition.connect(self._filter_collection_by_condition)
        self.stats_reports_tab.filter_collection_by_prep_type.connect(self._filter_collection_by_prep_type)
        self.stats_reports_tab.filter_collection_by_storage.connect(self._filter_collection_by_storage)
        self.stats_reports_tab.show_specimen_detail.connect(self._show_specimen_detail_by_id)
        self.stats_reports_tab.navigate_to_scheme.connect(self._navigate_to_scheme_tab)
        self.stats_reports_tab.navigate_to_scheme_vc.connect(self._navigate_to_scheme_tab_with_vc)
        self.stats_reports_tab.navigate_to_scheme_record.connect(self._navigate_to_scheme_record)
        # Commercial Reports: manage a project's records (8 Oct 2026)
        _crd = getattr(self.stats_reports_tab, 'commercial_reports_dashboard', None)
        if _crd is not None and hasattr(_crd, 'add_records_requested'):
            _crd.view_project_requested.connect(self._navigate_to_observation_tab_by_project)
            _crd.add_records_requested.connect(self._open_data_entry_for_project)

        # Connect Recording Scheme tab navigation signals (from record detail dialog)
        self.recording_scheme_tab.navigate_to_observations.connect(self._navigate_to_observation_tab)
        self.recording_scheme_tab.navigate_to_collection.connect(self._navigate_to_collection_tab)

        # Connect stats filter changes to RS data tab refresh
        if hasattr(self, 'stats_reports_tab') and hasattr(self.stats_reports_tab, 'scheme_dashboard'):
            self.stats_reports_tab.scheme_dashboard.data_filters_changed.connect(self.recording_scheme_tab.refresh)

        # When "View specimens" is clicked on Home tab, navigate to Insect Collection
        try:
            self.home_tab.navigate_to_collection.connect(self._navigate_to_collection_tab)
            self.home_tab.navigate_to_observations.connect(self._navigate_to_observation_tab)
        except AttributeError:
            pass  # Signal not available yet

        # Navigation from detail dialogs (Records/In Collection links)
        try:
            self.insect_collection_tab.navigate_to_observations.connect(self._navigate_to_observation_tab)
        except AttributeError:
            pass  # Signal not available yet

        try:
            self.observation_tab.navigate_to_collection.connect(self._navigate_to_collection_tab)
        except AttributeError:
            pass  # Signal not available yet

        # When observations are imported, refresh Home tab stats
        try:
            self.observation_tab.data_imported.connect(self.home_tab.refresh_data)
        except AttributeError:
            pass  # Signal not available yet

        # Track data changes for CSV backup on close
        try:
            self.home_tab.quick_entry.record_saved.connect(self._mark_data_changed)
        except AttributeError:
            pass
        try:
            self.observation_tab.data_imported.connect(self._mark_data_changed)
        except AttributeError:
            pass
        try:
            self.insect_collection_tab.data_changed.connect(self._mark_data_changed)
        except AttributeError:
            pass
        # Deletes / edits / Mark Commercial on the data tabs and the scheme dashboard (OBS-10)
        self.observation_tab.records_changed.connect(self._mark_data_changed)
        self.recording_scheme_tab.records_changed.connect(self._mark_data_changed)
        _sd = getattr(self.stats_reports_tab, 'scheme_dashboard', None)
        if _sd is not None and hasattr(_sd, 'scheme_records_changed'):
            _sd.scheme_records_changed.connect(self._mark_data_changed)
            _sd.scheme_records_changed.connect(self._refresh_scheme_tab_if_loaded)

    def _get_stats_data_type(self) -> str:
        """Get data type filter based on active stats sub-tab."""
        if hasattr(self, 'stats_reports_tab') and hasattr(self.stats_reports_tab, 'stack'):
            idx = self.stats_reports_tab.stack.currentIndex()
            if idx == 0:
                return 'personal'
            elif idx == 1:
                return 'commercial'
        return 'all'

    def _apply_data_type_filter(self):
        """Set the obs tab data type filter to match the active stats tab (triggers full reload)."""
        dt = self._get_stats_data_type()
        if hasattr(self.observation_tab, 'filter_bar') and hasattr(self.observation_tab.filter_bar, '_on_data_type_clicked'):
            self.observation_tab.filter_bar._on_data_type_clicked(dt)

    def _apply_exclusion_to_records(self, observations):
        """Filter observation list by the same exclusion rules as the stats service."""
        from PySide6.QtCore import QSettings
        settings = QSettings()
        exclude = settings.value("display/exclude_incomplete_species", True, type=bool)
        if not exclude:
            return observations
        filtered = []
        for obs in observations:
            tvk = getattr(obs, 'species_tvk', '')
            if not tvk:
                continue
            name = getattr(obs, 'species_name', '')
            if ' ' not in name:
                continue
            name_lower = name.lower()
            if any(x in name_lower for x in ['agg.', 'agg ', ' agg', 's.l.', 'sensu lato']):
                continue
            filtered.append(obs)
        return filtered

    def _set_data_type_visual(self):
        """Set the data type button visually without triggering a reload."""
        dt = self._get_stats_data_type()
        if hasattr(self.observation_tab, 'filter_bar') and hasattr(self.observation_tab.filter_bar, '_data_type_buttons'):
            for d, btn in self.observation_tab.filter_bar._data_type_buttons.items():
                btn.setChecked(d == dt)

    def _navigate_to_observation_tab(self, species_filter: str = ""):
        """Navigate to the Observation Data tab and filter by species."""
        self.tabs.setCurrentWidget(self.observation_tab)
        if species_filter:
            # This species alone -- no filter bar, wizard or pinned-project filter left
            # over from before (OBS-08: Rutpela showed 0 of its 62 records)
            if hasattr(self.observation_tab, 'show_species'):
                self.observation_tab.show_species(species_filter)
            elif hasattr(self.observation_tab, 'filter_by_species'):
                self.observation_tab.filter_by_species(species_filter)
        else:
            self.observation_tab.show_new_species_list()

    def _navigate_to_observation_tab_by_month(self, month: int):
        """Navigate to Observation Data tab filtered by a specific month (all years)."""
        MONTH_NAMES = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                       'July', 'August', 'September', 'October', 'November', 'December']
        month_name = MONTH_NAMES[month] if 1 <= month <= 12 else str(month)

        self.tabs.setCurrentWidget(self.observation_tab)
        if hasattr(self.observation_tab, 'filter_bar'):
            self.observation_tab.filter_bar.clear_filters()
            if hasattr(self.observation_tab, 'toolbar') and hasattr(self.observation_tab.toolbar, 'set_filters_visible'):
                self.observation_tab.toolbar.set_filters_visible(True)
        self._set_data_type_visual()

        # Filter client-side: by data type and month
        dt = self._get_stats_data_type()
        if hasattr(self.observation_tab, '_all_observations') and self.observation_tab._all_observations:
            filtered = []
            for obs in self.observation_tab._all_observations:
                # Record type filter
                if dt == 'personal' and getattr(obs, 'record_type', '') != 'Personal':
                    continue
                if dt == 'commercial' and getattr(obs, 'record_type', '') != 'Commercial':
                    continue
                date_val = getattr(obs, 'date', None) or getattr(obs, 'date_observed', None) or ''
                date_str = str(date_val)[:10]  # YYYY-MM-DD
                try:
                    obs_month = int(date_str[5:7])
                    if obs_month == month:
                        filtered.append(obs)
                except (ValueError, IndexError):
                    continue
            excluded = self._apply_exclusion_to_records(filtered)
            self.observation_tab.table_model.set_observations_fast(excluded)
            if hasattr(self.observation_tab, '_connect_proxy_after_load'):
                self.observation_tab._connect_proxy_after_load()
            if hasattr(self.observation_tab, '_count_species_with_exclusion'):
                species_count = self.observation_tab._count_species_with_exclusion(filtered)
            else:
                species_count = len(set(getattr(obs, 'species_name', '') for obs in filtered if getattr(obs, 'species_name', '')))
            self.observation_tab._update_stats(len(excluded), species_count)
            self.statusBar().showMessage(f"Showing {len(filtered):,} records for {month_name} (all years)", 5000)

    def _navigate_to_observation_tab_by_project(self, project: str, client: str = ""):
        """Observation Data showing only one commercial project's records (Commercial Reports).

        Pinned in the tab (set_project_filter), so it survives the reload after an edit or
        delete, until "Show all records" there. No species exclusion: when managing a
        job, every record of it should be visible."""
        self.tabs.setCurrentWidget(self.observation_tab)
        if hasattr(self.observation_tab, 'set_project_filter'):
            if hasattr(self.observation_tab, 'filter_bar'):
                self.observation_tab.filter_bar.clear_filters()
            self.observation_tab.set_project_filter(project, client)
            label = (project or '(no project)') + (f' \u2014 {client}' if client else '')
            self.statusBar().showMessage(f"Observation Data pinned to {label}", 8000)
            return
        if hasattr(self.observation_tab, 'filter_bar'):
            self.observation_tab.filter_bar.clear_filters()
            if hasattr(self.observation_tab.filter_bar, '_data_type_buttons'):
                for d, btn in self.observation_tab.filter_bar._data_type_buttons.items():
                    btn.setChecked(d == 'commercial')
        if not getattr(self.observation_tab, '_all_observations', None) and hasattr(self.observation_tab, '_load_data'):
            self.observation_tab._load_data()
        records = [o for o in (getattr(self.observation_tab, '_all_observations', None) or [])
                   if getattr(o, 'record_type', '') == 'Commercial'
                   and (getattr(o, 'project_name', '') or '') == (project or '')
                   and (getattr(o, 'client', '') or '') == (client or '')]
        self.observation_tab.table_model.set_observations_fast(records)
        if hasattr(self.observation_tab, '_connect_proxy_after_load'):
            self.observation_tab._connect_proxy_after_load()
        species = len({getattr(o, 'species_name', '') for o in records if getattr(o, 'species_name', '')})
        self.observation_tab._update_stats(len(records), species)
        label = (project or '(no project)') + (f' \u2014 {client}' if client else '')
        self.statusBar().showMessage(f"Showing {len(records):,} records for {label}", 8000)

    def _open_data_entry_for_project(self, project: str, client: str = "", embargo_until: str = ""):
        """Data Entry on this project's job -- reopened, or created -- from Commercial Reports."""
        from PySide6.QtWidgets import QMessageBox
        de = getattr(self, 'data_entry_tab', None)
        if de is None or not hasattr(de, 'open_project_job'):
            QMessageBox.information(self, "Data Entry", "The Data Entry tab is not available.")
            return
        how = de.open_project_job(project, client, embargo_until or None)
        if not how:
            QMessageBox.warning(self, "Data Entry", "Could not open a job: staging is unavailable.")
            return
        self.tabs.setCurrentWidget(de)
        msg = {"open": "Opened the project's job",
               "reopened": "Reopened the project's committed job",
               "created": "Created a job for this project"}.get(how, "Opened")
        self.statusBar().showMessage(f"{msg}: {project}. New records commit under the same "
                                     "project and client.", 10000)

    def _navigate_to_observation_tab_by_family(self, family_name: str):
        """Navigate to Observation Data tab filtered by a specific family."""
        self.tabs.setCurrentWidget(self.observation_tab)
        if family_name:
            if hasattr(self.observation_tab, 'filter_bar'):
                self.observation_tab.filter_bar.clear_filters()
            if hasattr(self.observation_tab, 'clear_wizard_filters'):   # OBS-08
                self.observation_tab.clear_wizard_filters()
            self._apply_data_type_filter()
            if hasattr(self.observation_tab, 'toolbar') and hasattr(self.observation_tab.toolbar, 'set_filters_visible'):
                self.observation_tab.toolbar.set_filters_visible(True)
            if hasattr(self.observation_tab, 'filter_bar') and hasattr(self.observation_tab.filter_bar, 'set_family_filter'):
                self.observation_tab.filter_bar.set_family_filter(family_name)


    def _navigate_to_observation_tab_by_order(self, order_name: str):
        """Navigate to the Observation Data tab and filter by order."""
        self.tabs.setCurrentWidget(self.observation_tab)
        if order_name:
            # First clear any existing filters so only order is active
            if hasattr(self.observation_tab, 'filter_bar'):
                self.observation_tab.filter_bar.clear_filters()
            if hasattr(self.observation_tab, 'clear_wizard_filters'):   # OBS-08
                self.observation_tab.clear_wizard_filters()
            self._apply_data_type_filter()
            # Show the filter bar
            if hasattr(self.observation_tab, 'toolbar') and hasattr(self.observation_tab.toolbar, 'set_filters_visible'):
                self.observation_tab.toolbar.set_filters_visible(True)
            # Set the order filter (this triggers _emit_filters -> _apply_current_filters)
            if hasattr(self.observation_tab, 'filter_bar') and hasattr(self.observation_tab.filter_bar, 'set_order_filter'):
                self.observation_tab.filter_bar.set_order_filter(order_name)

    def _navigate_to_observation_tab_by_year(self, year: int):
        """Navigate to Observation Data tab filtered by a specific year."""
        self.tabs.setCurrentWidget(self.observation_tab)
        if year:
            if hasattr(self.observation_tab, 'filter_bar'):
                self.observation_tab.filter_bar.clear_filters()
            self._set_data_type_visual()
            if hasattr(self.observation_tab, 'toolbar') and hasattr(self.observation_tab.toolbar, 'set_filters_visible'):
                self.observation_tab.toolbar.set_filters_visible(True)
            # Filter by data type and year
            dt = self._get_stats_data_type()
            if hasattr(self.observation_tab, '_all_observations') and self.observation_tab._all_observations:
                year_str = str(year)
                filtered = []
                for obs in self.observation_tab._all_observations:
                    if dt == 'personal' and getattr(obs, 'record_type', '') != 'Personal':
                        continue
                    if dt == 'commercial' and getattr(obs, 'record_type', '') != 'Commercial':
                        continue
                    if getattr(obs, 'date', '') and str(getattr(obs, 'date', '')).startswith(year_str):
                        filtered.append(obs)
                excluded = self._apply_exclusion_to_records(filtered)
                if hasattr(self.observation_tab, 'table_model'):
                    self.observation_tab.table_model.set_observations_fast(excluded)
                    self.observation_tab._connect_proxy_after_load()
                    if hasattr(self.observation_tab, '_count_species_with_exclusion'):
                        species_count = self.observation_tab._count_species_with_exclusion(filtered)
                    else:
                        species_count = len(set(getattr(obs, 'species_name', '') for obs in filtered if getattr(obs, 'species_name', '')))
                    self.observation_tab._update_stats(len(excluded), species_count)

    def _navigate_to_collection_tab(self, species_filter: str = ""):
        """Navigate to the Insect Collection tab and filter by species."""
        self.tabs.setCurrentWidget(self.insect_collection_tab)
        if species_filter == "__new_collections_list__":
            if hasattr(self.insect_collection_tab, 'filters') and hasattr(self.insect_collection_tab.filters, 'select_new_collections_list'):
                self.insect_collection_tab.filters.select_new_collections_list()
            return
        if species_filter:
            # Apply species filter using the new method
            if hasattr(self.insect_collection_tab, 'filters') and hasattr(self.insect_collection_tab.filters, 'set_species_filter'):
                if hasattr(self.insect_collection_tab, 'clear_wizard_filters'):   # OBS-08
                    self.insect_collection_tab.clear_wizard_filters()
                # applies the filter: one reload (a second _load_data here doubled it)
                self.insect_collection_tab.filters.set_species_filter(species_filter)
                # Sync toolbar button state
                if hasattr(self.insect_collection_tab, 'toolbar') and hasattr(self.insect_collection_tab.toolbar, 'set_filters_visible'):
                    self.insect_collection_tab.toolbar.set_filters_visible(True)
            elif hasattr(self.insect_collection_tab, 'filters') and hasattr(self.insect_collection_tab.filters, 'species_edit'):
                self.insect_collection_tab.filters.species_edit.setText(species_filter)
                self.insect_collection_tab.filters._emit_filters()

    def _navigate_to_scheme_tab(self, species_filter: str = ""):
        """Navigate to the Recording Scheme tab and filter by species."""
        self.tabs.setCurrentWidget(self.recording_scheme_tab)
        if hasattr(self.recording_scheme_tab, 'clear_wizard_filters'):   # OBS-08
            self.recording_scheme_tab.clear_wizard_filters()
        if species_filter:
            # Use direct filter with exact match for faster query
            filters = {'species': species_filter, 'species_exact': True}
            self.recording_scheme_tab._load_data(filters)
            # Update filter bar UI to show the filter
            if hasattr(self.recording_scheme_tab, 'filter_bar'):
                fb = self.recording_scheme_tab.filter_bar
                fb.blockSignals(True)
                fb.species_edit.setText(species_filter)
                fb.blockSignals(False)
                fb.setVisible(True)
                if hasattr(self.recording_scheme_tab, 'toolbar'):
                    self.recording_scheme_tab.toolbar.filter_btn.setChecked(True)
        elif hasattr(self.recording_scheme_tab, 'filter_bar'):
            fb = self.recording_scheme_tab.filter_bar
            fb.clear_filters()

    def _navigate_to_scheme_tab_with_vc(self, species_filter: str, vc_number: int):
        """Navigate to the Recording Scheme tab and filter by species and vice county."""
        self.tabs.setCurrentWidget(self.recording_scheme_tab)
        if hasattr(self.recording_scheme_tab, 'clear_wizard_filters'):   # OBS-08
            self.recording_scheme_tab.clear_wizard_filters()
        # Use direct filter with exact match for faster query
        filters = {'species_exact': True}
        if species_filter:
            filters['species'] = species_filter
        if vc_number > 0:
            filters['vice_county'] = vc_number
        self.recording_scheme_tab._load_data(filters)
        # Update filter bar UI to show the filters
        if hasattr(self.recording_scheme_tab, 'filter_bar'):
            fb = self.recording_scheme_tab.filter_bar
            fb.blockSignals(True)
            if species_filter:
                fb.species_edit.setText(species_filter)
            if vc_number > 0 and hasattr(fb, 'vc_combo'):
                for i in range(fb.vc_combo.count()):
                    if fb.vc_combo.itemData(i) == vc_number:
                        fb.vc_combo.setCurrentIndex(i)
                        break
            fb.blockSignals(False)
            fb.setVisible(True)
            if hasattr(self.recording_scheme_tab, 'toolbar'):
                self.recording_scheme_tab.toolbar.filter_btn.setChecked(True)
            # Show filter bar if hidden
            if hasattr(self.recording_scheme_tab, 'toolbar'):
                fb.setVisible(True)
                self.recording_scheme_tab.toolbar.filter_btn.setChecked(True)

    def _navigate_to_scheme_record(self, record_id: int):
        """Navigate to Recording Scheme tab and show a specific record."""
        self.tabs.setCurrentWidget(self.recording_scheme_tab)
        if hasattr(self.recording_scheme_tab, 'show_record_by_id'):
            self.recording_scheme_tab.show_record_by_id(record_id)

    def _filter_collection_by_order(self, order_name: str):
        """Navigate to Insect Collection tab filtered by order."""
        if order_name and hasattr(self.insect_collection_tab, 'filters'):
            filters = self.insect_collection_tab.filters
            # Block signals to prevent multiple reloads
            filters.blockSignals(True)
            # Clear filters
            if hasattr(filters, 'family_edit'):
                filters.family_edit.clear()
            if hasattr(filters, 'species_edit'):
                filters.species_edit.clear()
            if hasattr(filters, 'date_from_edit'):
                filters.date_from_edit.clear()
            if hasattr(filters, 'date_to_edit'):
                filters.date_to_edit.clear()
            # Set order filter - add if not present
            if hasattr(filters, 'order_combo'):
                idx = filters.order_combo.findText(order_name)
                if idx >= 0:
                    filters.order_combo.setCurrentIndex(idx)
                else:
                    filters.order_combo.addItem(order_name, order_name)
                    filters.order_combo.setCurrentIndex(filters.order_combo.count() - 1)
            # Unblock and show filters
            filters.blockSignals(False)
            if hasattr(self.insect_collection_tab, 'toolbar'):
                self.insect_collection_tab.toolbar.set_filters_visible(True)
            filters.setVisible(True)
            # Emit filters once to trigger load
            if hasattr(filters, '_emit_filters'):
                filters._emit_filters()
        # Navigate
        self.tabs.setCurrentWidget(self.insect_collection_tab)

    def _filter_collection_by_family(self, family_name: str):
        """Navigate to Insect Collection tab filtered by family."""
        if family_name and hasattr(self.insect_collection_tab, 'filters'):
            filters = self.insect_collection_tab.filters
            # Block signals to prevent multiple reloads
            filters.blockSignals(True)
            # Clear filters
            if hasattr(filters, 'order_combo'):
                filters.order_combo.setCurrentIndex(0)
            if hasattr(filters, 'species_edit'):
                filters.species_edit.clear()
            if hasattr(filters, 'date_from_edit'):
                filters.date_from_edit.clear()
            if hasattr(filters, 'date_to_edit'):
                filters.date_to_edit.clear()
            # Set family filter
            if hasattr(filters, 'family_edit'):
                filters.family_edit.setText(family_name)
            # Unblock and show filters
            filters.blockSignals(False)
            if hasattr(self.insect_collection_tab, 'toolbar'):
                self.insect_collection_tab.toolbar.set_filters_visible(True)
            filters.setVisible(True)
            # Emit filters once to trigger load
            if hasattr(filters, '_emit_filters'):
                filters._emit_filters()
        # Navigate
        self.tabs.setCurrentWidget(self.insect_collection_tab)

    def _filter_collection_by_year(self, year: str):
        """Navigate to Insect Collection tab filtered by year."""
        if year and hasattr(self.insect_collection_tab, 'filters'):
            filters = self.insect_collection_tab.filters
            # Block signals to prevent multiple reloads
            filters.blockSignals(True)
            # Clear other filters
            if hasattr(filters, 'order_combo'):
                filters.order_combo.setCurrentIndex(0)
            if hasattr(filters, 'species_edit'):
                filters.species_edit.clear()
            if hasattr(filters, 'family_edit'):
                filters.family_edit.clear()
            if hasattr(filters, 'location_edit'):
                filters.location_edit.clear()
            # Set date range for the year
            if hasattr(filters, 'date_from_edit'):
                from PySide6.QtCore import QDate; filters.date_from_edit.setDate(QDate(int(year), 1, 1))
            if hasattr(filters, 'date_to_edit'):
                filters.date_to_edit.setDate(QDate(int(year), 12, 31))
            # Unblock and show filters
            filters.blockSignals(False)
            if hasattr(self.insect_collection_tab, 'toolbar'):
                self.insect_collection_tab.toolbar.set_filters_visible(True)
            filters.setVisible(True)
            # Emit filters once to trigger load
            if hasattr(filters, '_emit_filters'):
                filters._emit_filters()
            # Also call _load_data directly to ensure refresh
            if hasattr(self.insect_collection_tab, '_load_data'):
                self.insect_collection_tab._load_data()
        # Navigate
        self.tabs.setCurrentWidget(self.insect_collection_tab)

    def _filter_collection_by_condition(self, condition: str):
        """Navigate to Insect Collection tab filtered by condition."""
        # Switch tab first to avoid triggering additional reloads
        self.tabs.setCurrentWidget(self.insect_collection_tab)
        if condition:
            self.insect_collection_tab.set_extra_filter('condition', condition)
            self.insect_collection_tab._load_data()

    def _filter_collection_by_prep_type(self, prep_type: str):
        """Navigate to Insect Collection tab filtered by preparation type."""
        self.tabs.setCurrentWidget(self.insect_collection_tab)
        if prep_type:
            self.insect_collection_tab.set_extra_filter('preparation_type', prep_type)
            self.insect_collection_tab._load_data()

    def _filter_collection_by_storage(self, storage: str):
        """Navigate to Insect Collection tab filtered by storage location."""
        self.tabs.setCurrentWidget(self.insect_collection_tab)
        if storage:
            self.insect_collection_tab.set_extra_filter('storage_location', storage)
            self.insect_collection_tab._load_data()

    def _navigate_to_collection_recent(self):
        """Navigate to the Insect Collection tab and show recent additions."""
        self.tabs.setCurrentWidget(self.insect_collection_tab)
        self.insect_collection_tab.show_recent_additions()

    def _add_placeholder_tab(self, name: str):
        """Add a placeholder tab."""
        placeholder = QWidget()
        layout = QVBoxLayout(placeholder)
        label = QLabel(f"{name} Tab - Coming Soon")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        self.tabs.addTab(placeholder, name)

    def _setup_statusbar(self):
        """Set up the status bar."""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("Ready")

    def apply_theme(self):
        """Apply the current theme to the main window and all tabs."""
        t = theme()

        # NEW: Use TabColors from centralised config (replaces hardcoded values)

        # Apply main window background and tab styling
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {t.get('background')};
            }}
            QTabWidget::pane {{
                border: none;
            }}
            QTabBar {{
                background-color: {t.get('surface')};
            }}
            QTabBar::tab {{
                padding: 8px 16px;
                border-bottom: 3px solid transparent;
                background-color: {t.get('surface')};
                color: {t.get('text_secondary')};
                font-size: 13px;
            }}
            QTabBar::tab:hover {{
                background-color: {t.get('surface_alt')};
            }}
            QTabBar::tab:selected {{
                color: {t.get('text_primary')};
                font-weight: 600;
                background-color: {t.get('surface')};
            }}
            /* Home tab */
            QTabBar::tab:first {{
                border-bottom-color: transparent;
            }}
            QTabBar::tab:first:selected {{
                border-bottom-color: {t.get('text_secondary')};
            }}
            /* Observation Data tab - Sage Green */
            QTabBar::tab:nth-of-type(2) {{
                border-bottom-color: transparent;
            }}
            QTabBar::tab:nth-of-type(2):selected {{
                border-bottom-color: {TabColors.OBSERVATION};
                color: {TabColors.OBSERVATION};
            }}
            /* Recording Scheme tab - Dusty Purple */
            QTabBar::tab:nth-of-type(3) {{
                border-bottom-color: transparent;
            }}
            QTabBar::tab:nth-of-type(3):selected {{
                border-bottom-color: {TabColors.RECORDING_SCHEME};
                color: {TabColors.RECORDING_SCHEME};
            }}
            /* Insect Collection tab - Warm Gold */
            QTabBar::tab:nth-of-type(4) {{
                border-bottom-color: transparent;
            }}
            QTabBar::tab:nth-of-type(4):selected {{
                border-bottom-color: {TabColors.COLLECTION};
                color: {TabColors.COLLECTION};
            }}
        """)

        # Notify all tabs to refresh their themes
        tabs_with_theme = [
            self.home_tab,
            self.observation_tab,
            self.contributed_tab,
            self.recording_scheme_tab,
            self.insect_collection_tab,
            self.stats_reports_tab,
            self.mapping_tab,
            self.settings_tab,
        ]

        for tab in tabs_with_theme:
            if hasattr(tab, 'apply_theme'):
                try:
                    tab.apply_theme()
                except Exception as e:
                    print(f"Warning: Could not apply theme to {tab.__class__.__name__}: {e}")

    def _initialize_services(self):
        """Initialize database and services."""
        _t_init = time.perf_counter()
        self._update_splash(56, "Connecting to database...")
        db = get_database()

        # Set database paths if provided
        if self._main_db_path:
            db.set_main_path(self._main_db_path)

        if self._uksi_db_path:
            db.set_uksi_path(self._uksi_db_path)

        # Initialize search service with UKSI model
        self._update_splash(58, "Loading species database...")
        try:
            search_service = get_search_service()

            if self._uksi_db_path and Path(self._uksi_db_path).exists():
                uksi_model = UKSIModel(db)
                search_service.set_uksi_model(uksi_model)

            if self._main_db_path:
                search_service.set_database(db)

        except Exception as e:
            print(f"Warning: Could not initialize search service: {e}")

        # Initialize stats services with database
        self._update_splash(62, "Initializing statistics...")
        try:
            db = get_database()
            get_observation_stats_service().initialize(db)
            get_recording_scheme_stats().initialize(db)
            get_specimen_stats().initialize(db)
        except Exception as e:
            print(f"Warning: Could not initialize stats services: {e}")

        # Initialize Home tab
        self._update_splash(65, "Loading Home tab...")
        try:
            self.home_tab.initialize()
        except Exception as e:
            print(f"Warning: Could not initialize Home tab: {e}")
            self.statusbar.showMessage(f"Warning: {e}")

        # Initialize Settings tab (to show db paths and stats)
        try:
            self.settings_tab.initialize()
        except Exception as e:
            print(f"Warning: Could not initialize Settings tab: {e}")

        # Initialize Observation tab (needed for Home tab stats)
        self._update_splash(70, "Loading Observation Data...")
        try:
            self.observation_tab.initialize()
        except Exception as e:
            print(f"Warning: Could not initialize Observation tab: {e}")

        # Pre-load Recording Scheme data in background thread
        # Data loads while user views Observation tab, ready when they click RS
        self.recording_scheme_tab.start_preload(self._main_db_path)

        # Defer other tab UI init - they initialize on first visit via _on_tab_changed
        # But RS data is already loading in background
        self._update_splash(85, "Ready...")

    def set_status(self, message: str, timeout: int = 5000):
        """Show a message in the status bar."""
        self.statusbar.showMessage(message, timeout)

    def _show_specimen_detail_by_id(self, specimen_id: int):
        """Show specimen detail dialog for a specific specimen ID."""
        try:
            from .dialogs import RecordDetailDialog
            from ..models.database import get_database

            db = get_database()
            result = db.execute_main(
                "SELECT * FROM specimens WHERE id = ?", (specimen_id,)
            )
            if result:
                specimen = dict(result[0])
                dialog = RecordDetailDialog(
                    specimen,
                    record_type='specimen',
                    parent=self
                )
                dialog.navigate_to_observations.connect(
                    lambda sp: (dialog.close(), self._navigate_to_observation_tab(sp))
                )
                dialog.navigate_to_collection.connect(
                    lambda sp: (dialog.close(), self._navigate_to_collection_tab(sp))
                )
                # Edit / Delete did nothing from the collection dashboard (OBS-04):
                # hand them to the Insect Collection tab, which owns specimen edits
                ic = self.insect_collection_tab
                ic.initialize(self._main_db_path, self._uksi_db_path)   # no-op once loaded
                ic._current_detail_dialog = dialog
                dialog.edit_requested.connect(ic._on_detail_edit_requested)
                dialog.delete_requested.connect(ic._on_detail_delete_requested)
                dialog.exec()
                ic._current_detail_dialog = None
        except Exception as e:
            print(f"[MainWindow] Error showing specimen detail: {e}")

    def _clear_all_data_tab_filters(self):
        """Clear filters on Observation, Recording Scheme, and Insect Collection tabs."""
        # Clear Observation tab filters
        try:
            if hasattr(self, 'observation_tab') and hasattr(self.observation_tab, 'filter_bar'):
                fb = self.observation_tab.filter_bar
                fb.blockSignals(True)
                if hasattr(fb, 'clear_filters'):
                    fb.clear_filters()
                fb.blockSignals(False)
        except Exception as e:
            print(f"[MainWindow] Could not clear observation filters: {e}")

        # Clear Recording Scheme tab filters
        try:
            if hasattr(self, 'recording_scheme_tab') and hasattr(self.recording_scheme_tab, 'filter_bar'):
                fb = self.recording_scheme_tab.filter_bar
                fb.blockSignals(True)
                if hasattr(fb, 'clear_filters'):
                    fb.clear_filters()
                fb.blockSignals(False)
        except Exception as e:
            print(f"[MainWindow] Could not clear recording scheme filters: {e}")

        # Clear Insect Collection tab filters
        try:
            if hasattr(self, 'insect_collection_tab') and hasattr(self.insect_collection_tab, 'filters'):
                fb = self.insect_collection_tab.filters
                fb.blockSignals(True)
                if hasattr(fb, 'clear_all'):
                    fb.clear_all()
                elif hasattr(fb, 'order_combo'):
                    fb.order_combo.setCurrentIndex(0)
                if hasattr(fb, 'family_edit'):
                    fb.family_edit.clear()
                if hasattr(fb, 'species_edit'):
                    fb.species_edit.clear()
                fb.blockSignals(False)
        except Exception as e:
            print(f"[MainWindow] Could not clear collection filters: {e}")

    def _on_tab_changed(self, index: int):
        """Lazy load tab data on first visit. Widget-based so tab ORDER does not matter."""
        if not getattr(self, "_ready", False):
            return

        w = self.tabs.widget(index)

        # Refresh stats on every visit (data/settings may have changed)
        if w is self.stats_reports_tab and index in self._initialized_tabs:
            try:
                self.stats_reports_tab.refresh()
            except Exception:
                pass
            return

        if index in self._initialized_tabs:
            return

        self._initialized_tabs.add(index)
        self.statusbar.showMessage("Loading...")

        try:
            if w is self.observation_tab:
                self.observation_tab.initialize()
                if hasattr(self.observation_tab, '_enable_sorting_on_first_view'):
                    self.observation_tab._enable_sorting_on_first_view()
            elif w is self.contributed_tab:
                self.contributed_tab.initialize()
            elif w is self.recording_scheme_tab:
                self.recording_scheme_tab.initialize(self._main_db_path, self._uksi_db_path)
                # Sorting enabled after async data load completes (in _on_data_loaded)
            elif w is self.insect_collection_tab:
                self.insect_collection_tab.initialize(self._main_db_path, self._uksi_db_path)
                if hasattr(self.insect_collection_tab, '_enable_sorting_on_first_view'):
                    self.insect_collection_tab._enable_sorting_on_first_view()
            elif w is self.stats_reports_tab:
                self.stats_reports_tab.initialize(self._main_db_path, self._uksi_db_path)
            # Mapping / Settings / Data Entry: no lazy init required
            self.statusbar.showMessage("Ready", 2000)
        except Exception as e:
            print(f"Warning: Could not initialize tab {index}: {e}")
            import traceback
            traceback.print_exc()
            self.statusbar.showMessage(f"Error loading tab: {e}", 5000)

    def _on_record_saved(self, record_data: dict):
        """Handle record saved from Home tab - refresh Observation tab and Home stats."""
        try:
            self.observation_tab.refresh()
        except Exception as e:
            print(f"Warning: Could not refresh Observation tab: {e}")

        # Also refresh Home tab stats when saving from Quick Entry
        try:
            self.home_tab.refresh_data()
        except Exception as e:
            print(f"Warning: Could not refresh Home tab stats: {e}")

    def _on_settings_changed(self):
        """Handle settings saved - refresh defaults, display settings, and theme."""
        try:
            self.home_tab.quick_entry.reload_defaults()
        except Exception as e:
            print(f"Warning: Could not reload defaults: {e}")

        # Refresh display settings on Home tab (common name visibility)
        try:
            self.home_tab.refresh_display_settings()
        except Exception as e:
            print(f"Warning: Could not refresh home display settings: {e}")

        # Refresh exclusion setting cache and invalidate stats services
        try:
            from ..repositories.observation_repository import ObservationRepository
            ObservationRepository.refresh_exclusion_setting()

            # Invalidate all stats services so they re-query with new setting
            from ..services.observation_stats_service import get_observation_stats_service
            from ..services.recording_scheme_stats_service import get_recording_scheme_stats
            from ..services.specimen_stats_service import get_specimen_stats

            get_observation_stats_service().invalidate()
            get_recording_scheme_stats().invalidate()
            get_specimen_stats().invalidate()
        except Exception as e:
            print(f"Warning: Could not refresh exclusion setting: {e}")

        # Refresh Home tab data (Quick Stats species count respects exclusion setting)
        try:
            self.home_tab.refresh_data()
        except Exception as e:
            print(f"Warning: Could not refresh home data: {e}")

        # Refresh Observation tab stats (species count respects exclusion setting)
        try:
            self.observation_tab._apply_current_filters()
        except Exception as e:
            print(f"Warning: Could not refresh observation tab: {e}")

        # Refresh display settings on all tabs (e.g., common name visibility)
        try:
            self.observation_tab.refresh_display_settings()
        except Exception as e:
            print(f"Warning: Could not refresh observation display settings: {e}")

        # Refresh RS data (scheme family scope may have changed)
        try:
            if hasattr(self.recording_scheme_tab, '_initialized') and self.recording_scheme_tab._initialized:
                self.recording_scheme_tab.refresh()
        except Exception as e:
            print(f"Warning: Could not refresh recording scheme data: {e}")

        try:
            self.recording_scheme_tab.refresh_display_settings()
        except Exception as e:
            print(f"Warning: Could not refresh scheme display settings: {e}")

        # Refresh stats dashboards (scheme family scope may have changed)
        try:
            self.stats_reports_tab.refresh()
            # Force scheme dashboard refresh even if not currently visible
            if hasattr(self.stats_reports_tab, 'scheme_dashboard'):
                self.stats_reports_tab.scheme_dashboard.refresh()
        except Exception as e:
            print(f"Warning: Could not refresh stats tab: {e}")

        try:
            self.insect_collection_tab.refresh_display_settings()
        except Exception as e:
            print(f"Warning: Could not refresh collection display settings: {e}")

    def _on_database_changed(self):
        """Handle database path changes from Settings."""
        db = get_database()

        # Re-initialize search service
        try:
            search_service = get_search_service()

            if db.uksi_db_path and db.uksi_db_path.exists():
                uksi_model = UKSIModel(db)
                search_service.set_uksi_model(uksi_model)

            if db.main_db_path:
                search_service.set_database(db)

        except Exception as e:
            print(f"Warning: Could not reinitialize search service: {e}")

        # Refresh tabs that depend on database
        try:
            self.home_tab.refresh()
            # Also reload default settings in case they changed
            self.home_tab.quick_entry.reload_defaults()
        except Exception as e:
            print(f"Warning: Could not refresh Home tab: {e}")

        try:
            if hasattr(self.observation_tab, 'refresh'):
                self.observation_tab.refresh()
        except Exception as e:
            print(f"Warning: Could not refresh Observation tab: {e}")

        if getattr(self.contributed_tab, '_initialized', False):
            try:
                self.contributed_tab.refresh()
            except Exception as e:
                print(f"Warning: Could not refresh Contributed tab: {e}")

        self.set_status("Database connected successfully")


    def showEvent(self, event):
        """Ensure window is maximized and apply filter settings after show."""
        super().showEvent(event)
        if not hasattr(self, '_first_show_done'):
            self._first_show_done = True
            from PySide6.QtCore import QTimer
            QTimer.singleShot(100, self._apply_filter_settings_after_show)
            QTimer.singleShot(150, self.showMaximized)
            # build the shared species-search index (about a second) before the first
            # keystroke needs it -- in the background, once the window is up
            from shared.species_search import warm_up
            QTimer.singleShot(2000, warm_up)

    def _apply_filter_settings_after_show(self):
        """Apply filter visibility settings after window is shown."""
        from PySide6.QtCore import QSettings
        from ..core.config import Settings, Defaults
        settings = QSettings()

        # Observation tab
        show_obs = settings.value(Settings.FILTERS_VISIBLE_OBSERVATIONS, Defaults.FILTERS_VISIBLE_OBSERVATIONS, type=bool)
        if show_obs and hasattr(self.observation_tab, 'filter_bar'):
            self.observation_tab.filter_bar.setVisible(True)
            self.observation_tab.toolbar.filter_btn.setChecked(True)

        # Recording Scheme tab
        show_scheme = settings.value(Settings.FILTERS_VISIBLE_RECORDING_SCHEME, Defaults.FILTERS_VISIBLE_RECORDING_SCHEME, type=bool)
        if show_scheme and hasattr(self.recording_scheme_tab, 'filter_bar'):
            self.recording_scheme_tab.filter_bar.setVisible(True)
            self.recording_scheme_tab.toolbar.filter_btn.setChecked(True)

        # Insect Collection tab
        show_coll = settings.value(Settings.FILTERS_VISIBLE_COLLECTION, Defaults.FILTERS_VISIBLE_COLLECTION, type=bool)
        if show_coll and hasattr(self.insect_collection_tab, 'filters'):
            self.insect_collection_tab.filters.setVisible(True)
            self.insect_collection_tab.toolbar.filter_btn.setChecked(True)

    def _refresh_scheme_tab_if_loaded(self):
        if getattr(self.recording_scheme_tab, '_initialized', False):
            self.recording_scheme_tab.refresh()

    def _mark_data_changed(self, *args):
        """Mark that data was changed during this session and invalidate stats."""
        self._data_changed = True
        try:
            from ..services.observation_stats_service import get_observation_stats_service
            from ..services.recording_scheme_stats_service import get_recording_scheme_stats
            from ..services.specimen_stats_service import get_specimen_stats
            get_observation_stats_service().invalidate()
            get_recording_scheme_stats().invalidate()
            get_specimen_stats().invalidate()
        except Exception:
            pass
        # Figures on screen follow the change (review OBS-10: Stats kept its first
        # load until restart; Home only refreshed after Quick Entry or an import)
        try:
            self.stats_reports_tab.mark_stale()
        except Exception as e:
            print(f"[MainWindow] stats refresh after a change failed: {e}")
        try:
            self.home_tab.refresh_data()
        except Exception as e:
            print(f"[MainWindow] Home refresh after a change failed: {e}")

    def closeEvent(self, event):
        """Handle window close with optional CSV backup."""
        # Data Entry staging -> rolling CSV, before anything else can go wrong
        try:
            _de = getattr(self, "data_entry_tab", None)
            if _de is not None and hasattr(_de, "backup_now"):
                _de.backup_now()
        except Exception as _e:
            print(f"[DataEntry] close backup skipped: {_e}")

        if True:  # Always offer backup option
            from PySide6.QtCore import QSettings
            from src.core.config import Settings
            settings = QSettings()
            backup_enabled = settings.value(Settings.CSV_BACKUP_ON_CLOSE, False, type=bool)
            backup_path = settings.value(Settings.CSV_BACKUP_PATH, "")

            if backup_enabled and backup_path:
                from PySide6.QtWidgets import QMessageBox
                # It asked this even when nothing had changed (review OBS-25)
                changed = ("Data was changed during this session." if self._data_changed
                           else "No data was changed in this session.")
                reply = QMessageBox.question(
                    self, "CSV Safety Backup",
                    f"{changed}\n\n"
                    "Would you like to export CSV backups before closing?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self._export_csv_backups(backup_path)

        # Fold WAL side-files into the main databases before close
        # (protects against cloud sync copying an incomplete state)
        try:
            import sqlite3 as _sqlite3
            import paths as _paths
            for _db in (_paths.OBSERVATUM_DB, _paths.UKSI_DB):
                _conn = _sqlite3.connect(str(_db))
                _conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                _conn.close()
        except Exception:
            pass

        # Database backup -- working set only (~115 MB), after the WAL checkpoint
        try:
            from shared.backup_service import backup_working
            backup_working('on close')
        except Exception as _e:
            print(f'[backup] close backup skipped: {_e}')

        event.accept()

    def _export_csv_backups(self, backup_path: str):
        """Export all three data tables to CSV files."""
        import os
        import csv
        import sqlite3

        os.makedirs(backup_path, exist_ok=True)
        db_path = self._main_db_path

        # File-level backups of small user databases (frozen assessments, Munia)
        try:
            import paths as _paths
            _aux = [("examen.db", _paths.EXAMEN_DB)]
            if hasattr(_paths, "MUNIA_DB"):
                _aux.append(("munia.db", _paths.MUNIA_DB))
            for _name, _srcdb in _aux:
                if os.path.exists(str(_srcdb)):
                    _src_conn = sqlite3.connect(str(_srcdb))
                    _dst_conn = sqlite3.connect(os.path.join(backup_path, _name))
                    _src_conn.backup(_dst_conn)
                    _src_conn.close()
                    _dst_conn.close()
        except Exception:
            pass

        tables = {
            "observations": "observations.csv",
            "specimens": "specimens.csv",
            "recording_scheme": "recording_scheme.csv",
        }

        exported = []
        try:
            conn = sqlite3.connect(db_path)
            for table_name, filename in tables.items():
                try:
                    cursor = conn.execute(f"SELECT * FROM {table_name}")
                    rows = cursor.fetchall()
                    if not rows:
                        continue
                    col_names = [desc[0] for desc in cursor.description]
                    filepath = os.path.join(backup_path, filename)
                    with open(filepath, "w", newline="", encoding="utf-8") as f:
                        writer = csv.writer(f)
                        writer.writerow(col_names)
                        writer.writerows(rows)
                    exported.append(f"{table_name} ({len(rows)} rows)")
                except Exception as e:
                    print(f"CSV backup error for {table_name}: {e}")
            conn.close()

            if exported:
                summary = ', '.join(exported)
                self.statusbar.showMessage(f'CSV backup: {summary}')
            conn.close()
        except Exception as e:
            print(f"CSV backup error: {e}")


# Claude: deferred Observation-Data refresh worker (module-level; safe, auto-detecting)
def _claude_wire_obs_refresh(mw):
    """Connect Data Entry 'committed' -> Observation Data refresh() once all tabs exist."""
    try:
        de = getattr(mw, "data_entry_tab", None)
        if de is None or not hasattr(de, "committed"):
            return
        obs = None
        for _n, _v in list(vars(mw).items()):
            if _v is not de and _v.__class__.__name__ == "ObservationTab" and hasattr(_v, "refresh"):
                obs = _v
                break
        if obs is None:
            for _attr in ("tabs", "tab_widget", "tabWidget", "central_tabs", "main_tabs"):
                _tw = getattr(mw, _attr, None)
                if _tw is not None and hasattr(_tw, "count"):
                    for _i in range(_tw.count()):
                        _pg = _tw.widget(_i)
                        if _pg.__class__.__name__ == "ObservationTab" and hasattr(_pg, "refresh"):
                            obs = _pg
                            break
                if obs is not None:
                    break
        if obs is not None:
            de.committed.connect(obs.refresh)
        if hasattr(mw, "_mark_data_changed"):
            de.committed.connect(mw._mark_data_changed)   # Home / Stats follow a commit (OBS-10)
    except Exception:
        pass
