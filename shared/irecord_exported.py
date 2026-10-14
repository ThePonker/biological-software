"""irecord_exported -- remember which records were exported for iRecord (14 Oct 2026), so a
second export before the sync brings them back cannot send them twice. No Qt.

observations.irecord_exported_on (TEXT, ISO date) is set when a record is written to an
iRecord export file. A record that has it but no iRecord ID yet is "exported, waiting for the
sync"; the next export leaves it out unless Wil says the earlier upload failed. The column is
added by scripts/add_irecord_exported_column.py; without it everything works as before.
"""
from __future__ import annotations

from datetime import date
from typing import Dict, Iterable

COLUMN = "irecord_exported_on"


def has_column(conn) -> bool:
    try:
        return COLUMN in {r[1] for r in conn.execute("PRAGMA table_info(observations)")}
    except Exception:
        return False


def ensure_schema(conn) -> bool:
    if has_column(conn):
        return False
    conn.execute(f"ALTER TABLE observations ADD COLUMN {COLUMN} TEXT")
    return True


def _ids(ids: Iterable) -> list:
    return [int(i) for i in ids if i not in (None, "")]


def waiting(conn, ids: Iterable) -> Dict[int, str]:
    """{id: exported on} for these records: exported for iRecord, no iRecord ID yet."""
    ids = _ids(ids)
    if not ids or not has_column(conn):
        return {}
    out = {}
    for i in range(0, len(ids), 900):
        part = ids[i:i + 900]
        out.update(conn.execute(
            f"SELECT id, {COLUMN} FROM observations WHERE id IN ({','.join('?' * len(part))}) "
            f"AND {COLUMN} IS NOT NULL AND COALESCE(irecord_id, '') IN ('', 0)", part).fetchall())
    return out


def stamp(conn, ids: Iterable, when: str = "") -> int:
    """Mark these records exported for iRecord today. 0 without the column. The caller commits."""
    ids = _ids(ids)
    if not ids or not has_column(conn):
        return 0
    when = when or date.today().isoformat()
    n = 0
    for i in range(0, len(ids), 900):
        part = ids[i:i + 900]
        n += conn.execute(f"UPDATE observations SET {COLUMN} = ? WHERE id IN ({','.join('?' * len(part))})",
                          [when, *part]).rowcount
    return n


__all__ = ["COLUMN", "has_column", "ensure_schema", "waiting", "stamp"]
