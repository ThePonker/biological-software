"""
Field record chooser (11 Oct 2026).

Opened by the Field record box's "Pick..." in the Add / Edit Specimen dialog: lists the
observations this specimen could be, best first (shared/specimen_links.candidates): the same
species on the specimen's date, the same grid ref first, then the nearest. "Any date" widens
it to every record of the species; the search box narrows by site, grid ref, recorder, date,
project or id. Choosing one does not write anything -- the specimen dialog saves it.

Read-only: opens observatum.db and uksi.db with ?mode=ro.
"""

import sqlite3
from typing import Optional, Dict

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QCheckBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from src.utils.date_utils import format_date_display
from shared.specimen_links import candidates

from ...themes import theme
from ...core.config import ButtonColors

COLUMNS = ("Obs ID", "Date", "Site", "Grid ref", "Distance", "Recorder", "Qty",
           "Specimens linked", "Sex", "Match")


def _distance(m) -> str:
    if m is None:
        return ""
    if m < 1:
        return "same square"
    return f"{m / 1000:.1f} km" if m >= 1000 else f"{m:.0f} m"


def _match_words(r) -> str:
    if r["rule"]:
        return "same date and grid ref"
    bits = []
    if r["same_date"]:
        bits.append("same date")
    if r["same_ref"]:
        bits.append("same grid ref")
    if r["person"] is False:
        bits.append("recorder differs")
    return ", ".join(bits)


SEX_WORDS = {"yes": "agrees", "no": "differs", "maybe": "mixed", "": ""}


