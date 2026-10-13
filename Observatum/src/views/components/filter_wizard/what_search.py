"""The What dialog's one search box (Round 11, 13 Oct 2026, backlog 17).

The dialog had four boxes -- Species, Taxon group, Order, Family -- and since Round 10 the
Species box also offered whole groups, so they overlapped. Now one box finds everything and
one list shows, in this order:

  1. whole groups the text names: a common word ("ladybird" -> "All Coccinellidae
     (ladybirds) — group", the shared species search's group choices, F49/F68) and the
     tab's orders and families whose name starts with the text ("Ceramb" -> Cerambycidae);
  2. taxon groups (shared/taxon_groups.py display labels, also found by their iRecord
     value: "insect - butterfly" -> Butterflies (Lepidoptera));
  3. species (the tab's own names, matched with the shared species search as before);
  4. other groups (a word inside a group's common name), and orders / families with the
     text inside their name.

Every row is drawn by the shared painter (shared/species_list_delegate.py): scientific name
in italics, common name in the secondary colour, then family and rank small and grey.

A pick becomes a chip under the SAME key the old boxes used, so saved filters, the tab's
chip summary and the filter builder are unchanged:
  species      a species name, or a group label (filtered by TVK, F68)
  group        a taxon group display label          ("Taxon group: ...")
  taxon_group  an order (the old key's name)        ("Order: ...")
  family       a family                             ("Family: ...")
A value starting "~" is a contains-match (SRCH13), shown as *text*.
"""
from typing import Dict, Iterable, List, NamedTuple, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QCompleter

from shared.species_list_delegate import HIT_ROLE, SpeciesListDelegate
from shared.species_search import parse_group_label

from .chip_values import PARTIAL, chip_label

KEY_LABELS = {"species": "Species", "group": "Taxon group",
              "taxon_group": "Order", "family": "Family"}
GROUP_TAG = " — group"


class Choice(NamedTuple):
    key: str          # the filters key (see the module docstring)
    value: str        # the chip's value
    chip: str         # the chip's text: "Family: All Coccinellidae (ladybirds)"
    display: str      # the row's text (what the box shows while the row is highlighted)
    hit: dict         # the row's parts, for the shared painter


def _fold(text) -> str:
    return " ".join(str(text or "").casefold().split())


def _uksi():
    """The shared species index (None when uksi.db can't be read)."""
    try:
        from shared.species_search import get_index
        return get_index()
    except Exception as e:
        print(f"[WhatSearch] species index unavailable: {e}")
        return None


