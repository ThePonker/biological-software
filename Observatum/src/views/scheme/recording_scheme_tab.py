"""Recording Scheme Tab - Orchestrator

Main tab for viewing Longhorn Beetle Recording Scheme data.
Uses Model/View pattern matching Observation Data tab structure.
"""
from typing import Optional, Dict, List
import paths

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFrame, QTableView,
    QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt, QSortFilterProxyModel, QSettings, Signal, QTimer

from .scheme_toolbar import SchemeToolbar
from .scheme_filter_bar import SchemeFilterBar
from .scheme_record_model import SchemeRecordModel
from ..components import tick_column
from .scheme_data_worker import SchemeDataWorker
from ..dialogs import SchemeRecordDetailDialog  # CHANGED: moved to dialogs folder
from ..dialogs.scheme_import_wizard import SchemeImportWizard
from ...models.database import get_database
from ...themes import theme
from ...core.config import TabColors, Settings
from ..components.filter_wizard import FilterWizard




class FastSortProxy(QSortFilterProxyModel):
    """Proxy that sorts using Python sorted() instead of Qt lessThan() callbacks.

    With 98k rows, Qt's default sort triggers ~600k+ Python lessThan() calls.
    This extracts values once and uses Python's built-in sorted() instead.
    """

    def sort(self, column, order=Qt.SortOrder.AscendingOrder):
        """Override sort to use cached keys for speed."""
        source = self.sourceModel()
        if not source or not hasattr(source, '_records') or not hasattr(source, '_columns'):
            return super().sort(column, order)

        n = source.rowCount()
        if n == 0:
            return

        col_key = source._columns[column][0] if column < len(source._columns) else None
        if not col_key or col_key == 'checkbox':
            return super().sort(column, order)

        # Extract values directly from cached data (bypass data() calls)
        is_date = col_key == 'date'
        keys = []
        for i in range(n):
            record = source._records[i]
            val = record.get(col_key, '') or ''
            sort_val = str(val).lower()
            # Convert DD/MM/YYYY to YYYY-MM-DD for chronological sort
            if is_date and '/' in sort_val:
                parts = sort_val.split('/')
                if len(parts) == 3 and len(parts[2]) == 4:
                    sort_val = f'{parts[2]}-{parts[1]}-{parts[0]}'
            keys.append((sort_val, i))

        reverse = (order == Qt.SortOrder.DescendingOrder)
        keys.sort(key=lambda x: x[0], reverse=reverse)

        # Apply the sort order
        source.beginResetModel()
        source._records = [source._records[k[1]] for k in keys]
        source.endResetModel()



