"""
A species' records in one calendar month (all years).

Opened by clicking a month on the Species lookup phenology chart (Wil 10 Oct: the
chart showed a hand cursor but did nothing). It lists exactly the records the bar
counts: observations and recording-scheme records selected by the same species
clause as the chart (shared/species_filter.py via SpeciesDashboard._by_species),
so the dialog's total equals the bar's height. Double-click a row for the record's
detail, as in the Stats VC records dialog.
"""

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QHeaderView, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QHBoxLayout,
)

from ...themes import theme

MONTH_NAMES = ['', 'January', 'February', 'March', 'April', 'May', 'June', 'July',
               'August', 'September', 'October', 'November', 'December']

# (table, label shown in the Source column)
SOURCES = (("observations", "Observation"), ("recording_scheme", "Recording Scheme"))

COLUMNS = ["Date", "Source", "Site", "Grid Ref", "VC", "Recorder"]


def month_records(execute: Callable, by_species: Callable, species_name: str,
                  month: int) -> list:
    """Rows for `species_name` in calendar `month` from observations and
    recording_scheme. `execute(sql, params)` runs a query on observatum.db;
    `by_species(table, name)` returns (clause, params) -- the chart's own selection."""
    rows = []
    for table, label in SOURCES:
        clause, params = by_species(table, species_name)
        result = execute(f"""
            SELECT id, date, site_name, grid_ref, vc_number, recorder
            FROM {table}
            WHERE {clause} AND date IS NOT NULL
              AND CAST(strftime('%m', date) AS INTEGER) = ?
        """, tuple(params) + (month,))
        for r in result or []:
            rows.append({'table': table, 'source': label, 'id': r[0], 'date': r[1] or '',
                         'site': r[2] or '', 'grid_ref': r[3] or '',
                         'vc': '' if r[4] is None else str(r[4]), 'recorder': r[5] or ''})
    rows.sort(key=lambda d: d['date'], reverse=True)
    return rows


def _fmt_date(d: str) -> str:
    if d and len(d) >= 10:
        return f"{d[8:10]}/{d[5:7]}/{d[:4]}"
    return d or ''


class MonthRecordsDialog(QDialog):
    """Table of a species' records in one month; double-click opens the record."""

    def __init__(self, species_name: str, month: int, rows: list, db=None, parent=None):
        super().__init__(parent)
        self._species = species_name
        self._db = db
        self.rows = rows
        t = theme()
        month_name = MONTH_NAMES[month] if 1 <= month <= 12 else str(month)
        self.setWindowTitle(f"Records for {species_name} in {month_name}")
        self.setMinimumSize(900, 500)
        self.setStyleSheet(f"background-color: {t.get('surface')};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        n = len(rows)
        header = QLabel(f"<b><i>{species_name}</i></b><br><span style='color: "
                        f"{t.get('text_secondary')}'>{month_name}, all years "
                        f"({n:,} record{'s' if n != 1 else ''})</span>")
        header.setStyleSheet(f"font-size: 16px; color: {t.get('text_primary')};")
        layout.addWidget(header)

        self.table = QTableWidget(n, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {t.get('surface')};
                alternate-background-color: {t.get('surface_alt')};
                border: 1px solid {t.get('border')};
                border-radius: 4px;
                color: {t.get('text_primary')};
            }}
            QHeaderView::section {{
                background-color: {t.get('surface')};
                color: {t.get('text_secondary')};
                padding: 8px;
                border: none;
                border-bottom: 1px solid {t.get('border')};
                font-weight: 600;
            }}
        """)
        for i, r in enumerate(rows):
            date_item = QTableWidgetItem(_fmt_date(r['date']))
            # Sorting moves rows, so each row carries its own (table, id)
            date_item.setData(Qt.ItemDataRole.UserRole, (r['table'], r['id']))
            date_item.setData(Qt.ItemDataRole.UserRole + 1, r['date'])
            self.table.setItem(i, 0, date_item)
            for c, key in enumerate(('source', 'site', 'grid_ref', 'vc', 'recorder'), 1):
                self.table.setItem(i, c, QTableWidgetItem(r[key]))
        self.table.setSortingEnabled(True)
        self.table.doubleClicked.connect(self._open_record)
        layout.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        hint = QLabel("Double-click a row to view the full record")
        hint.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 12px;")
        bottom.addWidget(hint)
        bottom.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {t.get('text_secondary')};
                           border: 1px solid {t.get('text_secondary')}; border-radius: 4px;
                           padding: 6px 16px; }}
        """)
        close_btn.clicked.connect(self.accept)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

    def record_key_at(self, row: int):
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def _open_record(self, index):
        key = self.record_key_at(index.row()) if index.row() >= 0 else None
        if not key or self._db is None:
            return
        table, record_id = key
        try:
            result = self._db.execute_main(f"SELECT * FROM {table} WHERE id = ?", (record_id,))
            if not result:
                return
            record = dict(result[0])
            if table == "recording_scheme":
                from ..dialogs import SchemeRecordDetailDialog
                record['species'] = record.get('species_name', '')
                record['common'] = record.get('common_name', '')
                record['location'] = record.get('site_name', '')
                record['gridRef'] = record.get('grid_ref', '')
                record['vc'] = record.get('vc_number', '')
                record['verification'] = record.get('verification_status', '')
                dlg = SchemeRecordDetailDialog(record, parent=self)
                from ..scheme.scheme_record_actions import wire_scheme_detail
                wire_scheme_detail(dlg, self, lambda: None)
            else:
                from ..dialogs import RecordDetailDialog
                dlg = RecordDetailDialog(record=record, record_type='observation', parent=self)
            dlg.exec()
        except Exception as e:
            print(f"[MonthRecordsDialog] Error opening record: {e}")
