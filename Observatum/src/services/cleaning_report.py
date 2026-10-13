"""The cleaning report (backlog B, claude/38 answers 12-14): the records Wil wants to tidy in
iRecord, one list per problem. Read-only; no Qt (the screen is views/stats/cleaning_dashboard.py,
the spreadsheet is services/cleaning_export.py).

Sources: Observation (observations), Recording Scheme (recording_scheme) and Contributed
(contributed_observations: records other people sent; no iRecord ID, so double-click opens the
record in Observatum). Every matching
record is listed, whatever the species-counting switches say: this is the list of the
excluded / problem records. A record with several problems is listed under each.

Problems:
    genus, family_plus, agg, sl, subsp, hybrid
                the name kinds from shared/record_kinds.classify (THE rule), with UKSI's rank
                for the record's TVK (or its current TVK) where the record holds no rank.
                s.s. is not a problem (it counts as the plain species, answer 4).
    no_tvk      no TVK, or a TVK UKSI can't place (not current and no name_map / tvk_remap).
    synonym     the same current species held under two different TVKs or two different
                names: the stored TVKs are resolved through UKSI (shared/species_filter.
                current_tvk_map) and a species is flagged only when two DISTINCT stored TVKs,
                or two distinct names (compared on genus + epithet, qualifiers such as agg.,
                s.l., sp. and bracketed notes ignored), resolve to the SAME current TVK.
    date        no date, or a vague one: date_type other than D (single day) -- DD day range,
                O month, OO month range, Y year, YY year range, ... (decision 9).
    early       dated before 1700 (Q65, 12 Oct): almost certainly a placeholder or a typing
                slip (e.g. Alosterna tabacicolor 1500, the Cerambycidae Dataset's 1675), and
                such a record lands in the earliest date class of a map. Listed only.
    grid        no grid ref, or 10 km or coarser (hectad, 100 km square). Tetrads (2 km) and
                quadrants (5 km) are not coarse.
    latlon      the grid ref field holds latitude/longitude text ("49.4557N2.5591W"), not a
                grid ref (decision 6, 11 Oct; listed only -- nothing is converted).
    returned    (Observation only) a record Wil removed here with "Deleted in iRecord --
                remove here" that a later download brought back: still hidden, listed so he
                can check iRecord and "Show again" if he wants it (F72, shared/hidden_records).
Verification status is not a problem (answer 12). A scheme count of 0 is presence
(decision 8), so counts are not checked at all.

Left out (F71, 13 Oct): the Recording Scheme's marked NBN copies of iRecord records
(shared/scheme_duplicates.py, THE rule) unless include_copies is asked for -- on Wil's PC
that takes the scheme from 110,510 to about 76,389 records checked (34,121 marked; on a
database without the duplicate_of column nothing changes); and hidden observations
(shared/hidden_records.py), which appear only under "returned".
"""
from __future__ import annotations

import re
import time
from functools import lru_cache
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

from shared.db_open import connect_ro
from shared.hidden_records import RETURNED_LABEL
from shared.record_kinds import KIND_LABELS, classify, ranks_for_tvks
from shared.species_filter import current_tvk_map

# Link to one record in iRecord: the one pattern lives in shared/irecord_links.py (confirmed
# by Wil 11 Oct, R9-3); re-exported here for cleaning_export and the dashboard.
from shared.irecord_links import IRECORD_URL, irecord_url  # noqa: F401

SOURCES: List[Tuple[str, str]] = [("observations", "Observation"),
                                  ("recording_scheme", "Recording Scheme"),
                                  ("contributed_observations", "Contributed")]

NAME_KINDS = ("genus", "family_plus", "agg", "sl", "subsp", "hybrid")
PROBLEMS: List[Tuple[str, str]] = [(k, KIND_LABELS[k]) for k in NAME_KINDS] + [
    ("no_tvk", "No TVK / TVK not in UKSI"),
    ("synonym", "Synonyms counted twice"),
    ("date", "No date or vague date"),
    ("early", "Date before 1700"),
    ("grid", "No grid ref or coarse (10 km+)"),
    ("latlon", "Not a grid ref (looks like latitude/longitude)"),
    ("returned", RETURNED_LABEL),
]
PROBLEM_LABELS = dict(PROBLEMS)
OBSERVATION_ONLY = ("returned",)          # tiles that mean nothing for the other sources

