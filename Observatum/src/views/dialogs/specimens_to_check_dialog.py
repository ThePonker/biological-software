"""Insect Collection > Specimens to check… (14 Oct 2026).

A non-modal window listing the specimens that have no field record, in seven tabs, so Wil can
work through them by hand: link to a field record, say "checked: no field record", make a
Data Entry row, or correct the date of a whole visit. The rules come from
scripts/report_specimens_without_records.py and scripts/stage_records_from_specimens.py; the
data and the writes are in shared/specimens_to_check.py. Every write takes a backup first
(once per window) and is refused unless the database is observatum.db.
"""
from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QDialog, QHBoxLayout, QInputDialog, QLabel, QMessageBox,
    QPushButton, QTableWidget, QTabWidget, QVBoxLayout, QWidget,
)

from shared import irecord_links
from shared import specimen_records
from shared import specimens_to_check as stc
from ...themes import theme
import re

from ..components.natural_sort_proxy import NaturalItem
from ..components.sort_items import date_item

_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
from .visit_date_dialog import VisitDateDialog, describe_change

LINK_TABS = ("near", "reid", "missing")
MAKE_TABS = ("ready", "season", "near", "reid", "held")
PLAN_TABS = ("ready", "season")
REFUSED = "Changes can only be made in the live database (observatum.db), not in a copy."


