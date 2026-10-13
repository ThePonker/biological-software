"""Stats/Reports > Cleaning Report (backlog B, claude/38 answers 12-14; F71 / F72, 13 Oct).

The records to tidy in iRecord, one tile per problem, for Observation, Recording Scheme or
Contributed data (chosen at the top). Click a tile: its list shows beneath (the clicked tile
stays marked). The lists come from services/cleaning_report.py (no Qt there); the table is
views/stats/cleaning_table.py; every matching record is shown, whatever the species-counting
switches say.

The iRecord ID cell is a link where the record holds one; "Open in iRecord" is enabled only
for such a row (the tooltip says why otherwise); double-click opens iRecord, or the record
in Observatum (view only) when it has no iRecord ID. "Export" writes one .xlsx: a Summary
sheet and a sheet per problem.

Recording Scheme: the marked NBN copies of iRecord records (shared/scheme_duplicates.py)
are left out unless "Include NBN copies of iRecord records" is ticked; the header line and
the export say which. Observation: "Came back from iRecord -- check" lists records removed
here that a download brought back (still hidden); "Show again" un-hides one.
"""
from __future__ import annotations

import datetime as _dt
from typing import Dict, Optional

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QGridLayout, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

import paths
from ...models.database import get_database
from ...services.cleaning_export import export_csv_folder, export_xlsx, have_openpyxl
from ...services.cleaning_report import (
    OBSERVATION_ONLY, PROBLEMS, SOURCES, CleaningReport, CleaningRow, build_report, irecord_url,
)
from ...themes import theme
from .cleaning_table import CleaningRowModel, CleaningTableView, link_colour

_TILES_PER_ROW = 6
NO_ROW_TIP = "Select a record first."
NO_ID_TIP = "This record has no iRecord ID. Use Open in Observatum."
COPIES_LABEL = "Include NBN copies of iRecord records"


