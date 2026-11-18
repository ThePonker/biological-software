"""Visits & weather (Round A, Nov 2026): one row per survey date of the open job, with the
weather typed as short text. Saved to visit_weather (shared/visit_weather.py), keyed by the
job's project + client, for the report tools."""
from __future__ import annotations

import re
import sqlite3
from typing import Dict, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
    QStyledItemDelegate, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from DataEntry import theme
from shared import visit_weather as vw
from shared.text_sizes import font_css

HEAD = ["Date", "Temperature", "Wind", "Cloud", "Notes"]
HINTS = {1: "e.g. 16–19 °C", 2: "e.g. Beaufort 2–3", 3: "e.g. 3–6 oktas", 4: ""}
MISSING_MSG = ("Weather can't be saved yet: run py -3.14 scripts\\add_report_tables.py --apply "
               "(close the apps first).")
AWAY_MSG = "Away machine (read-only copy): weather can't be saved here."


def job_project_client(job: Dict):
    """Project and client as commit writes them (no trimming): the keys the weather is saved
    under, the same as Examen's preview and the committed observations carry. The job's name
    stands in when it has no project, as in the preview."""
    return (job.get("project") or job.get("name") or ""), (job.get("client") or "")


_RANGE = re.compile(r"(?<=\d)\s*[-\u2013]\s*(?=\d)")


def with_unit(column: int, text: str) -> str:
    """The cell as typed, with its unit added: 30 - 32 -> "30–32 °C", 1 - 2 -> "Beaufort 1–2",
    1 - 3 -> "1–3 oktas". Number ranges take an en dash. A unit already there is not added again;
    a blank cell stays blank; the Notes column is left as typed."""
    s = (text or "").strip()
    if not s or column not in (1, 2, 3):
        return s
    s = _RANGE.sub("\u2013", s)
    if column == 1:
        s = re.sub(r"\s*°?\s*C$", "", s, flags=re.I) if re.search(r"\d\s*°?\s*C$", s, re.I) else s
        return f"{s} °C"
    if column == 2:
        s = re.sub(r"^beaufort\s*", "", s, flags=re.I)
        return f"Beaufort {s}"
    s = re.sub(r"\s*oktas?$", "", s, flags=re.I)
    return f"{s} okta" if s in ("0", "1") else f"{s} oktas"


def _dmy(iso: str) -> str:
    p = iso.split("-")
    return f"{p[2]}/{p[1]}/{p[0]}" if len(p) == 3 else iso


class VisitWeatherDialog(QDialog):
    def __init__(self, conn, job: Dict, parent=None):
        super().__init__(parent)
        self._job = job
        self.project, self.client = job_project_client(job)
        self.setWindowTitle("Visits & weather")
        self.resize(900, 480)
        self.setStyleSheet(theme.input_qss())
        v = QVBoxLayout(self)
        head = QLabel(f"<b>Project:</b> {self.project} &nbsp;&middot;&nbsp; "
                      f"<b>Client:</b> {self.client or '(none)'}")
        head.setWordWrap(True)
        head.setStyleSheet(f"color: {theme.INK}; font-size: {font_css('body')};")
        v.addWidget(head)

        try:
            staged = [r[0] for r in conn.execute(
                "SELECT DISTINCT date FROM entry_staging WHERE job_id=? AND date IS NOT NULL "
                "AND date<>''", (job["id"],))]
        except sqlite3.Error:
            staged = []
        saved = vw.weather_for(self.project, self.client)
        self.dates: List[str] = sorted(set(staged) | set(saved))

        self.table = QTableWidget(len(self.dates), len(HEAD))
        self.table.setHorizontalHeaderLabels(HEAD)
        self.table.verticalHeader().setVisible(False)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        h.setStretchLastSection(True)
        self.table.setColumnWidth(0, 110)
        for c in (1, 2, 3):
            self.table.setColumnWidth(c, 170)
        for r, iso in enumerate(self.dates):
            it = QTableWidgetItem(_dmy(iso))
            it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, 0, it)
            w = saved.get(iso, {})
            for c, f in enumerate(vw.FIELDS, start=1):
                self.table.setItem(r, c, QTableWidgetItem(w.get(f, "")))
        self.table.setItemDelegate(_HintDelegate(self.table))
        self.table.itemChanged.connect(self._add_unit)
        v.addWidget(self.table, 1)

        self.note = QLabel("")
        self.note.setWordWrap(True)
        self.note.setStyleSheet(f"color: {theme.MUTED}; font-size: {font_css('small')};")
        v.addWidget(self.note)

        btns = QHBoxLayout()
        btns.addStretch(1)
        self.save_btn = QPushButton("Save")
        self.save_btn.setStyleSheet(theme.button_primary_qss())
        self.save_btn.clicked.connect(self._save)
        btns.addWidget(self.save_btn)
        cancel = QPushButton("Cancel")
        cancel.setStyleSheet(theme.button_secondary_qss())
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        v.addLayout(btns)

        from shared.away_mode import away_active
        if away_active():
            self.note.setText(AWAY_MSG)
            self.save_btn.setEnabled(False)
        elif not vw.table_ready():
            self.note.setText(MISSING_MSG)
            self.save_btn.setEnabled(False)
        elif not self.dates:
            self.note.setText("No survey dates yet: this job has no dated rows.")

    def _add_unit(self, item):
        """Add the unit as soon as a cell is left (tab or Enter)."""
        new = with_unit(item.column(), item.text())
        if new != item.text():
            self.table.blockSignals(True)
            item.setText(new)
            self.table.blockSignals(False)

    def rows(self) -> List[Dict]:
        out = []
        for r, iso in enumerate(self.dates):
            row = {"date": iso}
            for c, f in enumerate(vw.FIELDS, start=1):
                it = self.table.item(r, c)
                row[f] = it.text() if it else ""
            out.append(row)
        return out

    def _save(self):
        try:
            vw.save_weather(self.project, self.client, self.rows())
        except Exception as e:
            QMessageBox.warning(self, "Visits & weather", f"Not saved: {e}")
            return
        self.accept()


class _HintDelegate(QStyledItemDelegate):
    """Shows the placeholder hint in the cell editor."""
    def createEditor(self, parent, option, index):
        ed = QStyledItemDelegate.createEditor(self, parent, option, index)
        if isinstance(ed, QLineEdit):
            ed.setPlaceholderText(HINTS.get(index.column(), ""))
        return ed
