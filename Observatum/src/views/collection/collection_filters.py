"""
Collection Filter Bar Component.

Horizontal filter bar with saved filters for the Insect Collection tab.
Uses shared components for ComboFilterWidget, SavedFiltersMixin, and styling.
"""


from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QWidget, QCompleter
)
from PySide6.QtCore import Signal, Qt, QStringListModel, QDate, QMetaMethod

from ...themes import theme
from ...core.config import TabColors

# Shared components
from ..components.date_filter_widget import DateFilterWidget
from ..components.combo_filter_widget import ComboFilterWidget
from ..components.filter_debounce import debounce_text, cancel_pending
from ..components.saved_filters_mixin import SavedFiltersMixin, create_saved_filter_buttons
from ..components.filter_styles import (
    STANDARD_INPUT_HEIGHT,
    COL_SPECIES, COL_LOCATION, COL_DATE_FROM, COL_DATE_TO,
    COL_ORDER, COL_FAMILY, COL_VICE_COUNTY, COL_RECORDER,
    COL_METHOD, COL_SOURCE, COL_VERIFICATION,
    get_input_style, get_placeholder_style, get_clear_button_style, create_filter_label,
)
from ...services.vc_lookup_service import VCLookupService


class CollectionFilterBar(QFrame, SavedFiltersMixin):
    """Horizontal filter bar for specimen filtering."""
    
    filters_changed = Signal(dict)
    clear_all_requested = Signal()   # Clear All clicked: the tab clears everything
    save_filter_requested = Signal()
    special_view_selected = Signal(str)  # Emits view mode like 'new_collections_list'
    
    ORDER_OPTIONS = ['', 'Coleoptera', 'Diptera', 'Hymenoptera', 'Hemiptera', 'Lepidoptera']
    
    # Built-in preset filters
    _preset_filters = [
        {'name': '📋 New Collections List', 'view_mode': 'new_collections_list', 'is_preset': True},
    ]
    
    # Settings key for saved filters
    _settings_key = "collection_saved_filters"
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._db = None
        self._accent = TabColors.COLLECTION
        self._setup_ui()
        self._init_saved_filters()  # From SavedFiltersMixin
    
    def _setup_ui(self):
        t = theme()
        self.setStyleSheet(f"background-color: {t.get('surface')}; border-bottom: 1px solid {t.get('border')};")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Row 1: Saved filters
        self._setup_saved_filters_row(layout)
        
        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {t.get('border')};")
        layout.addWidget(sep)
        
        # Row 2: Filter controls
        self._setup_filter_controls(layout)
    
    def _setup_saved_filters_row(self, layout):
        """Set up saved filters row."""
        t = theme()
        
        saved_row = QHBoxLayout()
        
        saved_label = QLabel("Saved Filters:")
        saved_label.setStyleSheet(f"font-size: {t.font_size('sm')}; font-weight: bold; color: {t.get('text_secondary')};")
        saved_row.addWidget(saved_label)
        
        self.saved_combo = QComboBox()
        self.saved_combo.setMinimumWidth(200)
        saved_row.addWidget(self.saved_combo)
        
        # Use helper to create styled buttons
        self.save_filter_btn, self.delete_filter_btn = create_saved_filter_buttons(self)
        saved_row.addWidget(self.save_filter_btn)
        saved_row.addWidget(self.delete_filter_btn)
        
        saved_row.addStretch()
        layout.addLayout(saved_row)
    
    def _setup_filter_controls(self, layout):
        """Set up filter controls row with unified column widths."""
        t = theme()
        input_style = get_input_style()
        placeholder_style = get_placeholder_style()
        
        filters_row = QHBoxLayout()
        filters_row.setSpacing(8)
        
        # Clear All: at the left, beside Species (Wil 10 Oct). On a record tab it
        # clears everything -- this bar, the saved filter and the Filter Wizard -- the
        # same as the toolbar's Clear Filters (the tab connects clear_all_requested)
        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.setFixedHeight(STANDARD_INPUT_HEIGHT)
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.setStyleSheet(get_clear_button_style())
        self.clear_btn.clicked.connect(self._on_clear_all_clicked)
        filters_row.addWidget(self.clear_btn, 0, Qt.AlignmentFlag.AlignBottom)

        # Column 1: Species
        species_container = QWidget()
        species_container.setFixedWidth(COL_SPECIES)
        species_box = QVBoxLayout(species_container)
        species_box.setContentsMargins(0, 0, 0, 0)
        species_box.setSpacing(4)
        species_box.addWidget(create_filter_label("Species"))
        self.species_edit = QLineEdit()
        self.species_edit.setPlaceholderText("Search...")
        self.species_edit.setFixedHeight(STANDARD_INPUT_HEIGHT)
        self.species_edit.setStyleSheet(f"QLineEdit {{ {input_style} }}")
        debounce_text(self.species_edit, self._emit_filters)   # once typing pauses (speed)
        
        self._species_completer_model = QStringListModel()
        self._species_completer = QCompleter(self._species_completer_model)
        self._species_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._species_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.species_edit.setCompleter(self._species_completer)
        species_box.addWidget(self.species_edit)
        filters_row.addWidget(species_container)
        
        # Column 2: Location
        location_container = QWidget()
        location_container.setFixedWidth(COL_LOCATION)
        location_box = QVBoxLayout(location_container)
        location_box.setContentsMargins(0, 0, 0, 0)
        location_box.setSpacing(4)
        location_box.addWidget(create_filter_label("Location"))
        self.location_edit = QLineEdit()
        self.location_edit.setPlaceholderText("Search...")
        self.location_edit.setFixedHeight(STANDARD_INPUT_HEIGHT)
        self.location_edit.setStyleSheet(f"QLineEdit {{ {input_style} }}")
        debounce_text(self.location_edit, self._emit_filters)   # once typing pauses (speed)
        
        self._location_completer_model = QStringListModel()
        self._location_completer = QCompleter(self._location_completer_model)
        self._location_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._location_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.location_edit.setCompleter(self._location_completer)
        location_box.addWidget(self.location_edit)
        filters_row.addWidget(location_container)
        
        # Column 3: Date From
        date_from_container = QWidget()
        date_from_container.setFixedWidth(COL_DATE_FROM)
        date_from_box = QVBoxLayout(date_from_container)
        date_from_box.setContentsMargins(0, 0, 0, 0)
        date_from_box.setSpacing(4)
        date_from_box.addWidget(create_filter_label("Date From"))
        self.date_from_edit = DateFilterWidget(accent_color=self._accent)
        self.date_from_edit.dateChanged.connect(self._emit_filters)
        date_from_box.addWidget(self.date_from_edit)
        filters_row.addWidget(date_from_container)
        
        # Column 4: Date To
        date_to_container = QWidget()
        date_to_container.setFixedWidth(COL_DATE_TO)
        date_to_box = QVBoxLayout(date_to_container)
        date_to_box.setContentsMargins(0, 0, 0, 0)
        date_to_box.setSpacing(4)
        date_to_box.addWidget(create_filter_label("Date To"))
        self.date_to_edit = DateFilterWidget(accent_color=self._accent)
        self.date_to_edit.dateChanged.connect(self._emit_filters)
        date_to_box.addWidget(self.date_to_edit)
        filters_row.addWidget(date_to_container)
        
        # Column 5: Order
        order_container = QWidget()
        order_container.setFixedWidth(COL_ORDER)
        order_box = QVBoxLayout(order_container)
        order_box.setContentsMargins(0, 0, 0, 0)
        order_box.setSpacing(4)
        order_box.addWidget(create_filter_label("Order"))
        self.order_combo = ComboFilterWidget(accent_color=self._accent)
        for order in self.ORDER_OPTIONS:
            data = None if order == '' else order
            display_text = "All" if order == '' else order
            self.order_combo.addItem(display_text, data)
        self.order_combo.currentTextChanged.connect(self._emit_filters)
        order_box.addWidget(self.order_combo)
        filters_row.addWidget(order_container)
        
        # Column 6: Family (search-based autocomplete)
        family_container = QWidget()
        family_container.setFixedWidth(COL_FAMILY)
        family_box = QVBoxLayout(family_container)
        family_box.setContentsMargins(0, 0, 0, 0)
        family_box.setSpacing(4)
        family_box.addWidget(create_filter_label("Family"))
        self.family_edit = QLineEdit()
        self.family_edit.setPlaceholderText("Search...")
        self.family_edit.setFixedHeight(STANDARD_INPUT_HEIGHT)
        self.family_edit.setStyleSheet(f"QLineEdit {{ {input_style} }}")
        debounce_text(self.family_edit, self._emit_filters)   # once typing pauses (speed)
        
        self._family_completer_model = QStringListModel()
        self._family_completer = QCompleter(self._family_completer_model)
        self._family_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._family_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._family_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._family_completer.setMaxVisibleItems(10)
        self.family_edit.setCompleter(self._family_completer)
        family_box.addWidget(self.family_edit)
        filters_row.addWidget(family_container)
        
        # Column 7: Vice County
        vc_container = QWidget()
        vc_container.setFixedWidth(COL_VICE_COUNTY)
        vc_box = QVBoxLayout(vc_container)
        vc_box.setContentsMargins(0, 0, 0, 0)
        vc_box.setSpacing(4)
        vc_box.addWidget(create_filter_label("Vice County"))
        self.vc_combo = ComboFilterWidget(accent_color=self._accent)
        self.vc_combo.addItem("All", None)
        self.vc_combo.currentTextChanged.connect(self._emit_filters)
        vc_box.addWidget(self.vc_combo)
        filters_row.addWidget(vc_container)
        
        # Column 8: Collector
        collector_container = QWidget()
        collector_container.setFixedWidth(COL_RECORDER)
        collector_box = QVBoxLayout(collector_container)
        collector_box.setContentsMargins(0, 0, 0, 0)
        collector_box.setSpacing(4)
        collector_box.addWidget(create_filter_label("Collector"))
        self.collector_edit = QLineEdit()
        self.collector_edit.setPlaceholderText("Search...")
        self.collector_edit.setFixedHeight(STANDARD_INPUT_HEIGHT)
        self.collector_edit.setStyleSheet(f"QLineEdit {{ {input_style} }}")
        debounce_text(self.collector_edit, self._emit_filters)   # once typing pauses (speed)
        collector_box.addWidget(self.collector_edit)
        filters_row.addWidget(collector_container)
        
        # Column 9: Method (placeholder - not used for collection)
        method_container = QWidget()
        method_container.setFixedWidth(COL_METHOD)
        method_box = QVBoxLayout(method_container)
        method_box.setContentsMargins(0, 0, 0, 0)
        method_box.setSpacing(4)
        method_box.addWidget(create_filter_label("Method", muted=True))
        method_placeholder = QLineEdit("—")
        method_placeholder.setReadOnly(True)
        method_placeholder.setFixedHeight(STANDARD_INPUT_HEIGHT)
        method_placeholder.setStyleSheet(placeholder_style)
        method_box.addWidget(method_placeholder)
        filters_row.addWidget(method_container)
        
        # Column 10: Source (placeholder)
        source_container = QWidget()
        source_container.setFixedWidth(COL_SOURCE)
        source_box = QVBoxLayout(source_container)
        source_box.setContentsMargins(0, 0, 0, 0)
        source_box.setSpacing(4)
        source_box.addWidget(create_filter_label("Source", muted=True))
        source_placeholder = QLineEdit("—")
        source_placeholder.setReadOnly(True)
        source_placeholder.setFixedHeight(STANDARD_INPUT_HEIGHT)
        source_placeholder.setStyleSheet(placeholder_style)
        source_box.addWidget(source_placeholder)
        filters_row.addWidget(source_container)
        
        # Column 11: Verification (placeholder)
        verification_container = QWidget()
        verification_container.setFixedWidth(COL_VERIFICATION)
        verification_box = QVBoxLayout(verification_container)
        verification_box.setContentsMargins(0, 0, 0, 0)
        verification_box.setSpacing(4)
        verification_box.addWidget(create_filter_label("Verification", muted=True))
        verification_placeholder = QLineEdit("—")
        verification_placeholder.setReadOnly(True)
        verification_placeholder.setFixedHeight(STANDARD_INPUT_HEIGHT)
        verification_placeholder.setStyleSheet(placeholder_style)
        verification_box.addWidget(verification_placeholder)
        filters_row.addWidget(verification_container)
        
        
        filters_row.addStretch()
        layout.addLayout(filters_row)
    
    def _emit_filters(self):
        """Emit the current filter values."""
        filters = self.get_filters()
        self.filters_changed.emit(filters)
    
    def get_filters(self) -> dict:
        """Get the current filter values."""
        # Any date that is set counts: "year >= 2000" dropped every earlier date (OBS-14)
        date_from = None
        from_date = self.date_from_edit.date()
        if from_date.isValid():
            date_from = from_date.toString("yyyy-MM-dd")
        
        date_to = None
        to_date = self.date_to_edit.date()
        if to_date.isValid():
            date_to = to_date.toString("yyyy-MM-dd")
        
        return {
            'species': self.species_edit.text().strip(),
            'location': self.location_edit.text().strip(),
            'date_from': date_from,
            'date_to': date_to,
            'order': self.order_combo.currentData(),
            'family': self.family_edit.text().strip() or None,
            'vice_county': self.vc_combo.currentData(),
            'collector': self.collector_edit.text().strip(),
        }
    
    def _set_quietly(self, change):
        """Run change() with every filter widget silent; the caller emits once."""
        widgets = [self.species_edit, self.location_edit, self.date_from_edit,
                   self.date_to_edit, self.order_combo, self.family_edit, self.vc_combo,
                   self.collector_edit]
        cancel_pending(self.species_edit, self.location_edit, self.family_edit,
                       self.collector_edit)
        for w in widgets:
            w.blockSignals(True)
        try:
            change()
        finally:
            for w in widgets:
                w.blockSignals(False)

    def _on_clear_all_clicked(self):
        """Clear All: the tab's clear-everything if it listens, else this bar alone."""
        if self.isSignalConnected(QMetaMethod.fromSignal(self.clear_all_requested)):
            self.clear_all_requested.emit()
        else:
            self.clear_filters()

    def clear_filters(self):
        """Clear all filter values and reload once (it reloaded once per widget)."""
        def change():
            self.species_edit.clear()
            self.location_edit.clear()
            self.date_from_edit.clear()
            self.date_to_edit.clear()
            self.order_combo.resetToFirst()
            self.family_edit.clear()
            self.vc_combo.resetToFirst()
            self.collector_edit.clear()
        self._set_quietly(change)
        self.saved_combo.setCurrentIndex(0)
        self._emit_filters()
    
    def _apply_saved_filter(self, filters: dict):
        """Apply a saved filter configuration (one reload). Required by SavedFiltersMixin."""
        def change():
            self.species_edit.setText(filters.get('species', ''))
            self.location_edit.setText(filters.get('location', ''))
            self.date_from_edit.setIsoDate(filters.get('date_from'))   # setText does not exist
            self.date_to_edit.setIsoDate(filters.get('date_to'))
            self.collector_edit.setText(filters.get('collector', ''))

            for combo, key in [(self.order_combo, 'order')]:
                val = filters.get(key, '')
                idx = combo.findData(val)
                if idx >= 0:
                    combo.setCurrentIndex(idx)

            # Family is now a text field
            self.family_edit.setText(filters.get('family', ''))

            vc = filters.get('vice_county', '')
            idx = self.vc_combo.findData(vc)
            if idx >= 0:
                self.vc_combo.setCurrentIndex(idx)
        self._set_quietly(change)
        self._emit_filters()
    
    def add_saved_filter(self, name: str, filters: dict):
        """Add a new saved filter."""
        self._saved_filters.append({'name': name, 'filters': filters})
        self._save_filters_to_settings()
        self._populate_saved_filters_combo()
    
    def select_new_collections_list(self):
        """Programmatically select the New Collections List preset."""
        return self.select_preset_by_view_mode('new_collections_list')
    
    def initialize_with_database(self, db):
        """Initialize completers and dropdowns from database."""
        self._db = db
        
        # Get date range for calendar defaults
        try:
            query = "SELECT MIN(date_collected) as min_date, MAX(date_collected) as max_date FROM specimens WHERE date_collected IS NOT NULL"
            results = db.execute_main(query)
            if results:
                if results[0]['min_date']:
                    parts = results[0]['min_date'].split('-')
                    if len(parts) == 3:
                        earliest_date = QDate(int(parts[0]), int(parts[1]), int(parts[2]))
                        self.date_from_edit.set_navigate_date(earliest_date)
                if results[0]['max_date']:
                    parts = results[0]['max_date'].split('-')
                    if len(parts) == 3:
                        latest_date = QDate(int(parts[0]), int(parts[1]), int(parts[2]))
                        self.date_to_edit.set_navigate_date(latest_date)
        except Exception as e:
            print(f"[CollectionFilterBar] Error getting date range: {e}")
        
        # Populate species completer
        try:
            query = "SELECT DISTINCT species_name FROM specimens WHERE species_name IS NOT NULL ORDER BY species_name"
            results = db.execute_main(query)
            species_list = [row['species_name'] or row[0] for row in results if row[0]]
            self._species_completer_model.setStringList(species_list)
        except Exception as e:
            print(f"[CollectionFilterBar] Error loading species list: {e}")
        
        # Populate location completer
        try:
            query = "SELECT DISTINCT site_name FROM specimens WHERE site_name IS NOT NULL ORDER BY site_name"
            results = db.execute_main(query)
            location_list = [row['site_name'] or row[0] for row in results if row[0]]
            self._location_completer_model.setStringList(location_list)
        except Exception as e:
            print(f"[CollectionFilterBar] Error loading location list: {e}")
        
        # Populate Order dropdown from data
        try:
            query = "SELECT DISTINCT order_name FROM specimens WHERE order_name IS NOT NULL ORDER BY order_name"
            results = db.execute_main(query)
            self.order_combo.clear()
            self.order_combo.addItem("All", "")
            for row in results:
                order = row['order_name'] or row[0]
                if order:
                    self.order_combo.addItem(order, order)
        except Exception as e:
            print(f"[CollectionFilterBar] Error loading orders: {e}")
        
        # Populate Family completer from data
        try:
            query = "SELECT DISTINCT family FROM specimens WHERE family IS NOT NULL ORDER BY family"
            results = db.execute_main(query)
            family_list = [row['family'] or row[0] for row in results if row[0]]
            self._family_completer_model.setStringList(family_list)
        except Exception as e:
            print(f"[CollectionFilterBar] Error loading families: {e}")
        
        # Populate Vice Counties
        self._populate_vice_counties_from_data(db)

    def _populate_vice_counties_from_data(self, db):
        """Populate vice counties dropdown from existing data."""
        # Use short names for compact display
        vc_short_names = VCLookupService.VC_SHORT_NAMES
        
        self.vc_combo.clear()
        self.vc_combo.addItem("All", "")
        
        try:
            query = "SELECT DISTINCT vc_number FROM specimens WHERE vc_number IS NOT NULL ORDER BY vc_number"
            results = db.execute_main(query)
            for row in results:
                vc_num = row['vc_number'] or row[0]
                if vc_num:
                    try:
                        vc_num = int(vc_num)
                        # Use short name for display
                        vc_name = VCLookupService.get_short_name(vc_num) or vc_short_names.get(vc_num, f"VC {vc_num}")
                        self.vc_combo.addItem(f"{vc_num} - {vc_name}", vc_num)
                    except (ValueError, TypeError):
                        pass
        except Exception as e:
            print(f"[CollectionFilterBar] Error loading vice counties: {e}")
    
    def apply_theme(self):
        """Apply current theme."""
        t = theme()
        self.setStyleSheet(f"background-color: {t.get('surface')}; border-bottom: 1px solid {t.get('border')};")
    
    def set_species_filter(self, species_name: str):
        """Set the species filter and show the filter bar.
        
        Used for cross-tab navigation when user clicks 'View all' in detail dialogs.
        
        Args:
            species_name: Species name to filter by
        """
        # The other filters are cleared first (OBS-08: they used to stay); the filter is
        # then applied once, here -- the callers no longer reload again (speed, 10 Oct)
        self.blockSignals(True)
        try:
            self.clear_filters()
            self.species_edit.setText(species_name)
        finally:
            self.blockSignals(False)
        self.setVisible(True)
        self._emit_filters()