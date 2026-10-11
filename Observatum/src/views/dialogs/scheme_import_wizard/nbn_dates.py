"""NBN Atlas dates that are not one day (11 Oct 2026).

The Atlas writes a year-only record as 1 January of that year (and a month-only one as the
1st of the month) in its single date field. Read as given, 11,363 scheme records were stored
as exact days on 1 January and filled every January bar. A download also says what the date
really is, in one of three ways; this reads them, finest evidence first:

1. a "datePrecision" / "Date precision" column ("Year", "Month", "Day", "... range");
2. the year / month / day columns: a year with no day is not a day;
3. a start and end date that cover whole years or whole months
   (1985-01-01 to 1985-12-31 is the year 1985).

The date itself is kept (the first day of the period, as the rest of the suite stores it);
only the date type changes: D -> Y / O, DD -> Y / O / YY / OO.
"""
import datetime as _dt
from typing import Dict, Optional


def _iso(text: str) -> Optional[_dt.date]:
    try:
        return _dt.date.fromisoformat(str(text or "").strip()[:10])
    except ValueError:
        return None


def _span_kind(start: _dt.date, end: _dt.date) -> str:
    """'Y' / 'YY' / 'O' / 'OO' when start..end is whole years / months, else ''."""
    if end < start:
        return ""
    last_of_month = (end + _dt.timedelta(days=1)).day == 1
    if (start.month, start.day) == (1, 1) and (end.month, end.day) == (12, 31):
        return "Y" if start.year == end.year else "YY"
    if start.day == 1 and last_of_month:
        return "O" if (start.year, start.month) == (end.year, end.month) else "OO"
    return ""


def nbn_date_kind(date_fields: Dict[str, str], date_text: str, precision: str = "",
                  year: str = "", month: str = "", day: str = "") -> Dict[str, str]:
    """date_fields (from parse_record_date) with the date type the NBN download gives it.

    `date_text` is the date as read ('1985-01-01' or '1985-01-01/1985-12-31'); `precision`
    the datePrecision column; year / month / day the separate columns. Only a date read as
    a day or a day range is changed, and only when the stored date fits the period (a 'Year'
    precision on 1985-06-03 is left as a day: the two disagree, so nothing is guessed)."""
    kind = date_fields.get("date_type") or ""
    date = date_fields.get("date") or ""
    if date_fields.get("date_error") or kind not in ("D", "DD") or not date:
        return date_fields
    start = _iso(date)
    if start is None:
        return date_fields
    first, _, last = str(date_text or "").partition("/")
    end = _iso(last) if last else start
    multi = end is not None and end != start
    prec = (precision or "").strip().lower()
    want, why = "", ""
    if "year" in prec:
        want, why = ("YY" if multi and end.year != start.year else "Y"), "the file's date precision"
    elif "month" in prec:
        want = "OO" if multi and (end.year, end.month) != (start.year, start.month) else "O"
        why = "the file's date precision"
    elif year.strip() and not day.strip() and not multi:
        want, why = ("O" if month.strip() else "Y"), "the file gives no day"
    elif multi:
        want, why = _span_kind(start, end), "the range covers whole periods"
    if not want:
        return date_fields
    fits = start.day == 1 and (want[0] == "O" or start.month == 1)
    if not fits:
        return date_fields
    name = {"Y": "a year", "YY": "a range of years", "O": "a month",
            "OO": "a range of months"}[want]
    out = dict(date_fields)
    out["date_type"] = want
    out["_date_note"] = (f"Date '{date_text}' is {name} ({why}): stored as {date} with "
                         f"date type {want}")
    return out
