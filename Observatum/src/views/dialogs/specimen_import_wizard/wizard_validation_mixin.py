"""
Wizard Validation Mixin for Specimen Import Wizard.

Contains validation callbacks and row update methods.
"""

from typing import List, Optional
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog, QTableWidgetItem, QMessageBox, QTableView
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from .validation_worker import ValidationWorker, ImportRow, RowStatus, _find_vc_database
from .validation_table_model import ValidationTableModel
from .species_search_dialog import SpeciesSearchDialog

from ....themes import theme
from ....core.config import TabColors


class WizardValidationMixin:
    """Mixin providing validation methods for SpecimenImportWizard."""
    
    def _start_validation(self) -> bool:
        """Start the validation process."""
        self.column_mapping = self._get_column_mapping()

        # Cache theme colors for performance
        t = theme()
        self._cached_success_color = QColor(t.get("success"))
        self._cached_warning_color = QColor(t.get("warning"))
        self._cached_error_color = QColor(t.get("error"))
        
        # Check required fields
        required = ['species_name', 'date_collected', 'grid_ref']
        missing = [f for f in required if f not in self.column_mapping]
        
        if missing:
            QMessageBox.warning(
                self,
                "Missing Required Fields",
                f"Please map the following required fields:\n* " +
                "\n* ".join(missing)
            )
            return False
        
        # Check VC database availability
        if not self.vc_db_path:
            self.vc_db_path = _find_vc_database()
        
        if not self.vc_db_path:
            QMessageBox.warning(
                self,
                "Vice County Database Not Found",
                "The Vice County lookup database (vc_lookup.db) was not found.\n\n"
                "Vice County will not be auto-populated from grid references.\n\n"
                "To enable VC lookup, place vc_lookup.db in the data folder."
            )
        
        # Create ImportRow objects
        self.validated_rows = []
        for i, raw_row in enumerate(self.raw_rows):
            if not any(v.strip() for v in raw_row.values()):
                continue
            
            import_row = ImportRow(
                row_number=i + 2,
                raw_data=raw_row
            )
            self.validated_rows.append(import_row)
        
        self._setup_validation_table()
        
        self._validation_complete = False
        self.next_btn.setEnabled(False)
        
        # Start validation worker
        self.validation_worker = ValidationWorker(
            self.validated_rows,
            self.column_mapping,
            self.uksi_model,
            self.vc_db_path,
        )
        self.validation_worker.progress.connect(self._on_validation_progress)
        self.validation_worker.row_validated.connect(self._on_row_validated)
        self.validation_worker.finished.connect(self._on_validation_finished)
        
        self.validation_worker.start()
        
        return True
    
    def _setup_validation_table(self):
        """Set up the validation table with the model."""
        t = theme()
        
        # Create and configure the model
        self.validation_model = ValidationTableModel(self)
        self.validation_model.set_theme_colors(
            success=t.get("success"),
            warning=t.get("warning"),
            error=t.get("error")
        )
        
        # Set the model on the view
        self.validation_table.setModel(self.validation_model)
        
        # Configure the view
        self.validation_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.validation_table.setAlternatingRowColors(True)
        
        # Set column widths
        header = self.validation_table.horizontalHeader()
        header.setStretchLastSection(True)
        self.validation_table.setColumnWidth(0, 60)   # Status
        self.validation_table.setColumnWidth(1, 50)   # Row
        self.validation_table.setColumnWidth(2, 200)  # Species
        self.validation_table.setColumnWidth(3, 100)  # Date
        self.validation_table.setColumnWidth(4, 100)  # Grid Ref
        self.validation_table.setColumnWidth(5, 60)   # VC
        self.validation_table.setColumnWidth(6, 150)  # Location
        
        # Style the table (matching Collection tab pattern)
        self.validation_table.setStyleSheet(f"""
            QTableView {{
                border: none;
                gridline-color: {t.get('border')};
                selection-background-color: transparent;
                outline: 0;
                background-color: {t.get('surface')};
            }}
            QTableView::item {{
                padding: 4px;
                border: none;
            }}
            QTableView::item:hover {{
                background-color: {TabColors.COLLECTION_LIGHT};
            }}
            QTableView::item:selected {{
                background-color: {TabColors.COLLECTION_LIGHT};
                color: {t.get('text_primary')};
            }}
            QHeaderView::section {{
                background-color: {t.get('surface_alt')};
                color: {t.get('text_primary')};
                padding: 6px;
                border: 1px solid {t.get('border')};
                font-weight: 600;
            }}
        """)
        
        # Set palette to override system colors for selection
        from PySide6.QtGui import QPalette
        palette = self.validation_table.palette()
        palette.setColor(QPalette.ColorRole.Highlight, QColor(t.get("primary_bg", "{t.get('surface_alt')}")))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(t.get("text", "{t.get('text_primary')}")))
        self.validation_table.setPalette(palette)
        
        # Connect double-click for species editing
        self.validation_table.doubleClicked.connect(self._on_table_double_clicked)

    def _on_validation_progress(self, current: int, total: int):
        """Handle validation progress updates."""
        self.validation_progress.setMaximum(total)
        self.validation_progress.setValue(current)
    
    def _on_row_validated(self, row_idx: int, row: ImportRow):
        """Handle a single row being validated."""
        # Use cached colors from _start_validation for performance
        
        
        # Ensure table has enough rows (only resize if needed)
        current_count = self.validation_table.rowCount()
        if current_count <= row_idx:
            # Pre-allocate in chunks of 100 to avoid repeated resizing
            self.validation_table.setRowCount(((row_idx // 100) + 1) * 100)
        
        # Status column
        status_item = QTableWidgetItem()
        if row.status == RowStatus.VALID:
            status_item.setText("[OK]")
            status_item.setForeground(self._cached_success_color)
        elif row.status == RowStatus.WARNING:
            status_item.setText("[!]")
            status_item.setForeground(self._cached_warning_color)
        else:
            status_item.setText("[X]")
            status_item.setForeground(self._cached_error_color)
        status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.validation_table.setItem(row_idx, 0, status_item)
        
        # Row number
        row_item = QTableWidgetItem(str(row.row_number))
        row_item.setFlags(row_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.validation_table.setItem(row_idx, 1, row_item)
        
        # Species (editable via dialog)
        species_item = QTableWidgetItem(row.species_name)
        species_item.setFlags(species_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.validation_table.setItem(row_idx, 2, species_item)
        
        # Date (editable)
        date_item = QTableWidgetItem(row.date_collected)
        self.validation_table.setItem(row_idx, 3, date_item)
        
        # Grid Ref (editable)
        gridref_item = QTableWidgetItem(row.grid_ref)
        self.validation_table.setItem(row_idx, 4, gridref_item)
        
        # VC (auto from grid ref)
        vc_item = QTableWidgetItem(f"VC{row.vc_number}" if row.vc_number else "")
        vc_item.setFlags(vc_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.validation_table.setItem(row_idx, 5, vc_item)
        
        # Location (editable)
        location_item = QTableWidgetItem(row.site_name)
        self.validation_table.setItem(row_idx, 6, location_item)
        
        # Message
        message_text = row.error_message if row.status == RowStatus.ERROR else "; ".join(row.warnings)
        message_item = QTableWidgetItem(message_text)
        message_item.setFlags(message_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.validation_table.setItem(row_idx, 7, message_item)
        
        
        # Update counts every 20 rows for performance
        if row_idx % 50 == 0:
            self._update_validation_counts_live()
    
    def _populate_table_row(self, row_idx: int, row: ImportRow):
        """Populate a single table row - lightweight version for batch updates."""
        # Use cached colors from _start_validation for performance
        
        # Status column
        status_item = QTableWidgetItem()
        if row.status == RowStatus.VALID:
            status_item.setText('[OK]')
            status_item.setForeground(self._cached_success_color)
        elif row.status == RowStatus.WARNING:
            status_item.setText('[!]')
            status_item.setForeground(self._cached_warning_color)
        else:
            status_item.setText('[X]')
            status_item.setForeground(self._cached_error_color)
        status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.validation_table.setItem(row_idx, 0, status_item)
        
        # Row number
        row_item = QTableWidgetItem(str(row.row_number))
        row_item.setFlags(row_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.validation_table.setItem(row_idx, 1, row_item)
        
        # Species
        species_item = QTableWidgetItem(row.species_name)
        species_item.setFlags(species_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.validation_table.setItem(row_idx, 2, species_item)
        
        # Date
        date_item = QTableWidgetItem(row.date_collected)
        self.validation_table.setItem(row_idx, 3, date_item)
        
        # Grid Ref
        gridref_item = QTableWidgetItem(row.grid_ref)
        self.validation_table.setItem(row_idx, 4, gridref_item)
        
        # VC
        vc_item = QTableWidgetItem(f'VC{row.vc_number}' if row.vc_number else '')
        vc_item.setFlags(vc_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.validation_table.setItem(row_idx, 5, vc_item)
        
        # Location
        location_item = QTableWidgetItem(row.site_name)
        self.validation_table.setItem(row_idx, 6, location_item)
        
        # Message
        message_text = row.error_message if row.status == RowStatus.ERROR else '; '.join(row.warnings)
        message_item = QTableWidgetItem(message_text)
        message_item.setFlags(message_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.validation_table.setItem(row_idx, 7, message_item)

    def _on_table_double_clicked(self, index):
        """Handle double-click on table - wrapper for QTableView."""
        if index.isValid():
            row_idx = index.row()
            col_idx = index.column()
            if col_idx == 2:  # Species column
                row = self.validation_model.get_row(row_idx)
                if row:
                    # Open species search dialog
                    current_species = row.species_name or ""
                    dialog = SpeciesSearchDialog(self, self.uksi_model, initial_text=current_species)
                    if dialog.exec() == QDialog.DialogCode.Accepted:
                        selected = dialog.get_selected_species()
                        if selected:
                            # Update the row (selected is a dict)
                            row.species_name = selected['scientific_name']
                            row.species_tvk = selected['tvk']
                            row.common_name = selected.get('common_name') or ""
                            row.order_name = selected.get('order_name') or ""
                            row.family = selected.get('family') or ""
                            row.error_message = ""
                            row.warnings = []
                            row.status = RowStatus.VALID
                            # Update the model
                            self.validation_model.update_row(row_idx, row)
                            self._update_validation_counts()
                            # Mark row as edited and enable revalidate button
                            self._edited_row_indices.add(row_idx)
                            self.revalidate_btn.setEnabled(True)

    def _on_cell_double_clicked(self, row: int, col: int):
        """Handle double-click on a cell."""
        if col == 2:  # Species column
            current_species = ""
            item = self.validation_table.item(row, col)
            if item:
                current_species = item.text()
            
            dialog = SpeciesSearchDialog(self, self.uksi_model, current_species)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                selected = dialog.get_selected_species()
                if selected:
                    self.validated_rows[row].species_name = selected['scientific_name']
                    self.validated_rows[row].species_tvk = selected['tvk']
                    self.validated_rows[row].common_name = selected['common_name']
                    self.validated_rows[row].order_name = selected['order_name']
                    self.validated_rows[row].family = selected['family']
                    
                    self.validation_table.blockSignals(True)
                    self.validation_table.item(row, 2).setText(selected['scientific_name'])
                    self.validation_table.blockSignals(False)
                    
                    self._edited_row_indices.add(row)
                    self.revalidate_btn.setEnabled(True)
    
    def _on_cell_changed(self, row: int, col: int):
        """Handle cell content changes."""
        if col in (3, 4, 6):  # Date, Grid Ref, Location
            self._edited_row_indices.add(row)
            self.revalidate_btn.setEnabled(True)
            
            item = self.validation_table.item(row, col)
            if item:
                new_value = item.text().strip()
                if col == 3:
                    self.validated_rows[row].date_collected = new_value
                elif col == 4:
                    self.validated_rows[row].grid_ref = new_value.upper().replace(" ", "")
                    item.setText(self.validated_rows[row].grid_ref)
                elif col == 6:
                    self.validated_rows[row].site_name = new_value
    
    def _revalidate_edited_rows(self):
        """Re-run validation on edited rows."""
        if not self._edited_row_indices:
            return
        
        for row_idx in list(self._edited_row_indices):
            row = self.validated_rows[row_idx]
            self._revalidate_single_row(row, row_idx)
        
        self._edited_row_indices.clear()
        self.revalidate_btn.setEnabled(False)
        self._update_validation_counts()
    
    def _revalidate_single_row(self, row: ImportRow, row_idx: int):
        """Re-validate a single row and update the table."""
        errors = []
        warnings = []
        
        # Validate species
        if not row.species_name:
            errors.append("Species name is required")
        elif not row.species_tvk and self.uksi_model:
            # The same rules as validation (shared/species_lookup.py): a search hit is a
            # suggestion, never a match
            from shared.species_lookup import lookup_names
            from shared.species_lookup_entries import entry
            typed = row.species_name
            e = entry(lookup_names([typed], self.uksi_model)[typed])
            if "error" in e:
                errors.append(e["error"])
            else:
                row.species_name = e["species_name"]
                row.species_tvk = e["tvk"]
                row.common_name = e["common_name"]
                row.order_name = e["order_name"]
                row.family = e["family"]
                if e["warning"]:
                    warnings.append(e["warning"])
                if e["import_notes"]:
                    row.import_notes = e["import_notes"]
        
        # Validate date
        if not row.date_collected:
            warnings.append("No date provided")
        else:
            parsed_date = self._parse_date_format(row.date_collected)
            if parsed_date:
                row.date_collected = parsed_date
            elif not self._is_valid_date_format(row.date_collected):
                errors.append(f"Invalid date format: {row.date_collected}")
        
        # Validate grid reference
        if not row.grid_ref:
            warnings.append("No grid reference provided")
            row.vc_number = None
            row.vc_name = ""
        elif self.vc_service:
            is_valid, msg = self.vc_service.validate_grid_ref(row.grid_ref)
            if is_valid:
                row.grid_ref = row.grid_ref.upper().replace(" ", "")
                vc_result = self.vc_service.get_vc_from_grid_ref(row.grid_ref)
                if vc_result:
                    row.vc_number, row.vc_name = vc_result
                else:
                    row.vc_number = None
                    row.vc_name = ""
                    warnings.append("Could not determine Vice County")
                
                if "Warning" in msg:
                    warnings.append(msg)
            else:
                errors.append(f"Invalid grid reference: {msg}")
                row.vc_number = None
                row.vc_name = ""
        
        # Set status
        row.warnings = warnings
        if errors:
            row.status = RowStatus.ERROR
            row.error_message = "; ".join(errors)
        elif warnings:
            row.status = RowStatus.WARNING
            row.error_message = "; ".join(warnings)
        else:
            row.status = RowStatus.VALID
            row.error_message = ""
        
        # Update the model (using QAbstractTableModel)
        self.validation_model.update_row(row_idx, row)
        self.validated_rows[row_idx] = row
    
    def _parse_date_format(self, date_str: str) -> Optional[str]:
        """Parse various date formats to ISO format."""
        formats = [
            "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d",
            "%d/%m/%y", "%d-%m-%y",
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None
    
    def _is_valid_date_format(self, date_str: str) -> bool:
        """Check if date string is already in valid ISO format."""
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            return False
    
    def _update_validation_counts_live(self):
        """Update validation counts during validation."""
        valid = sum(1 for r in self.validated_rows if r.status == RowStatus.VALID)
        warnings = sum(1 for r in self.validated_rows if r.status == RowStatus.WARNING)
        errors = sum(1 for r in self.validated_rows if r.status == RowStatus.ERROR)
        
        self.valid_count_label.setText(f"Valid: {valid}")
        self.warning_count_label.setText(f"Warnings: {warnings}")
        self.error_count_label.setText(f"Errors: {errors}")
    
    def _update_validation_counts(self):
        """Update the validation count labels."""
        # Get rows from model if available, otherwise use self.validated_rows
        if hasattr(self, 'validation_model') and self.validation_model:
            rows = self.validation_model.get_all_rows()
        else:
            rows = getattr(self, 'validated_rows', [])
        
        valid_count = sum(1 for r in rows if r.status == RowStatus.VALID)
        warning_count = sum(1 for r in rows if r.status == RowStatus.WARNING)
        error_count = sum(1 for r in rows if r.status == RowStatus.ERROR)
        
        self.valid_count_label.setText(f"Valid: {valid_count}")
        self.warning_count_label.setText(f"Warnings: {warning_count}")
        self.error_count_label.setText(f"Errors: {error_count}")
        return  # Early return to skip old implementation

    def _update_validation_counts_OLD(self):
        """Update validation count labels and enable next button."""
        valid = sum(1 for r in self.validated_rows if r.status == RowStatus.VALID)
        warnings = sum(1 for r in self.validated_rows if r.status == RowStatus.WARNING)
        errors = sum(1 for r in self.validated_rows if r.status == RowStatus.ERROR)
        
        self.valid_count_label.setText(f"Valid: {valid}")
        self.warning_count_label.setText(f"Warnings: {warnings}")
        self.error_count_label.setText(f"Errors: {errors}")
        
        self.export_problems_btn.setEnabled(errors > 0 or warnings > 0)
        
        if hasattr(self, '_validation_complete') and self._validation_complete:
            self.next_btn.setEnabled(valid > 0 or warnings > 0)
    
    def _on_validation_finished(self, validated_rows: List[ImportRow]):
        """Handle validation completion - just set the model data (instant)."""
        self.validated_rows = validated_rows
        self._validation_complete = True
        
        # Set data on model - this is INSTANT, no matter how many rows
        self.validation_model.set_data(validated_rows)
        
        # Update progress to 100%
        self.validation_progress.setValue(self.validation_progress.maximum())
        
        # Update counts
        self._update_validation_counts()

        # Check for species errors
        species_errors = self._get_unmatched_species()

        if species_errors:
            result = QMessageBox.question(
                self,
                "Unmatched Species Found",
                f"Found {len(species_errors)} unique species that could not be matched to UKSI.\n\n"
                f"Would you like to resolve them now?\n\n"
                f"* Yes: Open bulk resolution dialog to fix species matching\n"
                f"* No: Leave them as errors (they will not be imported until resolved)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )

            if result == QMessageBox.StandardButton.Yes:
                self._show_bulk_resolution_dialog(species_errors)
                return
        
        # Enable Next button and show Resolve Species button if there are errors
        self.next_btn.setEnabled(True)
        if hasattr(self, "match_report_btn"):
            self.match_report_btn.setEnabled(True)
        if hasattr(self, 'resolve_species_btn'):
            self.resolve_species_btn.setVisible(len(species_errors) > 0 if species_errors else False)

    def _open_resolve_species_dialog(self):
        """Open the bulk species resolution dialog."""
        species_errors = self._get_unmatched_species()
        if species_errors:
            self._show_bulk_resolution_dialog(species_errors)

    def _update_table_row_display(self, row_idx: int, row: ImportRow):
        """Update the display of a table row via the model."""
        if hasattr(self, "validation_model") and self.validation_model:
            self.validation_model.update_row(row_idx, row)

    def _filter_validation_table(self, button=None):
        """Filter the validation table based on selected filter."""
        for row_idx in range(self.validation_model.rowCount()):
            if row_idx >= len(self.validated_rows):
                continue
            
            row = self.validated_rows[row_idx]
            show = True
            
            if self.show_errors_radio.isChecked():
                show = row.status == RowStatus.ERROR
            elif self.show_warnings_radio.isChecked():
                show = row.status == RowStatus.WARNING
            
            self.validation_table.setRowHidden(row_idx, not show)
