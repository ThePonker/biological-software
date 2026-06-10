"""
Observation Tab - Orchestrator

Main tab for viewing and managing observation records.
Uses mixins for filter, export, and detail functionality.
"""

from typing import Optional, Dict, Any, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFrame,
    QTableView, QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt, QSortFilterProxyModel, QSettings, Signal

from .observation_toolbar import ObservationToolbar
from .loading_dialog import LoadingDialog
from .observation_filter_bar import ObservationFilterBar
from ..components.filter_wizard import FilterWizard
from .observation_table_model import ObservationTableModel
from .observation_filter_mixin import ObservationFilterMixin
from .observation_export_mixin import ObservationExportMixin
from .observation_detail_mixin import ObservationDetailMixin
from ..dialogs import RecordDetailDialog, ObservationImportWizard
from ...models.database import get_database
from ...models.observation import ObservationModel, Observation
from ...models.uksi import UKSIModel
from ...themes import theme
from ...core.config import TabColors, Settings, Defaults

# Repository for data access (preferred over model)
try:
    from ...repositories import ObservationRepository
    HAS_REPOSITORY = True
except ImportError:
    HAS_REPOSITORY = False


class ObservationTab(
    ObservationFilterMixin,
    ObservationExportMixin,
    ObservationDetailMixin,
    QWidget
):
    """Main tab for viewing observation data."""

    # Navigation signals - emitted when user wants to go to another tab
    navigate_to_observations = Signal(str)  # species name - stay/filter on this tab
    navigate_to_collection = Signal(str)    # species name - go to Insect Collection tab
    
    # Data change signals - emitted when data is modified
    data_imported = Signal()  # Emitted when import wizard completes successfully

    def __init__(self, parent=None):
        super().__init__(parent)
        self._observation_model: Optional[ObservationModel] = None
        self._uksi_model: Optional[UKSIModel] = None
        self._obs_repo = None  # Repository for data access
        self._current_view_mode = 'normal'  # 'normal' or 'new_species_list'
        self._all_observations: List = []  # Cache all observations for filtering
        self._current_detail_dialog = None  # Track open detail dialog
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Set up the user interface."""
        t = theme()
        self.setStyleSheet(f"background-color: {t.get('background')};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar row (Show Filters toggle, counts, export buttons)
        self.toolbar = ObservationToolbar()
        layout.addWidget(self.toolbar)

        # Filter Wizard (collapsible visual filter builder)
        self.filter_wizard = FilterWizard(
            accent_color=TabColors.OBSERVATION,
            show_save_controls=True
        )
        self.filter_wizard.setVisible(False)  # Hidden by default
        layout.addWidget(self.filter_wizard)

        # Filter bar (collapsible) - hidden by default
        # Filter bar (collapsible) - always starts hidden, settings applied after show
        self.filter_bar = ObservationFilterBar()
        self.filter_bar.setVisible(False)
        layout.addWidget(self.filter_bar)


        # Content area with table
        content = self._create_content_area(t)
        layout.addWidget(content, 1)

    def _create_content_area(self, t) -> QWidget:
        """Create the main content area with table."""
        content = QWidget()
        content.setStyleSheet(f"""
            QWidget {{
                background-color: {TabColors.OBSERVATION_LIGHT};
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_sm')};
            }}
        """)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 16, 16, 16)

        # Table card
        table_card = QFrame()
        table_card.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border-radius: {t.get('radius_lg')};
                border: 1px solid {t.get('border')};
            }}
        """)
        card_layout = QVBoxLayout(table_card)
        card_layout.setContentsMargins(0, 0, 0, 0)

        # Table view
        self.table_view = self._create_table_view(t)
        
        # Table model - proxy connected after first data load for performance
        self.table_model = ObservationTableModel()
        self.sort_proxy = self._create_sort_proxy()
        # Defer: proxy and view connected in _connect_proxy_after_load()
        self._proxy_connected = False
        self.table_model.checked_changed.connect(self._update_selection_count)

        # Default sort applied in _enable_sorting_on_first_view()

        # Set column widths
        self._setup_column_widths()

        card_layout.addWidget(self.table_view)
        content_layout.addWidget(table_card)
        
        return content

    def _create_table_view(self, t) -> QTableView:
        """Create and configure the table view."""
        table_view = QTableView()
        table_view.setStyleSheet(f"""
            QTableView {{
                border: none;
                background-color: {t.get('surface')};
                gridline-color: {t.get('border')};
                alternate-background-color: {t.get('surface_alt')};
            }}
            QTableView::item {{
                padding: 4px 8px;
                border: none;
            }}
            QTableView::item:hover {{
                background-color: {TabColors.OBSERVATION_LIGHT};
            }}
            QTableView::item:selected {{
                background-color: {TabColors.OBSERVATION_LIGHT};
                color: {t.get('text_primary')};
            }}
            QHeaderView::section {{
                background-color: {t.get('surface_alt')};
                padding: 8px;
                border: none;
                border-bottom: 1px solid {t.get('border')};
                font-weight: 600;
            }}
            QHeaderView::section:hover {{
                background-color: {t.get('hover')};
            }}
        """)
        table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table_view.setAlternatingRowColors(True)
        table_view.horizontalHeader().setStretchLastSection(True)
        table_view.verticalHeader().setVisible(False)
        table_view.verticalHeader().setDefaultSectionSize(24)
        table_view.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        table_view.setSortingEnabled(True)
        
        return table_view

    def _create_sort_proxy(self) -> QSortFilterProxyModel:
        """Create sort proxy with fast Python-based sorting."""

        class FastSortProxy(QSortFilterProxyModel):
            """Proxy that caches sort keys for performance."""

            def sort(self, column, order=Qt.SortOrder.AscendingOrder):
                """Override sort to use cached keys for speed."""
                source = self.sourceModel()
                if not source:
                    return super().sort(column, order)

                # Build sort key list once using raw data access
                n = source.rowCount()
                if n == 0:
                    return

                col_key = source._columns[column][0] if column < len(source._columns) else None
                if not col_key:
                    return super().sort(column, order)

                # Extract values directly from cached data (bypass data() calls)
                keys = []
                for i in range(n):
                    record = source._observations[i]
                    if isinstance(record, dict):
                        val = record.get(col_key, '') or ''
                    else:
                        val = getattr(record, col_key, '') or ''
                    keys.append((str(val).lower(), i))

                reverse = (order == Qt.SortOrder.DescendingOrder)
                keys.sort(key=lambda x: x[0], reverse=reverse)

                # Apply the sort order
                source.beginResetModel()
                source._observations = [source._observations[k[1]] for k in keys]
                source.endResetModel()


        return FastSortProxy()


    def _connect_proxy_after_load(self):
        """Connect proxy and view after data is loaded for fast startup."""
        if self._proxy_connected:
            return

        # Connect proxy to model (instant when view not attached)
        self.sort_proxy.setDynamicSortFilter(False)
        self.sort_proxy.setSourceModel(self.table_model)
        self.table_view.setModel(self.sort_proxy)
        self.sort_proxy.setDynamicSortFilter(True)
        # Don't enable sorting yet - data is pre-sorted from SQL
        # Sorting gets enabled when user first views the tab
        self._proxy_connected = True


    def _enable_sorting_on_first_view(self):
        """Enable sorting when tab becomes visible (deferred for performance)."""
        if not hasattr(self, '_sorting_enabled') or not self._sorting_enabled:
            self.table_view.setSortingEnabled(True)
            # Default sort: date descending (newest first)
            for i, col in enumerate(self.table_model.COLUMNS):
                if col[0] == 'date':
                    self.table_view.sortByColumn(i, Qt.SortOrder.DescendingOrder)
                    break
            self._sorting_enabled = True

    def _setup_column_widths(self):
        """Set up column widths from saved settings or defaults."""
        header = self.table_view.horizontalHeader()
        widths = self.table_model.get_column_widths()
        settings = QSettings()
        
        for i, width in enumerate(widths):
            if i < header.count():
                saved_width = settings.value(f"observation_table_columns/col_{i}", width, type=int)
                self.table_view.setColumnWidth(i, saved_width if saved_width > 0 else width)

        # Connect to save column widths when resized
        header.sectionResized.connect(self._save_column_width)

    def _connect_signals(self):
        """Connect UI signals to handlers."""
        # Toolbar signals
        self.toolbar.filters_toggled.connect(self._on_filters_toggled)
        self.toolbar.wizard_toggled.connect(self._on_wizard_toggled)
        
        # Filter Wizard signals
        self.filter_wizard.filters_applied.connect(self._on_wizard_filters_applied)
        self.filter_wizard.filters_reset.connect(self._on_wizard_filters_reset)
        self.toolbar.clear_filters_requested.connect(self.filter_bar.clear_filters)

        # Filter bar signals
        self.filter_bar.data_type_changed.connect(self._on_data_type_changed)
        self.filter_bar.filters_changed.connect(self._on_filters_changed)
        self.filter_bar.special_view_selected.connect(self._on_special_view_selected)

        # Table signals
        self.table_view.doubleClicked.connect(self._on_row_double_clicked)
        self.table_view.viewport().setCursor(Qt.CursorShape.PointingHandCursor)

        # Import signal
        self.toolbar.import_requested.connect(self._on_import_requested)
        self.toolbar.columns_requested.connect(self._on_columns_requested)
        
        # Export signals
        self.toolbar.export_selected_requested.connect(self._on_export_selected)
        self.toolbar.mark_commercial_requested.connect(self._mark_as_commercial)
        self.toolbar.select_all_requested.connect(self._select_all_records)
        self.toolbar.export_requested.connect(self._on_export_all)
        
        # Track checkbox changes for selection count
        self.table_model.dataChanged.connect(self._on_data_changed)

    # =========================================================================
    # Callback Methods (kept in main class for clarity)
    # =========================================================================

    def _on_filters_toggled(self, visible: bool):
        """Handle filter bar visibility toggle."""
        self.filter_bar.setVisible(visible)

    def _on_wizard_toggled(self, visible: bool):
        """Handle filter wizard visibility toggle."""
        self.filter_wizard.setVisible(visible)

    def _on_wizard_filters_applied(self, filters: dict):
        """Handle filter wizard apply button."""
        print(f"[ObservationTab] Wizard filters applied: {filters}")
        
        # Store wizard filters for filtering
        self._wizard_filters = filters
        
        # Apply filters directly to table
        self._apply_wizard_filters(filters)
    
    def _apply_wizard_filters(self, filters: dict):
        """Apply wizard filters to the observation table."""
        if not self._all_observations:
            self._load_data()
            if not self._all_observations:
                return
        
        filtered = self._all_observations.copy()
        
        # What filters use OR logic: show records matching ANY species/order/family
        species_list = filters.get('species', [])
        if isinstance(species_list, str): species_list = [species_list] if species_list else []
        orders = filters.get('taxon_group', [])
        if isinstance(orders, str): orders = [orders] if orders else []
        families = filters.get('family', [])
        if isinstance(families, str): families = [families] if families else []
        
        if species_list or orders or families:
            what_filtered = []
            for obs in filtered:
                if species_list and obs.species_name in species_list:
                    what_filtered.append(obs)
                elif orders and getattr(obs, 'order_name', None) in orders:
                    what_filtered.append(obs)
                elif families and getattr(obs, 'family', None) in families:
                    what_filtered.append(obs)
            filtered = what_filtered
            print(f"[Filter] What (OR): {len(filtered)} records")
        # Where filters use OR logic: show records matching ANY grid_ref/site_name/vice_county
        grid_refs = filters.get('grid_ref', [])
        if isinstance(grid_refs, str): grid_refs = [grid_refs] if grid_refs else []
        sites = filters.get('site_name', [])
        if isinstance(sites, str): sites = [sites] if sites else []
        vcs = filters.get('vice_county', [])
        if isinstance(vcs, str): vcs = [vcs] if vcs else []
        
        # Extract VC numbers for matching
        vc_nums = []
        for vc in vcs:
            if ' - ' in str(vc):
                vc_nums.append(vc.split(' - ')[0])
            else:
                vc_nums.append(str(vc))
        
        has_where_filters = bool(grid_refs or sites or vc_nums)
        
        if has_where_filters:
            where_filtered = []
            for obs in filtered:
                # Check grid ref (prefix match)
                if grid_refs:
                    obs_grid = getattr(obs, 'grid_ref', '') or ''
                    for ref in grid_refs:
                        if obs_grid.upper().startswith(ref.upper()):
                            where_filtered.append(obs)
                            break
                    else:
                        pass  # Continue to check other criteria
                    if obs in where_filtered:
                        continue
                
                # Check site name (partial or exact)
                if sites:
                    obs_site = getattr(obs, 'site_name', '') or ''
                    for site in sites:
                        if site.startswith('~'):
                            if site[1:].lower() in obs_site.lower():
                                where_filtered.append(obs)
                                break
                        else:
                            if obs_site == site:
                                where_filtered.append(obs)
                                break
                    if obs in where_filtered:
                        continue
                
                # Check vice county
                if vc_nums:
                    obs_vc = str(getattr(obs, 'vice_county', '')).split(' - ')[0]
                    if obs_vc in vc_nums:
                        where_filtered.append(obs)
            
            filtered = where_filtered
            print(f"[Filter] Where (OR): {len(filtered)} records - grids:{grid_refs}, sites:{len(sites)}, vcs:{vc_nums}")
            print(f"[Filter] VC filter: {len(filtered)} records")
        

        # Who filters (recorder/determiner) - OR logic with partial match support
        recorders = filters.get('recorder', [])
        if isinstance(recorders, str): recorders = [recorders] if recorders else []
        determiners = filters.get('determiner', [])
        if isinstance(determiners, str): determiners = [determiners] if determiners else []
        
        if recorders or determiners:
            who_filtered = []
            for obs in filtered:
                # Check recorder
                if recorders:
                    obs_recorder = getattr(obs, 'recorder', '') or ''
                    for rec in recorders:
                        if rec.startswith('~'):
                            if rec[1:].lower() in obs_recorder.lower():
                                who_filtered.append(obs)
                                break
                        else:
                            if obs_recorder == rec:
                                who_filtered.append(obs)
                                break
                    if obs in who_filtered:
                        continue
                
                # Check determiner
                if determiners:
                    obs_det = getattr(obs, 'determiner', '') or ''
                    for det in determiners:
                        if det.startswith('~'):
                            if det[1:].lower() in obs_det.lower():
                                who_filtered.append(obs)
                                break
                        else:
                            if obs_det == det:
                                who_filtered.append(obs)
                                break
            filtered = who_filtered
            print(f"[Filter] Who (OR): {len(filtered)} records")

        # How filters (method) - searches method, comment, internal_notes, sample_comment
        methods = filters.get('method', [])
        if isinstance(methods, str): methods = [methods] if methods else []
        
        if methods:
            how_filtered = []
            for obs in filtered:
                obs_method = getattr(obs, 'method', '') or ''
                obs_comment = getattr(obs, 'comment', '') or ''
                obs_internal = getattr(obs, 'internal_notes', '') or ''
                obs_sample = getattr(obs, 'sample_comment', '') or ''
                combined = f"{obs_method} {obs_comment} {obs_internal} {obs_sample}".lower()
                
                for method in methods:
                    if method.startswith('~'):
                        if method[1:].lower() in combined:
                            how_filtered.append(obs)
                            break
                    else:
                        if obs_method == method:
                            how_filtered.append(obs)
                            break
            filtered = how_filtered
            print(f"[Filter] How: {len(filtered)} records")
        # Filter by verification status
        if 'verification_status' in filters and filters['verification_status']:
            statuses = filters['verification_status']
            filtered = [obs for obs in filtered if getattr(obs, 'verification_status', '') in statuses]
            print(f"[Filter] Status filter: {len(filtered)} records")
        
        # Filter by record type
        if 'record_type' in filters and filters['record_type']:
            types = filters['record_type']
            filtered = [obs for obs in filtered if getattr(obs, 'record_type', '') in types]
            print(f"[Filter] Type filter: {len(filtered)} records")
        
        # Filter by date range
        if 'date_from' in filters and filters['date_from']:
            date_from = filters['date_from']
            filtered = [obs for obs in filtered if obs.date and obs.date >= date_from]
        if 'date_to' in filters and filters['date_to']:
            date_to = filters['date_to']
            filtered = [obs for obs in filtered if obs.date and obs.date <= date_to]
        
        # Update table with filtered data
        self.table_model.set_observations(filtered)
        
        # Update status
        total = len(self._all_observations)
        shown = len(filtered)
        if hasattr(self, '_count_species_with_exclusion'):
            species_count = self._count_species_with_exclusion(filtered)
        else:
            species_count = len(set(obs.species_name for obs in filtered if obs.species_name))
        self.toolbar.set_counts(shown, species_count)
        
        print(f"[Filter] Final: {shown}/{total} records displayed")

    def _on_wizard_filters_reset(self):
        """Handle filter wizard reset."""
        self.filter_bar.clear_filters()

    def _save_column_width(self, logical_index: int, old_size: int, new_size: int):
        """Save column width when resized."""
        settings = QSettings()
        settings.setValue(f"observation_table_columns/col_{logical_index}", new_size)

    def _on_data_type_changed(self, data_type: str):
        """Handle data type toggle change from filter bar."""
        if self._current_view_mode == 'normal':
            self._apply_current_filters()

    def _on_data_changed(self, top_left, bottom_right, roles):
        """Handle checkbox changes - update selection count in toolbar."""
        if top_left.column() == 0:
            checked_count = len(self.table_model.get_checked_rows())
            self.toolbar.set_selected_count(checked_count)

    # =========================================================================
    # Import Methods
    # =========================================================================

    def _on_columns_requested(self):
        """Open the column configuration dialog."""
        from ..components.column_selector_dialog import ColumnSelectorDialog
        dialog = ColumnSelectorDialog(
            self.table_model,
            tab_color=TabColors.OBSERVATION,
            parent=self
        )
        dialog.columns_changed.connect(self._on_columns_changed)
        dialog.exec()

    def _on_columns_changed(self):
        """Handle column visibility/order changes."""
        # Rebuild the table with new column settings
        observations = self.table_model._observations.copy()
        self.table_model._update_columns()
        self.table_model.set_observations(observations)
        # Update column widths
        header = self.table_view.horizontalHeader()
        widths = self.table_model.get_column_widths()
        for i, width in enumerate(widths):
            if i < header.count():
                self.table_view.setColumnWidth(i, width)

    def _update_selection_count(self):
        """Update toolbar with current selection count."""
        count = len(self.table_model._checked)
        self.toolbar.set_selected_count(count)

    def _select_all_records(self, select: bool):
        """Select or deselect all visible (filtered) records."""
        if select:
            for proxy_row in range(self.sort_proxy.rowCount()):
                source_index = self.sort_proxy.mapToSource(self.sort_proxy.index(proxy_row, 0))
                self.table_model.setData(source_index, Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
        else:
            self.table_model.set_all_checked(False)
        self._update_selection_count()

    def _mark_as_commercial(self):
        """Mark selected records as commercial."""
        from ..dialogs.mark_commercial_dialog import MarkCommercialDialog
        from PySide6.QtWidgets import QDialog
        from ...models.database import get_database

        checked_ids = []
        for row_idx in sorted(self.table_model._checked):
            if row_idx < len(self.table_model._observations):
                obs = self.table_model._observations[row_idx]
                obs_id = obs.id if hasattr(obs, "id") else obs.get("id")
                if obs_id:
                    checked_ids.append(obs_id)

        if not checked_ids:
            return

        dialog = MarkCommercialDialog(len(checked_ids), parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_commercial_data()
            db = get_database()
            try:
                placeholders = ",".join(["?"] * len(checked_ids))
                set_parts = ", ".join([f"{k} = ?" for k in data.keys()])
                values = list(data.values()) + checked_ids
                db.execute_main_write(
                    f"UPDATE observations SET {set_parts} WHERE id IN ({placeholders})",
                    tuple(values)
                )
                print(f"[ObservationTab] Marked {len(checked_ids)} records as commercial")
                self._load_data()
            except Exception as e:
                print(f"[ObservationTab] Error marking commercial: {e}")

    def _on_import_requested(self):
        """Handle import button click."""
        try:
            from ...services.vc_lookup_service import VCLookupService

            db = get_database()

            vc_service = None
            try:
                vc_service = VCLookupService()
            except Exception as e:
                pass

            wizard = ObservationImportWizard(
                parent=self,
                uksi_model=self._uksi_model,
                vc_service=vc_service,
                db=db,
                observation_model=self._observation_model
            )

            wizard.import_completed.connect(self._on_import_completed)
            result = wizard.exec()

            if result:
                self.refresh()
        except Exception as e:
            import traceback
            traceback.print_exc()

    def _on_import_completed(self, count: int):
        """Handle import completion - refresh this tab and notify others."""
        print(f'[ObservationTab] Imported {count} observations')
        self.refresh()
        self.data_imported.emit()

    # =========================================================================
    # Initialization and Refresh
    # =========================================================================

    def initialize(self, db_path: Optional[str] = None):
        """Initialize the tab with database connection."""
        if hasattr(self, "_obs_initialized") and self._obs_initialized:
            return
        self._obs_initialized = True
        db = get_database()
        self._observation_model = ObservationModel(db)
        self._uksi_model = UKSIModel(db)
        
        # Pass UKSI model to filter wizard for lazy loading
        self.filter_wizard.set_uksi_model(self._uksi_model)

        # Initialize repository (preferred)
        if HAS_REPOSITORY:
            try:
                self._obs_repo = ObservationRepository()
            except Exception as e:
                print(f"[ObservationTab] Could not create repository: {e}")
                self._obs_repo = None

        # Initialize filter bar with database for autocomplete
        self.filter_bar.initialize_with_database(db)

        # Show loading dialog during initial data load
        loading = LoadingDialog("Loading observations...", self)
        loading.show_and_process()
        try:
            self._load_data()
        finally:
            loading.close()

    def refresh(self):
        """Refresh the display with current data."""
        if self._current_view_mode == 'new_species_list':
            self._show_new_species_list()
        else:
            self._load_data()

    def get_selected_observation(self) -> Optional[Dict]:
        """Get the currently selected observation data."""
        indexes = self.table_view.selectedIndexes()
        if not indexes:
            return None

        proxy_index = indexes[0]
        source_index = self.sort_proxy.mapToSource(proxy_index)
        return self.table_model.get_observation_at_row(source_index.row())

    def refresh_display_settings(self):
        """Refresh display settings (e.g., common name visibility, date format)."""
        settings = QSettings()
        show_filters = settings.value(Settings.FILTERS_VISIBLE_OBSERVATIONS, Defaults.FILTERS_VISIBLE_OBSERVATIONS, type=bool)
        self.filter_bar.setVisible(show_filters)
        
        if self.table_model.refresh_common_name_setting():
            header = self.table_view.horizontalHeader()
            widths = self.table_model.get_column_widths()
            for i, width in enumerate(widths):
                if i < header.count():
                    self.table_view.setColumnWidth(i, width)

        self.table_model.refresh_date_format()







