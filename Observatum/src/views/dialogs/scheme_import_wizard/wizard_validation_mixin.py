"""
Wizard Validation Mixin for Recording Scheme Import Wizard.

Contains validation callbacks, live counter updates,
filtering, table population, and inline editing.
"""

import csv
from pathlib import Path
from typing import List, Optional

from PySide6.QtWidgets import (
    QApplication,
    QTableWidgetItem, QFileDialog, QDialog, QVBoxLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QCompleter,
    QMessageBox
)
from PySide6.QtCore import Qt, QStringListModel, QModelIndex

from .validation_worker import SchemeImportRow, RowStatus, SchemeValidationWorker, SchemeImportMode
from .validation_table_model import SchemeValidationTableModel
from src.themes import theme


class SpeciesSearchDialog(QDialog):
    """Dialog for searching UKSI species."""

    def __init__(self, parent, uksi_model, current_name: str = ""):
        super().__init__(parent)
        self.uksi_model = uksi_model
        self.selected_species = None
        self._setup_ui(current_name)

    def _setup_ui(self, current_name: str):
        t = theme()

        self.setWindowTitle("Search Species")
        self.setMinimumSize(500, 400)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Search input
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type species name...")
        self.search_input.setText(current_name)
        self.search_input.textChanged.connect(self._on_search)
        search_layout.addWidget(self.search_input, 1)
        layout.addLayout(search_layout)

        # Results list
        from PySide6.QtWidgets import QListWidget
        self.results_list = QListWidget()
        self.results_list.itemDoubleClicked.connect(self._on_select)
        layout.addWidget(self.results_list, 1)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        select_btn = QPushButton("Select")
        select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        select_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {t.get('success')};
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }}
        """)
        select_btn.clicked.connect(self._on_select)
        btn_layout.addWidget(select_btn)

        layout.addLayout(btn_layout)

        # Initial search
        if current_name:
            self._on_search(current_name)

    def _on_search(self, text: str):
        """Search UKSI for species."""
        self.results_list.clear()

        if not text or len(text) < 2:
            return

        if not self.uksi_model:
            return

        try:
            results = self.uksi_model.search_species(text, limit=50)
            for species in results:
                name = getattr(species, 'scientific_name', str(species))
                common = getattr(species, 'common_name', '')
                tvk = getattr(species, 'tvk', '')

                display = f"{name}"
                if common:
                    display += f" ({common})"

                from PySide6.QtWidgets import QListWidgetItem
                item = QListWidgetItem(display)
                item.setData(Qt.ItemDataRole.UserRole, {
                    'scientific_name': name,
                    'common_name': common,
                    'tvk': tvk,
                    'species': species
                })
                self.results_list.addItem(item)
        except Exception as e:
            print(f"Species search error: {e}")

    def _on_select(self):
        """Select the current species."""
        current = self.results_list.currentItem()
        if current:
            self.selected_species = current.data(Qt.ItemDataRole.UserRole)
            self.accept()


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

    def _on_table_double_clicked(self, index: QModelIndex):
        """Handle double-click on QTableView."""
        row = index.row()
        col = index.column()
        self._on_cell_double_clicked(row, col)
    
    def _on_cell_double_clicked(self, row: int, col: int):
        """Handle double-click for species search."""
        if col == 2:  # Species column
            if row < len(self.validated_rows):
                current_name = self.validated_rows[row].species_name
                dialog = SpeciesSearchDialog(self, self.uksi_model, current_name)
                if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_species:
                    species_data = dialog.selected_species
                    # Update the row
                    self.validated_rows[row].species_name = species_data['scientific_name']
                    self.validated_rows[row].species_tvk = species_data['tvk']
                    self.validated_rows[row].common_name = species_data['common_name']

                    # Update table
                    self.validation_table.item(row, 2).setText(species_data['scientific_name'])

                    # Mark for revalidation
                    self._edited_row_indices.add(row)

    def _on_cell_changed(self, row: int, col: int):
        """Handle cell edits."""
        if col in [2, 3, 4, 5]:  # Species, Date, Grid Ref, Site
            if row < len(self.validated_rows):
                item = self.validation_table.item(row, col)
                if item:
                    value = item.text()
                    if col == 2:
                        self.validated_rows[row].species_name = value
                    elif col == 3:
                        self.validated_rows[row].date = value
                    elif col == 4:
                        self.validated_rows[row].grid_ref = value
                    elif col == 5:
                        self.validated_rows[row].site_name = value

                    self._edited_row_indices.add(row)

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
        """Revalidate rows that were edited."""
        if not self._edited_row_indices:
            QMessageBox.information(self, "No Changes", "No rows have been edited.")
            return

        import_mode = self._get_selected_mode()
        column_mapping = self._get_column_mapping()

        # Create a mini-worker for revalidation
        rows_to_revalidate = [self.validated_rows[i] for i in self._edited_row_indices]

        worker = SchemeValidationWorker(
            rows=rows_to_revalidate,
            column_mapping=column_mapping,
            import_mode=import_mode,
            uksi_model=self.uksi_model,
            vc_db_path=self.vc_db_path,
            db_manager=self.db,
        )

        # Run synchronously for small batches
        worker.run()

        # Update validated rows and table
        for orig_idx, row in zip(self._edited_row_indices, worker.rows):
            self.validated_rows[orig_idx] = row
            self._on_row_validated(orig_idx, row)

        # Recalculate counts
        valid = sum(1 for r in self.validated_rows if r.status == RowStatus.VALID)
        warnings = sum(1 for r in self.validated_rows if r.status == RowStatus.WARNING)
        errors = sum(1 for r in self.validated_rows if r.status == RowStatus.ERROR)

        self._on_counts_updated(valid, warnings, errors)

        # Clear edited indices
        self._edited_row_indices.clear()

        QMessageBox.information(
            self, "Revalidation Complete",
            f"Revalidated {len(rows_to_revalidate)} row(s).\n"
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
        """Update confirmation page - now just logs counts since we use simpler layout."""
        new_count = sum(1 for r in self.validated_rows
                       if r.status != RowStatus.ERROR and not r.is_duplicate)
        duplicate_count = sum(1 for r in self.validated_rows
                             if r.status != RowStatus.ERROR and r.is_duplicate)
        error_count = sum(1 for r in self.validated_rows if r.status == RowStatus.ERROR)
        
        # Log counts for debugging (stat cards removed in new layout)
        print(f"Import counts - New: {new_count}, Duplicates: {duplicate_count}, Errors: {error_count}")
        
        # Update import status label if it exists
        if hasattr(self, 'import_status_label'):
            self.import_status_label.setText(
                f"Ready to import {new_count} records ({duplicate_count} duplicates, {error_count} errors)")

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
            dialog = SpeciesMatchReportDialog(self.validated_rows, self, uksi_model=uksi)
            dialog.exec()
        except Exception as e:
            print(f"Match report error: {e}")
