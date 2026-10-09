"""
Species Resolution Mixin for Specimen Import Wizard.

Contains species resolution dialog handling. (Saved aliases are no longer written or read:
UKSI's synonyms cover them -- 9 Oct 2026.)
"""

from typing import Dict, List

from PySide6.QtWidgets import QDialog

from shared.species_lookup import is_unresolved_error
from shared.species_lookup_entries import apply_confirmed

from .validation_worker import RowStatus
from .bulk_resolution_dialog import BulkSpeciesResolutionDialog



class WizardSpeciesResolutionMixin:
    """Mixin providing species resolution methods for SpecimenImportWizard."""
    
    def _get_unmatched_species(self) -> List[str]:
        """Get list of unique species names that failed UKSI lookup."""
        unmatched = set()
        
        for row in self.validated_rows:
            if row.status == RowStatus.ERROR and is_unresolved_error(row.error_message):
                unmatched.add(row.species_name)
        
        return sorted(list(unmatched))
    
    def _show_bulk_resolution_dialog(self, unmatched_species: List[str]):
        """Show the bulk species resolution dialog."""
        dialog = BulkSpeciesResolutionDialog(
            self,
            uksi_model=self.uksi_model,
            unmatched_species=unmatched_species,
        )
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._apply_species_resolutions(dialog.get_resolutions())
        
        self._update_validation_counts()

        # Re-enable Next button after bulk resolution
        valid = sum(1 for r in self.validated_rows if r.status == RowStatus.VALID)
        warnings = sum(1 for r in self.validated_rows if r.status == RowStatus.WARNING)
        errors = sum(1 for r in self.validated_rows if r.status == RowStatus.ERROR)
        if valid > 0 or warnings > 0:
            self.next_btn.setEnabled(True)
        # Show Resolve Species button if errors remain
        if hasattr(self, 'resolve_species_btn'):
            self.resolve_species_btn.setVisible(errors > 0)
    
    def _apply_species_resolutions(self, resolutions: Dict[str, dict]):
        """Apply species resolutions to validated rows."""
        for row in self.validated_rows:
            if row.species_name in resolutions:
                apply_confirmed(row, resolutions[row.species_name], row.species_name,
                                "resolved by you")
                self._update_row_in_table(row)
    
    def _update_row_in_table(self, row):
        """Update a single row's display in the validation table."""
        for row_idx, validated_row in enumerate(self.validated_rows):
            if validated_row.row_number == row.row_number:
                self._update_table_row_display(row_idx, row)
                break
