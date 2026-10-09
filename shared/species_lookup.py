"""Species lookup for the import wizards and Examen's Import List -- one rule set. No Qt.

Written once in C4 (9 Oct 2026) with each wizard's differences kept as options; the options
were removed the same evening (fix round, items 13 and 16, Wil's rules), so the three import
wizards and Examen now match a name the same way:

    lookup_names(names, uksi) -> {name: NameMatch | LookupFailure}

`uksi` is a UKSIModel (anything with .db.execute_uksi) or a sqlite3 connection to uksi.db.

For each distinct name:
  1. A qualifier is taken off -- 'cf' / 'cf.' (before the epithet or the whole name),
     'agg' / 'agg.', 's.l' / 's.l.' / 'sl' / 'sensu lato' / 'sens. lat.', and 's.str.' /
     'sensu stricto' (the plain species) -- in any case, with or without the dot.
  2. The rest (spaces tidied) is matched EXACTLY, case-insensitive: a UKSI scientific name,
     else a UKSI synonym. Where the name is held more than once:
       * Species over broad group (Wil's rule, IMP-14): a plain name held both as a species
         and as a sensu lato / aggregate taxon resolves to the species; the note says so.
       * a genus held also as a subgenus resolves to the genus;
       * otherwise the name is ambiguous ('needs choice').
  3. 'agg.' / 's.l.': the aggregate / sensu lato taxon of that name when UKSI has one;
     otherwise the species, with the warning "no aggregate in UKSI -- matched to species".
     'cf.': the species, with an uncertain-ID warning. Kingdom, rank etc. are kept.
  4. Anything not matched exactly is searched for (scientific names, synonyms, common names)
     but NEVER accepted: the candidates go back with the failure, for the user to confirm
     (Resolve Species / bulk resolution). "Ab" is not Populus alba.

Saved aliases (the species_aliases table) are no longer read: UKSI's synonyms cover all six
that existed (9 Oct 2026, agreed with Wil). The table is left in place.

Recorded against the real uksi.db in tests/golden/species_lookup_golden.json.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Union

# ---------------------------------------------------------------- results


@dataclass
class Taxon:
    """A UKSI taxon (None where UKSI has no value)."""
    tvk: Optional[str] = None
    scientific_name: Optional[str] = None
    common_name: Optional[str] = None
    rank: Optional[str] = None
    kingdom: Optional[str] = None
    phylum: Optional[str] = None
    class_name: Optional[str] = None
    order_name: Optional[str] = None
    family: Optional[str] = None
    genus: Optional[str] = None
    qualifier: str = ""            # taxon_qualifiers.qualifier ('sensu lato', 'agg.', ...)

    def as_dict(self) -> dict:
        return {f: getattr(self, f) for f in self.__dataclass_fields__}


@dataclass
class NameMatch:
    """How one imported name was matched.

    how:       'exact' (a UKSI scientific name) | 'synonym' (a UKSI synonym)
    qualifier: 'cf.' | 'agg.' | 's.l.' | 's.str.' | None, as the name was written
    looked_up: the name matched (without the qualifier, spaces tidied)
    notes:     for the import notes; warnings: for the row's warnings
    """
    name: str
    how: str
    qualifier: Optional[str]
    looked_up: str
    taxon: Taxon
    notes: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class LookupFailure:
    """No match accepted. kind: 'not_found'; 'ambiguous' (held more than once -- needs a
    choice); or 'error' (the lookup itself failed -- the name may well be in UKSI).
    candidates: UKSI taxa the user may confirm, best first."""
    name: str
    kind: str
    message: str = ""
    candidates: List[Taxon] = field(default_factory=list)


Result = Union[NameMatch, LookupFailure]

# ---------------------------------------------------------------- the error texts
# The wizards' Resolve Species buttons collect the rows whose error starts with one of these.

NOT_FOUND = "Species not found in UKSI"
AMBIGUOUS = "Species name matches more than one UKSI taxon"
FAILED = "Species lookup failed"
NO_AGGREGATE = "no aggregate in UKSI — matched to species"
SPECIES_ERRORS = (NOT_FOUND, AMBIGUOUS, FAILED, "Species not found", "UKSI lookup error",
                  "Not a species-level record", "Subgenus-level record")


def is_species_error(message: str) -> bool:
    """True for an error about the species name (one that a re-match or resolution fixes)."""
    return (message or "").strip().startswith(SPECIES_ERRORS)


def is_unresolved_error(message: str) -> bool:
    """True for a row error that Resolve Species should offer: not found, or needs a choice."""
    return any(p in (message or "") for p in (NOT_FOUND, AMBIGUOUS, "Species not found:"))


# ---------------------------------------------------------------- qualifiers

_CF_MID = re.compile(r"^(\S+)\s+cf\.?\s+(\S.*)$", re.IGNORECASE)
_CF_LEAD = re.compile(r"^cf\.?\s+(\S.*)$", re.IGNORECASE)
_AGG = re.compile(r"^(.+?)\s+agg\.?$", re.IGNORECASE)
_SL = re.compile(r"^(.+?)\s+(?:s\.\s?l\.?|sl\.?|s\.\s?lat\.?|sens(?:u|\.)\s?lat(?:o|\.)?)$",
                 re.IGNORECASE)
_SSTR = re.compile(r"^(.+?)\s+(?:s\.\s?str\.?|s\.\s?s\.|sens(?:u|\.)\s?str(?:icto|\.)?)$",
                   re.IGNORECASE)


def tidy(name: str) -> str:
    """Spaces trimmed and collapsed; a byte-order mark or zero-width space dropped."""
    return " ".join((name or "").replace("\ufeff", "").replace("\u200b", "").split())


def parse_qualifier(name: str):
    """('cf.' | 'agg.' | 's.l.' | 's.str.' | None, the name without it, spaces tidied).

    'Anthocoris cf confusus' -> ('cf.', 'Anthocoris confusus');
    'Bombus lucorum AGG' -> ('agg.', 'Bombus lucorum'); 'Bombus lucorum s.l' -> ('s.l.', ...)."""
    n = tidy(name)
    m = _CF_MID.match(n)
    if m:
        return "cf.", tidy(f"{m.group(1)} {m.group(2)}")
    m = _CF_LEAD.match(n)
    if m:
        return "cf.", tidy(m.group(1))
    m = _AGG.match(n)
    if m:
        return "agg.", tidy(m.group(1))
    m = _SL.match(n)
    if m:
        return "s.l.", tidy(m.group(1))
    m = _SSTR.match(n)
    if m:
        return "s.str.", tidy(m.group(1))
    return None, n


# ---------------------------------------------------------------- reading uksi.db

BROAD_RANKS = ("Species sensu lato", "Species aggregate", "Species group", "Genus aggregate")
BROAD_QUALIFIERS = ("agg.", "s.l.", "sensu lato", "sens. lat.", "s. lat.", "s.lat.", "sens.lat.")
_SPECIES_RANKS = ("Species", "Subspecies", "Variety", "Form", "Microspecies")


def is_broad(t: Taxon) -> bool:
    """A sensu lato / aggregate taxon -- by rank, or by UKSI's qualifier on a shared name."""
    return (t.rank or "") in BROAD_RANKS or (t.qualifier or "").strip().lower() in BROAD_QUALIFIERS


