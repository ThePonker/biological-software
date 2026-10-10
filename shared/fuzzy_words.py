"""Typo tolerance for the shared species search (backlog item 1, 10 Oct 2026). No Qt.

    allowed_edits(word)        how many typing slips a typed word may carry:
                               0 under 4 letters, 1 for 4-7, 2 for 8 or more
    osa_distance(a, b, limit)  Damerau-Levenshtein (optimal string alignment) distance --
                               a swap of two neighbouring letters counts as one edit;
                               returns limit + 1 as soon as the distance must exceed limit
    FuzzyVocab(words)          finds the words of a vocabulary within that distance of a
                               typed word, without comparing against all of them

How FuzzyVocab stays fast (90,000 UKSI words, a few milliseconds per word): if two words are
at most d edits apart, then cutting the typed word into d + 1 pieces, at least one piece
appears unchanged in the other word, within d letters of where it sits in the typed word
(the pigeonhole rule). Words are kept in one string per length, so each piece is found with
str.find over only the words of a possible length, and only those few candidates are
checked letter by letter. A swap across a cut breaks two pieces with one edit, so the typed
word with that pair swapped back is looked up too.
"""
from __future__ import annotations

from typing import Dict, Iterable, List


def allowed_edits(word: str) -> int:
    n = len(word)
    if n >= 8:
        return 2
    if n >= 4:
        return 1
    return 0


def osa_distance(a: str, b: str, limit: int = 2) -> int:
    """Optimal string alignment distance between a and b, capped at limit + 1."""
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if abs(la - lb) > limit:
        return limit + 1
    prev2 = None
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        cur = [i] + [0] * lb
        ai = a[i - 1]
        best = cur[0]
        for j in range(1, lb + 1):
            cost = 0 if ai == b[j - 1] else 1
            v = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            if (prev2 is not None and j > 1 and ai == b[j - 2] and a[i - 2] == b[j - 1]):
                v = min(v, prev2[j - 2] + 1)
            cur[j] = v
            if v < best:
                best = v
        if best > limit:
            return limit + 1
        prev2, prev = prev, cur
    d = prev[lb]
    return d if d <= limit else limit + 1


def _pieces(word: str, n: int) -> List[tuple]:
    """(offset, piece) for word cut into n nearly equal pieces."""
    out, start, size = [], 0, len(word)
    for k in range(n):
        end = start + (size - start) // (n - k)
        out.append((start, word[start:end]))
        start = end
    return out


class FuzzyVocab:
    """The words of a vocabulary, grouped by length, for close-spelling lookups."""

    def __init__(self, words: Iterable[str]):
        by_len: Dict[int, List[str]] = {}
        for w in words:
            by_len.setdefault(len(w), []).append(w)
        # one '|'-separated string per length: word k of length L starts at k * (L + 1)
        self._lists = by_len
        self._joined = {n: "|".join(ws) + "|" for n, ws in by_len.items()}

    def close_words(self, word: str, max_edits: int = None) -> Dict[str, int]:
        """{vocabulary word: edits} for words within max_edits of word (itself excluded)."""
        d = allowed_edits(word) if max_edits is None else max_edits
        if d <= 0:
            return {}
        variants = {word}
        cuts = [off for off, _ in _pieces(word, d + 1)][1:]
        for c in cuts:                      # a swap across a cut is one edit, two broken pieces
            if 0 < c < len(word):
                variants.add(word[:c - 1] + word[c] + word[c - 1] + word[c + 1:])
        found: Dict[str, int] = {}
        for length in range(len(word) - d, len(word) + d + 1):
            joined = self._joined.get(length)
            if not joined:
                continue
            words = self._lists[length]
            step = length + 1
            checked = set()
            for v in variants:
                for off, piece in _pieces(v, d + 1):
                    if not piece:
                        continue
                    pos = joined.find(piece)
                    while pos != -1:
                        k, at = divmod(pos, step)
                        if abs(at - off) <= d and k not in checked:
                            checked.add(k)
                            cand = words[k]
                            if cand != word:
                                dist = osa_distance(word, cand, d)
                                if dist <= d:
                                    found[cand] = dist
                        pos = joined.find(piece, pos + 1)
        return found


__all__ = ["allowed_edits", "osa_distance", "FuzzyVocab"]
