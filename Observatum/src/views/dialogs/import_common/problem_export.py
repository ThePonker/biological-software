"""'Export problems' for the observation and specimen import wizards (C4, 9 Oct 2026; each
had its own copy, differing only in the suggested file name).

Writes every error / warning row as it was read from the file, with its status, row number
and message in front, so it can be corrected and imported again. Needs self.validated_rows
and self.columns from the wizard; the scheme wizard writes a different layout of its own."""
import csv

from PySide6.QtWidgets import QFileDialog, QMessageBox

from ..row_status import RowStatus


class ProblemExportMixin:
    PROBLEMS_FILE_NAME = "import_problems.csv"

    def _export_problems(self):
        """Export problem rows to CSV for manual correction."""
        problems = [r for r in self.validated_rows
                    if r.status in (RowStatus.ERROR, RowStatus.WARNING)]

        if not problems:
            QMessageBox.information(self, "No Problems", "No problem rows to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Problem Rows",
            self.PROBLEMS_FILE_NAME,
            "CSV Files (*.csv)"
        )

        if not file_path:
            return

        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                fieldnames = ['_Status', '_Row', '_Error'] + self.columns
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for row in problems:
                    output_row = {
                        '_Status': row.status.value,
                        '_Row': row.row_number,
                        '_Error': row.error_message,
                    }
                    output_row.update(row.raw_data)
                    writer.writerow(output_row)

            QMessageBox.information(
                self,
                "Export Complete",
                f"Exported {len(problems)} problem rows to:\n{file_path}"
            )

        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export:\n{str(e)}")
