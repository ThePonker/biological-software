"""
Filter Wizard Widget.

Main container for the filter system.
Shows card grid and manages filter state.
Saving/loading lives in the filter bar's top row (13 Oct 2026).
"""

from typing import Dict, Any, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QScrollArea, QFrame, QSizePolicy
)
from PySide6.QtCore import Signal, Qt

from ....themes import theme
from .filter_cards import FilterCardGrid
from .what_filter_dialog import WhatFilterDialog
from .where_filter_dialog import WhereFilterDialog
from .when_filter_dialog import WhenFilterDialog
from .who_filter_dialog import WhoFilterDialog
from .how_filter_dialog import HowFilterDialog
from .status_filter_dialog import StatusFilterDialog
from ....services.filter_builder import CARD_KEYS, KEY_TO_CARD, as_list, tab_columns, tab_values


def _empty_filters() -> Dict[str, Dict]:
    return {card: {} for card in CARD_KEYS}


class FilterWizard(QWidget):
    """
    Filter Wizard widget with card-based interface.
    
    Opens dialogs for each filter category and combines
    all filters into a single configuration.
    
    Signals:
        filters_changed: Emitted when filters change (filter_dict)
        filter_applied: Emitted when a card dialog is accepted (filter_dict)
        filters_applied: Alias for filter_applied (backward compat)
        filter_cleared: kept for compatibility (Reset button removed 13 Oct 2026)
        filters_reset: Alias for filter_cleared (backward compat)
    """
    
    filters_changed = Signal(dict)
    filter_applied = Signal(dict)
    filters_applied = Signal(dict)  # Alias for backward compatibility
    filter_cleared = Signal()
    filters_reset = Signal()  # Alias for backward compatibility
    
    def __init__(
        self,
        accent_color: str = None,
        tab_name: str = "observations",
        parent=None
    ):
        super().__init__(parent)
        self._accent_color = accent_color or "#5f8575"
        self._tab_name = tab_name
        
        # Filter state
        self._filters: Dict[str, Dict] = _empty_filters()
        
        # Data for dialogs (populated by parent or lazy loaded)
        self._species_list: List[str] = []
        self._taxon_groups: List[str] = []   # despite the name: ORDERS (key 'taxon_group')
        self._group_list: List[str] = []     # real taxon groups (key 'group'), display labels
        self._species_info: Dict[str, dict] = {}   # {species: {common, family, rank}} (R11)
        self._family_list: List[str] = []
        self._taxon_family_map: Dict[str, List[str]] = {}
        self._recorder_list: List[str] = []
        self._determiner_list: List[str] = []
        self._method_list: List[str] = []
        self._year_list: List[int] = []
        self._vc_list: List[str] = []
        self._grid_ref_list: List[str] = []
        self._site_list: List[str] = []
        self._status_list: List[str] = []
        self._record_type_list: List[str] = []
        self._dataset_list: List = []        # [(dataset, records)], Recording Scheme only

        # The values present in this tab's own table, loaded when a dialog first opens
        # and again after the tab reloads (refresh_tab_values) -- review SRCH12
        self._db_path = None
        self._tab_values_loaded = False
        
        # UKSI model for lazy loading taxon data
        self._uksi_model = None
        self._taxon_data_loaded = False
        
        self._setup_ui()
        self._hide_cards_without_columns()
    
    def _setup_ui(self):
        """Set up the wizard UI: a title line, the cards, and one row of controls.

        L29 (10 Oct): it took ~410 px when open. Now compact (about half), its own
        background so it looks the same on every tab, and capped at MAX_HEIGHT with a
        scroll bar should the cards ever need more room (large fonts)."""
        t = theme()
        self.setObjectName("filterWizard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            QWidget#filterWizard {{
                background-color: {t.get('surface_alt')};
                border-bottom: 1px solid {t.get('border')};
            }}
        """)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; }")
        inner = QWidget()
        inner.setObjectName("filterWizardInner")
        inner.setStyleSheet("QWidget#filterWizardInner { background: transparent; }")
        self._scroll.setWidget(inner)
        outer.addWidget(self._scroll)

        layout = QVBoxLayout(inner)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 8, 12, 8)
        
        # Title line: name in the tab's colour, active-filter count on the right
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_label = QLabel("Filter Wizard")
        header_label.setStyleSheet(f"""
            QLabel {{
                font-size: 13px;
                font-weight: 600;
                color: {self._accent_color};
                background: transparent;
            }}
        """)
        header_layout.addWidget(header_label)
        header_layout.addStretch()
        
        # Active filter count
        self._filter_count_label = QLabel("No filters active")
        self._filter_count_label.setStyleSheet(f"""
            QLabel {{
                color: {t.get('text_muted')};
                font-size: 12px;
                background: transparent;
            }}
        """)
        header_layout.addWidget(self._filter_count_label)
        layout.addLayout(header_layout)
        
        # Card grid
        self.card_grid = FilterCardGrid(
            accent_color=self._accent_color,
            columns=3
        )
        self.card_grid.card_clicked.connect(self._on_card_clicked)
        layout.addWidget(self.card_grid)

    MAX_HEIGHT = 300     # px; the cards scroll beyond this (L29)

    def _fit_height(self):
        """As tall as the contents (to MAX_HEIGHT), so the table keeps the rest."""
        inner = self._scroll.widget()
        inner.adjustSize()
        self.setMaximumHeight(min(inner.sizeHint().height(), self.MAX_HEIGHT))

    def showEvent(self, event):
        self._fit_height()
        super().showEvent(event)

    def _on_card_clicked(self, card_id: str):
        """Handle card click - open appropriate dialog."""
        dialog = None
        current_values = self._filters.get(card_id, {})
        
        self._ensure_tab_values()
        if card_id == 'what':
            dialog = WhatFilterDialog(
                accent_color=self._accent_color,
                current_values=current_values,
                species_list=self._species_list,
                taxon_groups=self._taxon_groups,
                family_list=self._family_list,
                group_list=self._group_list,
                species_info=self._species_info,
                taxon_family_map=self._taxon_family_map,
                parent=self
            )
        elif card_id == 'where':
            dialog = WhereFilterDialog(
                accent_color=self._accent_color,
                current_values=current_values,
                vc_list=self._vc_list,
                grid_ref_list=self._grid_ref_list,
                site_list=self._site_list,
                parent=self
            )
        elif card_id == 'when':
            dialog = WhenFilterDialog(
                accent_color=self._accent_color,
                current_values=current_values,
                year_list=self._year_list,
                parent=self
            )
        elif card_id == 'who':
            dialog = WhoFilterDialog(
                accent_color=self._accent_color,
                current_values=current_values,
                recorder_list=self._recorder_list,
                determiner_list=self._determiner_list,
                parent=self
            )
        elif card_id == 'how':
            dialog = HowFilterDialog(
                accent_color=self._accent_color,
                current_values=current_values,
                method_list=self._method_list,
                parent=self
            )
        elif card_id == 'status':
            dialog = StatusFilterDialog(
                accent_color=self._accent_color,
                current_values=current_values,
                status_list=self._status_list,
                type_list=self._record_type_list,
                dataset_list=self._dataset_list,
                parent=self
            )
        
        if dialog:
            if dialog.exec():
                values = dialog.get_values()
                self._filters[card_id] = values
                self._update_card_states()
                self._update_filter_count()
                self.filters_changed.emit(self.get_all_filters())
                # 13 Oct 2026: the bottom Apply button is gone, so an accepted dialog applies
                self._apply_filters()
    
    def _update_card_states(self):
        """Update card visual states based on filter data."""
        for card_id, filters in self._filters.items():
            has_filters = any(as_list(v) for v in (filters or {}).values())   # a year is an int
            self.card_grid.set_card_active(card_id, has_filters)
    
    def _update_filter_count(self):
        """Update the active filter count label."""
        count = 0
        for filters in self._filters.values():
            if filters:
                for v in filters.values():
                    if isinstance(v, list):
                        count += len(v)
                    elif v:
                        count += 1
        
        if count == 0:
            self._filter_count_label.setText("No filters active")
        elif count == 1:
            self._filter_count_label.setText("1 filter active")
        else:
            self._filter_count_label.setText(f"{count} filters active")
    
    def _apply_filters(self):
        """Apply the current filters."""
        filters = self.get_all_filters()
        print(f"[FilterWizard] Applying filters: {filters}")
        self.filter_applied.emit(filters)
        self.filters_applied.emit(filters)  # Emit both for compatibility
    
    def clear_filters(self):
        """Empty every card without telling the tab (used when the tab navigates to a
        species and the wizard's filters must not linger -- OBS-08)."""
        self._filters = _empty_filters()
        self._update_card_states()
        self._update_filter_count()

    def get_all_filters(self) -> Dict[str, Any]:
        """Get combined filter configuration."""
        result = {}
        for card_id, filters in self._filters.items():
            if filters:
                result.update(filters)
        return result
    
    def set_filters(self, filters: Dict[str, Any]):
        """Set filters from a configuration dict."""
        # Reset first
        self._filters = _empty_filters()
        
        # One key->card table, shared with the builder: Notes search used to be dropped
        # here, so a saved filter lost it (SRCH11)
        for key, value in (filters or {}).items():
            card_id = KEY_TO_CARD.get(key)
            if card_id:
                self._filters[card_id][key] = value
        
        self._update_card_states()
        self._update_filter_count()
    
    def set_uksi_model(self, model):
        """Set UKSI model for lazy loading taxon data."""
        self._uksi_model = model

    # === This tab's own values for the dialogs (SRCH12) ===

    def set_db_path(self, db_path):
        """The database the tab reads (default: the app's main database)."""
        self._db_path = db_path
        self._tab_values_loaded = False

    def refresh_tab_values(self):
        """The tab's data changed: re-read the values on the next dialog."""
        self._tab_values_loaded = False

    def _resolve_db_path(self):
        if self._db_path:
            return self._db_path
        try:
            from ....models.database import get_database
            path = get_database().main_db_path
            if path:
                return path
        except Exception:
            pass
        import paths
        return paths.OBSERVATUM_DB

    def _ensure_tab_values(self):
        """Fill the dialogs' lists from this tab's own table, read-only (SRCH12, SRCH20)."""
        if self._tab_values_loaded:
            return
        try:
            v = tab_values(self._resolve_db_path(), self._tab_name)
        except Exception as e:
            print(f"[FilterWizard] Could not read {self._tab_name} values: {e}")
            return
        self._species_list = v['species']
        self._taxon_groups = v['orders']
        self._family_list = v['families']
        self._group_list = v.get('groups', [])
        self._species_info = v.get('species_info', {})   # common name / family per species (R11)
        self._vc_list = v['vice_counties']
        self._grid_ref_list = v['grid_refs']
        self._site_list = v['sites']
        self._recorder_list = v['recorders']
        self._determiner_list = v['determiners']
        self._method_list = v['methods']
        self._status_list = v['statuses']
        self._record_type_list = v['record_types']
        self._dataset_list = v.get('datasets', [])
        self._year_list = v['years']
        self._tab_values_loaded = True
        self._taxon_data_loaded = True      # never the whole UKSI order list (SRCH12)

    def matching_ids(self, filters: Dict[str, Any] = None):
        """Ids of this tab's records the wizard's filters keep (None = no wizard filter).
        The one translation of chips into a query for every tab (services/filter_builder)."""
        from ....services.filter_builder import matching_ids
        return matching_ids(self._resolve_db_path(), self._tab_name,
                            self.get_all_filters() if filters is None else filters)

    def _hide_cards_without_columns(self):
        """Hide a card when this tab has no field for any of its keys (the collection
        has no verification status or record type)."""
        try:
            cols = tab_columns(self._tab_name)
        except KeyError:
            return
        for card_id, keys in CARD_KEYS.items():
            card = self.card_grid.get_card(card_id)
            if card is not None and not any(cols.column_for(k) for k in keys):
                card.setVisible(False)
        status = self.card_grid.get_card('status')
        if status is not None and cols.dataset:
            # Recording Scheme: the Status card also chooses the dataset / provider
            status.desc_label.setText("Verification status or dataset / provider")

    def set_tab_data(self, species=None, orders=None, families=None,
                     recorders=None, determiners=None, sites=None,
                     grid_refs=None, years=None, methods=None):
        """Set tab-specific data for scoped filtering.
        
        When set, the wizard uses this data instead of querying UKSI directly.
        Call this from each tab's initialize() after loading data.
        """
        if species is not None:
            self._species_list = sorted(set(species))
        if orders is not None:
            self._taxon_groups = sorted(set(orders))
        if families is not None:
            self._family_list = sorted(set(families))
        if recorders is not None:
            self._recorder_list = sorted(set(recorders))
        if determiners is not None:
            self._determiner_list = sorted(set(determiners))
        if sites is not None:
            self._site_list = sorted(set(sites))
        if grid_refs is not None:
            self._grid_ref_list = sorted(set(grid_refs))
        if years is not None:
            self._year_list = sorted(set(years), reverse=True)
        if methods is not None:
            self._method_list = sorted(set(methods))
        
        # Mark as loaded so _ensure_taxon_data_loaded doesn't overwrite
        if species or orders or families:
            self._taxon_data_loaded = True
    
    def _ensure_taxon_data_loaded(self):
        """Lazy load taxon data from UKSI when first needed."""
        if self._taxon_data_loaded or not self._uksi_model:
            return
        
        try:
            # Get orders/taxon groups - fast query
            orders = self._uksi_model.get_orders()
            self._taxon_groups = orders
            
            # Get all families - fast query (no order filter)
            all_families = self._uksi_model.get_families()
            self._family_list = all_families
            
            # Family mapping loaded on-demand when taxon selected
            self._taxon_family_map = {}
            
            # Get distinct species from observations for autocomplete
            try:
                # 9 Oct 2026: this asked DatabaseManager for .execute() (it has execute_main)
                # and for a scientific_name column (observations has species_name), so it
                # always failed and the What card's Species box had nothing to suggest.
                from ....models.database import get_database
                rows = get_database().execute_main(
                    "SELECT DISTINCT species_name FROM observations "
                    "WHERE species_name IS NOT NULL AND species_name != '' ORDER BY species_name"
                )
                self._species_list = [row[0] for row in rows]
                print(f"[FilterWizard] Loaded {len(self._species_list)} species")
            except Exception as e:
                print(f"[FilterWizard] Could not load species: {e}")
            
            self._taxon_data_loaded = True
            print(f"[FilterWizard] Loaded {len(orders)} orders, {len(all_families)} families")
        except Exception as e:
            print(f"[FilterWizard] Error loading taxon data: {e}")
    
    # === Data setters for dialogs ===
    
    def set_species_list(self, species: List[str]):
        """Set species list for What dialog autocomplete."""
        self._species_list = species
    
    def set_taxon_groups(self, groups: List[str]):
        """Set taxon group list for What dialog."""
        self._taxon_groups = groups
    
    def set_group_list(self, groups: List[str]):
        """Taxon groups for the What dialog's Group box (display labels from
        shared.taxon_groups.display_labels())."""
        self._group_list = list(groups or [])

    def set_family_list(self, families: List[str]):
        """Set family list for What dialog."""
        self._family_list = families
    
    def set_taxon_family_map(self, mapping: Dict[str, List[str]]):
        """Set taxon group to family mapping."""
        self._taxon_family_map = mapping
    
    def set_recorder_list(self, recorders: List[str]):
        """Set recorder list for Who dialog autocomplete."""
        self._recorder_list = recorders
    
    def set_determiner_list(self, determiners: List[str]):
        """Set determiner list for Who dialog autocomplete."""
        self._determiner_list = determiners
    
    def set_method_list(self, methods: List[str]):
        """Set sample method list for How dialog."""
        self._method_list = methods
    
    def set_year_list(self, years: List[int]):
        """Set year list for When dialog."""
        self._year_list = years
    
    def apply_theme(self):
        """Apply the current theme."""
        self.card_grid.apply_theme()
    
    def _style_input(self, widget: QLineEdit):
        """Apply input styling."""
        t = theme()
        widget.setStyleSheet(f"""
            QLineEdit {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: 4px;
                padding: 5px 8px;
                font-size: 12px;
                color: {t.get('text_primary')};
            }}
            QLineEdit:focus {{
                border-color: {self._accent_color};
            }}
        """)
    
    def _style_combo(self, widget: QComboBox):
        """Apply combo box styling."""
        t = theme()
        widget.setStyleSheet(f"""
            QComboBox {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
                color: {t.get('text_primary')};
            }}
            QComboBox:focus {{
                border-color: {self._accent_color};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                selection-background-color: {self._accent_color};
            }}
        """)
    
    def _darken_color(self, hex_color: str, factor: float = 0.85) -> str:
        """Darken a hex color."""
        hex_color = hex_color.lstrip('#')
        r = int(int(hex_color[0:2], 16) * factor)
        g = int(int(hex_color[2:4], 16) * factor)
        b = int(int(hex_color[4:6], 16) * factor)
        return f"#{r:02x}{g:02x}{b:02x}"
