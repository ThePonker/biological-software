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

# The QSettings key the initials are saved under (Observatum > Settings > General). One home:
# Observatum's Settings.USER_INITIALS is this.
INITIALS_SETTING = "general/user_initials"


class MissingInitials(ValueError):
    """No user initials are set, so no Observatum key can be made."""


MISSING_INITIALS_MESSAGE = (
    "Your initials are not set, so Observatum cannot make record keys (OBS-<initials>-...). "
    "Open Observatum > Settings > General, type your initials (e.g. WJH) and try again. "
    "Nothing has been written.")


def user_initials(settings=None) -> str:
    """The user's initials from QSettings, upper case. Raises MissingInitials when blank:
    keys must never be made with a stand-in like 'USR' (703 records got it, 10 Nov 2026).
    settings: a QSettings-like object (tests); default is the application's QSettings."""
    if settings is None:
        from PySide6.QtCore import QSettings
        settings = QSettings()
    initials = str(settings.value(INITIALS_SETTING, "") or "").strip().upper()
    if not initials:
        raise MissingInitials(MISSING_INITIALS_MESSAGE)
    return initials


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


__all__ = ["INITIALS_SETTING", "MissingInitials", "MISSING_INITIALS_MESSAGE", "user_initials", "WIDTH", "prefix_for", "last_sequence", "make_key"]
