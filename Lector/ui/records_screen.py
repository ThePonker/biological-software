"""Extracted records: what you have read off BHL pages (Round 15b).

Records are made in the reading list ("Record from this page…"). Here they are listed, filtered
by search, species and year, edited, removed (a real delete of that one row, after a backup of
lector.db) and exported as CSV for Observatum's contributed-records import. Lector never
writes to observatum.db.
"""
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFileDialog,
                               QHeaderView, QTableWidget, QTableWidgetItem, QVBoxLayout)

from Lector import records
from Lector.ui import style as S
from Lector.ui.common import Screen, left_headers
from Lector.ui.record_dialog import RecordDialog

COLUMNS = ("Species", "Date", "Place", "Grid ref", "Recorder", "Source", "Search")
ROLE = Qt.ItemDataRole.UserRole


def date_text(r):
    """The date as printed, else the parsed parts (14/06/1873, 06/1873, 1873)."""
    if r.get("date_printed"):
        return r["date_printed"]
    parts = [f"{r[k]:02d}" for k in ("day", "month") if r.get(k)]
    return "/".join(parts + ([str(r["year"])] if r.get("year") else []))


class RecordsScreen(Screen):
    def __init__(self, win):
        super().__init__(win, "Extracted records",
                         "What you have read off BHL pages. Add one with “Record from this "
                         "page…” in the Reading list.")
        self.rows, self.dialog = [], None
        self.export_path = None
        self.search_box, self.species_box, self.year_box = QComboBox(), QComboBox(), QComboBox()
        for text, box in (("Search", self.search_box), ("Species", self.species_box),
                          ("Year", self.year_box)):
            box.setObjectName("rec_filter_" + text.lower())
            box.setMinimumWidth(150)
            box.activated.connect(lambda _i: self.reload())
            col = QVBoxLayout()
            col.setSpacing(2)
            col.addWidget(S.label(text, "small"))
            col.addWidget(box)
            self.actions.addLayout(col)
        self.edit_btn = S.button("Edit…", "outline", "Change the chosen record", self.edit)
        self.remove_btn = S.button("Remove…", "delete", "Delete the chosen record (lector.db "
                                   "is backed up first)", self.remove)
        self.export_btn = S.button("Export CSV…", "primary", "Write the records shown as a CSV "
                                   "file for Observatum's contributed-records import",
                                   self.export_csv)
        for b in (self.edit_btn, self.remove_btn, self.export_btn):
            self.actions.addWidget(b)
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setObjectName("recordsTable")
        self.table.setHorizontalHeaderLabels([c.upper() for c in COLUMNS])
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setShowGrid(False)
        self.table.setWordWrap(True)
        hh = self.table.horizontalHeader()
        for i in range(len(COLUMNS)):
            hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch if i in (0, 2, 5)
                                    else QHeaderView.ResizeMode.ResizeToContents)
        left_headers(self.table)
        self.table.setMinimumHeight(260)
        self.table.itemSelectionChanged.connect(self._buttons)
        self.table.itemDoubleClicked.connect(lambda _i: self.edit())
        self.body.addWidget(self.table, 1)
        self.empty = S.label("", "muted", wrap=True)
        self.body.addWidget(self.empty)
        self.note = S.label("", "small", wrap=True)
        self.body.addWidget(self.note)

    # --- data -----------------------------------------------------------------------------
    def open(self, **_kw):
        self._fill_filters()
        self.reload()

    def _fill_filters(self):
        ch = self.win.call(self.svc.record_filter_choices) or {"searches": [], "species": [],
                                                                "years": []}
        for box, first, items in (
                (self.search_box, "All searches", [(s["name"], s["search_id"])
                                                   for s in ch["searches"]]),
                (self.species_box, "All species", [(x, x) for x in ch["species"]]),
                (self.year_box, "All years", [(str(y), y) for y in ch["years"]])):
            keep = box.currentData()
            box.clear()
            box.addItem(first, None)
            for text, data in items:
                box.addItem(text, data)
            box.setCurrentIndex(max(box.findData(keep), 0))

    def reload(self, select=None):
        self.rows = self.win.call(self.svc.list_records, self.search_box.currentData(),
                                  self.species_box.currentData(),
                                  self.year_box.currentData()) or []
        self.table.setRowCount(len(self.rows))
        for r, rec in enumerate(self.rows):
            cells = (rec["species"], date_text(rec), rec["place"] or "", rec["grid_ref"] or "",
                     rec["recorder"] or "", records.short_citation(rec),
                     rec["search_name"] or "(deleted search)")
            for c, text in enumerate(cells):
                it = QTableWidgetItem(text)
                it.setData(ROLE, rec["record_id"])
                it.setToolTip(rec["citation"] or "")
                self.table.setItem(r, c, it)
            if rec["record_id"] == select:
                self.table.selectRow(r)
        self.table.resizeRowsToContents()
        self.empty.setText("" if self.rows else
                           "No records yet. Open a page in the Reading list and press "
                           "“Record from this page…”." if not self._filtered() else
                           "No record matches these filters.")
        self.subtitle.setText(f"{len(self.rows):,} record{'s' if len(self.rows) != 1 else ''}"
                              " shown")
        self._buttons()

    def _filtered(self):
        return any(b.currentData() is not None
                   for b in (self.search_box, self.species_box, self.year_box))

    def current(self):
        rows = {i.row() for i in self.table.selectedItems()}
        return self.rows[rows.pop()] if len(rows) == 1 else None

    def _buttons(self):
        has = self.current() is not None
        self.edit_btn.setEnabled(has)
        self.remove_btn.setEnabled(has)
        self.export_btn.setEnabled(bool(self.rows))

    # --- actions ----------------------------------------------------------------------------
    def edit(self):
        rec = self.current()
        if rec is None:
            return None
        dlg = RecordDialog(self.svc, record_id=rec["record_id"], parent=self.win)
        dlg.accepted.connect(lambda: (self._fill_filters(), self.reload(select=rec["record_id"])))
        self.dialog = dlg
        if not self.win.quiet:
            dlg.exec()
        return dlg

    def remove(self):
        """Remove…: asks, backs lector.db up, then deletes that one record. The page and its
        other records are untouched."""
        rec = self.current()
        if rec is None:
            return None
        text = (f"Remove this record of {rec['species']} ({date_text(rec) or 'no date'}, "
                f"{rec['place'] or 'no place'})?\n\nOnly this record is deleted. lector.db is "
                "backed up first (data\\_backups\\lector_pre_remove_record_<time>.db).")
        if not self.win.choose(text, "Remove it", "Keep it", "Remove record", danger=True):
            return None
        done = self.win.call(self.svc.remove_record, rec["record_id"])
        if done is not None:
            self._fill_filters()
            self.reload()
            self.note.setText(f"Record removed. Backup copy: {done['backup']}")
        return done

    def export_csv(self):
        """Export CSV…: the records shown (the filters apply). The file is for
        scripts\\import_contributed.py, which reads .xlsx: open it in Excel and save as a
        workbook first."""
        if not self.rows:
            return None
        path = self.export_path or str(
            self.svc.export_dir / f"lector_records_{datetime.now():%Y%m%d_%H%M%S}.csv")
        if not self.win.quiet and self.export_path is None:
            path, _ = QFileDialog.getSaveFileName(self, "Export records", path,
                                                  "CSV files (*.csv)")
            if not path:
                return None
        done = self.win.call(self.svc.export_records_csv, Path(path),
                             self.search_box.currentData(), self.species_box.currentData(),
                             self.year_box.currentData())
        if done is not None:
            self.note.setText(f"Wrote {done['rows']:,} record{'s' if done['rows'] != 1 else ''}"
                              f" to {done['path']}. To import them into Observatum, open the "
                              "file in Excel, save it as a workbook (.xlsx) and run "
                              "scripts\\import_contributed.py on it (dry run first).")
        return done
