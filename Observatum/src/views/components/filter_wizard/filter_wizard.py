"""
Filter Wizard Widget.

Main container for the filter system.
Shows card grid and manages filter state.
Supports saving and loading filter configurations.
"""

from typing import Dict, Any, List, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QComboBox, QMessageBox
)
from PySide6.QtCore import Signal, Qt

from ....themes import theme
from ....core.config import ButtonColors
from .filter_cards import FilterCardGrid
from .what_filter_dialog import WhatFilterDialog
from .where_filter_dialog import WhereFilterDialog
from .when_filter_dialog import WhenFilterDialog
from .who_filter_dialog import WhoFilterDialog
from .how_filter_dialog import HowFilterDialog
from .status_filter_dialog import StatusFilterDialog


class FilterWizard(QWidget):
    """
    Filter Wizard widget with card-based interface.
    
    Opens dialogs for each filter category and combines
    all filters into a single configuration.
    
    Signals:
        filters_changed: Emitted when filters change (filter_dict)
        filter_applied: Emitted when Apply is clicked (filter_dict)
        filters_applied: Alias for filter_applied (backward compat)
        filter_cleared: Emitted when Reset is clicked
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
        show_save_controls: bool = True,
        tab_name: str = "observations",
        parent=None
    ):
        super().__init__(parent)
        self._accent_color = accent_color or "#5f8575"
        self._show_save_controls = show_save_controls
        self._tab_name = tab_name
        
        # Filter state
        self._filters: Dict[str, Dict] = {
            'what': {},
            'where': {},
            'when': {},
            'who': {},
            'how': {},
            'status': {},
        }
        
        # Data for dialogs (populated by parent or lazy loaded)
        self._species_list: List[str] = []
        self._taxon_groups: List[str] = []
        self._family_list: List[str] = []
        self._taxon_family_map: Dict[str, List[str]] = {}
        self._recorder_list: List[str] = []
        self._determiner_list: List[str] = []
        self._method_list: List[str] = []
        self._year_list: List[int] = []
        
        # UKSI model for lazy loading taxon data
        self._uksi_model = None
        self._taxon_data_loaded = False
        
        # Saved filters service
        self._saved_filters_service = None
        
        self._setup_ui()
        self._load_saved_filter_names()
    
    def _setup_ui(self):
        """Set up the wizard UI."""
        t = theme()
        
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header row
        header_layout = QHBoxLayout()
        
        header_label = QLabel("Filter Records")
        header_label.setStyleSheet(f"""
            QLabel {{
                font-size: 16px;
                font-weight: 600;
                color: white;
                background-color: {self._accent_color};
                padding: 10px 20px;
                border-radius: 4px;
            }}
        """)
        header_layout.addWidget(header_label)
        
        header_layout.addStretch()
        
        # Active filter count
        self._filter_count_label = QLabel("No filters active")
        self._filter_count_label.setStyleSheet(f"""
            QLabel {{
                color: {t.get('text_muted')};
                font-size: 13px;
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
        
        # Save/Load filter row
        if self._show_save_controls:
            save_layout = QHBoxLayout()
            save_layout.setSpacing(12)
            
            # Load saved filter dropdown
            load_label = QLabel("Load saved:")
            load_label.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 12px;")
            save_layout.addWidget(load_label)
            
            self._saved_filters_combo = QComboBox()
            self._saved_filters_combo.setMinimumWidth(150)
            self._saved_filters_combo.setPlaceholderText("Select filter...")
            self._saved_filters_combo.currentTextChanged.connect(self._on_load_saved_filter)
            self._style_combo(self._saved_filters_combo)
            save_layout.addWidget(self._saved_filters_combo)
            
            # Delete saved filter button
            delete_btn = QPushButton("🗑")
            delete_btn.setToolTip("Delete selected saved filter")
            delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            delete_btn.clicked.connect(self._delete_saved_filter)
            delete_btn.setFixedWidth(36)
            delete_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    border: 1px solid {t.get('border')};
                    border-radius: 4px;
                    padding: 6px;
                    font-size: 14px;
                }}
                QPushButton:hover {{
                    background-color: {t.get('hover')};
                    border-color: #a63d40;
                }}
            """)
            save_layout.addWidget(delete_btn)
            
            save_layout.addSpacing(20)
            
            # Save filter section
            filter_label = QLabel("Save as:")
            filter_label.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 12px;")
            save_layout.addWidget(filter_label)
            
            self._filter_name_input = QLineEdit()
            self._filter_name_input.setPlaceholderText("Enter filter name...")
            self._filter_name_input.setMaximumWidth(180)
            self._filter_name_input.returnPressed.connect(self._save_filter)
            self._style_input(self._filter_name_input)
            save_layout.addWidget(self._filter_name_input)
            
            save_btn = QPushButton("💾 Save")
            save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            save_btn.clicked.connect(self._save_filter)
            save_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {ButtonColors.PRIMARY};
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                    font-size: 12px;
                }}
                QPushButton:hover {{
                    background-color: {self._darken_color(ButtonColors.PRIMARY)};
                }}
            """)
            save_layout.addWidget(save_btn)
            
            save_layout.addStretch()
            layout.addLayout(save_layout)
        
        # Button row
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        
        button_layout.addStretch()
        
        # Reset button
        reset_btn = QPushButton("Reset")
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.clicked.connect(self._reset_filters)
        reset_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {t.get('text_secondary')};
                border: 1px solid {t.get('border')};
                border-radius: 4px;
                padding: 10px 20px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {t.get('hover')};
            }}
        """)
        button_layout.addWidget(reset_btn)
        
        # Apply button
        apply_btn = QPushButton("Apply Filter")
        apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_btn.clicked.connect(self._apply_filters)
        apply_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ButtonColors.PRIMARY};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 24px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {self._darken_color(ButtonColors.PRIMARY)};
            }}
        """)
        button_layout.addWidget(apply_btn)
        
        layout.addLayout(button_layout)
    
    def _get_saved_filters_service(self):
        """Lazy load the saved filters service."""
        if self._saved_filters_service is None:
            try:
                from ....services.saved_filters_service import get_saved_filters_service
                self._saved_filters_service = get_saved_filters_service()
            except Exception as e:
                print(f"[FilterWizard] Could not load saved filters service: {e}")
        return self._saved_filters_service
    
    def _load_saved_filter_names(self):
        """Load saved filter names into the combo box."""
        if not self._show_save_controls:
            return
        
        service = self._get_saved_filters_service()
        if service:
            self._saved_filters_combo.blockSignals(True)
            self._saved_filters_combo.clear()
            self._saved_filters_combo.addItem("")  # Empty option
            
            names = service.get_filter_names(tab=self._tab_name)
            for name in sorted(names):
                self._saved_filters_combo.addItem(name)
            
            self._saved_filters_combo.blockSignals(False)
    
    def _on_load_saved_filter(self, name: str):
        """Load a saved filter by name."""
        if not name:
            return
        
        service = self._get_saved_filters_service()
        if service:
            config = service.get_filter(name)
            if config:
                self.set_filters(config)
                print(f"[FilterWizard] Loaded saved filter: {name}")
    
    def _save_filter(self):
        """Save current filter configuration."""
        if not hasattr(self, '_filter_name_input'):
            return
        
        name = self._filter_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Save Filter", "Please enter a name for the filter.")
            return
        
        service = self._get_saved_filters_service()
        if service:
            config = self.get_all_filters()
            if service.save_filter(name, config, tab=self._tab_name):
                self._filter_name_input.clear()
                self._load_saved_filter_names()
                QMessageBox.information(self, "Save Filter", f"Filter '{name}' saved successfully.")
            else:
                QMessageBox.warning(self, "Save Filter", "Could not save filter.")
    
    def _delete_saved_filter(self):
        """Delete the currently selected saved filter."""
        if not hasattr(self, '_saved_filters_combo'):
            return
        
        name = self._saved_filters_combo.currentText()
        if not name:
            return
        
        reply = QMessageBox.question(
            self, "Delete Filter",
            f"Delete saved filter '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            service = self._get_saved_filters_service()
            if service and service.delete_filter(name):
                self._load_saved_filter_names()
    
    def _on_card_clicked(self, card_id: str):
        """Handle card click - open appropriate dialog."""
        dialog = None
        current_values = self._filters.get(card_id, {})
        
        if card_id == 'what':
            # Lazy load taxon data
            self._ensure_taxon_data_loaded()
            dialog = WhatFilterDialog(
                accent_color=self._accent_color,
                current_values=current_values,
                species_list=self._species_list,
                taxon_groups=self._taxon_groups,
                family_list=self._family_list,
                taxon_family_map=self._taxon_family_map,
                parent=self
            )
        elif card_id == 'where':
            dialog = WhereFilterDialog(
                accent_color=self._accent_color,
                current_values=current_values,
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
                parent=self
            )
        
        if dialog:
            if dialog.exec():
                values = dialog.get_values()
                self._filters[card_id] = values
                self._update_card_states()
                self._update_filter_count()
                self.filters_changed.emit(self.get_all_filters())
    
    def _update_card_states(self):
        """Update card visual states based on filter data."""
        for card_id, filters in self._filters.items():
            has_filters = bool(filters) and any(
                v for v in filters.values() 
                if v and (isinstance(v, list) and len(v) > 0 or isinstance(v, str) and v)
            )
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
    
    def _reset_filters(self):
        """Reset all filters."""
        self._filters = {
            'what': {},
            'where': {},
            'when': {},
            'who': {},
            'how': {},
            'status': {},
        }
        self._update_card_states()
        self._update_filter_count()
        
        # Clear saved filter selection
        if hasattr(self, '_saved_filters_combo'):
            self._saved_filters_combo.setCurrentIndex(0)
        
        self.filter_cleared.emit()
        self.filters_reset.emit()  # Emit both for compatibility
        self.filters_changed.emit({})
    
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
        self._filters = {
            'what': {},
            'where': {},
            'when': {},
            'who': {},
            'how': {},
            'status': {},
        }
        
        key_to_card = {
            'species': 'what',
            'taxon_group': 'what',
            'family': 'what',
            'vice_county': 'where',
            'grid_ref': 'where',
            'site_name': 'where',
            'date_from': 'when',
            'date_to': 'when',
            'year': 'when',
            'recorder': 'who',
            'determiner': 'who',
            'method': 'how',
            'verification_status': 'status',
            'record_type': 'status',
        }
        
        for key, value in filters.items():
            card_id = key_to_card.get(key)
            if card_id:
                self._filters[card_id][key] = value
        
        self._update_card_states()
        self._update_filter_count()
    
    def set_uksi_model(self, model):
        """Set UKSI model for lazy loading taxon data."""
        self._uksi_model = model

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
                from ....models.database import get_database
                db = get_database()
                cursor = db.execute(
                    "SELECT DISTINCT scientific_name FROM observations "
                    "WHERE scientific_name IS NOT NULL ORDER BY scientific_name LIMIT 5000"
                )
                self._species_list = [row[0] for row in cursor.fetchall()]
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
                padding: 8px 12px;
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
                padding: 6px 10px;
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
