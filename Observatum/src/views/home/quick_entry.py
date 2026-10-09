"""
Quick Entry Form Component.

Simple form for entering observation records with sticky field support.

REFACTORED: Field creation methods extracted to quick_entry_fields_mixin.py
FIXED: QSpinBox arrow buttons now display properly
"""

from typing import Optional, Dict, Any, List

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout,
    QLabel, QWidget, QCheckBox, QMessageBox
)
from PySide6.QtCore import Signal, QDate, QSettings

from .card import Card
from .status_bar import StatusBar
from .quick_entry_fields_mixin import (
    QuickEntryFieldsMixin
)
from ...models.database import get_database
from ...models.observation import ObservationModel, Observation
from ...services.search_service import get_search_service
from ...services.grid_ref_service import GridRefService
from ...services.vc_lookup_service import get_vc_service
from ...themes import theme


class QuickEntryForm(QuickEntryFieldsMixin, Card):
    """Simple form for entering observation records."""
    
    record_saved = Signal(dict)
    
    # Fields that can be sticky (including species)
    STICKY_FIELDS = ['species', 'date', 'grid_ref', 'location', 'recorder', 'determiner', 
                     'sex', 'stage', 'quantity', 'certainty', 'method', 'comment', 'record_type']
    
    def __init__(self, parent=None):
        super().__init__("Quick Single Observation", parent)
        self._selected_species: Optional[Dict] = None
        self._sticky_checkboxes: Dict[str, QCheckBox] = {}
        self._setup_ui()
        self._load_sticky_settings()
        self._load_default_settings()
    
    def _setup_ui(self):
        """Set up the form UI with all fields."""
        t = theme()
        
        self.setAutoFillBackground(True)
        self.setStyleSheet(self._get_form_stylesheet())
        
        form_layout = QVBoxLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(8)
        
        # Add all fields with sticky toggles
        field_configs = [
            ("Species", self._create_species_field(), 'species'),
            ("Date", self._create_date_field(), 'date'),
            ("Grid Ref", self._create_grid_ref_field(), 'grid_ref'),
            ("Location", self._create_location_field(), 'location'),
            ("Recorder", self._create_recorder_field(), 'recorder'),
            ("Determiner", self._create_determiner_field(), 'determiner'),
            ("Sex", self._create_sex_field(), 'sex'),
            ("Stage", self._create_stage_field(), 'stage'),
            ("Quantity", self._create_quantity_field(), 'quantity'),
            ("Certainty", self._create_certainty_field(), 'certainty'),
            ("Method", self._create_method_field(), 'method'),
            ("Comment", self._create_comment_field(), 'comment'),
            ("Data Type", self._create_record_type_field(), 'record_type'),
            ("", self._create_never_upload_field(), None),
        ]
        
        for label, widget, sticky_key in field_configs:
            self._add_field_row(form_layout, label, widget, sticky=sticky_key)
        
        self.add_layout(form_layout)
        
        # Status bar
        self.status_bar = StatusBar()
        self.add_widget(self.status_bar)
        
        self.add_stretch()
        
        # Buttons
        self._setup_buttons()
        
        # Reference boxes
        self._setup_reference_boxes()
    
    def _get_form_stylesheet(self) -> str:
        """Get the form stylesheet. Note: QSpinBox styled separately to preserve native arrows."""
        t = theme()
        return f"""
            QFrame {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_lg')};
            }}
            QLineEdit, QDateEdit, QComboBox {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_sm')};
                padding: 6px 10px;
                color: {t.get('text_primary')};
                font-size: {t.font_size('base')};
            }}
            QLineEdit:focus, QDateEdit:focus, QComboBox:focus {{
                border: 2px solid {t.get('focus_border')};
                padding: 5px 9px;
            }}
        """
    
    def _add_field_row(self, layout, label_text: str, field_widget: QWidget, sticky: str = None):
        """Add a field row with label and optional sticky toggle."""
        t = theme()
        
        row = QHBoxLayout()
        row.setSpacing(8)
        
        label = QLabel(label_text)
        label.setFixedWidth(90)
        label.setStyleSheet(f"font-size: {t.font_size('sm')}; font-weight: 500; color: {t.get('text_secondary')}; background-color: transparent; border: none;")
        row.addWidget(label)
        
        row.addWidget(field_widget, 1)
        
        if sticky:
            sticky_cb = QCheckBox()
            sticky_cb.setToolTip("Sticky: Keep this value after saving")
            sticky_cb.setStyleSheet(self._get_sticky_checkbox_style())
            sticky_cb.stateChanged.connect(self._save_sticky_settings)
            row.addWidget(sticky_cb)
            self._sticky_checkboxes[sticky] = sticky_cb
        
        layout.addLayout(row)
    
    def _get_sticky_checkbox_style(self) -> str:
        """Get the green toggle style for sticky checkboxes."""
        t = theme()
        return f"""
            QCheckBox {{ spacing: 0px; }}
            QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 3px; }}
            QCheckBox::indicator:unchecked {{ border: 2px solid {t.get('border_strong')}; background-color: {t.get('surface')}; }}
            QCheckBox::indicator:unchecked:hover {{ border: 2px solid {t.get('success')}; }}
            QCheckBox::indicator:checked {{ border: 2px solid {t.get('success')}; background-color: {t.get('success')}; }}
        """
    
    def _load_sticky_settings(self):
        """Load sticky checkbox states from QSettings."""
        settings = QSettings()
        settings.beginGroup("QuickEntry")
        for field in self.STICKY_FIELDS:
            if field in self._sticky_checkboxes:
                is_sticky = settings.value(f"sticky_{field}", False, type=bool)
                self._sticky_checkboxes[field].setChecked(is_sticky)
        settings.endGroup()
    
    def _save_sticky_settings(self):
        """Save sticky checkbox states to QSettings."""
        settings = QSettings()
        settings.beginGroup("QuickEntry")
        for field in self.STICKY_FIELDS:
            if field in self._sticky_checkboxes:
                settings.setValue(f"sticky_{field}", self._sticky_checkboxes[field].isChecked())
        settings.endGroup()
    
    def _load_default_settings(self):
        """Load default values from General Settings."""
        settings = QSettings()
        default_recorder = settings.value("general/default_recorder", "")
        if default_recorder and not self.recorder_edit.text():
            self.recorder_edit.setText(default_recorder)
        
        default_determiner = settings.value("general/default_determiner", "")
        if default_determiner and not self.determiner_edit.text():
            self.determiner_edit.setText(default_determiner)
    
    def _on_species_selected(self, species_data: dict):
        """Handle species selection from search."""
        self._selected_species = species_data
    
    def _on_save_clicked(self):
        """Handle save button click - validates and saves to database."""
        if not self._selected_species or not self._selected_species.get('tvk'):
            QMessageBox.warning(
                self, "Validation Error", 
                "Please select a species from the search dropdown.\n\n"
                "Type a species name and select from the list."
            )
            return
        
        form_data = self._collect_form_data()
        errors = self._validate_form_data(form_data)
        if errors:
            QMessageBox.warning(self, "Validation Errors", 
                "Please correct:\n\n• " + "\n• ".join(errors))
            return
        
        observation = self._create_observation(form_data)
        
        try:
            db = get_database()
            model = ObservationModel(db)
            new_id = model.create(observation)
            
            if new_id:
                species_name = self._selected_species.get('scientific_name', 'Unknown')
                self.status_bar.show_success(f"Record saved - {species_name}")
                
                tvk = self._selected_species.get('tvk')
                if tvk:
                    search_service = get_search_service()
                    search_service.add_recorded_tvk(tvk)
                
                self.record_saved.emit(form_data)
                self._clear_after_save()
            else:
                self.status_bar.show_error("Failed to save")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
    
    def _collect_form_data(self) -> Dict[str, Any]:
        """Collect form data."""
        return {
            'species_name': self._selected_species.get('scientific_name', ''),
            'species_tvk': self._selected_species.get('tvk'),
            'common_name': self._selected_species.get('common_name'),
            'order_name': self._selected_species.get('order'),
            'family': self._selected_species.get('family'),
            'date': self.date_edit.date().toString("yyyy-MM-dd"),
            'grid_ref': self.grid_ref_edit.text().strip().upper(),
            'site_name': self.location_edit.text().strip(),
            'recorder': self.recorder_edit.text().strip(),
            'determiner': self.determiner_edit.text().strip(),
            'sex': self.sex_combo.currentText() or None,
            'stage': self.stage_combo.currentText() or None,
            'quantity': self.quantity_spin.value(),
            'certainty': self.certainty_combo.currentText() or None,
            'method': self.method_combo.currentText() or None,
            'comment': self.comment_edit.text().strip() or None,
            'record_type': self.record_type_combo.currentText(),
            'never_upload_to_irecord': 1 if self.never_upload_check.isChecked() else 0,
        }
    
    def _validate_form_data(self, data: Dict[str, Any]) -> List[str]:
        """Validate form data."""
        errors = []
        
        grid_ref = data.get('grid_ref', '')
        if not grid_ref:
            errors.append("Grid reference is required")
        elif not GridRefService.validate(grid_ref):
            errors.append(f"Invalid grid reference: {grid_ref}")
        
        if not data.get('site_name'):
            errors.append("Location is required")
        if not data.get('recorder'):
            errors.append("Recorder is required")
        if not data.get('determiner'):
            errors.append("Determiner is required")
        
        return errors
    
    def _create_observation(self, data: Dict[str, Any]) -> Observation:
        """Create observation object."""
        grid_precision = None
        vice_county = None
        vc_number = None
        if data.get('grid_ref'):
            grid_precision = GridRefService.get_precision(data['grid_ref'])
            # Look up vice county from grid reference
            vc_service = get_vc_service()
            vc_info = vc_service.get_vice_county(data['grid_ref'])
            if vc_info:
                vice_county = vc_info.get('name')
                vc_number = vc_info.get('number')
        
        comment_parts = []
        if data.get('comment'):
            comment_parts.append(data['comment'])
        if data.get('certainty'):
            comment_parts.append(f"Certainty: {data['certainty']}")
        
        combined_comment = "; ".join(comment_parts) if comment_parts else None
        
        return Observation(
            species_name=data['species_name'],
            species_tvk=data['species_tvk'],
            common_name=data['common_name'],
            order_name=data.get('order_name'),
            family=data.get('family'),
            date=data['date'],
            date_type='D',
            grid_ref=data['grid_ref'] or None,
            grid_precision=grid_precision,
            site_name=data['site_name'] or None,
            vice_county=vice_county,
            vc_number=vc_number,
            recorder=data['recorder'] or None,
            determiner=data['determiner'] or None,
            sex=data['sex'] if data['sex'] else None,
            stage=data['stage'] if data['stage'] else None,
            quantity=data['quantity'],
            method=data['method'] if data.get('method') else None,
            comment=combined_comment,
            verification_status='Pending',
            record_type=data.get('record_type', 'Personal'),
            never_upload_to_irecord=data.get('never_upload_to_irecord', 0),
        )
    
    def _clear_after_save(self):
        """Clear form after save, respecting sticky fields."""
        settings = QSettings()
        default_recorder = settings.value("general/default_recorder", "")
        default_determiner = settings.value("general/default_determiner", "")
        
        field_defaults = {
            'species': (lambda: (setattr(self, '_selected_species', None), self.species_search.clear())),
            'date': (lambda: self.date_edit.setDate(QDate.currentDate())),
            'grid_ref': (lambda: self.grid_ref_edit.clear()),
            'location': (lambda: self.location_edit.clear()),
            'recorder': (lambda: self.recorder_edit.setText(default_recorder)),
            'determiner': (lambda: self.determiner_edit.setText(default_determiner)),
            'sex': (lambda: self.sex_combo.setCurrentIndex(0)),
            'stage': (lambda: self.stage_combo.setCurrentIndex(0)),
            'quantity': (lambda: self.quantity_spin.setValue(1)),
            'certainty': (lambda: self.certainty_combo.setCurrentIndex(0)),
            'method': (lambda: self.method_combo.setCurrentIndex(0)),
            'comment': (lambda: self.comment_edit.clear()),
            'record_type': (lambda: self.record_type_combo.setCurrentIndex(0)),
        }
        
        for field, clear_fn in field_defaults.items():
            if not self._sticky_checkboxes.get(field, QCheckBox()).isChecked():
                clear_fn()
    
    def clear_form(self):
        """Clear all fields."""
        self._selected_species = None
        self.species_search.clear()
        self.date_edit.setDate(QDate.currentDate())
        self.grid_ref_edit.clear()
        self.location_edit.clear()
        
        settings = QSettings()
        self.recorder_edit.setText(settings.value("general/default_recorder", ""))
        self.determiner_edit.setText(settings.value("general/default_determiner", ""))
        
        self.sex_combo.setCurrentIndex(0)
        self.stage_combo.setCurrentIndex(0)
        self.quantity_spin.setValue(1)
        self.certainty_combo.setCurrentIndex(0)
        self.method_combo.setCurrentIndex(0)
        self.comment_edit.clear()
    
    def set_species(self, species_data: dict):
        """Set species in form."""
        self._selected_species = species_data
        self.species_search.set_species(species_data)
    
    def reload_defaults(self):
        """Reload default settings."""
        settings = QSettings()
        if not self.recorder_edit.text():
            self.recorder_edit.setText(settings.value("general/default_recorder", ""))
        if not self.determiner_edit.text():
            self.determiner_edit.setText(settings.value("general/default_determiner", ""))
    
    def apply_theme(self):
        """Apply theme."""
        self.setStyleSheet(self._get_form_stylesheet())
        
        style = self._get_sticky_checkbox_style()
        for cb in self._sticky_checkboxes.values():
            cb.setStyleSheet(style)
        
        # Update quantity spinner theme
        if hasattr(self, 'quantity_spin') and hasattr(self.quantity_spin, 'apply_theme'):
            self.quantity_spin.apply_theme()
