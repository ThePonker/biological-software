"""The drop-down of a quick filter bar's Species box (F69, 13 Oct 2026).

The Species boxes on Observation Data, the Recording Scheme and Contributed filtered on
typed text ("rut mac" worked) but their plain QCompleter matched "contains" only, so no
list opened to pick the full name from. They now carry the Filter Wizard's SpeciesCompleter
(filter_wizard/fuzzy.py: the shared species search, group choices "All Cerambycidae
(longhorn beetles) — group") drawn by the suite's shared list painter, scoped to the
species in that tab's data. Picking a row puts its text in the box, and the box filters on
that as it did on typed text (shared/species_filter understands a group label: F68).

    completer = attach_species_completer(self.species_edit)
    completer.set_items(*species_items(rows))     # rows: (scientific_name, common_name)
"""
from typing import Dict, Iterable, List, Optional, Tuple

from PySide6.QtWidgets import QCompleter, QLineEdit

from ...themes import theme
from .filter_wizard.fuzzy import SpeciesCompleter

MAX_VISIBLE = 10


def species_items(rows: Iterable[Tuple[Optional[str], Optional[str]]]
                  ) -> Tuple[List[str], Dict[str, str]]:
    """(display texts, {display: scientific name}) from (scientific, common) pairs, as the
    What dialog shows them: "Common Name (Scientific name)", or the scientific name alone.
    A species met under several common names is listed once per name; blanks are dropped."""
    items: List[str] = []
    names: Dict[str, str] = {}
    for sci, common in rows:
        sci = (sci or "").strip()
        if not sci:
            continue
        common = (common or "").strip()
        display = f"{common} ({sci})" if common and common.lower() != sci.lower() else sci
        if display not in names:
            items.append(display)
            names[display] = sci
    return items, names


class QuickBarSpeciesCompleter(SpeciesCompleter):
    """SpeciesCompleter whose pick puts the FILTER text in the box: the scientific name
    of a species row (the list shows "Western Honey Bee (Apis mellifera)", but the box
    filters on its text, and shared/species_filter finds no record for the whole label:
    review 13 Oct 2026), or a group row's label as it is (the filter understands it, F68)."""

    def pathFromIndex(self, index) -> str:
        display = super().pathFromIndex(index)
        if not display or self.is_group(display):
            return display
        return self.scientific_name(display)


def attach_species_completer(edit: QLineEdit, items: Iterable[str] = (),
                             names: Optional[Dict[str, str]] = None) -> SpeciesCompleter:
    """Give a filter bar's Species box the shared species drop-down (empty until
    set_items). Typing keeps filtering as before; a picked row fills the box with the
    species' scientific name (or a group's label)."""
    completer = QuickBarSpeciesCompleter(list(items), edit, names=names,
                                         secondary=theme().get("text_secondary"))
    completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
    completer.setMaxVisibleItems(MAX_VISIBLE)
    edit.setCompleter(completer)
    return completer


__all__ = ["QuickBarSpeciesCompleter", "attach_species_completer", "species_items", "MAX_VISIBLE"]