class CleaningDashboard(QWidget):
    """The cleaning report screen."""

    navigate_to_observations = Signal(str)
    navigate_to_collection = Signal(str)

    def __init__(self, parent=None, main_db=None, uksi_db=None):
        super().__init__(parent)
        self._main_db, self._uksi_db = main_db, uksi_db
        self._reports: Dict[tuple, CleaningReport] = {}
        self._models: Dict[str, CleaningRowModel] = {}
        self._views: Dict[str, CleaningTableView] = {}
        self._tiles: Dict[str, QPushButton] = {}
        self._keys = [k for k, _ in PROBLEMS]
        self.open_url = QDesktopServices.openUrl          # replaceable in tests
        self._setup_ui()

    # ------------------------------------------------------------------ layout
    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 16)
        root.setSpacing(10)

        top = QHBoxLayout()
        self.title = QLabel("Cleaning report")
        top.addWidget(self.title)
        top.addSpacing(16)
        top.addWidget(QLabel("Data:"))
        self.cmb_source = QComboBox()
        for table, label in SOURCES:
            self.cmb_source.addItem(label, table)
        self.cmb_source.currentIndexChanged.connect(lambda _i: self.refresh())
        top.addWidget(self.cmb_source)
        top.addSpacing(12)
        self.chk_copies = QCheckBox(COPIES_LABEL)
        self.chk_copies.setToolTip("Recording Scheme only: also check the rows marked as the NBN "
                                   "Atlas copy of an iRecord record (left out by default).")
        self.chk_copies.toggled.connect(lambda _c: self.refresh())
        top.addWidget(self.chk_copies)
        top.addStretch()
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(lambda: self.refresh(force=True))
        top.addWidget(self.btn_refresh)
        self.btn_export = QPushButton("Export…")
        self.btn_export.clicked.connect(self._on_export)
        top.addWidget(self.btn_export)
        root.addLayout(top)

        self.lbl_summary = QLabel("")
        self.lbl_summary.setWordWrap(True)
        root.addWidget(self.lbl_summary)

        tiles = QGridLayout()
        tiles.setSpacing(8)
        self.stack = QStackedWidget()
        for i, (key, label) in enumerate(PROBLEMS):
            tile = QPushButton(label)
            tile.setCheckable(True)
            tile.setCursor(Qt.CursorShape.PointingHandCursor)
            tile.clicked.connect(lambda _c=False, k=key: self.show_problem(k))
            self._tiles[key] = tile
            tiles.addWidget(tile, i // _TILES_PER_ROW, i % _TILES_PER_ROW)
            model = CleaningRowModel(parent=self)
            view = CleaningTableView(model)
            view.doubleClicked.connect(self._on_double_click)
            view.selectionModel().currentRowChanged.connect(lambda *_: self._update_buttons())
            self._models[key], self._views[key] = model, view
            self.stack.addWidget(view)
        root.addLayout(tiles)
        root.addWidget(self.stack, 1)

        bottom = QHBoxLayout()
        self.lbl_hint = QLabel("Double-click a record: opens it in iRecord (underlined iRecord ID), "
                               "or in Observatum if it has no iRecord ID.")
        bottom.addWidget(self.lbl_hint)
        bottom.addStretch()
        self.btn_show_again = QPushButton("Show again")
        self.btn_show_again.setToolTip("Un-hide this record in Observatum (it came back from "
                                       "iRecord, so it is in both).")
        self.btn_show_again.clicked.connect(self.show_selected_again)
        self.btn_irecord = QPushButton("Open in iRecord")
        self.btn_irecord.clicked.connect(self.open_selected_in_irecord)
        self.btn_observatum = QPushButton("Open in Observatum")
        self.btn_observatum.clicked.connect(self.open_selected_in_observatum)
        bottom.addWidget(self.btn_show_again)
        bottom.addWidget(self.btn_irecord)
        bottom.addWidget(self.btn_observatum)
        root.addLayout(bottom)
        self.show_problem(self._keys[0])
        self.apply_theme()

    # ------------------------------------------------------------------ data
    def source(self) -> str:
        return self.cmb_source.currentData()

    def include_copies(self) -> bool:
        return self.source() == "recording_scheme" and self.chk_copies.isChecked()

    def _paths(self):
        db = get_database()
        main = self._main_db or (db.main_db_path if db else None) or paths.OBSERVATUM_DB
        uksi = self._uksi_db or (db.uksi_db_path if db else None) or paths.UKSI_DB
        return str(main), str(uksi)

    def refresh(self, force: bool = False):
        """Show the report for the chosen source (built once per choice, rebuilt on Refresh)."""
        key = (self.source(), self.include_copies())
        self.chk_copies.setEnabled(self.source() == "recording_scheme")
        if force or key not in self._reports:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                main, uksi = self._paths()
                self._reports[key] = build_report(main, uksi, key[0], include_copies=key[1])
            except Exception as e:
                print(f"[CleaningDashboard] report not built: {e}")
                self.lbl_summary.setText(f"The report could not be made: {e}")
                return
            finally:
                QApplication.restoreOverrideCursor()
        self._show(self._reports[key])

    def mark_stale(self):
        """Records changed elsewhere: rebuild on the next visit."""
        self._reports.clear()

    def report(self) -> Optional[CleaningReport]:
        return self._reports.get((self.source(), self.include_copies()))

    def _show(self, rep: CleaningReport):
        counts = rep.counts
        for key, label in PROBLEMS:
            self._models[key].set_rows(rep.rows.get(key, []))
            self._tiles[key].setText(f"{label}\n{counts[key]:,}")
            self._tiles[key].setVisible(rep.source == "observations" or key not in OBSERVATION_ONLY)
        if self.current_key() in OBSERVATION_ONLY and rep.source != "observations":
            self.show_problem(self._keys[0])
        text = (f"{rep.source_label}: {rep.records_with_problem:,} of {rep.total_records:,} records "
                f"checked have at least one problem. A record with several problems is listed "
                f"under each. Every record is listed, whatever your species-counting settings.")
        if rep.copies_note:
            text += " " + rep.copies_note
        if rep.source == "observations" and rep.hidden_records:
            text += (f" {rep.hidden_records:,} record(s) removed here but still in iRecord are "
                     f"hidden and not checked.")
        self.lbl_summary.setText(text)
        self._update_buttons()

    # ------------------------------------------------------------------ tiles
    def current_key(self) -> str:
        return self._keys[self.stack.currentIndex()]

    def show_problem(self, key: str):
        """Show one problem's list and mark its tile."""
        self.stack.setCurrentIndex(self._keys.index(key))
        for k, tile in self._tiles.items():
            tile.setChecked(k == key)
        self._update_buttons()

    def current_view(self) -> CleaningTableView:
        return self.stack.currentWidget()

    def current_row(self) -> Optional[CleaningRow]:
        view = self.current_view()
        return view.current_row() if view is not None else None

    def _update_buttons(self):
        row = self.current_row()
        has_link = bool(row is not None and irecord_url(row.irecord_id))
        self.btn_irecord.setEnabled(has_link)
        self.btn_irecord.setToolTip("" if has_link else (NO_ROW_TIP if row is None else NO_ID_TIP))
        self.btn_irecord.setCursor(Qt.CursorShape.PointingHandCursor if has_link
                                   else Qt.CursorShape.ArrowCursor)
        self.btn_observatum.setEnabled(row is not None)
        self.btn_observatum.setToolTip("" if row is not None else NO_ROW_TIP)
        returned = self.current_key() == "returned" and self.source() == "observations"
        self.btn_show_again.setVisible(returned)
        self.btn_show_again.setEnabled(returned and row is not None)

    # ------------------------------------------------------------------ actions
    def _on_double_click(self, index):
        row = index.data(Qt.ItemDataRole.UserRole)
        if row is None:
            return
        if irecord_url(row.irecord_id):
            self._open_irecord(row)
        else:
            self.open_in_observatum(row)

    def open_selected_in_irecord(self):
        row = self.current_row()
        if row is None:
            QMessageBox.information(self, "Open in iRecord", NO_ROW_TIP)
        elif not irecord_url(row.irecord_id):
            QMessageBox.information(self, "Open in iRecord", NO_ID_TIP)
        else:
            self._open_irecord(row)

    def _open_irecord(self, row: CleaningRow):
        self.open_url(QUrl(irecord_url(row.irecord_id)))

    def open_selected_in_observatum(self):
        row = self.current_row()
        if row is None:
            QMessageBox.information(self, "Open in Observatum", NO_ROW_TIP)
            return
        self.open_in_observatum(row)

    def show_selected_again(self):
        """Un-hide the selected "came back" record (clears hidden_at; the ID is forgotten)."""
        row = self.current_row()
        if row is None or self.source() != "observations":
            return
        from shared.hidden_records import show_again
        try:
            db = get_database()
            if db is not None and not self._main_db:
                with db.main_connection() as conn:
                    ok = show_again(conn, row.record_id)
            else:
                import sqlite3
                conn = sqlite3.connect(self._paths()[0])
                try:
                    ok = show_again(conn, row.record_id)
                finally:
                    conn.close()
        except Exception as e:
            QMessageBox.warning(self, "Show again", f"The record could not be shown again:\n{e}")
            return
        if not ok:
            QMessageBox.warning(self, "Show again", "The database has no hidden_at column yet.")
            return
        print(f"[CleaningDashboard] record {row.record_id} shown again")
        self.mark_stale()
        self.refresh()
        self.show_problem("returned")

    def detail_dialog(self, row: CleaningRow):
        """The existing record detail dialog for a row, view only (no Edit / Delete)."""
        main, _uksi = self._paths()
        from shared.db_open import connect_ro
        conn = connect_ro(main)
        try:
            import sqlite3
            conn.row_factory = sqlite3.Row
            found = conn.execute(f"SELECT * FROM {self.source()} WHERE id = ?",
                                 (row.record_id,)).fetchone()
        finally:
            conn.close()
        if found is None:
            return None
        record = dict(found)
        if self.source() == "recording_scheme":
            from ..dialogs import SchemeRecordDetailDialog
            record.update(species=record.get("species_name", ""), common=record.get("common_name", ""),
                          location=record.get("site_name", ""), gridRef=record.get("grid_ref", ""),
                          vc=record.get("vc_number", ""),
                          verification=record.get("verification_status", ""))
            dlg = SchemeRecordDetailDialog(record, parent=self)
        else:
            from ..dialogs import RecordDetailDialog
            dlg = RecordDetailDialog(record=record, record_type="observation", parent=self)
        for btn in dlg.findChildren(QPushButton):
            if btn.text().strip() in ("Edit", "Delete"):
                btn.hide()
        dlg.navigate_to_observations.connect(lambda sp: (dlg.close(), self.navigate_to_observations.emit(sp)))
        dlg.navigate_to_collection.connect(lambda sp: (dlg.close(), self.navigate_to_collection.emit(sp)))
        return dlg

    def open_in_observatum(self, row: CleaningRow):
        try:
            dlg = self.detail_dialog(row)
        except Exception as e:
            print(f"[CleaningDashboard] record {row.record_id} not opened: {e}")
            dlg = None
        if dlg is None:
            QMessageBox.information(self, "Open in Observatum", "That record could not be found.")
            return
        dlg.exec()

    def _on_export(self):
        rep = self.report()
        if rep is None:
            return
        stamp = _dt.date.today().strftime("%Y%m%d")
        kind = {"observations": "observation", "recording_scheme": "scheme",
                "contributed_observations": "contributed"}.get(rep.source, rep.source)
        base = f"cleaning_report_{kind}_{stamp}"
        try:
            if have_openpyxl():
                path, _ = QFileDialog.getSaveFileName(self, "Export cleaning report", base + ".xlsx",
                                                      "Excel workbook (*.xlsx)")
                if not path:
                    return
                if not path.lower().endswith(".xlsx"):
                    path += ".xlsx"
                export_xlsx(rep, path)
            else:
                folder = QFileDialog.getExistingDirectory(self, "Folder for the CSV files")
                if not folder:
                    return
                path = export_csv_folder(rep, f"{folder}/{base}")
        except Exception as e:
            QMessageBox.warning(self, "Export", f"The report could not be saved:\n{e}")
            return
        QMessageBox.information(self, "Export", f"Saved:\n{path}")

    # ------------------------------------------------------------------ theme
    def apply_theme(self):
        t = theme()
        self.setStyleSheet(f"CleaningDashboard {{ background-color: {t.get('background')}; }}")
        self.title.setStyleSheet(f"font-size: {t.font_size('xl')}; font-weight: 600; "
                                 f"color: {t.get('text_primary')};")
        self.lbl_summary.setStyleSheet(f"color: {t.get('text_secondary')};")
        self.lbl_hint.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 12px;")
        self.chk_copies.setStyleSheet(f"color: {t.get('text_secondary')};")
        self.btn_export.setStyleSheet(t.button_primary_style())
        self.btn_refresh.setStyleSheet(t.button_secondary_style())
        self.btn_show_again.setStyleSheet(t.button_secondary_style())
        for b in (self.btn_irecord, self.btn_observatum):
            b.setStyleSheet(t.button_tab_style("observation"))
        tile_css = (f"QPushButton {{ background-color: {t.get('surface')}; color: {t.get('text_primary')};"
                    f" border: 1px solid {t.get('border')}; border-radius: {t.get('radius_md')};"
                    f" padding: 6px 10px; text-align: left; }}"
                    f" QPushButton:hover {{ background-color: {t.get('hover')}; }}"
                    f" QPushButton:checked {{ background-color: {t.get('selected_bg')};"
                    f" border: 2px solid {link_colour()}; font-weight: 600; }}")
        for tile in self._tiles.values():
            tile.setStyleSheet(tile_css)
