"""scheme_duplicates -- Recording Scheme records held twice, the iRecord / NBN copies (fault
F53, Wil's answer Q59, 12 Oct 2026): count each record once, keep the iRecord copy, FLAG the
NBN copy (never delete it), reversibly.

THE rule, used everywhere the scheme is counted, mapped, charted or exported:

  * The column `recording_scheme.duplicate_of` holds, on an NBN Atlas row, the id of the
    iRecord row it copies. NULL = a record in its own right (every iRecord row, and every
    NBN row that is not a copy). It is added and filled by
    scripts/mark_scheme_irecord_duplicates.py (dry run first, backup, --undo clears it).
  * live_sql(db) is the WHERE fragment that leaves the marked rows out:
        " AND duplicate_of IS NULL"   (or "" on a database without the column yet)
    shared/species_counting.not_excluded_sql / only_excluded_sql / export_sql add it for
    recording_scheme, so every screen that follows the species-counting switches (Scheme
    stats and dashboard, Species lookup, phenology and month lists, Mapping, Quick stats,
    exports) skips the copies through that one door; the scheme stats service adds it to
    its family scope (grid squares, month charts); the Scheme tab adds it unless its
    "Show duplicates" toggle is on.

The match (moved here from scripts/report_scheme_duplicates.py, its "same iRecord id" tier,
so the report and the marking cannot drift): an NBN Atlas row (nbn_atlas_id set, no
irecord_id) whose occurrence ID is an iRecord row's irecord_id, with the same TVK and date.
The Atlas may blur a sensitive record's grid ref, so the grid ref is not required. When two
iRecord rows carry the same irecord_id (an "exact" duplicate, not handled here) the copy
points at the lower id. The exact / likely / possible tiers are NOT marked (left for the
final dataset, M1).
"""
from __future__ import annotations

import sqlite3
import threading
from typing import Dict, Iterable, List, Tuple

from shared.record_match import blank

COLUMN = "duplicate_of"
TABLE = "recording_scheme"
MATCH_COLUMNS = ("id", "irecord_id", "nbn_atlas_id", "occurrence_id", "species_tvk", "date")

_lock = threading.RLock()
_has: Dict[str, bool] = {}            # db file -> column present (True is never re-checked)


def route(row: dict) -> str:
    """How a scheme row came in: 'iRecord', 'NBN Atlas' or 'Other' (as the Scheme filter
    bar's Source, services/filter_builder.SCHEME_SOURCES)."""
    if not blank(row.get("irecord_id")):
        return "iRecord"
    if not blank(row.get("nbn_atlas_id")):
        return "NBN Atlas"
    return "Other"


def match_pairs(rows: Iterable[dict]) -> List[Tuple[dict, dict]]:
    """[(iRecord row, NBN row)] for every NBN Atlas row that re-supplies an iRecord record:
    occurrence_id == the iRecord row's irecord_id, same TVK and same date. An NBN row whose
    occurrence ID two iRecord rows share gets a pair with each (the caller keeps the lower
    id); rows need the MATCH_COLUMNS keys."""
    rows = list(rows)
    by_irecord: Dict[str, List[dict]] = {}
    for r in rows:
        if route(r) == "iRecord":
            by_irecord.setdefault(str(r["irecord_id"]).strip(), []).append(r)
    out = []
    for r in rows:
        if route(r) != "NBN Atlas" or blank(r.get("occurrence_id")):
            continue
        for i in by_irecord.get(str(r["occurrence_id"]).strip(), ()):
            if i["species_tvk"] == r["species_tvk"] and i["date"] == r["date"]:
                out.append((i, r))
    return out


def copies(rows: Iterable[dict]) -> Dict[int, int]:
    """{NBN row id: id of the iRecord row it copies} -- what duplicate_of should hold."""
    out: Dict[int, int] = {}
    for i, r in match_pairs(rows):
        if r["id"] not in out or i["id"] < out[r["id"]]:
            out[r["id"]] = i["id"]
    return out


def load_rows(conn: sqlite3.Connection) -> List[dict]:
    """The MATCH_COLUMNS of every scheme row (NULL for a column the table lacks)."""
    have = {r[1] for r in conn.execute(f"PRAGMA table_info({TABLE})")}
    sel = ", ".join(c if c in have else f"NULL AS {c}" for c in MATCH_COLUMNS)
    return [dict(zip(MATCH_COLUMNS, r)) for r in conn.execute(f"SELECT {sel} FROM {TABLE}")]


# ------------------------------------------------------------------ the WHERE fragment

def _columns(conn) -> set:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({TABLE})")}


def has_column(db) -> bool:
    """True when the scheme table has duplicate_of. `db`: a sqlite3 connection, an
    execute(sql) callable returning rows, a DatabaseManager (main_db_path) or a path."""
    try:
        if isinstance(db, sqlite3.Connection):
            return COLUMN in _columns(db)
        if callable(db) and not isinstance(db, (str, bytes)):
            return any((r[1] if not hasattr(r, "keys") else r["name"]) == COLUMN
                       for r in (db(f"PRAGMA table_info({TABLE})") or ()))
        path = str(getattr(db, "main_db_path", db) or "")
        if not path:
            return False
        with _lock:
            if _has.get(path):
                return True
            from shared.db_open import connect_ro
            conn = connect_ro(path)
            try:
                found = COLUMN in _columns(conn)
            finally:
                conn.close()
            if found:
                _has[path] = True
            return found
    except (sqlite3.Error, OSError, TypeError, ValueError):
        return False


def live_sql(db, prefix: str = "") -> str:
    """' AND <prefix>duplicate_of IS NULL' -- leave the marked copies out -- or '' when the
    database has no duplicate_of column yet. prefix e.g. 'rs.'."""
    return f" AND {prefix}{COLUMN} IS NULL" if has_column(db) else ""


def prefix_of(col: str) -> str:
    """'rs.id' -> 'rs.'; 'id' -> ''."""
    return col.rsplit(".", 1)[0] + "." if "." in col else ""


def reason(kept_id) -> str:
    """The words shown for a marked row ('Duplicate of #123')."""
    return f"Duplicate of #{kept_id}"


def forget() -> None:
    """Forget the cached column checks (tests; after the marking script ran)."""
    with _lock:
        _has.clear()
