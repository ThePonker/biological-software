"""Stats/Reports > Cleaning Report (backlog B, claude/38 answers 12-14).

The records to tidy in iRecord, one tab per problem, for Observation or Recording Scheme
data (chosen at the top). The lists come from services/cleaning_report.py (no Qt there);
every matching record is shown, whatever the species-counting switches say.

Double-click a row (or "Open in iRecord") opens the record in iRecord when it holds an
iRecord ID; "Open in Observatum" shows the existing record detail, view only (cleaning
happens in iRecord). "Export" writes one .xlsx: a Summary sheet and a sheet per problem.
"""
from __future__ import annotations

import datetime as _dt
from typing import Dict, List, Optional

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QFileDialog, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QMessageBox, QPushButton, QTableView, QTabWidget, QVBoxLayout, QWidget,
)

import paths
from ...models.database import get_database
from ...services.cleaning_export import export_csv_folder, export_xlsx, have_openpyxl
from ...services.cleaning_report import (
    PROBLEMS, SOURCES, CleaningReport, CleaningRow, build_report, irecord_url,
)
from ...themes import theme

COLUMNS = ["Species", "Rank", "Date", "Grid ref", "Site", "Recorder", "Problem", "iRecord ID",
           "Source"]
_FIELDS = ["species", "rank", "date", "grid_ref", "site", "recorder", "detail", "irecord_id",
           "dataset"]
_TILES_PER_ROW = 6


