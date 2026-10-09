"""
Observation Export Mixin

Handles export functionality for ObservationTab.
"""



class ObservationExportMixin:
    """Mixin providing export functionality."""

    def _on_export_selected(self):
        """Export selected (checked) observations."""
        # The ticked records themselves, held by id: a sort cannot swap them (OBS-01).
        # (This used to map model row numbers through the proxy a second time.)
        observations = self.table_model.get_checked_observations()
        if not observations:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "No Selection", "Please check at least one row to export.")
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

        # Filter records that must not go to iRecord
        if use_irecord:
            observations, excluded = self._irecord_export_filter(observations)
            embargo_excluded = excluded['embargo']
            never_upload_excluded = excluded['never_upload']
            from_irecord_excluded = excluded['from_irecord']

            if embargo_excluded or never_upload_excluded or from_irecord_excluded:
                excluded_msg = []
                if from_irecord_excluded:
                    excluded_msg.append(
                        f"{from_irecord_excluded} came from iRecord (already there -- "
                        f"uploading them again would make duplicates)")
                if embargo_excluded:
                    excluded_msg.append(f"{embargo_excluded} under embargo")
                if never_upload_excluded:
                    excluded_msg.append(f"{never_upload_excluded} marked never upload")
                excluded_text = '; '.join(excluded_msg)

                if not observations:
                    # Nothing left: say so plainly and stop -- no Save dialog follows.
                    total = embargo_excluded + never_upload_excluded + from_irecord_excluded
                    QMessageBox.information(
                        self, "Nothing to Export to iRecord",
                        f"All {total} record(s) are excluded from iRecord export "
                        f"({excluded_text}), so no file has been written."
                        f"\n\nFor a client export, choose \"All columns\" instead."
                    )
                    return

                QMessageBox.information(
                    self, "Records Excluded",
                    f"Excluded from the iRecord export: {excluded_text}."
                    f"\n\n{len(observations)} record(s) will be exported."
                )

        # Get default export path from settings
        settings = QSettings()
        default_path = settings.value(Settings.EXPORT_DEFAULT_PATH, "")
        default_name = self._export_file_name(observations, use_irecord)
        default_file = os.path.join(default_path, default_name) if default_path else default_name

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

    @staticmethod
    def _irecord_export_filter(observations: list):
        """(records to send, {'from_irecord', 'embargo', 'never_upload': counts}).

        Left out, each counted once under the first reason that applies:
          - records that came from iRecord (an iRecord id, or a source starting
            'iRecord') -- they are already there; sending them back duplicates them
            (review OBS-12, 9 Oct 2026);
          - records marked never upload;
          - records under an active embargo.
        """
        from datetime import date
        today = date.today().isoformat()
        keep = []
        counts = {'from_irecord': 0, 'embargo': 0, 'never_upload': 0}
        for obs in observations:
            irecord_id = obs.get('irecord_id')
            source = str(obs.get('source') or '').strip()
            if (irecord_id not in (None, '', 0)) or source.lower().startswith('irecord'):
                counts['from_irecord'] += 1
                continue
            if obs.get('never_upload_to_irecord'):
                counts['never_upload'] += 1
                continue
            embargo = obs.get('embargo_status', '')
            until = obs.get('embargo_until', '')
            if embargo == 'Active' and until and until > today:
                counts['embargo'] += 1
                continue
            keep.append(obs)
        return keep, counts

    @staticmethod
    def _export_file_name(observations: list, use_irecord: bool) -> str:
        """Suggested file name: '<project or site>_<YYYY-MM-DD>[_iRecord].csv'.

        Uses the project name if every exported record shares one, otherwise
        the site name if they share one, otherwise 'observations'. The date is
        today's, so exports of different jobs never share a name.
        """
        import re
        from datetime import date

        def single(key):
            values = {str(o.get(key) or '').strip() for o in observations}
            values.discard('')
            return values.pop() if len(values) == 1 else ''

        label = single('project_name') or single('site_name') or 'observations'
        label = re.sub(r'[\\/:*?"<>|]+', '-', label).strip(' .') or 'observations'
        suffix = '_iRecord' if use_irecord else ''
        return f"{label}_{date.today().isoformat()}{suffix}.csv"

    def _get_observation_at_row(self, row: int):
        """Get observation data for a given row."""
        # Map proxy row to source row if using proxy
        source_row = self.sort_proxy.mapToSource(self.sort_proxy.index(row, 0)).row()

        # Use the model's get_observation_at_row method
        return self.table_model.get_observation_at_row(source_row)
