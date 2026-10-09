"""
Wizard Validation Mixin for Observation Import Wizard.

Contains validation worker callbacks, table updates, filtering,
inline editing, and revalidation methods.
"""

from typing import List

from PySide6.QtWidgets import (
    QTableWidgetItem, QHeaderView, QMessageBox, QInputDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush

from .validation_worker import (
    ObservationImportRow, ObservationValidationWorker, RowStatus, ImportMode
)

from src.themes import theme


class WizardValidationMixin:
    """Mixin providing validation methods for ObservationImportWizard."""
    
    def _start_validation(self) -> bool:
        """Start the validation worker."""
        if not self.raw_rows:
            QMessageBox.warning(self, "No Data", "No data to validate.")
            return False
        
        # Get import mode
        import_mode = self._get_selected_mode()
        
        # Get column mapping (only for personal mode)
        if import_mode in (ImportMode.PERSONAL_UPLOAD, ImportMode.COMMERCIAL_UPLOAD):
            self.column_mapping = self._get_column_mapping()
            
            # Check required fields are mapped
            required = ['species_name', 'date', 'grid_ref', 'recorder']
            missing = [f for f in required if f not in self.column_mapping]
            if missing:
                QMessageBox.warning(
                    self,
                    "Missing Mappings",
                    f"Please map the required fields: {', '.join(missing)}"
                )
                return False
        else:
            # iRecord mode only - auto mapping
            self.column_mapping = {}
        
        # Create import rows
        import_rows = []
        for i, raw in enumerate(self.raw_rows):
            row = ObservationImportRow(
                row_number=i + 2,  # 1-indexed, skip header
                raw_data=raw,
                is_irecord=(import_mode == ImportMode.IRECORD_SYNC)
            )
            import_rows.append(row)
        
        # Set up validation table columns
        self._setup_validation_table(import_mode)
        
        # Reset counters
        self.valid_label.setText("Valid: 0")
        self.warning_label.setText("Warnings: 0")
        self.error_label.setText("Errors: 0")
        
        # Reset progress
        self.validation_progress.setMaximum(len(import_rows))
        self.validation_progress.setValue(0)
        
        # Configure UI based on mode
        self._configure_validation_ui(import_mode)
        
        # Create and start worker
        self.validation_worker = ObservationValidationWorker(
            rows=import_rows,
            column_mapping=self.column_mapping,
            import_mode=import_mode,
            uksi_model=self.uksi_model,
            vc_db_path=self.vc_db_path,
            db_manager=self.db,
            species_aliases=self.species_aliases,
        )
        
        self.validation_worker.progress.connect(self._on_validation_progress)
        self.validation_worker.row_validated.connect(self._on_row_validated)
        self.validation_worker.counts_updated.connect(self._on_counts_updated)
        self.validation_worker.finished.connect(self._on_validation_finished)
        
        self.validation_worker.start()
        
        return True
    
    def _setup_validation_table(self, import_mode: ImportMode):
        """Set up validation table columns based on import mode."""
        t = theme()
        
        if import_mode == ImportMode.IRECORD_SYNC:
            columns = ['Status', 'Row', 'iRecord ID', 'Species', 'Date', 'Grid Ref', 'VC', 'Verification', 'Message']
            self.validation_table.setColumnCount(len(columns))
            self.validation_table.setHorizontalHeaderLabels(columns)
        else:
            columns = ['Status', 'Row', 'Species', 'Date', 'Grid Ref', 'VC', 'Recorder', 'Message']
            self.validation_table.setColumnCount(len(columns))
            self.validation_table.setHorizontalHeaderLabels(columns)
        
        self.validation_table.setRowCount(0)
        self.validation_table.setStyleSheet('''
            QTableWidget::item:selected { background-color: {t.get('surface_alt')}; color: {t.get('text_primary')}; }
        ''')
        self.validation_table.horizontalHeader().setSectionResizeMode(
            len(columns) - 1, QHeaderView.ResizeMode.Stretch
        )
    
    def _configure_validation_ui(self, import_mode: ImportMode):
        """Configure validation page UI based on import mode."""
        # iRecord mode: hide edit hint and revalidate, hide export problems
        if import_mode == ImportMode.IRECORD_SYNC:
            self.edit_hint.hide()
            self.revalidate_btn.hide()
            self.export_problems_btn.hide()
        else:
            self.edit_hint.show()
            self.revalidate_btn.show()
            self.export_problems_btn.show()
    
    def _on_validation_progress(self, current: int, total: int):
        """Update progress bar."""
        self.validation_progress.setValue(current)
        percent = int((current / total) * 100) if total > 0 else 0
        self.validation_progress.setFormat(f"{percent}%")
    
    def _on_row_validated(self, row_index: int, row: ObservationImportRow):
        """Add validated row to table."""
        import_mode = self._get_selected_mode()
        
        # Add row to table
        table_row = self.validation_table.rowCount()
        self.validation_table.insertRow(table_row)
        
        self._populate_table_row(table_row, row, import_mode)
    
    def _on_counts_updated(self, valid: int, warnings: int, errors: int):
        """Update live counters."""
        t = theme()
        
        self.valid_label.setText(f"Valid: {valid}")
        self.warning_label.setText(f"Warnings: {warnings}")
        self.error_label.setText(f"Errors: {errors}")
    
    def _on_validation_finished(self, validated_rows: List[ObservationImportRow]):
        """Handle validation completion."""
        self.validated_rows = validated_rows
        self.next_btn.setEnabled(True)
        if hasattr(self, "match_report_btn"):
            self.match_report_btn.setEnabled(True)

        # Check for unmatched species (personal/commercial only)
        import_mode = self._get_selected_mode()
        if import_mode != ImportMode.IRECORD_SYNC:
            self._prompt_resolve_unmatched()

        # Update confirmation page counts
        self._update_confirmation_counts()

    def _populate_table_row(self, table_row: int, row: ObservationImportRow, import_mode: ImportMode):
        """Populate a single table row with validation data."""
        t = theme()
        
        # Status icon
        status_icons = {
            RowStatus.VALID: ("✓", t.get('success')),
            RowStatus.WARNING: ("⚠", t.get('warning')),
            RowStatus.ERROR: ("✗", t.get('error')),
            RowStatus.PENDING: ("○", t.get('text_muted')),
        }
        icon, color = status_icons.get(row.status, ("?", t.get('text_muted')))
        
        status_item = QTableWidgetItem(icon)
        status_item.setForeground(QBrush(QColor(color)))
        status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.validation_table.setItem(table_row, 0, status_item)
        
        # Row number
        row_item = QTableWidgetItem(str(row.row_number))
        row_item.setFlags(row_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.validation_table.setItem(table_row, 1, row_item)
        
        if import_mode == ImportMode.IRECORD_SYNC:
            # iRecord ID
            id_item = QTableWidgetItem(str(row.irecord_id or ""))
            id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.validation_table.setItem(table_row, 2, id_item)
            
            # Species (not editable)
            species_item = QTableWidgetItem(row.species_name)
            species_item.setFlags(species_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.validation_table.setItem(table_row, 3, species_item)
            
            # Date (not editable)
            date_item = QTableWidgetItem(row.date)
            date_item.setFlags(date_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.validation_table.setItem(table_row, 4, date_item)
            
            # Grid Ref (not editable)
            grid_item = QTableWidgetItem(row.grid_ref)
            grid_item.setFlags(grid_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.validation_table.setItem(table_row, 5, grid_item)
            
            # VC
            vc_text = f"VC{int(row.vc_number)}" if row.vc_number else ""
            vc_item = QTableWidgetItem(vc_text)
            vc_item.setFlags(vc_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.validation_table.setItem(table_row, 6, vc_item)
            
            # Verification status
            verif_item = QTableWidgetItem(row.verification_status)
            verif_item.setFlags(verif_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.validation_table.setItem(table_row, 7, verif_item)
            
            # Message
            msg_item = QTableWidgetItem(row.error_message)
            msg_item.setFlags(msg_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.validation_table.setItem(table_row, 8, msg_item)
            
        else:
            # Personal mode - some fields editable
            
            # Species (editable via double-click search)
            species_item = QTableWidgetItem(row.species_name)
            species_item.setData(Qt.ItemDataRole.UserRole, "species")
            self.validation_table.setItem(table_row, 2, species_item)
            
            # Date (editable)
            date_item = QTableWidgetItem(row.date)
            date_item.setData(Qt.ItemDataRole.UserRole, "date")
            self.validation_table.setItem(table_row, 3, date_item)
            
            # Grid Ref (editable)
            grid_item = QTableWidgetItem(row.grid_ref)
            grid_item.setData(Qt.ItemDataRole.UserRole, "grid_ref")
            self.validation_table.setItem(table_row, 4, grid_item)
            
            # VC (not editable - derived from grid ref)
            vc_text = f"VC{int(row.vc_number)}" if row.vc_number else ""
            vc_item = QTableWidgetItem(vc_text)
            vc_item.setFlags(vc_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.validation_table.setItem(table_row, 5, vc_item)
            
            # Recorder (editable)
            recorder_item = QTableWidgetItem(row.recorder)
            recorder_item.setData(Qt.ItemDataRole.UserRole, "recorder")
            self.validation_table.setItem(table_row, 6, recorder_item)
            
            # Message (not editable)
            msg_item = QTableWidgetItem(row.error_message)
            msg_item.setFlags(msg_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.validation_table.setItem(table_row, 7, msg_item)
        
        # Store row reference
        self.validation_table.item(table_row, 0).setData(Qt.ItemDataRole.UserRole + 1, row.row_number)
    
    def _on_cell_double_clicked(self, row: int, col: int):
        """Handle double-click on table cell."""
        import_mode = self._get_selected_mode()
        
        if import_mode == ImportMode.IRECORD_SYNC:
            return  # No editing in iRecord mode
        
        item = self.validation_table.item(row, col)
        if not item:
            return
        
        field_type = item.data(Qt.ItemDataRole.UserRole)
        
        if field_type == "species":
            self._show_species_search_dialog(row)
    
    def _on_cell_changed(self, row: int, col: int):
        """Handle cell edit."""
        import_mode = self._get_selected_mode()
        
        if import_mode == ImportMode.IRECORD_SYNC:
            return
        
        item = self.validation_table.item(row, col)
        if not item:
            return
        
        # Track edited rows
        row_num_item = self.validation_table.item(row, 1)
        if row_num_item:
            try:
                row_number = int(row_num_item.text())
                self._edited_row_indices.add(row_number)
                self.next_btn.setEnabled(False)
            except ValueError:
                pass
    
    def _show_species_search_dialog(self, table_row: int):
        """Show species search dialog for the given row."""
        if not self.uksi_model:
            QMessageBox.warning(self, "UKSI Not Available", "Species lookup is not available.")
            return
        
        current_species = self.validation_table.item(table_row, 2).text()
        
        text, ok = QInputDialog.getText(
            self,
            "Search Species",
            "Enter species name to search:",
            text=current_species
        )
        
        if ok and text:
            results = self.uksi_model.search_species(text, limit=10)
            
            if not results:
                QMessageBox.information(self, "No Results", f"No species found matching '{text}'")
                return
            
            # For simplicity, take the first match
            # In a full implementation, show a selection dialog
            match = results[0]
            species_name = getattr(match, 'scientific_name', '')
            
            # Update table
            self.validation_table.item(table_row, 2).setText(species_name)
            
            # Track as edited
            row_num_item = self.validation_table.item(table_row, 1)
            if row_num_item:
                try:
                    self._edited_row_indices.add(int(row_num_item.text()))
                    self.next_btn.setEnabled(False)
                except ValueError:
                    pass
    
    def _apply_filter(self):
        """Apply row filter based on selected radio button."""
        show_all = self.filter_all_radio.isChecked()
        show_errors = self.filter_errors_radio.isChecked()
        show_warnings = self.filter_warnings_radio.isChecked()
        
        for row_idx in range(self.validation_table.rowCount()):
            status_item = self.validation_table.item(row_idx, 0)
            if not status_item:
                continue
            
            status_text = status_item.text()
            
            if show_all:
                self.validation_table.setRowHidden(row_idx, False)
            elif show_errors:
                self.validation_table.setRowHidden(row_idx, status_text != "✗")
            elif show_warnings:
                self.validation_table.setRowHidden(row_idx, status_text != "⚠")
    
    def _revalidate_edited_rows(self):
        """Revalidate rows that have been edited."""
        if not self._edited_row_indices:
            QMessageBox.information(self, "No Edits", "No rows have been edited.")
            return
        
        # Get edited row numbers
        edited_rows = list(self._edited_row_indices)
        
        # Update validated_rows with new values from table
        for table_row in range(self.validation_table.rowCount()):
            row_num_item = self.validation_table.item(table_row, 1)
            if not row_num_item:
                continue
            
            try:
                row_number = int(row_num_item.text())
            except ValueError:
                continue
            
            if row_number not in edited_rows:
                continue
            
            # Find the validated row
            for validated_row in self.validated_rows:
                if validated_row.row_number == row_number:
                    # Update from table cells (personal mode columns)
                    validated_row.species_name = self.validation_table.item(table_row, 2).text()
                    validated_row.date = self.validation_table.item(table_row, 3).text()
                    validated_row.grid_ref = self.validation_table.item(table_row, 4).text()
                    validated_row.recorder = self.validation_table.item(table_row, 6).text()
                    
                    # Update raw_data too
                    mapping = self.column_mapping
                    if mapping.get('species_name'):
                        validated_row.raw_data[mapping['species_name']] = validated_row.species_name
                    if mapping.get('date'):
                        validated_row.raw_data[mapping['date']] = validated_row.date
                    if mapping.get('grid_ref'):
                        validated_row.raw_data[mapping['grid_ref']] = validated_row.grid_ref
                    if mapping.get('recorder'):
                        validated_row.raw_data[mapping['recorder']] = validated_row.recorder
                    
                    break
        
        # Re-run validation on edited rows
        import_mode = self._get_selected_mode()
        rows_to_revalidate = [r for r in self.validated_rows if r.row_number in edited_rows]
        
        if not rows_to_revalidate:
            return
        
        # Create worker for revalidation
        self.validation_worker = ObservationValidationWorker(
            rows=rows_to_revalidate,
            column_mapping=self.column_mapping,
            import_mode=import_mode,
            uksi_model=self.uksi_model,
            vc_db_path=self.vc_db_path,
            db_manager=self.db,
            species_aliases=self.species_aliases,
        )
        
        self.validation_worker.row_validated.connect(self._on_row_revalidated)
        self.validation_worker.finished.connect(self._on_revalidation_finished)
        
        self.validation_worker.start()
        self._edited_row_indices.clear()
    
    def _on_row_revalidated(self, idx: int, row: ObservationImportRow):
        """Update table with revalidated row."""
        # Find table row by row number
        for table_row in range(self.validation_table.rowCount()):
            row_num_item = self.validation_table.item(table_row, 1)
            if row_num_item and int(row_num_item.text()) == row.row_number:
                # Update the row in validated_rows
                for i, vr in enumerate(self.validated_rows):
                    if vr.row_number == row.row_number:
                        self.validated_rows[i] = row
                        break
                
                # Update table display
                import_mode = self._get_selected_mode()
                self._update_table_row_display(table_row, row, import_mode)
                break
    
    def _on_revalidation_finished(self, rows: List[ObservationImportRow]):
        """Handle revalidation completion."""
        self._update_validation_counts()
        self._update_confirmation_counts()
        QMessageBox.information(self, "Revalidation Complete", f"Revalidated {len(rows)} row(s).")
        self.next_btn.setEnabled(True)
        if hasattr(self, "match_report_btn"):
            self.match_report_btn.setEnabled(True)
        if hasattr(self, "resolve_species_btn"):
            errors = sum(1 for r in self.validated_rows if r.status == RowStatus.ERROR)
            self.resolve_species_btn.setVisible(errors > 0)
    
    def _update_table_row_display(self, table_row: int, row: ObservationImportRow, import_mode: ImportMode):
        """Update display of a single table row."""
        t = theme()
        
        # Update status
        status_icons = {
            RowStatus.VALID: ("✓", t.get('success')),
            RowStatus.WARNING: ("⚠", t.get('warning')),
            RowStatus.ERROR: ("✗", t.get('error')),
        }
        icon, color = status_icons.get(row.status, ("?", t.get('text_muted')))
        
        status_item = self.validation_table.item(table_row, 0)
        status_item.setText(icon)
        status_item.setForeground(QBrush(QColor(color)))
        
        if import_mode == ImportMode.PERSONAL_UPLOAD:
            # Update VC
            vc_text = f"VC{int(row.vc_number)}" if row.vc_number else ""
            self.validation_table.item(table_row, 5).setText(vc_text)
            
            # Update message
            if row.error_message:
                msg = row.error_message
            elif row.warnings:
                msg = "; ".join(row.warnings)
            else:
                msg = ""
            self.validation_table.item(table_row, 7).setText(msg)
    
    def _update_validation_counts(self):
        """Update validation counters from validated_rows."""
        valid = sum(1 for r in self.validated_rows if r.status == RowStatus.VALID)
        warnings = sum(1 for r in self.validated_rows if r.status == RowStatus.WARNING)
        errors = sum(1 for r in self.validated_rows if r.status == RowStatus.ERROR)
        
        self.valid_label.setText(f"Valid: {valid}")
        self.warning_label.setText(f"Warnings: {warnings}")
        self.error_label.setText(f"Errors: {errors}")
    
    def _update_confirmation_counts(self):
        """Update confirmation page counts."""
        if not hasattr(self, 'validated_rows') or not self.validated_rows:
            return
        
        new_count = 0
        update_count = 0
        skip_count = 0
        
        for row in self.validated_rows:
            if row.status == RowStatus.ERROR:
                skip_count += 1
            elif row.is_duplicate:
                update_count += 1
            else:
                new_count += 1
        
        # Update stat cards
        self.new_count_frame.findChild(type(self.new_count_frame), "value_label")
        new_label = self.new_count_frame.findChildren(type(self.valid_label))[0]
        new_label.setText(str(new_count))
        
        update_label = self.update_count_frame.findChildren(type(self.valid_label))[0]
        update_label.setText(str(update_count))
        
        skip_label = self.skip_count_frame.findChildren(type(self.valid_label))[0]
        skip_label.setText(str(skip_count))
        
        # Show/hide view updates button
        self.view_updates_btn.setVisible(update_count > 0)
        
        # Show/hide skip duplicates checkbox based on mode
        import_mode = self._get_selected_mode()
        self.skip_duplicates_checkbox.setVisible(import_mode == ImportMode.PERSONAL_UPLOAD)
        self.include_errors_checkbox.setChecked(False)
        # Row handling radios control this now ? keep checkbox hidden
        self.include_errors_checkbox.setVisible(False)

    def _show_match_report(self):
        """Show species match report dialog."""
        try:
            from .species_match_report import SpeciesMatchReportDialog
            uksi = getattr(self, 'uksi_model', None)
            dialog = SpeciesMatchReportDialog(self.validated_rows, self, uksi_model=uksi)
            dialog.exec()
        except Exception as e:
            print(f"Match report error: {e}")
