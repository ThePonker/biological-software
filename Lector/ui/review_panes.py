"""Reading list panes: the page (middle) and the review marks (right)."""
from html import escape

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QButtonGroup, QGridLayout, QHBoxLayout, QLabel,
                               QPlainTextEdit, QTextBrowser)

from Lector.service import REVIEW_STATUSES
from Lector.translate import translate_url
from Lector.ui import style as S
from Lector.ui.common import clear_layout

COPYRIGHT_GENERAL = ("Pages printed after 1930 may still be in copyright: check the rights "
                     "statement on BHL before reproducing them.")


def runs_html(runs):
    """[(text, bold)] -> HTML with the searched names in bold."""
    return "".join(f"<b>{escape(t)}</b>" if bold else escape(t) for t, bold in runs) \
        .replace("\n", "<br>")


def _sent_len(text):
    from Lector.translate import cut_at_sentence
    return len(cut_at_sentence(text)[0])


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
        self.translate_note = S.note_box("", "info")
        self.translate_note.hide()
        for w in (self.position, self.citation, self.meta, self.copyright, self.index_note,
                  self.translate_note):
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
        self.translate_btn = S.button("Translate", "outline",
                                      "Open the page text in Google Translate (your browser): "
                                      "any language to English. Nothing is stored.",
                                      self.translate)
        self.copy_btn = S.button("Copy page text", "outline",
                                 "Copy the whole page text, to paste into a translator", self.copy_text)
        self.copy_btn.hide()
        row.addWidget(self.open_btn)
        row.addWidget(self.full_btn)
        row.addStretch(1)
        self.prev_btn = S.button("Previous", "link", "Previous page (K)", self.prev_requested.emit)
        self.next_btn = S.button("Next", "link", "Next page (J)", self.next_requested.emit)
        row.addWidget(self.prev_btn)
        row.addWidget(self.next_btn)
        self.body.addLayout(row)
        row2 = QHBoxLayout()                      # a second row: the page is not wide
        row2.addWidget(self.translate_btn)
        row2.addWidget(self.copy_btn)
        row2.addStretch(1)
        self.body.addLayout(row2)
        self.show_item(None)

    def show_item(self, item, search_id=None, position=""):
        self.item, self.search_id, self._full = item, search_id, False
        self.full_btn.setText("Show full page text")
        has = item is not None
        for w in (self.open_btn, self.full_btn, self.prev_btn, self.next_btn):
            w.setEnabled(has)
        self.translate_btn.setEnabled(has and item["has_text"])
        self.translate_btn.setToolTip(
            "Open the page text in Google Translate (your browser): any language to English. "
            "Nothing is stored." if not has or item["has_text"]
            else "This page has no downloaded text to translate")
        self.translate_note.hide()
        self.copy_btn.hide()
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
        if (item.get("page_id") or 0) < 0:
            self.text.setHtml("<p><i>This is a whole book or article found by a free-text "
                              "search: BHL gives no page here, so there is no page text. "
                              "Use “Open on BHL” to read it.</i></p>")
            return
        if not item["has_text"]:
            self.text.setHtml("<p><i>The page text has not been downloaded yet: use "
                              "“Fetch missing text” (the search's More menu on Saved "
                              "searches, or Fetch now under Needs attention).</i></p>")
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

    def page_text(self):
        d = self.svc.page_detail(self.search_id, self.item["page_id"])
        return d.get("ocr_text") or ""

    def translate(self):
        """Open the page text in Google Translate (auto -> English) in the browser. Over
        ~4,500 characters only the first part (to a sentence end) is sent; the note says so
        and Copy page text offers the rest. Nothing is stored."""
        if self.item is None or not self.item["has_text"]:
            return None
        text = self.page_text()
        url, cut = translate_url(text)
        QDesktopServices.openUrl(QUrl(url))
        self.copy_btn.setVisible(cut)
        self.translate_note.setVisible(cut)
        if cut:
            self.translate_note.setText(
                f"Only the first part of the page (about {_sent_len(text):,} of {len(text):,} "
                "characters, to the end of a sentence) was sent to Google Translate. To "
                "translate the rest, press “Copy page text” and paste it there.")
        return url

    def copy_text(self):
        if self.item is not None:
            QApplication.clipboard().setText(self.page_text())

    def open_bhl(self):
        if self.item and self.item.get("bhl_url"):
            QDesktopServices.openUrl(QUrl(self.item["bhl_url"]))


