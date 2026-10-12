"""Reading list panes: the page (middle) and the review marks (right)."""
from html import escape

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QButtonGroup, QGridLayout, QHBoxLayout, QLabel, QPlainTextEdit,
                               QTextBrowser)

from Lector.service import REVIEW_STATUSES, REVIEW_TAGS
from Lector.ui import style as S

COPYRIGHT_GENERAL = ("Pages printed after 1930 may still be in copyright: check the rights "
                     "statement on BHL before reproducing them.")


def runs_html(runs):
    """[(text, bold)] -> HTML with the searched names in bold."""
    return "".join(f"<b>{escape(t)}</b>" if bold else escape(t) for t, bold in runs) \
        .replace("\n", "<br>")


class PageView(S.Card):
    """The page being read: citation, excerpts with the names in bold, copies, links."""
    prev_requested = Signal()
    next_requested = Signal()

    def __init__(self, svc):
        super().__init__()
        self.svc, self.item, self.search_id, self._full = svc, None, None, False
        self.position = S.label("", "caps")
        self.citation = S.label("", "h2", wrap=True)
        self.citation.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.meta = S.label("", "small", wrap=True)
        self.meta.setTextFormat(Qt.TextFormat.RichText)
        self.copyright = S.note_box("", "warning")
        self.index_note = S.note_box("", "info")
        for w in (self.position, self.citation, self.meta, self.copyright, self.index_note):
            self.body.addWidget(w)
        self.text = QTextBrowser()
        self.text.setOpenExternalLinks(False)
        self.text.setStyleSheet(self.text.styleSheet() + f" font-size: {S.T.font_size('lg')};")
        self.body.addWidget(self.text, 1)
        self.copies = QLabel()
        self.copies.setWordWrap(True)
        self.copies.setTextFormat(Qt.TextFormat.RichText)
        self.copies.setOpenExternalLinks(False)
        self.copies.linkActivated.connect(lambda url: QDesktopServices.openUrl(QUrl(url)))
        self.body.addWidget(self.copies)
        row = QHBoxLayout()
        self.open_btn = S.button("Open on BHL", "outline", "Open the page scan in your browser",
                                 self.open_bhl)
        self.full_btn = S.button("Show full page text", "outline",
                                 "The whole OCR text of the page", self.toggle_full)
        row.addWidget(self.open_btn)
        row.addWidget(self.full_btn)
        row.addStretch(1)
        self.prev_btn = S.button("Previous", "link", "Previous page (K)", self.prev_requested.emit)
        self.next_btn = S.button("Next", "link", "Next page (J)", self.next_requested.emit)
        row.addWidget(self.prev_btn)
        row.addWidget(self.next_btn)
        self.body.addLayout(row)
        self.show_item(None)

    def show_item(self, item, search_id=None, position=""):
        self.item, self.search_id, self._full = item, search_id, False
        self.full_btn.setText("Show full page text")
        has = item is not None
        for w in (self.open_btn, self.full_btn, self.prev_btn, self.next_btn):
            w.setEnabled(has)
        if not has:
            self.position.setText("")
            self.citation.setText("No page chosen")
            self.meta.setText("Pick a page in the list on the left.")
            self.copyright.hide()
            self.index_note.hide()
            self.text.setHtml("")
            self.copies.setText("")
            return
        self.position.setText(position.upper())
        self.citation.setText(item["citation"])
        bits = [f"Matched name: <i>{escape(item['matched_names'] or '')}</i>",
                f"BHL page {item['page_id']}"]
        if item.get("page_type"):
            bits.append(f"page type: {escape(item['page_type'])}")
        if item.get("section") != "main":
            bits.append(escape(item["section_label"]))
        if item.get("state") == "withdrawn":
            bits.append("<b>no longer matched by the filters</b>")
        self.meta.setText(" · ".join(bits))
        self.copyright.setText(item.get("copyright_note") or "")
        self.copyright.setVisible(bool(item.get("copyright_note")))
        self.index_note.setVisible(bool(item.get("likely_index")))
        if item.get("likely_index"):
            self.index_note.setText(f"Probably an index or contents page ({item['index_reason']}).")
        self._show_excerpts()
        copies = item.get("copies") or []
        if copies:
            links = "; ".join(f"<a href='{escape(c['bhl_url'] or '')}'>{escape(c['citation'])}</a>"
                              for c in copies)
            self.copies.setText(f"<b>Same text also at:</b> {links}")
        else:
            self.copies.setText("")

    def _show_excerpts(self):
        item = self.item
        if not item["has_text"]:
            self.text.setHtml("<p><i>The page text has not been downloaded yet: run the "
                              "search again to fetch it.</i></p>")
            return
        parts = [f"<p>… {runs_html(runs)} …</p>" for runs in item["excerpt_runs"]]
        self.text.setHtml("".join(parts) or "<p><i>The searched name was not found in the "
                                             "page text (OCR errors are common).</i></p>")

    def toggle_full(self):
        if self.item is None:
            return
        self._full = not self._full
        if self._full:
            d = self.svc.page_detail(self.search_id, self.item["page_id"])
            self.text.setHtml(runs_html(d["text_runs"]))
            self.full_btn.setText("Show excerpts")
        else:
            self._show_excerpts()
            self.full_btn.setText("Show full page text")

    def open_bhl(self):
        if self.item and self.item.get("bhl_url"):
            QDesktopServices.openUrl(QUrl(self.item["bhl_url"]))


