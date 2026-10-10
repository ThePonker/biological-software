"""
Scheme Filter Bar Component.

Horizontal filter bar for recording scheme records with saved filters support.
Uses shared components for ComboFilterWidget, SavedFiltersMixin, and styling.
"""


from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QWidget, QCompleter
)
from PySide6.QtCore import Qt, Signal, QStringListModel, QDate, QMetaMethod

from ...utils.constants import VERIFICATION_STATUS_OPTIONS
from ...themes import theme
from ...core.config import TabColors  # Added import

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


class SchemeFilterBar(QFrame, SavedFiltersMixin):
    """Horizontal filter bar for recording scheme records."""
    
    filters_changed = Signal(dict)
    clear_all_requested = Signal()   # Clear All clicked: the tab clears everything
    save_filter_requested = Signal()
    special_view_selected = Signal(str)  # For consistency with other filter bars
    
    # How the record came in (services/filter_builder.SCHEME_SOURCES). Was iRecord / NBN /
    # Email compared with the stored source -- a dataset name -- so always 0 (SRCH8)
    SOURCE_OPTIONS = ['All', 'iRecord', 'NBN Atlas', 'Other']
    # Filled from the records (subfamily is empty on every scheme row on 9 Oct: the
    # July 2025 UKSI has no Cerambycidae subfamilies); disabled while there are none
    SUBFAMILY_OPTIONS = ['All']
    
    # No preset filters for scheme (can add later if needed)
    _preset_filters = []
    
    # Settings key for saved filters
    _settings_key = "scheme_saved_filters"
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._db = None
        self._accent = TabColors.RECORDING_SCHEME  # Fixed: use TabColors instead of hardcoded
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
        debounce_text(self.species_edit, self._emit_filters)   # one reload per pause, not per key
        
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
        debounce_text(self.location_edit, self._emit_filters)
        
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
        
        # Column 5: Order (placeholder - fixed to Coleoptera for Cerambycidae scheme)
        order_container = QWidget()
        order_container.setFixedWidth(COL_ORDER)
        order_box = QVBoxLayout(order_container)
        order_box.setContentsMargins(0, 0, 0, 0)
        order_box.setSpacing(4)
        order_box.addWidget(create_filter_label("Order", muted=True))
        order_placeholder = QLineEdit("Coleoptera")
        order_placeholder.setReadOnly(True)
        order_placeholder.setFixedHeight(STANDARD_INPUT_HEIGHT)
        order_placeholder.setStyleSheet(placeholder_style)
        order_box.addWidget(order_placeholder)
        filters_row.addWidget(order_container)
        
        # Column 6: Subfamily
        subfamily_container = QWidget()
        subfamily_container.setFixedWidth(COL_FAMILY)
        subfamily_box = QVBoxLayout(subfamily_container)
        subfamily_box.setContentsMargins(0, 0, 0, 0)
        subfamily_box.setSpacing(4)
        subfamily_box.addWidget(create_filter_label("Subfamily"))
        self.subfamily_combo = ComboFilterWidget(accent_color=self._accent)
        for subfamily in self.SUBFAMILY_OPTIONS:
            data = None if subfamily == 'All' else subfamily
            self.subfamily_combo.addItem(subfamily, data)
        self.subfamily_combo.currentTextChanged.connect(self._emit_filters)
        subfamily_box.addWidget(self.subfamily_combo)
        filters_row.addWidget(subfamily_container)
        
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
        
        # Column 8: Recorder
        recorder_container = QWidget()
        recorder_container.setFixedWidth(COL_RECORDER)
        recorder_box = QVBoxLayout(recorder_container)
        recorder_box.setContentsMargins(0, 0, 0, 0)
        recorder_box.setSpacing(4)
        recorder_box.addWidget(create_filter_label("Recorder"))
        self.recorder_edit = QLineEdit()
        self.recorder_edit.setPlaceholderText("Search...")
        self.recorder_edit.setFixedHeight(STANDARD_INPUT_HEIGHT)
        self.recorder_edit.setStyleSheet(f"QLineEdit {{ {input_style} }}")
        debounce_text(self.recorder_edit, self._emit_filters)
        recorder_box.addWidget(self.recorder_edit)
        filters_row.addWidget(recorder_container)
        
        # Column 9: Method (placeholder - not typically used for scheme)
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
        
        # Column 10: Source
        source_container = QWidget()
        source_container.setFixedWidth(COL_SOURCE)
        source_box = QVBoxLayout(source_container)
        source_box.setContentsMargins(0, 0, 0, 0)
        source_box.setSpacing(4)
        source_box.addWidget(create_filter_label("Source"))
        self.source_combo = ComboFilterWidget(accent_color=self._accent)
        for source in self.SOURCE_OPTIONS:
            data = None if source == 'All' else source
            self.source_combo.addItem(source, data)
        self.source_combo.currentTextChanged.connect(self._emit_filters)
        source_box.addWidget(self.source_combo)
        filters_row.addWidget(source_container)
        
        # Column 11: Verification Status
        status_container = QWidget()
        status_container.setFixedWidth(COL_VERIFICATION)
        status_box = QVBoxLayout(status_container)
        status_box.setContentsMargins(0, 0, 0, 0)
        status_box.setSpacing(4)
        status_box.addWidget(create_filter_label("Verification"))
        self.status_combo = ComboFilterWidget(accent_color=self._accent)
        self.status_combo.addItem("All", None)
        for status in VERIFICATION_STATUS_OPTIONS:
            self.status_combo.addItem(status, status)
        self.status_combo.currentTextChanged.connect(self._emit_filters)
        status_box.addWidget(self.status_combo)
        filters_row.addWidget(status_container)
        
        
        filters_row.addStretch()
        layout.addLayout(filters_row)
    
    def _emit_filters(self):
        """Emit current filters."""
        filters = self.get_filters()
        self.filters_changed.emit(filters)
    
    def get_filters(self) -> dict:
        """Get current filter values."""
        # Any date that is set counts: "year >= 2000" dropped every earlier date, and
        # 28,958 scheme records are older (OBS-14)
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
            'subfamily': self.subfamily_combo.currentData(),
            'vice_county': self.vc_combo.currentData(),
            'recorder': self.recorder_edit.text().strip(),
            'source': self.source_combo.currentData(),
            'status': self.status_combo.currentData(),
        }
    
    def _filter_widgets(self):
        return [self.species_edit, self.location_edit, self.date_from_edit,
                self.date_to_edit, self.subfamily_combo, self.vc_combo, self.recorder_edit,
                self.source_combo, self.status_combo]     # not saved_combo: its index 0
                                                             # only disables Delete

    def _set_quietly(self, change):
        """Run change() with every filter widget silent; the caller emits once."""
        widgets = self._filter_widgets()
        cancel_pending(self.species_edit, self.location_edit, self.recorder_edit)
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
        """Clear all filters and reload once (it reloaded once per widget: 9 loads of
        up to 110,510 records, 58 s on Wil's PC -- speed review 10 Oct 2026)."""
        def change():
            self.species_edit.clear()
            self.location_edit.clear()
            self.date_from_edit.clear()
            self.date_to_edit.clear()
            self.subfamily_combo.resetToFirst()
            self.vc_combo.resetToFirst()
            self.recorder_edit.clear()
            self.source_combo.resetToFirst()
            self.status_combo.resetToFirst()
            self.saved_combo.setCurrentIndex(0)
        self._set_quietly(change)
        self._emit_filters()
    
    def _apply_saved_filter(self, filters: dict):
        """Apply a saved filter configuration (one reload). Required by SavedFiltersMixin."""
        def change():
            self.species_edit.setText(filters.get('species', ''))
            self.location_edit.setText(filters.get('location', ''))
            self.date_from_edit.setIsoDate(filters.get('date_from'))   # setText does not exist
            self.date_to_edit.setIsoDate(filters.get('date_to'))
            self.recorder_edit.setText(filters.get('recorder', ''))

            for combo, key in [(self.subfamily_combo, 'subfamily'), (self.source_combo, 'source'),
                               (self.status_combo, 'status')]:
                val = filters.get(key, '')
                idx = combo.findData(val)
                if idx >= 0:
                    combo.setCurrentIndex(idx)

            vc = filters.get('vice_county', '')
            idx = self.vc_combo.findData(vc)
            if idx >= 0:
                self.vc_combo.setCurrentIndex(idx)
        self._set_quietly(change)
        self._emit_filters()
    
    def add_saved_filter(self, name: str, filters: dict):
        """Add a saved filter."""
        self._saved_filters.append({'name': name, 'filters': filters})
        self._save_filters_to_settings()
        self._populate_saved_filters_combo()
    
    def initialize_with_database(self, db):
        """Initialize completers and dropdowns from database."""
        self._db = db
        
        # Get date range for calendar defaults
        try:
            query = "SELECT MIN(date) as min_date, MAX(date) as max_date FROM recording_scheme WHERE date IS NOT NULL AND date <> ''"
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
            print(f"[SchemeFilterBar] Error getting date range: {e}")
        
        # Populate species completer
        try:
            query = "SELECT DISTINCT species_name FROM recording_scheme WHERE species_name IS NOT NULL ORDER BY species_name"
            results = db.execute_main(query)
            species_list = [row['species_name'] or row[0] for row in results if row[0]]
            self._species_completer_model.setStringList(species_list)
        except Exception as e:
            print(f"[SchemeFilterBar] Error loading species list: {e}")
        
        # Populate location completer
        try:
            query = "SELECT DISTINCT site_name FROM recording_scheme WHERE site_name IS NOT NULL ORDER BY site_name"
            results = db.execute_main(query)
            location_list = [row['site_name'] or row[0] for row in results if row[0]]
            self._location_completer_model.setStringList(location_list)
        except Exception as e:
            print(f"[SchemeFilterBar] Error loading location list: {e}")
        
        # Populate Vice Counties
        self._populate_vice_counties_from_data(db)

        # Subfamily and Verification from the records themselves (SRCH8)
        self._populate_choices_from_data(db)

    def _populate_choices_from_data(self, db):
        """Subfamily: the values recorded (none yet: the combo is disabled and says why).
        Verification: the main statuses recorded ("Accepted" covers "Accepted - correct")."""
        # Subfamily on its own: a failure loading the statuses skipped it (it stayed
        # enabled), and a disabled combo looked enabled (Wil 10 Oct)
        try:
            subfamilies = [r[0] for r in db.execute_main(
                "SELECT DISTINCT subfamily FROM recording_scheme "
                "WHERE subfamily IS NOT NULL AND TRIM(subfamily) <> '' ORDER BY subfamily")]
        except Exception as e:
            print(f"[SchemeFilterBar] Error loading subfamilies: {e}")
            subfamilies = []
        self.subfamily_combo.clear()
        self.subfamily_combo.addItem("All", None)
        for sf in subfamilies:
            self.subfamily_combo.addItem(sf, sf)
        self.subfamily_combo.set_unavailable(
            "" if subfamilies else "No subfamily data on scheme records")
        try:
            from ...services.filter_builder import tab_values
            statuses = tab_values(db.main_db_path, 'recording_scheme', only=('statuses',))['statuses']
        except Exception as e:
            print(f"[SchemeFilterBar] Error loading statuses: {e}")
            return
        self.status_combo.clear()
        self.status_combo.addItem("All", None)
        for st in statuses:
            self.status_combo.addItem(st, st)

    def _populate_vice_counties_from_data(self, db):
        """Populate vice counties dropdown from existing data."""
        # Use short names for compact display
        vc_short_names = VCLookupService.VC_SHORT_NAMES
        
        self.vc_combo.clear()
        self.vc_combo.addItem("All", "")
        
        try:
            query = "SELECT DISTINCT vc_number FROM recording_scheme WHERE vc_number IS NOT NULL ORDER BY vc_number"
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
            print(f"[SchemeFilterBar] Error loading vice counties: {e}")
    
    def apply_theme(self):
        """Apply the current theme."""
        t = theme()
        self.setStyleSheet(f"background-color: {t.get('surface')}; border-bottom: 1px solid {t.get('border')};")
        
        # Update accent color reference
        self._accent = TabColors.RECORDING_SCHEME
        
        # Update date widgets
        self.date_from_edit.apply_theme()
        self.date_to_edit.apply_theme()
        
        # Update combo widgets
        self.subfamily_combo.apply_theme()
        self.vc_combo.apply_theme()
        self.source_combo.apply_theme()
        self.status_combo.apply_theme()
        
        # Update clear button
        self.clear_btn.setStyleSheet(get_clear_button_style())
