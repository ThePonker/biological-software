"""
Species Resolution Mixin for Specimen Import Wizard.

Contains species resolution dialog handling and alias management.
"""

from typing import Dict, List

from PySide6.QtWidgets import QDialog, QMessageBox

from .validation_worker import RowStatus
from .bulk_resolution_dialog import BulkSpeciesResolutionDialog

from ...themes import theme


class WizardSpeciesResolutionMixin:
    """Mixin providing species resolution methods for SpecimenImportWizard."""
    
    def _get_unmatched_species(self) -> List[str]:
        """Get list of unique species names that failed UKSI lookup."""
        unmatched = set()
        
        for row in self.validated_rows:
            if row.status == RowStatus.ERROR and row.error_message:
                if "Species not found in UKSI" in row.error_message:
                    unmatched.add(row.species_name)
        
        return sorted(list(unmatched))
    
    def _show_bulk_resolution_dialog(self, unmatched_species: List[str]):
        """Show the bulk species resolution dialog."""
        dialog = BulkSpeciesResolutionDialog(
            self,
            uksi_model=self.uksi_model,
            unmatched_species=unmatched_species,
            alias_service=self.alias_service
        )
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            resolutions = dialog.get_resolutions()
            aliases_to_save = dialog.get_aliases_to_save()
            
            # Save aliases
            if self.alias_service and aliases_to_save:
                self._save_species_aliases(aliases_to_save)
            
            self._apply_species_resolutions(resolutions)
        
        self._update_validation_counts()
    
    def _save_species_aliases(self, aliases_to_save: Dict[str, dict]):
        """Save species aliases to database and memory."""
        for original_name, uksi_data in aliases_to_save.items():
            self.alias_service.save_alias(
                input_name=original_name,
                uksi_name=uksi_data.get('scientific_name', ''),
                uksi_tvk=uksi_data.get('tvk', ''),
                uksi_common_name=uksi_data.get('common_name', ''),
                uksi_order=uksi_data.get('order_name', ''),
                uksi_family=uksi_data.get('family', ''),
                uksi_subfamily=uksi_data.get('subfamily', '')
            )
            # Add to in-memory aliases
            key = original_name.lower().strip()
            self.species_aliases[key] = {
                'uksi_name': uksi_data.get('scientific_name', ''),
                'uksi_tvk': uksi_data.get('tvk', ''),
                'uksi_common_name': uksi_data.get('common_name', ''),
                'uksi_order': uksi_data.get('order_name', ''),
                'uksi_family': uksi_data.get('family', ''),
                'uksi_subfamily': uksi_data.get('subfamily', '')
            }
        
        print(f"[SpecimenImportWizard] Saved {len(aliases_to_save)} new species aliases")
    
    def _apply_species_resolutions(self, resolutions: Dict[str, dict]):
        """Apply species resolutions to validated rows."""
        for row in self.validated_rows:
            if row.species_name in resolutions:
                uksi_data = resolutions[row.species_name]
                original_name = row.species_name
                
                # Update row with resolved data
                new_name = uksi_data.get('scientific_name', row.species_name)
                row.species_name = new_name
                row.species_tvk = uksi_data.get('tvk', '')
                row.common_name = uksi_data.get('common_name', '')
                row.order_name = uksi_data.get('order_name', '')
                row.family = uksi_data.get('family', '')
                row.subfamily = uksi_data.get('subfamily', '')
                
                row.import_notes = f"Original: '{original_name}' → Resolved via bulk lookup to '{new_name}'"
                
                # Update status
                if row.status == RowStatus.ERROR and "Species not found" in row.error_message:
                    other_errors = [e for e in row.error_message.split("; ")
                                    if "Species not found" not in e]
                    if other_errors:
                        row.error_message = "; ".join(other_errors)
                    else:
                        row.status = RowStatus.WARNING if row.warnings else RowStatus.VALID
                        row.error_message = ""
                        if row.warnings:
                            row.warnings.append("Species resolved via bulk lookup")
                        else:
                            row.warnings = ["Species resolved via bulk lookup"]
                
                self._update_row_in_table(row)
    
    def _update_row_in_table(self, row):
        """Update a single row's display in the validation table."""
        from .validation_worker import ImportRow
        for row_idx, validated_row in enumerate(self.validated_rows):
            if validated_row.row_number == row.row_number:
                self._update_table_row_display(row_idx, row)
                break
