"""Fuzzy multi-word matching for the Filter Wizard's text boxes (backlog I9, 9 Oct 2026).

One copy of what what/who/where_filter_dialog.py each carried: every space-separated word
must appear in the item ("rut mac" -> "Rutpela maculata"). The Where dialog's place names
also accept common abbreviations (Sth Fen Wd -> South Fen Wood).
"""
from typing import List

from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtWidgets import QCompleter


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
