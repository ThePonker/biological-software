"""Recorder names: split a recorder field into names and say which names are one person (R17).

split_names() cuts a field on ";", " & " and " and ". person_key() gives a name a key so that
"Lyons, G.", "Graeme Lyons", "G. Lyons" and "Lyons, G.J." are one person: (surname, first initial),
both lower case, read from "Surname, Initials/Forenames" or "Forenames Surname". A name that cannot
be read that way (one word, an organisation, nothing alphabetic) is kept whole: its key is its
normalised text, and parsed() says False for it. Two people with the same surname and first initial
are counted as one: the count is of distinct (surname, initial), not of people proved different.
No Qt, no database.
"""
from __future__ import annotations

import re
from typing import Iterable, List, Tuple

_SPLIT = re.compile(r"\s*;\s*|\s+&\s+|\s+and\s+", re.IGNORECASE)
# words that mark a group or organisation rather than a person ("Natural England", "Bristol Museum")
_ORG_WORDS = frozenset((
    "society", "group", "ltd", "limited", "trust", "council", "england", "survey", "club", "museum",
    "university", "project", "team", "department", "association", "agency", "service", "services",
    "partnership", "consultancy", "ecology", "recorders", "records", "centre", "center",
    "collection", "wildlife", "natural", "national", "county", "network", "scheme", "committee",
))


def split_names(text) -> List[str]:
    """The names in one recorder field, split on ";", " & " and " and ", trimmed, no blanks."""
    return [n for n in (" ".join(p.split()) for p in _SPLIT.split(str(text or ""))) if n]


def _letters(word: str) -> str:
    return "".join(ch for ch in word if ch.isalpha() or ch in "'-").strip("'-").lower()


def _read(name: str):
    """(surname, first initial) for a name that reads as a person, else None."""
    name = " ".join(str(name or "").split())
    if not name or any(ch.isdigit() for ch in name):
        return None
    if {w.strip(".,").lower() for w in name.split()} & _ORG_WORDS:
        return None
    if "," in name:
        sur, _c, rest = name.partition(",")
        if "," in rest:
            return None
        surname, forenames = _letters(sur.replace(" ", "")), rest.split()
        initial = next((ch.lower() for w in forenames for ch in w if ch.isalpha()), "")
        if not surname or not initial or not forenames[0][:1].isalpha():
            return None
        return surname, initial
    words = name.split()
    if len(words) < 2 or not words[0][:1].isalpha():
        return None
    surname = _letters(words[-1])
    return (surname, words[0][0].lower()) if surname else None


def parsed(name) -> bool:
    """True when the name read as a person (surname and first initial)."""
    return _read(name) is not None


def person_key(name) -> Tuple[str, str]:
    """One key per person: (surname, first initial) lower case; for a name that could not be read,
    ("", its normalised text) so it counts by that text."""
    hit = _read(name)
    return hit if hit else ("", " ".join(str(name or "").split()).lower())


def count_people(names: Iterable[str]) -> Tuple[int, int]:
    """(distinct people, how many of the distinct keys came from a name that could not be read)."""
    keys = {person_key(n) for n in names}
    return len(keys), sum(1 for k in keys if k[0] == "")
