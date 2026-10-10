"""
Wizard Validation Mixin for Recording Scheme Import Wizard.

Contains validation callbacks, live counter updates,
filtering, table population, and inline editing.
"""

import csv
from typing import List

from PySide6.QtWidgets import QApplication, QFileDialog, QDialog, QMessageBox
from PySide6.QtCore import QModelIndex

from shared.species_lookup import is_unresolved_error
from shared.species_lookup_entries import apply_confirmed

from .validation_worker import SchemeImportRow, RowStatus, SchemeValidationWorker, SchemeImportMode
from .validation_table_model import SchemeValidationTableModel
# The species picker the other two wizards use (IMP-6: this wizard's own copy called a
# search_species the UKSI model does not have)
from ..specimen_import_wizard.species_search_dialog import SpeciesSearchDialog
from src.themes import theme

# Table edits that the validation worker reads back from the file row (generic CSV mode)
_EDIT_TO_MAPPED_FIELD = {"date": "date", "grid_ref": "grid_ref", "site_name": "site_name"}


class WizardValidationMixin:
    """Mixin providing validation methods for SchemeImportWizard."""

    def _start_validation(self):
        """Start the validation process."""
        import_mode = self._get_selected_mode()
        column_mapping = self._get_column_mapping()

        # Create import rows
        rows = self._create_import_rows()

        if not rows:
            self.validation_progress.setValue(100)
            self.error_label.setText("Errors: No data to validate")
            return

        # Reset counters
        self.valid_label.setText("Valid: 0")
        self.warning_label.setText("Warnings: 0")
        self.error_label.setText("Errors: 0")
        # Disable buttons until validation completes
        self.next_btn.setEnabled(False)
        if hasattr(self, "revalidate_btn"):
            self.revalidate_btn.setEnabled(False)

        # Setup validation table
        self._setup_validation_table()

        # Create and start worker
        self.validation_worker = SchemeValidationWorker(
            rows=rows,
            column_mapping=column_mapping,
            import_mode=import_mode,
            uksi_model=self.uksi_model,
            vc_db_path=self.vc_db_path,
            db_manager=self.db,
        )

        self.validation_worker.progress.connect(self._on_validation_progress)
        self.validation_worker.row_validated.connect(self._on_row_validated)
        self.validation_worker.counts_updated.connect(self._on_counts_updated)
        self.validation_worker.finished.connect(self._on_validation_finished)

        self.validation_worker.start()

    def _setup_validation_table(self):
        """Setup the validation results table with QAbstractTableModel."""
        t = theme()
        
        # Create model if not exists
        if not hasattr(self, 'validation_model') or self.validation_model is None:
            self.validation_model = SchemeValidationTableModel(self.validation_table)
            self.validation_model.set_theme_colors(
                success=t.get('success'),
                warning=t.get('warning'),
                error=t.get('error')
            )
            self.validation_table.setModel(self.validation_model)
            self.validation_model.row_edited.connect(self._on_model_row_edited)
        # Edits are read back from the file row, which only the generic CSV mode maps;
        # iRecord and NBN rows are the source's records (IMP-6, 10 Oct 2026)
        self.validation_model.editable = self._get_selected_mode() == SchemeImportMode.GENERIC_CSV
        self._edited_row_indices.clear()
        
        # Pre-allocate rows for incremental population
        self.validation_model.pre_allocate(len(self.raw_rows))
        
        # Set column widths
        self.validation_table.setColumnWidth(0, 70)   # Status
        self.validation_table.setColumnWidth(1, 50)   # Row
        self.validation_table.setColumnWidth(2, 200)  # Species
        self.validation_table.setColumnWidth(3, 100)  # Date
        self.validation_table.setColumnWidth(4, 100)  # Grid Ref
        self.validation_table.setColumnWidth(5, 150)  # Site
        self.validation_table.horizontalHeader().setStretchLastSection(True)  # Message

    def _on_validation_progress(self, current: int, total: int):
        """Update progress bar."""
        percent = int((current / total) * 100) if total > 0 else 0
        self.validation_progress.setValue(percent)

    def _on_row_validated(self, row_index: int, row: SchemeImportRow):
        """Update table with validated row - uses model for instant updates."""
        if hasattr(self, 'validation_model') and self.validation_model:
            self.validation_model.set_row(row_index, row)
            if row_index % 50 == 0:
                QApplication.processEvents()
        # Model handles display, no need for QTableWidgetItem code
    def _on_counts_updated(self, valid: int, warnings: int, errors: int):
        """Update live counters."""
        self.valid_label.setText(f"Valid: {valid}")
        self.warning_label.setText(f"Warnings: {warnings}")
        self.error_label.setText(f"Errors: {errors}")

    def _on_validation_finished(self, validated_rows: List[SchemeImportRow]):
        """Handle validation completion."""
        self.validated_rows = validated_rows
        self.validation_progress.setValue(100)
        
        # Ensure model has final data
        if hasattr(self, 'validation_model') and self.validation_model:
            self.validation_model.set_data(validated_rows)

        # Show/hide edit hint based on mode
        import_mode = self._get_selected_mode()
        self.edit_hint.setVisible(import_mode == SchemeImportMode.GENERIC_CSV)
        self.revalidate_btn.setVisible(import_mode == SchemeImportMode.GENERIC_CSV)

        # Enable next button
        self.next_btn.setEnabled(True)
        if hasattr(self, "match_report_btn"):
            self.match_report_btn.setEnabled(True)
        if hasattr(self, "revalidate_btn"):
            self.revalidate_btn.setEnabled(True)
        if hasattr(self, "resolve_species_btn"):
            self.resolve_species_btn.setVisible(bool(self._get_unmatched_species()))

    def _get_unmatched_species(self) -> List[str]:
        """Names not found in UKSI, or held more than once: they wait for the user's choice."""
        return sorted({r.species_name for r in self.validated_rows
                       if r.status == RowStatus.ERROR and is_unresolved_error(r.error_message)})

    def _open_resolve_species_dialog(self):
        """Choose the UKSI taxon for each unmatched name (suggestions shown; nothing automatic)."""
        unmatched = self._get_unmatched_species()
        if not unmatched:
            QMessageBox.information(self, "No Errors", "No unmatched species to resolve.")
            return
        from ..specimen_import_wizard.bulk_resolution_dialog import BulkSpeciesResolutionDialog
        from ....core.config import TabColors
        dialog = BulkSpeciesResolutionDialog(
            self, uksi_model=self.uksi_model, unmatched_species=unmatched,
            accent=TabColors.RECORDING_SCHEME, accent_light=TabColors.RECORDING_SCHEME_LIGHT,
            accent_dark=TabColors.RECORDING_SCHEME_DARK)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            resolutions = dialog.get_resolutions()
            for row in self.validated_rows:
                if row.species_name in resolutions:
                    apply_confirmed(row, resolutions[row.species_name], row.species_name,
                                    "resolved by you")
            self._refresh_after_species_change()

    def _refresh_after_species_change(self):
        """Redraw the table and counters after rows were resolved or re-matched."""
        if hasattr(self, 'validation_model') and self.validation_model:
            self.validation_model.set_data(self.validated_rows)
        valid = sum(1 for r in self.validated_rows if r.status == RowStatus.VALID)
        warnings = sum(1 for r in self.validated_rows if r.status == RowStatus.WARNING)
        errors = sum(1 for r in self.validated_rows if r.status == RowStatus.ERROR)
        self._on_counts_updated(valid, warnings, errors)
        self._update_confirmation_counts()
        if hasattr(self, "resolve_species_btn"):
            self.resolve_species_btn.setVisible(bool(self._get_unmatched_species()))

    def _on_table_double_clicked(self, index: QModelIndex):
        """Handle double-click on QTableView."""
        row = index.row()
        col = index.column()
        self._on_cell_double_clicked(row, col)
    
    def _on_cell_double_clicked(self, row: int, col: int):
        """Double-click on Species: pick the UKSI taxon (IMP-6, 10 Oct 2026).

        It crashed -- QTableView has no item() -- and its search called a method the UKSI
        model does not have. The pick is applied as Resolve Species does: the UKSI name and
        TVK, the species error removed and any other error kept."""
        if col != 2 or not (0 <= row < len(self.validated_rows)):
            return
        target = self.validated_rows[row]
        original = target.species_name or ""
        dialog = SpeciesSearchDialog(self, self.uksi_model, initial_text=original)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        picked = dialog.get_selected_species()
        if not picked or not picked.get("tvk"):
            return
        # (the file row keeps the name as written: a revalidation re-applies the pick, so the
        # import note still says what the file had)
        apply_confirmed(target, picked, original, "picked by you")
        if getattr(self, "validation_model", None) is not None:
            self.validation_model.update_row(row, target)
        self._refresh_after_species_change()

    def _on_model_row_edited(self, row_idx: int, attr: str, text: str):
        """A Date, Grid Ref or Site cell was edited (IMP-6). The edit is kept on the row and in
        the file row the worker reads; the row is revalidated before it can be imported."""
        if not (0 <= row_idx < len(self.validated_rows)):
            return
        col = self._get_column_mapping().get(_EDIT_TO_MAPPED_FIELD.get(attr, ""))
        if col:
            self.validated_rows[row_idx].raw_data[col] = text
        self._edited_row_indices.add(row_idx)
        self.next_btn.setEnabled(False)             # until the edits are revalidated
        if hasattr(self, "revalidate_btn"):
            self.revalidate_btn.setEnabled(True)

    def _on_cell_changed(self, row: int, col: int):
        """Kept for old callers; edits now arrive through the model (row_edited)."""
        attr = SchemeValidationTableModel.EDIT_FIELDS.get(col)
        if attr and 0 <= row < len(self.validated_rows):
            self._on_model_row_edited(row, attr, getattr(self.validated_rows[row], attr, ""))

    def _apply_filter(self):
        """Apply filter to validation table."""
        show_all = self.filter_all_radio.isChecked()
        show_errors = self.filter_errors_radio.isChecked()
        show_warnings = self.filter_warnings_radio.isChecked()

        for i, row in enumerate(self.validated_rows):
            show = show_all
            if show_errors and row.status == RowStatus.ERROR:
                show = True
            elif show_warnings and row.status == RowStatus.WARNING:
                show = True
            elif not show_all:
                show = False

            self.validation_table.setRowHidden(i, not show)

    def _revalidate_edited_rows(self):
        """Revalidate rows that were edited (IMP-6, 10 Oct 2026).

        It used to put the rows it was given back in place -- the worker's results went
        nowhere -- so an edit was never checked and the row kept its old status."""
        if not self._edited_row_indices:
            QMessageBox.information(self, "No Changes", "No rows have been edited.")
            return

        import_mode = self._get_selected_mode()
        column_mapping = self._get_column_mapping()
        indices = sorted(self._edited_row_indices)
        old_rows = [self.validated_rows[i] for i in indices]

        worker = SchemeValidationWorker(
            rows=old_rows,
            column_mapping=column_mapping,
            import_mode=import_mode,
            uksi_model=self.uksi_model,
            vc_db_path=self.vc_db_path,
            db_manager=self.db,
        )
        results = []
        worker.finished.connect(lambda rows: results.extend(rows))
        worker.run()                                  # synchronously: a handful of rows

        for orig_idx, old, new in zip(indices, old_rows, results):
            # A species picked by hand stays picked if the name alone does not match
            if (old.species_tvk and not new.species_tvk and new.status == RowStatus.ERROR
                    and is_unresolved_error(new.error_message)):
                apply_confirmed(new, {"scientific_name": old.species_name, "tvk": old.species_tvk,
                                      "common_name": old.common_name, "order_name": old.order_name,
                                      "family": old.family, "kingdom": old.kingdom,
                                      "rank": old.taxon_rank}, new.species_name, "picked by you")
            self.validated_rows[orig_idx] = new
        if hasattr(self, 'validation_model') and self.validation_model:
            self.validation_model.set_data(self.validated_rows)
        self._apply_filter()

        valid = sum(1 for r in self.validated_rows if r.status == RowStatus.VALID)
        warnings = sum(1 for r in self.validated_rows if r.status == RowStatus.WARNING)
        errors = sum(1 for r in self.validated_rows if r.status == RowStatus.ERROR)
        self._on_counts_updated(valid, warnings, errors)

        self._edited_row_indices.clear()
        self.next_btn.setEnabled(True)
        if hasattr(self, "resolve_species_btn"):
            self.resolve_species_btn.setVisible(bool(self._get_unmatched_species()))

        QMessageBox.information(
            self, "Revalidation Complete",
            f"Revalidated {len(results)} row(s).\n"
            f"Valid: {valid}, Warnings: {warnings}, Errors: {errors}"
        )

    def _export_problems(self):
        """Export problem rows to CSV."""
        problem_rows = [r for r in self.validated_rows if r.status in [RowStatus.ERROR, RowStatus.WARNING]]

        if not problem_rows:
            QMessageBox.information(self, "No Problems", "No problem rows to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Problems",
            "import_problems.csv",
            "CSV Files (*.csv)"
        )

        if not file_path:
            return

        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Row', 'Status', 'Species', 'Date', 'Grid Ref', 'Site', 'Message'])

                for row in problem_rows:
                    message = row.error_message
                    if row.warnings:
                        message += "; " + "; ".join(row.warnings)

                    writer.writerow([
                        row.row_number,
                        row.status.value,
                        row.species_name,
                        row.date,
                        row.grid_ref,
                        row.site_name,
                        message
                    ])

            QMessageBox.information(
                self, "Export Complete",
                f"Exported {len(problem_rows)} problem row(s) to:\n{file_path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Error exporting: {str(e)}")

    def _update_confirmation_counts(self):
        """'Ready to import' on the confirmation page, following its boxes (IMP-9/16)."""
        if not hasattr(self, "import_errors_checkbox"):
            return
        rows, counts = self._rows_for_import()
        updates = sum(1 for r in rows if r.is_duplicate and r.existing_record_id)
        left_out = sum(counts.values())
        if hasattr(self, 'confirm_status_label'):
            self.confirm_status_label.setText(
                f"Ready to import {len(rows) - updates} new record(s)"
                + (f", update {updates} held" if updates else "")
                + (f"; {left_out} row(s) left out" if left_out else ""))

    def _show_duplicate_preview(self):
        """Show dialog with duplicate records."""
        duplicates = [r for r in self.validated_rows if r.is_duplicate and r.status != RowStatus.ERROR]

        if not duplicates:
            QMessageBox.information(self, "No Duplicates", "No duplicate records found.")
            return

        from .wizard_import_mixin import DuplicatePreviewDialog
        dialog = DuplicatePreviewDialog(self, duplicates)
        dialog.exec()

    def _show_match_report(self):
        """Show species match report dialog."""
        try:
            from .species_match_report import SpeciesMatchReportDialog
            uksi = getattr(self, 'uksi_model', None)
            mode = self._get_selected_mode()
            if mode == SchemeImportMode.IRECORD:
                name_columns = ["Taxon"]
            elif mode == SchemeImportMode.NBN_ATLAS:
                name_columns = ["scientificName", "Scientific name"]
            else:
                name_columns = [self._get_column_mapping().get("species_name", "")]
            dialog = SpeciesMatchReportDialog(self.validated_rows, self, uksi_model=uksi,
                                              name_columns=name_columns)
            dialog.exec()
            if dialog.changed_rows():
                self._refresh_after_species_change()
        except Exception as e:
            print(f"Match report error: {e}")
