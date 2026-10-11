"""record_match -- the comparison rules for "is this the same find?" (moved here 11 Oct 2026).

One home for the small rules the specimen-observation link uses, so the read-only report
scripts (scripts/report_common.py re-exports these) and the Edit Specimen dialog's field
record chooser agree:

    blank(v)                  None or only spaces
    norm_ref(ref)             grid ref as compared: upper case, no spaces (Mapping's MAP2 rule)
    norm_text(v)              case, spacing and punctuation folded
    name_words(v)             the surname-like words of a recorder / collector field
    comparable_people(a, b)   both fields name somebody (not blank, not just 'Collected')
    same_person(a, b)         they share a surname-like word ('Heeney, W.J.' == 'Wil Heeney')

Pure functions; nothing here opens a database.
"""
from __future__ import annotations

import re


def blank(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def norm_ref(ref) -> str:
    """A grid reference as compared: upper case, no spaces (Mapping's MAP2 rule)."""
    return "" if ref is None else str(ref).upper().replace(" ", "")


def norm_text(v) -> str:
    """Case, spacing and punctuation folded: 'Heeney, W.J.' == 'heeney  w j'."""
    return " ".join(re.sub(r"[^\w]+", " ", str(v or "")).casefold().split())


# words that are not a person: titles, fillers, and the methods that ended up in some
# observations' recorder column ('Collected', 'Net', 'Field sighting', 'Swept')
_NOT_NAMES = {"unknown", "anon", "anonymous", "and", "the", "per", "via", "mr", "mrs", "ms",
              "dr", "miss", "prof", "collected", "collection", "net", "netted", "swept",
              "sweep", "sweeping", "beaten", "beating", "field", "sighting", "trap", "trapped",
              "pitfall", "light", "malaise", "reared", "specimen", "searched"}


def name_words(v) -> set:
    """The words of a recorder / collector field that could be a surname (3+ letters)."""
    return {w for w in norm_text(v).split() if len(w) >= 3 and w.isalpha()
            and w not in _NOT_NAMES}


def comparable_people(a, b) -> bool:
    """Both fields name somebody (not blank, not just a method word like 'Collected')."""
    return bool(name_words(a)) and bool(name_words(b))


def same_person(a, b) -> bool:
    """True when two recorder / collector fields share a surname-like word: 'Heeney, W.J.',
    'Wil Heeney' and 'Heeney, Wil. Lamin, John' all agree; 'Collected' agrees with nobody."""
    return bool(name_words(a) & name_words(b))
