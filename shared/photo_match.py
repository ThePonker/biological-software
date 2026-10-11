"""Match the names read from photo files (shared/photo_names.py) to UKSI, and microscope
photos to candidate specimens. Read-only: uksi.db and observatum.db are opened ?mode=ro and
nothing is written anywhere (A8 groundwork, 11 Oct 2026). No Qt.

    m = PhotoMatcher()                       # paths.UKSI_DB, or uksi_path= / uksi_conn=
    m.match_many([(binomial, common), ...])  # {(binomial, common): PhotoMatch}, cached
    m.match_photo(photo_name)                # one PhotoName -> PhotoMatch
    folder_warnings(photo_name, match)       # Microscope: Order / Family folder vs UKSI
    SpecimenIndex(conn).candidates(tvk, iso_date, name)

The order of trust (groundwork A4):
  1. exact current UKSI name -> TVK                         method 'exact'
  2. UKSI synonym -> current TVK                            method 'synonym' (review: F25)
     Steps 1-2 are shared/species_lookup.lookup_names -- the import wizards' rule, unchanged
     (qualifiers 'cf.', 'agg.' ...; species over broad group). A name held twice ('needs a
     choice') is settled by the photo's common name when exactly one candidate has it.
  3. fuzzy (difflib, cutoff 0.85): the rest of the name within the same genus; if the genus
     itself is unknown, close genera first ('Perostichus' -> Pterostichus; the genera one or
     two slips away are found with shared/fuzzy_words.FuzzyVocab, then difflib's cutoff
     applies), then the epithet there                       method 'fuzzy' (review)
  4. the common name from the Life convention only breaks a tie between candidates.
A subspecies not in UKSI falls back to its species, with a note (review).
The name table is shared/species_search's in-memory index (built once, about a second).
"""
from __future__ import annotations

import difflib
import sqlite3
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

from shared.fuzzy_words import FuzzyVocab
from shared.photo_names import PhotoName
from shared.species_lookup import LookupFailure, NameMatch, lookup_names, parse_qualifier
from shared.species_search import SPECIES_LEVEL, get_index

CUTOFF = 0.85
EXACT, SYNONYM, FUZZY, NONE = "exact", "synonym", "fuzzy", "none"


@dataclass
class PhotoMatch:
    query: str                          # the binomial looked up
    method: str = NONE                  # exact / synonym / fuzzy / none
    review: bool = True                 # True unless an exact, unique, unqualified name
    tvk: Optional[str] = None
    scientific_name: Optional[str] = None
    common_name: Optional[str] = None   # UKSI's preferred common name
    rank: Optional[str] = None
    order: Optional[str] = None
    family: Optional[str] = None
    note: str = ""
    candidates: List[str] = field(default_factory=list)   # 'Name [TVK]', best first

    @property
    def status(self) -> str:
        if self.method == NONE:
            return NONE
        return f"{self.method}, review" if self.review else self.method


