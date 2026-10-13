"""hidden_records -- observations removed here but still in iRecord (F72, agreed with Wil
12 Oct 2026, late): HIDE them, never delete them, so the next iRecord download cannot bring
them back as a second copy.

THE rule, used everywhere observations are listed, counted, mapped, charted or exported:

  * observations.hidden_at (TEXT, ISO timestamp) is set when Wil chooses "Deleted in iRecord
    -- remove here" on a record that has an iRecord ID. NULL = a live record. The column and
    the table below are added by scripts/add_hidden_at_column.py (dry run first, backup).
  * hidden_irecord_ids(irecord_id TEXT PRIMARY KEY, hidden_at TEXT, species_name TEXT,
    returned_at TEXT) remembers every iRecord ID hidden this way, so a download that brings
    the record again (same iRecord ID) keeps it hidden and marks returned_at: the cleaning
    report's "Came back from iRecord -- check" tile lists those; "Show again" clears both.
  * live_sql(db) is the WHERE fragment that leaves the hidden rows out:
        " AND hidden_at IS NULL"   (or "" on a database without the column yet)
    shared/species_counting.copies_sql adds it for observations, so every screen that
    follows the species-counting switches (stats dashboards, Species lookup, Mapping, Quick
    stats, year export, achievements) skips hidden rows through that one door; the
    Observation tab's list, the repository's search and the Examen reader add it themselves.

Records with no iRecord ID are deleted as before (they cannot come back).
"""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime
from typing import Dict, Optional

COLUMN = "hidden_at"
TABLE = "observations"
ID_TABLE = "hidden_irecord_ids"
ID_COLUMNS = ("irecord_id", "hidden_at", "species_name", "returned_at")

RETURNED_LABEL = "Came back from iRecord -- check"

_lock = threading.RLock()
_has: Dict[str, bool] = {}            # db file -> column present (True is never re-checked)


