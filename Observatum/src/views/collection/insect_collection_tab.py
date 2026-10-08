"""Insect Collection Tab - Orchestrator

Main tab for viewing specimen collection data.
Uses standardized table layout matching Observation Data tab.
Mixins provide sidebar, data-loading, and export functionality.
"""
from typing import Optional, Any
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFrame, QTableView, QSplitter,
    QHeaderView, QAbstractItemView, QMessageBox,
)
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtCore import Qt, QSettings, Signal

from .collection_toolbar import CollectionToolbar
from .collection_filters import CollectionFilterBar
from .specimen_table_model import SpecimenTableModel
from .ic_sidebar_mixin import ICSidebarMixin
from .ic_data_mixin import ICDataMixin
from .ic_export_mixin import ICExportMixin
from ..dialogs import AddSpecimenDialog, SpecimenImportWizard
from ...models.database import get_database
from ...models.specimen import SpecimenModel
from ...models.uksi import UKSIModel
from ...services.vc_lookup_service import VCLookupService
from ...themes import theme
from ...core.config import TabColors, Settings, Defaults
from ..components.filter_wizard import FilterWizard

# Repository for data access (preferred over model)
try:
    from ...repositories import SpecimenRepository
    HAS_REPOSITORY = True
except ImportError:
    HAS_REPOSITORY = False


