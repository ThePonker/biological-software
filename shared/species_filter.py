"""Species text in a record table's filter box -> the records, by TVK (backlog item 1,
SRCH15/17, OBS-09; 10 Oct 2026). No Qt.

    f = species_filter("Spotted Longhorn", present_tvks)
    clause, params = f.sql()              # for a WHERE on observations / recording_scheme / ...
    f.matches(row_tvk, row_name, row_common)   # the same test for rows already in memory

What the text selects (shared/species_search.py does the matching):
  * the exact name, if the text is one (a scientific name first, else an old name or a
    common name): "Nicrophorus vespillo" is that species, not N. vespilloides as well;
  * otherwise every taxon the text matches as typed ("rhag mor", "spotted longhorn");
  * otherwise its close spellings ("Rhagium mordx").
A taxon above species takes everything below it ("Rhagium", "Cerambycidae"), and an
old name its current taxon. A record is chosen by its TVK, so the record's own common_name
column (often blank) no longer decides it -- but no filter finds fewer records than the
old match by name (every typed word in species_name or common_name) did (review 10 Oct):
  * text UKSI doesn't hold ("Tawny Longhorn Beetle", "agg", "... red scutellum"): the old
    match by name, alone;
  * text that only partly matches UKSI names ("rhag mor", "vespillo"): the TVKs OR the old
    match by name;
  * text that is exactly a UKSI name ("Nicrophorus vespillo"): the TVKs, OR a record whose
    species_name or common_name is the text itself (whole, any case), OR -- for a record
    with no TVK or one UKSI doesn't hold -- the old match by name. So N. vespilloides
    stays out.
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Set

from shared.species_search import fold, fold_words, get_index

_SAFE_TVK = re.compile(r"^[A-Za-z0-9:_.\-]+$")
_current_cache: Dict[str, Optional[str]] = {}


def choose_taxa(text: str, db_path: Optional[str] = None) -> List[dict]:
    """The taxa a filter box's text stands for (best tier only -- see the module docstring)."""
    return _choose(text, db_path)[0]


def _choose(text: str, db_path: Optional[str] = None) -> tuple:
    """(the taxa, True if the text is exactly their name) -- see choose_taxa."""
    from shared.species_lookup import parse_qualifier
    results = get_index(db_path).search(text, limit=None)
    if not results:
        return [], False
    qualifier, bare = parse_qualifier(text)
    if qualifier:
        # the taxon whose full name, qualifier included, is the text: "Oligia strigilis
        # agg." is the aggregate (its own records), not the species the search puts first
        want = (qualifier, fold(bare))

        def full(name):
            q, b = parse_qualifier(name or "")
            return (q, fold(b))
        named = [r for r in results if want in (full(r.get("label")), full(r["scientific_name"]))]
        if named:
            return named, True
    exact = [r for r in results if r["search_key"][0] == 0]
    if exact:
        chosen = [r for r in exact if r["matched_kind"] == "scientific"] or exact
        is_exact = True
    else:
        is_exact = False
        # the best kind of match only: words as typed (start of a word), else inside a
        # word, else a close spelling -- and of those, the ones where most typed words are
        # whole words ("N. vespillo": N. vespillo, not N. vespilloides)
        cls = {1: 1, 2: 1, 3: 2, 4: 3}
        best = min(cls[r["search_key"][0]] for r in results)
        chosen = [r for r in results if cls[r["search_key"][0]] == best]
        fewest = min(r["search_key"][3] for r in chosen)
        chosen = [r for r in chosen if r["search_key"][3] == fewest]
    if qualifier in ("agg.", "s.l."):
        broad = [r for r in chosen if r["search_key"][2] == 0]
        chosen = broad or chosen
    return chosen, is_exact