def _rows(uksi, sql: str, params) -> list:
    db = getattr(uksi, "db", None)
    if db is not None and hasattr(db, "execute_uksi"):
        return list(db.execute_uksi(sql, tuple(params)) or [])
    cur = uksi.execute(sql, tuple(params))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _get(r, key):
    try:
        return r[key]
    except (KeyError, IndexError):
        return None


def _qualifier_sql(uksi) -> tuple:
    """(column, join) -- taxon_qualifiers exists in uksi.db built since Oct 2026. Asked each
    time (a cache keyed on id() was wrong once the object was gone and the id reused)."""
    try:
        has = bool(_rows(uksi, "SELECT name FROM sqlite_master "
                               "WHERE type='table' AND name='taxon_qualifiers'", ()))
    except Exception:
        has = False
    if has:
        return "COALESCE(q.qualifier, '')", "LEFT JOIN taxon_qualifiers q ON q.tvk = t.tvk"
    return "''", ""


def _taxon_select(uksi) -> str:
    qcol, qjoin = _qualifier_sql(uksi)
    return (
        "SELECT {key} AS k, t.tvk, t.scientific_name, t.rank, t.kingdom, t.phylum, "
        "t.class AS class_name, t.\"order\" AS order_name, t.family, t.genus, "
        f"t.sort_code, {qcol} AS qualifier, "
        "(SELECT cn.common_name FROM common_names cn WHERE cn.tvk = t.tvk "
        " ORDER BY cn.preferred DESC, CASE WHEN cn.common_name GLOB '[A-Z]*' THEN 0 ELSE 1 END, "
        " LENGTH(cn.common_name) LIMIT 1) AS common_name "
        "FROM {src} " + qjoin + " ")


def _taxon(r) -> Taxon:
    return Taxon(tvk=_get(r, "tvk"), scientific_name=_get(r, "scientific_name"),
                 common_name=_get(r, "common_name"), rank=_get(r, "rank"),
                 kingdom=_get(r, "kingdom"), phylum=_get(r, "phylum"),
                 class_name=_get(r, "class_name"), order_name=_get(r, "order_name"),
                 family=_get(r, "family"), genus=_get(r, "genus"),
                 qualifier=_get(r, "qualifier") or "")


