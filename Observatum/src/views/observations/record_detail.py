"""
Record Detail Dialog for Observatum V2.

Modal dialog for viewing and editing observation records.

REFACTORED: UI section builders extracted to record_detail_ui_mixin.py
"""

from typing import Optional, Dict

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QComboBox, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QDate

from .record_detail_ui_mixin import RecordDetailUIMixin, VERIFICATION_OPTIONS
from ...models.database import get_database
from ...models.observation import ObservationModel, Observation
from ...themes import theme


class RecordDetailDialog(RecordDetailUIMixin, QDialog):
    """Modal dialog for viewing/editing observation record details."""
    
    record_updated = Signal(dict)
    record_deleted = Signal(int)
    species_profile_requested = Signal(str, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._record: Optional[Dict] = None
        self._edit_mode = False
        self._taxonomy_data: Optional[Dict] = None
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Set up the user interface."""
        self.setWindowTitle("Record Detail")
        self.setModal(True)
        self.setMinimumSize(600, 680)
        self.resize(700, 700)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Build UI sections using mixin methods
        self._build_species_header(layout)
        self._build_species_edit_section(layout)
        self._build_taxonomy_row(layout)
        self._build_collection_status(layout)
        self._build_details_grid(layout)
        self._build_verification_section(layout)
        self._build_irecord_section(layout)
        self._build_action_buttons(layout)
    
    def _connect_signals(self):
        """Connect widget signals."""
        self.edit_btn.clicked.connect(self._on_edit_clicked)
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        self.save_btn.clicked.connect(self._on_save_clicked)
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        self.species_profile_btn.clicked.connect(self._on_profile_clicked)
        self.allow_species_change.stateChanged.connect(
            lambda state: self.species_edit_container.setVisible(state == Qt.CheckState.Checked.value)
        )
    
    def _on_profile_clicked(self):
        """Handle species profile button click."""
        if self._record:
            tvk = self._record.get('species_tvk', '')
            name = self._record.get('species_name', '')
            self.species_profile_requested.emit(tvk, name)
    
    def set_record(self, record: Dict):
        """Set the record to display/edit."""
        self._record = record
        self._edit_mode = False
        self._set_edit_mode(False)
        self._populate_fields()
        self._load_taxonomy()
        self._check_collection_status()
    
    def _load_taxonomy(self):
        """Load taxonomy from UKSI."""
        if not self._record:
            return
        
        tvk = self._record.get('species_tvk')
        if not tvk:
            return
        
        try:
            from ...models.uksi import UKSIModel
            db = get_database()
            uksi = UKSIModel(db)
            species = uksi.get_species_by_tvk(tvk)
            if species:
                self._taxonomy_data = {
                    'class': getattr(species, 'class_name', None) or 'Insecta',
                    'order': getattr(species, 'order_name', None),
                    'family': getattr(species, 'family', None),
                }
                self.class_value.setText(self._taxonomy_data.get('class', '-') or '-')
                self.order_value.setText(self._taxonomy_data.get('order', '-') or '-')
                self.family_value.setText(self._taxonomy_data.get('family', '-') or '-')
        except Exception as e:
            print(f"Error loading taxonomy: {e}")
    
    def _check_collection_status(self):
        """Check if species is in collection."""
        t = theme()
        
        if not self._record:
            return
        
        tvk = self._record.get('species_tvk')
        if not tvk:
            return
        
        try:
            db = get_database()
            query = "SELECT COUNT(*) FROM specimens WHERE species_tvk = ?"
            result = db.execute_main(query, (tvk,))
            count = result[0][0] if result else 0
            
            if count > 0:
                self.collection_frame.setStyleSheet(f"""
                    QFrame {{
                        background-color: {t.get('success_bg')};
                        border: 1px solid {t.get('success')};
                        border-radius: {t.get('radius_md')};
                        padding: 8px;
                    }}
                """)
                self.collection_icon.setText("✓")
                self.collection_icon.setStyleSheet(f"color: {t.get('success')}; font-weight: bold; font-size: {t.font_size('xl')};")
                self.collection_text.setText(f"In Collection ({count} specimen{'s' if count != 1 else ''})")
                self.collection_text.setStyleSheet(f"color: {t.get('success_text')}; font-weight: bold;")
            else:
                self.collection_frame.setStyleSheet(f"""
                    QFrame {{
                        background-color: {t.get('warning_bg')};
                        border: 1px solid {t.get('warning')};
                        border-radius: {t.get('radius_md')};
                        padding: 8px;
                    }}
                """)
                self.collection_icon.setText("!")
                self.collection_icon.setStyleSheet(f"color: {t.get('warning')}; font-weight: bold; font-size: {t.font_size('xl')};")
                self.collection_text.setText("Not in Collection")
                self.collection_text.setStyleSheet(f"color: {t.get('warning_text')}; font-weight: bold;")
        except Exception as e:
            print(f"Error checking collection status: {e}")
    
    def _populate_fields(self):
        """Populate form fields from record."""
        if not self._record:
            return
        
        # Species
        self.species_label.setText(self._record.get('species_name', 'Unknown'))
        self.common_name_label.setText(self._record.get('common_name', ''))
        self.species_edit.setText(self._record.get('species_name', ''))
        
        # Taxonomy
        if self._taxonomy_data:
            self.class_value.setText(self._taxonomy_data.get('class', '-') or '-')
            self.order_value.setText(self._taxonomy_data.get('order', '-') or '-')
            self.family_value.setText(self._taxonomy_data.get('family', '-') or '-')
        else:
            self.class_value.setText('-')
            self.order_value.setText('-')
            self.family_value.setText('-')
        
        # Date
        date_str = self._record.get('date', '')
        if date_str:
            try:
                parts = date_str.split('-')
                self.date_edit.setDate(QDate(int(parts[0]), int(parts[1]), int(parts[2])))
            except:
                self.date_edit.setDate(QDate.currentDate())
        
        # Other fields
        self.grid_ref_edit.setText(self._record.get('grid_ref', '') or '')
        self.location_edit.setText(self._record.get('site_name', '') or '')
        
        vc_num = self._record.get('vc_number', '')
        self.vc_label.setText(str(vc_num) if vc_num else '-')
        
        self.quantity_spin.setValue(self._record.get('quantity', 1) or 1)
        
        self._set_combo(self.sex_combo, self._record.get('sex', ''))
        self._set_combo(self.stage_combo, self._record.get('stage', ''))
        
        self.recorder_edit.setText(self._record.get('recorder', '') or '')
        self.determiner_edit.setText(self._record.get('determiner', '') or '')
        
        self._set_combo(self.method_combo, self._record.get('method', ''))
        
        # Verification
        status = self._record.get('verification_status', '') or 'Pending'
        self._update_verification_badge(status)
        self._set_combo(self.verification_combo, status)
        
        # iRecord
        irecord = self._record.get('irecord_id')
        if irecord:
            self.irecord_value.setText(f"iBRC{irecord}")
            self.irecord_widget.setVisible(True)
        else:
            self.irecord_widget.setVisible(False)
    
    def _set_combo(self, combo: QComboBox, value: str):
        """Set combo box value."""
        idx = combo.findText(value or '')
        combo.setCurrentIndex(idx if idx >= 0 else 0)
    
    def _update_verification_badge(self, status: str):
        """Update the verification status badge."""
        t = theme()
        styles = {
            'Accepted': (f'background: {t.get("success_bg")}; color: {t.get("success_text")};', 'Accepted'),
            'Unconfirmed': (f'background: {t.get("background")}; color: {t.get("text_secondary")};', 'Unconfirmed'),
            'Pending': (f'background: {t.get("warning_bg")}; color: {t.get("warning_text")};', 'Pending'),
            'Rejected': (f'background: {t.get("error_bg")}; color: {t.get("error")};', 'Rejected'),
        }
        style, text = styles.get(status, (f'background: {t.get("background")}; color: {t.get("text_secondary")};', status or 'Unknown'))
        self.verification_badge.setStyleSheet(f"padding: 4px 8px; border-radius: {t.get('radius_sm')}; font-weight: bold; font-size: {t.font_size('sm')}; {style}")
        self.verification_badge.setText(text)
    
    def _set_edit_mode(self, edit_mode: bool):
        """Toggle edit mode for the dialog."""
        self._edit_mode = edit_mode
        
        # Species edit controls
        self.species_edit_frame.setVisible(edit_mode)
        self.allow_species_change.setChecked(False)
        self.species_edit_container.setVisible(False)
        
        # Form fields
        self.date_edit.setEnabled(edit_mode)
        self.grid_ref_edit.setReadOnly(not edit_mode)
        self.location_edit.setReadOnly(not edit_mode)
        self.quantity_spin.setEnabled(edit_mode)
        self.sex_combo.setEnabled(edit_mode)
        self.stage_combo.setEnabled(edit_mode)
        self.recorder_edit.setReadOnly(not edit_mode)
        self.determiner_edit.setReadOnly(not edit_mode)
        self.method_combo.setEnabled(edit_mode)
        
        # Verification
        self.verification_badge.setVisible(not edit_mode)
        self.verification_combo.setVisible(edit_mode)
        
        # Buttons
        self.edit_btn.setVisible(not edit_mode)
        self.save_btn.setVisible(edit_mode)
        self.cancel_btn.setText("Cancel" if edit_mode else "Close")
        
        self.setWindowTitle("Edit Record" if edit_mode else "Record Detail")
    
    def _on_edit_clicked(self):
        """Handle edit button click."""
        self._set_edit_mode(True)
    
    def _on_cancel_clicked(self):
        """Handle cancel/close button click."""
        if self._edit_mode:
            self._populate_fields()
            self._set_edit_mode(False)
        else:
            self.reject()
    
    def _on_save_clicked(self):
        """Handle save button click."""
        if not self._record or not self._record.get('id'):
            return
        
        # Handle species change
        new_species_name = None
        new_species_tvk = None
        new_common_name = None
        
        if self.allow_species_change.isChecked():
            new_species_name = self.species_edit.text().strip()
            if not new_species_name:
                QMessageBox.warning(self, "Error", "Species name cannot be empty.")
                return
            
            if new_species_name != self._record.get('species_name'):
                try:
                    from ...models.uksi import UKSIModel
                    db = get_database()
                    uksi = UKSIModel(db)
                    species = uksi.get_species_by_name(new_species_name)
                    if species:
                        new_species_tvk = species.tvk
                        new_common_name = species.common_name
                    else:
                        reply = QMessageBox.question(
                            self, "Species Not Found",
                            f"'{new_species_name}' not found in UKSI.\nSave anyway?",
                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                        )
                        if reply != QMessageBox.StandardButton.Yes:
                            return
                except Exception as e:
                    print(f"Error looking up species: {e}")
        
        try:
            db = get_database()
            model = ObservationModel(db)
            
            obs = Observation(
                id=self._record['id'],
                irecord_id=self._record.get('irecord_id'),
                species_name=new_species_name or self._record.get('species_name', ''),
                species_tvk=new_species_tvk if new_species_name else self._record.get('species_tvk'),
                common_name=new_common_name if new_species_name else self._record.get('common_name'),
                date=self.date_edit.date().toString("yyyy-MM-dd"),
                date_type=self._record.get('date_type', 'D'),
                grid_ref=self.grid_ref_edit.text().strip().upper() or None,
                grid_precision=self._record.get('grid_precision'),
                vice_county=self._record.get('vice_county'),
                vc_number=self._record.get('vc_number'),
                site_name=self.location_edit.text().strip() or None,
                site_name_local=self._record.get('site_name_local'),
                recorder=self.recorder_edit.text().strip() or None,
                determiner=self.determiner_edit.text().strip() or None,
                sex=self.sex_combo.currentText() or None,
                stage=self.stage_combo.currentText() or None,
                quantity=self.quantity_spin.value(),
                comment=self._record.get('comment'),
                internal_notes=self._record.get('internal_notes'),
                verification_status=self.verification_combo.currentText() or None,
                synced_at=self._record.get('synced_at')
            )
            
            if model.update(obs):
                self.record_updated.emit(obs.to_dict())
                self.accept()
            else:
                QMessageBox.warning(self, "Error", "Failed to update record.")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {str(e)}")
    
    def _on_delete_clicked(self):
        """Handle delete button click."""
        if not self._record or not self._record.get('id'):
            return
        
        reply = QMessageBox.question(
            self, "Confirm Delete", "Delete this record?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                db = get_database()
                model = ObservationModel(db)
                if model.delete(self._record['id']):
                    self.record_deleted.emit(self._record['id'])
                    self.accept()
                else:
                    QMessageBox.warning(self, "Error", "Failed to delete record.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete: {str(e)}")
    
    def get_record(self) -> Optional[Dict]:
        """Get the current record."""
        return self._record