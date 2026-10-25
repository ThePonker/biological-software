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
_YM = re.compile(r"^(\d{4})-(\d{1,2})$")                # 2026-06 (also the stored form)
_MON_ABBR = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_NO_LIMIT = _dt.date(9999, 12, 31)    # the reader's "today": a date still to come is read, not refused
                                      # (is_future flags it; the 2-digit year is always the 2000s)


def to_iso(value) -> Optional[str]:
    """Return YYYY-MM-DD if the value parses to a real day, else None."""
    p = parse(value)
    return p[0] if p and p[1] == "D" else None


def parse(value):
    """(stored form, date type) for anything the grid can read, else None.

    D: 'YYYY-MM-DD'; O: 'YYYY-MM'; Y: 'YYYY'. The type codes are Observation.date_type's.
    The reading is shared.import_core.parse_record_date (R13: one date reader for the suite);
    'today' / 'yesterday' are added here, and a range ('2019-2021') is not one date: None."""
    if value is None:
        return None
    # 'June, 2021' read as before R13 (review 24 Oct 2026): a comma is a separator here
    s = " ".join(str(value).strip().lower().replace(",", " ").split())
    if not s:
        return None
    if s in ("today", "now"):
        return _dt.date.today().isoformat(), "D"
    if s in ("yesterday", "yday"):
        return (_dt.date.today() - _dt.timedelta(days=1)).isoformat(), "D"
    from shared.import_core import parse_record_date
    try:
        got = parse_record_date(s, today=_NO_LIMIT)
    except ValueError:                 # December 9999: its month end would be in year 10000
        return None
    if got.error or not got.date or got.date_type not in ("D", "O", "Y"):
        return None
    cut = {"D": 10, "O": 7, "Y": 4}[got.date_type]
    return got.date[:cut], got.date_type


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
