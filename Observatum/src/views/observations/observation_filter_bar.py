"""
Observation Filter Bar Component.

Filter bar with saved filters support for the Observation tab.
Uses shared components for ComboFilterWidget, SavedFiltersMixin, and styling.
"""
from ...utils.constants import SAMPLE_METHOD_OPTIONS

from typing import List, Dict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame,
    QLabel, QLineEdit, QComboBox, QPushButton, QCompleter
)
from PySide6.QtCore import Signal, QDate, QSettings, Qt, QStringListModel

from ...themes import theme
from ...core.config import TabColors

# Shared components
from ..components.date_filter_widget import DateFilterWidget
from ..components.combo_filter_widget import ComboFilterWidget
from ..components.saved_filters_mixin import SavedFiltersMixin, create_saved_filter_buttons
from ..components.filter_styles import (
    STANDARD_INPUT_HEIGHT,
    COL_SPECIES, COL_LOCATION, COL_DATE_FROM, COL_DATE_TO,
    COL_ORDER, COL_FAMILY, COL_VICE_COUNTY, COL_RECORDER,
    COL_METHOD, COL_SOURCE, COL_VERIFICATION,
    get_input_style, get_clear_button_style, create_filter_label,
)
from ...services.vc_lookup_service import VCLookupService


class ObservationFilterBar(QFrame, SavedFiltersMixin):
    """Filter bar with saved filters support."""

    filters_changed = Signal(dict)
    filters_cleared = Signal()
    data_type_changed = Signal(str)  # Emits 'all', 'personal', or 'commercial'
    special_view_selected = Signal(str)  # Emits view mode like 'new_species_list'

    # Built-in preset filters
    _preset_filters = [
        {'name': '📋 New Species List', 'view_mode': 'new_species_list', 'is_preset': True},
        {'name': '📅 This Year', 'filters': {'date_from': 'THIS_YEAR'}, 'is_preset': True},
        {'name': '📅 Last 30 Days', 'filters': {'date_from': 'LAST_30_DAYS'}, 'is_preset': True},
    ]
    
    # Settings key for saved filters
    _settings_key = "observation_saved_filters"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._db = None
        self._all_families = []
        self._saved_filter_active = False
        self._earliest_date = None
        self._latest_date = None
        self._current_data_type = 'all'
        self._accent = TabColors.OBSERVATION  # Sage Green for Observation tab
        
        self._setup_ui()
        self._init_saved_filters()  # From SavedFiltersMixin
        self._connect_filter_change_signals()

    def _setup_ui(self):
        """Set up the filter bar UI."""
        t = theme()
        
        self.setStyleSheet(f"background-color: {t.get('surface')}; border-bottom: 1px solid {t.get('border')};")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Row 1: Saved Filters + Data Type
        self._setup_saved_filters_row(layout)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {t.get('border')};")
        layout.addWidget(sep)

        # Row 2: Filters
        self._setup_filters_row(layout)

    def _setup_saved_filters_row(self, content_layout):
        """Set up saved filters row with Data Type toggle."""
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

        # Spacer between Delete and Data Type
        saved_row.addSpacing(15)
        
        # Data Type toggle (All/Personal/Commercial)
        data_type_label = QLabel("Data Type:")
        data_type_label.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {t.get('text_secondary')};")
        saved_row.addWidget(data_type_label)
        
        data_type_btns = QHBoxLayout()
        data_type_btns.setSpacing(0)
        self._data_type_buttons = {}
        btn_widths = {'all': 36, 'personal': 60, 'commercial': 80}
        for i, dtype in enumerate(['all', 'personal', 'commercial']):
            btn = QPushButton(dtype.capitalize())
            btn.setCheckable(True)
            btn.setFixedHeight(22)
            btn.setMinimumWidth(btn_widths[dtype])
            if i == 0:
                radius = f"border-top-left-radius: {t.get('radius_sm')}; border-bottom-left-radius: {t.get('radius_sm')};"
            elif i == 2:
                radius = f"border-top-right-radius: {t.get('radius_sm')}; border-bottom-right-radius: {t.get('radius_sm')};"
            else:
                radius = ""
            btn.setStyleSheet(f"""
                QPushButton {{
                    padding: 2px 6px;
                    border: 1px solid {t.get('separator')};
                    background: {t.get('surface')};
                    color: {t.get('text_secondary')};
                    font-size: 11px;
                    font-weight: 500;
                    {radius}
                }}
                QPushButton:checked {{
                    background-color: {TabColors.OBSERVATION_DARK};
                    color: white;
                    border-color: {TabColors.OBSERVATION_DARK};
                    font-weight: 700;
                }}
                QPushButton:hover:not(:checked) {{ 
                    background-color: {t.get('background')}; 
                }}
                QPushButton:pressed {{
                    background-color: {TabColors.OBSERVATION_DARK};
                }}
            """)
            btn.clicked.connect(lambda checked, d=dtype: self._on_data_type_clicked(d))
            data_type_btns.addWidget(btn)
            self._data_type_buttons[dtype] = btn

        self._data_type_buttons['all'].setChecked(True)
        saved_row.addLayout(data_type_btns)
        
        saved_row.addStretch()
        content_layout.addLayout(saved_row)

    def _setup_filters_row(self, content_layout):
        """Set up main filters row with unified column widths."""
        t = theme()
        input_style = get_input_style()
        
        filters_row = QHBoxLayout()
        filters_row.setSpacing(8)

        # Column 1: Species (with auto-complete)
        species_container = QWidget()
        species_container.setFixedWidth(COL_SPECIES)
        species_box = QVBoxLayout(species_container)
        species_box.setContentsMargins(0, 0, 0, 0)
        species_box.setSpacing(4)
        species_box.addWidget(create_filter_label("Species"))
        self.species_edit = QLineEdit()
        self.species_edit.setPlaceholderText("Search...")
        self.species_edit.returnPressed.connect(self._apply_filters)
        self.species_edit.setFixedHeight(STANDARD_INPUT_HEIGHT)
        self.species_edit.setStyleSheet(f"QLineEdit {{ {input_style} }}")
        
        self._species_completer_model = QStringListModel()
        self._species_completer = QCompleter(self._species_completer_model)
        self._species_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._species_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._species_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._species_completer.setMaxVisibleItems(10)
        self.species_edit.setCompleter(self._species_completer)
        species_box.addWidget(self.species_edit)
        filters_row.addWidget(species_container)

        # Column 2: Location (with auto-complete)
        location_container = QWidget()
        location_container.setFixedWidth(COL_LOCATION)
        location_box = QVBoxLayout(location_container)
        location_box.setContentsMargins(0, 0, 0, 0)
        location_box.setSpacing(4)
        location_box.addWidget(create_filter_label("Location"))
        self.location_edit = QLineEdit()
        self.location_edit.setPlaceholderText("Search...")
        self.location_edit.returnPressed.connect(self._apply_filters)
        self.location_edit.setFixedHeight(STANDARD_INPUT_HEIGHT)
        self.location_edit.setStyleSheet(f"QLineEdit {{ {input_style} }}")
        
        self._location_completer_model = QStringListModel()
        self._location_completer = QCompleter(self._location_completer_model)
        self._location_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._location_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._location_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._location_completer.setMaxVisibleItems(10)
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
        for order in ["All", "Coleoptera", "Diptera", "Hymenoptera", "Lepidoptera",
                      "Hemiptera", "Orthoptera", "Neuroptera", "Odonata"]:
            data = None if order == 'All' else order
            self.order_combo.addItem(order, data)
        self.order_combo.currentTextChanged.connect(self._on_order_changed)
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
        vc_box.addWidget(self.vc_combo)
        filters_row.addWidget(vc_container)

        # Column 8: Recorder
        recorder_container = QWidget()
        recorder_container.setFixedWidth(COL_RECORDER)
        recorder_box = QVBoxLayout(recorder_container)
        recorder_box.setContentsMargins(0, 0, 0, 0)
        recorder_box.setSpacing(4)
        recorder_box.addWidget(create_filter_label("Recorder"))
        self.recorder_edit = QLineEdit()
        self.recorder_edit.setPlaceholderText("Search...")
        self.recorder_edit.returnPressed.connect(self._apply_filters)
        self.recorder_edit.setFixedHeight(STANDARD_INPUT_HEIGHT)
        self.recorder_edit.setStyleSheet(f"QLineEdit {{ {input_style} }}")
        recorder_box.addWidget(self.recorder_edit)
        filters_row.addWidget(recorder_container)

        # Column 9: Method
        method_container = QWidget()
        method_container.setFixedWidth(COL_METHOD)
        method_box = QVBoxLayout(method_container)
        method_box.setContentsMargins(0, 0, 0, 0)
        method_box.setSpacing(4)
        method_box.addWidget(create_filter_label("Method"))
        self.method_combo = ComboFilterWidget(accent_color=self._accent)
        for method in ["All"] + [m for m in SAMPLE_METHOD_OPTIONS if m]:
            data = None if method == 'All' else method
            self.method_combo.addItem(method, data)
        method_box.addWidget(self.method_combo)
        filters_row.addWidget(method_container)

        # Column 11: Verification Status
        status_container = QWidget()
        status_container.setFixedWidth(COL_VERIFICATION)
        status_box = QVBoxLayout(status_container)
        status_box.setContentsMargins(0, 0, 0, 0)
        status_box.setSpacing(4)
        status_box.addWidget(create_filter_label("Verification"))
        self.status_combo = ComboFilterWidget(accent_color=self._accent)
        for status in ["All", "Pending", "Accepted", "Unconfirmed", "Rejected"]:
            data = None if status == 'All' else status
            self.status_combo.addItem(status, data)
        status_box.addWidget(self.status_combo)
        filters_row.addWidget(status_container)

        # Clear All button
        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.setFixedHeight(STANDARD_INPUT_HEIGHT)
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.setStyleSheet(get_clear_button_style())
        self.clear_btn.clicked.connect(self.clear_filters)
        filters_row.addWidget(self.clear_btn, 0, Qt.AlignmentFlag.AlignBottom)

        filters_row.addStretch()
        content_layout.addLayout(filters_row)

    def _connect_filter_change_signals(self):
        """Connect filter widgets to emit changes automatically."""
        self.species_edit.textChanged.connect(self._emit_filters)
        self.location_edit.textChanged.connect(self._emit_filters)
        self.recorder_edit.textChanged.connect(self._emit_filters)
        self.date_from_edit.dateChanged.connect(self._emit_filters)
        self.date_to_edit.dateChanged.connect(self._emit_filters)
        self.order_combo.currentTextChanged.connect(self._emit_filters)
        self.family_edit.textChanged.connect(self._emit_filters)
        self.vc_combo.currentTextChanged.connect(self._emit_filters)
        self.method_combo.currentTextChanged.connect(self._emit_filters)
        self.status_combo.currentTextChanged.connect(self._emit_filters)
    
    def _emit_filters(self):
        """Emit current filters."""
        filters = self.get_filters()
        self.filters_changed.emit(filters)

    def _on_data_type_clicked(self, dtype: str):
        """Handle data type button click."""
        for d, btn in self._data_type_buttons.items():
            btn.setChecked(d == dtype)
        self._current_data_type = dtype
        self.data_type_changed.emit(dtype)

    def _on_order_changed(self):
        """Handle order selection change - update family dropdown."""
        self._update_family_completer()

    def _apply_filters(self):
        """Apply current filters and emit signal."""
        self._saved_filter_active = False
        self.saved_combo.setCurrentIndex(0)
        filters = self.get_filters()
        self.filters_changed.emit(filters)

    def get_filters(self) -> dict:
        """Get current filter values."""
        date_from = None
        from_date = self.date_from_edit.date()
        if from_date.year() >= 2000:
            date_from = from_date.toString("yyyy-MM-dd")
        
        date_to = None
        to_date = self.date_to_edit.date()
        if to_date.year() >= 2000:
            date_to = to_date.toString("yyyy-MM-dd")
        
        order = self.order_combo.currentText()
        if order == "All" or self.order_combo.currentIndex() == 0:
            order = None
            
        family = self.family_edit.text().strip()
        if not family:
            family = None
            
        vc = self.vc_combo.currentData()
        
        method = self.method_combo.currentText()
        if method == "All" or self.method_combo.currentIndex() == 0:
            method = None
            
            
        verification = self.status_combo.currentText()
        if verification == "All" or self.status_combo.currentIndex() == 0:
            verification = None
        
        return {
            'data_type': self._current_data_type,
            'species': self.species_edit.text().strip(),
            'location': self.location_edit.text().strip(),
            'date_from': date_from,
            'date_to': date_to,
            'order': order,
            'family': family,
            'vice_county': vc,
            'recorder': self.recorder_edit.text().strip(),
            'method': method,
            'verification_status': verification,
        }

    def get_data_type(self) -> str:
        """Get the currently selected data type."""
        return self._current_data_type

    def clear_filters(self):
        """Clear all filter values."""
        # Block signals to prevent multiple reloads during clear
        widgets = [
            self.species_edit, self.location_edit, self.recorder_edit,
            self.date_from_edit, self.date_to_edit,
            self.order_combo, self.family_edit, self.vc_combo,
            self.method_combo, self.status_combo,
            self.saved_combo
        ]
        for w in widgets:
            w.blockSignals(True)
        
        try:
            self._on_data_type_clicked('all')
            self.species_edit.clear()
            self.location_edit.clear()
            self.recorder_edit.clear()
            self.date_from_edit.clear()
            self.date_to_edit.clear()
            self.order_combo.resetToFirst()
            self.family_edit.clear()
            self.vc_combo.resetToFirst()
            self.method_combo.resetToFirst()
            self.status_combo.resetToFirst()
            self.saved_combo.setCurrentIndex(0)
            self._saved_filter_active = False
        finally:
            for w in widgets:
                w.blockSignals(False)
        
        # Emit once at the end
        self.filters_cleared.emit()
        self.filters_changed.emit(self.get_filters())

    def _apply_saved_filter(self, filters: dict):
        """Apply saved filter values to the UI. Required by SavedFiltersMixin."""
        # Handle special date values
        date_from = filters.get('date_from', '')
        if date_from == 'THIS_YEAR':
            from datetime import datetime
            self.date_from_edit.setDate(QDate(datetime.now().year, 1, 1))
        elif date_from == 'LAST_30_DAYS':
            self.date_from_edit.setDate(QDate.currentDate().addDays(-30))
        elif date_from:
            self.date_from_edit.setDate(QDate.fromString(date_from, "yyyy-MM-dd"))
        else:
            self.date_from_edit.setDate(QDate(1900, 1, 1))
        
        date_to = filters.get('date_to', '')
        if date_to:
            self.date_to_edit.setDate(QDate.fromString(date_to, "yyyy-MM-dd"))
        else:
            self.date_to_edit.setDate(QDate(1900, 1, 1))
        
        self.species_edit.setText(filters.get('species', ''))
        self.location_edit.setText(filters.get('location', ''))
        self.recorder_edit.setText(filters.get('recorder', ''))
        
        for combo, key in [(self.order_combo, 'order'),
                           (self.method_combo, 'method'), 
                           (self.status_combo, 'verification_status')]:
            val = filters.get(key)
            if val:
                idx = combo.findText(val)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
        
        # Family is now a text field
        self.family_edit.setText(filters.get('family', ''))
        
        vc = filters.get('vice_county')
        if vc:
            idx = self.vc_combo.findData(vc)
            if idx >= 0:
                self.vc_combo.setCurrentIndex(idx)
        
        self.filters_changed.emit(self.get_filters())

    def populate_vice_counties(self, vc_list: List[Dict]):
        """Populate vice county dropdown."""
        self.vc_combo.clear()
        self.vc_combo.addItem("All", None)
        for vc in vc_list:
            # Use short_name if available, otherwise fall back to name
            display_name = vc.get('short_name') or vc.get('name', f"VC {vc['number']}")
            self.vc_combo.addItem(f"{vc['number']} - {display_name}", vc['number'])
    
    def initialize_with_database(self, db):
        """Initialize completers and dropdowns from database."""
        self._db = db
        
        # Block signals while populating
        for widget in [self.order_combo, self.family_edit, self.vc_combo,
                       self.method_combo, self.status_combo,
                       self.date_from_edit, self.date_to_edit]:
            widget.blockSignals(True)
        
        # Get date range for calendar defaults
        try:
            query = "SELECT MIN(date) as min_date, MAX(date) as max_date FROM observations WHERE date IS NOT NULL"
            results = db.execute_main(query)
            if results:
                if results[0]['min_date']:
                    parts = results[0]['min_date'].split('-')
                    if len(parts) == 3:
                        self._earliest_date = QDate(int(parts[0]), int(parts[1]), int(parts[2]))
                        self.date_from_edit.set_navigate_date(self._earliest_date)
                if results[0]['max_date']:
                    parts = results[0]['max_date'].split('-')
                    if len(parts) == 3:
                        self._latest_date = QDate(int(parts[0]), int(parts[1]), int(parts[2]))
                        self.date_to_edit.set_navigate_date(self._latest_date)
        except Exception as e:
            print(f"[FilterBar] Error getting date range: {e}")
        
        # Populate species completer
        try:
            query = """
                SELECT DISTINCT species_name FROM observations WHERE species_name IS NOT NULL 
                UNION SELECT DISTINCT common_name FROM observations WHERE common_name IS NOT NULL
                ORDER BY 1
            """
            results = db.execute_main(query)
            species_list = [row['species_name'] or row[0] for row in results if row[0]]
            self._species_completer_model.setStringList(species_list)
        except Exception as e:
            print(f"[FilterBar] Error loading species list: {e}")
        
        # Populate location completer
        try:
            query = "SELECT DISTINCT site_name FROM observations WHERE site_name IS NOT NULL ORDER BY site_name"
            results = db.execute_main(query)
            location_list = [row['site_name'] or row[0] for row in results if row[0]]
            self._location_completer_model.setStringList(location_list)
        except Exception as e:
            print(f"[FilterBar] Error loading location list: {e}")
        
        # Populate order-family mapping
        try:
            query = """
                SELECT DISTINCT order_name, family FROM observations 
                WHERE order_name IS NOT NULL AND family IS NOT NULL
                ORDER BY order_name, family
            """
            results = db.execute_main(query)
            self._order_family_map = {}
            self._all_families = set()
            for row in results:
                order = row['order_name'] or row[0]
                family = row['family'] or row[1]
                if order and family:
                    if order not in self._order_family_map:
                        self._order_family_map[order] = []
                    if family not in self._order_family_map[order]:
                        self._order_family_map[order].append(family)
                    self._all_families.add(family)
            self._all_families = sorted(self._all_families)
            self._update_family_completer()

            # Repopulate order combo with all orders from data
            self.order_combo.blockSignals(True)
            current = self.order_combo.currentText()
            self.order_combo.clear()
            self.order_combo.addItem("All", None)
            for order in sorted(self._order_family_map.keys()):
                self.order_combo.addItem(order, order)
            # Restore previous selection if still valid
            idx = self.order_combo.findText(current)
            if idx >= 0:
                self.order_combo.setCurrentIndex(idx)
            self.order_combo.blockSignals(False)

        except Exception as e:
            print(f"[FilterBar] Error loading families: {e}")
            self._order_family_map = {}
            self._all_families = []
        
        # Populate Vice Counties
        self._populate_vice_counties_from_data(db)
        
        # Restore signals
        for widget in [self.order_combo, self.family_edit, self.vc_combo,
                       self.method_combo, self.status_combo,
                       self.date_from_edit, self.date_to_edit]:
            widget.blockSignals(False)
    
    def _populate_vice_counties_from_data(self, db):
        """Populate vice counties dropdown from existing data."""
        # Use short names for compact display
        vc_short_names = VCLookupService.VC_SHORT_NAMES
        
        self.vc_combo.clear()
        self.vc_combo.addItem("All", None)
        
        try:
            query = "SELECT DISTINCT vc_number FROM observations WHERE vc_number IS NOT NULL ORDER BY vc_number"
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
            print(f"[FilterBar] Error loading vice counties: {e}")

    def _update_family_completer(self):
        """Update family autocomplete based on selected order."""
        if not hasattr(self, '_order_family_map'):
            return
        
        selected_order = self.order_combo.currentText()
        if selected_order == "All" or self.order_combo.currentIndex() == 0:
            # Show all families
            if hasattr(self, '_all_families'):
                self._family_completer_model.setStringList(self._all_families)
        else:
            # Show only families for selected order
            families = self._order_family_map.get(selected_order, [])
            self._family_completer_model.setStringList(sorted(families))
    
    def select_new_species_list(self):
        """Programmatically select the New Species List preset."""
        return self.select_preset_by_view_mode('new_species_list')
    
    def reset_to_normal_view(self):
        """Reset to normal view (clear special view mode)."""
        self.saved_combo.setCurrentIndex(0)
        self.clear_filters()
    
    def apply_theme(self):
        """Apply the current theme."""
        t = theme()
        self.setStyleSheet(f"background-color: {t.get('surface')}; border-bottom: 1px solid {t.get('border')};")

    def set_species_filter(self, species_name: str):
        """Set the species filter and apply it."""
        self.species_edit.setText(species_name)
        self._emit_filters()

    def set_order_filter(self, order_name: str):
        """Set the order filter and apply it."""
        idx = self.order_combo.findText(order_name)
        if idx >= 0:
            self.order_combo.setCurrentIndex(idx)
        self._emit_filters()

    def set_family_filter(self, family_name: str):
        """Set the family filter and apply it."""
        self.family_edit.setText(family_name)
        self._emit_filters()