def _current_tvks(tvks: Iterable[str], db_path: Optional[str]) -> Dict[str, Optional[str]]:
    """{record TVK not in UKSI's taxa: the current TVK UKSI maps it to, or None}."""
    need = [t for t in tvks if t not in _current_cache]
    if need:
        idx = get_index(db_path)
        try:
            import paths
            from shared.db_open import connect_ro
            conn = connect_ro(db_path or paths.UKSI_DB)
            try:
                for i in range(0, len(need), 400):
                    chunk = need[i:i + 400]
                    ph = ",".join("?" * len(chunk))
                    found = dict(conn.execute(
                        f"SELECT tvk, recommended_tvk FROM name_map WHERE tvk IN ({ph})", chunk))
                    try:
                        found.update({k: v for k, v in conn.execute(
                            f"SELECT old_tvk, new_tvk FROM tvk_remap WHERE old_tvk IN ({ph}) "
                            f"AND new_tvk IS NOT NULL", chunk) if k not in found})
                    except Exception:
                        pass
                    for t in chunk:
                        cur = found.get(t)
                        _current_cache[t] = cur if cur in idx.pos else None
            finally:
                conn.close()
        except Exception as e:
            print(f"[species_filter] old TVKs not mapped: {e}")
            for t in need:
                _current_cache[t] = None
    return {t: _current_cache.get(t) for t in tvks}


def current_tvk_map(tvks: Iterable[str], db_path: Optional[str] = None) -> Dict[str, Optional[str]]:
    """{record TVK: the current UKSI TVK it stands for (itself if UKSI holds it), or None}."""
    idx = get_index(db_path)
    tvks = {t for t in tvks if t}
    odd = [t for t in tvks if t not in idx.pos]
    out: Dict[str, Optional[str]] = {t: t for t in tvks if t in idx.pos}
    out.update(_current_tvks(odd, db_path) if odd else {})
    return out


def tvks_under(wanted: Iterable[str], present_tvks: Iterable[str], db_path: Optional[str] = None
               ) -> tuple:
    """(the present TVKs at or below any wanted taxon, the present TVKs UKSI can't place).
    A record TVK under an old name counts as its current taxon. Used by SpeciesFilter and
    by the Mapping tab's multi-taxon selection (several species, genera, families...)."""
    idx = get_index(db_path)
    wanted = set(wanted)
    chosen: Set[str] = set()
    unknown: Set[str] = set()
    anc_cache: Dict[str, bool] = {}
    for t, c in current_tvk_map(present_tvks, db_path).items():
        if c is None:
            unknown.add(t)
            continue
        if c not in anc_cache:
            anc_cache[c] = any(a in wanted for a in idx.ancestors(c))
        if anc_cache[c]:
            chosen.add(t)
    return chosen, unknown


class SpeciesFilter:
    """The records a species filter text selects, out of a table's TVKs (see module doc)."""

    def __init__(self, text: str, present_tvks: Iterable[str], db_path: Optional[str] = None,
                 by_name: bool = False):
        self.text = (text or "").strip()
        self.words = [w for w in self.text.split() if w]
        self.taxa: List[dict] = []
        self.tvks: Set[str] = set()        # the table's TVKs that are chosen
        self.unknown: Set[str] = set()     # the table's TVKs UKSI can't place (matched by name)
        self.exact = False                  # the text is exactly the chosen taxa's name
        self.by_name_only = by_name or len("".join(fold_words(self.text))) < 2
        if self.by_name_only:
            return
        self.taxa, self.exact = _choose(self.text, db_path)
        if not self.taxa:                   # nothing in UKSI: the old match by name
            self.by_name_only = True
            return
        self.tvks, self.unknown = tvks_under({r["tvk"] for r in self.taxa}, present_tvks, db_path)

    # ------------------------------------------------------------ in memory

    def _name_hit(self, *names) -> bool:
        hay = " ".join(n for n in names if n).lower()
        return all(w.lower() in hay for w in self.words)

    def matches(self, tvk, *names) -> bool:
        """Does a record with this TVK and these names (species_name, common_name) pass?"""
        if self.by_name_only:
            return self._name_hit(*names)
        if tvk and tvk not in self.unknown and tvk in self.tvks:
            return True
        if not self.exact or not tvk or tvk in self.unknown:
            return self._name_hit(*names)
        low = self.text.lower()
        return any((n or "").strip().lower() == low for n in names)

    # ------------------------------------------------------------ SQL

    def sql(self, tvk_col: str = "species_tvk",
            name_cols=("species_name", "common_name")) -> tuple:
        """(clause, params) for a WHERE: the chosen TVKs, or a name match where the record's
        TVK is blank or unknown to UKSI."""
        hay = " || ' ' || ".join(f"COALESCE({c}, '')" for c in name_cols)
        name_sql = " AND ".join(f"({hay}) LIKE ? ESCAPE '\\'" for _ in self.words) or "1=0"
        params = ["%" + w.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
                  for w in self.words]
        if self.by_name_only:
            return f"({name_sql})", params
        by_tvk = f"{tvk_col} IN ({_literals(self.tvks)})" if self.tvks else "0"
        if not self.exact:
            return f"({by_tvk} OR ({name_sql}))", params
        no_tvk = f"{tvk_col} IS NULL OR {tvk_col} = ''"
        if self.unknown:
            no_tvk += f" OR {tvk_col} IN ({_literals(self.unknown)})"
        same = " OR ".join(f"LOWER(TRIM(COALESCE({c}, ''))) = ?" for c in name_cols)
        return (f"({by_tvk} OR (({no_tvk}) AND {name_sql}) OR {same})",
                params + [self.text.lower()] * len(name_cols))


