"""
Observation Export Mixin

Handles export functionality for ObservationTab.
"""

from typing import Dict


class ObservationExportMixin:
    """Mixin providing export functionality."""

    def _on_export_selected(self):
        """Export selected (checked) observations."""
        checked_rows = self.table_model.get_checked_rows()
        if not checked_rows:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "No Selection", "Please check at least one row to export.")
            return

        # Get observations for checked rows
        observations = []
        for row in checked_rows:
            obs = self._get_observation_at_row(row)
            if obs:
                # Convert to dict if needed
                if isinstance(obs, dict):
                    observations.append(obs)
                else:
                    observations.append(obs.__dict__ if hasattr(obs, '__dict__') else vars(obs))

        if not observations:
            return

        self._export_observations(observations, "Export Selected Observations")

    def _on_export_all(self):
        """Export all observations."""
        # Get all observations from model
        observations = []
        for row in range(self.table_model.rowCount()):
            obs = self._get_observation_at_row(row)
            if obs:
                # Convert to dict if needed
                if isinstance(obs, dict):
                    observations.append(obs)
                else:
                    observations.append(obs.__dict__ if hasattr(obs, '__dict__') else vars(obs))

        if not observations:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "No Data", "No observations to export.")
            return

        self._export_observations(observations, "Export All Observations")

    def _export_observations(self, observations: list, dialog_title: str):
        """Common export logic for observations."""
        from PySide6.QtWidgets import (
            QFileDialog, QMessageBox, QDialog, QVBoxLayout,
            QRadioButton, QDialogButtonBox, QLabel
        )
        from PySide6.QtCore import QSettings
        from src.core.config import Settings
        from src.themes import theme
        import os

        # Ask export format
        t = theme()
        fmt_dialog = QDialog(self)
        fmt_dialog.setWindowTitle("Export Format")
        fmt_dialog.setMinimumWidth(350)
        fmt_layout = QVBoxLayout(fmt_dialog)

        label = QLabel("Choose export format:")
        label.setStyleSheet(f"font-weight: bold; color: {t.get('text_primary')};")
        fmt_layout.addWidget(label)

        radio_style = f"""
            QRadioButton {{
                padding: 8px 12px;
                border: 1px solid {t.get('border')};
                border-radius: 4px;
                color: {t.get('text_primary')};
            }}
            QRadioButton:checked {{
                background-color: #e8f0ea;
                border-color: #4a7c59;
                color: #4a7c59;
                font-weight: bold;
            }}
        """

        all_cols_radio = QRadioButton("All columns (full data export)")
        all_cols_radio.setChecked(True)
        all_cols_radio.setStyleSheet(radio_style)
        fmt_layout.addWidget(all_cols_radio)

        irecord_radio = QRadioButton("iRecord format (for upload to iRecord)")
        irecord_radio.setStyleSheet(radio_style)
        fmt_layout.addWidget(irecord_radio)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(fmt_dialog.accept)
        buttons.rejected.connect(fmt_dialog.reject)
        fmt_layout.addWidget(buttons)

        if fmt_dialog.exec() != QDialog.DialogCode.Accepted:
            return

        use_irecord = irecord_radio.isChecked()

        # Filter embargoed records for iRecord export
        embargo_excluded = 0
        never_upload_excluded = 0
        if use_irecord:
            from datetime import date
            today = date.today().isoformat()
            filtered = []
            for obs in observations:
                # Skip records flagged as never upload
                if obs.get('never_upload_to_irecord'):
                    never_upload_excluded += 1
                    continue
                # Skip records under active embargo
                embargo = obs.get('embargo_status', '')
                until = obs.get('embargo_until', '')
                if embargo == 'Active' and until and until > today:
                    embargo_excluded += 1
                    continue
                filtered.append(obs)
            observations = filtered

            if embargo_excluded or never_upload_excluded:
                excluded_msg = []
                if embargo_excluded:
                    excluded_msg.append(f"{embargo_excluded} embargoed")
                if never_upload_excluded:
                    excluded_msg.append(f"{never_upload_excluded} marked never upload")
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.information(
                    self, "Records Excluded",
                    f"{' and '.join(excluded_msg)} record(s) excluded from iRecord export."
                    f"\n\n{len(observations)} records will be exported."
                )
                if not observations:
                    return

        # Get default export path from settings
        settings = QSettings()
        default_path = settings.value(Settings.EXPORT_DEFAULT_PATH, "")
        default_file = os.path.join(default_path, "observations_export.csv") if default_path else ""

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            dialog_title,
            default_file,
            "CSV Files (*.csv);;Excel Files (*.xlsx)"
        )
        if not file_path:
            return

        # Export using service
        try:
            from ...services.export_service import ExportService
            export_service = ExportService()

            if file_path.endswith('.xlsx'):
                export_service.export_to_excel(observations, file_path)
            else:
                if use_irecord:
                    columns, headers = export_service.get_irecord_columns()
                    export_service.export_to_csv(observations, file_path, columns, headers)
                else:
                    export_service.export_to_csv(observations, file_path, columns=None, headers=None)

            QMessageBox.information(
                self,
                "Export Complete",
                f"Exported {len(observations)} observations to:\n{file_path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export: {e}")

    def _get_observation_at_row(self, row: int):
        """Get observation data for a given row."""
        # Map proxy row to source row if using proxy
        source_row = self.sort_proxy.mapToSource(self.sort_proxy.index(row, 0)).row()

        # Use the model's get_observation_at_row method
        return self.table_model.get_observation_at_row(source_row)
