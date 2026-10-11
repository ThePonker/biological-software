"""
Dataset / provider picker for the Filter Wizard's Status card (Recording Scheme).

Decision 4 (10 Oct): the scheme bar's Source stays the import route (iRecord / NBN
Atlas / Other); this picker chooses where scheme records came from -- the NBN Atlas
data provider's dataset or the iRecord survey (stored in recording_scheme.source).
There are a few hundred, so it is a searchable tick list showing "<dataset> (n)".
The wizard key is 'dataset' (services/filter_builder.py).

Sub-surveys (decision 7, 11 Oct): a dataset whose name is another's plus " | <survey>"
("iRecord | iRecord App | Bayfordbury" under "iRecord | iRecord App") is listed indented
under it. Ticking the parent ticks all its sub-surveys; any of them can then be unticked,
and the parent shows a part-filled box while some are unticked (its own records stay
chosen). Unticking the parent unticks them all. A sub-survey can still be ticked alone.
The filter is still the plain list of ticked names, so the counts are the sums of the
ticked rows.
"""

from typing import Dict, Iterable, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from ....themes import theme

SEP = " | "
_INDENT = "\u2003\u2003"          # two em spaces per level
_ROLE_PARENT = Qt.ItemDataRole.UserRole + 1


def dataset_tree(names: Iterable[str]) -> Tuple[List[Tuple[str, int]], Dict[str, Optional[str]]]:
    """([(name, depth)] in display order, {name: parent or None}).

    A name's parent is the longest OTHER listed name it starts with followed by " | ".
    Roots and each parent's children are in name order (ignoring case)."""
    names = list(dict.fromkeys(names))
    present = set(names)
    parent: Dict[str, Optional[str]] = {}
    for n in names:
        parts = n.split(SEP)
        parent[n] = next((SEP.join(parts[:i]) for i in range(len(parts) - 1, 0, -1)
                          if SEP.join(parts[:i]) in present), None)
    kids: Dict[Optional[str], List[str]] = {}
    for n in names:
        kids.setdefault(parent[n], []).append(n)
    order: List[Tuple[str, int]] = []

    def walk(p, depth):
        for n in sorted(kids.get(p, []), key=lambda v: (v.casefold(), v)):
            order.append((n, depth))
            walk(n, depth + 1)
    walk(None, 0)
    return order, parent


class DatasetPicker(QWidget):
    """Search box + tick list of datasets with their record counts."""

    def __init__(self, datasets: Iterable[Tuple[str, int]], accent_color: str, parent=None):
        super().__init__(parent)
        self._accent = accent_color
        self.setStyleSheet("background: transparent;")
        t = theme()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        label = QLabel("Dataset / provider")
        label.setStyleSheet(f"font-weight: 600; color: {t.get('text_primary')}; "
                            "font-size: 13px; background: transparent;")
        layout.addWidget(label)

        hint = QLabel("Where the records came from: the NBN Atlas dataset or the iRecord survey. "
                      "Tick one or more (any of them). Ticking a dataset also ticks its "
                      "sub-surveys (listed under it); untick any you don't want.")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 11px; background: transparent;")
        layout.addWidget(hint)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Type to narrow the list...")
        self.search.setClearButtonEnabled(True)
        self.search.setStyleSheet(f"""
            QLineEdit {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: 4px;
                padding: 6px 10px;
                color: {t.get('text_primary')};
            }}
            QLineEdit:focus {{ border-color: {accent_color}; }}
        """)
        self.search.textChanged.connect(self._narrow)
        layout.addWidget(self.search)

        self.list = QListWidget()
        self.list.setMinimumHeight(200)
        self.list.setStyleSheet(f"""
            QListWidget {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: 4px;
                color: {t.get('text_primary')};
            }}
        """)
        counts = dict(datasets)
        order, self._parent = dataset_tree(counts)
        self._children: Dict[str, List[str]] = {}
        for name, _depth in order:
            if self._parent[name] is not None:
                self._children.setdefault(self._parent[name], []).append(name)
        self._item: Dict[str, QListWidgetItem] = {}
        for name, depth in order:
            shown = name[len(self._parent[name]) + len(SEP):] if self._parent[name] else name
            item = QListWidgetItem(f"{_INDENT * depth}{shown} ({counts[name]:,})")
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setData(_ROLE_PARENT, self._parent[name])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            if self._children.get(name) is not None or self._parent[name]:
                item.setToolTip(name)
            self.list.addItem(item)
            self._item[name] = item
        self._busy = False
        self.list.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.list)

    def _items(self):
        return [self.list.item(i) for i in range(self.list.count())]

    # -- parents and sub-surveys -----------------------------------------------------
    def _descendants(self, name: str) -> List[str]:
        out = []
        for c in self._children.get(name, []):
            out.append(c)
            out += self._descendants(c)
        return out

    def _refresh_ancestors(self, name: str):
        """A ticked (or part-filled) parent: full when every sub-survey is ticked, else part."""
        p = self._parent.get(name)
        while p is not None:
            item = self._item[p]
            if item.checkState() != Qt.CheckState.Unchecked:
                full = all(self._item[d].checkState() == Qt.CheckState.Checked
                           for d in self._descendants(p))
                item.setCheckState(Qt.CheckState.Checked if full
                                   else Qt.CheckState.PartiallyChecked)
            p = self._parent.get(p)

    def _on_item_changed(self, item: QListWidgetItem):
        if self._busy:
            return
        self._busy = True
        try:
            name = str(item.data(Qt.ItemDataRole.UserRole))
            state = item.checkState()
            if state != Qt.CheckState.PartiallyChecked:       # a click: the subtree follows
                for d in self._descendants(name):
                    self._item[d].setCheckState(state)
            self._refresh_ancestors(name)
        finally:
            self._busy = False

    def _narrow(self, text: str):
        needle = text.strip().casefold()
        shown = set()
        for name, item in self._item.items():
            # ticked rows stay visible so a choice is never hidden by the search
            if not needle or needle in name.casefold() or \
                    item.checkState() != Qt.CheckState.Unchecked:
                shown.add(name)
                p = self._parent.get(name)
                while p is not None:                          # keep a match's parents
                    shown.add(p)
                    p = self._parent.get(p)
        for name, item in self._item.items():
            item.setHidden(name not in shown)

    def set_selected(self, names: Iterable[str]):
        """Tick exactly these (case ignored); a ticked parent with any sub-survey not in
        the list shows part-filled."""
        wanted = {str(n).casefold() for n in names or []}
        self._busy = True
        try:
            for name, item in self._item.items():
                item.setCheckState(Qt.CheckState.Checked if name.casefold() in wanted
                                   else Qt.CheckState.Unchecked)
            for name, item in self._item.items():
                if self._children.get(name) and item.checkState() == Qt.CheckState.Checked and \
                        any(self._item[d].checkState() != Qt.CheckState.Checked
                            for d in self._descendants(name)):
                    item.setCheckState(Qt.CheckState.PartiallyChecked)
        finally:
            self._busy = False

    def selected(self) -> List[str]:
        """The datasets whose records are chosen: ticked and part-filled rows, in name
        order (the filter's value)."""
        return sorted((name for name, item in self._item.items()
                       if item.checkState() != Qt.CheckState.Unchecked),
                      key=lambda v: (v.casefold(), v))

    def clear(self):
        self.search.clear()
        self.set_selected([])
