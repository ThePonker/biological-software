"""Finding scientific names in OCR text (review finding LEC6).

BHL's OCR prints names in many ways. A searched name is found when it appears:
  - in any case ('LAMIA TEXTOR', 'lamia textor');
  - with any whitespace between the words, line breaks included ('Lamia\\ntextor');
  - with or without accents, either way round ('Rosenmüller' / 'rosenmuller');
  - hyphenated across a line end ('tex-\\ntor', 'Lami-\\n  a textor');
  - with the genus abbreviated ('L. textor') or left out ('textor', as in a
    list under the genus heading).

    find_names(text, names) -> list of (start, end) spans in the ORIGINAL text,
                               so callers can bold or cut excerpts exactly.
Pure functions: no database, no network.
"""
import re
import unicodedata

# A word broken at a line end: hyphen (or soft hyphen / not-sign some OCR gives),
# optional spaces, the line break, optional indentation.
_BREAK = r"(?:[-­¬]\s*\n\s*|­)"


def fold(text):
    """Lower-case and strip accents: 'Rosenmüller' -> 'rosenmuller'."""
    folded, _ = fold_with_map(text)
    return folded


def fold_with_map(text):
    """Fold text and keep, for each folded character, its index in the original.

    Most characters fold one-to-one; ligatures such as 'ﬁ' become two, combining
    accents vanish. The map lets a match in the folded text be mapped back.
    """
    out, where = [], []
    for i, ch in enumerate(text or ""):
        for f in unicodedata.normalize("NFKD", ch):
            if unicodedata.combining(f):
                continue
            for c in f.lower():
                out.append(c)
                where.append(i)
    return "".join(out), where


def _word(word):
    """Regex for one folded word that tolerates a hyphenated line break
    between any two of its letters."""
    letters = [re.escape(c) for c in fold(word)]
    return f"{_BREAK}?".join(letters)


def name_regex(names):
    """One compiled regex (for FOLDED text) matching any of the names.

    Binomials and trinomials match with the full genus, its initial plus a
    full stop, or no genus at all. A single word (a genus) matches as is.
    """
    alts = []
    for name in names or []:
        parts = [p for p in (name or "").split() if not p.startswith("(")]
        if not parts:
            continue
        if len(parts) == 1:
            alts.append(_word(parts[0]))
            continue
        genus, rest = parts[0], [p for p in parts[1:] if p not in ("var.", "subsp.", "ssp.", "f.")]
        rest = [p for p in rest if p[:1].islower()] or rest[-1:]
        tail = r"\s+".join(_word(p) for p in rest)
        g = fold(genus)
        alts.append(rf"(?:(?:{_word(genus)}|{re.escape(g[0])}\.)\s*)?{tail}")
    if not alts:
        return None
    alts.sort(key=len, reverse=True)
    return re.compile(r"(?<![^\W\d_])(?:" + "|".join(alts) + r")(?![^\W\d_])")


def find_names(text, names, regex=None):
    """Spans (start, end) in the original text where any of the names occurs."""
    regex = regex or name_regex(names)
    if not text or regex is None:
        return []
    folded, where = fold_with_map(text)
    spans = []
    for m in regex.finditer(folded):
        if m.end() == m.start():
            continue
        start, end = where[m.start()], where[m.end() - 1] + 1
        if spans and start < spans[-1][1]:
            continue
        spans.append((start, end))
    return spans


def name_in_text(text, names):
    return bool(find_names(text, names))
