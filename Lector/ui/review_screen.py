"""Reading list: page list, the page, review marks (mock-up screen 4).

Keys (when not typing in a box): J next page, K previous, 1-4 status
(relevant, not relevant, record extracted, unreviewed). Notes save as you type.
"""
from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (QComboBox, QLineEdit, QListWidget, QListWidgetItem, QSplitter,
                               QStyledItemDelegate, QVBoxLayout, QWidget)

from Lector.ui import style as S
from Lector.ui.common import Screen
from Lector.ui.review_panes import PageView, ReviewPanel
from shared.fit_to_screen import scroll_body

SHOW = (("Unreviewed", "unreviewed"), ("All pages", "all"), ("Relevant", "relevant"),
        ("Record extracted", "record_extracted"), ("Not relevant", "not_relevant"),
        ("No longer matched", "withdrawn"))
ROLE = Qt.ItemDataRole.UserRole


def _label(item, show_new=True):
    bits = [item.get("title"), item.get("volume"), item.get("page_label")]
    src = ", ".join(b for b in bits if b) or item["source"] or item["citation"]
    if item["year"] and str(item["year"]) not in src:
        src += f" ({item['year']})"
    marks = [S.STATUS_LABELS[item["review_status"]]]
    if item.get("review_tag"):
        marks.append(S.TAG_LABELS[item["review_tag"]])
    if item.get("likely_index"):
        marks.append("likely index")
    if item.get("copies"):
        n = len(item["copies"])
        marks.append(f"+{n} scan{'s' if n != 1 else ''}")
    if show_new and item.get("new_in_last_run"):
        marks.append("new")
    if item.get("state") == "withdrawn":
        marks.append("no longer matched")
    return f"{src}\n{' · '.join(marks)}"


class _WrapDelegate(QStyledItemDelegate):
    """Rows tall enough for their wrapped text (Qt's own measure cut some last lines)."""

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        text = index.data() or ""
        width = max(80, self.parent().viewport().width() - 44)   # icon, padding, border
        r = option.fontMetrics.boundingRect(QRect(0, 0, width, 100000),
                                            int(Qt.TextFlag.TextWordWrap), text)
        return QSize(size.width(), max(size.height(), r.height() + 16))


