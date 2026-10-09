"""Insect Collection Tab — Export & Special Views Mixin

Handles CSV export (all / selected) and the New Collections List view.
"""
import csv
import os

from PySide6.QtCore import Qt, QSettings

from ...models.database import get_database
from ...core.config import Settings


class ICExportMixin:
    """Mixin providing export and special-view methods for InsectCollectionTab."""

    # ── Export ───────────────────────────────────────────────────────

    def _on_export_all(self):
        """Export all specimens to CSV."""
        from PySide6.QtWidgets import QFileDialog, QMessageBox

        specimens = self.table_model._specimens
        if not specimens:
            QMessageBox.information(self, "No Data", "No specimens to export.")
            return

        settings = QSettings()
        default_path = settings.value(Settings.EXPORT_DEFAULT_PATH, "")
        default_file = (
            os.path.join(default_path, "specimens_export.csv")
            if default_path else "specimens_export.csv"
        )

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Specimens", default_file,
            "CSV Files (*.csv);;All Files (*)"
        )

        if file_path:
            self._export_specimens_to_csv(specimens, file_path)

    def _on_export_selected(self):
        """Export selected specimens to CSV."""
        from PySide6.QtWidgets import QFileDialog, QMessageBox

        checked_rows = self.table_model.get_checked_rows()
        if not checked_rows:
            QMessageBox.information(
                self, "No Selection", "No specimens selected for export."
            )
            return

        specimens = self.table_model.get_checked_specimens()

        settings = QSettings()
        default_path = settings.value(Settings.EXPORT_DEFAULT_PATH, "")
        default_file = (
            os.path.join(default_path, "specimens_selected_export.csv")
            if default_path else "specimens_selected_export.csv"
        )

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Selected Specimens", default_file,
            "CSV Files (*.csv);;All Files (*)"
        )

        if file_path:
            self._export_specimens_to_csv(specimens, file_path)

    def _export_specimens_to_csv(self, specimens, file_path: str):
        """Export specimens list to CSV file."""
        from PySide6.QtWidgets import QMessageBox

        export_columns = [
            ('specimen_code', 'Specimen Code'),
            ('date_collected', 'Date'),
            ('species_name', 'Species'),
            ('species_tvk', 'TVK'),
            ('common_name', 'Common Name'),
            ('order_name', 'Order'),
            ('family', 'Family'),
            ('subfamily', 'Subfamily'),
            ('site_name', 'Location'),
            ('grid_ref', 'Grid Ref'),
            ('vice_county', 'Vice County'),
            ('vc_number', 'VC Number'),
            ('collector', 'Collector'),
            ('determiner', 'Determiner'),
            ('sex', 'Sex'),
            ('preparation_type', 'Prep Type'),
            ('storage_location', 'Storage'),
            ('drawer_number', 'Drawer'),
            ('condition', 'Condition'),
            ('label_data', 'Label Data'),
            ('notes', 'Notes'),
        ]

        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([col[1] for col in export_columns])

                for specimen in specimens:
                    row = []
                    for col_key, _ in export_columns:
                        value = self.table_model._get_specimen_value(specimen, col_key)
                        row.append(value if value is not None else '')
                    writer.writerow(row)

            QMessageBox.information(
                self, "Export Complete",
                f"Successfully exported {len(specimens)} specimens to:\n{file_path}"
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Export Error",
                f"Failed to export specimens:\n{str(e)}"
            )

    # ── New Collections List ────────────────────────────────────────

    def _show_new_collections_list(self):
        """Show one row per unique species, by first collection date."""
        if not self._specimen_model and not self._specimen_repo:
            return

        self._current_view_mode = 'new_collections_list'

        try:
            if self._specimen_repo and hasattr(self._specimen_repo, 'get_new_species_first_specimens'):
                specimens = self._specimen_repo.get_new_species_first_specimens(limit=1000)
            else:
                query = """
                    SELECT * FROM specimens
                    WHERE id IN (
                        SELECT MIN(id)
                        FROM specimens
                        WHERE species_name IS NOT NULL
                        AND (species_name, date_collected) IN (
                            SELECT species_name, MIN(date_collected)
                            FROM specimens
                            WHERE species_name IS NOT NULL
                            GROUP BY species_name
                        )
                        GROUP BY species_name
                    )
                    ORDER BY date_collected DESC
                """
                db = get_database()
                results = db.execute_main(query)

                if results:
                    col_query = "PRAGMA table_info(specimens)"
                    col_info = db.execute_main(col_query)
                    columns = [c[1] for c in col_info]

                    specimens = []
                    for row in results:
                        specimen = {}
                        for i, col in enumerate(columns):
                            if i < len(row):
                                specimen[col] = row[i]
                        specimens.append(specimen)
                else:
                    specimens = []

            self.table_model.set_specimens(specimens)
            self._connect_proxy_after_load()

            self.toolbar.set_counts(len(specimens), len(specimens))
            self.table_view.sortByColumn(2, Qt.SortOrder.DescendingOrder)

        except Exception as e:
            print(f"[InsectCollectionTab] Error loading new collections list: {e}")
            import traceback
            traceback.print_exc()
