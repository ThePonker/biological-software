"""
Wizard Import Mixin for Observation Import Wizard.

Contains the actual import execution, duplicate handling,
update preview dialog, and summary generation.
"""

from typing import List, Optional
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QApplication
)
from PySide6.QtCore import Qt

from .validation_worker import ObservationImportRow, RowStatus, ImportMode

from src.themes import theme
from src.core.config import TabColors


class UpdatePreviewDialog(QDialog):
    """Dialog showing records that will be updated."""
    
    def __init__(self, parent, rows_to_update: List[ObservationImportRow]):
        super().__init__(parent)
        self.rows = rows_to_update
        self._setup_ui()
    
    def _setup_ui(self):
        t = theme()
        
        self.setWindowTitle("Records to Update")
        self.setMinimumSize(800, 500)
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        
        # Info label
        info = QLabel(f"{len(self.rows)} existing record(s) will be updated with data from iRecord:")
        info.setStyleSheet(f"color: {t.get('text_secondary')};")
        layout.addWidget(info)
        
        # Table
        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels([
            'iRecord ID', 'Species', 'Date', 'Grid Ref', 'Verification', 'Local ID'
        ])
        table.setRowCount(len(self.rows))
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        
        for i, row in enumerate(self.rows):
            table.setItem(i, 0, QTableWidgetItem(str(row.irecord_id or "")))
            table.setItem(i, 1, QTableWidgetItem(row.species_name))
            table.setItem(i, 2, QTableWidgetItem(row.date))
            table.setItem(i, 3, QTableWidgetItem(row.grid_ref))
            table.setItem(i, 4, QTableWidgetItem(row.verification_status))
            table.setItem(i, 5, QTableWidgetItem(str(row.existing_record_id or "")))
        
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(table, 1)
        
        # Close button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setMinimumWidth(100)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)


