"""A saved search: its settings, every run, and what changed between runs (mock-up screen 3)."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QGridLayout, QHBoxLayout,
                               QHeaderView, QListWidget, QListWidgetItem, QTableWidget,
                               QTableWidgetItem, QTabWidget)

from Lector.ui import style as S
from Lector.ui.common import Screen, WrapDelegate, fit_widget_column, left_headers

TABS = (("new", "New"), ("withdrawn", "No longer matched"), ("unchanged", "Unchanged"))


def _run_text(r):
    """A run in the list: numbered within its search (run["label"]: 'Run 2' / 'Count')."""
    when = S.fmt_when(r["started"])
    if r["mode"] == "count":
        return (f"Count only · {when}\n{r['found'] or 0:,} found · no pages downloaded"
                f" · {r['requests_text']}")
    status = {"cancelled": " (cancelled)", "failed": " (failed)",
              "migrated": " (from an earlier Lector)"}.get(r["status"], "")
    lines = [f"{r['label']} · {when}{status}",
             f"{r['kept'] or 0:,} pages kept of {r['found'] or 0:,} found · "
             f"{r['new']} new, {r['withdrawn']} withdrawn",
             r["requests_text"] + (f" · {r['failed']} failed" if r["failed"] else "")]
    return "\n".join(lines)


def skips_text(f):
    """The two skips, which drop pages even when no years or journals are set."""
    bits = [t for on, t in ((f.get("skip_duplicates"), "duplicate scans"),
                            (f.get("skip_index"), "index pages")) if on]
    return " and ".join(bits).capitalize() if bits else "Nothing"


def plain_change(text):
    """'to year: None -> 1930' -> 'to year: any -> 1930'."""
    return text.replace("None", "any").replace("->", "\u2192")


class HistoryScreen(Screen):
    def __init__(self, win):
        super().__init__(win, "Saved search")
        self.show_back()
        self.search_id, self.search, self.runs, self.diff = None, None, [], None
        self.edit_btn = S.button("Edit search", "outline", "Change the names and filters",
                                 lambda: win.go("builder", search_id=self.search_id))
        self.dup_btn = S.button("Duplicate", "outline", "Copy as a new draft", self._duplicate)
        self.count_btn = S.button("Count only", "outline",
                                  "Ask BHL how many pages each name has; download nothing",
                                  lambda: self.run("count"))
        self.run_btn = S.button("Run again", "primary", "Run the search with its filters",
                                lambda: self.run("fetch"))
        for b in (self.edit_btn, self.dup_btn, self.count_btn, self.run_btn):
            self.actions.addWidget(b)

        self.summary = S.Card()
        self.summary_grid = QGridLayout()
        self.summary_grid.setHorizontalSpacing(24)
        self.summary.body.addLayout(self.summary_grid)
        self.refresh_check = QCheckBox("Look for newly scanned pages (asks BHL again for every "
                                       "name; untick to re-apply changed filters only)")
        self.refresh_check.setChecked(True)
        self.summary.body.addWidget(self.refresh_check)
        self.status_line = S.label("", "muted", wrap=True)
        self.status_line.hide()
        self.summary.body.addWidget(self.status_line)
        self.body.addWidget(self.summary)

        row = QHBoxLayout()
        row.setSpacing(12)
        runs_card = S.Card("Runs")
        runs_card.setMinimumWidth(300)
        runs_card.setMaximumWidth(420)
        runs_card.body.addWidget(S.label("Every run keeps a copy of the settings it used, so "
                                         "results can be reproduced and cited. Pick a run to "
                                         "compare it with the one before.", "small", wrap=True))
        self.run_list = QListWidget()
        self.run_list.setWordWrap(True)
        self.run_list.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.run_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.run_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.run_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.run_list.setItemDelegate(WrapDelegate(self.run_list))
        self.run_list.setMinimumHeight(260)
        self.run_list.currentRowChanged.connect(self._run_picked)
        runs_card.body.addWidget(self.run_list, 1)
        row.addWidget(runs_card, 2)

        diff_card = S.Card()
        head = QHBoxLayout()
        self.diff_title = S.label("What changed", "h2")
        self.diff_against = S.label("", "small")
        head.addWidget(self.diff_title, 1)
        head.addWidget(self.diff_against)
        diff_card.body.addLayout(head)
        self.settings_changed = S.label("", "small", wrap=True)
        diff_card.body.addWidget(self.settings_changed)
        self.tabs = QTabWidget()
        self.tables = {}
        for key, _text in TABS:
            t = QTableWidget(0, 3)
            t.setHorizontalHeaderLabels(["PAGE", "YEAR", ""])
            t.verticalHeader().hide()
            t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            t.setWordWrap(True)
            t.setShowGrid(False)
            hh = t.horizontalHeader()
            hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            t.setMinimumHeight(220)
            left_headers(t)
            t.cellDoubleClicked.connect(lambda r, _c, k=key: self._read_row(k, r))
            self.tables[key] = t
            self.tabs.addTab(t, _text)
        diff_card.body.addWidget(self.tabs, 1)
        diff_card.body.addWidget(S.label("Double-click a page to read it.", "small"))
        bottom = QHBoxLayout()
        self.review_btn = S.button("Review new pages", "view", "Open the reading list",
                                   self._review_new)
        self.export_btn = S.button("Export", "outline", "Make a dossier of this search",
                                   lambda: win.go("export", search_id=self.search_id))
        bottom.addWidget(self.review_btn)
        bottom.addWidget(self.export_btn)
        bottom.addStretch(1)
        diff_card.body.addLayout(bottom)
        row.addWidget(diff_card, 5)
        self.body.addLayout(row, 1)

    # --- load ---------------------------------------------------------------
    def open(self, search_id=None, run=None, refresh=None, **_kw):
        if search_id is not None:
            self.search_id = search_id
        if refresh is not None:
            self.refresh_check.setChecked(refresh)
        self.refresh()
        if run:
            self.run(run)

    def refresh(self):
        if self.search_id is None:
            return
        s = self.win.call(self.svc.get_search, self.search_id)
        if s is None:
            return
        self.search = s
        self.title.setText(s["name"])
        self.subtitle.setText(f"{s['target_tvk'] or s['kind']} · created "
                              f"{S.fmt_when(s['created']).split(',')[0]} · "
                              f"{'draft' if s['status'] == 'draft' else 'active'}")
        self._fill_summary(s)
        self.runs = self.win.call(self.svc.list_runs, self.search_id) or []
        self.run_list.blockSignals(True)
        self.run_list.clear()
        for r in self.runs:
            item = QListWidgetItem(_run_text(r))
            item.setData(Qt.ItemDataRole.UserRole, r["run_id"])
            self.run_list.addItem(item)
        self.run_list.blockSignals(False)
        self.run_btn.setText("Run again" if self.runs else "Run")
        fetches = [r for r in self.runs if r["mode"] == "fetch"]
        if fetches:
            self.run_list.setCurrentRow(self.runs.index(fetches[0]))
        else:
            self._show_diff(None, "No pages fetched yet. Press Run to fetch them.")

    def _fill_summary(self, s):
        grid = self.summary_grid
        while grid.count():
            w = grid.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        f = s["filters"]
        names = [n["name"] for n in s["names"] if n["included"]]
        held = len(s["names"]) - len(names)
        # the service's words for the filters: the same as Saved searches' Scope column
        years, journals = s["years"], s["scope"]
        held_pages = next((x["pages_held"] for x in self.win.call(self.svc.list_searches) or []
                           if x["search_id"] == s["search_id"]), 0)
        cells = (("Names", ", ".join(names) + (f" ({held} held back)" if held else "")),
                 ("Years", years), ("Journals", journals),
                 ("Page limit", f"{f['max_pages']:,} per name" if f["max_pages"] else "None"),
                 ("Left out", skips_text(f)),
                 ("Pages held", f"{held_pages:,}"))
        for col, (head, value) in enumerate(cells):
            grid.addWidget(S.label(head, "caps"), 0, col)
            grid.addWidget(S.label(value, "body", wrap=True), 1, col)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(2, 2)

    # --- runs and their differences -------------------------------------------
    def _run_picked(self, row):
        if not (0 <= row < len(self.runs)):
            return
        r = self.runs[row]
        if r["mode"] != "fetch":
            self._show_diff(None, "A count-only run downloads nothing, so there is nothing "
                                  "to compare.")
            return
        fetches = [x for x in self.runs if x["mode"] == "fetch"]
        i = fetches.index(r)
        if i + 1 >= len(fetches):
            self._show_diff(None, f"{r['label']} is the first run of this search: "
                                  f"{r['kept'] or 0:,} pages kept. Later runs are compared "
                                  "with it.", title=r["label"])
            return
        d = self.win.call(self.svc.run_diff, self.search_id, fetches[i + 1]["run_id"], r["run_id"])
        self._show_diff(d)

    def _show_diff(self, d, message="", title="What changed"):
        self.diff = d
        kept = {}
        if d is not None and d["withdrawn"]:
            kept = {i["page_id"]: i["state"] for i in
                    self.win.call(self.svc.review_queue, self.search_id,
                                  include_withdrawn=True) or []}
        if d is None:
            self.diff_title.setText(title)
            self.diff_against.setText("")
            self.settings_changed.setText(message)
        else:
            self.diff_title.setText(f"What changed in run {d['number_b']}")
            self.diff_against.setText(f"Compared with run {d['number_a']}")
            sc = d["settings_changed"]
            self.settings_changed.setText("Settings changed: " + "; ".join(map(plain_change, sc))
                                          if sc
                                          else "Same settings as the run before.")
        for i, (key, text) in enumerate(TABS):
            items = (d or {}).get(key, [])
            self.tabs.setTabText(i, f"{text} ({len(items):,})")
            self._fill_table(key, items, kept)
        if d is not None and not d["new"] and d["withdrawn"]:
            self.tabs.setCurrentIndex(1)
        else:
            self.tabs.setCurrentIndex(0 if d is None or d["new"] else 2)

    def _fill_table(self, key, items, kept):
        t = self.tables[key]
        t.setRowCount(len(items))
        for r, p in enumerate(items):
            text = p["citation"] or f"BHL page {p['page_id']}"
            note = p.get("reason") or (f"Matched name: {p['matched_names']}"
                                       if p.get("matched_names") else "")
            cell = QTableWidgetItem(text + (f"\n{note}" if note else ""))
            cell.setToolTip(text)
            t.setItem(r, 0, cell)
            t.setItem(r, 1, QTableWidgetItem(str(p["year"] or "")))
            if key == "withdrawn":
                if kept.get(p["page_id"]) == "kept":
                    t.setCellWidget(r, 2, S.badge("Kept", "success"))
                else:
                    t.setCellWidget(r, 2, S.button(
                        "Keep anyway", "outline", "Keep this page in the search (your notes on "
                        "it are kept either way)", lambda _=False, pid=p["page_id"]: self.keep(pid)))
            else:
                t.setItem(r, 2, QTableWidgetItem(""))
        if key == "withdrawn":
            hh = t.horizontalHeader()
            hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
            fit_widget_column(t, 2, 20)
        t.resizeRowsToContents()

    def keep(self, page_id):
        self.win.call(self.svc.keep_page, self.search_id, page_id)
        self._run_picked(self.run_list.currentRow())

    def _read_row(self, key, row):
        items = (self.diff or {}).get(key, [])
        if 0 <= row < len(items):
            self.win.go("review", search_id=self.search_id, page_id=items[row]["page_id"],
                        status="all")

    def _review_new(self):
        new = (self.diff or {}).get("new") or []
        self.win.go("review", search_id=self.search_id,
                    page_id=new[0]["page_id"] if new else None)

    def _duplicate(self):
        new = self.win.call(self.svc.duplicate_search, self.search_id)
        if new:
            self.win.go("builder", search_id=new)

    # --- running ------------------------------------------------------------
    def run(self, mode="fetch"):
        """Run (or count) this search in the background; the result shows here."""
        if self.search_id is None:
            return False
        sid, name = self.search_id, (self.search or {}).get("name", "search")
        if mode == "fetch" and self.search and not self.search["filters"]["recorded"]:
            self.win.say(f"\u201c{name}\u201d was fetched before Lector kept each search's "
                         "filters. Set its filters (years, journals, page limit) and save; "
                         "then run it.")
            self.win.go("builder", search_id=sid)
            return False
        verb = "Counting" if mode == "count" else "Running"
        started = self.win.run_task(f"{verb} “{name}”", self.svc.run_search, sid,
                                    mode=mode, refresh=self.refresh_check.isChecked(),
                                    on_done=lambda r: self._ran(sid, r),
                                    on_error=lambda m: self._failed(sid, m))
        if started:
            self.status_line.show()
            self.status_line.setText(f"{verb}… BHL allows one request a second; you can "
                                     "keep reading other pages, or press Cancel below.")
        return started

    def _ran(self, sid, r):
        if r["status"] == "cancelled":
            msg = f"{r['label']} cancelled. Whatever was downloaded is kept; running again " \
                  "carries on from there."
        elif r["mode"] == "count":
            msg = (f"Counted: {r['found']:,} pages found on BHL, {r['kept']:,} within the "
                   f"filters; {r['requests_text']}.")
        else:
            msg = (f"{r['label']} finished: {r['kept']:,} pages kept of {r['found']:,} "
                   f"found — {r['new']:,} new, {r['withdrawn']:,} no longer matched, "
                   f"{r['requests_text']}.")
            if r["failed"]:
                msg += f" {r['failed']} pages could not be downloaded: run again to retry them."
        if r.get("message") and r["status"] == "failed":
            msg += f" ({r['message']})"
        self.win.statusBar().showMessage(msg, 15000)
        if self.search_id == sid:
            self.refresh()
            self.status_line.setText(msg)
            self.status_line.show()

    def _failed(self, sid, message):
        if self.search_id == sid:
            self.status_line.setText(message)
            self.status_line.show()
        self.win.say(message, "warning")
