"""What kind of name a record carries: the one rule for "incomplete" records (10 Oct 2026).

Used by the species-counting switches (backlog A) and the cleaning report (backlog B), so
both agree on what counts as genus-only, an aggregate, a subspecies and so on.

Kinds (a record can carry more than one):
    genus        genus only: "Leiopus", "Leiopus sp.", "Leiopus spp." (rank Genus/Subgenus)
    family_plus  family or any higher rank: "Cerambycidae", "Coleoptera" (rank Family and up)
    agg          aggregate: "agg." / a slash pair ("Leiopus linnei/nebulosus") / rank Species aggregate
    sl           sensu lato: "s.l." / "sensu lato" / rank Species sensu lato
    ss           sensu stricto: "s.s." / "sensu stricto"   (counted as the plain species)
    hybrid       "x" / "×" between names, or rank Species hybrid
    subsp        below species: Subspecies, Variety, Form, Aberration, ... or "ssp." / "subsp." /
                 "var." / "f." / "ab." in the name, or a trinomial (subgenus "(Xxx)" ignored)

The record's own taxon_rank wins where it says more than the name (e.g. "Xanthogramma
pedissequum" held on the s.l. TVK has rank "Species sensu lato"); the name adds markers the
rank misses (e.g. "Forficula auricularia/dentata agg." stored with rank "Species").
Where a record has no rank, pass UKSI's rank for its TVK (see ranks_for_tvks).

Pure functions, plus two small batched UKSI lookups that take an open (read-only) connection.
"""
from __future__ import annotations

import re
import sqlite3
from typing import Dict, FrozenSet, Iterable, Optional

KINDS = ("genus", "family_plus", "agg", "sl", "ss", "hybrid", "subsp")

KIND_LABELS = {
    "genus": "Genus only",
    "family_plus": "Family or higher",
    "agg": "Aggregate (agg.)",
    "sl": "Sensu lato (s.l.)",
    "ss": "Sensu stricto (s.s.)",
    "hybrid": "Hybrid",
    "subsp": "Subspecies / variety / form",
}

_GENUS_RANKS = {"genus", "subgenus"}
_FAMILY_PLUS_RANKS = {
    "family", "subfamily", "superfamily", "tribe", "subtribe", "section", "order", "suborder",
    "infraorder", "parvorder", "superorder", "class", "subclass", "infraclass", "superclass",
    "phylum", "subphylum", "division", "subdivision", "kingdom", "subkingdom", "domain",
    "cohort", "infrakingdom", "unranked",
}
_SUBSP_RANKS = {
    "subspecies", "variety", "subvariety", "form", "subform", "aberration", "abberation",
    "morph", "race", "cultivar", "breed", "forma", "nothosubspecies", "nothovariety",
}

_SUBGENUS = re.compile(r"\s*\([A-Z][a-z]+\)\s*")
_AGG = re.compile(r"\bagg\b\.?", re.IGNORECASE)
_SL = re.compile(r"\bs\.\s?l\.|\bsensu\s+lato\b", re.IGNORECASE)
_SS = re.compile(r"\bs\.\s?s\.|\bsensu\s+stricto\b", re.IGNORECASE)
_HYBRID = re.compile(r"(^|\s)[x×](\s|$)|×")
_INFRA = re.compile(r"\b(ssp|subsp|var|f|ab|forma|morph)\.(\s|$)", re.IGNORECASE)
_SP = re.compile(r"^\s*([A-Z][a-z]+)\s+(sp|spp|sp\.|spp\.)\s*(\(.*\))?\s*$", re.IGNORECASE)
_AUTH_PAREN = re.compile(r"\s*\(=.*?\)\s*")          # "(=nigra auctt.)" notes


def _clean(name: str) -> str:
    n = (name or "").strip()
    n = _AUTH_PAREN.sub(" ", n)
    n = _SUBGENUS.sub(" ", n)
    return re.sub(r"\s+", " ", n).strip()