class WizardImportMixin:
    """Mixin providing import execution methods for ObservationImportWizard."""
    
    def _show_update_preview(self):
        """Show dialog with records that will be updated."""
        rows_to_update = [r for r in self.validated_rows if r.is_duplicate and r.status != RowStatus.ERROR]
        
        if not rows_to_update:
            QMessageBox.information(self, "No Updates", "No records will be updated.")
            return
        
        dialog = UpdatePreviewDialog(self, rows_to_update)
        dialog.exec()
    
    def _do_import(self):
        """Execute the actual import using batch processing."""
        t = theme()
        
        if not self.db:
            QMessageBox.critical(self, "Error", "Database connection not available.")
            return
        
        if not self.observation_model:
            QMessageBox.critical(self, "Error", "Observation model not available.")
            return
        
        import_mode = self._get_selected_mode()
        skip_duplicates = self.skip_duplicates_checkbox.isChecked() if import_mode in [ImportMode.PERSONAL_UPLOAD, ImportMode.COMMERCIAL_UPLOAD] else False
        never_upload = self.never_upload_checkbox.isChecked() if import_mode in [ImportMode.PERSONAL_UPLOAD, ImportMode.COMMERCIAL_UPLOAD] else False
        
        # Filter rows to import
        rows_to_import = []
        include_errors = getattr(self, "_include_errors_at_import", False)
        # Determine which rows to import based on user selection
        if hasattr(self, 'import_valid_only_checkbox') and self.import_valid_only_checkbox.isChecked():
            import_rows = [r for r in self.validated_rows if r.status == RowStatus.VALID]
        elif hasattr(self, 'import_warnings_checkbox') and self.import_warnings_checkbox.isChecked():
            import_rows = self.validated_rows  # Import everything
        else:
            # Default: import valid + warning, skip errors
            import_rows = [r for r in self.validated_rows if r.status != RowStatus.ERROR]

        for row in import_rows:
            if row.status == RowStatus.ERROR and not include_errors:
                continue
            if skip_duplicates and row.is_duplicate and import_mode == ImportMode.PERSONAL_UPLOAD:
                continue
            rows_to_import.append(row)
        
        if not rows_to_import:
            QMessageBox.warning(self, "No Data", "No valid rows to import.")
            return
        
        self.imported_count = 0
        self.updated_count = 0
        self.skipped_count = 0
        self.error_count = 0
        
        try:
            # Separate rows into inserts and updates for batch processing
            insert_rows = []
            update_rows = []
            
            for row in rows_to_import:
                if never_upload:
                    row.never_upload_to_irecord = 1
                if row.is_duplicate and row.existing_record_id:
                    update_rows.append(row)
                else:
                    insert_rows.append(row)
            
            total_ops = len(insert_rows) + len(update_rows)
            completed = 0
            batch_size = 500  # Commit every 500 rows
            ui_update_freq = 100  # Update UI every 100 rows
            
            self.import_progress.setMaximum(total_ops)
            
            # Batch insert new records
            if insert_rows:
                insert_batch = []
                for i, row in enumerate(insert_rows):
                    # Notes are combined non-destructively by
                    # _combine_import_notes(), called from
                    # _row_to_observation_dict() below. Doing it here as well
                    # mutated row.import_notes and doubled every warning.
                    obs_data = self._row_to_observation_dict(row, import_mode)
                    insert_batch.append(obs_data)
                    
                    # Execute batch when full or at end
                    if len(insert_batch) >= batch_size or i == len(insert_rows) - 1:
                        success_count = self._batch_insert_observations(insert_batch)
                        self.imported_count += success_count
                        self.error_count += len(insert_batch) - success_count
                        insert_batch = []
                    
                    completed += 1
                    if completed % ui_update_freq == 0 or i == len(insert_rows) - 1:
                        self.import_progress.setValue(completed)
                        self.import_status_label.setText(f"Importing row {completed} of {total_ops}...")
                        self.import_counts_label.setText(
                            f"Imported: {self.imported_count} | Updated: {self.updated_count} | Skipped: {self.skipped_count} | Errors: {self.error_count}"
                        )
                        QApplication.processEvents()
            
            # Process updates (still one by one for change detection)
            for i, row in enumerate(update_rows):
                obs_data = self._row_to_observation_dict(row, import_mode)
                result = self._update_observation(row.existing_record_id, obs_data)
                if result == 'skipped':
                    self.skipped_count += 1
                elif result:
                    self.updated_count += 1
                else:
                    self.error_count += 1
                
                completed += 1
                if completed % ui_update_freq == 0 or i == len(update_rows) - 1:
                    self.import_progress.setValue(completed)
                    self.import_status_label.setText(f"Updating row {completed} of {total_ops}...")
                    self.import_counts_label.setText(
                        f"Imported: {self.imported_count} | Updated: {self.updated_count} | Skipped: {self.skipped_count} | Errors: {self.error_count}"
                    )
                    QApplication.processEvents()
            
            self.import_status_label.setText("Import complete!")
            self.import_status_label.setStyleSheet(f"color: {t.get('success')}; font-weight: 600;")
            
            # Final counts
            self.import_counts_label.setText(
                f"Imported: {self.imported_count} | Updated: {self.updated_count} | Skipped: {self.skipped_count}"
            )
            QApplication.processEvents()
            
            # Auto-advance to summary page
            self._update_summary()
            self.stack.setCurrentIndex(6)
            self._update_step_ui()
            
            # Emit completion signal for auto-refresh
            total_success = self.imported_count + self.updated_count
            if total_success > 0:
                self.import_completed.emit(total_success)
                
                # Update last sync date for iRecord imports
                if import_mode == ImportMode.IRECORD_SYNC:
                    from datetime import datetime
                    from PySide6.QtCore import QSettings
                    from src.core.config import Settings
                    settings = QSettings()
                    settings.setValue(Settings.SYNC_LAST_SYNC, datetime.now().strftime("%d %b %Y %H:%M"))
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Import Error", f"Error during import:\n{str(e)}")
            self.import_status_label.setText(f"Error: {str(e)}")
            self.import_status_label.setStyleSheet(f"color: {t.get('error')};")

    def _batch_insert_observations(self, records: list) -> int:
        """Batch insert multiple observation records.
        
        Args:
            records: List of observation dictionaries
        
        Returns:
            Number of successfully inserted records
        """
        if not records:
            return 0
        
        try:
            # Use first record to determine columns
            first_record = records[0]
            columns = list(first_record.keys())
            column_names = ", ".join(columns)
            placeholders = ", ".join(["?" for _ in columns])
            
            # Build params list
            params_list = []
            for record in records:
                values = tuple(record.get(c) for c in columns)
                params_list.append(values)
            
            # Use INSERT OR IGNORE to handle duplicates within the import file
            query = f"INSERT INTO observations ({column_names}) VALUES ({placeholders})"
            
            # Use executemany for batch insert
            if hasattr(self.db, 'execute_main_many'):
                result = self.db.execute_main_many(query, params_list)
                # executemany returns total rows affected
                return result if result else len(params_list)
            else:
                # Fallback to individual inserts
                success_count = 0
                for params in params_list:
                    try:
                        result = self.db.execute_main_write(query, params)
                        if result and result > 0:
                            success_count += 1
                    except Exception:
                        pass
                return success_count
        
        except Exception as e:
            print(f"[ObservationImportWizard] Batch insert error: {e}")
            return 0

    def _pre_generate_observatum_keys(self, rows, import_mode):
        """Pre-generate unique observatum_keys for all rows in a batch.
        
        This ensures each row gets a unique key before batch insert.
        For iRecord sync, uses external_key if available.
        For personal uploads, generates sequential keys.
        """
        from .validation_worker import ImportMode
        from PySide6.QtCore import QSettings
        from src.core.config import Settings, Defaults
        from datetime import datetime
        
        if import_mode == ImportMode.IRECORD_SYNC:
            # For iRecord, external_key is the observatum_key
            # Only generate for rows without external_key
            rows_needing_keys = [r for r in rows if not r.external_key]
        else:
            # Personal upload - all rows need keys
            rows_needing_keys = rows
        
        if not rows_needing_keys:
            return
        
        settings = QSettings()
        initials = settings.value(Settings.USER_INITIALS, Defaults.USER_INITIALS) or 'UNK'
        date_str = datetime.now().strftime('%Y%m%d')
        prefix = f"OBS-{initials}-{date_str}-"
        
        # Find the current max sequence in the database
        try:
            result = self.db.execute_main(
                """SELECT observatum_key FROM observations
                WHERE observatum_key LIKE ?
                ORDER BY observatum_key DESC
                LIMIT 1""",
                (f"{prefix}%",)
            )
            if result and len(result) > 0:
                last_key = result[0]['observatum_key'] if isinstance(result[0], dict) else result[0][0]
                if last_key:
                    last_seq = int(last_key.split('-')[-1])
                else:
                    last_seq = 0
            else:
                last_seq = 0
        except Exception:
            last_seq = 0
        
        # Assign sequential keys to each row
        for i, row in enumerate(rows_needing_keys):
            next_seq = last_seq + i + 1
            row._pre_generated_key = f"{prefix}{next_seq:04d}"

    def _combine_import_notes(self, row):
        """Combine import_notes with any error/warning messages."""
        parts = []
        if row.import_notes:
            parts.append(row.import_notes)
        if row.status == RowStatus.ERROR and row.error_message:
            parts.append(f"[Error: {row.error_message}]")
        elif row.status == RowStatus.WARNING and hasattr(row, "warnings") and row.warnings:
            parts.append(f"[Warning: {'; '.join(row.warnings)}]")
        return " | ".join(parts) if parts else None

    def _row_to_observation_dict(self, row: ObservationImportRow, import_mode: ImportMode) -> dict:
        """Convert an import row to an observation dictionary for database."""
        now = datetime.now().isoformat()
        
        obs = {
            # External identity
            'irecord_id': row.irecord_id,
            'record_key': row.record_key or None,
            'external_key': row.external_key or None,
            'source': row.source or None,
            
            # Species
            'species_name': row.species_name,
            'species_tvk': row.species_tvk or None,
            'common_name': row.common_name or None,
            'order_name': row.order_name or None,
            'family': row.family or None,
            'kingdom': row.kingdom or None,
            'taxon_group': row.taxon_group or None,
            'taxon_rank': row.taxon_rank or None,
            
            # Date
            'date': row.date,
            'date_type': row.date_type or 'D',
            
            # Location
            'grid_ref': row.grid_ref or None,
            'grid_precision': row.grid_precision,
            'vice_county': row.vice_county or None,
            'vc_number': row.vc_number,
            'site_name': row.site_name or None,
            'latitude': row.latitude,
            'longitude': row.longitude,
            'geodetic_datum': row.geodetic_datum or None,
            
            # Sensitive
            'sensitive': row.sensitive,
            'sensitive_site': row.sensitive_site or None,
            'sensitive_output_map_ref': row.sensitive_output_map_ref or None,
            
            # People
            'recorder': row.recorder or None,
            'determiner': row.determiner or None,
            'recorder_certainty': row.recorder_certainty or None,
            
            # Occurrence
            'sex': row.sex or None,
            'stage': row.stage or None,
            'quantity': row.quantity or 1,
            'zero_abundance': row.zero_abundance,
            'method': row.method or None,
            
            # Comments
            'comment': row.comment or None,
            'sample_comment': row.sample_comment or None,
            'biotope': row.biotope or None,
            
            # Verification
            'verification_status': row.verification_status or None,
            'verification_status_2': row.verification_status_2 or None,
            'verifier': row.verifier or None,
            'verified_on': row.verified_on or None,
            'automated_checks': row.automated_checks or None,
            
            # Metadata
            'images': row.images or None,
            'licence': row.licence or None,
            'input_on_date': row.input_on_date or None,
            'last_edited_date': row.last_edited_date or None,
            
            # Record management
            'record_type': self._get_record_type_for_import(import_mode, row),
            'project_name': self._get_commercial_field(import_mode, row, 'project_name', self.commercial_project.text() if hasattr(self, 'commercial_project') else None),
            'client': self._get_commercial_field(import_mode, row, 'client', self.commercial_client.text() if hasattr(self, 'commercial_client') else None),
            'embargo_status': self._get_embargo_status(import_mode, row),
            'embargo_until': self._get_embargo_until(import_mode, row),
            'never_upload_to_irecord': self._get_never_upload(import_mode, row),
            'import_notes': self._combine_import_notes(row),
            'superfamily': row.superfamily or None,
            'subfamily': row.subfamily or None,
            'taxonomic_sort_key': row.taxonomic_sort_key,

            # Sync fields (for iRecord imports)
            # Generate observatum_key for Personal Upload, use external_key for iRecord Sync
            'observatum_key': self._generate_observatum_key_for_import(import_mode, row.external_key, row),
            'irecord_key': str(row.irecord_id) if row.irecord_id else None,  # iRecord's occurrence ID
            'sync_status': 'synced' if import_mode == ImportMode.IRECORD_SYNC else 'local',
            'last_synced': now if import_mode == ImportMode.IRECORD_SYNC else None,

            # Timestamps
            'created_at': now,
            'updated_at': now,
        }
        
        return obs
    
    def _is_commercial_import(self, import_mode) -> bool:
        """Check if this import should apply commercial settings."""
        from .validation_worker import ImportMode
        if import_mode == ImportMode.COMMERCIAL_UPLOAD:
            return True
        if import_mode == ImportMode.IRECORD_SYNC:
            return hasattr(self, 'irecord_commercial_checkbox') and self.irecord_commercial_checkbox.isChecked()
        return False

    def _is_new_irecord_record(self, row) -> bool:
        """Check if this is a NEW record from iRecord (no external_key match)."""
        # If row has no external_key, it's a new record from iRecord
        return not row.external_key or not row.external_key.strip()

    def _get_record_type_for_import(self, import_mode, row) -> str:
        """Determine record_type based on import mode and row status."""
        from .validation_worker import ImportMode
        if import_mode == ImportMode.COMMERCIAL_UPLOAD:
            return 'Commercial'
        if import_mode == ImportMode.IRECORD_SYNC:
            # For iRecord: only mark NEW records as Commercial if checkbox checked
            if self._is_commercial_import(import_mode) and self._is_new_irecord_record(row):
                return 'Commercial'
            # Matched records preserve their type, new records default to Personal
            return row.record_type or 'Personal'
        return row.record_type or 'Personal'

    def _get_commercial_field(self, import_mode, row, field_name: str, wizard_value):
        """Get commercial field value based on import mode."""
        from .validation_worker import ImportMode
        if import_mode == ImportMode.COMMERCIAL_UPLOAD:
            return wizard_value
        if import_mode == ImportMode.IRECORD_SYNC:
            if self._is_commercial_import(import_mode) and self._is_new_irecord_record(row):
                return wizard_value
        return getattr(row, field_name, None) if hasattr(row, field_name) else None

    def _get_embargo_status(self, import_mode, row):
        """Get embargo_status based on import mode and embargo checkbox."""
        from .validation_worker import ImportMode
        embargo_enabled = hasattr(self, 'embargo_checkbox') and self.embargo_checkbox.isChecked()
        if import_mode == ImportMode.COMMERCIAL_UPLOAD and embargo_enabled:
            return 'Active'
        if import_mode == ImportMode.IRECORD_SYNC:
            if self._is_commercial_import(import_mode) and self._is_new_irecord_record(row) and embargo_enabled:
                return 'Active'
        return None

    def _get_embargo_until(self, import_mode, row):
        """Get embargo_until date based on import mode."""
        from .validation_worker import ImportMode
        embargo_enabled = hasattr(self, 'embargo_checkbox') and self.embargo_checkbox.isChecked()
        if not embargo_enabled:
            return None
        if import_mode == ImportMode.COMMERCIAL_UPLOAD:
            return self.commercial_embargo_date.date().toString('yyyy-MM-dd') if hasattr(self, 'commercial_embargo_date') else None
        if import_mode == ImportMode.IRECORD_SYNC:
            if self._is_commercial_import(import_mode) and self._is_new_irecord_record(row):
                return self.commercial_embargo_date.date().toString('yyyy-MM-dd') if hasattr(self, 'commercial_embargo_date') else None
        return None

    def _get_never_upload(self, import_mode, row):
        """Get never_upload_to_irecord based on import mode and embargo."""
        from .validation_worker import ImportMode
        embargo_enabled = hasattr(self, 'embargo_checkbox') and self.embargo_checkbox.isChecked()
        if import_mode == ImportMode.COMMERCIAL_UPLOAD and embargo_enabled:
            return 1
        if import_mode == ImportMode.IRECORD_SYNC:
            if self._is_commercial_import(import_mode) and self._is_new_irecord_record(row) and embargo_enabled:
                return 1
        return row.never_upload_to_irecord

    def _generate_observatum_key_for_import(self, import_mode, external_key: str, row=None) -> str:
        """Generate observatum_key for imports.

        - Personal Upload: Generate new key (like Home tab)
        - iRecord Sync: Use external_key from CSV (our key returning from iRecord)
        - iRecord records without external_key: Generate new key
        """
        from .validation_worker import ImportMode

        # Check if row has a pre-generated key (from batch processing)
        if row and hasattr(row, '_pre_generated_key') and row._pre_generated_key:
            return row._pre_generated_key

        if import_mode == ImportMode.IRECORD_SYNC:
            if external_key:
                return external_key
            # New iRecord record without our key - generate one

        # Generate new key for Personal Upload or iRecord without external_key
        from PySide6.QtCore import QSettings
        from src.core.config import Settings, Defaults
        from datetime import datetime

        settings = QSettings()
        initials = settings.value(Settings.USER_INITIALS, Defaults.USER_INITIALS) or 'UNK'
        date_str = datetime.now().strftime('%Y%m%d')
        prefix = f"OBS-{initials}-{date_str}-"

        # Initialise batch sequence tracker on first call
        if not hasattr(self, '_import_key_sequence'):
            self._import_key_sequence = {}

        batch_key = f"{initials}-{date_str}"

        if batch_key not in self._import_key_sequence:
            # Query DB once for starting sequence
            try:
                result = self.db.execute_main(
                    """SELECT observatum_key FROM observations
                    WHERE observatum_key LIKE ?
                    ORDER BY observatum_key DESC
                    LIMIT 1""",
                    (f"{prefix}%",)
                )
                if result and len(result) > 0 and result[0]['observatum_key']:
                    last_key = result[0]['observatum_key']
                    last_seq = int(last_key.split('-')[-1])
                    self._import_key_sequence[batch_key] = last_seq
                else:
                    self._import_key_sequence[batch_key] = 0
            except Exception:
                self._import_key_sequence[batch_key] = 0

        # Increment and return
        self._import_key_sequence[batch_key] += 1
        next_seq = self._import_key_sequence[batch_key]
        return f"{prefix}{next_seq:04d}"

    def _insert_observation(self, obs_data: dict) -> bool:
        """Insert a new observation record."""
        try:
            # Use observation model if available
            if hasattr(self.observation_model, 'create'):
                from src.models.observation import Observation
                obs = Observation(**{k: v for k, v in obs_data.items() if hasattr(Observation, k) or k in ['created_at', 'updated_at']})
                result = self.observation_model.create(obs)
                return result is not None and result > 0
            
            # Fallback to direct SQL
            columns = list(obs_data.keys())
            placeholders = ', '.join(['?' for _ in columns])
            column_names = ', '.join(columns)
            values = [obs_data[c] for c in columns]
            
            query = f"INSERT INTO observations ({column_names}) VALUES ({placeholders})"
            result = self.db.execute_main_write(query, tuple(values))
            return result > 0
            
        except Exception as e:
            print(f"[ObservationImportWizard] Insert error: {e}")
            return False
    
    def _has_changes(self, existing, new_data: dict) -> bool:
        """Check if new data differs from existing record."""
        # Fields to compare for changes (sync-relevant fields)
        compare_fields = [
            'verification_status', 'verification_status_2', 'verifier', 'verified_on',
            'species_name', 'species_tvk', 'common_name', 'date', 'grid_ref',
            'site_name', 'recorder', 'determiner', 'sex', 'stage', 'quantity',
            'method', 'comment', 'irecord_key', 'sync_status'
        ]
        
        for field in compare_fields:
            existing_val = getattr(existing, field, None) if existing else None
            new_val = new_data.get(field)
            
            # Normalize None and empty string
            if existing_val == '':
                existing_val = None
            if new_val == '':
                new_val = None
                
            if existing_val != new_val:
                return True
        
        return False

    def _update_observation(self, record_id: int, obs_data: dict) -> bool:
        """Update an existing observation record."""
        try:
            # Remove fields that should be preserved from original record
            preserve_fields = ['created_at', 'observatum_key', 'irecord_id']
            update_data = {k: v for k, v in obs_data.items() if k not in preserve_fields}
            update_data['updated_at'] = datetime.now().isoformat()

            # Use observation model if available
            if hasattr(self.observation_model, 'update'):
                from src.models.observation import Observation

                # Get existing record to preserve fields and check for changes
                existing = self.observation_model.get_by_id(record_id)
                if existing:
                    # Check if there are actual changes
                    if not self._has_changes(existing, update_data):
                        return 'skipped'

                    # Preserve record_type, observatum_key, and commercial fields from existing
                    update_data['record_type'] = existing.record_type
                    update_data['observatum_key'] = existing.observatum_key
                    update_data['project_name'] = existing.project_name
                    update_data['client'] = existing.client
                    update_data['embargo_status'] = existing.embargo_status
                    update_data['embargo_until'] = existing.embargo_until
                    update_data['irecord_id'] = existing.irecord_id



                obs = Observation(id=record_id, **{k: v for k, v in update_data.items() if hasattr(Observation, k) or k in ['updated_at', 'irecord_key', 'sync_status', 'last_synced']})
                result = self.observation_model.update(obs)
                return result
            
            # Fallback to direct SQL
            set_clauses = ', '.join([f"{k} = ?" for k in update_data.keys()])
            values = list(update_data.values()) + [record_id]
            
            query = f"UPDATE observations SET {set_clauses} WHERE id = ?"
            result = self.db.execute_main_write(query, tuple(values))
            return result > 0
            
        except Exception as e:
            print(f"[ObservationImportWizard] Update error: {e}")
            return False
    
    def _update_summary(self):
        """Update the summary page with final counts."""
        t = theme()

        # Calculate skipped (errors not imported)
        total_rows = len(self.validated_rows) if hasattr(self, "validated_rows") else 0
        imported_total = self.imported_count + self.updated_count
        skipped = total_rows - imported_total - self.error_count
        if skipped < 0:
            skipped = 0

        summary_parts = [
            f"New records: {self.imported_count}",
            f"Updated records: {self.updated_count}",
        ]
        if skipped > 0:
            summary_parts.append(f"Skipped (errors): {skipped}")
        if self.error_count > 0:
            summary_parts.append(f"Import errors: {self.error_count}")

        self.summary_stats.setText("\n".join(summary_parts))

        if self.error_count > 0:
            self.summary_icon.setText("\u26A0")
            self.summary_icon.setStyleSheet(f"font-size: 64px; color: {t.get('warning')};")
            self.summary_title.setText("Import Complete with Errors")
        elif skipped > 0:
            self.summary_icon.setText("\u2713")
            self.summary_icon.setStyleSheet(f"font-size: 64px; color: {t.get('success')};")
            self.summary_title.setText(f"Import Complete ({skipped} rows skipped)")
        else:
            self.summary_icon.setText("\u2713")
            self.summary_icon.setStyleSheet(f"font-size: 64px; color: {t.get('success')};")
            self.summary_title.setText("Import Complete!")

