"""Saved searches: the dashboard (four figures, the searches, recent activity, attention)."""
from html import escape

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QMenu, QProgressBar, QTableWidget, QToolButton, QVBoxLayout,
                               QWidget)
from src.views.stats.stat_widgets import StatCard

from Lector.ui import style as S
from Lector.ui.common import Screen, clear_layout, fit_rows, fit_widget_column

COLUMNS = ("Search", "Scope", "Last run", "Pages", "Reviewed", "")


def _cell(html, tip=None):
    lab = QLabel(html)
    lab.setTextFormat(Qt.TextFormat.RichText)
    lab.setWordWrap(True)
    lab.setContentsMargins(8, 6, 8, 6)
    lab.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    lab.setStyleSheet("background: transparent; border: none;")
    if tip:
        lab.setToolTip(tip)
    return lab


def _small(text):
    return f"<span style='color:{S.c('text_secondary')}; font-size:{S.T.font_size('sm')}'>" \
           f"{escape(text)}</span>"


class SearchesScreen(Screen):
    def __init__(self, win):
        super().__init__(win, "Saved searches",
                         "Each search keeps its names, filters and every run, so it can be "
                         "repeated exactly or updated as BHL adds new scans.")
        self.filter_box = QLineEdit()
        self.filter_box.setPlaceholderText("Filter: species, journal or name")
        self.filter_box.setClearButtonEnabled(True)
        self.filter_box.setMinimumWidth(200)
        self.filter_box.textChanged.connect(self._apply_filter)
        self.actions.addWidget(self.filter_box)
        self.actions.addWidget(S.button("New search", "primary",
                                        slot=lambda: win.go("builder", search_id=None)))
        cards = QHBoxLayout()
        cards.setSpacing(12)
        self.cards = {}
        for key, title in (("searches", "Saved searches"), ("pages_harvested", "Pages harvested"),
                           ("awaiting_review", "Awaiting review"),
                           ("records_extracted", "Records extracted")):
            card = StatCard(title, "0", color=S.ACCENT_DARK)
            self.cards[key] = card
            cards.addWidget(card, 1)
        self.body.addLayout(cards)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels([c.upper() for c in COLUMNS])
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setShowGrid(False)
        self.table.setWordWrap(True)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)   # fills the rest (_fit_height)
        for col, w in ((1, 140), (2, 116), (3, 96), (4, 116)):
            hh.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
            self.table.setColumnWidth(col, w)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        hh.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.table.cellDoubleClicked.connect(self._open_row)
        self.table.viewport().installEventFilter(self)
        self.body.addWidget(self.table)
        self.empty = S.label("No saved searches yet. Press “New search” to make one: "
                             "type a species, check its names, choose the journals and run it.",
                             "muted", wrap=True)
        self.body.addWidget(self.empty)

        bottom = QHBoxLayout()
        bottom.setSpacing(12)
        self.activity = S.Card("Recent activity")
        self.activity_rows = QVBoxLayout()
        self.activity.body.addLayout(self.activity_rows)
        self.activity.body.addStretch(1)
        self.attention = S.Card("Needs attention", variant="warning")
        self.attention_rows = QVBoxLayout()
        self.attention.body.addLayout(self.attention_rows)
        self.attention.body.addStretch(1)
        bottom.addWidget(self.activity, 1)
        bottom.addWidget(self.attention, 1)
        self.body.addLayout(bottom)
        self.body.addStretch(1)
        self.rows = []

    # --- data ---------------------------------------------------------------
    def open(self, **_kw):
        self.refresh()

    def refresh(self):
        dash = self.win.call(self.svc.dashboard)
        searches = self.win.call(self.svc.list_searches)
        if dash is None or searches is None:
            return
        for key, card in self.cards.items():
            card.set_value(f"{dash[key]:,}")
        self._fill_table(searches)
        clear_layout(self.activity_rows)
        for a in dash["activity"][:8] or [{"when": "", "text": "Nothing run yet."}]:
            row = S.label(f"{S.fmt_when(a['when'])}   {a['text']}".strip(), "body", wrap=True)
            self.activity_rows.addWidget(row)
        clear_layout(self.attention_rows)
        notes = dash["attention"] or ["Nothing needs attention."]
        for text in notes[:8]:
            self.attention_rows.addWidget(S.label(text, "warn", wrap=True))

    def _fill_table(self, searches):
        self.rows = searches
        self.table.setRowCount(len(searches))
        for r, s in enumerate(searches):
            sub = s["target_tvk"] or {"family": "Whole family from UKSI",
                                      "list": "Species list"}.get(s["kind"], "")
            n = s["names_included"]
            name_html = (f"<a href='open' style='color:{S.ACCENT}; font-weight:700;"
                         f" text-decoration:none'>{escape(s['name'])}</a><br>"
                         f"<i>{escape(s['target_name'] or '')}</i><br>"
                         + _small(f"{sub} · {n} name{'s' if n != 1 else ''}"))
            cell = _cell(name_html, "Open the search: its runs and what changed")
            cell.linkActivated.connect(lambda _l, sid=s["search_id"]:
                                       self.win.go("history", search_id=sid))
            self.table.setCellWidget(r, 0, cell)
            scope = escape(s["journal_preset"] or ("Your title words" if s.get("filters_recorded")
                                                   else "Filters not recorded"))
            self.table.setCellWidget(r, 1, _cell(f"{scope}<br>{escape(s['years'])}"))
            last = s["last_run"]
            if last:
                when = S.fmt_when(last["started"]).split(",")[0]
                runs = s["runs"]
                status = "" if last["status"] in ("done", "migrated") else f" ({last['status']})"
                self.table.setCellWidget(r, 2, _cell(
                    f"{escape(when)}{escape(status)}<br>"
                    + _small(f"{runs} run{'s' if runs != 1 else ''}")))
                found = s["found_last"]
                self.table.setCellWidget(r, 3, _cell(
                    f"<b>{s['pages_held']:,}</b><br>"
                    + _small(f"of {found:,} found" if found is not None else "")))
            else:
                self.table.setCellWidget(r, 2, _cell(
                    f"<span style='{S.T.badge_style('default')}'>Draft — not run</span>"))
                self.table.setCellWidget(r, 3, _cell("—"))
            self.table.setCellWidget(r, 4, self._reviewed_cell(s))
            self.table.setCellWidget(r, 5, self._actions_cell(s))
        fit_widget_column(self.table, 5)
        self._fit_height()
        self.table.setVisible(bool(searches))
        self.empty.setVisible(not searches)
        self._apply_filter(self.filter_box.text())

    def _fit_height(self):
        """Rows as tall as their wrapped text; the table as tall as its rows (the page
        scrolls, not the table)."""
        others = sum(self.table.columnWidth(c) for c in range(1, len(COLUMNS)))
        self.table.setColumnWidth(0, max(200, self.table.viewport().width() - others))
        fit_rows(self.table, 64)
        self.table.setFixedHeight(self.table.horizontalHeader().sizeHint().height()
                                  + sum(self.table.rowHeight(i) for i in range(self.table.rowCount())
                                        if not self.table.isRowHidden(i)) + 4
                                  + (self.table.horizontalScrollBar().sizeHint().height()
                                     if self.table.horizontalScrollBar().maximum() > 0 else 0))

    def eventFilter(self, obj, event):
        if obj is self.table.viewport() and event.type() == QEvent.Type.Resize:
            QTimer.singleShot(0, self._fit_height)
        return False

    def _reviewed_cell(self, s):
        held = s["pages_held"]
        if not held:
            return _cell("—")
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(8, 10, 8, 6)
        v.setSpacing(4)
        bar = QProgressBar()
        bar.setRange(0, held)
        bar.setValue(min(s["reviewed"], held))
        bar.setTextVisible(False)
        bar.setFixedHeight(8)
        v.addWidget(bar)
        v.addWidget(S.label(f"{s['reviewed']:,} of {held:,}", "small"))
        v.addStretch(1)
        return w

    def _actions_cell(self, s):
        sid = s["search_id"]
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(6, 6, 8, 6)
        h.setSpacing(6)
        if s["last_run"]:
            if not s["filters_recorded"]:
                h.addWidget(S.button("Set filters", "outline", "This search's first filters "
                                     "were not recorded: set them before running it again",
                                     lambda: self.win.go("builder", search_id=sid)))
            else:
                h.addWidget(S.button("Run again", "outline", "Run the search again with its "
                                     "filters",
                                     lambda: self.win.go("history", search_id=sid, run="fetch")))
            if s["pages_held"]:
                h.addWidget(S.button("Review", "view", "Read and mark the pages",
                                     lambda: self.win.go("review", search_id=sid)))
        else:
            h.addWidget(S.button("Edit", "outline", "Change the names and filters",
                                 lambda: self.win.go("builder", search_id=sid)))
            h.addWidget(S.button("Run", "primary", "Fetch the pages from BHL",
                                 lambda: self.win.go("history", search_id=sid, run="fetch")))
        more = QToolButton()
        more.setText("More")
        more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        more.setStyleSheet(S.button_qss("outline").replace("QPushButton", "QToolButton"))
        menu = QMenu(more)
        menu.addAction("Open (runs and changes)", lambda: self.win.go("history", search_id=sid))
        menu.addAction("Edit names and filters", lambda: self.win.go("builder", search_id=sid))
        menu.addAction("Count only (no pages downloaded)",
                       lambda: self.win.go("history", search_id=sid, run="count"))
        menu.addAction("Duplicate as a new draft", lambda: self._duplicate(sid))
        menu.addAction("Export a dossier", lambda: self.win.go("export", search_id=sid))
        more.setMenu(menu)
        h.addWidget(more)
        return w

    # --- actions ------------------------------------------------------------
    def _open_row(self, row, _col):
        if 0 <= row < len(self.rows):
            self.win.go("history", search_id=self.rows[row]["search_id"])

    def _duplicate(self, sid):
        new = self.win.call(self.svc.duplicate_search, sid)
        if new:
            self.win.go("builder", search_id=new)

    def _apply_filter(self, text):
        words = text.lower().split()
        for r, s in enumerate(self.rows):
            hay = " ".join(str(s.get(k) or "") for k in
                           ("name", "target_name", "target_tvk", "journal_preset", "years")).lower()
            self.table.setRowHidden(r, not all(w in hay for w in words))
        self._fit_height()
