"""
Saved Filters Mixin.

Provides saved filter functionality for filter bar components.
Handles loading, saving, selecting, and deleting saved filters via QSettings.
"""

from typing import List, Dict

from PySide6.QtWidgets import QPushButton, QMessageBox, QInputDialog
from PySide6.QtCore import QSettings

from ...themes import theme


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
        self._load_saved_filters()
        self._populate_saved_filters_combo()
        
        # Connect signals
        self.saved_combo.currentIndexChanged.connect(self._on_saved_filter_selected)
        self.save_filter_btn.clicked.connect(self._on_save_filter)
        self.delete_filter_btn.clicked.connect(self._on_delete_filter)
    
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
            self._apply_saved_filter(filters)
    
    def _on_save_filter(self):
        """Save current filter configuration."""
        name, ok = QInputDialog.getText(
            self, "Save Filter",
            "Enter a name for this filter:"
        )
        
        if ok and name:
            filters = self.get_filters()
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
