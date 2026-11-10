"""Reading-list filters and sorting (Round 15): years, journals, tag, hide not relevant,
and the sort order; remembered per search in QSettings.

filter_items / sort_items / count_text are plain functions (no Qt) so they can be tested
without a window; ReadingFilters is the bar of widgets above the list.
"""
import json

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QMenu, QSpinBox, QToolButton, QWidget,
                               QHBoxLayout, QVBoxLayout)

from Lector.ui import style as S
from shared.settings_store import app_settings

SORTS = (("year", "Year, oldest first"), ("year_desc", "Year, newest first"),
         ("journal", "Journal"), ("title", "Title"), ("found", "Date found"))
NO_TAG, ANY_TAG = "__none__", ""
DEFAULTS = {"from_year": 0, "to_year": 0, "journals": [], "tag": ANY_TAG,
            "hide_not_relevant": True, "sort": "year"}


def _norm(text):
    return " ".join((text or "").lower().split())


def journal_of(item):
    return item.get("journal") or item.get("title") or "Unknown journal"


def filter_items(items, f, status="all"):
    """Items passing the filters. status: a review status, 'withdrawn' or 'all' (the Show
    box). Hide-not-relevant never hides a list you asked for by status."""
    out = []
    lo, hi, journals = f.get("from_year") or 0, f.get("to_year") or 0, set(f.get("journals") or [])
    for i in items:
        if status == "withdrawn":
            if i["state"] != "withdrawn":
                continue
        elif status != "all" and i["review_status"] != status:
            continue
        y = i["year"]
        if (lo and (y is None or y < lo)) or (hi and (y is None or y > hi)):
            continue
        if journals and journal_of(i) not in journals:
            continue
        tag = f.get("tag", ANY_TAG)
        if tag == NO_TAG and i.get("review_tag"):
            continue
        if tag not in (ANY_TAG, NO_TAG) and i.get("review_tag") != tag:
            continue
        if (f.get("hide_not_relevant") and i["review_status"] == "not_relevant"
                and status != "not_relevant"):
            continue
        out.append(i)
    return out


def sort_items(items, key):
    """key: one of SORTS. Pages with no year or no date go last whichever way it runs."""
    def year(i):
        return (i["year"] is None, i["year"] or 0)

    def tie(i):
        return (_norm(journal_of(i)), i["page_id"])
    if key == "year_desc":
        return sorted(items, key=lambda i: (i["year"] is None, -(i["year"] or 0)) + tie(i))
    if key == "journal":
        return sorted(items, key=lambda i: (_norm(journal_of(i)),) + year(i) + (i["page_id"],))
    if key == "title":
        return sorted(items, key=lambda i: (_norm(i.get("article_title") or journal_of(i)),)
                      + year(i) + (i["page_id"],))
    if key == "found":
        return sorted(items, key=lambda i: (not i.get("found_at"), i.get("found_at") or "")
                      + year(i) + (i["page_id"],))
    return sorted(items, key=lambda i: year(i) + tie(i))


def page_count(items):
    """Pages in entries: an entry holds the other scans of the same text."""
    return sum(1 + len(i.get("copies") or []) for i in items)


def count_text(shown, every):
    """'12 of 79 pages': what the filters leave, of all the search's pages."""
    n, m = page_count(shown), page_count(every)
    return f"{n:,} of {m:,} page{'s' if m != 1 else ''}"


def load_filters(search_id):
    f = dict(DEFAULTS)
    try:
        st = app_settings()
        raw = st.value(f"lector/reading/{search_id}")
        if raw:
            f.update({k: v for k, v in json.loads(str(raw)).items() if k in DEFAULTS})
    except (ValueError, TypeError):
        pass
    return f


def save_filters(search_id, f):
    st = app_settings()
    st.setValue(f"lector/reading/{search_id}", json.dumps(f))
    st.sync()


class _StayOpenMenu(QMenu):
    """A menu of tick boxes that stays open while you tick several."""

    def mouseReleaseEvent(self, event):
        action = self.activeAction()
        if action is not None and action.isCheckable():
            action.trigger()
            return
        super().mouseReleaseEvent(event)


def _year_box(tip):
    box = QSpinBox()
    box.setRange(0, 2100)
    box.setSpecialValueText("Any")
    box.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
    box.setMinimumWidth(70)
    box.setToolTip(tip)
    return box


