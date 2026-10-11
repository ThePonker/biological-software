"""Close spellings in the import wizards (Wil's decision 3, 10 Oct 2026). No Qt.

    close_spelling(uksi, bare) -> Taxon | None

The three import wizards accept a name not found exactly ONLY when it is a close spelling of
one species in the SAME genus:
  * two or more words, the first (the genus) written exactly as UKSI has it (any case);
  * the rest one or two letters out (a swap of neighbouring letters counts as one), with the
    same tolerance as the shared species search: 0 slips under 4 letters, 1 for 4-7,
    2 for 8 or more (shared/fuzzy_words.allowed_edits);
  * exactly ONE species-level UKSI name within that distance (two near names -> pick list);
  * that name not held twice in a way that needs a choice (species_lookup._choose).

Anything looser -- a misspelt genus ("Rutpla maculata"), a genus-only name ("Clytus", "Ab"),
two candidates -- is not accepted: it stays an error with suggestions, for the pick list.
'Rutpela maculta' -> Rutpela maculata; 'Rhagium mordx' -> Rhagium mordax.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .fuzzy_words import allowed_edits, osa_distance
from .species_lookup import Taxon, _choose, _rows, _SPECIES_RANKS, _taxon, _taxon_select, tidy

CLOSE_SPELLING = "Close spelling"


def close_spelling(uksi, bare: str) -> Optional[Taxon]:
    """The one species-level taxon that `bare` is a close spelling of (same genus), else None."""
    words = tidy(bare).split()
    if len(words) < 2:
        return None
    genus, rest = words[0], " ".join(words[1:]).lower()
    limit = allowed_edits(rest.replace(" ", ""))
    if limit == 0:
        return None
    sel = _taxon_select(uksi).format(key="t.scientific_name", src="taxa t")
    ph = ",".join("?" * len(_SPECIES_RANKS))
    found: Dict[str, List[Taxon]] = {}
    g = genus.lower()       # a range on LOWER(name), so idx_taxa_scientific_lower is used
    for r in _rows(uksi, sel + "WHERE LOWER(t.scientific_name) >= ? AND LOWER(t.scientific_name) < ? "
                   f"AND t.rank IN ({ph})", (f"{g} ", f"{g}!", *_SPECIES_RANKS)):
        t = _taxon(r)
        name = (t.scientific_name or "").lower()
        parts = name.split()
        if not parts or parts[0] != genus.lower() or len(parts) != len(words):
            continue
        lst = found.setdefault(name, [])
        if all(x.tvk != t.tvk for x in lst):
            lst.append(t)
    near = [n for n in found if osa_distance(rest, n.split(" ", 1)[1], limit) <= limit]
    if len(near) != 1:
        return None
    t, _note = _choose(found[near[0]])
    return t


def close_spelling_warning(typed: str, matched: str) -> str:
    return f"{CLOSE_SPELLING}: '{typed}' matched to '{matched}'"


__all__ = ["close_spelling", "close_spelling_warning", "CLOSE_SPELLING"]