class ReviewPanel(S.Card):
    """Status (keys 1-4), what the page is (tag), notes (saved as you type)."""
    status_set = Signal(str)
    tag_set = Signal(str)
    manage_tags = Signal()
    record_requested = Signal()
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
        self.record_btn = S.button("Record from this page…", "primary",
                                   "Type what the page says (species, date, place, recorder…) "
                                   "as a record, and mark the page Record extracted",
                                   self.record_requested.emit)
        self.body.addWidget(self.record_btn)
        self.body.addWidget(S.label("What is this page?", "caps"))
        self.tags_grid = QGridLayout()
        self.tags_grid.setSpacing(6)
        self.body.addLayout(self.tags_grid)
        self.manage_btn = S.button("Manage tags…", "link", "Add, rename or hide your own tags",
                                   self.manage_tags.emit)
        self.body.addWidget(self.manage_btn, 0, Qt.AlignmentFlag.AlignLeft)
        self._tags, self._tag, self._page_id = [], None, None
        self.set_tags([{"key": k, "label": S.TAG_LABELS[k], "hidden": False}
                       for k in S.TAG_LABELS])
        notes_label = S.label("Notes", "body")
        notes_label.setStyleSheet(notes_label.styleSheet() + " font-weight: 600;")
        self.body.addWidget(notes_label)
        self.notes = QPlainTextEdit()
        self.notes.setObjectName("reviewNotes")
        self.notes.setPlaceholderText("Locality as printed, date, recorder, doubts…")
        # an outlined box, as every text box of the theme (the plain one hardly showed)
        self.notes.setStyleSheet(
            f"QPlainTextEdit#reviewNotes {{ background: {S.c('input_bg')};"
            f" color: {S.c('text_primary')}; border: 1px solid {S.c('border_strong')};"
            f" border-radius: {S.c('radius_sm')}; padding: 4px 6px; }}"
            f"QPlainTextEdit#reviewNotes:focus {{ border: 2px solid {S.c('focus_border')}; }}"
            f"QPlainTextEdit#reviewNotes:disabled {{ background: {S.c('disabled_bg')};"
            f" border-color: {S.c('disabled_border')}; }}")
        notes_label.setBuddy(self.notes)
        self.notes.setMinimumHeight(90)
        self.notes.textChanged.connect(self._typed)
        self.notes.setMaximumHeight(220)
        self.body.addWidget(self.notes)
        self.saved = S.label("", "small")
        self.body.addWidget(self.saved)
        self.body.addWidget(S.label("Keys: J next, K previous, 1–4 status and next page.",
                                    "small", wrap=True))
        self.body.addWidget(S.label(COPYRIGHT_GENERAL, "small", wrap=True))
        self.body.addWidget(S.label("Records are listed under Extracted records, where they "
                                    "can be exported for Observatum.", "small", wrap=True))
        self.body.addStretch(1)
        self._loading = False
        self._page_id = None
        self._build_tag_buttons()
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
        self.record_btn.setEnabled(enabled)
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

    def set_tags(self, tags):
        """tags: list_tags() rows. Hidden tags get no button (unless the page carries one)."""
        self._tags = tags
        self._build_tag_buttons()

    def _build_tag_buttons(self):
        clear_layout(self.tags_grid)
        self.tag_buttons = {}
        shown = [t for t in self._tags if not t["hidden"] or t["key"] == self._tag]
        for i, t in enumerate(shown):
            b = S.button(t["label"], "outline", "Click again to clear",
                         lambda _=False, k=t["key"]: self._tag_clicked(k))
            b.setCheckable(True)
            b.setChecked(t["key"] == self._tag)
            b.setEnabled(self._page_id is not None)
            self.tag_buttons[t["key"]] = b
            self.tags_grid.addWidget(b, i // 2, i % 2)

    def set_tag(self, tag):
        self._tag = tag
        self._build_tag_buttons()

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