class InsectCollectionTab(ICSidebarMixin, ICDataMixin, ICExportMixin, QWidget):
    """Main tab for viewing specimen collection data."""

    # Navigation signals
    navigate_to_observations = Signal(str)
    navigate_to_collection = Signal(str)
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._specimen_model: Optional[SpecimenModel] = None
        self._specimen_repo = None
        self._extra_filters: dict = {}
        self._uksi_model: Optional[UKSIModel] = None
        self._vc_service: Optional[VCLookupService] = None
        self._current_view_mode = 'normal'
        self._current_detail_dialog = None
        self._sidebar_visible = False
        self._taxonomic_sidebar = None
        self._family_notes_repo = None
        self._setup_ui()
        self._connect_signals()

    # ── UI setup ────────────────────────────────────────────────────

    def _setup_ui(self):
        t = theme()

        self.setStyleSheet(f"background-color: {t.get('background')};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        self.toolbar = CollectionToolbar()
        layout.addWidget(self.toolbar)

        # Filters — hidden by default
        self.filters = CollectionFilterBar()
        self.filters.setVisible(False)
        layout.addWidget(self.filters)

        # Filter Wizard (hidden by default)
        self.filter_wizard = FilterWizard(
            accent_color=TabColors.COLLECTION,
            tab_name="insect_collection",
            parent=self
        )
        self.filter_wizard.setVisible(False)
        layout.addWidget(self.filter_wizard)

        # Content area
        content = QWidget()
        content.setStyleSheet(f"""
            QWidget {{
                background-color: {TabColors.COLLECTION_LIGHT};
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_sm')};
            }}
        """)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 16, 16, 16)

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
        self.table_view = QTableView()
        self._apply_table_stylesheet(t)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.verticalHeader().setDefaultSectionSize(24)
        self.table_view.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)

        # Table model — proxy connected after first data load
        self.table_model = SpecimenTableModel()
        self.sort_proxy = self._create_sort_proxy()
        self._proxy_connected = False

        # Column widths (restore saved or use defaults)
        header = self.table_view.horizontalHeader()
        widths = self.table_model.get_column_widths()
        settings = QSettings()
        for i, width in enumerate(widths):
            if i < header.count():
                saved = settings.value(f"collection_table_columns/col_{i}", width, type=int)
                self.table_view.setColumnWidth(i, saved if saved > 0 else width)

        header.sectionResized.connect(self._save_column_width)

        card_layout.addWidget(self.table_view)
        content_layout.addWidget(table_card)

        # Splitter: sidebar + content
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setChildrenCollapsible(True)

        self._sidebar_container = QWidget()
        self._sidebar_container.setFixedWidth(0)
        self._splitter.addWidget(self._sidebar_container)

        self._splitter.addWidget(content)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)

        layout.addWidget(self._splitter, 1)

    def _connect_signals(self):
        self.toolbar.add_specimen_requested.connect(self._on_add_specimen)
        if hasattr(self.toolbar, "drawer_assign_requested"):
            self.toolbar.drawer_assign_requested.connect(self._on_drawer_assign)
        self.toolbar.import_requested.connect(self._on_import_specimens)
        self.toolbar.columns_requested.connect(self._on_columns_requested)
        self.toolbar.filters_toggled.connect(self._on_filters_toggled)
        self.toolbar.sidebar_toggled.connect(self.toggle_sidebar)
        self.toolbar.wizard_toggled.connect(self._on_wizard_toggled)
        self.filter_wizard.filters_applied.connect(self._on_wizard_filters_applied)
        self.filter_wizard.filters_reset.connect(self._on_wizard_filters_reset)
        self.toolbar.export_requested.connect(self._on_export_all)
        self.toolbar.export_selected_requested.connect(self._on_export_selected)
        self.filters.filters_changed.connect(self._on_filters_changed)
        self.filters.special_view_selected.connect(self._on_special_view_selected)
        self.table_view.doubleClicked.connect(self._on_row_double_clicked)

        # Ctrl+Enter shortcut to open Add Specimen
        shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        shortcut.activated.connect(self._on_add_specimen)
        self.table_view.clicked.connect(self._on_table_row_clicked)
        self.table_view.viewport().setCursor(Qt.CursorShape.PointingHandCursor)

    # ── UI event handlers ───────────────────────────────────────────

    def _on_wizard_toggled(self, visible: bool):
        """Handle filter wizard visibility toggle."""
        self.filter_wizard.setVisible(visible)

    def _on_wizard_filters_applied(self, filters: dict):
        """Handle filter wizard apply — translate to IC filter format."""
        self._wizard_filters = filters
        tab_filters = {}

        # What: species, orders, families
        species_list = filters.get('species', [])
        if isinstance(species_list, str): species_list = [species_list] if species_list else []
        if species_list:
            tab_filters['species'] = species_list[0]

        orders = filters.get('taxon_group', [])
        if isinstance(orders, str): orders = [orders] if orders else []
        if orders:
            tab_filters['order'] = orders[0]

        families = filters.get('family', [])
        if isinstance(families, str): families = [families] if families else []
        if families:
            tab_filters['family'] = families[0]

        # Where: vice counties, sites
        vcs = filters.get('vice_county', [])
        if isinstance(vcs, str): vcs = [vcs] if vcs else []
        if vcs:
            vc = vcs[0]
            tab_filters['vice_county'] = vc.split(' - ')[0] if ' - ' in str(vc) else str(vc)

        sites = filters.get('site_name', [])
        if isinstance(sites, str): sites = [sites] if sites else []
        if sites:
            tab_filters['location'] = sites[0]

        # When: date range
        if filters.get('date_from'):
            tab_filters['date_from'] = filters['date_from']
        if filters.get('date_to'):
            tab_filters['date_to'] = filters['date_to']

        # Who: collector
        recorders = filters.get('recorder', [])
        if isinstance(recorders, str): recorders = [recorders] if recorders else []
        if recorders:
            tab_filters['collector'] = recorders[0]

        self._extra_filters = tab_filters
        self._load_data()

    def _on_wizard_filters_reset(self):
        """Handle filter wizard reset."""
        self._wizard_filters = {}
        self.filters.clear_filters()
        self._load_data()

    def _load_wizard_tab_data(self):
        """Load tab-specific data into the filter wizard from specimens table."""
        try:
            import sqlite3
            db = get_database()
            main_path = db.get_main_path() if hasattr(db, 'get_main_path') else str(db._main_db_path)
            conn = sqlite3.connect(main_path)
            
            species = [r[0] for r in conn.execute(
                "SELECT DISTINCT species_name FROM specimens WHERE species_name IS NOT NULL ORDER BY species_name"
            ).fetchall()]
            orders = [r[0] for r in conn.execute(
                "SELECT DISTINCT order_name FROM specimens WHERE order_name IS NOT NULL AND order_name != '' ORDER BY order_name"
            ).fetchall()]
            families = [r[0] for r in conn.execute(
                "SELECT DISTINCT family FROM specimens WHERE family IS NOT NULL AND family != '' ORDER BY family"
            ).fetchall()]
            collectors = [r[0] for r in conn.execute(
                "SELECT DISTINCT collector FROM specimens WHERE collector IS NOT NULL AND collector != '' ORDER BY collector"
            ).fetchall()]
            determiners = [r[0] for r in conn.execute(
                "SELECT DISTINCT determiner FROM specimens WHERE determiner IS NOT NULL AND determiner != '' ORDER BY determiner"
            ).fetchall()]
            sites = [r[0] for r in conn.execute(
                "SELECT DISTINCT site_name FROM specimens WHERE site_name IS NOT NULL AND site_name != '' ORDER BY site_name"
            ).fetchall()]
            years = [str(r[0]) for r in conn.execute(
                "SELECT DISTINCT substr(date_collected, 1, 4) as yr FROM specimens WHERE date_collected IS NOT NULL ORDER BY yr DESC"
            ).fetchall() if r[0]]
            
            conn.close()
            
            self.filter_wizard.set_tab_data(
                species=species, orders=orders, families=families,
                recorders=collectors, determiners=determiners,
                sites=sites, years=years
            )
        except Exception as e:
            print(f"[IC] Error loading wizard tab data: {e}")

    def _on_filters_toggled(self, visible: bool):
        self.filters.setVisible(visible)
        if visible:
            self._load_data()

    def _save_column_width(self, logical_index: int, old_size: int, new_size: int):
        settings = QSettings()
        settings.setValue(f"collection_table_columns/col_{logical_index}", new_size)

    def _on_drawer_assign(self):
        """Open "Drawer in hand" (A1); refresh the collection after any save."""
        from .drawer_assign_dialog import DrawerAssignDialog
        dlg = DrawerAssignDialog(self)
        dlg.saved.connect(lambda *_: self.refresh())
        dlg.exec()

    def _on_add_specimen(self):
        """Open the add-specimen dialog."""
        dialog = AddSpecimenDialog(
            self,
            self._uksi_model,
            self._vc_service,
            db=get_database()
        )
        if dialog.exec():
            specimen_data = dialog.get_specimen_data()
            if self._specimen_repo:
                self._specimen_repo.create(specimen_data)
            elif self._specimen_model:
                self._specimen_model.add_specimen(specimen_data)
            self._load_data()
            self.data_changed.emit()

    def _on_edit_specimen(self):
        """Open the edit-specimen dialog for the selected row."""
        specimen = self.get_selected_specimen()
        if not specimen:
            QMessageBox.information(self, "No Selection", "Please select a specimen to edit.")
            return

        specimen_dict = specimen if isinstance(specimen, dict) else vars(specimen)

        dialog = AddSpecimenDialog(
            self,
            self._uksi_model,
            self._vc_service,
            existing_specimen=specimen_dict,
            db=get_database()
        )
        if dialog.exec():
            specimen_data = dialog.get_specimen_data()
            specimen_id = specimen_dict.get('id')
            if specimen_id:
                if self._specimen_repo:
                    self._specimen_repo.update(specimen_id, specimen_data)
                elif self._specimen_model:
                    self._specimen_model.update_specimen(specimen_id, specimen_data)
            self._load_data()
            self.data_changed.emit()

    def _on_columns_requested(self):
        """Open column selector dialog."""
        from ..components.column_selector_dialog import ColumnSelectorDialog
        dialog = ColumnSelectorDialog(self.table_model, TabColors.COLLECTION, self)
        dialog.columns_changed.connect(self._on_columns_changed)
        dialog.exec()

    def _on_columns_changed(self):
        """Handle column visibility changes."""
        specimens = self.table_model._specimens.copy()
        self.table_model._setup_headers()
        self.table_model.set_specimens(specimens)
        header = self.table_view.horizontalHeader()
        widths = self.table_model.get_column_widths()
        for i, width in enumerate(widths):
            if i < header.count():
                self.table_view.setColumnWidth(i, width)

    def _on_import_specimens(self):
        """Open the specimen import wizard."""
        db = get_database()
        wizard = SpecimenImportWizard(
            uksi_model=self._uksi_model,
            vc_service=self._vc_service,
            parent=self,
            db=db
        )
        wizard.specimen_imported.connect(self._on_specimen_imported)
        wizard.exec()
        # Always reload after wizard closes (batch imports may not emit per-row signals)
        self._load_data()
        self._refresh_sidebar()

    def _on_specimen_imported(self, specimen):
        """Handle a newly imported specimen."""
        self._load_data()
        self._refresh_sidebar()
        self.data_changed.emit()

    def _on_filters_changed(self, filters: dict):
        self._current_view_mode = 'normal'
        self._load_data()

    def _on_row_double_clicked(self, index):
        """Open detail dialog on double-click."""
        source_index = self.sort_proxy.mapToSource(index)
        specimen = self.table_model.get_specimen_at_row(source_index.row())
        if specimen:
            self._show_specimen_detail(specimen)

    # ── Lifecycle ───────────────────────────────────────────────────

    def initialize(self, db_path=None, uksi_path=None):
        """Initialize with database connection."""
        if hasattr(self, "_ic_initialized") and self._ic_initialized:
            return
        self._ic_initialized = True
        db = get_database()
        self._specimen_model = SpecimenModel(db)

        if HAS_REPOSITORY:
            try:
                self._specimen_repo = SpecimenRepository()
            except Exception as e:
                print(f"[InsectCollectionTab] Could not create repository: {e}")
                self._specimen_repo = None

        if uksi_path:
            self._uksi_model = UKSIModel(db)
            self.filter_wizard.set_uksi_model(self._uksi_model)
        self._vc_service = VCLookupService()

        self.filters.initialize_with_database(db)
        self._load_data()
        self._load_wizard_tab_data()

    def refresh(self):
        """Refresh the display."""
        if self._current_view_mode == 'new_collections_list':
            self._show_new_collections_list()
        else:
            self._load_data()

    def refresh_display_settings(self):
        """Refresh display settings (common name, date format, filter visibility)."""
        settings = QSettings()
        show_filters = settings.value(
            Settings.FILTERS_VISIBLE_COLLECTION,
            Defaults.FILTERS_VISIBLE_COLLECTION, type=bool
        )
        self.filters.setVisible(show_filters)

        if self.table_model.refresh_common_name_setting():
            header = self.table_view.horizontalHeader()
            widths = self.table_model.get_column_widths()
            for i, width in enumerate(widths):
                if i < header.count():
                    self.table_view.setColumnWidth(i, width)

        self.table_model.refresh_date_format()

    def get_selected_specimen(self) -> Optional[Any]:
        """Get the currently selected specimen data."""
        indexes = self.table_view.selectedIndexes()
        if not indexes:
            return None
        proxy_index = indexes[0]
        source_index = self.sort_proxy.mapToSource(proxy_index)
        return self.table_model.get_specimen_at_row(source_index.row())

    def show_recent_additions(self):
        """Show unique species sorted by first collection date (newest first)."""
        self.filters.select_new_collections_list()

    def _on_special_view_selected(self, view_mode: str):
        """Handle special view mode selection from filter bar."""
        if view_mode == 'new_collections_list':
            self._show_new_collections_list()

    # ── Theming ─────────────────────────────────────────────────────

    def apply_theme(self):
        """Apply current theme to all components."""
        t = theme()
        self.setStyleSheet(f"background-color: {t.get('background')};")
        self.toolbar.apply_theme()
        self.filters.apply_theme()
        self._apply_table_stylesheet(t)

    def _apply_table_stylesheet(self, t=None):
        """Apply table styling (shared between _setup_ui and apply_theme)."""
        if t is None:
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
                background-color: {TabColors.COLLECTION_LIGHT};
            }}
            QTableView::item:selected {{
                background-color: {TabColors.COLLECTION_LIGHT};
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