class ReviewPanel(S.Card):
    """Status (keys 1-4), what the page is (tag), notes (saved as you type)."""
    status_set = Signal(str)
    tag_set = Signal(str)
    notes_edited = Signal(int, str)        # page id, notes

    STATUS_ORDER = ("relevant", "not_relevant", "record_extracted", "unreviewed")

    def __init__(self):
        super().__init__("Review")
        self.status_buttons, self.tag_buttons = {}, {}
        self.status_group = QButtonGroup(self)
        self.status_group.setExclusive(True)
        grid = QGridLayout()
        grid.setSpacing(6)
        for i, st in enumerate(self.STATUS_ORDER):
            b = S.button(f"{S.STATUS_LABELS[st]}  ({i + 1})", "outline",
                         f"Mark the page {S.STATUS_LABELS[st].lower()} (key {i + 1})",
                         lambda _=False, s=st: self.status_set.emit(s))
            b.setCheckable(True)
            self.status_group.addButton(b)
            self.status_buttons[st] = b
            grid.addWidget(b, i, 0)
        self.body.addLayout(grid)
        self.body.addWidget(S.label("What is this page?", "caps"))
        tags = QGridLayout()
        tags.setSpacing(6)
        for i, tag in enumerate(REVIEW_TAGS):
            b = S.button(S.TAG_LABELS[tag], "outline", "Click again to clear",
                         lambda _=False, t=tag: self._tag_clicked(t))
            b.setCheckable(True)
            self.tag_buttons[tag] = b
            tags.addWidget(b, i // 2, i % 2)
        self.body.addLayout(tags)
        self.body.addWidget(S.label("Notes", "caps"))
        self.notes = QPlainTextEdit()
        self.notes.setPlaceholderText("Locality as printed, date, recorder, doubts…")
        self.notes.setMinimumHeight(90)
        self.notes.textChanged.connect(self._typed)
        self.notes.setMaximumHeight(220)
        self.body.addWidget(self.notes)
        self.saved = S.label("", "small")
        self.body.addWidget(self.saved)
        self.body.addWidget(S.label("Keys: J next, K previous, 1–4 status.", "small", wrap=True))
        self.body.addWidget(S.label(COPYRIGHT_GENERAL, "small", wrap=True))
        self.body.addWidget(S.label("Taking records into Observatum comes later: mark a page "
                                    "“Record extracted” once you have entered it by "
                                    "hand.", "small", wrap=True))
        self.body.addStretch(1)
        self._loading = False
        self._page_id = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(700)
        self._timer.timeout.connect(self._save)
        self.show_item(None)

    def show_item(self, item):
        self.flush()
        self._loading = True
        self._page_id = (item or {}).get("page_id")
        enabled = item is not None
        for b in list(self.status_buttons.values()) + list(self.tag_buttons.values()):
            b.setEnabled(enabled)
        self.notes.setEnabled(enabled)
        self.set_status((item or {}).get("review_status"))
        self.set_tag((item or {}).get("review_tag"))
        self.notes.setPlainText((item or {}).get("notes") or "")
        self.saved.setText("")
        self._loading = False

    def set_status(self, status):
        self.status_group.setExclusive(False)
        for st, b in self.status_buttons.items():
            b.setChecked(st == status)
        self.status_group.setExclusive(True)

    def set_tag(self, tag):
        for t, b in self.tag_buttons.items():
            b.setChecked(t == tag)

    def _tag_clicked(self, tag):
        on = self.tag_buttons[tag].isChecked()
        self.set_tag(tag if on else None)
        self.tag_set.emit(tag if on else "")

    def _typed(self):
        if not self._loading:
            self.saved.setText("Saving…")
            self._timer.start()

    def flush(self):
        """Save notes typed since the last save (now, not after the pause)."""
        if self._timer.isActive():
            self._timer.stop()
            self._save()

    def _save(self):
        if self._page_id is not None:
            self.notes_edited.emit(self._page_id, self.notes.toPlainText())


assert set(ReviewPanel.STATUS_ORDER) == set(REVIEW_STATUSES)
