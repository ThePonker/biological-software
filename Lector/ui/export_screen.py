"""Exports: a Word dossier with an Excel index, PDF, or a plain text bundle (mock-up screen 5)."""
import os
from html import escape
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QCheckBox, QComboBox, QGridLayout,
                               QHBoxLayout, QHeaderView, QLabel, QListWidget, QListWidgetItem,
                               QRadioButton, QTableWidget, QTableWidgetItem)

from Lector.ui import style as S
from Lector.ui.common import Screen, left_headers
from Lector.ui.review_panes import runs_html

STATUSES = (("relevant", True), ("record_extracted", True), ("unreviewed", True),
            ("not_relevant", False))
INSTALL = "py -3.14 -m pip install {}"


def open_path(path):
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


class ExportScreen(Screen):
    def __init__(self, win):
        super().__init__(win, "Export a literature dossier",
                         "A Word document for reading and citing, with an Excel index "
                         "alongside for sorting and checking.")
        self.search_id = None
        cols = QHBoxLayout()
        cols.setSpacing(12)
        cols.addWidget(self._options_card(), 3)
        cols.addWidget(self._preview_card(), 2)
        self.body.addLayout(cols)
        prev = S.Card("Previous exports")
        self.exports = QListWidget()
        self.exports.setMinimumHeight(90)
        self.exports.setMaximumHeight(160)
        self.exports.itemDoubleClicked.connect(
            lambda it: open_path(it.data(Qt.ItemDataRole.UserRole)))
        prev.body.addWidget(self.exports)
        row = QHBoxLayout()
        row.addWidget(S.label("Double-click a file to open it.", "small"))
        row.addStretch(1)
        row.addWidget(S.button("Open folder", "outline", "Open the exports folder",
                               lambda: open_path(self.svc.export_dir)))
        prev.body.addLayout(row)
        self.body.addWidget(prev)
        self.body.addStretch(1)

    # --- layout -------------------------------------------------------------
    def _options_card(self):
        card = S.Card()
        card.body.addWidget(S.label("Search", "small"))
        self.search_box = QComboBox()
        self.search_box.activated.connect(lambda _i: self.open(
            search_id=self.search_box.currentData()))
        card.body.addWidget(self.search_box)
        card.body.addWidget(S.label("Include pages marked as", "small"))
        row = QHBoxLayout()
        self.status_checks = {}
        for st, on in STATUSES:
            cb = QCheckBox(S.STATUS_LABELS[st])
            cb.setChecked(on)
            cb.toggled.connect(self.update_preview)
            self.status_checks[st] = cb
            row.addWidget(cb)
        row.addStretch(1)
        card.body.addLayout(row)
        card.body.addWidget(S.label("Order entries", "small"))
        row = QHBoxLayout()
        self.by_year, self.by_journal = QRadioButton("By year"), QRadioButton("By journal, then year")
        self.by_year.setChecked(True)
        group = QButtonGroup(self)
        for b in (self.by_year, self.by_journal):
            group.addButton(b)
            b.toggled.connect(self.update_preview)
            row.addWidget(b)
        row.addStretch(1)
        card.body.addLayout(row)
        card.body.addWidget(S.label("Write", "small"))
        grid = QGridLayout()
        grid.setVerticalSpacing(4)
        self.fmt_checks, self.fmt_notes = {}, {}
        for r, (fmt, text, on) in enumerate((
                ("docx", "Word dossier (.docx)", True),
                ("xlsx", "Excel index (.xlsx), made with the dossier", True),
                ("pdf", "PDF copy of the dossier", False),
                ("txt", "Plain text bundle and index (.txt, .csv)", False))):
            cb = QCheckBox(text)
            cb.setChecked(on)
            note = S.label("", "warn", wrap=True)
            grid.addWidget(cb, r, 0)
            grid.addWidget(note, r, 1)
            self.fmt_checks[fmt], self.fmt_notes[fmt] = cb, note
        grid.setColumnStretch(1, 1)
        card.body.addLayout(grid)
        card.body.addWidget(S.label("Options", "small"))
        self.appendix = QCheckBox("Put index pages and pages without the name in appendices")
        self.appendix.setChecked(True)
        self.notes = QCheckBox("Include my notes")
        self.notes.setChecked(True)
        card.body.addWidget(self.appendix)
        card.body.addWidget(self.notes)
        card.body.addWidget(S.label("Duplicate scans are always merged into one entry that lists "
                                    "the other copies, and pages that may still be in copyright "
                                    "(after 1930) are flagged.", "small", wrap=True))
        self.save_to = S.label("", "small", wrap=True)
        card.body.addWidget(self.save_to)
        row = QHBoxLayout()
        self.create_btn = S.button("Create dossier", "primary", "Write the files", self.export)
        row.addWidget(self.create_btn)
        row.addWidget(S.button("Cancel", "cancel", "Back to Saved searches",
                               lambda: self.win.go("searches")))
        row.addStretch(1)
        card.body.addLayout(row)
        self.result = QLabel("")
        self.result.setWordWrap(True)
        self.result.setTextFormat(Qt.TextFormat.RichText)
        self.result.linkActivated.connect(open_path)
        card.body.addWidget(self.result)
        return card

    def _preview_card(self):
        card = S.Card()
        card.body.addWidget(S.label("Preview", "caps"))
        self.pv_title = S.label("", "h2", wrap=True)
        self.pv_sub = S.label("", "small", wrap=True)
        card.body.addWidget(self.pv_title)
        card.body.addWidget(self.pv_sub)
        self.pv_table = QTableWidget(0, 3)
        self.pv_table.setHorizontalHeaderLabels(["YEAR", "SOURCE", "STATUS"])
        self.pv_table.verticalHeader().hide()
        self.pv_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.pv_table.setShowGrid(False)
        hh = self.pv_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.pv_table.setMinimumHeight(180)
        left_headers(self.pv_table)
        card.body.addWidget(self.pv_table)
        self.pv_entry = QLabel("")
        self.pv_entry.setWordWrap(True)
        self.pv_entry.setTextFormat(Qt.TextFormat.RichText)
        card.body.addWidget(self.pv_entry)
        card.body.addStretch(1)
        return card

    # --- data ---------------------------------------------------------------
    def open(self, search_id=None, **_kw):
        searches = [s for s in self.win.call(self.svc.list_searches) or [] if s["pages_held"]]
        self.search_box.clear()
        for s in searches:
            self.search_box.addItem(s["name"], s["search_id"])
        if search_id is None or self.search_box.findData(search_id) < 0:
            search_id = self.search_id if self.search_box.findData(self.search_id) >= 0 else (
                searches[0]["search_id"] if searches else None)
        self.search_id = search_id
        self.search_box.setCurrentIndex(max(self.search_box.findData(search_id), 0))
        self._check_packages()
        self.result.setText("")
        self.update_preview()
        self._fill_exports()

    def _check_packages(self):
        info = self.svc.settings_info()
        self.save_to.setText(f"Saved to {info['export_dir']}")
        need = {"docx": None if info["docx_available"] else "python-docx",
                "xlsx": None if info["xlsx_available"] else "openpyxl",
                "pdf": None, "txt": None}
        if not info["docx_available"]:
            need["xlsx"] = need["xlsx"] or "python-docx"
            need["pdf"] = "python-docx"
        for fmt, pkg in need.items():
            cb, note = self.fmt_checks[fmt], self.fmt_notes[fmt]
            cb.setEnabled(pkg is None)
            if pkg:
                cb.setChecked(False)
                note.setText(f"Needs {pkg}: install once with  {INSTALL.format(pkg)}")
            else:
                note.setText("")
        if info["docx_available"] and not info["pdf_method"]:
            self.fmt_notes["pdf"].setText("Needs Microsoft Word (with docx2pdf) or LibreOffice")
        if not info["docx_available"] and not self.fmt_checks["txt"].isChecked():
            self.fmt_checks["txt"].setChecked(True)

    def _statuses(self):
        return [st for st, cb in self.status_checks.items() if cb.isChecked()]

    def _order(self):
        return "journal" if self.by_journal.isChecked() else "year"

    def update_preview(self, *_a):
        if self.search_id is None:
            self.pv_title.setText("No pages to export yet")
            self.pv_sub.setText("Run a saved search first.")
            self.pv_table.setRowCount(0)
            self.pv_entry.setText("")
            self.create_btn.setEnabled(False)
            return
        self.create_btn.setEnabled(True)
        s = self.win.call(self.svc.get_search, self.search_id) or {}
        keep = set(self._statuses())
        items = [i for i in self.win.call(self.svc.review_queue, self.search_id,
                                          order=self._order()) or []
                 if i["review_status"] in keep]
        self.pv_title.setText(s.get("target_name") or s.get("name") or "")
        self.pv_sub.setText(f"Literature from the Biodiversity Heritage Library · "
                            f"{len(items):,} entries")
        shown = items[:12]
        self.pv_table.setRowCount(len(shown))
        for r, i in enumerate(shown):
            for col, text in enumerate((str(i["year"] or ""), i["source"] or i["citation"],
                                        S.STATUS_LABELS[i["review_status"]])):
                self.pv_table.setItem(r, col, QTableWidgetItem(text))
        first = next((i for i in items if i["excerpt_runs"]), None)
        if first:
            note = f"<br><i>Note: {escape(first['notes'])}</i>" if first["notes"] else ""
            self.pv_entry.setText(f"<b>{escape(str(first['year'] or ''))} · "
                                  f"{escape(first['source'] or '')}</b><br>… "
                                  f"{runs_html(first['excerpt_runs'][0])} …{note}")
        else:
            self.pv_entry.setText("")

    def _fill_exports(self):
        self.exports.clear()
        for e in self.win.call(self.svc.list_exports, self.search_id) or []:
            path = Path(e["path"])
            it = QListWidgetItem(f"{S.fmt_when(e['created'])}   {path.name} · {e['kind']}"
                                 f" · {e['pages'] or 0:,} pages"
                                 + ("" if path.exists() else "   (file moved or deleted)"))
            it.setData(Qt.ItemDataRole.UserRole, str(path))
            self.exports.addItem(it)
        if not self.exports.count():
            self.exports.addItem("Nothing exported from this search yet.")

    # --- export -------------------------------------------------------------
    def export(self):
        formats = tuple(f for f, cb in self.fmt_checks.items() if cb.isChecked() and cb.isEnabled())
        if self.search_id is None or not formats:
            self.win.say("Choose what to write first.")
            return False
        statuses = tuple(self._statuses())
        if not statuses:
            self.win.say("Tick at least one kind of page to include.")
            return False
        sid, opts = self.search_id, dict(formats=formats, order=self._order(),
                                         include_appendices=self.appendix.isChecked(),
                                         include_statuses=statuses,
                                         include_notes=self.notes.isChecked())

        def work(progress=None, cancel=None):
            return self.svc.export(sid, **opts)
        self.result.setText("Writing…")
        return self.win.run_task("Exporting", work, on_done=self._exported)

    def _exported(self, out):
        lines = [escape(m) for m in out["messages"]]
        for fmt, path in out["files"].items():
            lines.append(f"{fmt.upper()}: <a href='{escape(path)}'>{escape(os.path.basename(path))}</a>")
        if not out["files"] and not lines:
            lines.append("Nothing was written.")
        self.result.setText("<br>".join(lines))
        self._fill_exports()
