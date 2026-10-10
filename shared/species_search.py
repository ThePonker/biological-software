"""The one species search for every interactive species box in the suite (backlog item 1,
review SRCH15-19, 10 Oct 2026). No Qt.

    from shared.species_search import search
    search("rhag mor")        -> [{'tvk', 'scientific_name', 'common_name', 'rank', ...}, ...]

What it matches, over the whole of uksi.db (scientific names, synonyms, common names):
  * every typed word as the start of -- or, from 3 letters, anywhere in -- some word of the
    name, in any order: "rhag mor", "mor rhag", "agium mord" all find Rhagium mordax;
  * typing slips: a word of 4-7 letters may be 1 edit out, 8 or more 2 (a swap of two
    neighbouring letters is one edit): "Rhagium mordx", "Rutpela maculta";
  * old names: a UKSI synonym returns the CURRENT taxon, with old_name set
    ("Strangalia maculata" -> Rutpela maculata, old name: Strangalia maculata);
  * common names from UKSI ("spotted longhorn" -> Anoplodera sexguttata);
  * qualifiers as written: "Bombus lucorum agg." puts the aggregate first; "cf." is dropped;
    "Rhagium sp." searches the genus;
  * accents, curly apostrophes, hyphens and other punctuation are folded
    ("Mullers" finds "Müllers", "6 spotted" finds "6-spotted").

Order: match quality (exact name; the words in order; every word a prefix; a substring;
then typing slips, fewest edits first), then species before infraspecific, genus, family
and higher ranks, then species you have recorded, then name.

This is for SEARCHING only. Imports keep shared/species_lookup.py's exact rules and never
accept one of these matches without a person choosing it.
The index is built once per process (about a second), on first use, and rebuilt if uksi.db
changes on disk. shared/species_filter.py turns typed text into a TVK set for record tables.
"""
from __future__ import annotations

import bisect
import os
import re
import sqlite3
import threading
import unicodedata
from typing import Dict, Iterable, List, Optional

from shared.fuzzy_words import FuzzyVocab, allowed_edits
from shared.species_lookup import BROAD_QUALIFIERS, BROAD_RANKS, parse_qualifier

# The ranks the record-entry boxes (Quick Entry, Add Specimen, Data Entry...) offer.
SPECIES_LEVEL = frozenset({
    "Species", "Subspecies", "Variety", "Form", "Species aggregate", "Species sensu lato",
    "Microspecies", "Species pro parte", "Species group"})
_MAIN_SPECIES = {"Species", "Species aggregate", "Species sensu lato", "Species pro parte",
                 "Microspecies", "Species group"}
_GENUS_LEVEL = {"Genus", "Subgenus", "Genus aggregate", "Section", "Series"}
_FAMILY_LEVEL = {"Family", "Subfamily", "Superfamily", "Tribe", "Subtribe", "Epifamily"}
_KIND_NAMES = ("scientific", "common", "synonym")
_FILLER = {"sp", "spp", "indet", "ssp"}   # "Rhagium sp." searches the genus
FUZZY_BELOW = 10   # look for typing slips when fewer taxa than this match as typed, none exactly

_PUNCT = re.compile(r"[^0-9a-z]+")
_APOS = dict.fromkeys(map(ord, "'’‘`´ʼ"), None)
_ASCII_FOLD = {c: " " for c in range(128) if not chr(c).isalnum()}
_ASCII_FOLD.update(dict.fromkeys(map(ord, "'`"), None))
_SPECIAL = str.maketrans({"ß": "ss", "æ": "ae", "œ": "oe", "ø": "o",
                          "ł": "l", "×": " "})


def fold_words(text: str) -> List[str]:
    """Lower case, accents and apostrophes dropped, other punctuation a space; the words."""
    s = (text or "").lower()
    if s.isascii():
        return s.translate(_ASCII_FOLD).split()
    s = unicodedata.normalize("NFKD", s.translate(_APOS).translate(_SPECIAL))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return _PUNCT.sub(" ", s).split()


def fold(text: str) -> str:
    return " ".join(fold_words(text))


def rank_group(rank: Optional[str]) -> int:
    """0 species, 1 below species, 2 genus, 3 family, 4 higher (the 'species first' order)."""
    r = rank or ""
    if r in _MAIN_SPECIES:
        return 0
    if r in _GENUS_LEVEL:
        return 2
    if r in _FAMILY_LEVEL:
        return 3
    if r in SPECIES_LEVEL or "species" in r.lower() or r in ("Breed", "Cultivar", "Forma specialis"):
        return 1
    return 4