class RecordingSchemeTab(QWidget):
    """Main tab for viewing Recording Scheme data."""
    
    # Navigation signals from record detail dialog
    navigate_to_observations = Signal(str)  # species name
    navigate_to_collection = Signal(str)    # species name
    records_changed = Signal()              # a record was edited or deleted here (OBS-04/10)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._initialized = False
        self._current_view = 'records'
        self._data_worker = None
        self._old_workers = []           # replaced loads still finishing (cancelled)
        self._poll_timer = None
        self._loading = False
        self._main_db_path = None
        self._preload_started = False
        self._preload_records = None
        self._db = None
        self._all_records: List[Dict] = []  # Cache all records for filtering
        # Results the poll timer has taken from the worker but not yet shown, and the
        # last load error. _worker_results was read in initialize() but never defined,
        # so startup could stop on the splash screen (review OBS-02 / SRCH20b).
        self._worker_results = None
        self._load_error: Optional[str] = None
        self._wizard_filters: Dict = {}     # the Filter Wizard's applied filters (kept)
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        t = theme()
        self.setStyleSheet(f"background-color: {t.get('background')};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # View selector row (full width with counts, export, import)
        self.toolbar = SchemeToolbar()
        layout.addWidget(self.toolbar)
        
        # Filter bar row (full width) - visibility from settings
        self.filter_bar = SchemeFilterBar()
        # Set initial visibility from settings
        from PySide6.QtCore import QSettings
        # Filter bar - always starts hidden, settings applied after show
        self.filter_bar.setVisible(False)
        layout.addWidget(self.filter_bar)

        # Filter Wizard (hidden by default)
        self.filter_wizard = FilterWizard(
            accent_color=TabColors.RECORDING_SCHEME,
            tab_name="recording_scheme",
            parent=self
        )
        self.filter_wizard.setVisible(False)
        layout.addWidget(self.filter_wizard)

        # Content area with table - use tab accent light for background
        content = QWidget()
        content.setStyleSheet(f"""
            QWidget {{
                background-color: {TabColors.RECORDING_SCHEME_LIGHT};
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
        
        # Table view (Model/View pattern)
        self.table_view = QTableView()
        self._apply_table_style()
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.verticalHeader().setDefaultSectionSize(24)  # Fixed row height
        self.table_view.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        
        # Table model - proxy connected after first data load for performance
        self.table_model = SchemeRecordModel()
        self.sort_proxy = FastSortProxy()
        # Defer: proxy and view connected in _connect_proxy_after_load()
        self._proxy_connected = False

        # Set column widths
        header = self.table_view.horizontalHeader()
        widths = self.table_model.get_column_widths()
        for i, width in enumerate(widths):
            if i < header.count():
                # Try to load saved width, fall back to default
                settings = QSettings()
                saved_width = settings.value(f"scheme_table_columns/col_{i}", width, type=int)
                self.table_view.setColumnWidth(i, saved_width if saved_width > 0 else width)
        
        # Connect to save column widths when resized
        header.sectionResized.connect(self._save_column_width)
        
        card_layout.addWidget(self.table_view)
        content_layout.addWidget(table_card)
        
        layout.addWidget(content, 1)
    
    def _apply_table_style(self):
        """Apply table styling using theme tokens."""
        t = theme()
        self.table_view.setStyleSheet(f"""
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
                background-color: {TabColors.RECORDING_SCHEME_LIGHT};
            }}
            QTableView::item:selected {{
                background-color: {TabColors.RECORDING_SCHEME_LIGHT};
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
    
    def _connect_signals(self):
        self.toolbar.filters_toggled.connect(self._on_filters_toggled)
        self.toolbar.clear_filters_requested.connect(self.clear_all_filters)
        self.filter_bar.clear_all_requested.connect(self.clear_all_filters)
        self.toolbar.wizard_toggled.connect(self._on_wizard_toggled)
        self.filter_bar.filters_changed.connect(self._on_filters_changed)
        self.filter_wizard.filters_applied.connect(self._on_wizard_filters_applied)
        self.filter_wizard.filters_reset.connect(self._on_wizard_filters_reset)
        
        # Connect table double-click to show detail dialog
        self.table_view.doubleClicked.connect(self._on_row_double_clicked)
        self.table_view.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        tick_column.install(self.table_view, "accent_scheme")   # one tick style, click anywhere
        self.toolbar.import_requested.connect(self._on_import_requested)
        self.toolbar.columns_requested.connect(self._on_columns_requested)
        self.toolbar.export_requested.connect(self._on_export_all)
        self.toolbar.export_selected_requested.connect(self._on_export_selected)
    
    def _on_filters_toggled(self, visible: bool):
        """Handle filter bar visibility toggle."""
        self.filter_bar.setVisible(visible)
    
    def _on_filters_changed(self, filters):
        self._load_data(filters)
    
    def _on_row_double_clicked(self, index):
        """Handle row double-click to show detail dialog."""
        # Map from proxy index to source model index
        source_index = self.sort_proxy.mapToSource(index)
        record = self.table_model.get_record_at_row(source_index.row())
        if record:
            # Load species profile
            profile_text = self._load_species_profile(record)
            
            dialog = SchemeRecordDetailDialog(
                record=record,
                parent=self,
                profile_text=profile_text
            )
            
            # Store reference for profile updates
            self._current_detail_dialog = dialog
            
            dialog.profile_requested.connect(self._on_profile_requested)
            dialog.navigate_to_observations.connect(self._on_navigate_to_observations)
            dialog.navigate_to_collection.connect(self._on_navigate_to_collection)
            self._wire_edit_delete(dialog)
            dialog.exec()
            
            self._current_detail_dialog = None

    def _wire_edit_delete(self, dialog):
        """Edit / Delete in the record detail dialog (they did nothing: OBS-04)."""
        from .scheme_record_actions import wire_scheme_detail
        wire_scheme_detail(dialog, self, self._after_record_change,
                           uksi_model=getattr(self, '_uksi_model', None))

    def _after_record_change(self):
        self.refresh()
        self.records_changed.emit()

    def _load_species_profile(self, record: dict) -> str:
        """Profile text for display -- via the one shared reader (TVK, else name)."""
        species_name = record.get('species') or record.get('species_name', '')
        tvk = record.get('species_tvk') or record.get('tvk')
        if not (species_name or tvk):
            return None
        try:
            from shared.species_accounts import get_preview_text
            return get_preview_text(tvk, species_name)
        except Exception as e:
            print(f"[RecordingSchemeTab] Error loading profile: {e}")
            return None
    
    def _on_profile_requested(self, record: dict):
        """Handle profile view/create request from detail dialog."""
        from ..home.species_profile_dialog import SpeciesProfileDialog
        
        species_data = {
            'scientific_name': record.get('species') or record.get('species_name'),
            'species_name': record.get('species') or record.get('species_name'),
            'tvk': record.get('species_tvk') or record.get('tvk'),
            'common_name': record.get('common') or record.get('common_name'),
        }
        
        profile_dialog = SpeciesProfileDialog(species_data, self)
        
        # Connect with lambda to capture detail dialog reference
        detail_dialog = getattr(self, '_current_detail_dialog', None)
        if detail_dialog:
            profile_dialog.profile_saved.connect(lambda text: detail_dialog.update_profile(text))
        
        profile_dialog.exec()
    
    def _on_profile_saved(self, profile_text: str):
        """Handle profile saved - refresh the current view."""
        self.refresh()
    
    def _save_column_width(self, logical_index: int, old_size: int, new_size: int):
        """Save column width when resized."""
        settings = QSettings()
        settings.setValue(f"scheme_table_columns/col_{logical_index}", new_size)
    

    def _on_wizard_toggled(self, visible: bool):
        """Handle filter wizard visibility toggle."""
        self.filter_wizard.setVisible(visible)

    def _on_wizard_filters_applied(self, filters: dict):
        """Filter Wizard Apply: kept, and added to every load with the filter bar's filters.

        10 Oct 2026 (OBS-06, SRCH1-3): this kept only the first chip of four keys, left
        the "~" partial marker in (site "Wood": 0 of 16,645) and compared a VC name with
        vc_number; year, family, determiner, method, notes and status were ignored. The
        shared builder now turns every chip into SQL (services/filter_builder)."""
        self._wizard_filters = dict(filters or {})
        self._load_data(self._bar_filters())

    def _on_wizard_filters_reset(self):
        """Wizard Reset: drop the wizard's filters; the filter bar's stay."""
        self._wizard_filters = {}
        self._load_data(self._bar_filters())

    def clear_wizard_filters(self):
        """Forget the wizard's filters without reloading (navigation, OBS-08)."""
        self._wizard_filters = {}
        self.filter_wizard.clear_filters()

    def clear_all_filters(self):
        """Toolbar "Clear Filters" and the filter bar's "Clear All" -- one behaviour
        (Wil 10 Oct): the filter bar, the saved-filter choice and the Filter Wizard
        are all cleared, then one reload. (Clear Filters cleared the bar only, so a
        wizard filter stayed on and it looked as if nothing happened; on the Insect
        Collection it was not connected at all.) The wizard's own Reset still clears
        the wizard alone."""
        self.clear_wizard_filters()
        self.filter_bar.clear_filters()               # one load (filters_changed)

    def _bar_filters(self) -> dict:
        """The filter bar's current filters (none until the tab is set up)."""
        return self.filter_bar.get_filters() if self._initialized else {}


    def _load_data(self, filters=None):
        """Load scheme records in background thread."""
        if not self._db and not self._preload_started:
            return

        # A load still running is replaced: stop its query and ignore its results.
        # (It used to quit() + wait(2000): quit() does not stop run(), so every change
        # froze the window for up to 2 s and the old load kept going -- speed, 10 Oct 2026)
        old = self._data_worker
        if old is not None and old.isRunning():
            if hasattr(old, 'cancel'):
                old.cancel()
            self._old_workers.append(old)        # keep a reference until its thread ends
        self._old_workers = [w for w in self._old_workers if w.isRunning()]

        # Show loading overlay
        self._loading = True
        if hasattr(self, "_stack"):
            self._stack.setCurrentIndex(1)

        # Resolve db path for thread-safe connection
        db_path = self._main_db_path
        if not db_path:
            db_path = str(paths.OBSERVATUM_DB)

        # Inject scheme family scope from settings
        from PySide6.QtCore import QSettings
        filters = dict(filters or {})
        scheme_fam = QSettings().value(Settings.SCHEME_FAMILIES, "", str).strip()
        if scheme_fam:
            filters['_scheme_families'] = [f.strip() for f in scheme_fam.split(',') if f.strip()]
        # The Filter Wizard's filters, on every load until Reset (SRCH9: lost on reload)
        if self._wizard_filters:
            from ...services.filter_builder import build_where
            sql, params = build_where('recording_scheme', self._wizard_filters)
            if sql:
                filters['_wizard_sql'] = (sql, params)
        filters = filters or None

        # Start background worker
        self._data_worker = SchemeDataWorker(db_path, filters, self)
        # Store results via signal for thread safety, but poll for completion
        self._data_worker.error.connect(self._on_data_error)
        self._data_worker.start()

        # Poll every 50 ms instead of waiting for queued signal delivery (one timer:
        # a new one per load left the old ones running)
        if self._poll_timer is None:
            self._poll_timer = QTimer(self)
            self._poll_timer.setInterval(50)
            self._poll_timer.timeout.connect(self._check_worker_done)
        self._poll_timer.start()

    def _check_worker_done(self):
        """Poll timer - check if worker results are ready via threading.Event."""
        if not self._data_worker or not self._data_worker.results_ready.is_set():
            return
        # Results ready - stop polling and process immediately
        self._poll_timer.stop()
        results = self.take_worker_results()
        if results is None:
            err = getattr(self._data_worker, "error_message", None)
            if err:
                self._on_data_error(err)
            return
        self._on_data_loaded(*results)

    def take_worker_results(self):
        """(records, species_count) from the finished worker, once; else None."""
        w = self._data_worker
        if not w or not w.results_ready.is_set() or w.results is None:
            return None
        results, w.results = w.results, None
        return results

    def worker_error(self) -> Optional[str]:
        """The error the last load raised, if it has finished with one."""
        w = self._data_worker
        if w and w.results_ready.is_set():
            return getattr(w, "error_message", None)
        return None

    def _on_data_loaded(self, records, species_count):
        """Handle data loaded from background worker."""
        self._loading = False

        # If tab hasn't been visited yet, stash the data for initialize()
        if not self._initialized:
            self._preload_records = (records, species_count)
            return

        # Tab is already visible - apply data immediately
        self.table_model.set_records(records)

        self._connect_proxy_after_load()

        self._enable_sorting_on_first_view()

        self.toolbar.set_counts(len(records), species_count)

        # The wizard's lists come from this table: re-read them on the next dialog
        if hasattr(self, 'filter_wizard'):
            self.filter_wizard.refresh_tab_values()

        if hasattr(self, '_stack'):
            self._stack.setCurrentIndex(0)


    def _on_data_error(self, error_msg):
        """Handle error from background worker: say so, once, rather than show an empty table."""
        self._loading = False
        if self._load_error == error_msg:
            return                          # the signal and the poll timer both report it
        self._load_error = error_msg
        print(f"[RecordingSchemeTab] Could not load records: {error_msg}")
        if self._initialized and self.isVisible():
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Recording Scheme",
                                f"The Recording Scheme records could not be loaded:\n\n{error_msg}")


    def _connect_proxy_after_load(self):
        """Connect proxy and view after data is loaded for fast startup."""
        if self._proxy_connected:
            return
        # Hide table view so Qt skips expensive layout calculations
        was_visible = self.table_view.isVisible()
        if was_visible:
            self.table_view.setVisible(False)
        self.sort_proxy.setDynamicSortFilter(False)
        self.sort_proxy.setSourceModel(self.table_model)
        self.table_view.setModel(self.sort_proxy)
        self.sort_proxy.setDynamicSortFilter(True)
        self._proxy_connected = True
        if was_visible:
            self.table_view.setVisible(True)

    def _enable_sorting_on_first_view(self):
        """Connect header clicks to FastSortProxy.sort() directly.

        We avoid setSortingEnabled(True) because Qt triggers an immediate
        internal sort on all rows through the proxy (5.5s with 98k rows).
        Instead, we connect the header sectionClicked signal so sorting
        only happens when the user actually clicks a column header,
        and always goes through our fast Python-based sort.
        """
        if not hasattr(self, "_sorting_enabled") or not self._sorting_enabled:
            self._sorting_enabled = True
            self._sort_order = {}  # track toggle state per column
            header = self.table_view.horizontalHeader()
            header.setSectionsClickable(True)
            header.setSortIndicatorShown(True)
            header.sectionClicked.connect(self._on_header_sort_clicked)

    def _on_header_sort_clicked(self, logical_index: int):
        """Handle column header click for sorting."""
        from PySide6.QtCore import Qt
        # Toggle sort order for this column
        current = self._sort_order.get(logical_index, Qt.SortOrder.DescendingOrder)
        new_order = Qt.SortOrder.AscendingOrder if current == Qt.SortOrder.DescendingOrder else Qt.SortOrder.DescendingOrder
        self._sort_order[logical_index] = new_order
        # Update visual indicator
        self.table_view.horizontalHeader().setSortIndicator(logical_index, new_order)
        # Call our FastSortProxy.sort() directly
        self.sort_proxy.sort(logical_index, new_order)

    def get_selected_record(self) -> Optional[Dict]:
        """Get the currently selected record data."""
        indexes = self.table_view.selectedIndexes()
        if not indexes:
            return None
        
        # Map from proxy index to source model index
        proxy_index = indexes[0]
        source_index = self.sort_proxy.mapToSource(proxy_index)
        return self.table_model.get_record_at_row(source_index.row())
    
    def _on_navigate_to_observations(self, species_name: str):
        """Forward navigation to observations tab."""
        self.navigate_to_observations.emit(species_name)

    def _on_navigate_to_collection(self, species_name: str):
        """Forward navigation to collection tab."""
        self.navigate_to_collection.emit(species_name)

    def clear_single_record_filter(self):
        """Clear the single record filter and reload all data."""
        if hasattr(self, "_showing_single_record") and self._showing_single_record:
            self._showing_single_record = False
            if hasattr(self, "filter_bar"):
                self.filter_bar.clear_filters()
            self._load_data()

    def start_preload(self, db_path: str):
        """Start loading data in background immediately after app startup.

        Called from main_window._initialize_services() so data is ready
        before the user clicks the tab. Does NOT initialize filter bar
        or other UI elements - that happens in initialize().
        """
        self._main_db_path = db_path
        self._preload_started = True
        self._load_data()

    def initialize(self, db_path=None, uksi_path=None):
        """Initialize with database connection (called on first tab visit)."""
        if self._initialized:
            return
        self._initialized = True
        self._db = get_database()
        self._main_db_path = db_path or self._main_db_path

        # Initialize filter bar with database for autocomplete
        self.filter_bar.initialize_with_database(self._db)

        # If pre-load already delivered data, use it immediately
        if self._preload_records is not None:
            records, species_count = self._preload_records
            self._preload_records = None
            self.table_model.set_records(records)
            self._connect_proxy_after_load()
            self._enable_sorting_on_first_view()
            self.toolbar.set_counts(len(records), species_count)
            if hasattr(self, 'filter_wizard'):
                self.filter_wizard.refresh_tab_values()
            if hasattr(self, "_stack"):
                self._stack.setCurrentIndex(0)
            return

        # Worker finished but the poll timer has not collected yet: take the results now
        results = self._worker_results or self.take_worker_results()
        self._worker_results = None
        if results is not None:
            if getattr(self, "_poll_timer", None):
                self._poll_timer.stop()
            self._on_data_loaded(*results)
            return

        # Worker finished with an error: the window still opens; the error is shown
        # (main.py at startup) and the table stays empty until a refresh
        if self.worker_error():
            return

        # If worker is still running, just wait for it (polling timer is active)
        if self._data_worker and self._data_worker.isRunning():
            return

        # No preload at all, load now
        self._load_data()

    def refresh(self):
        """Refresh the display, keeping the filter bar's and the wizard's filters."""
        self._load_data(self._bar_filters())
    
    def refresh_display_settings(self):
        """Refresh display settings when settings change."""
        # Refresh filter bar visibility from settings
        from PySide6.QtCore import QSettings
        from ...core.config import Settings, Defaults
        settings = QSettings()
        show_filters = settings.value(Settings.FILTERS_VISIBLE_RECORDING_SCHEME, Defaults.FILTERS_VISIBLE_RECORDING_SCHEME, type=bool)
        self.filter_bar.setVisible(show_filters)
        
        # Sync toolbar button state with filter visibility
        self.toolbar.set_filters_visible(show_filters)
        
        # Refresh common name column visibility
        if self.table_model.refresh_common_name_setting():
            # Column structure changed, update column widths
            header = self.table_view.horizontalHeader()
            widths = self.table_model.get_column_widths()
            for i, width in enumerate(widths):
                if i < header.count():
                    self.table_view.setColumnWidth(i, width)
        
        # Refresh date format
        self.table_model.refresh_date_format()
    
    def apply_theme(self):
        """Apply current theme to all components."""
        t = theme()
        
        self.setStyleSheet(f"background-color: {t.get('background')};")
        
        # Apply to child components
        self.toolbar.apply_theme()
        self.filter_bar.apply_theme()
        
        # Re-apply table styling
        self._apply_table_style()

    def _on_columns_requested(self):
        """Open the column configuration dialog."""
        from ..components.column_selector_dialog import ColumnSelectorDialog
        dialog = ColumnSelectorDialog(
            self.table_model,
            tab_color=TabColors.RECORDING_SCHEME,
            parent=self
        )
        dialog.columns_changed.connect(self._on_columns_changed)
        dialog.exec()

    def _on_columns_changed(self):
        """Handle column visibility/order changes."""
        # Rebuild the table with new column settings
        records = self.table_model._records.copy()
        self.table_model._update_columns()
        self.table_model.set_records(records)
        # Update column widths
        header = self.table_view.horizontalHeader()
        widths = self.table_model.get_column_widths()
        for i, width in enumerate(widths):
            if i < header.count():
                self.table_view.setColumnWidth(i, width)

    def _on_export_all(self):
        """Export all recording scheme records to CSV."""
        # (9 Oct 2026: imported ..models.database, which does not exist, and called
        # db.execute, which Database does not have -- both exports failed on first use)
        db = get_database()
        if not db:
            return
        rows = [dict(r) for r in db.execute_main(
            "SELECT * FROM recording_scheme ORDER BY taxonomic_sort_key, species_name")]
        if not rows:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "No Data", "No recording scheme records to export.")
            return
        self._export_rs_records(rows, "Export Recording Scheme")

    def _on_export_selected(self):
        """Export the ticked recording scheme records to CSV (or the highlighted row if none)."""
        db = get_database()
        if not db:
            return
        # The ticked records by id: a sort between ticking and exporting cannot change
        # which records go (OBS-01; before 9 Oct 2026 this used the highlighted row)
        ids = list(self.table_model.get_checked_ids())
        selection = [] if ids else self.table_view.selectionModel().selectedRows()
        if not ids and not selection:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "No Selection", "Tick at least one row to export.")
            return
        for index in selection:
            # The view shows sort_proxy once connected; mapping through a non-existent
            # proxy_model exported the wrong rows whenever the table was sorted (8 Oct 2026)
            source_index = self.sort_proxy.mapToSource(index) if self._proxy_connected else index
            row_data = self.table_model.get_record_at_row(source_index.row())
            if row_data and 'id' in row_data:
                ids.append(row_data['id'])
        if not ids:
            return
        rows = []
        for i in range(0, len(ids), 900):                # stay under SQLite's variable limit
            chunk = ids[i:i + 900]
            placeholders = ",".join(["?" for _ in chunk])
            rows.extend(dict(r) for r in db.execute_main(
                f"SELECT * FROM recording_scheme WHERE id IN ({placeholders})", tuple(chunk)))
        rows.sort(key=lambda r: (str(r.get("taxonomic_sort_key") or ""), str(r.get("species_name") or "")))
        self._export_rs_records(rows, "Export Selected Records")

    def _export_rs_records(self, rows, dialog_title: str):
        """Common export logic for recording scheme records."""
        import os, csv
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from PySide6.QtCore import QSettings
        from ...core.config import Settings

        export_columns = [
            ("species_name", "Species"),
            ("common_name", "Common Name"),
            ("species_tvk", "TVK"),
            ("order_name", "Order"),
            ("family", "Family"),
            ("superfamily", "Superfamily"),
            ("subfamily", "Subfamily"),
            ("taxon_group", "Taxon Group"),
            ("taxon_rank", "Rank"),
            ("date", "Date"),
            ("grid_ref", "Grid Ref"),
            ("site_name", "Site Name"),
            ("vice_county", "Vice County"),
            ("vc_number", "VC Number"),
            ("latitude", "Latitude"),
            ("longitude", "Longitude"),
            ("recorder", "Recorder"),
            ("determiner", "Determiner"),
            ("sex", "Sex"),
            ("stage", "Stage"),
            ("quantity", "Quantity"),
            ("method", "Sample Method"),
            ("comment", "Comment"),
            ("verification_status", "Verification Status"),
            ("source", "Source"),
            ("dataset_name", "Dataset"),
            ("import_notes", "Import Notes"),
        ]

        settings = QSettings()
        default_path = settings.value(Settings.EXPORT_DEFAULT_PATH, "")
        default_file = (
            os.path.join(default_path, "recording_scheme_export.csv")
            if default_path else "recording_scheme_export.csv"
        )

        file_path, _ = QFileDialog.getSaveFileName(
            self, dialog_title, default_file,
            "CSV Files (*.csv);;All Files (*)"
        )
        if not file_path:
            return

        try:
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow([col[1] for col in export_columns])
                for row in rows:
                    rec = row if isinstance(row, dict) else dict(row)   # sqlite3.Row -> values
                    writer.writerow([
                        '' if rec.get(col_key) is None else rec.get(col_key)
                        for col_key, _ in export_columns
                    ])
            QMessageBox.information(
                self, "Export Complete",
                f"Exported {len(rows)} records to:\n{file_path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export:\n{str(e)}")

    def _on_import_requested(self):
        """Handle import button click - open import wizard."""
        db = self._db or get_database()
        
        uksi_model = None
        try:
            from ...models.uksi import UKSIModel
            uksi_model = UKSIModel(db)
        except Exception as e:
            print(f"Warning: Could not initialize UKSI model: {e}")
        
        vc_service = None
        try:
            from ...services.vc_lookup_service import VCLookupService
            vc_service = VCLookupService()
        except Exception:
            pass
        
        wizard = SchemeImportWizard(
            parent=self,
            uksi_model=uksi_model,
            vc_service=vc_service,
            db=db,
        )
        wizard.import_completed.connect(self._on_import_completed)
        wizard.exec()

    def _on_import_completed(self, count: int):
        """Handle import completion - refresh the table (filters kept)."""
        self.refresh()

    def show_record_by_id(self, record_id: int):
        """Show a specific record by its ID - used for navigation from county firsts."""
        if not self._db:
            return
        
        try:
            # Query the specific record
            query = "SELECT * FROM recording_scheme WHERE id = ?"
            results = self._db.execute_main(query, (record_id,))
            
            if results:
                row = results[0]
                # Build record dict from the row
                record = dict(row)
                record['species'] = record.get('species_name', '')
                record['common'] = record.get('common_name', '')
                record['location'] = record.get('site_name', '')
                record['gridRef'] = record.get('grid_ref', '')
                record['vc'] = record.get('vc_number', '')
                record['verification'] = record.get('verification_status', '')
                
                # Filter table to show only this record
                self.table_model.set_records([record])
                self.toolbar.set_counts(1, 1)
                
                # Show filter bar with indication that we're viewing a single record
                if hasattr(self, 'filter_bar'):
                    self.filter_bar.setVisible(True)
                    if hasattr(self, 'toolbar'):
                        self.toolbar.filter_btn.setChecked(True)
                
                # Open the detail dialog for this record
                dialog = SchemeRecordDetailDialog(record, parent=self)
                dialog.profile_requested.connect(self._on_profile_requested)
                dialog.navigate_to_observations.connect(self._on_navigate_to_observations)
                dialog.navigate_to_collection.connect(self._on_navigate_to_collection)
                self._wire_edit_delete(dialog)
                dialog.exec()
        except Exception as e:
            print(f"Error showing record {record_id}: {e}")