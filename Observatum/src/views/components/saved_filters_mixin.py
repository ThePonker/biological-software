"""
Saved Filters Mixin.

Provides saved filter functionality for filter bar components.
Handles loading, saving, selecting, and deleting saved filters via QSettings.

13 Oct 2026: this top row is the only place to save filters. A saved filter holds the
bar's values and, under 'wizard', the Filter Wizard's chips (attach_wizard).
"""

from typing import List, Dict

from PySide6.QtWidgets import QPushButton, QMessageBox, QInputDialog
from PySide6.QtCore import QSettings

from ...themes import theme
from ...services.filter_builder import as_list
from ...services.saved_filters_service import SavedFiltersService

# Chip keys holding one value, not a list (the rest come back as lists)
_SCALAR_CHIP_KEYS = ('date_from', 'date_to', 'year')


def normalise_chips(chips) -> Dict:
    """Wizard chips as the wizard holds them. QSettings can hand a one-element list back
    as a bare string, so list-valued keys go through as_list again."""
    out = {}
    for key, value in (chips or {}).items():
        out[key] = value if key in _SCALAR_CHIP_KEYS else as_list(value)
    return out


class SavedFiltersMixin:
    """
    Mixin providing saved filter functionality for filter bars.
    
    Requirements for using class:
    - Must have self.saved_combo (QComboBox)
    - Must have self.save_filter_btn (QPushButton)
    - Must have self.delete_filter_btn (QPushButton)
    - Must implement get_filters() -> dict
    - Must implement _apply_saved_filter(filters: dict)
    - Must set self._settings_key before calling _init_saved_filters()
    - Optionally set self._preset_filters list before calling _init_saved_filters()
    - Optionally set self._wizard_tab ("observations", ...) to move that tab's old
      wizard-saved filters (saved_filters.json) into this list, once
    
    Signals to define in using class:
    - special_view_selected = Signal(str) - if using preset view modes
    """
    
    def _init_saved_filters(self):
        """
        Initialize saved filters system. Call this in __init__ after UI setup.
        
        Before calling, ensure:
        - self._settings_key is set (e.g., 'observation_saved_filters')
        - self._preset_filters is set (can be empty list)
        - UI elements are created (saved_combo, save_filter_btn, delete_filter_btn)
        """
        self._saved_filters: List[Dict] = []
        self._wizard_get = None
        self._wizard_set = None
        self._load_saved_filters()
        self._move_wizard_saved_filters()
        self._populate_saved_filters_combo()
        
        # Connect signals
        self.saved_combo.currentIndexChanged.connect(self._on_saved_filter_selected)
        self.save_filter_btn.clicked.connect(self._on_save_filter)
        self.delete_filter_btn.clicked.connect(self._on_delete_filter)
    
    def attach_wizard(self, get_chips, set_chips):
        """Let saved filters carry the tab's Filter Wizard chips. get_chips() returns the
        wizard's get_all_filters(); set_chips(dict) sets the tab's wizard state with no
        reload (the bar's own filters_changed does the one reload)."""
        self._wizard_get = get_chips
        self._wizard_set = set_chips

    def _move_wizard_saved_filters(self):
        """One-off (13 Oct 2026): the wizard's own saved filters (saved_filters.json, left
        untouched) are appended to this list as {'wizard': config}, then a flag stops it."""
        tab = getattr(self, '_wizard_tab', None)
        if not tab:
            return
        flag = f"{self._settings_key}_wizard_moved"
        settings = QSettings()
        if settings.value(flag, False, type=bool):
            return
        try:
            entries = SavedFiltersService().get_all_filters(tab=tab)
        except Exception as e:
            print(f"[SavedFilters] Could not read wizard filters: {e}")
            return
        names = {sf['name'] for sf in self._saved_filters}
        for name, entry in sorted(entries.items()):
            new_name = name
            while new_name in names:
                new_name += " (wizard)"
            names.add(new_name)
            self._saved_filters.append(
                {'name': new_name, 'filters': {'wizard': dict(entry.get('config') or {})}})
        self._save_filters_to_settings()
        settings.setValue(flag, True)

    def _load_saved_filters(self):
        """Load saved filters from QSettings."""
        settings = QSettings()
        count = settings.beginReadArray(self._settings_key)
        for i in range(count):
            settings.setArrayIndex(i)
            name = settings.value("name")
            filters = settings.value("filters", {})
            self._saved_filters.append({'name': name, 'filters': filters})
        settings.endArray()
    
    def _save_filters_to_settings(self):
        """Persist saved filters to QSettings."""
        settings = QSettings()
        settings.beginWriteArray(self._settings_key)
        for i, sf in enumerate(self._saved_filters):
            settings.setArrayIndex(i)
            settings.setValue("name", sf['name'])
            settings.setValue("filters", sf['filters'])
        settings.endArray()
    
    def _populate_saved_filters_combo(self):
        """Populate the saved filters dropdown with presets and user filters."""
        self.saved_combo.clear()
        self.saved_combo.addItem("-- Select saved filter --", None)
        
        # Add preset filters first (if any)
        preset_filters = getattr(self, '_preset_filters', [])
        for preset in preset_filters:
            self.saved_combo.addItem(preset['name'], preset)
        
        # Add separator if there are user filters
        if self._saved_filters and preset_filters:
            self.saved_combo.insertSeparator(len(preset_filters) + 1)
        
        # Add user-saved filters
        for sf in self._saved_filters:
            self.saved_combo.addItem(sf['name'], sf)
    
    def _on_saved_filter_selected(self, index: int):
        """Handle saved filter selection."""
        if index <= 0:
            self.delete_filter_btn.setEnabled(False)
            return
        
        data = self.saved_combo.currentData()
        if not data:
            self.delete_filter_btn.setEnabled(False)
            return
        
        # Check if it's a special view mode (like New Species List)
        if data.get('view_mode'):
            if hasattr(self, 'special_view_selected'):
                self.special_view_selected.emit(data['view_mode'])
            self.delete_filter_btn.setEnabled(False)
            return
        
        # Check if it's a preset (cannot be deleted)
        is_preset = data.get('is_preset', False)
        self.delete_filter_btn.setEnabled(not is_preset)
        
        # Apply the filters
        filters = data.get('filters', {})
        if filters:
            # Wizard chips first (no reload), then the bar's one reload applies both.
            # No 'wizard' key = no chips: the wizard is cleared.
            if self._wizard_set:
                self._wizard_set(normalise_chips(filters.get('wizard')))
            self._apply_saved_filter(filters)
    
    def _on_save_filter(self):
        """Save current filter configuration."""
        name, ok = QInputDialog.getText(
            self, "Save Filter",
            "Enter a name for this filter:"
        )
        
        if ok and name:
            filters = dict(self.get_filters())
            chips = self._wizard_get() if self._wizard_get else None
            if chips:
                filters['wizard'] = dict(chips)
            self._saved_filters.append({'name': name, 'filters': filters})
            self._save_filters_to_settings()
            self._populate_saved_filters_combo()
            
            # Select the newly saved filter
            idx = self.saved_combo.findText(name)
            if idx >= 0:
                self.saved_combo.setCurrentIndex(idx)
    
    def _on_delete_filter(self):
        """Delete the currently selected saved filter."""
        index = self.saved_combo.currentIndex()
        if index <= 0:
            return
        
        # Check if it's a preset (cannot delete presets)
        data = self.saved_combo.currentData()
        if data and data.get('is_preset', False):
            QMessageBox.information(
                self, "Cannot Delete",
                "This is a built-in preset filter and cannot be deleted."
            )
            return
        
        name = self.saved_combo.currentText()
        result = QMessageBox.question(
            self, "Delete Filter",
            f"Delete saved filter '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if result == QMessageBox.StandardButton.Yes:
            # Calculate the index in _saved_filters
            # Account for: default item (1) + presets + separator (if presets exist)
            preset_count = len(getattr(self, '_preset_filters', []))
            separator_offset = 1 if preset_count > 0 and self._saved_filters else 0
            user_filter_index = index - 1 - preset_count - separator_offset
            
            if 0 <= user_filter_index < len(self._saved_filters):
                del self._saved_filters[user_filter_index]
                self._save_filters_to_settings()
                self._populate_saved_filters_combo()
            
            self.saved_combo.setCurrentIndex(0)
    
    def add_saved_filter(self, name: str, filters: dict):
        """Programmatically add a new saved filter."""
        self._saved_filters.append({'name': name, 'filters': filters})
        self._save_filters_to_settings()
        self._populate_saved_filters_combo()
    
    def select_preset_by_view_mode(self, view_mode: str) -> bool:
        """
        Select a preset filter by its view_mode.
        Returns True if found and selected, False otherwise.
        """
        for i in range(self.saved_combo.count()):
            data = self.saved_combo.itemData(i)
            if data and data.get('view_mode') == view_mode:
                self.saved_combo.setCurrentIndex(i)
                return True
        return False


def create_saved_filter_buttons(parent, accent_color: str = None) -> tuple:
    """
    Create styled Save and Delete buttons for saved filters.
    
    Returns:
        tuple: (save_button, delete_button)
    """
    t = theme()
    
    save_btn = QPushButton("Save Current")
    save_btn.setStyleSheet(f"""
        QPushButton {{
            color: {t.get('success')};
            border: 1px solid {t.get('separator')};
            border-radius: {t.get('radius_sm')};
            padding: 3px 10px;
            background: {t.get('surface')};
            font-size: 11px;
        }}
        QPushButton:hover:enabled {{
            background-color: {t.get('success_bg')};
            border-color: {t.get('success')};
        }}
        QPushButton:disabled {{
            color: {t.get('text_muted')};
            border-color: {t.get('border')};
        }}
    """)
    
    delete_btn = QPushButton("Delete")
    delete_btn.setStyleSheet(f"""
        QPushButton {{
            color: {t.get('error')};
            border: 1px solid {t.get('separator')};
            border-radius: {t.get('radius_sm')};
            padding: 3px 10px;
            background: {t.get('surface')};
            font-size: 11px;
        }}
        QPushButton:hover:enabled {{
            background-color: {t.get('error_bg')};
            border-color: {t.get('error')};
        }}
        QPushButton:disabled {{
            color: {t.get('text_muted')};
            border-color: {t.get('border')};
        }}
    """)
    delete_btn.setEnabled(False)
    
    return save_btn, delete_btn
