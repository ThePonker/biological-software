"""
Validation Table Model for Recording Scheme Import Wizard.

The table itself is shared with the specimen wizard (import_common, C4); this says which
columns the scheme wizard shows.
"""

from ..import_common.validation_table_model import ImportValidationTableModel
from .validation_worker import SchemeImportRow, RowStatus


class SchemeValidationTableModel(ImportValidationTableModel):
    """Validation results for recording-scheme rows (SchemeImportRow)."""

    COLUMNS = ["Status", "Row", "Species", "Date", "Grid Ref", "Site", "Message"]
    MESSAGE_COLUMN = 6
    COLOURED_COLUMNS = (0, 6)
    EDITABLE_COLUMNS = (3, 4, 5)                 # Date, Grid Ref, Site (Species: double-click)
    EDIT_FIELDS = {3: "date", 4: "grid_ref", 5: "site_name"}

    def _get_display_value(self, row: SchemeImportRow, col: int) -> str:
        if col == 0:
            if row.status == RowStatus.VALID:
                return "✓"
            elif row.status == RowStatus.WARNING:
                return "⚠"
            elif row.status == RowStatus.PENDING:
                return "..."
            else:
                return "✗"
        elif col == 1:
            return str(row.row_number)
        elif col == 2:
            return row.species_name or ""
        elif col == 3:
            return row.date or ""
        elif col == 4:
            return row.grid_ref or ""
        elif col == 5:
            return row.site_name or ""
        elif col == 6:
            message = row.error_message or ""
            if row.import_notes:
                if message:
                    message += " | "
                message += row.import_notes
            return message
        return ""
