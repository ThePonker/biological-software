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

        self._export_observations(observations, "Export All Observations", ask_counting=True)

    def _export_counting_filter(self, observations: list):
        """Export All, "All columns": counted records only (default), include the excluded
        ones, or only them (species-counting switches; answer 6 of note 38). None = cancel."""
        from shared.species_counting import EXPORT_INCLUDE, EXPORT_ONLY
        from ..components.counting_widgets import ask_export_mode
        reasons = getattr(self, '_excluded_now', None) or {}
        if not reasons:
            return observations
        mode = ask_export_mode(self, "observations")
        if mode is None:
            return None
        if mode == EXPORT_INCLUDE:
            return observations
        keep_excluded = mode == EXPORT_ONLY
        return [o for o in observations if (o.get('id') in reasons) == keep_excluded]

    def _export_observations(self, observations: list, dialog_title: str, ask_counting=False):
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
        if ask_counting and not use_irecord:     # the iRecord export always takes every record
            observations = self._export_counting_filter(observations)
            if observations is None:
                return
            if not observations:
                QMessageBox.information(self, "No Data", "No observations to export.")
                return

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

        # Exported before and not back from iRecord yet (14 Oct 2026): sending them again would
        # put a second copy in iRecord, unless the earlier upload failed
        if use_irecord:
            observations = self._leave_out_exported(observations)
            if not observations:
                return

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
        stamped = None
        try:
            from ...services.export_service import ExportService
            export_service = ExportService()

            if file_path.endswith('.xlsx'):
                export_service.export_to_excel(observations, file_path)
            else:
                if use_irecord:
                    # 14 Oct 2026: the External key must name one record, or iRecord's copy
                    # cannot be matched back (the sync guard then holds it)
                    shared = self._shared_keys(observations)
                    if shared:
                        QMessageBox.warning(
                            self, "Export for iRecord",
                            f"{len(shared)} of these records share their Observatum key with "
                            "another record, so iRecord could not send them back to the right "
                            "record. Nothing was exported.\n\nRun once (Observatum closed):\n"
                            "py -3.14 scripts\\renumber_duplicate_keys.py --apply")
                        return
                    columns, headers = export_service.get_irecord_columns()
                    export_service.export_to_csv(observations, file_path, columns, headers)
                    stamped = self._stamp_exported(observations)
                else:
                    export_service.export_to_csv(observations, file_path, columns=None, headers=None)

            note = ""
            if use_irecord and not file_path.endswith('.xlsx') and stamped is None:
                note = ("\n\nObservatum could not note these records as exported, so a second "
                        "export before the next sync would include them again. Run once "
                        "(Observatum closed):\npy -3.14 scripts\\add_irecord_exported_column.py --apply")
            QMessageBox.information(
                self,
                "Export Complete",
                f"Exported {len(observations)} observations to:\n{file_path}{note}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export: {e}")

    @staticmethod
    def _main_db_path() -> str:
        from ...models.database import get_database
        return str(getattr(get_database(), 'main_db_path', '') or '')

    def _leave_out_exported(self, observations: list) -> list:
        """Records exported for iRecord before that have not come back with an iRecord ID:
        left out unless Wil says the earlier upload failed. [] = stop."""
        import sqlite3
        from PySide6.QtWidgets import QMessageBox
        from shared import irecord_exported
        path = self._main_db_path()
        if not path:
            return observations
        try:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            try:
                waiting = irecord_exported.waiting(conn, [o.get('id') for o in observations])
            finally:
                conn.close()
        except sqlite3.Error:
            return observations
        if not waiting:
            return observations
        last = max(waiting.values())
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Exported before")
        box.setText(f"{len(waiting)} of these records were exported for iRecord before (latest "
                    f"{last}) and have not come back from iRecord yet.\n\nSending them again "
                    "would put a second copy in iRecord. Upload the earlier file and run the "
                    "iRecord sync first; include them again only if that upload failed.")
        leave = box.addButton("Leave them out", QMessageBox.ButtonRole.AcceptRole)
        again = box.addButton("Include them again", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(leave)
        box.exec()
        if box.clickedButton() is again:
            return observations
        if box.clickedButton() is not leave:
            return []
        keep = [o for o in observations if o.get('id') not in waiting]
        if not keep:
            QMessageBox.information(self, "Nothing to Export to iRecord",
                                    "Every record was exported before, so no file has been written.")
        return keep

    def _stamp_exported(self, observations: list):
        """Note the exported records (shared/irecord_exported). Rows stamped, or None when the
        column is missing or the write failed."""
        import sqlite3
        from shared import irecord_exported
        path = self._main_db_path()
        if not path:
            return None
        try:
            conn = sqlite3.connect(path)
            try:
                if not irecord_exported.has_column(conn):
                    return None
                with conn:
                    return irecord_exported.stamp(conn, [o.get('id') for o in observations])
            finally:
                conn.close()
        except sqlite3.Error as e:
            print(f"[ObservationTab] exported records not noted: {e}")
            return None

    @staticmethod
    def _shared_keys(observations: list) -> list:
        """The keys among these records that more than one record in observatum.db holds."""
        keys = [getattr(o, 'observatum_key', None) or (o.get('observatum_key') if isinstance(o, dict) else None)
                for o in observations]
        keys = [k for k in dict.fromkeys(keys) if k]
        if not keys:
            return []
        from ...models.database import get_database
        db = get_database()
        out = []
        for i in range(0, len(keys), 900):
            part = keys[i:i + 900]
            rows = db.execute_main(
                f"SELECT observatum_key FROM observations WHERE observatum_key IN "
                f"({','.join('?' * len(part))}) GROUP BY observatum_key HAVING COUNT(*) > 1", tuple(part))
            out += [r[0] for r in rows]
        return out

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