def _by_name(uksi, keys: List[str], synonyms: bool) -> Dict[str, List[Taxon]]:
    """{lower-cased name: [taxa]} for exact scientific names (or synonyms), chunked."""
    out: Dict[str, List[Taxon]] = {}
    if synonyms:
        base = _taxon_select(uksi).format(key="LOWER(s.synonym)",
                                          src="synonyms s JOIN taxa t ON t.tvk = s.tvk")
        where = "WHERE LOWER(s.synonym) IN ({ph}) ORDER BY t.sort_code"
    else:
        base = _taxon_select(uksi).format(key="LOWER(t.scientific_name)", src="taxa t")
        where = "WHERE LOWER(t.scientific_name) IN ({ph}) ORDER BY t.sort_code"
    for i in range(0, len(keys), 400):
        chunk = keys[i:i + 400]
        sql = base + where.format(ph=",".join("?" * len(chunk)))
        for r in _rows(uksi, sql, chunk):
            t = _taxon(r)
            lst = out.setdefault(_get(r, "k"), [])
            if all(x.tvk != t.tvk for x in lst):
                lst.append(t)
    return out


def _choose(taxa: List[Taxon]):
    """(taxon, note) for one name held by these taxa, or (None, '') when it needs a choice."""
    if len(taxa) == 1:
        return taxa[0], ""
    narrow = [t for t in taxa if not is_broad(t)]
    if len(narrow) == 1:
        broad = [t for t in taxa if is_broad(t)]
        what = broad[0].rank if broad[0].rank in BROAD_RANKS else (broad[0].qualifier or broad[0].rank)
        return narrow[0], (f"'{narrow[0].scientific_name}' is held in UKSI both as a species and "
                           f"as a broader taxon ({what}); matched to the species")
    if not narrow and len(taxa) > 1:
        return None, ""
    genera = [t for t in narrow if t.rank == "Genus"]
    if len(genera) == 1 and all(t.rank in ("Genus", "Subgenus") for t in narrow):
        return genera[0], ""
    return None, ""


def aggregate_taxa(uksi, bare_name: str, qualifier: str = "agg.") -> List[Taxon]:
    """The sensu lato / aggregate taxa named bare_name (or 'bare_name agg.' / 's.l.' / ...),
    the preferred kind first: 'Species aggregate' for agg., 'Species sensu lato' for s.l."""
    b = tidy(bare_name).lower()
    names = [b] + [f"{b} {s}" for s in ("agg.", "agg", "s.l.", "s. lat.", "sensu lato", "sens. lat.")]
    found = _by_name(uksi, names, synonyms=False)
    taxa = [t for n in names for t in found.get(n, []) if is_broad(t)]
    first = "Species aggregate" if qualifier == "agg." else "Species sensu lato"
    taxa.sort(key=lambda t: 0 if t.rank == first else 1)
    return taxa


def search_candidates(uksi, text: str, limit: int = 8) -> List[Taxon]:
    """UKSI taxa whose scientific name, synonym or common name contains every word of text --
    suggestions for the user to confirm, never matches. Best first: an exact name, then names
    whose words start with the terms, then the rest; species-level ranks before others."""
    terms = [t for t in tidy(text).split() if t]
    if not terms or len(tidy(text)) < 2:
        return []
    like = " AND ".join(["{col} LIKE ?"] * len(terms))
    params = [f"%{t}%" for t in terms]
    sel = _taxon_select(uksi)
    found: Dict[str, tuple] = {}
    for key, src, col in (("t.scientific_name", "taxa t", "t.scientific_name"),
                          ("s.synonym", "synonyms s JOIN taxa t ON t.tvk = s.tvk", "s.synonym"),
                          ("cn2.common_name", "common_names cn2 JOIN taxa t ON t.tvk = cn2.tvk",
                           "cn2.common_name")):
        sql = sel.format(key=key, src=src) + "WHERE " + like.format(col=col) + " LIMIT 300"
        for r in _rows(uksi, sql, params):
            t = _taxon(r)
            matched = (_get(r, "k") or "").lower()
            low = tidy(text).lower()
            words = matched.split()
            if matched == low:
                score = 0
            elif all(any(w.startswith(x.lower()) for w in words) for x in terms):
                score = 1
            elif matched.startswith(low):
                score = 2
            else:
                score = 3
            score = score * 2 + (0 if (t.rank or "") in _SPECIES_RANKS else 1)
            rank = (score, len(t.scientific_name or ""), _get(r, "sort_code") or 0)
            if t.tvk not in found or rank < found[t.tvk][0]:
                found[t.tvk] = (rank, t)
    if not found and len(terms) >= 2:
        return _close_spellings(uksi, terms, limit)
    return [t for _, t in sorted(found.values(), key=lambda x: x[0])][:limit]


