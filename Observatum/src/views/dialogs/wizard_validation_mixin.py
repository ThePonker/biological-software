"""
Wizard Validation Mixin for Specimen Import Wizard.

Contains validation callbacks and row update methods.
UPDATED for pandas batch processing.
"""

from typing import List, Optional
from datetime import datetime

from PySide6.QtWidgets import (
    QDialog, QTableWidgetItem, QHeaderView, QMessageBox, QApplication
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from .validation_worker import ValidationWorker, ImportRow, RowStatus, _find_vc_database
from .species_search_dialog import SpeciesSearchDialog

from ....themes import theme


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

        # Start validation worker (now uses pandas for batch processing)
        self.validation_worker = ValidationWorker(
            self.validated_rows,
            self.column_mapping,
            self.uksi_model,
            self.vc_db_path,
            species_aliases=self.species_aliases
        )
        self.validation_worker.progress.connect(self._on_validation_progress)
        self.validation_worker.row_validated.connect(self._on_row_validated)
        self.validation_worker.finished.connect(self._on_validation_finished)

        self.validation_worker.start()

        return True

    def _setup_validation_table(self):
        """Set up the validation results table with editable columns."""
        columns = [
            "Status", "Row", "Species", "Date", "Grid Ref",
            "VC", "Location", "Message"
        ]

        self.validation_table.blockSignals(True)

        self.validation_table.setColumnCount(len(columns))
        self.validation_table.setHorizontalHeaderLabels(columns)
        # Pre-allocate rows for better performance
        self.validation_table.setRowCount(len(self.validated_rows))
        self.validation_table.setStyleSheet('''
            QTableWidget::item:selected { background-color: #e8e6e4; color: #1a1a1a; }
        ''')

        self.validation_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.validation_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Interactive
        )
        self.validation_table.setColumnWidth(2, 200)
        self.validation_table.horizontalHeader().setSectionResizeMode(
            7, QHeaderView.ResizeMode.Stretch
        )

        self._edited_row_indices = set()
        self.validation_table.blockSignals(False)

    def _on_validation_progress(self, current: int, total: int):
        """Handle validation progress updates."""
        self.validation_progress.setMaximum(total)
        self.validation_progress.setValue(current)

    def _on_row_validated(self, row_idx: int, row: ImportRow):
        """Handle a single row being validated (called in batches from worker)."""
        # Populate table row
        self._populate_table_row(row_idx, row)
        
        # Update counts periodically
        if row_idx % 50 == 0:
            self._update_validation_counts_live()
            QApplication.processEvents()

    def _populate_table_row(self, row_idx: int, row: ImportRow):
        """Populate a single table row efficiently."""
        self.validation_table.blockSignals(True)

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
        vc_item = QTableWidgetItem(f'VC{row.vc_number}' if row.vc_number else '')
        vc_item.setFlags(vc_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.validation_table.setItem(row_idx, 5, vc_item)

        # Location (editable)
        location_item = QTableWidgetItem(row.site_name)
        self.validation_table.setItem(row_idx, 6, location_item)

        # Message
        message_text = row.error_message if row.status == RowStatus.ERROR else '; '.join(row.warnings)
        message_item = QTableWidgetItem(message_text)
        message_item.setFlags(message_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.validation_table.setItem(row_idx, 7, message_item)

        self.validation_table.blockSignals(False)

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
            results = self.uksi_model.search_species(row.species_name, limit=1)
            if results:
                match = results[0]
                row.species_tvk = match.tvk
                row.common_name = match.common_name or ''
                row.order_name = match.order_name or ''
                row.family = match.family or ''
                if match.scientific_name.lower() != row.species_name.lower():
                    warnings.append(f"Matched to '{match.scientific_name}'")
            else:
                errors.append(f"Species not found in UKSI: {row.species_name}")

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

        # Update table display
        self._populate_table_row(row_idx, row)

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
        """Handle validation completion."""
        self.validated_rows = validated_rows
        self._validation_complete = True

        # Final count update
        self._update_validation_counts()

        # Check for species errors - calls method from WizardSpeciesResolutionMixin
        species_errors = self._get_unmatched_species()

        if species_errors:
            result = QMessageBox.question(
                self,
                "Unmatched Species Found",
                f"Found {len(species_errors)} unique species that could not be matched to UKSI.\n\n"
                f"Would you like to resolve them now?\n\n"
                f"* Yes: Open bulk resolution dialog to fix species matching\n"
                f"* No: Continue and import without TVK for unmatched species",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )

            if result == QMessageBox.StandardButton.Yes:
                self._show_bulk_resolution_dialog(species_errors)
                return

        self._update_validation_counts()

    def _update_table_row_display(self, row_idx: int, row: ImportRow):
        """Update the display of a table row."""
        t = theme()

        status_icons = {
            RowStatus.VALID: ("[OK]", t.get('success')),
            RowStatus.WARNING: ("[!]", t.get('warning')),
            RowStatus.ERROR: ("[X]", t.get('error')),
            RowStatus.PENDING: ("...", t.get('text_secondary')),
        }
        icon, color = status_icons.get(row.status, ("?", t.get('text_secondary')))

        item = self.validation_table.item(row_idx, 0)
        if item:
            item.setText(icon)
            item.setForeground(QColor(color))

        item = self.validation_table.item(row_idx, 2)
        if item:
            item.setText(row.species_name)

        item = self.validation_table.item(row_idx, 7)
        if item:
            message = row.error_message if row.status == RowStatus.ERROR else "; ".join(row.warnings)
            item.setText(message)

    def _filter_validation_table(self, button=None):
        """Filter the validation table based on selected filter."""
        for row_idx in range(self.validation_table.rowCount()):
            if row_idx >= len(self.validated_rows):
                continue

            row = self.validated_rows[row_idx]
            show = True

            if self.show_errors_radio.isChecked():
                show = row.status == RowStatus.ERROR
            elif self.show_warnings_radio.isChecked():
                show = row.status == RowStatus.WARNING

            self.validation_table.setRowHidden(row_idx, not show)
