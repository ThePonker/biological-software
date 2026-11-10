"""data_reference -- the free-text "Reference" kept on records (26 Oct 2026). No Qt.

For data that came from a person or a source rather than iRecord / NBN ("Joe Bloggs, data to
1990"), so it can be found again. Stored as data_reference (TEXT) on observations,
recording_scheme and contributed_observations. The column is added by
scripts/add_data_reference.py; without it everything works as before and the Reference
field is shown disabled (TOOLTIP_MISSING).
"""
from __future__ import annotations

import os
from typing import List, Optional

COLUMN = "data_reference"
TABLES = ("observations", "recording_scheme", "contributed_observations")
INDEX_FMT = "idx_{table}_data_reference"
# Private notes that stay out of every client-facing export (Wil, 10 Nov 2026). The one list:
# ExportService.export_to_csv drops these when it is asked for "all columns". Backups and other
# exports that are not for clients simply do not use it.
CLIENT_EXPORT_EXCLUDED = (COLUMN,)
MAX_SUGGESTIONS = 15
TOOLTIP_MISSING = "Run scripts\\add_data_reference.py to add the Reference column"
TOOLTIP_FIELD = ("For data that came from a person or a source rather than iRecord/NBN, "
                 "so you can find it again later. Names already used are suggested as you type.")
PLACEHOLDER = "e.g. Joe Bloggs, data to 1990"

_cache: dict = {}


def clear_cache() -> None:
    _cache.clear()


def _db_key(conn) -> Optional[str]:
    try:
        f = conn.execute("PRAGMA database_list").fetchone()[2]
        return os.path.abspath(f) if f else None
    except Exception:
        return None


def has_column(conn, table: str) -> bool:
    """True if `table` has data_reference. Cached per database file and table."""
    key = _db_key(conn)
    if key is not None and (key, table) in _cache:
        return _cache[(key, table)]
    try:
        found = COLUMN in {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    except Exception:
        return False
    if key is not None:
        _cache[(key, table)] = found
    return found


def ensure_schema(conn) -> List[str]:
    """Add the column and its index to every table that exists. Returns the tables changed.
    The caller owns the transaction (scripts/add_data_reference.py wraps it in BEGIN IMMEDIATE ... COMMIT)."""
    changed = []
    for t in TABLES:
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({t})")}
        if not cols:
            continue
        if COLUMN not in cols:
            conn.execute(f"ALTER TABLE {t} ADD COLUMN {COLUMN} TEXT")
            changed.append(t)
        conn.execute(f"CREATE INDEX IF NOT EXISTS {INDEX_FMT.format(table=t)} ON {t}({COLUMN})")
    clear_cache()
    return changed


def clean(text) -> Optional[str]:
    t = (text or "").strip()
    return t or None


def suggestions(conn, text: str = "", limit: int = MAX_SUGGESTIONS) -> List[str]:
    """References already used in any of the three tables that contain `text` (case-insensitive,
    anywhere), most recently used first, at most `limit`."""
    parts = []
    for t in TABLES:
        if not has_column(conn, t):
            continue
        has_created = "created_at" in {r[1] for r in conn.execute(f"PRAGMA table_info({t})")}
        stamp = "MAX(COALESCE(created_at, ''))" if has_created else "''"
        parts.append(f"SELECT {COLUMN} AS ref, {stamp} AS used FROM {t} "
                     f"WHERE {COLUMN} IS NOT NULL AND TRIM({COLUMN}) <> '' GROUP BY {COLUMN}")
    if not parts:
        return []
    rows = conn.execute(" UNION ALL ".join(parts)).fetchall()
    needle = (text or "").strip().lower()
    best: dict = {}
    for ref, used in rows:
        if needle and needle not in ref.lower():
            continue
        if ref not in best or used > best[ref]:
            best[ref] = used
    ordered = sorted(best.items(), key=lambda kv: kv[0].lower())
    ordered.sort(key=lambda kv: kv[1], reverse=True)
    return [r for r, _ in ordered[:limit]]


def similar_references(conn, text: str, limit: int = 10) -> List[str]:
    """Existing references that resemble `text`: those containing it (either way round) plus
    difflib close matches, so a new import can follow the naming convention."""
    import difflib
    t = (text or "").strip().lower()
    if not t:
        return []
    every = suggestions(conn, "", 100000)
    hits = [r for r in every if t in r.lower() or (len(r) >= 4 and r.lower() in t)]
    lowered = {r.lower(): r for r in every}
    for m in difflib.get_close_matches(t, list(lowered), n=limit, cutoff=0.6):
        if lowered[m] not in hits:
            hits.append(lowered[m])
    return hits[:limit]


def like_clause(text: str, column: str = COLUMN):
    """(sql, params) for a case-insensitive contains filter; ('', []) when text is empty."""
    t = (text or "").strip()
    if not t:
        return "", []
    esc = t.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"LOWER(COALESCE({column}, '')) LIKE ? ESCAPE '\\'", [f"%{esc.lower()}%"]


class ReadOnlyDb:
    """A tiny stand-in for the app's database manager that only reads: main_connection() opens
    the file read-only. For widgets that have a path but no manager (the Mapping tab)."""

    def __init__(self, path):
        self.path = path

    def main_connection(self):
        import contextlib

        from shared.db_open import connect_ro

        @contextlib.contextmanager
        def cm():
            conn = connect_ro(self.path)
            try:
                yield conn
            finally:
                conn.close()
        return cm()


def db_has_column(db, table: str) -> bool:
    """has_column through the app's database manager (db.main_connection()); False if no db."""
    if db is None:
        return False
    try:
        with db.main_connection() as conn:
            return has_column(conn, table)
    except Exception:
        return False


def db_suggestions(db, text: str = "", limit: int = MAX_SUGGESTIONS) -> List[str]:
    if db is None:
        return []
    try:
        with db.main_connection() as conn:
            return suggestions(conn, text, limit)
    except Exception:
        return []


def stamp_records(db, table: str, records: list, reference) -> int:
    """Put `reference` on every record dict (a row an import is about to write), if there is one
    and `table` has the column. Returns how many dicts were stamped."""
    ref = clean(reference)
    if not ref or not records or not db_has_column(db, table):
        return 0
    for r in records:
        r[COLUMN] = ref
    return len(records)


__all__ = ["ReadOnlyDb", "similar_references", "db_has_column", "db_suggestions", "stamp_records", "COLUMN", "TABLES", "has_column", "ensure_schema", "suggestions", "like_clause",
           "clean", "clear_cache", "TOOLTIP_MISSING", "TOOLTIP_FIELD", "PLACEHOLDER"]