DATE_TYPE_LABELS = {
    "DD": "day range", "O": "month only", "OO": "month range", "Y": "year only",
    "YY": "year range", "-Y": "up to a year", "Y-": "from a year", "P": "season",
    "C": "century", "U": "unknown date", "ND": "no date",
}

_COLUMNS = ("id", "irecord_id", "species_name", "species_tvk", "taxon_rank", "date",
            "date_type", "grid_ref", "site_name", "recorder", "latitude", "longitude")
# where the record came from (scheme: the dataset / iRecord survey; contributed: who sent it),
# first column present
_SOURCE_COLUMNS = ("source", "dataset_name", "contributor")

EARLIEST_YEAR = 1700          # a record dated before this is listed under "early" (Q65)


# ------------------------------------------------------------------ dates and grid refs

def date_problem(date: Optional[str], date_type: Optional[str]) -> Optional[str]:
    """'No date', 'Vague date: month only (O)' ..., or None for an exact single day."""
    if not (date or "").strip():
        return "No date"
    dt = (date_type or "").strip().upper()
    if dt in ("", "D"):
        return None
    return f"Vague date: {DATE_TYPE_LABELS.get(dt, 'not a single day')} ({dt})"


def early_date_problem(date: Optional[str], earliest: int = EARLIEST_YEAR) -> Optional[str]:
    """'Dated 1500 (before 1700)' when the date's year is before `earliest`, else None.
    Only a date that starts with a 4-digit year is read (stored dates are ISO)."""
    m = re.match(r"\s*(\d{4})", date or "")
    if not m:
        return None
    year = int(m.group(1))
    return f"Dated {year} (before {earliest})" if year < earliest else None


def display_date(date: Optional[str], date_type: Optional[str]) -> str:
    """The stored date, cut to what a vague one really says (1956-06-01, O -> 1956-06)."""
    d = (date or "").strip()
    dt = (date_type or "").strip().upper()
    if dt in ("O", "OO") and len(d) >= 7:
        return d[:7]
    if dt in ("Y", "YY", "-Y", "Y-") and len(d) >= 4:
        return d[:4]
    return d


_LATLON = re.compile(r"^~?\d{1,2}(\.\d+)?[NS]\d{1,3}(\.\d+)?[EW]$")
_GB = re.compile(r"^([A-Z]{2})(\d*)$")
_IE = re.compile(r"^([A-HJ-Z])(\d*)$")
_TETRAD = re.compile(r"^[A-Z]{1,2}\d\d[A-NP-Z]$")
_QUADRANT = re.compile(r"^[A-Z]{1,2}\d\d(NE|NW|SE|SW)$")