class FieldRecordPicker(QDialog):
    """Choose the observation a specimen is the same find as."""

    def __init__(self, spec: Dict, db_path: str, uksi_path: Optional[str] = None,
                 current_id=None, parent=None):
        super().__init__(parent)
        self._spec = spec
        self._db_path = str(db_path)
        self._uksi_path = str(uksi_path) if uksi_path else None
        self._current_id = current_id
        self._rows = []
        self._chosen = None
        self.setWindowTitle("Pick the field record")
        self.setModal(True)
        self.resize(1000, 520)
        self._build()
        self.reload()
        if not self._rows and not self.any_date.isChecked():
            self.any_date.setChecked(True)          # nothing that day: show every date
            self.note.setText("No field record of this species on the specimen's date; "
                              "showing every date.")

    # ── UI ─────────────────────────────────────────────────────────────
    def _build(self):
        t = theme()
        lay = QVBoxLayout(self)
        s = self._spec
        when = format_date_display(s.get("date_collected") or "", "user") or "no date"
        head = QLabel(f"<b><i>{s.get('species_name') or 'No species'}</i></b> — specimen "
                      f"{when}, {s.get('grid_ref') or 'no grid ref'}, "
                      f"{s.get('collector') or 'no collector'}"
                      + (f", {s.get('sex')}" if s.get("sex") else ""))
        head.setStyleSheet(f"color: {t.get('text_primary')}; font-size: 13px;")
        lay.addWidget(head)

        row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search site, grid ref, recorder, date, project or id")
        self.search.textChanged.connect(self.reload)
        row.addWidget(self.search, 1)
        self.any_date = QCheckBox("Any date (every record of this species)")
        self.any_date.toggled.connect(self.reload)
        row.addWidget(self.any_date)
        lay.addLayout(row)

        self.note = QLabel("")
        self.note.setWordWrap(True)
        self.note.setStyleSheet(f"color: {t.get('text_muted')}; font-size: 11px;")
        lay.addWidget(self.note)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._on_selection)
        self.table.cellDoubleClicked.connect(lambda *_: self._on_link())
        lay.addWidget(self.table, 1)

        self.status = QLabel("")
        self.status.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 11px;")
        lay.addWidget(self.status)

        btns = QHBoxLayout()
        btns.addStretch()
        self.link_btn = QPushButton("Link to this record")
        self.link_btn.setEnabled(False)
        self.link_btn.setStyleSheet(
            f"QPushButton {{ background-color: {ButtonColors.PRIMARY}; color: white; border: none;"
            f" border-radius: {t.get('radius_md')}; padding: 8px 18px; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {ButtonColors.PRIMARY_HOVER}; }}"
            f"QPushButton:disabled {{ background-color: {t.get('text_muted')}; }}")
        self.link_btn.clicked.connect(self._on_link)
        btns.addWidget(self.link_btn)
        cancel = QPushButton("Cancel")
        cancel.setStyleSheet(
            f"QPushButton {{ border: 1px solid {ButtonColors.SECONDARY}; color: "
            f"{ButtonColors.SECONDARY}; border-radius: {t.get('radius_md')}; padding: 8px 18px; }}"
            f"QPushButton:hover {{ background-color: {t.get('hover')}; }}")
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        lay.addLayout(btns)
        for b in (self.link_btn, cancel):      # Enter in the search box must not link
            b.setAutoDefault(False)
            b.setDefault(False)

    # ── data ───────────────────────────────────────────────────────────
    def reload(self, *_):
        conn = uksi = None
        try:
            conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
            if self._uksi_path:
                try:
                    uksi = sqlite3.connect(f"file:{self._uksi_path}?mode=ro", uri=True)
                except sqlite3.Error:
                    uksi = None
            self._rows = candidates(conn, self._spec, uksi, any_date=self.any_date.isChecked(),
                                    text=self.search.text())
        except sqlite3.Error as e:
            self._rows = []
            self.note.setText(f"Could not read the field records: {e}")
        finally:
            for c in (conn, uksi):
                if c is not None:
                    c.close()
        self._fill()

    def _fill(self):
        t = theme()
        warn = QColor(t.get("warning_text"))
        self.table.setRowCount(0)
        for r in self._rows:
            i = self.table.rowCount()
            self.table.insertRow(i)
            qty = r["quantity"]
            n = r["linked"]
            vals = (str(r["id"]), format_date_display(r["date"] or "", "user"),
                    r["site_name"] or "", r["grid_ref"] or "", _distance(r["distance_m"]),
                    r["recorder"] or "", "" if qty is None else str(qty),
                    f"{n} of {qty}" if qty is not None else str(n),
                    SEX_WORDS.get(r["sex_hint"], ""), _match_words(r))
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if c == 0:
                    it.setData(Qt.ItemDataRole.UserRole, r["id"])
                self.table.setItem(i, c, it)
            full = isinstance(qty, int) and n >= qty
            if full:
                self.table.item(i, 7).setForeground(warn)
                self.table.item(i, 7).setToolTip(
                    "Already as many specimens linked as the record's quantity")
            if r["sex_hint"] == "no":
                self.table.item(i, 8).setForeground(warn)
            if r["person"] is False:
                self.table.item(i, 5).setForeground(warn)
            if self._current_id is not None and r["id"] == int(self._current_id):
                for c in range(len(COLUMNS)):
                    f = self.table.item(i, c).font()
                    f.setBold(True)
                    self.table.item(i, c).setFont(f)
                self.table.item(i, 0).setToolTip("Linked now")
        n = len(self._rows)
        scope = "any date" if self.any_date.isChecked() else "the specimen's date"
        self.status.setText(f"{n:,} field record{'s' if n != 1 else ''} of this species, "
                            f"{scope}. Bold = linked now. Double-click or "
                            "'Link to this record' to choose.")
        if n:
            self.table.selectRow(0)
        self._on_selection()

    def _on_selection(self):
        self.link_btn.setEnabled(bool(self.table.selectedItems()))

    def _on_link(self):
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return
        self._chosen = self._rows[rows[0].row()]
        self.accept()

    def chosen(self) -> Optional[Dict]:
        """The observation chosen (a candidates() row), or None."""
        return self._chosen
