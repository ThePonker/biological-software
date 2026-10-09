"""
Validation Table Model for Specimen Import Wizard.

The table itself is shared with the scheme wizard (import_common, C4); this says which
columns the specimen wizard shows.
"""

from ..import_common.validation_table_model import ImportValidationTableModel
from .validation_worker import ImportRow, RowStatus


class ValidationTableModel(ImportValidationTableModel):
    """Validation results for specimen rows (ImportRow)."""

    COLUMNS = ["Status", "Row", "Species", "Date", "Grid Ref", "VC", "Location", "Message"]
    MESSAGE_COLUMN = 7
    EDITABLE_COLUMNS = (3, 4, 6)                 # Date, Grid Ref, Location

    def _get_display_value(self, row: ImportRow, col: int) -> str:
        if col == 0:  # Status
            if row.status == RowStatus.VALID:
                return "[OK]"
            elif row.status == RowStatus.WARNING:
                return "[!]"
            else:
                return "[X]"
        elif col == 1:  # Row number
            return str(row.row_number)
        elif col == 2:  # Species
            return row.species_name or ""
        elif col == 3:  # Date
            return row.date_collected or ""
        elif col == 4:  # Grid Ref
            return row.grid_ref or ""
        elif col == 5:  # VC
            return f"VC{row.vc_number}" if row.vc_number else ""
        elif col == 6:  # Location
            return row.site_name or ""
        elif col == 7:  # Message
            if row.status == RowStatus.ERROR:
                return row.error_message or ""
            else:
                return "; ".join(row.warnings) if row.warnings else ""
        return ""