class SpecimensToCheckDialog(QDialog):
    def __init__(self, db_path, uksi_path=None, parent=None):
        super().__init__(parent)
        self._db = str(db_path)
        self._uksi = str(uksi_path) if uksi_path else None
        self._data = None
        self._rows = {k: [] for k in stc.KEYS}
        self._backed_up = set()
        self.setWindowTitle("Specimens to check")
        self.setModal(False)
        self.resize(1100, 650)
        # replaceable in tests
        self.confirm = lambda text: QMessageBox.question(
            self, "Specimens to check", text) == QMessageBox.StandardButton.Yes
        self.info = lambda text: QMessageBox.information(self, "Specimens to check", text)
        self.choose = self._choose
        self.ask_date = self._ask_date
        self.pick_record = self._pick_record
        self.open_url = lambda url: QDesktopServices.openUrl(QUrl(url))
        self._build()
        self.refresh()

    # ── UI ─────────────────────────────────────────────────────────────
    def _build(self):
        v = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.tables, self.notes = {}, {}
        for key in stc.KEYS:
            page = QWidget()
            pv = QVBoxLayout(page)
            note = QLabel(stc.NOTES[key])
            note.setWordWrap(True)
            note.setStyleSheet(f"color: {theme().get('text_secondary')};")
            pv.addWidget(note)
            cols = stc.COLUMNS[key]
            t = QTableWidget(0, len(cols))
            t.setHorizontalHeaderLabels(list(cols))
            t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            t.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
            t.verticalHeader().setVisible(False)
            t.horizontalHeader().setStretchLastSection(True)
            t.setSortingEnabled(True)
            t.itemSelectionChanged.connect(self._buttons)
            pv.addWidget(t, 1)
            self.tables[key] = t
            self.tabs.addTab(page, stc.TITLES[key])
        self.tabs.currentChanged.connect(self._buttons)
        v.addWidget(self.tabs, 1)
        self.status = QLabel("")
        v.addWidget(self.status)
        row = QHBoxLayout()
        self.btn_link = self._button("Link to field record…", self.link_selected, True)
        self.btn_irecord = self._button("Open in iRecord", self.open_irecord)
        self.btn_make = self._button("Make record", self.make_record, True)
        self.btn_check = self._button("Checked: no field record", self.mark_checked)
        self.btn_date = self._button("Change date of whole visit…", self.change_visit_date)
        row.addWidget(self.btn_link)
        row.addWidget(self.btn_make)
        for b in (self.btn_irecord, self.btn_check, self.btn_date):
            row.addWidget(b)
        row.addStretch(1)
        self.btn_refresh = self._button("Refresh", self.refresh)
        close = QPushButton("Close")
        close.setStyleSheet(theme().button_cancel_style())
        close.clicked.connect(self.close)
        row.addWidget(self.btn_refresh)
        row.addWidget(close)
        v.addLayout(row)

    def _button(self, text, slot, primary=False):
        b = QPushButton(text)
        b.setStyleSheet(theme().button_primary_style() if primary else theme().button_secondary_style())
        b.clicked.connect(lambda *_: slot())
        b.setAutoDefault(False)
        return b

    # ── data ───────────────────────────────────────────────────────────
    def refresh(self):
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self._data = stc.load(self._db, self._uksi)
            self._rows = stc.tabs(self._data)
            self.status.setText("")
        except (sqlite3.Error, OSError) as e:
            self._data, self._rows = None, {k: [] for k in stc.KEYS}
            self.status.setText(f"Could not read the specimens: {e}")
        finally:
            QApplication.restoreOverrideCursor()
        for i, key in enumerate(stc.KEYS):
            self._fill(key)
            self.tabs.setTabText(i, f"{stc.TITLES[key]} ({len(self._rows[key])})")
        self._buttons()

    def _fill(self, key):
        t = self.tables[key]
        t.setSortingEnabled(False)
        t.setRowCount(len(self._rows[key]))
        for i, row in enumerate(self._rows[key]):
            for c, v in enumerate(row["cells"]):
                # dates shown dd/mm/yyyy as everywhere else, sorted as dates (14 Oct 2026)
                it = date_item(v) if isinstance(v, str) and _ISO.match(v) else \
                    NaturalItem("" if v is None else str(v))
                if c == 0:
                    it.setData(Qt.ItemDataRole.UserRole, i)
                t.setItem(i, c, it)
        t.setSortingEnabled(True)

    def key(self) -> str:
        return stc.KEYS[self.tabs.currentIndex()]

    def selected(self, key=None) -> list:
        """Row dicts selected in the current tab."""
        key = key or self.key()
        t = self.tables[key]
        sm = t.selectionModel()
        idx = sorted({m.row() for m in sm.selectedRows()}) if sm else []
        return [self._rows[key][t.item(r, 0).data(Qt.ItemDataRole.UserRole)] for r in idx]

    def selected_ids(self) -> list:
        return sorted({i for r in self.selected() for i in r["ids"]})

    def _buttons(self, *_):
        key, sel = self.key(), self.selected()
        ids = {i for r in sel for i in r["ids"]}
        self.btn_link.setEnabled(key in LINK_TABS and len(sel) == 1)
        self.btn_irecord.setEnabled(key in ("near", "reid") and len(sel) == 1
                                    and bool(sel[0].get("irecord")))
        self.btn_make.setEnabled(key in MAKE_TABS and bool(ids))
        self.btn_check.setEnabled(key in LINK_TABS and bool(ids) and bool(
            self._data and self._data["has_check"]))
        self.btn_date.setEnabled(bool(ids) and key != "onrow")

    # ── helpers ────────────────────────────────────────────────────────
    def _writable(self) -> bool:
        if not stc.is_live_db(self._db):
            self.info(REFUSED)
            return False
        return True

    def _backup(self, label) -> bool:
        if label in self._backed_up:
            return True
        from shared import backup_service
        if not backup_service.backup_main_only(label):
            self.info("The backup could not be made, so nothing was changed.")
            return False
        self._backed_up.add(label)
        return True

    def _choose(self, items):
        item, ok = QInputDialog.getItem(self, "Make record", "Make the record as:", items, 0, False)
        return item if ok else None

    def _ask_date(self, rows):
        dlg = VisitDateDialog(rows, self)
        return dlg.new_iso() if dlg.exec() else None

    def _pick_record(self, spec):
        from .field_record_picker import FieldRecordPicker
        dlg = FieldRecordPicker(spec, self._db, self._uksi, None, self)
        return dlg.chosen()["id"] if dlg.exec() and dlg.chosen() else None

    # ── actions ────────────────────────────────────────────────────────
    def link_selected(self):
        sel = self.selected()
        if len(sel) != 1 or not self._writable():
            return
        spec = stc.picker_spec(self._db, sel[0]["ids"][0])
        obs = self.pick_record(spec) if spec else None
        if obs is None or not self._backup("pre-specimen-link"):
            return
        n = stc.link(self._db, spec["id"], obs)
        self.refresh()
        if not n:
            self.info("That specimen already has a field record, so it was not changed.")

    def open_irecord(self):
        sel = self.selected()
        if len(sel) == 1:
            url = irecord_links.record_irecord_url({"irecord_id": sel[0].get("irecord")})
            if url:
                self.open_url(url)

    def make_record(self):
        key, sel = self.key(), self.selected()
        if not sel or not self._writable():
            return
        if key in PLAN_TABS:
            jobs = stc.jobs_for_items(r["item"] for r in sel)
        else:
            terms = self._data["g"]["rule"].terms
            choice = self.choose(["Personal"] + sorted(terms))
            if choice is None:
                return
            jobs = stc.jobs_for_choice(self._data["g"], self.selected_ids(), choice)
        if not jobs:
            return
        names = sorted({specimen_records.job_name(j["kind"], j["project"], j["year"]) for j in jobs})
        if not self.confirm(f"{len(jobs)} Data Entry row(s) will be made in: " + "; ".join(names)
                            + ".\n\nNothing is committed. Go ahead?"):
            return
        if not self._backup("pre-specimen-records"):
            return
        n = stc.make_records(self._db, jobs)
        self.refresh()
        self.info(f"Made {n} row(s) in Data Entry. Check and commit them there.")

    def mark_checked(self):
        ids = self.selected_ids()
        if not ids or not self._writable() or not self._backup("pre-specimen-check"):
            return
        stc.mark_checked(self._db, ids)
        self.refresh()

    def change_visit_date(self):
        ids = self.selected_ids()
        if not ids or not self._writable():
            return
        rows = stc.specimen_rows(self._db, ids)
        problem = stc.visit_problem(rows)
        if problem:
            self.info(problem + " Select the specimens of one visit.")
            return
        iso = self.ask_date(rows)
        if not iso or not self.confirm(describe_change(rows, iso) + "?"):
            return
        if not self._backup("pre-specimen-date"):
            return
        n = stc.change_date(self._db, ids, iso)
        if n < len(ids):
            self.info(f"{len(ids) - n} specimen(s) are on a Data Entry row and were left; "
                      "change the date on that row in Data Entry.")
        self.refresh()