def classify(name: Optional[str], rank: Optional[str] = None) -> FrozenSet[str]:
    """The kinds a record's name carries (empty set = a plain, complete species)."""
    kinds = set()
    r = (rank or "").strip().lower()
    if r in _GENUS_RANKS:
        kinds.add("genus")
    elif r in _FAMILY_PLUS_RANKS:
        kinds.add("family_plus")
    elif r == "species aggregate":
        kinds.add("agg")
    elif r == "species sensu lato":
        kinds.add("sl")
    elif r == "species hybrid":
        kinds.add("hybrid")
    elif r in _SUBSP_RANKS:
        kinds.add("subsp")

    raw = (name or "").strip()
    n = _clean(raw)
    if not n:
        return frozenset(kinds)
    if _AGG.search(n):
        kinds.add("agg")
    if "/" in n and not _SL.search(n):
        kinds.add("agg")
    if _SL.search(n):
        kinds.add("sl")
    if _SS.search(n):
        kinds.add("ss")
    if _HYBRID.search(n):
        kinds.add("hybrid")
    if _INFRA.search(n):
        kinds.add("subsp")

    core = _SS.sub(" ", _SL.sub(" ", _AGG.sub(" ", n)))
    core = re.sub(r"\s+", " ", core).strip()
    words = core.split(" ")
    if _SP.match(core) or (len(words) == 1 and words[0][:1].isupper()):
        if not kinds & {"family_plus", "agg", "sl", "hybrid"}:
            if not r or r in _GENUS_RANKS or r in ("species",):
                # one capitalised word: genus, unless the rank (or an -idae/-inae/-ini ending,
                # or an order-style -ptera) says higher
                w = words[0]
                if r in _FAMILY_PLUS_RANKS or re.search(r"(idae|inae|ini|oidea|ptera|formes)$", w):
                    kinds.add("family_plus")
                else:
                    kinds.add("genus")
    elif (len(words) >= 3 and words[0][:1].isupper() and all(w[:1].islower() for w in words[1:3])
          and not kinds & {"agg", "sl", "hybrid"} and "/" not in core):
        kinds.add("subsp")
    if "family_plus" in kinds:
        kinds.discard("genus")
    return frozenset(kinds)


def is_excluded(kinds: Iterable[str], excluded: Iterable[str]) -> bool:
    """True when any of the record's kinds is switched off."""
    ex = set(excluded)
    return any(k in ex for k in kinds)


def ranks_for_tvks(uksi_conn: sqlite3.Connection, tvks: Iterable[str]) -> Dict[str, str]:
    """{tvk: UKSI rank} for records with no stored rank. Batched (900 a query); raises on error."""
    out: Dict[str, str] = {}
    ids = [t for t in {t for t in tvks if t}]
    for i in range(0, len(ids), 900):
        chunk = ids[i:i + 900]
        ph = ",".join("?" * len(chunk))
        for tvk, rank in uksi_conn.execute(f"SELECT tvk, rank FROM taxa WHERE tvk IN ({ph})", chunk):
            out[tvk] = rank
    return out


def species_tvks(uksi_conn: sqlite3.Connection, tvks: Iterable[str]) -> Dict[str, str]:
    """{tvk: tvk of the species it rolls up to} for subspecies/variety/form... TVKs.

    Walks parent_tvk until a rank of Species (at most 4 steps). TVKs already at species (or
    above, or unknown) map to themselves. Batched; raises on error.
    """
    ids = [t for t in {t for t in tvks if t}]
    info: Dict[str, tuple] = {}

    def load(batch):
        for i in range(0, len(batch), 900):
            chunk = batch[i:i + 900]
            ph = ",".join("?" * len(chunk))
            for tvk, rank, parent in uksi_conn.execute(
                    f"SELECT tvk, rank, parent_tvk FROM taxa WHERE tvk IN ({ph})", chunk):
                info[tvk] = ((rank or "").lower(), parent)

    load(ids)
    out: Dict[str, str] = {}
    for t in ids:
        cur, steps = t, 0
        while steps < 4 and cur in info and info[cur][0] in _SUBSP_RANKS and info[cur][1]:
            nxt = info[cur][1]
            if nxt not in info:
                load([nxt])
            cur, steps = nxt, steps + 1
        out[t] = cur if cur in info and info[cur][0] == "species" else t
    return out


def species_name_for_ss(name: str) -> str:
    """'Bombus terrestris s.s.' -> 'Bombus terrestris' (s.s. counts as the plain species)."""
    return re.sub(r"\s+", " ", _SS.sub(" ", name or "")).strip()