def _columns(conn, table: str = TABLE) -> set:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def has_column(db) -> bool:
    """True when the observations table has hidden_at. `db`: a sqlite3 connection, an
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
    """' AND <prefix>hidden_at IS NULL' -- leave the hidden rows out -- or '' when the
    database has no hidden_at column yet. prefix e.g. 'o.'."""
    return f" AND {prefix}{COLUMN} IS NULL" if has_column(db) else ""


def forget() -> None:
    """Forget the cached column checks (tests; after the migration script ran)."""
    with _lock:
        _has.clear()


# ------------------------------------------------------------------ schema (the script
# and the importer both use these, so the two cannot drift)

def ensure_schema(conn: sqlite3.Connection) -> bool:
    """Add the column and the table when missing (idempotent). Returns True when something
    was added. Caller holds the transaction and has backed up first."""
    changed = False
    if COLUMN not in _columns(conn):
        conn.execute(f"ALTER TABLE {TABLE} ADD COLUMN {COLUMN} TEXT")
        changed = True
    if not conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
                        (ID_TABLE,)).fetchone():
        conn.execute(f"CREATE TABLE {ID_TABLE} (irecord_id TEXT PRIMARY KEY, hidden_at TEXT, "
                     f"species_name TEXT, returned_at TEXT)")
        changed = True
    elif "returned_at" not in _columns(conn, ID_TABLE):
        conn.execute(f"ALTER TABLE {ID_TABLE} ADD COLUMN returned_at TEXT")
        changed = True
    return changed


def schema_present(conn: sqlite3.Connection) -> bool:
    return COLUMN in _columns(conn) and "returned_at" in _columns(conn, ID_TABLE)


# Examen reads observations through the assessment_records VIEW (scripts/reset_database.py),
# so the fragment has to be in the view's own SQL: its "FROM observations" becomes
# "FROM observations WHERE hidden_at IS NULL". The rest of the view is kept as found.
VIEW = "assessment_records"
_VIEW_FROM = "FROM observations"
_VIEW_FROM_HIDDEN = f"FROM observations WHERE {COLUMN} IS NULL"


def view_sql(conn: sqlite3.Connection) -> Optional[str]:
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'view' AND name = ?",
                       (VIEW,)).fetchone()
    return row[0] if row else None


def view_skips_hidden(conn: sqlite3.Connection) -> Optional[bool]:
    """True / False for the view as it stands; None when there is no such view."""
    sql = view_sql(conn)
    if sql is None:
        return None
    return _VIEW_FROM_HIDDEN in sql


def ensure_view(conn: sqlite3.Connection) -> bool:
    """Rebuild assessment_records with the fragment (idempotent). True when rebuilt."""
    sql = view_sql(conn)
    if sql is None or _VIEW_FROM_HIDDEN in sql or sql.count(_VIEW_FROM) != 1:
        return False
    conn.execute(f"DROP VIEW {VIEW}")
    conn.execute(sql.replace(_VIEW_FROM, _VIEW_FROM_HIDDEN))
    return True


# ------------------------------------------------------------------ writes (one
# transaction each; the caller backs up where the suite does)

def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def hide(conn: sqlite3.Connection, record_id: int, irecord_id, species_name: str = "") -> bool:
    """Hide one observation and remember its iRecord ID. False when the schema is missing."""
    if not schema_present(conn):
        return False
    stamp = now_iso()
    with conn:
        conn.execute(f"UPDATE {TABLE} SET {COLUMN} = ? WHERE id = ? AND {COLUMN} IS NULL",
                     (stamp, record_id))
        conn.execute(f"INSERT INTO {ID_TABLE} (irecord_id, hidden_at, species_name, returned_at) "
                     f"VALUES (?, ?, ?, NULL) ON CONFLICT(irecord_id) DO UPDATE SET "
                     f"hidden_at = excluded.hidden_at, species_name = excluded.species_name, "
                     f"returned_at = NULL",
                     (str(irecord_id).strip(), stamp, species_name or ""))
    return True


def show_again(conn: sqlite3.Connection, record_id: int) -> bool:
    """Clear hidden_at on one observation and forget its iRecord ID."""
    if not schema_present(conn):
        return False
    with conn:
        row = conn.execute(f"SELECT irecord_id FROM {TABLE} WHERE id = ?", (record_id,)).fetchone()
        conn.execute(f"UPDATE {TABLE} SET {COLUMN} = NULL WHERE id = ?", (record_id,))
        if row and row[0] not in (None, ""):
            conn.execute(f"DELETE FROM {ID_TABLE} WHERE irecord_id = ?", (str(row[0]).strip(),))
    return True


def hidden_ids(conn: sqlite3.Connection) -> Dict[str, Optional[str]]:
    """{iRecord ID (text): hidden_at} for every remembered ID; {} without the table."""
    try:
        return {str(r[0]): r[1] for r in conn.execute(f"SELECT irecord_id, hidden_at FROM {ID_TABLE}")}
    except sqlite3.Error:
        return {}


def mark_returned(conn: sqlite3.Connection, irecord_id, stamp: Optional[str] = None) -> int:
    """A download brought a hidden record again: note when. Rows changed (0 without the table)."""
    try:
        with conn:
            return conn.execute(f"UPDATE {ID_TABLE} SET returned_at = ? WHERE irecord_id = ?",
                                (stamp or now_iso(), str(irecord_id).strip())).rowcount
    except sqlite3.Error:
        return 0


def after_download(conn: sqlite3.Connection, irecord_ids, stamp: Optional[str] = None) -> int:
    """After an iRecord download: every remembered ID among `irecord_ids` keeps its record
    hidden (hidden_at set again if the download re-inserted it) and gets returned_at, so
    the cleaning report lists it under "Came back from iRecord -- check". Returns how many
    came back; 0 without the schema. One transaction."""
    if not schema_present(conn):
        return 0
    want = {str(i).strip() for i in irecord_ids if i not in (None, "")}
    if not want:
        return 0
    remembered = hidden_ids(conn)
    back = sorted(want & set(remembered))
    if not back:
        return 0
    stamp = stamp or now_iso()
    with conn:
        for start in range(0, len(back), 500):
            chunk = back[start:start + 500]
            marks = ",".join("?" * len(chunk))
            conn.execute(f"UPDATE {ID_TABLE} SET returned_at = ? WHERE irecord_id IN ({marks})",
                         [stamp] + chunk)
            conn.execute(f"UPDATE {TABLE} SET {COLUMN} = ? WHERE {COLUMN} IS NULL "
                         f"AND CAST(irecord_id AS TEXT) IN ({marks})", [stamp] + chunk)
    return len(back)


def returned(conn: sqlite3.Connection):
    """[(observation id, irecord_id, species_name, hidden_at, returned_at)] for the hidden
    records a download brought again (the cleaning report's tile); [] without the schema.
    Only rows still hidden: a live row is never listed (or counted) twice."""
    if not schema_present(conn):
        return []
    return conn.execute(
        f"SELECT o.id, h.irecord_id, o.species_name, h.hidden_at, h.returned_at "
        f"FROM {ID_TABLE} h JOIN {TABLE} o ON CAST(o.irecord_id AS TEXT) = h.irecord_id "
        f"WHERE h.returned_at IS NOT NULL AND o.{COLUMN} IS NOT NULL "
        f"ORDER BY o.species_name, o.id").fetchall()
