"""observatum_keys -- THE rule for the next Observatum key (OBS-<initials>-<YYYYMMDD>-<n>).

14 Oct 2026 (review of A3): three generators found "the last key" by sorting the key TEXT,
while one wrote 4-digit and another 6-digit numbers. Text order puts ...-9999 after ...-10000
and ...-0120 after ...-000121, so keys repeated: 3,712 records share 993 keys (13 Oct copy).
A key goes to iRecord as the External key and comes back to match the record, so it must be
unique. The next number is now the NUMERIC maximum of every key with the day's prefix, and
numbers are written with 6 digits (wider when needed).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

WIDTH = 6


def prefix_for(initials: str, when: Optional[datetime] = None) -> str:
    return f"OBS-{initials}-{(when or datetime.now()):%Y%m%d}-"


def last_sequence(db, prefix: str) -> int:
    """The highest number used after `prefix` (0 when none). db: a sqlite3 connection or
    anything with execute_main(sql, params). Raises if the database cannot be read -- a
    guess of 0 would hand out keys already in use."""
    sql = ("SELECT MAX(CAST(substr(observatum_key, ?) AS INTEGER)) FROM observations "
           "WHERE observatum_key LIKE ? AND substr(observatum_key, ?) GLOB '[0-9]*'")
    if db is None:                  # no database at all (tests): nothing can be in use
        return 0
    start = len(prefix) + 1
    params = (start, f"{prefix}%", start)
    rows = db.execute_main(sql, params) if hasattr(db, "execute_main") else db.execute(sql, params).fetchall()
    value = rows[0][0] if rows else None
    return int(value or 0)


def make_key(prefix: str, seq: int) -> str:
    return f"{prefix}{seq:0{WIDTH}d}"


__all__ = ["WIDTH", "prefix_for", "last_sequence", "make_key"]
