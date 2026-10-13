"""Fuzzy multi-word matching for the Filter Wizard's text boxes (backlog I9, 9 Oct 2026).

One copy of what what/who/where_filter_dialog.py each carried: every space-separated word
must appear in the item ("rut mac" -> "Rutpela maculata"). The Where dialog's place names
also accept common abbreviations (Sth Fen Wd -> South Fen Wood). Species lists also go
through the suite's shared species search (SpeciesCompleter, 10 Oct 2026).
"""
from typing import Dict, List, Optional

from PySide6.QtCore import QEvent, Qt, QSortFilterProxyModel
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtWidgets import QCompleter

from shared.species_list_delegate import HIT_ROLE, SpeciesListDelegate


class FuzzyFilterProxyModel(QSortFilterProxyModel):
    """Proxy model that filters by matching ALL space-separated words."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filter_words = []
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def setFilterText(self, text: str):
        # Qt 6.10 deprecates invalidateFilter() in favour of begin/endFilterChange()
        if hasattr(self, "beginFilterChange"):
            self.beginFilterChange()
            self._filter_words = text.lower().split()
            self.endFilterChange()
        else:
            self._filter_words = text.lower().split()
            self.invalidateFilter()

    def _word_matches(self, word: str, text_lower: str) -> bool:
        return word in text_lower

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        if not self._filter_words:
            return True
        index = self.sourceModel().index(source_row, 0, source_parent)
        text = self.sourceModel().data(index, Qt.ItemDataRole.DisplayRole)
        if not text:
            return False
        text_lower = text.lower()
        return all(self._word_matches(word, text_lower) for word in self._filter_words)


class PlaceFilterProxyModel(FuzzyFilterProxyModel):
    """As FuzzyFilterProxyModel, and each word may also match a common place-name abbreviation."""

    ABBREVIATIONS = {
        'south': ['sth', 's'],
        'sth': ['south', 's'],
        'north': ['nth', 'n'],
        'nth': ['north', 'n'],
        'east': ['e', 'est'],
        'west': ['w', 'wst'],
        'fen': ['fn'],
        'fn': ['fen'],
        'wood': ['wd', 'wds'],
        'wd': ['wood'],
        'woods': ['wds', 'wd'],
        'wds': ['woods', 'wood'],
        'field': ['fld', 'flds'],
        'fld': ['field'],
        'fields': ['flds', 'fld'],
        'farm': ['fm'],
        'fm': ['farm'],
        'lane': ['ln'],
        'ln': ['lane'],
        'road': ['rd'],
        'rd': ['road'],
        'meadow': ['mdw', 'mead'],
        'mdw': ['meadow'],
        'reserve': ['res', 'rsv'],
        'res': ['reserve'],
        'nature': ['nat'],
        'nat': ['nature'],
        'green': ['grn'],
        'grn': ['green'],
        'great': ['gt', 'grt'],
        'gt': ['great'],
        'little': ['lt', 'ltl'],
        'lt': ['little'],
        'saint': ['st'],
        'st': ['saint', 'street'],
        'street': ['st'],
    }

    def _word_matches(self, word: str, text_lower: str) -> bool:
        if word in text_lower:
            return True
        return any(v in text_lower for v in self.ABBREVIATIONS.get(word, []))


class SpeciesFilterProxyModel(FuzzyFilterProxyModel):
    """As FuzzyFilterProxyModel, and a row also shows when its species is one the shared
    species search (shared/species_filter.py) finds for the text: typing slips
    ("Rhagium mordx"), old names, UKSI common names the records don't carry."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.names: Dict[str, str] = {}      # display text -> scientific name
        self._allowed = set()
        self.groups: List[tuple] = []        # [(group label, scientific name, first)]

    def setFilterText(self, text: str):
        # Wil's decision 2 (10 Oct): a common word naming a whole group ("longhorn") lists
        # the species it names and the group as ONE labelled choice (SpeciesCompleter adds
        # it: at the top when the text is the group's name, F49) -- not every species of
        # the group mixed in with them.
        self._allowed = set()
        self.groups = []
        if text and text.strip():
            try:
                from shared.species_filter import completer_choices
                self._allowed, self.groups = completer_choices(text, set(self.names.values()))
            except Exception as e:
                print(f"[SpeciesCompleter] shared search unavailable: {e}")
        super().setFilterText(text)

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        index = self.sourceModel().index(source_row, 0, source_parent)
        text = self.sourceModel().data(index, Qt.ItemDataRole.DisplayRole) or ""
        if any(text == g[0] for g in self.groups):
            return True
        if super().filterAcceptsRow(source_row, source_parent):
            return True
        return self.names.get(text, text) in self._allowed


