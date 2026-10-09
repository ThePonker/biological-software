"""Date normalisation for Data Entry.

The whole suite stores dates as ISO YYYY-MM-DD (Session-25 migration). The grid accepts what a
recorder naturally types -- dd/mm/yyyy, yyyy-mm-dd, or 'today'/'yesterday' -- and normalises to
ISO. Anything unrecognised is left as-is (so the user sees it's wrong rather than losing it).

Vague dates (9 Oct 2026, review DE1): a year alone ("2026") or a month and year ("06/2026",
"Jun 2026", "2026-06") are kept as typed in staging ("2026", "2026-06") and carry the date
type the suite already uses (Observation.date_type: D = day, O = month, Y = year). At commit
the record's date is the first day of the period with that type -- the convention iRecord's
own vague dates follow. Anything else unreadable ("31/02/2026", "summer") is flagged in the
grid and by Check before commit.
"""
from __future__ import annotations

import datetime as _dt
import re
from typing import Optional

_ISO = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
_DMY = re.compile(r"^(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2}|\d{4})$")
_YEAR = re.compile(r"^(\d{4})$")
_MY = re.compile(r"^(\d{1,2})[/.\-](\d{4})$")           # 06/2026
_YM = re.compile(r"^(\d{4})-(\d{1,2})$")                # 2026-06 (also the stored form)
_MONTHS = {m: i for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), start=1)}
_MON_ABBR = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_MON_Y = re.compile(r"^([a-z]+)\.?,?\s+(\d{4})$")       # Jun 2026 / June 2026
_MIN_YEAR = 1700                                         # earlier than any plausible record


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


def parse(value):
    """(stored form, date type) for anything the grid can read, else None.

    D: 'YYYY-MM-DD'; O: 'YYYY-MM'; Y: 'YYYY'. The type codes are Observation.date_type's."""
    iso = to_iso(value)
    if iso:
        return iso, "D"
    if value is None:
        return None
    s = " ".join(str(value).strip().lower().split())
    m = _YEAR.match(s)
    if m:
        y = int(m.group(1))
        return (f"{y:04d}", "Y") if y >= _MIN_YEAR else None
    m = _MY.match(s) or _YM.match(s)
    if m:
        a, b = m.groups()
        y, mo = (int(b), int(a)) if m.re is _MY else (int(a), int(b))
        return (f"{y:04d}-{mo:02d}", "O") if 1 <= mo <= 12 and y >= _MIN_YEAR else None
    m = _MON_Y.match(s)
    if m:
        mo = _MONTHS.get(m.group(1)[:3])
        y = int(m.group(2))
        if mo and y >= _MIN_YEAR and (len(m.group(1)) == 3 or _full_month(m.group(1))):
            return f"{y:04d}-{mo:02d}", "O"
    return None


def _full_month(word: str) -> bool:
    return word in ("january", "february", "march", "april", "may", "june", "july", "august",
                    "september", "october", "november", "december", "sept")


def is_readable(value) -> bool:
    """True for a real day, month-year or year; False for '31/02/2026', 'summer', blank."""
    return parse(value) is not None


def date_type(value) -> Optional[str]:
    """'D', 'O' or 'Y' for a readable date, else None."""
    p = parse(value)
    return p[1] if p else None


def start_iso(value) -> Optional[str]:
    """ISO date of the first day of the period (the day itself for an exact date)."""
    p = parse(value)
    if not p:
        return None
    stored, kind = p
    if kind == "D":
        return stored
    if kind == "O":
        return stored + "-01"
    return stored + "-01-01"


def end_iso(value) -> Optional[str]:
    """ISO date of the last day of the period."""
    p = parse(value)
    if not p:
        return None
    stored, kind = p
    if kind == "D":
        return stored
    if kind == "Y":
        return stored + "-12-31"
    y, mo = (int(x) for x in stored.split("-"))
    nxt = _dt.date(y + (mo == 12), mo % 12 + 1, 1)
    return (nxt - _dt.timedelta(days=1)).isoformat()


def normalise(value):
    """The stored form if readable (ISO for a day), otherwise the original value unchanged."""
    p = parse(value)
    return p[0] if p is not None else value


def is_future(value) -> bool:
    """True if the value parses to a date (or a period starting) after today."""
    iso = start_iso(value)
    if not iso:
        return False
    try:
        return _dt.date.fromisoformat(iso) > _dt.date.today()
    except ValueError:
        return False


def to_irecord(value) -> str:
    """The date as iRecord's import reads it: 05/06/2026, Jun 2026 or 2026 (blank if unreadable)."""
    p = parse(value)
    if not p:
        return ""
    stored, kind = p
    if kind == "D":
        return _dt.date.fromisoformat(stored).strftime("%d/%m/%Y")
    if kind == "O":
        y, mo = (int(x) for x in stored.split("-"))
        return f"{_MON_ABBR[mo - 1]} {y}"                 # not strftime: that follows the locale
    return stored


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
    m = _YM.match(s)
    if m and 1 <= int(m.group(2)) <= 12:
        return f"{int(m.group(2)):02d}/{m.group(1)}"     # a month-year shows as 06/2026
    return s