def _close_spellings(uksi, terms: List[str], limit: int) -> List[Taxon]:
    """A misspelt binomial ('Rutpela maculta', 'Rutpla maculata'): the closest spellings among
    names sharing its genus or its last word. Suggestions only."""
    import difflib
    sel = _taxon_select(uksi).format(key="t.scientific_name", src="taxa t")
    pool: Dict[str, Taxon] = {}
    for pattern in (f"{terms[0]} %", f"% {terms[-1]}"):
        for r in _rows(uksi, sel + "WHERE t.scientific_name LIKE ? LIMIT 2000", (pattern,)):
            t = _taxon(r)
            pool.setdefault((t.scientific_name or "").lower(), t)
    close = difflib.get_close_matches(" ".join(terms).lower(), list(pool), n=limit, cutoff=0.8)
    return [pool[n] for n in close]


# ---------------------------------------------------------------- the lookup


def _match_exact(uksi, keys: List[str]) -> Dict[str, object]:
    """{lower name: (Taxon, how, note) | ('ambiguous', [taxa])} -- names, then synonyms."""
    out: Dict[str, object] = {}
    by_name = _by_name(uksi, keys, synonyms=False)
    rest = [k for k in keys if k not in by_name]
    by_syn = _by_name(uksi, rest, synonyms=True) if rest else {}
    for how, found in (("exact", by_name), ("synonym", by_syn)):
        for k, taxa in found.items():
            t, note = _choose(taxa)
            out[k] = (t, how, note) if t is not None else ("ambiguous", taxa)
    return out


def _typed_note(name: str, matched: str) -> str:
    """IMP-15: the name as typed, when it differs from the stored UKSI name."""
    return f"Imported as '{name}'" if tidy(name) != (matched or "") else ""


def lookup_names(names: Iterable[str], uksi, cancelled: Callable[[], bool] = lambda: False,
                 candidates: int = 5) -> Dict[str, Result]:
    """Match each distinct name (blank names are the caller's to leave out).

    Names neither matched nor failed (only when cancelled part-way) are absent."""
    names = [n for n in dict.fromkeys(names) if tidy(n)]
    parsed = {n: parse_qualifier(n) for n in names}
    out: Dict[str, Result] = {}
    try:
        exact = _match_exact(uksi, sorted({b.lower() for _, b in parsed.values()}))
    except Exception as e:                          # not the same as "not found" (I7)
        return {n: LookupFailure(n, "error", str(e)) for n in names}

    for name in names:
        if cancelled():
            break
        qualifier, bare = parsed[name]
        try:
            hit = exact.get(bare.lower())
            if qualifier in ("agg.", "s.l."):
                aggs = aggregate_taxa(uksi, bare, qualifier)
                if aggs and (len(aggs) == 1 or aggs[0].rank != aggs[1].rank):
                    t = aggs[0]
                    what = t.rank if t.rank in BROAD_RANKS else (t.qualifier or t.rank or "aggregate")
                    typed = _typed_note(name, t.scientific_name)
                    warn = (f"{'Aggregate' if qualifier == 'agg.' else 'Sensu lato'}: matched to "
                            f"'{t.scientific_name}' ({what})") if typed else ""
                    out[name] = NameMatch(name, "exact", qualifier, bare, t,
                                          notes=[n for n in [typed] if n],
                                          warnings=[w for w in [warn] if w])
                    continue
                if len(aggs) > 1:
                    out[name] = LookupFailure(name, "ambiguous", candidates=aggs)
                    continue
            if hit is None:
                out[name] = LookupFailure(name, "not_found",
                                          candidates=search_candidates(uksi, bare, candidates))
                continue
            if hit[0] == "ambiguous":
                out[name] = LookupFailure(name, "ambiguous", candidates=list(hit[1]))
                continue
            t, how, choice_note = hit
            notes = [_typed_note(name, t.scientific_name)]
            warnings = []
            if how == "synonym":
                notes = [f"Imported as '{name}' (UKSI synonym of '{t.scientific_name}')"]
                warnings.append(f"Synonym: matched to '{t.scientific_name}'")
            if choice_note:
                notes.append(choice_note)
            if qualifier == "cf.":
                warnings.append(f"cf. identification: matched to '{t.scientific_name}' (uncertain ID)")
                notes.append("cf. = uncertain identification")
            elif qualifier in ("agg.", "s.l."):
                warnings.append(NO_AGGREGATE)
            out[name] = NameMatch(name, how, qualifier, bare, t, notes=[n for n in notes if n],
                                  warnings=warnings)
        except Exception as e:
            out[name] = LookupFailure(name, "error", str(e))
    return out
