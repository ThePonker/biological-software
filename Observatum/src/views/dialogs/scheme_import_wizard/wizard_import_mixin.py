"""
Wizard Import Mixin for Recording Scheme Import Wizard.

Contains the actual import execution, duplicate handling,
preview dialogs, and summary generation.
"""

from typing import List, Optional
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QApplication
)
from PySide6.QtCore import Qt

from .validation_worker import SchemeImportRow, RowStatus, SchemeImportMode

from src.themes import theme


class DuplicatePreviewDialog(QDialog):
    """Dialog showing records that are duplicates."""

    def __init__(self, parent, rows: List[SchemeImportRow]):
        super().__init__(parent)
        self.rows = rows
        self._setup_ui()

    def _setup_ui(self):
        t = theme()

        self.setWindowTitle("Duplicate Records")
        self.setMinimumSize(800, 500)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Info label
        info = QLabel(f"{len(self.rows)} record(s) match existing records in the database:")
        info.setStyleSheet(f"color: {t.get('text_secondary')};")
        layout.addWidget(info)

        # Table
        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels([
            'Row', 'Species', 'Date', 'Grid Ref', 'Source', 'Existing ID'
        ])
        table.setRowCount(len(self.rows))
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)

        for i, row in enumerate(self.rows):
            table.setItem(i, 0, QTableWidgetItem(str(row.row_number)))
            table.setItem(i, 1, QTableWidgetItem(row.species_name))
            table.setItem(i, 2, QTableWidgetItem(row.date))
            table.setItem(i, 3, QTableWidgetItem(row.grid_ref))
            table.setItem(i, 4, QTableWidgetItem(row.source_type))
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
    """Mixin providing import execution methods for SchemeImportWizard."""

    def _do_import(self):
        """Execute the actual import."""
        t = theme()

        if not self.db:
            QMessageBox.critical(self, "Error", "Database connection not available.")
            return

        update_duplicates = self.update_duplicates_checkbox.isChecked()

        # Filter rows to import (always skip duplicates unless update is enabled)
        rows_to_import = []
        for row in self.validated_rows:
            if row.status == RowStatus.ERROR and not (hasattr(self, "import_errors_checkbox") and self.import_errors_checkbox.isVisible() and self.import_errors_checkbox.isChecked()):
                continue
            if row.is_duplicate and not update_duplicates:
                continue
            rows_to_import.append(row)

        if not rows_to_import:
            QMessageBox.warning(self, "No Data", "No valid rows to import.")
            return

        self.import_progress.setMaximum(len(rows_to_import))
        self.imported_count = 0
        self.updated_count = 0
        self.skipped_count = 0
        self.error_count = 0

        try:
            # Separate rows into inserts and updates for batch processing
            insert_rows = []
            update_rows = []
            
            for row in rows_to_import:
                if row.is_duplicate and row.existing_record_id:
                    if update_duplicates:
                        update_rows.append(row)
                    else:
                        self.skipped_count += 1
                else:
                    insert_rows.append(row)
            
            total_ops = len(insert_rows) + len(update_rows)
            completed = 0
            batch_size = 500  # Commit every 500 rows
            ui_update_freq = 100  # Update UI every 100 rows
            
            # Batch insert new records
            if insert_rows:
                insert_batch = []
                for i, row in enumerate(insert_rows):
                    record_data = self._row_to_record_dict(row)
                    insert_batch.append(record_data)
                    
                    # Execute batch when full or at end
                    if len(insert_batch) >= batch_size or i == len(insert_rows) - 1:
                        success_count = self._batch_insert_records(insert_batch)
                        self.imported_count += success_count
                        self.error_count += len(insert_batch) - success_count
                        insert_batch = []
                    
                    completed += 1
                    if completed % ui_update_freq == 0 or i == len(insert_rows) - 1:
                        self.import_progress.setValue(completed)
                        self.import_status_label.setText(f"Importing row {completed} of {total_ops}...")
                        self.import_counts_label.setText(
                            f"Imported: {self.imported_count} | Updated: {self.updated_count} | Errors: {self.error_count}"
                        )
                        QApplication.processEvents()
            
            # Process updates (still row-by-row as they need individual WHERE clauses)
            for i, row in enumerate(update_rows):
                record_data = self._row_to_record_dict(row)
                success = self._update_record(row.existing_record_id, record_data)
                if success:
                    self.updated_count += 1
                else:
                    self.error_count += 1
                
                completed += 1
                if completed % ui_update_freq == 0 or i == len(update_rows) - 1:
                    self.import_progress.setValue(completed)
                    self.import_status_label.setText(f"Updating row {completed} of {total_ops}...")
                    self.import_counts_label.setText(
                        f"Imported: {self.imported_count} | Updated: {self.updated_count} | Errors: {self.error_count}"
                    )
                    QApplication.processEvents()

            self.import_status_label.setText("Import complete!")
            self.import_status_label.setStyleSheet(f"color: {t.get('success')}; font-weight: 600;")

            self.next_btn.setEnabled(True)

            # Emit completion signal
            total_success = self.imported_count + self.updated_count
            if total_success > 0:
                self.import_completed.emit(total_success)

        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Error during import:\n{str(e)}")
            self.import_status_label.setText(f"Error: {str(e)}")
            self.import_status_label.setStyleSheet(f"color: {t.get('error')};")

    def _row_to_record_dict(self, row: SchemeImportRow) -> dict:
        """Convert an import row to a recording scheme dictionary."""
        now = datetime.now().isoformat()

        record = {
            # External identity
            'irecord_id': row.irecord_id,
            'nbn_atlas_id': row.nbn_atlas_id or None,
            'occurrence_id': row.occurrence_id or None,
            'record_key': row.record_key or None,
            'external_key': row.external_key or None,
            'event_id': row.event_id or None,

            # Dataset info
            'collection_code': row.collection_code or None,
            'dataset_name': row.dataset_name or None,
            'institution_code': row.institution_code or None,
            'source': row.source or row.source_type or None,

            # Species
            'species_name': row.species_name,
            'species_tvk': row.species_tvk or None,
            'common_name': row.common_name or None,
            'taxon_author': row.taxon_author or None,
            'order_name': row.order_name or None,
            'family': row.family or None,
            'subfamily': row.subfamily or None,
            'genus': row.genus or None,
            'kingdom': row.kingdom or None,
            'phylum': row.phylum or None,
            'class_name': row.class_name or None,
            'taxon_group': row.taxon_group or None,
            'taxon_rank': row.taxon_rank or None,
            'identification_qualifier': row.identification_qualifier or None,
            'identification_remarks': row.identification_remarks or None,
            'recorder_certainty': row.recorder_certainty or None,

            # Date
            'date': row.date,
            'date_type': row.date_type or 'D',

            # Location - grid
            'grid_ref': row.grid_ref or None,
            'grid_precision': row.grid_precision,
            'vice_county': row.vice_county or None,
            'vc_number': row.vc_number,
            'site_name': row.site_name or None,
            'site_name_local': row.site_name_local or None,
            'country': row.country or None,
            'state_province': row.state_province or None,

            # Location - coordinates
            'latitude': row.latitude,
            'longitude': row.longitude,
            'geodetic_datum': row.geodetic_datum or None,
            'location_id': row.location_id or None,
            'location_remarks': row.location_remarks or None,
            'georeference_verification_status': row.georeference_verification_status or None,

            # Sensitive
            'sensitive': row.sensitive,
            'sensitive_site': row.sensitive_site or None,
            'sensitive_output_map_ref': row.sensitive_output_map_ref or None,

            # People
            'recorder': row.recorder or None,
            'determiner': row.determiner or None,
            'verifier': row.verifier or None,
            'verified_on': row.verified_on or None,

            # Occurrence
            'sex': row.sex or None,
            'stage': row.stage or None,
            'quantity': row.quantity or 1,
            'individual_count': row.individual_count,
            'organism_quantity': row.organism_quantity or None,
            'organism_quantity_type': row.organism_quantity_type or None,
            'zero_abundance': row.zero_abundance,
            'method': row.method or None,
            'basis_of_record': row.basis_of_record or None,
            'occurrence_status': row.occurrence_status or None,

            # Comments
            'comment': row.comment or None,
            'internal_notes': row.internal_notes or None,
            'import_notes': self._combine_import_notes(row),
            'superfamily': row.superfamily or None,
            'taxonomic_sort_key': row.taxonomic_sort_key,
            'sample_comment': row.sample_comment or None,
            'biotope': row.biotope or None,

            # Verification
            'verification_status': row.verification_status or None,
            'verification_status_2': row.verification_status_2 or None,
            'automated_checks': row.automated_checks or None,

            # Metadata
            'licence': row.licence or None,
            'rights_holder': row.rights_holder or None,
            'images': row.images or None,
            'input_on_date': row.input_on_date or None,
            'last_edited_date': row.last_edited_date or None,

            # Sync status (Recording Scheme records are read-only from external sources)
            'sync_status': 'synced',

            # Timestamps
            'created_at': now,
            'updated_at': now,
        }

        return record

    def _combine_import_notes(self, row):
        """Combine import_notes with any error/warning messages."""
        parts = []
        if row.import_notes:
            parts.append(row.import_notes)
        if row.error_message:
            parts.append(f"[{row.error_message}]")
        elif hasattr(row, 'warnings') and row.warnings:
            parts.append(f"[Warning: {'; '.join(row.warnings)}]")
        return " | ".join(parts) if parts else None

    def _insert_record(self, record_data: dict) -> bool:
        """Insert a new recording scheme record."""
        try:
            # Filter out None values and build query
            data = {k: v for k, v in record_data.items() if v is not None}

            columns = list(data.keys())
            placeholders = ', '.join(['?' for _ in columns])
            column_names = ', '.join(columns)
            values = [data[c] for c in columns]

            query = f"INSERT INTO recording_scheme ({column_names}) VALUES ({placeholders})"
            result = self.db.execute_main_write(query, tuple(values))
            return result > 0

        except Exception as e:
            print(f"[SchemeImportWizard] Insert error: {e}")
            return False

    def _batch_insert_records(self, records: list) -> int:
        """Batch insert multiple recording scheme records.
        
        Args:
            records: List of record dictionaries
            
        Returns:
            Number of successfully inserted records
        """
        if not records:
            return 0
            
        try:
            # Use the first record to determine columns (filter out None values)
            # All records should have the same structure
            first_data = {k: v for k, v in records[0].items() if v is not None}
            columns = list(first_data.keys())
            column_names = ', '.join(columns)
            placeholders = ', '.join(['?' for _ in columns])
            
            # Build params list for all records
            params_list = []
            for record in records:
                data = {k: v for k, v in record.items() if v is not None}
                # Ensure consistent column order, use None for missing keys
                values = tuple(data.get(c) for c in columns)
                params_list.append(values)
            
            query = f"INSERT INTO recording_scheme ({column_names}) VALUES ({placeholders})"
            
            # Use executemany for batch insert
            if hasattr(self.db, 'execute_main_many'):
                result = self.db.execute_main_many(query, params_list)
                return result if result else len(params_list)
            else:
                # Fallback to individual inserts
                success_count = 0
                for params in params_list:
                    try:
                        self.db.execute_main_write(query, params)
                        success_count += 1
                    except Exception:
                        pass
                return success_count
                
        except Exception as e:
            print(f"[SchemeImportWizard] Batch insert error: {e}")
            # Fallback to individual inserts on batch failure
            success_count = 0
            for record in records:
                if self._insert_record(record):
                    success_count += 1
            return success_count

    def _update_record(self, record_id: int, record_data: dict) -> bool:
        """Update an existing recording scheme record."""
        try:
            # Remove fields that shouldn't be updated
            preserve_fields = ['created_at', 'id']
            update_data = {k: v for k, v in record_data.items()
                          if k not in preserve_fields and v is not None}
            update_data['updated_at'] = datetime.now().isoformat()

            set_clauses = ', '.join([f"{k} = ?" for k in update_data.keys()])
            values = list(update_data.values()) + [record_id]

            query = f"UPDATE recording_scheme SET {set_clauses} WHERE id = ?"
            result = self.db.execute_main_write(query, tuple(values))
            return result > 0

        except Exception as e:
            print(f"[SchemeImportWizard] Update error: {e}")
            return False

    def _update_summary(self):
        """Update the summary page with final counts."""
        t = theme()

        self.summary_stats.setText(
            f"New records: {self.imported_count}\n"
            f"Updated records: {self.updated_count}\n"
            f"Skipped duplicates: {self.skipped_count}\n"
            f"Errors: {self.error_count}"
        )

        if self.error_count > 0:
            self.summary_icon.setText("⚠")
            self.summary_icon.setStyleSheet(f"font-size: 64px; color: {t.get('warning')};")
            self.summary_title.setText("Import Complete with Errors")
        else:
            self.summary_icon.setText("✓")
            self.summary_icon.setStyleSheet(f"font-size: 64px; color: {t.get('success')};")
            self.summary_title.setText("Import Complete!")
