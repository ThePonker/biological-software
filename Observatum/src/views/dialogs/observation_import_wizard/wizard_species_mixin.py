"""
Species Resolution Mixin for Observation Import Wizard.

Contains species resolution dialog handling for unmatched species
found during validation of personal/commercial uploads.
"""

from typing import Dict, List

from PySide6.QtWidgets import QDialog, QMessageBox

from shared.species_lookup import is_unresolved_error
from shared.species_lookup_entries import apply_confirmed

from .validation_worker import ObservationImportRow, RowStatus
from ..specimen_import_wizard.bulk_resolution_dialog import BulkSpeciesResolutionDialog
from ....core.config import TabColors


class WizardSpeciesResolutionMixin:
    """Mixin providing species resolution methods for ObservationImportWizard."""

    def _get_unmatched_species(self) -> List[str]:
        """Get list of unique species names that failed UKSI lookup."""
        unmatched = set()
        for row in self.validated_rows:
            if row.status == RowStatus.ERROR and is_unresolved_error(row.error_message):
                unmatched.add(row.species_name)
        return sorted(list(unmatched))

    def _show_bulk_resolution_dialog(self, unmatched_species: List[str]):
        """Show the bulk species resolution dialog with observation theme."""
        dialog = BulkSpeciesResolutionDialog(
            self,
            uksi_model=self.uksi_model,
            unmatched_species=unmatched_species,
            accent=TabColors.OBSERVATION,
            accent_light=TabColors.OBSERVATION_LIGHT,
            accent_dark=TabColors.OBSERVATION_DARK,
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._apply_species_resolutions(dialog.get_resolutions())

        self._update_validation_counts()

        # Re-enable Next button after bulk resolution
        valid = sum(1 for r in self.validated_rows if r.status == RowStatus.VALID)
        warnings = sum(1 for r in self.validated_rows if r.status == RowStatus.WARNING)
        if valid > 0 or warnings > 0:
            self.next_btn.setEnabled(True)
        # Disable revalidate - bulk resolution doesn't need revalidation
        if hasattr(self, 'revalidate_btn'):
            self.revalidate_btn.setEnabled(False)

    def _apply_species_resolutions(self, resolutions: Dict[str, dict]):
        """Apply species resolutions to validated rows (only the species error goes)."""
        for row in self.validated_rows:
            if row.species_name in resolutions:
                apply_confirmed(row, resolutions[row.species_name], row.species_name,
                                "resolved by you")
                self._update_table_row_display_resolved(row)

    def _update_table_row_display_resolved(self, row: ObservationImportRow):
        """Update a single row in the validation table after resolution."""
        import_mode = self._get_selected_mode()
        for row_idx, validated_row in enumerate(self.validated_rows):
            if validated_row.row_number == row.row_number:
                self._update_table_row_display(row_idx, row, import_mode)
                break

    def _prompt_resolve_unmatched(self):
        """Check for unmatched species after validation and prompt user."""
        unmatched = self._get_unmatched_species()
        if not unmatched:
            return

        result = QMessageBox.question(
            self,
            "Unmatched Species Found",
            f"Found {len(unmatched)} unique species that could not be matched to UKSI.\n\n"
            f"Would you like to resolve them now?\n\n"
            f"* Yes: Open bulk resolution dialog to fix species matching\n"
            f"* No: Leave them as errors (they will not be imported until resolved)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )

        if result == QMessageBox.StandardButton.Yes:
            self._show_bulk_resolution_dialog(unmatched)

        # Show persistent button whether user chose Yes or No
        if hasattr(self, "resolve_species_btn"):
            self.resolve_species_btn.setVisible(True)
