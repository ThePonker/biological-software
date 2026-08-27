"""Date normalisation for Data Entry.

The whole suite stores dates as ISO YYYY-MM-DD (Session-25 migration). The grid accepts what a
recorder naturally types -- dd/mm/yyyy, yyyy-mm-dd, or 'today'/'yesterday' -- and normalises to
ISO. Anything unrecognised is left as-is (so the user sees it's wrong rather than losing it).
"""
from __future__ import annotations

import datetime as _dt
import re
from typing import Optional

_ISO = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
_DMY = re.compile(r"^(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2}|\d{4})$")


def to_iso(value) -> Optional[str]:
    """Return YYYY-MM-DD if the value parses to a real date, else None."""
    if value is None:
        return None
    s = str(value).strip().lower()
    if not s:
        return None
    if s in ("today", "now"):
        return _dt.date.today().isoformat()
    if s in ("yesterday", "yday"):
        return (_dt.date.today() - _dt.timedelta(days=1)).isoformat()

    m = _ISO.match(s)
    if m:
        y, mo, d = (int(g) for g in m.groups())
        return _valid(y, mo, d)

    m = _DMY.match(s)
    if m:
        d, mo, yr = m.groups()
        d, mo = int(d), int(mo)
        y = int(yr)
        if len(yr) == 2:                       # 2-digit year -> 2000s
            y += 2000
        return _valid(y, mo, d)
    return None


def _valid(y: int, mo: int, d: int) -> Optional[str]:
    try:
        return _dt.date(y, mo, d).isoformat()
    except ValueError:
        return None


def normalise(value):
    """ISO string if parseable, otherwise the original value unchanged."""
    iso = to_iso(value)
    return iso if iso is not None else value


def is_future(value) -> bool:
    """True if the value parses to a date after today."""
    iso = to_iso(value)
    if not iso:
        return False
    try:
        return _dt.date.fromisoformat(iso) > _dt.date.today()
    except ValueError:
        return False


def to_display(value) -> str:
    """ISO YYYY-MM-DD -> DD/MM/YYYY for showing in the grid. Non-ISO text is returned unchanged."""
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""
    m = _ISO.match(s)
    if m:
        y, mo, d = (int(g) for g in m.groups())
        try:
            return _dt.date(y, mo, d).strftime("%d/%m/%Y")
        except ValueError:
            return s
    return s