class FuzzyCompleter(QCompleter):
    """Completer with fuzzy multi-word matching."""

    proxy_class = FuzzyFilterProxyModel

    def __init__(self, items: List[str], parent=None):
        self._source_model = QStandardItemModel(parent)
        for item in items:
            self._source_model.appendRow(QStandardItem(item))
        self._proxy_model = self.proxy_class(parent)
        self._proxy_model.setSourceModel(self._source_model)
        super().__init__(self._proxy_model, parent)
        self.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setMaxVisibleItems(10)

    def splitPath(self, path: str) -> List[str]:
        # The proxy does the matching. Hand QCompleter an empty path so it shows every row the
        # proxy lets through -- returning the typed text made QCompleter re-filter by plain
        # prefix, which hid "rut mac" -> Rutpela maculata and any mid-name match (fixed 9 Oct).
        self._proxy_model.setFilterText(path)
        return [""]

    def pathFromIndex(self, index) -> str:
        source_index = self._proxy_model.mapToSource(index)
        return self._source_model.data(source_index, Qt.ItemDataRole.DisplayRole)


def picking_from_popup(line_edit) -> bool:
    """True while Return is choosing a highlighted item in the box's completer popup.

    Qt delivers that Return to the box (returnPressed, with the half-typed text) before the
    completer's activated signal, so an Enter handler that saw "rut mac" would add a chip for
    the half-typed text as well as the chosen name. Enter handlers return early when this is
    True and leave the choice to the activated handler.
    """
    c = line_edit.completer() if line_edit is not None else None
    if c is None:
        return False
    popup = c.popup()
    return bool(popup is not None and popup.isVisible() and popup.currentIndex().isValid())


class PlaceCompleter(FuzzyCompleter):
    """FuzzyCompleter for place names (abbreviations understood)."""
    proxy_class = PlaceFilterProxyModel


def _species_item(display: str, scientific: str) -> QStandardItem:
    """A list row drawn by the shared painter: the scientific name in italics, the common
    name (the rest of a "Common (Scientific)" entry) after it in the secondary colour."""
    item = QStandardItem(display)
    common = display.replace(f"({scientific})", "").strip() if display != scientific else ""
    item.setData({"scientific": scientific, "group_of": scientific, "common": common}, HIT_ROLE)
    return item


def _group_item(label: str, scientific: str) -> QStandardItem:
    item = QStandardItem(label)
    item.setData({"group_label": label, "group_of": scientific, "scientific": scientific}, HIT_ROLE)
    return item


class SpeciesCompleter(FuzzyCompleter):
    """FuzzyCompleter for a list of species ("Common (Scientific)" or "Scientific"), matched
    with the shared species search as well. names: display text -> scientific name.

    The rows are drawn by the suite's shared species list painter
    (shared/species_list_delegate.py) when `secondary` (the colour of common names) is
    given, as Quick Entry's box is (F69, 13 Oct 2026); set_items() replaces the list when
    a tab's data changes (the quick filter bars)."""
    proxy_class = SpeciesFilterProxyModel

    def __init__(self, items: List[str], parent=None, names: Optional[Dict[str, str]] = None,
                 secondary: Optional[str] = None):
        super().__init__([], parent)
        self._group_rows = (0, 0)            # group choices added (at the top, at the end)
        self._group_names: Dict[str, str] = {}   # every group label offered -> its taxon
        self._secondary = secondary
        self._painted = False
        self.set_items(items, names)

    def _ensure_painter(self):
        """Give the pop-up list the shared painter, the first time it is about to open.
        QCompleter makes its pop-up (a top-level window) only when needed; making it in
        __init__ left one for every filter bar built, shown or not."""
        if self._secondary is not None and not self._painted:
            self._painted = True
            self.popup().setItemDelegate(
                SpeciesListDelegate(self.popup(), secondary=self._secondary))

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress and obj is self.widget():
            self._ensure_painter()
        return super().eventFilter(obj, event)

    def set_items(self, items: List[str], names: Optional[Dict[str, str]] = None):
        """Replace the species offered (display texts; names: display -> scientific)."""
        names = dict(names or {i: i for i in items})
        self._proxy_model.names = names
        self._source_model.removeRows(0, self._source_model.rowCount())
        self._group_rows = (0, 0)
        for display in items:
            self._source_model.appendRow(_species_item(display, names.get(display, display)))

    def splitPath(self, path: str) -> List[str]:
        """As FuzzyCompleter, and the whole groups the text names are added, labelled
        "All Cerambycidae (longhorn beetles) \u2014 group" (decision 2): at the TOP of the
        list when the text is the group's name ("longhorn"), else at the end (F49)."""
        top, end = self._group_rows
        if end:
            self._source_model.removeRows(self._source_model.rowCount() - end, end)
        if top:
            self._source_model.removeRows(0, top)
        self._group_rows = (0, 0)
        out = super().splitPath(path)
        groups = self._proxy_model.groups
        first = [g for g in groups if len(g) > 2 and g[2]]
        later = [g for g in groups if g not in first]
        for k, g in enumerate(first):
            self._source_model.insertRow(k, _group_item(g[0], g[1]))
        for g in later:
            self._source_model.appendRow(_group_item(g[0], g[1]))
        for g in groups:
            self._group_names[g[0]] = g[1]
        self._group_rows = (len(first), len(later))
        return out

    def is_group(self, display: str) -> bool:
        """Is this list entry a group choice ("All Cerambycidae (...) \u2014 group")?"""
        return display in self._group_names

    def scientific_name(self, display: str) -> str:
        """The scientific name behind a list entry: a species, or a group choice's taxon."""
        if display in self._group_names:
            return self._group_names[display]
        return self._proxy_model.names.get(display, display)
