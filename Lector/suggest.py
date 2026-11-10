"""Fuzzy suggestions for a species name typed in the search builder (Round 15).

Typos and partial words are tolerated: each typed word is compared with the words of every
name (a word that starts with it scores full marks, otherwise a trigram score checked with
difflib), the best matches come first. Pure Python, no new dependency. The index is built
once from the UKSI names (NameIndex) and then answers each keystroke from a trigram lookup.
"""
import difflib
from collections import defaultdict

import unicodedata

RANK_ORDER = {"species": 0, "family": 1, "genus": 2, "subspecies": 3}


def fold(text):
    """Lower-case, accents stripped ('Rosenmüller' -> 'rosenmuller'); ASCII is quick."""
    text = text or ""
    if text.isascii():
        return text.lower()
    return "".join(c for c in unicodedata.normalize("NFKD", text)
                   if not unicodedata.combining(c)).lower()


def _trigrams(word):
    w = f"  {word} "
    return {w[i:i + 3] for i in range(len(w) - 2)}


def word_score(typed, word):
    """0..1: how well a typed word matches a name's word."""
    if not typed or not word:
        return 0.0
    if word.startswith(typed):
        return 1.0 if len(typed) > 1 else 0.6
    a, b = _trigrams(typed), _trigrams(word)
    tri = len(a & b) / len(a | b)
    return max(tri, difflib.SequenceMatcher(None, typed, word).ratio() * 0.95)


class NameIndex:
    """names: iterable of dicts with at least 'name' (and e.g. 'tvk', 'rank', 'family')."""

    def __init__(self, names):
        self.items, self._words, self._by_tri = [], [], defaultdict(set)
        self._owners = defaultdict(list)
        for item in names:
            fname = fold(item["name"])
            ws = fname.split()
            if not ws:
                continue
            idx = len(self.items)
            self.items.append((item, fname, ws))
            for w in set(ws):
                if w not in self._owners:
                    self._words.append(w)
                    for t in _trigrams(w):
                        self._by_tri[t].add(len(self._words) - 1)
                self._owners[w].append(idx)

    def _similar_words(self, typed, limit=60):
        """Words of the list that could match a typed word: shared trigrams, best first."""
        counts = defaultdict(int)
        for t in _trigrams(typed):
            for wi in self._by_tri.get(t, ()):
                counts[wi] += 1
        need = 1 if len(typed) <= 3 else 2
        cands = [wi for wi, n in counts.items() if n >= need]
        cands.sort(key=lambda wi: -counts[wi])
        scored = [(word_score(typed, self._words[wi]), self._words[wi]) for wi in cands[:600]]
        scored.sort(reverse=True)
        return [(s, w) for s, w in scored[:limit] if s >= 0.5]

    def suggest(self, text, limit=8):
        """[{**item, 'score'}] best first; [] for text shorter than two letters."""
        typed = fold(text).split()
        if not typed or len(" ".join(typed)) < 2:
            return []
        sims = [dict((w, s) for s, w in self._similar_words(t)) for t in typed]
        cand = set()
        for d in sims:
            for w in d:
                cand.update(self._owners[w])
        scored = []
        for idx in cand:
            item, fname, ws = self.items[idx]
            total = 0.0
            for pos, (t, d) in enumerate(zip(typed, sims, strict=True)):
                best = max((d.get(w, 0.0) for w in ws), default=0.0)
                if pos < len(ws) and d.get(ws[pos], 0.0) >= best - 1e-9 and best:
                    best += 0.05                                  # same word order
                total += best
            score = total / len(typed)
            if len(typed) < len(ws):
                score -= 0.01 * (len(ws) - len(typed))            # a closer length wins a tie
            if " ".join(typed) == fname:
                score += 1.0
            if score >= 0.5:
                rank = RANK_ORDER.get(str(item.get("rank") or "").lower(), 9)
                scored.append((-score, rank, item["name"], item))
        scored.sort(key=lambda x: x[:3])
        return [dict(x[3], score=round(-x[0], 3)) for x in scored[:limit]]
