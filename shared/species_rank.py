"""The one ranking for species-search results -- Data Entry grid and the
SpeciesSearch popup (Add Specimen etc.). Moved from DataEntry/entry_grid.py.

Also the one decision on what a typed or pasted name resolves to (B4, B6; 9 Oct 2026),
so the grid's typing cascade and its paste use the same rules.
"""


def name_tier(text, r):
    """How well the text matches the result's *scientific name*.

    0: tokens are ordered prefixes of successive name words (rut mac -> Rutpela maculata)
    1: every token is a prefix of some word (any order)
    2: the first token prefixes the genus
    3: none of that -- the hit came through a common name, an old name or a 'contains'
    """
    tokens = [t for t in (text or "").lower().split() if t]
    words = (r.get("scientific_name") or "").lower().split()
    if not tokens:
        return 3
    if len(tokens) <= len(words) and all(words[i].startswith(tokens[i]) for i in range(len(tokens))):
        return 0
    if all(any(w.startswith(t) for w in words) for t in tokens):
        return 1
    if words and words[0].startswith(tokens[0]):
        return 2
    return 3


def rank_matches(text, results):
    """Sort matches so genus+epithet prefix hits float to the top (Wil's option b),
    while still showing everything Tabella's fuzzy match would."""
    return sorted(
        results,
        key=lambda r: (name_tier(text, r), 0 if r.get("is_recorded") else 1, (r.get("scientific_name") or "")),
    )


def resolve_name(text, results, interactive=True):
    """What a typed (interactive) or pasted (not interactive) species name resolves to.

    Returns ('fill', result) | ('pick', ranked) | ('unresolved', None).

    - exactly the scientific name, or the only exact hit on any name (an old name, an
      exact common name): fill;
    - a single hit that matches the scientific name by prefix (tier 0/1): fill;
    - otherwise a person has to choose. Typing shows the picker; a paste leaves the text
      unresolved (no TVK) for you to fix -- it never guesses. A single hit reached only
      through part of a common name ("Cricket bat spid" -> Cricket-bat Willow) is not
      filled silently any more: it goes to the picker, or stays unresolved on paste (B6).
    """
    t = (text or "").strip().lower()
    ranked = rank_matches(text, results or [])
    if not t or not ranked:
        return ("unresolved", None)
    sci = [r for r in ranked if (r.get("scientific_name") or "").lower() == t]
    if sci:
        return ("fill", sci[0])
    exact = [r for r in ranked if r.get("match_type") == "exact"]
    if len(exact) == 1:
        return ("fill", exact[0])
    if len(ranked) == 1 and name_tier(text, ranked[0]) <= 1:
        return ("fill", ranked[0])
    return ("pick", ranked) if interactive else ("unresolved", None)