class CleaningRowModel(QAbstractTableModel):
    """The rows of one problem; UserRole gives the CleaningRow."""

    def __init__(self, rows: Optional[List[CleaningRow]] = None, parent=None):
        super().__init__(parent)
        self._rows = rows or []

    def set_rows(self, rows: List[CleaningRow]):
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return COLUMNS[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        r = self._rows[index.row()]
        if role == Qt.ItemDataRole.UserRole:
            return r
        value = getattr(r, _FIELDS[index.column()])
        if role == Qt.ItemDataRole.DisplayRole:
            return "" if value is None else str(value)
        if role == Qt.ItemDataRole.EditRole:            # sort key: iRecord IDs as numbers
            return value if value is not None else (-1 if index.column() == 7 else "")
        return None


class CleaningDashboard(QWidget):
    """The cleaning report screen."""

    navigate_to_observations = Signal(str)
    navigate_to_collection = Signal(str)

    def __init__(self, parent=None, main_db=None, uksi_db=None):
        super().__init__(parent)
        self._main_db, self._uksi_db = main_db, uksi_db
        self._reports: Dict[str, CleaningReport] = {}
        self._models: Dict[str, CleaningRowModel] = {}
        self._views: Dict[str, QTableView] = {}
        self._tiles: Dict[str, QPushButton] = {}
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
        self.tabs = QTabWidget()
        for i, (key, label) in enumerate(PROBLEMS):
            tile = QPushButton(label)
            tile.setCursor(Qt.CursorShape.PointingHandCursor)
            tile.clicked.connect(lambda _c=False, n=i: self.tabs.setCurrentIndex(n))
            self._tiles[key] = tile
            tiles.addWidget(tile, i // _TILES_PER_ROW, i % _TILES_PER_ROW)

            model = CleaningRowModel(parent=self)
            proxy = QSortFilterProxyModel(self)
            proxy.setSourceModel(model)
            proxy.setSortRole(Qt.ItemDataRole.EditRole)
            view = QTableView()
            view.setModel(proxy)
            view.setSortingEnabled(True)
            view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
            view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            view.verticalHeader().setVisible(False)
            view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            view.horizontalHeader().setStretchLastSection(True)
            for col, w in enumerate((200, 110, 90, 140, 190, 150, 240, 90, 260)):
                view.setColumnWidth(col, w)
            view.doubleClicked.connect(self._on_double_click)
            self._models[key], self._views[key] = model, view
            self.tabs.addTab(view, label)
        root.addLayout(tiles)
        root.addWidget(self.tabs, 1)

        bottom = QHBoxLayout()
        self.lbl_hint = QLabel("Double-click a record: opens it in iRecord, or in Observatum "
                               "if it has no iRecord ID.")
        bottom.addWidget(self.lbl_hint)
        bottom.addStretch()
        self.btn_irecord = QPushButton("Open in iRecord")
        self.btn_irecord.clicked.connect(self.open_selected_in_irecord)
        self.btn_observatum = QPushButton("Open in Observatum")
        self.btn_observatum.clicked.connect(self.open_selected_in_observatum)
        bottom.addWidget(self.btn_irecord)
        bottom.addWidget(self.btn_observatum)
        root.addLayout(bottom)
        self.apply_theme()

    # ------------------------------------------------------------------ data
    def source(self) -> str:
        return self.cmb_source.currentData()

    def _paths(self):
        db = get_database()
        main = self._main_db or (db.main_db_path if db else None) or paths.OBSERVATUM_DB
        uksi = self._uksi_db or (db.uksi_db_path if db else None) or paths.UKSI_DB
        return str(main), str(uksi)

    def refresh(self, force: bool = False):
        """Show the report for the chosen source (built once, rebuilt on Refresh / stale)."""
        src = self.source()
        if force or src not in self._reports:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                main, uksi = self._paths()
                self._reports[src] = build_report(main, uksi, src)
            except Exception as e:
                print(f"[CleaningDashboard] report not built: {e}")
                self.lbl_summary.setText(f"The report could not be made: {e}")
                return
            finally:
                QApplication.restoreOverrideCursor()
        self._show(self._reports[src])

    def mark_stale(self):
        """Records changed elsewhere: rebuild on the next visit."""
        self._reports.clear()

    def report(self) -> Optional[CleaningReport]:
        return self._reports.get(self.source())

    def _show(self, rep: CleaningReport):
        counts = rep.counts
        for i, (key, label) in enumerate(PROBLEMS):
            self._models[key].set_rows(rep.rows.get(key, []))
            self.tabs.setTabText(i, f"{label} ({counts[key]:,})")
            self._tiles[key].setText(f"{label}\n{counts[key]:,}")
        self.lbl_summary.setText(
            f"{rep.source_label}: {rep.records_with_problem:,} of {rep.total_records:,} records "
            f"have at least one problem. A record with several problems is listed under each. "
            f"Every record is listed, whatever your species-counting settings.")

    # ------------------------------------------------------------------ actions
    def current_row(self) -> Optional[CleaningRow]:
        view = self.tabs.currentWidget()
        if view is None:
            return None
        idx = view.currentIndex()
        return idx.data(Qt.ItemDataRole.UserRole) if idx.isValid() else None

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
            QMessageBox.information(self, "Open in iRecord", "Select a record first.")
        elif not irecord_url(row.irecord_id):
            QMessageBox.information(self, "Open in iRecord",
                                    "This record has no iRecord ID. Use Open in Observatum.")
        else:
            self._open_irecord(row)

    def _open_irecord(self, row: CleaningRow):
        self.open_url(QUrl(irecord_url(row.irecord_id)))

    def open_selected_in_observatum(self):
        row = self.current_row()
        if row is None:
            QMessageBox.information(self, "Open in Observatum", "Select a record first.")
            return
        self.open_in_observatum(row)

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
        base = f"cleaning_report_{'observation' if rep.source == 'observations' else 'scheme'}_{stamp}"
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
        self.btn_export.setStyleSheet(t.button_primary_style())
        self.btn_refresh.setStyleSheet(t.button_secondary_style())
        for b in (self.btn_irecord, self.btn_observatum):
            b.setStyleSheet(t.button_tab_style("observation"))
        tile_css = (f"QPushButton {{ background-color: {t.get('surface')}; color: {t.get('text_primary')};"
                    f" border: 1px solid {t.get('border')}; border-radius: {t.get('radius_md')};"
                    f" padding: 6px 10px; text-align: left; }}"
                    f" QPushButton:hover {{ background-color: {t.get('hover')}; }}")
        for tile in self._tiles.values():
            tile.setStyleSheet(tile_css)
