"""
Observation Tab - Orchestrator

Main tab for viewing and managing observation records.
Uses mixins for filter, export, and detail functionality.
"""

from typing import Optional, Dict, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFrame,
    QTableView, QHeaderView, QAbstractItemView
, QHBoxLayout, QLabel, QPushButton)
from PySide6.QtCore import Qt, QSortFilterProxyModel, QSettings, Signal

from .observation_toolbar import ObservationToolbar
from .loading_dialog import LoadingDialog
from .observation_filter_bar import ObservationFilterBar
from ..components.filter_wizard import FilterWizard
from .observation_table_model import ObservationTableModel
from ..components import tick_column
from .observation_filter_mixin import ObservationFilterMixin
from .observation_export_mixin import ObservationExportMixin
from .observation_detail_mixin import ObservationDetailMixin
from ..dialogs import ObservationImportWizard
from ...models.database import get_database
from ...models.observation import ObservationModel
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
    records_changed = Signal()  # records deleted / edited / re-typed here (OBS-10: stats refresh)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._observation_model: Optional[ObservationModel] = None
        self._uksi_model: Optional[UKSIModel] = None
        self._obs_repo = None  # Repository for data access
        self._current_view_mode = 'normal'  # 'normal' or 'new_species_list'
        self._all_observations: List = []  # Cache all observations for filtering
        self._current_detail_dialog = None  # Track open detail dialog
        self._wizard_filters: Dict = {}     # the Filter Wizard's applied filters
        self._wizard_ids = None             # ids they keep (None = no wizard filter)
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
            show_save_controls=True,
            tab_name="observations"
        )
        self.filter_wizard.setVisible(False)  # Hidden by default
        layout.addWidget(self.filter_wizard)

        # Filter bar (collapsible) - hidden by default
        # Filter bar (collapsible) - always starts hidden, settings applied after show
        self.filter_bar = ObservationFilterBar()
        self.filter_bar.setVisible(False)
        layout.addWidget(self.filter_bar)

        # One commercial project pinned from Commercial Reports' "View / edit": kept
        # across reloads (an edit or delete) until cleared here (8 Oct 2026).
        self._project_filter = None          # (project, client) or None
        self._project_banner = QWidget()
        pb = QHBoxLayout(self._project_banner)
        pb.setContentsMargins(12, 5, 12, 5)
        self._project_label = QLabel("")
        self._project_label.setStyleSheet(f"color: {t.get('text_heading')}; font-weight: 600;")
        pb.addWidget(self._project_label, 1)
        _clear = QPushButton("Show all records")
        _clear.setCursor(Qt.CursorShape.PointingHandCursor)
        _clear.clicked.connect(self.clear_project_filter)
        pb.addWidget(_clear)
        self._project_banner.setStyleSheet(
            f"background-color: {t.get('surface_alt')}; border-bottom: 1px solid {t.get('border')};")
        self._project_banner.setVisible(False)
        layout.addWidget(self._project_banner)


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
        self.toolbar.clear_filters_requested.connect(self.clear_all_filters)
        self.filter_bar.clear_all_requested.connect(self.clear_all_filters)

        # Filter bar signals
        self.filter_bar.data_type_changed.connect(self._on_data_type_changed)
        self.filter_bar.filters_changed.connect(self._on_filters_changed)
        self.filter_bar.special_view_selected.connect(self._on_special_view_selected)

        # Table signals
        self.table_view.doubleClicked.connect(self._on_row_double_clicked)
        self.table_view.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        tick_column.install(self.table_view, "accent_observations")   # one tick style, click anywhere

        # Import signal
        self.toolbar.import_requested.connect(self._on_import_requested)
        self.toolbar.columns_requested.connect(self._on_columns_requested)
        
        # Export signals
        self.toolbar.export_selected_requested.connect(self._on_export_selected)
        self.toolbar.mark_commercial_requested.connect(self._mark_as_commercial)
        self.toolbar.delete_selected_requested.connect(self._on_delete_selected)
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
        """Filter Wizard Apply: keep its filters (they survive reloads and combine with the
        filter bar), and show the result.

        10 Oct 2026 (OBS-07, SRCH4, SRCH9): the wizard used to filter the loaded list in
        Python -- up to 54 s (a list-membership test per record), "Specific year" and
        "Notes search" ignored, no species exclusion (Coleoptera 8,174 vs the bar's 8,149)
        and lost on the next reload. Now the shared builder queries the database once."""
        self._wizard_filters = dict(filters or {})
        if getattr(self, "_project_filter", None):    # a wizard search replaces the pin
            self._project_filter = None
            self._project_banner.setVisible(False)
        self._refresh_wizard_ids()
        if not self._all_observations:
            self._load_data()          # loads, then applies bar + wizard
        else:
            self._apply_current_filters(use_cache=True)

    def _refresh_wizard_ids(self):
        """Re-run the wizard's query (after Apply, and after any reload of the data)."""
        filters = getattr(self, "_wizard_filters", None)
        try:
            self._wizard_ids = self.filter_wizard.matching_ids(filters) if filters else None
        except Exception as e:
            print(f"[ObservationTab] Wizard filter failed: {e}")
            self._wizard_ids = None

    def clear_wizard_filters(self):
        """Forget the wizard's filters without reloading (navigation to a species, OBS-08)."""
        self._wizard_filters = {}
        self._wizard_ids = None
        self.filter_wizard.clear_filters()

    def clear_all_filters(self):
        """Toolbar "Clear Filters" and the filter bar's "Clear All" -- one behaviour
        (Wil 10 Oct): the filter bar, the saved-filter choice and the Filter Wizard and
        the pinned project
        are all cleared, then one reload. (Clear Filters cleared the bar only, so a
        wizard filter stayed on and it looked as if nothing happened; on the Insect
        Collection it was not connected at all.) The wizard's own Reset still clears
        the wizard alone."""
        self.clear_wizard_filters()
        if getattr(self, "_project_filter", None):
            self._project_filter = None
            self._project_banner.setVisible(False)
        self.filter_bar.clear_filters()               # applies once

    def show_species(self, species_name: str):
        """Show one species' records with no other filter left over: filter bar,
        Filter Wizard and pinned project all cleared (OBS-08)."""
        self.clear_wizard_filters()
        if getattr(self, "_project_filter", None):
            self._project_filter = None
            self._project_banner.setVisible(False)
        self.filter_bar.set_species_filter(species_name)   # clears the bar, applies once
        self.toolbar.set_filters_visible(True)

    def _on_wizard_filters_reset(self):
        """Wizard Reset: drop the wizard's filters; the filter bar's stay."""
        self._wizard_filters = {}
        self._wizard_ids = None
        self._apply_current_filters(use_cache=True)

    # -- one commercial project, pinned from Commercial Reports ----------------
    def set_project_filter(self, project: str, client: str = ""):
        """Show only this project's commercial records, until cleared; survives reloads."""
        self._project_filter = ((project or "").strip(), (client or "").strip())
        self._project_label.setText(
            f"Project: {project or '(no project)'}" + (f"  \u2014  {client}" if client else "")
            + "   (commercial records only)")
        self._project_banner.setVisible(True)
        if not self._all_observations:
            self._load_data()
        else:
            self._apply_current_filters()

    def clear_project_filter(self):
        self._project_filter = None
        self._project_banner.setVisible(False)
        self._apply_current_filters()

    def _save_column_width(self, logical_index: int, old_size: int, new_size: int):
        """Save column width when resized."""
        settings = QSettings()
        settings.setValue(f"observation_table_columns/col_{logical_index}", new_size)

    def _on_data_type_changed(self, data_type: str):
        """Handle data type toggle change from filter bar."""
        if self._current_view_mode == 'normal':
            self._apply_current_filters()
        elif self._current_view_mode == 'new_species_list':
            self._show_new_species_list()          # follows Personal/Commercial (OBS-24)

    def _on_data_changed(self, top_left, bottom_right, roles):
        """Handle checkbox changes - update selection count in toolbar."""
        if top_left.column() == 0:
            self.toolbar.set_selected_count(self.table_model.checked_count())

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
        self.toolbar.set_selected_count(self.table_model.checked_count())

    def _select_all_records(self, select: bool):
        """Select or deselect all visible (filtered) records."""
        # The model holds only the filtered records (filters replace its list), so
        # "all" here is all that are shown
        self.table_model.set_all_checked(bool(select))
        self._update_selection_count()

    def _mark_as_commercial(self):
        """Mark selected records as commercial."""
        from ..dialogs.mark_commercial_dialog import MarkCommercialDialog
        from PySide6.QtWidgets import QDialog
        from ...models.database import get_database

        # The ticked records by id -- ticks follow their records through a sort (OBS-01)
        checked_ids = self.table_model.get_checked_ids()

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
                self.records_changed.emit()
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








    def _on_delete_selected(self):
        """Delete the ticked observations after a confirmation that names them.

        Acts on the ticked records by id, so a sort between ticking and deleting
        cannot change which records go (OBS-01). observatum.db is backed up first
        (a kept, named copy); if that fails nothing is deleted.
        """
        from PySide6.QtWidgets import QMessageBox
        from ...models.database import get_database
        from .checked_records import describe_records

        checked = [o for o in self.table_model.get_checked_observations() if o.get("id")]
        checked_ids = [o.get("id") for o in checked]
        if not checked_ids:
            QMessageBox.information(self, "Delete Selected", "No records are selected.")
            return

        count = len(checked_ids)
        reply = QMessageBox.warning(
            self,
            "Delete Selected",
            f"Permanently delete {count} observation{'s' if count != 1 else ''}?\n\n"
            f"{describe_records(checked)}\n\n"
            "A backup of the database is taken first. This cannot be undone here.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            from shared.backup_service import backup_main_only
            backed_up = backup_main_only("pre-delete")
        except Exception as e:
            print(f"[ObservationTab] pre-delete backup unavailable: {e}")
            backed_up = False
        if not backed_up:
            QMessageBox.critical(self, "Delete Not Done",
                                 "The backup before deleting failed, so nothing has been deleted.")
            return

        db = get_database()
        try:
            placeholders = ",".join(["?"] * len(checked_ids))
            db.execute_main_write(
                f"DELETE FROM observations WHERE id IN ({placeholders})",
                tuple(checked_ids),
            )
            print(f"[ObservationTab] Deleted {count} records: ids {checked_ids[:20]}")
            self.table_model.set_all_checked(False)
            self._load_data()
            self._update_selection_count()
            self.records_changed.emit()
        except Exception as e:
            print(f"[ObservationTab] Error deleting: {e}")
            QMessageBox.critical(self, "Delete Failed", f"Could not delete records:\n{e}")