def is_broad(rank: Optional[str], qualifier: Optional[str]) -> bool:
    q = (qualifier or "").strip().lower()
    return (rank or "") in BROAD_RANKS or q in BROAD_QUALIFIERS or q.startswith("s.l.")


class SpeciesIndex:
    """Every UKSI name, folded into words, with a word index for prefix, substring and
    close-spelling lookups. Built once; read-only afterwards (safe from worker threads)."""

    def __init__(self, conn: sqlite3.Connection):
        self.tvk: List[str] = []
        self.sci: List[str] = []
        self.rank: List[str] = []
        self.family: List[str] = []
        self.order: List[str] = []
        self.genus: List[str] = []
        self.kingdom: List[str] = []
        self.parent: List[Optional[str]] = []
        self.qualifier: List[str] = []
        self.label: List[str] = []
        self.common: List[str] = []
        self.pos: Dict[str, int] = {}
        for r in conn.execute('SELECT tvk, scientific_name, rank, family, "order", genus, '
                              'kingdom, parent_tvk FROM taxa'):
            self.pos[r[0]] = len(self.tvk)
            for lst, v in zip((self.tvk, self.sci, self.rank, self.family, self.order,
                               self.genus, self.kingdom, self.parent), r):
                lst.append(v)
        n = len(self.tvk)
        self.qualifier = [""] * n
        self.label = [""] * n
        self.common = [""] * n
        try:
            for tvk, q, label in conn.execute("SELECT tvk, qualifier, label FROM taxon_qualifiers "
                                              "WHERE COALESCE(qualifier, '') != ''"):
                i = self.pos.get(tvk)
                if i is not None:
                    self.qualifier[i], self.label[i] = q or "", label or ""
        except sqlite3.Error:
            pass                                      # uksi.db built before Oct 2026
        # entries: (taxon, kind, name, words)
        self.e_taxon: List[int] = []
        self.e_kind: List[int] = []
        self.e_name: List[str] = []
        self.e_words: List[tuple] = []
        postings: Dict[str, List[int]] = {}

        def add(i, kind, name, words=None):
            words = words if words is not None else tuple(fold_words(name))
            if not words:
                return
            e = len(self.e_taxon)
            self.e_taxon.append(i)
            self.e_kind.append(kind)
            self.e_name.append(name)
            self.e_words.append(words)
            for w in set(words):
                postings.setdefault(w, []).append(e)

        sci_words = [None] * n
        for i, name in enumerate(self.sci):
            add(i, 0, name or "")
            sci_words[i] = self.e_words[-1] if self.e_taxon and self.e_taxon[-1] == i else ()
        best_common: Dict[int, tuple] = {}
        for name, tvk, pref in conn.execute("SELECT common_name, tvk, preferred FROM common_names"):
            i = self.pos.get(tvk)
            if i is None or not name:
                continue
            add(i, 1, name)
            key = (-(pref or 0), 0 if name[:1].isupper() else 1, len(name), name)
            if i not in best_common or key < best_common[i]:
                best_common[i] = key
        for i, key in best_common.items():
            self.common[i] = key[3]
        for name, tvk in conn.execute("SELECT synonym, tvk FROM synonyms"):
            i = self.pos.get(tvk)
            words = tuple(fold_words(name)) if i is not None and name else ()
            if words and words != sci_words[i]:
                add(i, 2, name, words)
        self.postings = postings
        self.vocab = sorted(postings)
        self._vjoined = "|".join(self.vocab)
        self._vstarts, at = [], 0
        for w in self.vocab:
            self._vstarts.append(at)
            at += len(w) + 1
        self.fuzzy = FuzzyVocab(self.vocab)

    # ------------------------------------------------------------ word lookups

    def _word_quality(self, token: str) -> Dict[str, int]:
        """{word: 0 equal | 1 prefix | 2 substring (tokens of 3+ letters)}."""
        q: Dict[str, int] = {}
        vocab = self.vocab
        i = bisect.bisect_left(vocab, token)
        while i < len(vocab) and vocab[i].startswith(token):
            q[vocab[i]] = 0 if vocab[i] == token else 1
            i += 1
        if len(token) >= 3:
            joined, starts = self._vjoined, self._vstarts
            pos = joined.find(token)
            while pos != -1:
                k = bisect.bisect_right(starts, pos) - 1
                q.setdefault(vocab[k], 2)
                pos = joined.find(token, starts[k + 1] if k + 1 < len(starts) else len(joined))
        return q

    def _slips(self, token: str, q: Dict[str, int]) -> Dict[str, int]:
        """q plus close spellings of token (3 + edits)."""
        out = dict(q)
        if allowed_edits(token):
            for w, d in self.fuzzy.close_words(token).items():
                out.setdefault(w, 2 + d)
        return out

    def _match(self, tokens: List[str], quals: List[Dict[str, int]], ranks) -> Dict[int, tuple]:
        """{entry: (tier, misses, slips)} for entries matching every token, given each
        token's {word: quality}."""
        if any(not q for q in quals):
            return {}
        sizes = [sum(len(self.postings[w]) for w in q) for q in quals]
        pivot = sizes.index(min(sizes))
        cands = set()
        for w in quals[pivot]:
            cands.update(self.postings[w])
        out: Dict[int, tuple] = {}
        n = len(tokens)
        for e in cands:
            if ranks is not None and self.rank[self.e_taxon[e]] not in ranks:
                continue
            words = self.e_words[e]
            best = []
            for q in quals:
                b = min((q[w] for w in words if w in q), default=None)
                if b is None:
                    break
                best.append(b)
            else:
                worst = max(best)
                slips = sum(b - 2 for b in best if b > 2)
                if slips:
                    tier = 4
                elif worst == 2:
                    tier = 3
                elif n == len(words) and all(b == 0 for b in best) and list(tokens) == list(words):
                    tier = 0
                elif n <= len(words) and all(words[k].startswith(tokens[k]) for k in range(n)):
                    tier = 1
                else:
                    tier = 2
                out[e] = (tier, sum(1 for b in best if b != 0), slips)
        return out

    # ------------------------------------------------------------ search

    def search(self, text: str, limit: Optional[int] = 50, ranks: Optional[Iterable[str]] = None,
               recorded: Optional[set] = None, fuzzy: str = "auto") -> List[dict]:
        """Taxa matching text, best first (see the module docstring). limit=None for all.
        ranks: only taxa of these ranks (SPECIES_LEVEL for the record-entry boxes).
        fuzzy: 'auto' (look for typing slips when fewer than FUZZY_BELOW taxa match as
        typed and none exactly), 'always' or 'never'."""
        qualifier, bare = parse_qualifier(text or "")
        tokens = fold_words(bare)
        if len(tokens) > 1:
            tokens = [t for t in tokens if t not in _FILLER] or tokens
        if not tokens or len("".join(tokens)) < 2:
            return []
        ranks = frozenset(ranks) if ranks is not None else None
        quals = [self._word_quality(t) for t in tokens]
        if fuzzy == "always":
            quals = [self._slips(t, q) for t, q in zip(tokens, quals)]
        hits = self._match(tokens, quals, ranks)
        if (fuzzy == "auto" and len({self.e_taxon[e] for e in hits}) < FUZZY_BELOW
                and not any(v[0] == 0 for v in hits.values())):
            quals = [self._slips(t, q) for t, q in zip(tokens, quals)]
            hits.update({e: v for e, v in self._match(tokens, quals, ranks).items()
                         if e not in hits})
        want_broad = qualifier in ("agg.", "s.l.")
        recorded = recorded or set()
        best: Dict[int, tuple] = {}
        for e, (tier, misses, slips) in hits.items():
            i = self.e_taxon[e]
            broad = is_broad(self.rank[i], self.qualifier[i])
            key = (tier, slips, 0 if broad == want_broad else 1, misses, rank_group(self.rank[i]),
                   self.e_kind[e], 0 if self.tvk[i] in recorded else 1,
                   (self.sci[i] or "").lower(), e)
            if i not in best or key < best[i]:
                best[i] = key
        ordered = sorted(best.items(), key=lambda kv: kv[1])
        if limit is not None:
            ordered = ordered[:limit]
        return [self._result(i, key, recorded) for i, key in ordered]

    def _result(self, i: int, key: tuple, recorded: set) -> dict:
        tier, e = key[0], key[-1]
        kind = _KIND_NAMES[self.e_kind[e]]
        matched = self.e_name[e]
        sci = self.sci[i]
        label = self.label[i] if self.label[i] and self.label[i] != sci else ""
        if not label and self.rank[i] in ("Species aggregate", "Species sensu lato"):
            suffix = " agg." if self.rank[i] == "Species aggregate" else " s.l."
            label = sci if ("agg" in sci or "/" in sci or "group" in sci) else sci + suffix
        return {
            "tvk": self.tvk[i], "scientific_name": sci,
            "common_name": matched if kind == "common" else (self.common[i] or None),
            "family": self.family[i], "order": self.order[i], "order_name": self.order[i],
            "genus": self.genus[i], "kingdom": self.kingdom[i], "rank": self.rank[i],
            "qualifier": self.qualifier[i], "label": label or sci,
            "match_type": ("exact", "starts_with", "starts_with", "contains", "fuzzy")[tier],
            "matched_name": matched, "matched_kind": kind,
            "old_name": matched if kind == "synonym" else None,
            "is_recorded": self.tvk[i] in recorded,
            "search_key": key[:-1],
        }

    # ------------------------------------------------------------ taxonomy

    def tvk_for_name(self, name: str) -> Optional[str]:
        """The current TVK of a name as stored on a record: its scientific name, else an old
        name (synonym); a species-level taxon is preferred where the name is held twice.
        None if UKSI doesn't hold it. Qualifiers ('agg.', 'cf.') are dropped first."""
        exact = getattr(self, "_exact", None)
        if exact is None:
            exact = {}
            for e, words in enumerate(self.e_words):
                if self.e_kind[e] != 1:
                    exact.setdefault(" ".join(words), []).append(e)
            self._exact = exact
        es = exact.get(fold(parse_qualifier(name or "")[1]))
        if not es:
            return None
        e = min(es, key=lambda e: (self.e_kind[e], rank_group(self.rank[self.e_taxon[e]])))
        return self.tvk[self.e_taxon[e]]

    def ancestors(self, tvk: str) -> List[str]:
        """tvk and every taxon above it (via taxa.parent_tvk)."""
        out, seen = [], set()
        while tvk and tvk not in seen and tvk in self.pos:
            seen.add(tvk)
            out.append(tvk)
            tvk = self.parent[self.pos[tvk]]
        return out