class ReviewScreen(Screen):
    def __init__(self, win):
        super().__init__(win, "Reading list")
        self.search_id, self.items, self.shown, self._show_new = None, [], [], True
        self.search_box = QComboBox()
        self.search_box.setMinimumWidth(200)
        self.search_box.activated.connect(lambda _i: self.open(
            search_id=self.search_box.currentData()))
        self.show_box = QComboBox()
        for text, key in SHOW:
            self.show_box.addItem(text, key)
        self.show_box.activated.connect(lambda _i: self.reload())
        self.order_box = QComboBox()
        self.order_box.addItem("By year", "year")
        self.order_box.addItem("By journal", "journal")
        self.order_box.activated.connect(lambda _i: self.reload())
        for text, w in (("Search", self.search_box), ("Show", self.show_box),
                        ("Order", self.order_box)):
            col = QVBoxLayout()
            col.setSpacing(2)
            col.addWidget(S.label(text, "small"))
            col.addWidget(w)
            self.actions.addLayout(col)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        self.find_box = QLineEdit()
        self.find_box.setPlaceholderText("Find in the list (journal, words, notes)")
        self.find_box.setClearButtonEnabled(True)
        self.find_box.textChanged.connect(lambda _t: self._fill_list())
        lv.addWidget(self.find_box)
        self.list = QListWidget()
        self.list.setWordWrap(True)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # a scroll bar appearing after the rows were measured cut their last line off
        self.list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list.setItemDelegate(_WrapDelegate(self.list))
        self.list.currentItemChanged.connect(self._picked)
        lv.addWidget(self.list, 1)
        left.setMinimumWidth(220)
        self.page = PageView(self.svc)
        self.page.setMinimumWidth(320)
        self.page.next_requested.connect(lambda: self.step(1))
        self.page.prev_requested.connect(lambda: self.step(-1))
        self.panel = ReviewPanel()
        self.panel.status_set.connect(self.set_status)
        self.panel.tag_set.connect(self.set_tag)
        self.panel.notes_edited.connect(self._save_notes)
        panel_scroll = scroll_body(self.panel)
        panel_scroll.setMinimumWidth(240)
        panel_scroll.setMaximumWidth(330)
        for w in (left, self.page, panel_scroll):
            split.addWidget(w)
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 5)
        split.setStretchFactor(2, 2)
        split.setSizes([300, 640, 280])
        self.body.addWidget(split, 1)
        self.empty = S.label("", "muted", wrap=True)
        self.body.addWidget(self.empty)
        keys = (("J", lambda: self.step(1)), ("K", lambda: self.step(-1)))
        keys += tuple((str(i + 1), lambda st=st: self.set_status(st))
                      for i, st in enumerate(ReviewPanel.STATUS_ORDER))
        self.shortcuts = []
        for key, fn in keys:
            sc = QShortcut(QKeySequence(key), win)
            sc.activated.connect(lambda fn=fn: self._key(fn))
            self.shortcuts.append(sc)

    # --- loading ------------------------------------------------------------
    def open(self, search_id=None, page_id=None, status=None, **_kw):
        searches = self.win.call(self.svc.list_searches) or []
        with_pages = [s for s in searches if s["pages_held"]]
        self.search_box.clear()
        for s in with_pages:
            self.search_box.addItem(s["name"], s["search_id"])
        if search_id is None:
            search_id = self.search_id if any(s["search_id"] == self.search_id
                                               for s in with_pages) else (
                with_pages[0]["search_id"] if with_pages else None)
        self.search_id = search_id
        i = self.search_box.findData(search_id)
        if i >= 0:
            self.search_box.setCurrentIndex(i)
        if status or page_id is not None:
            j = self.show_box.findData(status or "all")
            self.show_box.setCurrentIndex(max(j, 0))
        self.reload(page_id)
        self.list.setFocus()

    def reload(self, page_id=None):
        self.panel.flush()
        if page_id is None and self.page.item:
            page_id = self.page.item["page_id"]
        if self.search_id is None:
            self.items = []
            self.empty.setText("No search has pages yet: run a saved search first.")
        else:
            show = self.show_box.currentData()
            self.items = self.win.call(self.svc.review_queue, self.search_id,
                                       order=self.order_box.currentData(),
                                       include_withdrawn=show == "withdrawn") or []
            self.empty.setText("")
        self._update_subtitle()
        self._fill_list(page_id)

    def _update_subtitle(self):
        name = self.search_box.currentText()
        current = [i for i in self.items if i["state"] != "withdrawn"]
        done = sum(1 for i in current if i["review_status"] != "unreviewed")
        self.subtitle.setText(f"{name} · {done:,} of {len(current):,} reviewed"
                              if name else "")

    def _wanted(self, item, show, words):
        if show == "withdrawn":
            if item["state"] != "withdrawn":
                return False
        elif show != "all" and item["review_status"] != show:
            return False
        if words:
            hay = " ".join([item["citation"] or "", item["notes"] or "",
                            " ".join(" ".join(x) for x in item["excerpts"])]).lower()
            return all(w in hay for w in words)
        return True

    def _fill_list(self, page_id=None):
        show, words = self.show_box.currentData(), self.find_box.text().lower().split()
        self.shown = [i for i in self.items if self._wanted(i, show, words)]
        # "new" means new in the last run: not worth saying when every page is new
        self._show_new = not all(i["new_in_last_run"] for i in self.items)
        by_journal = self.order_box.currentData() == "journal"
        self.list.blockSignals(True)
        self.list.clear()
        group, select = None, None
        bold = QFont()
        bold.setBold(True)
        for item in self.shown:
            g = (item["title"] or "Unknown journal") if by_journal else (
                f"{item['year'] // 10 * 10}s" if item["year"] else "Year unknown")
            if g != group:
                group = g
                head = QListWidgetItem(g)
                head.setFlags(Qt.ItemFlag.NoItemFlags)
                head.setFont(bold)
                head.setForeground(QBrush(QColor(S.c("text_heading"))))
                head.setBackground(QBrush(QColor(S.c("surface_alt"))))
                self.list.addItem(head)
            li = QListWidgetItem(S.dot_icon(S.STATUS_DOT[item["review_status"]]),
                                 _label(item, self._show_new))
            li.setData(ROLE, item["page_id"])
            li.setToolTip(item["citation"])
            self.list.addItem(li)
            if item["page_id"] == page_id:
                select = li
        self.list.blockSignals(False)
        if select is None:
            select = next((self.list.item(r) for r in range(self.list.count())
                           if self.list.item(r).data(ROLE) is not None), None)
        if select is not None:
            self.list.setCurrentItem(select)
        else:
            self._picked(None, None)
            if self.items and not self.shown:
                self.empty.setText("No page matches: choose “All pages” under Show.")

    # --- current page ---------------------------------------------------------
    def current_item(self):
        li = self.list.currentItem()
        pid = li.data(ROLE) if li is not None else None
        return next((i for i in self.items if i["page_id"] == pid), None)

    def _picked(self, li, _old):
        item = self.current_item() if li is not None else None
        rows = [r for r in range(self.list.count()) if self.list.item(r).data(ROLE) is not None]
        pos = ""
        if item is not None:
            n = rows.index(self.list.currentRow()) + 1 if self.list.currentRow() in rows else 0
            pos = f"Page {n} of {len(rows)}"
        self.panel.show_item(item)
        self.page.show_item(item, self.search_id, pos)

    def step(self, delta):
        rows = [r for r in range(self.list.count()) if self.list.item(r).data(ROLE) is not None]
        if not rows:
            return
        cur = self.list.currentRow()
        if cur not in rows:
            target = rows[0]
        else:
            i = rows.index(cur) + delta
            target = rows[max(0, min(i, len(rows) - 1))]
        self.list.setCurrentRow(target)

    def _key(self, fn):
        if self.win.current() is self and self.isVisible():
            fn()

    # --- review marks ---------------------------------------------------------
    def _refresh_row(self, item):
        for r in range(self.list.count()):
            li = self.list.item(r)
            if li.data(ROLE) == item["page_id"]:
                li.setText(_label(item, self._show_new))
                li.setIcon(S.dot_icon(S.STATUS_DOT[item["review_status"]]))

    def set_status(self, status):
        item = self.current_item()
        if item is None:
            return
        self.win.call(self.svc.set_review, self.search_id, item["page_id"], status=status)
        item["review_status"] = status
        self.panel.set_status(status)
        self._refresh_row(item)
        self._update_subtitle()

    def set_tag(self, tag):
        item = self.current_item()
        if item is None:
            return
        self.win.call(self.svc.set_review, self.search_id, item["page_id"], tag=tag)
        item["review_tag"] = tag or None
        self._refresh_row(item)

    def _save_notes(self, page_id, text):
        if self.search_id is None:
            return
        self.win.call(self.svc.set_review, self.search_id, page_id, notes=text)
        for i in self.items:
            if i["page_id"] == page_id:
                i["notes"] = text
        if self.page.item and self.page.item["page_id"] == page_id:
            self.panel.saved.setText("Notes saved.")

    def save_notes(self):
        """Save notes not yet saved (closing the window)."""
        self.panel.flush()
