"""The one ranking for species-search results -- Data Entry grid and the
SpeciesSearch popup (Add Specimen etc.). Moved from DataEntry/entry_grid.py."""


def rank_matches(text, results):
    """Sort matches so genus+epithet prefix hits float to the top (Wil's option b),
    while still showing everything Tabella's fuzzy match would."""
    tokens = [t for t in (text or "").lower().split() if t]

    def score(r):
        name = (r.get("scientific_name") or "").lower()
        words = name.split()
        if not tokens:
            return 3
        # tier 0: tokens are ordered prefixes of successive name words (rut mac -> Rutpela maculata)
        if len(tokens) <= len(words) and all(words[i].startswith(tokens[i]) for i in range(len(tokens))):
            return 0
        # tier 1: every token is a prefix of some word (any order)
        if all(any(w.startswith(t) for w in words) for t in tokens):
            return 1
        # tier 2: first token prefixes the genus
        if words and words[0].startswith(tokens[0]):
            return 2
        return 3

    return sorted(
        results,
        key=lambda r: (score(r), 0 if r.get("is_recorded") else 1, (r.get("scientific_name") or "")),
    )