def _ro(path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


class PhotoMatcher:
    def __init__(self, uksi_path=None, uksi_conn: Optional[sqlite3.Connection] = None):
        if uksi_path is None:
            import paths
            uksi_path = paths.UKSI_DB
        self.uksi_path = str(uksi_path)
        self.conn = uksi_conn or _ro(self.uksi_path)
        self.idx = get_index(self.uksi_path)
        self._cache: Dict[Tuple[str, str], PhotoMatch] = {}
        self._build_tables()

    # ------------------------------------------------------------ name tables (once)

    def _build_tables(self) -> None:
        idx = self.idx
        self.known = set()                  # lower-case scientific names and synonyms
        for name, kind in zip(idx.e_name, idx.e_kind):
            if kind != 1:
                self.known.add(" ".join(name.split()).lower())
        self.by_genus: Dict[str, Dict[str, List[int]]] = {}   # genus -> {rest: [taxon]}
        self.genus_taxa: Dict[str, List[int]] = {}
        for i, (sci, rank) in enumerate(zip(idx.sci, idx.rank)):
            words = (sci or "").split()
            if not words:
                continue
            g = words[0].lower()
            if rank == "Genus" and len(words) == 1:
                self.genus_taxa.setdefault(g, []).append(i)
            elif rank in SPECIES_LEVEL and len(words) >= 2:
                self.by_genus.setdefault(g, {}).setdefault(" ".join(words[1:]).lower(), []).append(i)
        self.genera = sorted(set(self.by_genus) | set(self.genus_taxa))
        self.genus_vocab = FuzzyVocab(self.genera)     # a fast pre-filter for difflib

    def _fill(self, pm: PhotoMatch, i: int) -> PhotoMatch:
        idx = self.idx
        pm.tvk, pm.scientific_name, pm.rank = idx.tvk[i], idx.sci[i], idx.rank[i]
        pm.common_name = idx.common[i] or None
        pm.order, pm.family = idx.order[i], idx.family[i]
        return pm

    def _label(self, i: int) -> str:
        return f"{self.idx.sci[i]} [{self.idx.tvk[i]}]"

    # ------------------------------------------------------------ matching

    def match_many(self, queries: Iterable[Tuple[str, str]]) -> Dict[Tuple[str, str], PhotoMatch]:
        keys = [(b or "", c or "") for b, c in dict.fromkeys(queries)]
        todo = [k for k in keys if k not in self._cache and k[0].strip()]
        exact_names = set()
        for b, _c in todo:
            _q, bare = parse_qualifier(b)
            if bare.lower() in self.known:
                exact_names.add(b)
        looked = lookup_names(sorted(exact_names), self.conn) if exact_names else {}
        for k in todo:
            self._cache[k] = self._one(k[0], k[1], looked.get(k[0]))
        for k in keys:
            if k not in self._cache:
                self._cache[k] = PhotoMatch(query=k[0], note="no name")
        return {k: self._cache[k] for k in keys}

    def match(self, binomial: str, common: str = "") -> PhotoMatch:
        return self.match_many([(binomial, common)])[(binomial or "", common or "")]

    def match_photo(self, pn: PhotoName) -> PhotoMatch:
        return self.match(pn.binomial, pn.common_name)

    def _by_tvk(self, tvk: str) -> Optional[int]:
        return self.idx.pos.get(tvk)

    def _one(self, query: str, common: str, hit) -> PhotoMatch:
        pm = PhotoMatch(query=query)
        if isinstance(hit, NameMatch):
            i = self._by_tvk(hit.taxon.tvk)
            if i is None:
                pm.note = f"UKSI taxon {hit.taxon.tvk} not in the search index"
                return pm
            self._fill(pm, i)
            pm.method = SYNONYM if hit.how == "synonym" else EXACT
            pm.review = pm.method != EXACT or bool(hit.qualifier) or bool(hit.warnings)
            pm.note = "; ".join(hit.notes + hit.warnings)
            return pm
        if isinstance(hit, LookupFailure) and hit.kind == "ambiguous":
            cands = [i for i in (self._by_tvk(t.tvk) for t in hit.candidates) if i is not None]
            pick = self._common_tiebreak(cands, common)
            pm.candidates = [self._label(i) for i in cands]
            if pick is not None:
                self._fill(pm, pick)
                pm.method, pm.note = EXACT, "name held more than once in UKSI; the common name decided"
            else:
                pm.note = "name held more than once in UKSI; needs a choice"
            return pm
        pm = self._fuzzy(query, common)
        words = query.split()
        if pm.method == NONE and len(words) == 3:          # a subspecies UKSI does not hold
            sp = self.match(" ".join(words[:2]), common)
            if sp.method != NONE:
                out = PhotoMatch(**{**sp.__dict__, "query": query, "review": True,
                                    "candidates": list(sp.candidates)})
                out.note = "; ".join(x for x in (f"'{query}' not in UKSI; matched to the species",
                                                  sp.note) if x)
                return out
        return pm

    def _common_tiebreak(self, cands: List[int], common: str) -> Optional[int]:
        c = " ".join((common or "").split()).lower()
        if not c:
            return None
        same = [i for i in cands if (self.idx.common[i] or "").lower() == c]
        return same[0] if len(same) == 1 else None

    def _fuzzy(self, query: str, common: str) -> PhotoMatch:
        pm = PhotoMatch(query=query)
        words = query.lower().split()
        if not words:
            return pm
        genus, rest = words[0], " ".join(words[1:])
        if genus in self.by_genus or genus in self.genus_taxa:
            genera, genus_note = [genus], ""
        else:
            near = list(self.genus_vocab.close_words(genus))   # 1-2 slips (fuzzy_words)
            genera = difflib.get_close_matches(genus, near, n=3, cutoff=CUTOFF)
            genus_note = f"genus '{query.split()[0]}' not in UKSI"
        scored: Dict[int, float] = {}
        for g in genera:
            if not rest:                                   # 'Genus sp'
                for i in self.genus_taxa.get(g, []):
                    scored[i] = difflib.SequenceMatcher(None, genus, g).ratio()
                continue
            rests = self.by_genus.get(g, {})
            if g == genus:
                close = difflib.get_close_matches(rest, list(rests), n=3, cutoff=CUTOFF)
            else:
                close = [rest] if rest in rests else \
                    difflib.get_close_matches(rest, list(rests), n=3, cutoff=CUTOFF)
            for r in close:
                ratio = difflib.SequenceMatcher(None, " ".join(words), f"{g} {r}").ratio()
                for i in rests[r]:
                    scored[i] = max(scored.get(i, 0.0), ratio)
        if not scored:
            pm.note = genus_note or "no UKSI name close enough"
            return pm
        ranked = sorted(scored, key=lambda i: (-scored[i], self.idx.sci[i]))
        pm.candidates = [self._label(i) for i in ranked]
        pick = ranked[0] if len(ranked) == 1 else self._common_tiebreak(ranked, common)
        if pick is None and scored[ranked[0]] > scored[ranked[1]]:
            pick = ranked[0]
        if pick is None:
            pm.note = "several UKSI names equally close; needs a choice"
            return pm
        self._fill(pm, pick)
        pm.method = FUZZY
        pm.note = "; ".join(x for x in (genus_note,
                                        f"close spelling of '{self.idx.sci[pick]}' "
                                        f"({scored[pick]:.2f})") if x)
        return pm


def folder_warnings(pn: PhotoName, pm: PhotoMatch) -> List[str]:
    """Soft check of a microscope photo's Order / Family folders against the matched taxon."""
    out = []
    for label, folder, uksi in (("order", pn.folder_order, pm.order),
                                ("family", pn.folder_family, pm.family)):
        if folder and uksi and folder.lower() != uksi.lower():
            out.append(f"{label} folder '{folder}', UKSI says '{uksi}'")
    return out


class SpecimenIndex:
    """Specimens by (TVK, date) and (name, date), from observatum.db, read-only."""

    def __init__(self, conn: Optional[sqlite3.Connection] = None, db_path=None):
        if conn is None:
            if db_path is None:
                import paths
                db_path = paths.OBSERVATUM_DB
            conn = _ro(db_path)
        self._by: Dict[tuple, Dict[int, dict]] = {}
        cur = conn.execute("SELECT id, specimen_code, species_tvk, species_name, date_collected "
                           "FROM specimens WHERE COALESCE(date_collected, '') != ''")
        for sid, code, tvk, name, date in cur.fetchall():
            row = {"id": sid, "specimen_code": code, "species_tvk": tvk,
                   "species_name": name, "date_collected": date}
            d = (date or "")[:10]
            for key in ((tvk or "", d), ("name:" + " ".join((name or "").split()).lower(), d)):
                if key[0] and key[0] != "name:":
                    self._by.setdefault(key, {})[sid] = row

    def candidates(self, tvk: Optional[str], date: Optional[str], name: str = "") -> List[dict]:
        if not date:
            return []
        found: Dict[int, dict] = {}
        for key in ((tvk or "", date), ("name:" + " ".join((name or "").split()).lower(), date)):
            found.update(self._by.get(key, {}))
        return [found[k] for k in sorted(found)]


__all__ = ["PhotoMatcher", "PhotoMatch", "SpecimenIndex", "folder_warnings",
           "EXACT", "SYNONYM", "FUZZY", "NONE", "CUTOFF"]
