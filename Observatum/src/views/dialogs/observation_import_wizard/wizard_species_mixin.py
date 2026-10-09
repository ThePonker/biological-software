"""
Species Resolution Mixin for Observation Import Wizard.

Contains species resolution dialog handling for unmatched species
found during validation of personal/commercial uploads.
"""

from typing import Dict, List

from PySide6.QtWidgets import QDialog, QMessageBox

from .validation_worker import ObservationImportRow, RowStatus
from ..specimen_import_wizard.bulk_resolution_dialog import BulkSpeciesResolutionDialog
from ....core.config import TabColors


class WizardSpeciesResolutionMixin:
    """Mixin providing species resolution methods for ObservationImportWizard."""

    def _get_unmatched_species(self) -> List[str]:
        """Get list of unique species names that failed UKSI lookup."""
        unmatched = set()
        for row in self.validated_rows:
            if row.status == RowStatus.ERROR and row.error_message:
                if "Species not found in UKSI" in row.error_message:
                    unmatched.add(row.species_name)
        return sorted(list(unmatched))

    def _show_bulk_resolution_dialog(self, unmatched_species: List[str]):
        """Show the bulk species resolution dialog with observation theme."""
        dialog = BulkSpeciesResolutionDialog(
            self,
            uksi_model=self.uksi_model,
            unmatched_species=unmatched_species,
            alias_service=None,
            accent=TabColors.OBSERVATION,
            accent_light=TabColors.OBSERVATION_LIGHT,
            accent_dark=TabColors.OBSERVATION_DARK,
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            resolutions = dialog.get_resolutions()
            self._apply_species_resolutions(resolutions)

            # Save aliases if requested
            aliases_to_save = dialog.get_aliases_to_save()
            if aliases_to_save:
                self._save_observation_aliases(aliases_to_save)

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
        """Apply species resolutions to validated rows."""
        resolved_count = 0
        for row in self.validated_rows:
            if row.species_name in resolutions:
                resolved_count += 1
                uksi_data = resolutions[row.species_name]
                original_name = row.species_name

                new_name = uksi_data.get("scientific_name", row.species_name)
                row.species_name = new_name
                row.species_tvk = uksi_data.get("tvk", "")
                row.common_name = uksi_data.get("common_name", "")
                row.order_name = uksi_data.get("order_name", "")
                row.family = uksi_data.get("family", "")
                row.kingdom = uksi_data.get("kingdom", "")
                row.taxon_group = uksi_data.get("taxon_group", "")

                row.import_notes = (
                    f"Original: '{original_name}' -> "
                    f"Resolved via bulk lookup to '{new_name}'"
                )

                if row.status == RowStatus.ERROR and "Species not found" in row.error_message:
                    other_errors = [
                        e for e in row.error_message.split("; ")
                        if "Species not found" not in e
                    ]
                    if other_errors:
                        row.error_message = "; ".join(other_errors)
                        row.status = RowStatus.ERROR
                    else:
                        row.error_message = ""
                        if row.warnings:
                            row.warnings.append("Species resolved via bulk lookup")
                            row.status = RowStatus.WARNING
                        else:
                            row.warnings = ["Species resolved via bulk lookup"]
                            row.status = RowStatus.WARNING

                self._update_table_row_display_resolved(row)

    def _update_table_row_display_resolved(self, row: ObservationImportRow):
        """Update a single row in the validation table after resolution."""
        import_mode = self._get_selected_mode()
        for row_idx, validated_row in enumerate(self.validated_rows):
            if validated_row.row_number == row.row_number:
                self._update_table_row_display(row_idx, row, import_mode)
                break

    def _save_observation_aliases(self, aliases_to_save: dict):
        """Save species aliases for future imports."""
        try:
            from ....services.species_alias_service import SpeciesAliasService
            from ....models.database import get_database
            db = get_database()
            if db:
                alias_service = SpeciesAliasService(db_manager=db)
                for original_name, uksi_data in aliases_to_save.items():
                    alias_service.save_alias(
                        input_name=original_name,
                        uksi_name=uksi_data.get("scientific_name", ""),
                        uksi_tvk=uksi_data.get("tvk", ""),
                        uksi_common_name=uksi_data.get("common_name", ""),
                        uksi_order=uksi_data.get("order_name", ""),
                        uksi_family=uksi_data.get("family", ""),
                    )
                print(f"[ObsImportWizard] Saved {len(aliases_to_save)} species aliases")
        except Exception as e:
            print(f"[ObsImportWizard] Error saving aliases: {e}")

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
            f"* No: Continue and import without TVK for unmatched species",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )

        if result == QMessageBox.StandardButton.Yes:
            self._show_bulk_resolution_dialog(unmatched)

        # Show persistent button whether user chose Yes or No
        if hasattr(self, "resolve_species_btn"):
            self.resolve_species_btn.setVisible(True)