class WhatChoices:
    """What the one box offers for a text, and what a typed or stored value means."""

    def __init__(self, species: Iterable[str] = (), orders: Iterable[str] = (),
                 families: Iterable[str] = (), groups: Iterable[str] = (),
                 species_info: Optional[Dict[str, dict]] = None):
        self.species = [s for s in dict.fromkeys(species or ()) if s]
        self.orders = [o for o in dict.fromkeys(orders or ()) if o]
        self.families = [f for f in dict.fromkeys(families or ()) if f]
        self.groups = [g for g in dict.fromkeys(groups or ()) if g]
        self._info = {k: dict(v) for k, v in (species_info or {}).items()}
        self._idx = _uksi()
        self._taxon_cache: Dict[str, dict] = {}
        self._raw = {g: self._raw_values(g) for g in self.groups}
        self._species_text = {s: _fold(f"{s} {self.info(s).get('common', '')}")
                              for s in self.species}

    # ------------------------------------------------------------ what a name is

    def _taxon(self, name: str) -> dict:
        """UKSI's common name, rank, family and order for a scientific name ({} if unknown)."""
        if name in self._taxon_cache:
            return self._taxon_cache[name]
        out = {}
        idx = self._idx
        if idx is not None and name:
            try:
                tvk = idx.tvk_for_name(name)
                i = idx.pos.get(tvk) if tvk else None
                if i is not None:
                    out = {"common": idx.common[i] or "", "rank": idx.rank[i] or "",
                           "family": idx.family[i] or "", "order": idx.order[i] or ""}
            except Exception as e:
                print(f"[WhatSearch] no taxonomy for {name}: {e}")
        self._taxon_cache[name] = out
        return out

    def info(self, species: str) -> dict:
        """A species' common name, family and rank: the tab's records first, else UKSI."""
        mine = self._info.get(species, {})
        if mine.get("common") and mine.get("family") and mine.get("rank"):
            return mine
        uksi = self._taxon(species)
        merged = {k: mine.get(k) or uksi.get(k, "") for k in ("common", "family", "rank")}
        self._info[species] = merged
        return merged

    @staticmethod
    def _raw_values(label: str) -> List[str]:
        """The iRecord taxon_group values a display label stands for ("insect - butterfly")."""
        try:
            from shared.taxon_groups import group_values
            return [v for v in group_values(label) if v != label]
        except Exception:
            return []

    # ------------------------------------------------------------ one choice

    def species_choice(self, name: str) -> Choice:
        info = self.info(name)
        rank = info.get("rank", "")
        hit = {"scientific": name, "group_of": name, "common": info.get("common", ""),
               "family": info.get("family", ""),
               "rank": "" if rank in ("", "Species") else rank}
        common = f" ({hit['common']})" if hit["common"] else ""
        return Choice("species", name, f"Species: {name}{common}", name, hit)

    def group_choice(self, label: str, scientific: str = "") -> Choice:
        """A whole group by TVK ("All Coccinellidae (ladybirds) — group"); the chip says
        its rank: "Family: All Coccinellidae (ladybirds)"."""
        scientific = scientific or parse_group_label(label) or ""
        rank = self._taxon(scientific).get("rank", "") if scientific else ""
        short = label[:-len(GROUP_TAG)] if label.endswith(GROUP_TAG) else label
        hit = {"group_label": label, "group_of": scientific, "scientific": scientific,
               "rank": rank}
        return Choice("species", label, f"{rank or 'Group'}: {short}", label, hit)

    def rank_choice(self, key: str, name: str) -> Choice:
        """An order (key taxon_group) or family (key family) from the tab's own list."""
        taxon = self._taxon(name)
        rank = KEY_LABELS[key]
        hit = {"scientific": name, "group_of": name, "common": taxon.get("common", ""),
               "family": taxon.get("order", "") if key == "family" else "", "rank": rank}
        return Choice(key, name, f"{rank}: {name}", f"{name} — {rank.lower()}", hit)

    def taxon_group_choice(self, label: str) -> Choice:
        hit = {"scientific": label, "plain": True, "common": ", ".join(self._raw.get(label, ())),
               "rank": "taxon group"}
        return Choice("group", label, f"Taxon group: {label}", f"{label} — taxon group", hit)

    def for_value(self, key: str, value: str) -> Choice:
        """The chip for a value already in the filters (an older saved filter, a reopened
        dialog): the same text a pick would have given."""
        value = str(value)
        if value.startswith(PARTIAL):
            return Choice(key, value, f"{KEY_LABELS.get(key, key)}: {chip_label(value)}",
                          value, {})
        if key == "species":
            if parse_group_label(value):
                return self.group_choice(value)
            return self.species_choice(value)
        if key == "group":
            return self.taxon_group_choice(value)
        if key in ("taxon_group", "family"):
            return self.rank_choice(key, value)
        return Choice(key, value, f"{key}: {value}", value, {})

    # ------------------------------------------------------------ the list

    def rows(self, text: str) -> List[Choice]:
        """Everything the text finds, in the order the list shows it."""
        words = _fold(text).split()
        if not words:
            return []
        folded = " ".join(words)
        allowed, found_groups = self._shared_search(text)

        def all_words(hay: str) -> bool:
            return all(w in hay for w in words)

        named, inner = [], []
        for key, names in (("taxon_group", self.orders), ("family", self.families)):
            for n in names:
                low = n.casefold()
                if low.startswith(folded):
                    named.append(self.rank_choice(key, n))
                elif all_words(low):
                    inner.append(self.rank_choice(key, n))
        first = [self.group_choice(g[0], g[1]) for g in found_groups if len(g) > 2 and g[2]]
        later = [self.group_choice(g[0], g[1]) for g in found_groups
                 if not (len(g) > 2 and g[2])]
        tgroups = [self.taxon_group_choice(g) for g in self.groups
                   if all_words(_fold(" ".join([g] + self._raw.get(g, []))))]

        def species_order(name: str):
            hay = self._species_text[name]
            common = _fold(self.info(name).get("common", ""))
            starts = hay.startswith(folded) or common.startswith(folded)
            return (0 if starts else 1 if all_words(hay) else 2, name.casefold())

        species = [s for s in self.species if all_words(self._species_text[s]) or s in allowed]
        species.sort(key=species_order)
        return (first + named + tgroups + [self.species_choice(s) for s in species]
                + later + inner)

    def _shared_search(self, text: str):
        """(species names the shared search finds, [(group label, taxon, first)])."""
        try:
            from shared.species_filter import completer_choices
            return completer_choices(text, self.species)
        except Exception as e:
            print(f"[WhatSearch] shared search unavailable: {e}")
            return set(), []

    def typed(self, text: str) -> Optional[Choice]:
        """Enter without a pick: a value the text names exactly (a species, its common name,
        an order, a family, a taxon group or its iRecord value), else the list's top row,
        else a contains-match on the species name (*text*)."""
        text = (text or "").strip()
        if not text:
            return None
        folded = _fold(text)
        if parse_group_label(text):
            return self.group_choice(text)
        for s in self.species:
            if s.casefold() == folded:
                return self.species_choice(s)
        for key, names in (("taxon_group", self.orders), ("family", self.families)):
            for n in names:
                if n.casefold() == folded:
                    return self.rank_choice(key, n)
        for g in self.groups:
            if folded in (_fold(v) for v in [g] + self._raw.get(g, [])):
                return self.taxon_group_choice(g)
        commons = [s for s in self.species if _fold(self.info(s).get("common")) == folded]
        if len(commons) == 1:
            return self.species_choice(commons[0])
        rows = self.rows(text)
        if rows:
            return rows[0]
        return Choice("species", PARTIAL + text, f"Species: *{text}*", text, {})