class ReadingFilters(QWidget):
    """Year from/to, journals (several), tag, Hide not relevant. changed fires after any
    change; values() is the filter dict."""
    changed = Signal()

    def __init__(self):
        super().__init__()
        self._journals, self._ticked, self._loading = [], set(), False
        self._counts = {}
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        self.from_year, self.to_year = (_year_box("Pages published from this year"),
                                        _year_box("Pages published up to this year"))
        self.journal_btn = QToolButton()
        self.journal_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.journal_btn.setStyleSheet(S.button_qss("outline").replace("QPushButton",
                                                                       "QToolButton"))
        self.journal_btn.setToolTip("Show only these journals (tick several)")
        self.menu = _StayOpenMenu(self.journal_btn)
        self.journal_btn.setMenu(self.menu)
        self.tag_box = QComboBox()
        self.tag_box.setMinimumWidth(130)
        self.hide_nr = QCheckBox("Hide not relevant")
        self.hide_nr.setToolTip("Pages marked not relevant leave the list but are kept; "
                                "untick to see them again")
        self.clear_btn = S.button("Clear filters", "link", "Years, journals and tag back to all",
                                  self.clear)
        for text, w in (("From year", self.from_year), ("To year", self.to_year),
                        ("Journal", self.journal_btn), ("Tag", self.tag_box)):
            col = QVBoxLayout()
            col.setSpacing(2)
            col.addWidget(S.label(text, "small"))
            col.addWidget(w)
            row.addLayout(col)
        row.addWidget(self.hide_nr, 0, Qt.AlignmentFlag.AlignBottom)
        row.addWidget(self.clear_btn, 0, Qt.AlignmentFlag.AlignBottom)
        row.addStretch(1)
        self.count = S.label("", "body")
        row.addWidget(self.count, 0, Qt.AlignmentFlag.AlignBottom)
        for w in (self.from_year, self.to_year):
            w.valueChanged.connect(self._edited)
        self.tag_box.activated.connect(lambda _i: self._edited())
        self.hide_nr.toggled.connect(lambda _on: self._edited())
        self._set_journal_text()

    # --- state ---------------------------------------------------------------
    def values(self):
        return {"from_year": self.from_year.value(), "to_year": self.to_year.value(),
                "journals": sorted(self._ticked), "tag": self.tag_box.currentData() or ANY_TAG,
                "hide_not_relevant": self.hide_nr.isChecked()}

    def set_values(self, f):
        self._loading = True
        self.from_year.setValue(int(f.get("from_year") or 0))
        self.to_year.setValue(int(f.get("to_year") or 0))
        self._ticked = set(f.get("journals") or []) & set(self._journals) or set()
        self.hide_nr.setChecked(bool(f.get("hide_not_relevant", True)))
        i = self.tag_box.findData(f.get("tag", ANY_TAG))
        self.tag_box.setCurrentIndex(max(i, 0))
        self._rebuild_menu()
        self._loading = False

    def set_tags(self, tags, keep=None):
        """tags: list_tags() rows; hidden tags are listed too (pages may still carry them)."""
        keep = keep if keep is not None else self.tag_box.currentData()
        self.tag_box.blockSignals(True)
        self.tag_box.clear()
        self.tag_box.addItem("Any tag", ANY_TAG)
        self.tag_box.addItem("No tag", NO_TAG)
        for t in tags:
            self.tag_box.addItem(t["label"] + (" (hidden)" if t["hidden"] else ""), t["key"])
        self.tag_box.setCurrentIndex(max(self.tag_box.findData(keep), 0))
        self.tag_box.blockSignals(False)

    def set_journals(self, counts):
        """counts: {journal: pages} for the journals present."""
        self._journals = sorted(counts, key=_norm)
        self._counts = counts
        self._ticked &= set(self._journals)
        self._rebuild_menu()

    def _rebuild_menu(self):
        self.menu.clear()
        every = self.menu.addAction("All journals")
        every.triggered.connect(lambda: self._tick_all())
        self.menu.addSeparator()
        for j in self._journals:
            a = self.menu.addAction(f"{j} ({self._counts.get(j, 0):,})")
            a.setCheckable(True)
            a.setChecked(j in self._ticked)
            a.toggled.connect(lambda on, name=j: self._journal_toggled(name, on))
        self._set_journal_text()

    def _set_journal_text(self):
        n = len(self._ticked)
        self.journal_btn.setText("All journals ▾" if not n else (
            f"{next(iter(self._ticked))} ▾" if n == 1 else f"{n} journals ▾"))

    def _journal_toggled(self, name, on):
        (self._ticked.add if on else self._ticked.discard)(name)
        self._set_journal_text()
        self._edited()

    def _tick_all(self):
        self._ticked = set()
        self._rebuild_menu()
        self._edited()

    def clear(self):
        self._loading = True
        self.from_year.setValue(0)
        self.to_year.setValue(0)
        self.tag_box.setCurrentIndex(0)
        self._ticked = set()
        self._rebuild_menu()
        self._loading = False
        self._edited()

    def _edited(self):
        if not self._loading:
            self.changed.emit()
