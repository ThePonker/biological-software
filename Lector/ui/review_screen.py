"""Reading list: page list, the page, review marks (mock-up screen 4).

Keys (when not typing in a box): J next page, K previous, 1-4 set the status
(relevant, not relevant, record extracted, unreviewed) and move to the next page.
Notes save as you type. Filters (years, journals, tag, hide not relevant) and the sort
order are remembered per search (Round 15); the count follows them.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QComboBox, QLineEdit, QListWidget,
                               QListWidgetItem, QPlainTextEdit, QSplitter, QTextEdit,
                               QVBoxLayout, QWidget)

from Lector.ui import style as S
from Lector.ui.common import Screen, WrapDelegate
from Lector.ui.reading_filters import (SORTS, ReadingFilters, count_text, filter_items,
                                       journal_of, load_filters, save_filters, sort_items)
from Lector.ui.review_panes import PageView, ReviewPanel
from Lector.ui.tags_dialog import TagsDialog
from shared.fit_to_screen import scroll_body

SHOW = (("Unreviewed", "unreviewed"), ("All pages", "all"), ("Relevant", "relevant"),
        ("Record extracted", "record_extracted"), ("Not relevant", "not_relevant"),
        ("No longer matched", "withdrawn"))
ROLE = Qt.ItemDataRole.UserRole


def entries_text(items):
    """'79 entries (87 pages, duplicates merged)': an entry is a page with the other
    scans of the same text inside it."""
    pages = sum(1 + len(i.get("copies") or []) for i in items)
    head = f"{len(items):,} entr{'ies' if len(items) != 1 else 'y'}"
    if pages == len(items):
        return head
    return f"{head} ({pages:,} pages, duplicates merged)"


def _label(item, show_new=True):
    bits = [item.get("title"), item.get("volume"), item.get("page_label")]
    src = ", ".join(b for b in bits if b) or item["source"] or item["citation"]
    if item["year"] and str(item["year"]) not in src:
        src += f" ({item['year']})"
    marks = [S.STATUS_LABELS[item["review_status"]]]
    if item.get("review_tag"):
        marks.append(item.get("review_tag_label") or item["review_tag"])
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


class ReviewScreen(Screen):
    def __init__(self, win):
        super().__init__(win, "Reading list")
        self.show_back()
        self.search_id, self.items, self.shown, self._show_new = None, [], [], True
        self._pending, self._dialog = None, None
        self.search_box = QComboBox()
        self.search_box.setMinimumWidth(200)
        self.search_box.activated.connect(lambda _i: self.open(
            search_id=self.search_box.currentData()))
        self.show_box = QComboBox()
        for text, key in SHOW:
            self.show_box.addItem(text, key)
        self.show_box.activated.connect(lambda _i: self._filters_changed(reload=True))
        self.order_box = QComboBox()                      # the sort order (Round 15)
        for key, text in SORTS:
            self.order_box.addItem(text, key)
        self.order_box.activated.connect(lambda _i: self._filters_changed())
        for text, w in (("Search", self.search_box), ("Show", self.show_box),
                        ("Sort by", self.order_box)):
            col = QVBoxLayout()
            col.setSpacing(2)
            col.addWidget(S.label(text, "small"))
            col.addWidget(w)
            self.actions.addLayout(col)
        self.remove_btn = S.button("Remove not-relevant pages…", "delete",
                                   "Take the pages marked not relevant out of this search",
                                   self.remove_not_relevant)
        self.actions.addWidget(self.remove_btn)
        self.filters = ReadingFilters()
        self.filters.changed.connect(self._filters_changed)
        self.body.addWidget(self.filters)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        self.key = S.status_key()
        lv.addWidget(self.key)
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
        self.list.setItemDelegate(WrapDelegate(self.list))
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
        self.panel.manage_tags.connect(self.manage_tags)
        self.panel.record_requested.connect(self.record_from_page)
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
        keys += tuple((str(i + 1), lambda st=st: self.mark_and_next(st))
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
        self._load_filters()
        self.reload(page_id)
        self.list.setFocus()

    def _load_filters(self):
        """The filters and sort order remembered for this search."""
        self.panel.set_tags(self._tag_rows())
        f = load_filters(self.search_id)
        self.filters.set_tags(self._tag_rows(), keep=f["tag"])
        self.order_box.setCurrentIndex(max(self.order_box.findData(f["sort"]), 0))
        self._pending = f

    def _tag_rows(self):
        return self.win.call(self.svc.list_tags) or []

    def _filters_changed(self, reload=False):
        """Any filter or the sort changed: remember it for this search and redraw."""
        if self.search_id is not None:
            save_filters(self.search_id, dict(self.filters.values(),
                                              sort=self.order_box.currentData()))
        if reload:
            self.reload()
        else:
            self._fill_list(self.page.item["page_id"] if self.page.item else None)

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
                                       include_withdrawn=show == "withdrawn") or []
            self.empty.setText("")
        self._update_subtitle()
        counts = {}
        for i in self.items:
            if i["state"] != "withdrawn":
                counts[journal_of(i)] = counts.get(journal_of(i), 0) + 1
        self.filters.set_journals(counts)
        if self._pending is not None:               # a search just opened: its remembered filters
            self.filters.set_values(self._pending)
            self._pending = None
        self._fill_list(page_id)

    def _update_subtitle(self):
        name = self.search_box.currentText()
        current = [i for i in self.items if i["state"] != "withdrawn"]
        done = sum(1 for i in current if i["review_status"] != "unreviewed")
        self.subtitle.setText(f"{name} · {entries_text(current)} · {done:,} of "
                              f"{len(current):,} reviewed" if name else "")

    def _fill_list(self, page_id=None):
        show, words = self.show_box.currentData(), self.find_box.text().lower().split()
        f, sort = self.filters.values(), self.order_box.currentData()
        self.filters.hide_nr.setEnabled(show != "not_relevant")
        shown = filter_items(self.items, f, show)
        if words:
            shown = [i for i in shown if all(w in self._hay(i) for w in words)]
        self.shown = sort_items(shown, sort)
        every = [i for i in self.items if (i["state"] == "withdrawn") == (show == "withdrawn")]
        self.filters.count.setText(count_text(self.shown, every))
        # "new" means new in the last run: not worth saying when every page is new
        self._show_new = not all(i["new_in_last_run"] for i in self.items)
        self.list.blockSignals(True)
        self.list.clear()
        group, select = None, None
        bold = QFont()
        bold.setBold(True)
        for item in self.shown:
            g = self._group(item, sort)
            if g and g != group:
                group = g
                head = QListWidgetItem(g)
                head.setFlags(Qt.ItemFlag.NoItemFlags)
                head.setFont(bold)
                head.setForeground(QBrush(QColor(S.c("text_heading"))))
                head.setBackground(QBrush(QColor(S.c("surface_alt"))))
                self.list.addItem(head)
            li = QListWidgetItem(S.status_icon(item["review_status"]),
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
                self.empty.setText("No page matches: widen the filters, or choose "
                                   "“All pages” under Show.")
            else:
                self.empty.setText("")

    @staticmethod
    def _hay(item):
        return " ".join([item["citation"] or "", item["notes"] or "",
                         " ".join(" ".join(x) for x in item["excerpts"])]).lower()

    @staticmethod
    def _group(item, sort):
        """The heading a row sits under: decade for the year sorts, journal for Journal."""
        if sort == "journal":
            return journal_of(item)
        if sort in ("year", "year_desc"):
            return f"{item['year'] // 10 * 10}s" if item["year"] else "Year unknown"
        return None

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
        """A J/K/1-4 key: only on this screen, and never while typing in a box (the
        notes, the find box), where the key is text."""
        if self.win.current() is not self or not self.isVisible():
            return
        w = QApplication.focusWidget()
        # the page's own text (a read-only QTextBrowser, clicked to scroll or copy) is not
        # typing: the keys still work there (R8 review)
        if isinstance(w, (QPlainTextEdit, QLineEdit, QTextEdit)) and not w.isReadOnly():
            return
        fn()

    def mark_and_next(self, status):
        """Keys 1-4: set the page's status, then go to the next page."""
        if self.current_item() is None:
            return
        self.set_status(status)
        self.step(1)

    # --- review marks ---------------------------------------------------------
    def _refresh_row(self, item):
        for r in range(self.list.count()):
            li = self.list.item(r)
            if li.data(ROLE) == item["page_id"]:
                li.setText(_label(item, self._show_new))
                li.setIcon(S.status_icon(item["review_status"]))

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
        labels = {t["key"]: t["label"] for t in self._tag_rows()}
        item["review_tag_label"] = labels.get(tag, tag) if tag else None
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

    def record_from_page(self):
        """Record from this page…: the form opens with the species and citation filled in.
        Saved, the page is marked Record extracted."""
        item = self.current_item()
        if item is None or self.search_id is None:
            return None
        from Lector.ui.record_dialog import RecordDialog
        self.panel.flush()
        dlg = RecordDialog(self.svc, self.search_id, item["page_id"], parent=self.win)
        dlg.accepted.connect(lambda: self._record_saved(item))
        self._dialog = dlg
        if not self.win.quiet:
            dlg.exec()
        return dlg

    def _record_saved(self, item):
        item["review_status"] = "record_extracted"
        self.panel.set_status("record_extracted")
        self._refresh_row(item)
        self._update_subtitle()
        self.panel.saved.setText("Record saved. See Extracted records.")

    # --- tags and removing pages ------------------------------------------------
    def manage_tags(self):
        """Manage tags… : add, rename, hide. Afterwards the buttons and the list follow."""
        dlg = TagsDialog(self.svc, self)
        self._dialog = dlg
        if not self.win.quiet:
            dlg.exec()
        self.panel.set_tags(self._tag_rows())
        self.filters.set_tags(self._tag_rows())
        self.reload()

    def remove_not_relevant(self):
        """Remove not-relevant pages…: the count, a confirmation, a backup, then only the
        pages marked not relevant leave the search (never another status)."""
        if self.search_id is None:
            return None
        self.panel.flush()
        info = self.win.call(self.svc.remove_not_relevant_preview, self.search_id)
        if info is None:
            return None
        name = self.search_box.currentText()
        if not info["pages"]:
            self.win.say(f"No page of “{name}” is marked not relevant.")
            return None
        n, shared = info["pages"], info["pages_shared"]
        text = (f"Remove {n:,} not-relevant page{'s' if n != 1 else ''} from “{name}”?\n\n"
                "They leave this search only. Pages with any other status are not touched."
                f"\nA page no other search holds loses its page text too ({info['pages_deleted']:,}"
                f" page{'s' if info['pages_deleted'] != 1 else ''}); "
                f"{shared:,} also used by another search stay whole.\n\n"
                "lector.db is backed up first (data\\_backups\\lector_pre_remove_<time>.db).")
        if not self.win.choose(text, "Remove them", "Keep them", "Remove not-relevant pages",
                               danger=True):
            return None
        done = self.win.call(self.svc.remove_not_relevant, self.search_id)
        if done is not None:
            self.win.say(f"Removed {done['pages']:,} page{'s' if done['pages'] != 1 else ''}. "
                         f"Backup copy: {done['backup']}")
            self.open(search_id=self.search_id)
        return done