class WhatCompleter(QCompleter):
    """The one box's drop-down: WhatChoices.rows() for the typed text, drawn by the shared
    painter. choice(display) gives the Choice behind a row's text."""

    def __init__(self, choices: WhatChoices, parent=None, secondary: Optional[str] = None):
        self._model = QStandardItemModel(parent)
        super().__init__(self._model, parent)
        self.choices = choices
        self._shown: Dict[str, Choice] = {}
        self.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setMaxVisibleItems(12)
        self.popup().setItemDelegate(SpeciesListDelegate(self.popup(), secondary=secondary))
        # rows differ (a group row, a species row): each takes its own height from its fonts
        self.popup().setUniformItemSizes(False)

    def splitPath(self, path: str) -> List[str]:
        # The rows are chosen here; QCompleter is handed an empty path so it shows them all
        # (as FuzzyCompleter does, fixed 9 Oct).
        self._model.removeRows(0, self._model.rowCount())
        self._shown = {}
        for c in self.choices.rows(path):
            if c.display in self._shown:
                continue
            self._shown[c.display] = c
            item = QStandardItem(c.display)
            item.setData(c.hit, HIT_ROLE)
            self._model.appendRow(item)
        return [""]

    def pathFromIndex(self, index) -> str:
        return index.data(Qt.ItemDataRole.DisplayRole) or ""

    def choice(self, display: str) -> Optional[Choice]:
        return self._shown.get(display)


__all__ = ["WhatChoices", "WhatCompleter", "Choice", "KEY_LABELS"]
