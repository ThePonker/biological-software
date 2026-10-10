"""The Mapping tab's selection: a rank picker, a search box and the chosen taxa as chips
(backlog item 4, review SRCH18; 10 Oct 2026).

Rank: Species / Genus / Family / Order / Taxon group. The box searches with the suite's
shared species search (every word, typing slips, old names, common names; an old name gives
the current taxon) and offers only taxa with records. Click a result to add it as a chip;
add as many as you like -- the map shows all their records together. Each chip shows how
many of its records are on the map once it has been generated (MAP7).

Each chip has a colour (10 Oct 2026, Wil: "no distinction between what you are mapping"):
the swatch at its left; click it to choose another. A taxon keeps the colour chosen for it
(QSettings "mapping/taxon_colour/<tvk or group>"); otherwise it takes the first free colour
of square_style.TAXON_PALETTE. The By taxon style and a one-taxon Presence map use them.
"""
from typing import List, Optional

from PySide6.QtCore import QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QColorDialog, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QVBoxLayout, QWidget)

from ...core.config import TabColors
from ...services.map_taxa import RANK_LABELS, search_taxa
from ...themes import theme
from .square_style import default_taxon_colour

MAX_RESULTS = 8


class MapSelectionBox(QWidget):
    """Rank picker + search + chips. selection_changed(list of chips) on every add/remove."""

    selection_changed = Signal(list)
    colours_changed = Signal()       # a chip's colour changed: recolour, no new query

    def __init__(self, parent=None):
        super().__init__(parent)
        self._chips: List[dict] = []
        self._counts: Optional[List[int]] = None
        self._accent, self._light, self._dark = (TabColors.MAPPING, TabColors.MAPPING_LIGHT,
                                                 TabColors.MAPPING_DARK)
        self._build()

    # ---------------------------------------------------------------- UI
    def _build(self):
        t = theme()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        head = QLabel("Map")
        head.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {t.get('text_secondary')};")
        lay.addWidget(head)

        row = QHBoxLayout()
        row.setSpacing(4)
        self.rank_combo = QComboBox()
        for key, label in RANK_LABELS.items():
            self.rank_combo.addItem(label, key)
        self.rank_combo.setToolTip("What the search box looks for")
        self.rank_combo.currentIndexChanged.connect(self._on_rank_changed)
        row.addWidget(self.rank_combo)
        lay.addLayout(row)

        self.search = QLineEdit()
        self.search.setMinimumHeight(32)
        self.search.setClearButtonEnabled(True)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self.run_search)
        self.search.textChanged.connect(lambda _t: self._timer.start())
        lay.addWidget(self.search)

        self.results_frame = QFrame()
        self.results_frame.setObjectName("mapResults")
        self.results_frame.setStyleSheet(
            f"QFrame#mapResults {{ background-color: {t.get('surface')}; border: 1px solid {t.get('border')};"
            f" border-radius: {t.get('radius_sm')}; }}")
        self.results_layout = QVBoxLayout(self.results_frame)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setSpacing(0)
        self.results_frame.hide()
        lay.addWidget(self.results_frame)

        self.chip_area = QVBoxLayout()
        self.chip_area.setSpacing(4)
        lay.addLayout(self.chip_area)

        foot = QHBoxLayout()
        self.summary = QLabel("Nothing chosen: the map shows every record.")
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 11px;")
        foot.addWidget(self.summary, 1)
        self.clear_btn = QPushButton("Clear all")
        self.clear_btn.setStyleSheet(
            f"QPushButton {{ padding: 4px 8px; border: 1px solid {t.get('border')}; "
            f"border-radius: {t.get('radius_sm')}; font-size: 11px; }}"
            f"QPushButton:hover {{ background-color: {t.get('hover')}; }}")
        self.clear_btn.clicked.connect(self.clear)
        self.clear_btn.hide()
        foot.addWidget(self.clear_btn)
        lay.addLayout(foot)
        self._on_rank_changed()

    def rank(self) -> str:
        return self.rank_combo.currentData() or "species"

    def _on_rank_changed(self, *_a):
        rank = self.rank()
        self.search.setPlaceholderText(
            "Type to filter the groups..." if rank == "group" else
            f"{RANK_LABELS[rank]}: scientific, old or common name...")
        self.run_search()

    # ---------------------------------------------------------------- search
    def run_search(self):
        """Search now (the box waits for a pause in typing)."""
        self._timer.stop()
        text = self.search.text().strip()
        rank = self.rank()
        self._clear_layout(self.results_layout)
        if rank != "group" and len(text) < 2:
            self.results_frame.hide()
            return
        try:
            matches = search_taxa(text, rank, limit=MAX_RESULTS if rank != "group" else 40)
        except Exception as e:                      # a missing uksi.db must not break the tab
            print(f"[MapSelectionBox] search failed: {e}")
            matches = []
        chosen = {self._key(c) for c in self._chips}
        matches = [m for m in matches if self._key(m) not in chosen]
        if not matches:
            self.results_frame.hide()
            return
        for m in matches:
            self.results_layout.addWidget(self._result_item(m))
        self.results_frame.show()

    def results(self) -> List[dict]:
        """The results now offered (for tests and keyboard use)."""
        out = []
        for i in range(self.results_layout.count()):
            w = self.results_layout.itemAt(i).widget()
            if w is not None and hasattr(w, "taxon"):
                out.append(w.taxon)
        return out

    def _result_item(self, m: dict) -> QFrame:
        t = theme()
        item = QFrame()
        item.taxon = m
        item.setObjectName("mapResult")
        item.setStyleSheet(f"QFrame#mapResult {{ border-bottom: 1px solid {t.get('separator')}; }}"
                           f"QFrame#mapResult:hover {{ background-color: {self._light}; }}")
        item.setCursor(Qt.CursorShape.PointingHandCursor)
        row = QHBoxLayout(item)
        row.setContentsMargins(8, 6, 8, 6)
        info = QVBoxLayout()
        name = QLabel(m["scientific_name"] if m["kind"] == "group"
                      else f"<i>{m['scientific_name']}</i>")
        name.setStyleSheet(f"font-weight: 600; color: {t.get('text_primary')};")
        info.addWidget(name)
        sub = []
        if m.get("old_name"):
            sub.append(f"was {m['old_name']}")
        if m.get("common_name"):
            sub.append(m["common_name"])
        if m["kind"] != "group":
            sub.append(m["rank"])
        if sub:
            s = QLabel(" · ".join(sub))
            s.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 11px;")
            info.addWidget(s)
        row.addLayout(info)
        row.addStretch()
        n = QLabel(f"{m['records']:,}")
        n.setToolTip("Records in every source")
        n.setStyleSheet(f"background-color: {t.get('surface_alt')}; padding: 2px 6px; "
                        f"border-radius: {t.get('radius_sm')}; font-size: 11px;")
        row.addWidget(n)
        item.mousePressEvent = lambda e, m=m: self.add(m)
        return item

    # ---------------------------------------------------------------- chips
    @staticmethod
    def _key(c: dict):
        return ("group", c.get("label")) if c.get("kind") == "group" else ("taxon", c.get("tvk"))

    def add(self, taxon: dict):
        """Add a chip (ignored if already chosen) and say the selection changed."""
        if self._key(taxon) in {self._key(c) for c in self._chips}:
            return
        chip = dict(taxon)
        chip["colour"] = (self._saved_colour(chip)
                          or default_taxon_colour([c.get("colour") for c in self._chips]))
        self._chips.append(chip)
        self._counts = None
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.results_frame.hide()
        self._render_chips()
        self.selection_changed.emit(self.selection())

    def remove(self, index: int):
        if 0 <= index < len(self._chips):
            del self._chips[index]
            self._counts = None
            self._render_chips()
            self.selection_changed.emit(self.selection())

    def clear(self):
        if self._chips:
            self._chips = []
            self._counts = None
            self._render_chips()
            self.selection_changed.emit([])

    def selection(self) -> List[dict]:
        return [dict(c) for c in self._chips]

    # ---------------------------------------------------------------- colours
    @classmethod
    def _settings_key(cls, c: dict) -> str:
        kind, value = cls._key(c)
        return f"mapping/taxon_colour/{kind}:{value}"

    def _saved_colour(self, c: dict) -> Optional[str]:
        try:
            v = QSettings().value(self._settings_key(c))
        except Exception:
            return None
        return str(v) if v and QColor(str(v)).isValid() else None

    def colours(self) -> List[str]:
        """Each chip's colour, in chip order."""
        return [c.get("colour") or "" for c in self._chips]

    def set_chip_colour(self, index: int, colour: str):
        """Give a chip a colour (remembered for that taxon) and say so."""
        if not (0 <= index < len(self._chips)) or not QColor(colour).isValid():
            return
        colour = QColor(colour).name()
        self._chips[index]["colour"] = colour
        try:
            QSettings().setValue(self._settings_key(self._chips[index]), colour)
        except Exception as e:
            print(f"[MapSelectionBox] colour not saved: {e}")
        self._render_chips()
        self.colours_changed.emit()

    def choose_colour(self, index: int):
        """The swatch was clicked: pick a colour for that chip."""
        if not (0 <= index < len(self._chips)):
            return
        c = self._chips[index]
        col = QColorDialog.getColor(QColor(c.get("colour") or "#0072B2"), self,
                                    f"Colour for {c.get('scientific_name', '')}")
        if col.isValid():
            self.set_chip_colour(index, col.name())

    def set_counts(self, counts: Optional[List[int]]):
        """The mapped records per chip, after a map is generated (None = not yet mapped)."""
        self._counts = list(counts) if counts is not None else None
        self._render_chips()

    def chip_texts(self) -> List[str]:
        """What each chip says (for tests)."""
        return [self._chip_text(i, c) for i, c in enumerate(self._chips)]

    def _chip_text(self, i: int, c: dict) -> str:
        name = c["scientific_name"] if c.get("kind") == "group" else f"<i>{c['scientific_name']}</i>"
        rank = "group" if c.get("kind") == "group" else (c.get("rank") or "").lower()
        if self._counts is not None and i < len(self._counts):
            n = self._counts[i]
            count = f"{n:,} record{'s' if n != 1 else ''} mapped"
        else:
            count = f"{c.get('records', 0):,} in all sources"
        return f"{name} <span style='font-size:10px'>({rank}) · {count}</span>"

    def _render_chips(self):
        t = theme()
        self._clear_layout(self.chip_area)
        for i, c in enumerate(self._chips):
            chip = QFrame()
            chip.setObjectName("mapChip")
            chip.setStyleSheet(f"QFrame#mapChip {{ background-color: {self._light}; border: 1px solid "
                               f"{self._accent}; border-radius: {t.get('radius_md')}; }}")
            row = QHBoxLayout(chip)
            row.setContentsMargins(6, 4, 4, 4)
            sw = QPushButton()
            sw.setObjectName("chipSwatch")
            sw.setFixedSize(16, 16)
            sw.setCursor(Qt.CursorShape.PointingHandCursor)
            sw.setToolTip("This taxon's colour on the map (By taxon style). Click to change it.")
            sw.setStyleSheet(f"QPushButton#chipSwatch {{ background-color: {c.get('colour')}; "
                             f"border: 1px solid {t.get('border_strong')}; border-radius: 3px; }}")
            sw.clicked.connect(lambda _c=False, i=i: self.choose_colour(i))
            row.addWidget(sw)
            label = QLabel(self._chip_text(i, c))
            label.setWordWrap(True)
            label.setStyleSheet(f"border: none; color: {self._dark};")
            row.addWidget(label, 1)
            x = QPushButton("✕")
            x.setFixedSize(20, 20)
            x.setToolTip("Remove from the map")
            x.setStyleSheet(f"border: none; color: {t.get('text_secondary')};")
            x.clicked.connect(lambda _c=False, i=i: self.remove(i))
            row.addWidget(x)
            self.chip_area.addWidget(chip)
        n = len(self._chips)
        self.clear_btn.setVisible(n > 1)
        self.summary.setText("Nothing chosen: the map shows every record." if not n else
                             "" if n == 1 else f"{n} chosen: the map shows all their records.")
        self.summary.setVisible(n != 1)

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().hide()          # gone now, not at the next event loop
                item.widget().deleteLater()