@lru_cache(maxsize=65536)
def grid_size_m(ref: Optional[str]) -> Optional[int]:
    """Square size in metres of a GB or Irish grid ref (tetrad 2000, quadrant 5000, hectad
    10000, bare 100 km letters 100000); 0 for lat/long text; None when unreadable or empty."""
    s = (ref or "").strip().upper().replace(" ", "")
    if not s:
        return None
    if _LATLON.match(s):
        return 0
    s = s.lstrip("~")
    if _QUADRANT.match(s):
        return 5000
    if _TETRAD.match(s):
        return 2000
    m = _GB.match(s) or _IE.match(s)
    if not m or len(m.group(2)) % 2 or len(m.group(2)) > 10:
        return None
    return 10 ** (5 - len(m.group(2)) // 2)


def latlon_problem(ref: Optional[str]) -> Optional[str]:
    """'Latitude/longitude text, not a grid ref' when the grid ref field holds lat/long."""
    if (ref or "").strip() and grid_size_m(ref) == 0:
        return "Latitude/longitude text, not a grid ref"
    return None


def grid_problem(ref: Optional[str], has_latlon: bool = False) -> Optional[str]:
    """'No grid ref', 'Coarse grid ref (10 km)', 'Grid ref not readable', or None."""
    if not (ref or "").strip():
        return "No grid ref (lat/long held)" if has_latlon else "No grid ref"
    size = grid_size_m(ref)
    if size is None:
        return "Grid ref not readable"
    if size >= 10000:
        return f"Coarse grid ref ({size // 1000} km)"
    return None


# ------------------------------------------------------------------ synonyms

_QUALIFIERS = re.compile(r"\b(agg|spp|sp|sensu\s+lato|sensu\s+stricto)\b\.?|\bs\.\s?[ls]\.",
                         re.IGNORECASE)


def base_name(name: Optional[str]) -> str:
    """Genus + epithet, lower case, qualifiers and bracketed notes dropped: the part of a name
    that differs between two names for one species."""
    n = re.sub(r"\([^)]*\)", " ", name or "")
    n = _QUALIFIERS.sub(" ", n)
    return " ".join(n.lower().split()[:2])


def synonym_groups(pairs: Iterable[Tuple[str, str]], current: Dict[str, Optional[str]]
                   ) -> Dict[Tuple[str, str], Tuple[str, List[str]]]:
    """{(stored tvk, stored name): (current tvk, the OTHER names it shares that species with)}
    for every pair whose current species is also held under another TVK or name."""
    by_cur: Dict[str, set] = defaultdict(set)
    for tvk, name in pairs:
        cur = current.get(tvk) if tvk else None
        if cur:
            by_cur[cur].add((tvk, name or ""))
    out = {}
    for cur, members in by_cur.items():
        tvks = {t for t, _ in members}
        bases = {base_name(n) for _, n in members}
        if len(tvks) < 2 and len(bases) < 2:
            continue
        for t, n in members:
            others = sorted({m for tt, m in members if (tt, m) != (t, n)
                             and (tt != t or base_name(m) != base_name(n))})
            if others:
                out[(t, n)] = (cur, others)
    return out


# ------------------------------------------------------------------ the report

@dataclass
class CleaningRow:
    record_id: int
    species: str
    rank: str
    date: str
    grid_ref: str
    site: str
    recorder: str
    irecord_id: Optional[int]
    problem: str          # key in PROBLEM_LABELS
    detail: str           # what exactly is wrong, in plain words
    dataset: str = ""     # where the record came from (stored source / dataset_name)


@dataclass
class CleaningReport:
    source: str                                   # table name
    total_records: int = 0                        # records checked (copies / hidden left out)
    rows: Dict[str, List[CleaningRow]] = field(default_factory=dict)
    records_with_problem: int = 0
    seconds: float = 0.0
    include_copies: bool = False                  # scheme: NBN copies of iRecord records in
    copies_marked: int = 0                        # scheme: rows marked as such (0 = no column)
    hidden_records: int = 0                       # observations: removed here, still in iRecord

    @property
    def copies_note(self) -> str:
        """One line saying what was done about the scheme's NBN copies ('' elsewhere)."""
        if self.source != "recording_scheme":
            return ""
        if not self.copies_marked:
            return "NBN copies of iRecord records: none marked in this database (every row checked)."
        if self.include_copies:
            return (f"NBN copies of iRecord records included: {self.copies_marked:,} marked copies "
                    f"are among the records checked.")
        return (f"NBN copies of iRecord records left out: {self.copies_marked:,} marked copies "
                f"not checked (tick 'Include NBN copies of iRecord records' to add them).")

    @property
    def counts(self) -> Dict[str, int]:
        return {k: len(self.rows.get(k, [])) for k, _ in PROBLEMS}

    @property
    def source_label(self) -> str:
        return dict(SOURCES).get(self.source, self.source)


def _scope_sql(conn, source: str, include_copies: bool) -> str:
    """The WHERE fragment leaving out the scheme's marked copies (unless asked for) and
    hidden observations -- through the two shared rules."""
    if source == "recording_scheme" and not include_copies:
        from shared.scheme_duplicates import live_sql
        return live_sql(conn)
    if source == "observations":
        from shared.hidden_records import live_sql
        return live_sql(conn)
    return ""


def _returned_rows(conn) -> Dict[int, Tuple[str, str]]:
    """{observation id: (hidden_at, returned_at)} for hidden records a download brought back."""
    from shared.hidden_records import returned
    return {r[0]: (r[3] or "", r[4] or "") for r in returned(conn)}


def build_report(main_db, uksi_db, source: str, include_copies: bool = False) -> CleaningReport:
    """The cleaning report for one source table. Read-only; UKSI lookups batched.
    include_copies: scheme only -- check the marked NBN copies of iRecord records too."""
    if source not in dict(SOURCES):
        raise ValueError(f"unknown source {source!r}")
    t0 = time.perf_counter()
    conn = connect_ro(main_db)
    copies_marked = hidden_count = 0
    returned_at: Dict[int, Tuple[str, str]] = {}
    try:
        have = {r[1] for r in conn.execute(f"PRAGMA table_info({source})")}
        if not have:                         # an older database without this table
            rows = []
        else:
            src_col = next((c for c in _SOURCE_COLUMNS if c in have), "NULL")
            cols = [c if c in have else "NULL" for c in _COLUMNS]   # contributed: no iRecord
            select = f"SELECT {', '.join(cols)}, {src_col} FROM {source} WHERE 1"
            rows = conn.execute(select + _scope_sql(conn, source, include_copies)).fetchall()
            if source == "recording_scheme" and "duplicate_of" in have:
                copies_marked = conn.execute(
                    f"SELECT COUNT(*) FROM {source} WHERE duplicate_of IS NOT NULL").fetchone()[0]
            if source == "observations" and "hidden_at" in have:
                hidden_count = conn.execute(
                    f"SELECT COUNT(*) FROM {source} WHERE hidden_at IS NOT NULL").fetchone()[0]
                returned_at = _returned_rows(conn)
                if returned_at:
                    marks = ",".join("?" * len(returned_at))
                    rows += conn.execute(f"{select} AND id IN ({marks})",
                                         list(returned_at)).fetchall()
    finally:
        conn.close()
    pairs = {(r[3] or "", r[2] or "") for r in rows}
    stored_tvks = {t for t, _ in pairs if t}
    current = current_tvk_map(stored_tvks, str(uksi_db)) if stored_tvks else {}
    need_rank = {r[3] for r in rows if r[3] and not (r[4] or "").strip()}
    uksi_ranks: Dict[str, str] = {}
    if need_rank:
        u = connect_ro(uksi_db)
        try:
            uksi_ranks = ranks_for_tvks(u, need_rank | {current.get(t) for t in need_rank
                                                        if current.get(t)})
        finally:
            u.close()
    synonyms = synonym_groups(pairs, current)

    report = CleaningReport(source=source, total_records=len(rows) - len(returned_at),
                            rows={k: [] for k, _ in PROBLEMS}, include_copies=include_copies,
                            copies_marked=copies_marked, hidden_records=hidden_count)
    kind_cache: Dict[Tuple[str, str], frozenset] = {}
    flagged = set()
    for (rid, irec, name, tvk, rank, date, dtype, grid, site, recorder, lat, lon, ds) in rows:
        name, tvk = name or "", tvk or ""
        if rid in returned_at:               # hidden: listed under "returned" only
            h, r = returned_at[rid]
            report.rows["returned"].append(CleaningRow(
                record_id=rid, species=name, rank=(rank or "").strip(),
                date=display_date(date, dtype), grid_ref=grid or "", site=site or "",
                recorder=recorder or "", irecord_id=irec, problem="returned",
                detail=f"Removed here {h[:16].replace('T', ' ')}; came back from iRecord "
                       f"{r[:16].replace('T', ' ')} (still hidden)", dataset=ds or ""))
            continue
        rank = (rank or "").strip() or uksi_ranks.get(tvk) or \
            uksi_ranks.get(current.get(tvk) or "", "")
        problems: List[Tuple[str, str]] = []
        key = (name, rank)
        if key not in kind_cache:
            kind_cache[key] = classify(name, rank)
        for k in NAME_KINDS:
            if k in kind_cache[key]:
                problems.append((k, PROBLEM_LABELS[k]))
        if not tvk:
            problems.append(("no_tvk", "No TVK"))
        elif current.get(tvk) is None:
            problems.append(("no_tvk", f"TVK {tvk} not found in UKSI"))
        syn = synonyms.get((tvk, name))
        if syn:
            problems.append(("synonym", "Same species as: " + "; ".join(syn[1])))
        d = date_problem(date, dtype)
        if d:
            problems.append(("date", d))
        e = early_date_problem(date)
        if e:
            problems.append(("early", e))
        g = grid_problem(grid, lat is not None and lon is not None)
        if g:
            problems.append(("grid", g))
        ll = latlon_problem(grid)
        if ll:
            problems.append(("latlon", ll))
        if not problems:
            continue
        flagged.add(rid)
        for k, detail in problems:
            report.rows[k].append(CleaningRow(
                record_id=rid, species=name, rank=rank, date=display_date(date, dtype),
                grid_ref=grid or "", site=site or "", recorder=recorder or "",
                irecord_id=irec, problem=k, detail=detail, dataset=ds or ""))
    for lst in report.rows.values():
        lst.sort(key=lambda r: (r.species.lower(), r.date, r.record_id))
    report.records_with_problem = len(flagged)
    report.seconds = time.perf_counter() - t0
    return report