def filter_names(text: str, names: Iterable[str], db_path: Optional[str] = None) -> Set[str]:
    """For lists that hold species names but no TVKs (the scheme dashboard, the collection
    sidebar): the names the filter text selects. Each name is placed through UKSI (its
    scientific or old name); names UKSI doesn't hold are matched by name."""
    names = [n for n in dict.fromkeys(names) if n]
    try:
        idx = get_index(db_path)
        tvk_of = {n: idx.tvk_for_name(n) for n in names}
    except Exception as e:
        print(f"[species_filter] by name only ({e})")
        tvk_of = {n: None for n in names}
    f = species_filter(text, {t for t in tvk_of.values() if t}, db_path)
    return {n for n in names if f.matches(tvk_of[n], n)}


def _literals(tvks: Iterable[str]) -> str:
    """TVKs as SQL string literals (a table can hold thousands -- more than the parameter
    limit of older SQLite builds); anything that isn't a plain TVK is quoted safely."""
    out = []
    for t in sorted(tvks):
        if not _SAFE_TVK.match(t):
            t = t.replace("'", "''")
        out.append(f"'{t}'")
    return ",".join(out)


def species_filter(text: str, present_tvks: Iterable[str], db_path: Optional[str] = None
                   ) -> SpeciesFilter:
    """SpeciesFilter, or -- if uksi.db can't be indexed -- the old match by name (every word
    in species_name or common_name), so a filter box never stops working."""
    try:
        return SpeciesFilter(text, present_tvks, db_path)
    except Exception as e:
        print(f"[species_filter] by name only ({e})")
        return SpeciesFilter(text, (), db_path, by_name=True)


def table_tvks(execute, table: str, tvk_col: str = "species_tvk") -> Set[str]:
    """The distinct TVKs of a table. execute(sql) returns rows (tuples or sqlite3.Row)."""
    rows = execute(f"SELECT DISTINCT {tvk_col} FROM {table} WHERE {tvk_col} IS NOT NULL "
                   f"AND {tvk_col} != ''") or []
    return {r[0] for r in rows if r[0]}


def sql_for_table(text: str, execute, table: str, tvk_col: str = "species_tvk",
                  name_cols=("species_name", "common_name")) -> tuple:
    """(clause, params) for the species text on one table -- the usual one-call use.
    If the shared index can't be built, the old name match (every word) is used."""
    return species_filter(text, table_tvks(execute, table, tvk_col)).sql(tvk_col, name_cols)


__all__ = ["SpeciesFilter", "species_filter", "choose_taxa", "table_tvks", "sql_for_table",
           "filter_names", "tvks_under", "current_tvk_map"]
