"""Search builder, part 3: years, journal preset, page limit, title words, skips."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QGridLayout, QHBoxLayout, QInputDialog,
                               QLineEdit, QPushButton, QSpinBox, QWidget)

from Lector.ui import style as S
from Lector.ui.common import FlowLayout

OWN_WORDS = "No preset (your own words)"


class WordChips(QWidget):
    """Whole-word title chips with a box to add one; click a chip to remove it."""
    changed = Signal()

    def __init__(self, variant="info", placeholder="Add word"):
        super().__init__()
        self._variant = variant
        self._words = []
        self.flow = FlowLayout(self)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        self.edit.setFixedWidth(130)
        self.edit.returnPressed.connect(self._add_typed)
        self._rebuild()

    def words(self):
        return list(self._words)

    def set_words(self, words, emit=False):
        self._words = [w for w in (words or []) if w.strip()]
        self._rebuild()
        if emit:
            self.changed.emit()

    def _chip(self, word):
        b = QPushButton(f"{word}  ×")
        b.setToolTip(f"Remove “{word}”")
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        bg, fg = S.c(self._variant + "_bg"), S.c(self._variant + "_text")
        b.setStyleSheet(f"QPushButton {{ background: {bg}; color: {fg}; border: none;"
                        f" border-radius: {S.c('radius_sm')}; padding: 4px 8px; }}"
                        f"QPushButton:hover {{ border: 1px solid {fg}; }}")
        b.clicked.connect(lambda _=False, w=word: self._remove(w))
        return b

    def _rebuild(self):
        while self.flow.count():
            item = self.flow.takeAt(0)
            w = item.widget()
            if w is not None and w is not self.edit:
                w.setParent(None)
                w.deleteLater()
        for w in self._words:
            self.flow.addWidget(self._chip(w))
        self.flow.addWidget(self.edit)
        self.updateGeometry()

    def _remove(self, word):
        self._words = [w for w in self._words if w != word]
        self._rebuild()
        self.changed.emit()

    def _add_typed(self):
        word = " ".join(self.edit.text().split())
        if word and word.lower() not in {w.lower() for w in self._words}:
            self._words.append(word)
            self.edit.clear()
            self._rebuild()
            self.changed.emit()


def _year_box():
    box = QSpinBox()
    box.setRange(0, 2100)
    box.setSpecialValueText("Any")
    box.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
    box.setMinimumWidth(90)
    return box


class FiltersPanel(S.Card):
    """filters() -> dict for LectorService (from_year ... skip_duplicates)."""
    changed = Signal()

    def __init__(self, svc, say):
        super().__init__("3. Filters")
        self.svc, self.say = svc, say
        self._presets = []
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(4)
        self.from_year, self.to_year = _year_box(), _year_box()
        self.preset = QComboBox()
        self.preset.setMinimumWidth(180)
        self.max_pages = QSpinBox()
        self.max_pages.setRange(0, 100000)
        self.max_pages.setSingleStep(100)
        self.max_pages.setSpecialValueText("No limit")
        self.max_pages.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.max_pages.setToolTip("At most this many pages per name (the earliest first)")
        for col, (text, w) in enumerate((("From year", self.from_year), ("To year", self.to_year),
                                         ("Journal preset", self.preset),
                                         ("Page limit per name", self.max_pages))):
            grid.addWidget(S.label(text, "small"), 0, col)
            grid.addWidget(w, 1, col)
        grid.setColumnStretch(2, 1)
        self.body.addLayout(grid)
        self.body.addWidget(S.label("Title must contain one of (whole words; plurals count)",
                                    "small"))
        self.include = WordChips("info")
        self.body.addWidget(self.include)
        self.body.addWidget(S.label("Leave out titles containing", "small"))
        self.exclude = WordChips("error")
        self.body.addWidget(self.exclude)
        skips = QHBoxLayout()
        self.skip_index = QCheckBox("Skip index pages")
        self.skip_dupes = QCheckBox("Skip duplicate scans")
        self.skip_index.setToolTip("Leave out pages BHL marks as an index or contents page")
        self.skip_dupes.setToolTip("Download one copy when BHL holds the same volume twice")
        skips.addWidget(self.skip_index)
        skips.addWidget(self.skip_dupes)
        skips.addStretch(1)
        skips.addWidget(S.button("Save words as a preset", "link",
                                 "Keep these title words as a journal preset for other searches",
                                 self._save_preset))
        self.body.addLayout(skips)
        for w in (self.from_year, self.to_year, self.max_pages):
            w.valueChanged.connect(self.changed)
        for w in (self.skip_index, self.skip_dupes):
            w.toggled.connect(self.changed)
        self.include.changed.connect(self._words_changed)
        self.exclude.changed.connect(self._words_changed)
        self.preset.activated.connect(self._preset_chosen)

    def load_presets(self, current=None):
        self._presets = self.svc.journal_presets()
        self.preset.blockSignals(True)
        self.preset.clear()
        self.preset.addItem(OWN_WORDS)
        for p in self._presets:
            self.preset.addItem(p["name"])
            self.preset.setItemData(self.preset.count() - 1, p.get("description") or "",
                                    Qt.ItemDataRole.ToolTipRole)
        i = self.preset.findText(current) if current else 0
        self.preset.setCurrentIndex(max(i, 0))
        self.preset.blockSignals(False)

    def set_filters(self, f):
        self.load_presets(f.get("journal_preset"))
        widgets = (self.from_year, self.to_year, self.max_pages, self.skip_index,
                   self.skip_dupes)
        for w in widgets:
            w.blockSignals(True)
        self.from_year.setValue(f.get("from_year") or 0)
        self.to_year.setValue(f.get("to_year") or 0)
        self.max_pages.setValue(f.get("max_pages") or 0)
        self.skip_index.setChecked(bool(f.get("skip_index")))
        self.skip_dupes.setChecked(bool(f.get("skip_duplicates", True)))
        for w in widgets:
            w.blockSignals(False)
        self.include.set_words(f.get("include_words"))
        self.exclude.set_words(f.get("exclude_words"))

    def filters(self):
        preset = self.preset.currentText()
        return {"from_year": self.from_year.value() or None, "to_year": self.to_year.value() or None,
                "journal_preset": None if preset == OWN_WORDS else preset,
                "include_words": self.include.words(), "exclude_words": self.exclude.words(),
                "max_pages": self.max_pages.value(), "skip_index": self.skip_index.isChecked(),
                "skip_duplicates": self.skip_dupes.isChecked()}

    def _preset_by_name(self, name):
        return next((p for p in self._presets if p["name"] == name), None)

    def _preset_chosen(self, _index):
        """A preset's words are copied into the search (editing a preset later never
        changes an earlier search)."""
        p = self._preset_by_name(self.preset.currentText())
        if p:
            self.include.set_words(p["include_words"])
            self.exclude.set_words(p["exclude_words"])
        self.changed.emit()

    def _words_changed(self):
        p = self._preset_by_name(self.preset.currentText())
        if p and (p["include_words"] != self.include.words()
                  or p["exclude_words"] != self.exclude.words()):
            self.preset.setCurrentIndex(0)            # the words are now your own
        self.changed.emit()

    def _save_preset(self):
        if not self.include.words() and not self.exclude.words():
            self.say("Add some title words first.")
            return
        name, ok = QInputDialog.getText(self, "Save journal preset", "Name for these words:")
        name = " ".join(name.split())
        if ok and name:
            self.svc.save_preset(name, self.include.words(), self.exclude.words())
            self.load_presets(name)
            self.changed.emit()
