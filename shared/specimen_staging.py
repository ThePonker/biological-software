"""specimen_staging -- which specimens a Data Entry row was made from (14 Oct 2026).

Records made from specimens go through Data Entry like any other row, so Wil sees and edits
them before they are committed. This table remembers which specimens each row stands for;
on commit those specimens are linked to the new record (specimens.observation_id), and a
deleted row lets its specimens go (they show as "no field record" again).

    staging_specimens(staging_id, specimen_id)   one row per specimen

No Qt. Never touches a specimen that already has a field record.
"""
from __future__ import annotations

import sqlite3
from typing import Dict, Iterable, List, Set

TABLE = "staging_specimens"


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(f"CREATE TABLE IF NOT EXISTS {TABLE} (staging_id INTEGER NOT NULL, "
                 "specimen_id INTEGER NOT NULL, PRIMARY KEY (staging_id, specimen_id))")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{TABLE}_specimen ON {TABLE}(specimen_id)")


def has_table(conn) -> bool:
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                             (TABLE,)).fetchone())


def add(conn: sqlite3.Connection, staging_id: int, specimen_ids: Iterable[int]) -> None:
    ensure_schema(conn)
    conn.executemany(f"INSERT OR IGNORE INTO {TABLE} (staging_id, specimen_id) VALUES (?, ?)",
                     [(int(staging_id), int(s)) for s in specimen_ids])


def for_row(conn, staging_id: int) -> List[int]:
    if not has_table(conn):
        return []
    return [r[0] for r in conn.execute(
        f"SELECT specimen_id FROM {TABLE} WHERE staging_id = ? ORDER BY specimen_id", (staging_id,))]


def staged(conn) -> Dict[int, int]:
    """{specimen id: staging row id} for every specimen already on a Data Entry row."""
    if not has_table(conn):
        return {}
    return {s: r for r, s in conn.execute(f"SELECT staging_id, specimen_id FROM {TABLE}")}


def staged_ids(conn) -> Set[int]:
    return set(staged(conn))


def link_on_commit(conn, staging_id: int, observation_id: int) -> List[str]:
    """The row became observation `observation_id`: link its specimens to it (only those
    still without a field record) and forget the row's list. Returns notes for the commit
    summary. The caller commits."""
    notes = []
    ids = for_row(conn, staging_id)
    if not ids:
        return notes
    for sid in ids:
        cur = conn.execute("UPDATE specimens SET observation_id = ? WHERE id = ? "
                           "AND observation_id IS NULL", (observation_id, sid))
        if cur.rowcount == 0:
            notes.append(f"specimen {sid}: already had a field record (or is gone) -- "
                         f"not linked to record {observation_id}")
    conn.execute(f"DELETE FROM {TABLE} WHERE staging_id = ?", (staging_id,))
    return notes


def release(conn, staging_ids: Iterable[int]) -> None:
    """Rows deleted without a commit: their specimens are free again. The caller commits."""
    if not has_table(conn):
        return
    conn.executemany(f"DELETE FROM {TABLE} WHERE staging_id = ?", [(int(i),) for i in staging_ids])


__all__ = ["TABLE", "ensure_schema", "has_table", "add", "for_row", "staged", "staged_ids",
           "link_on_commit", "release"]