# ---------------------------------------------------------------- the per-process index

_lock = threading.Lock()
_cache: Dict[str, tuple] = {}


def _default_path() -> str:
    import paths
    return str(paths.UKSI_DB)


def get_index(db_path: Optional[str] = None) -> SpeciesIndex:
    """The index for uksi.db (built on first use, rebuilt if the file changes)."""
    path = os.path.abspath(str(db_path or _default_path()))
    try:
        stamp = os.stat(path).st_mtime_ns
    except OSError:
        stamp = 0
    hit = _cache.get(path)
    if hit and hit[0] == stamp:
        return hit[1]
    with _lock:
        hit = _cache.get(path)
        if hit and hit[0] == stamp:
            return hit[1]
        from shared.db_open import connect_ro
        conn = connect_ro(path)
        try:
            idx = SpeciesIndex(conn)
        finally:
            conn.close()
        _cache[path] = (stamp, idx)
        return idx


def warm_up(db_path: Optional[str] = None) -> None:
    """Build the index in a background thread so the first keystroke doesn't wait."""
    threading.Thread(target=lambda: _safe_index(db_path), daemon=True).start()


def _safe_index(db_path):
    try:
        get_index(db_path)
    except Exception as e:                          # a missing uksi.db must not crash a view
        print(f"[species_search] index not built: {e}")


def search(text: str, limit: Optional[int] = 50, ranks: Optional[Iterable[str]] = None,
           recorded: Optional[set] = None, fuzzy: str = "auto",
           db_path: Optional[str] = None) -> List[dict]:
    """SpeciesIndex.search on the suite's uksi.db (see the module docstring)."""
    return get_index(db_path).search(text, limit=limit, ranks=ranks, recorded=recorded,
                                     fuzzy=fuzzy)


def search_objects(text: str, limit: Optional[int] = 50, ranks: Optional[Iterable[str]] = None,
                   db_path: Optional[str] = None) -> list:
    """search() as objects with attributes (tvk, scientific_name, common_name, order_name,
    family, rank, kingdom, old_name, match_type, ...) -- the shape UKSIModel.search_species
    returned, for the dialogs written against it."""
    from types import SimpleNamespace
    return [SimpleNamespace(**r) for r in search(text, limit=limit, ranks=ranks, db_path=db_path)]


__all__ = ["SPECIES_LEVEL", "SpeciesIndex", "get_index", "search", "search_objects", "fold",
           "fold_words", "rank_group", "is_broad", "warm_up"]
