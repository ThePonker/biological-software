"""display_format -- how dates and analysis modes are shown to a reader.

One home for presentation strings that more than one screen or export needs, so
the Examen screen and the assessment workbook cannot drift apart (05_Rules: a rule
written twice drifts). UI-agnostic: no Qt imports.
"""
import datetime as _dt
import re

DATE_NUMBER_FORMAT = "DD/MM/YYYY"      # the Excel number format of a real date cell

_ISO_DAY = re.compile(r"(\d{4})-(\d{2})-(\d{2})(?=$|[T ]\d{2}:\d{2})")
_ISO_MONTH = re.compile(r"(\d{4})-(\d{2})$")
_ISO_TIME = re.compile(r"[T ](\d{2}:\d{2})")


# Record-table columns that hold a stored ISO date or timestamp, in the order a table offers them
# (the optional columns of the Observations, Recording Scheme and Collection tables).
RECORD_DATE_COLUMNS = frozenset({
    "verified_on", "embargo_until", "input_on_date", "last_edited_date",
    "created_at", "updated_at", "last_synced"})


def dmy(iso):
    """'2026-05-05' -> '05/05/2026'; a time after the date is dropped; '2021-06' -> '06/2021'.

    A bare year ('2021'), blank and anything unreadable are returned unchanged (None -> '').
    Dates are STORED as ISO; this is for what a person reads (CLAUDE.md: import, don't copy)."""
    s = str(iso or "")
    m = _ISO_DAY.match(s)
    if m:
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    m = _ISO_MONTH.match(s.strip())
    if m and 1 <= int(m.group(2)) <= 12:
        return f"{m.group(2)}/{m.group(1)}"
    return s


def dmy_time(stamp):
    """'2026-10-14T21:14:07' -> '14/10/2026 21:14'; a date alone -> '14/10/2026'; else unchanged."""
    s = str(stamp or "")
    day = dmy(s)
    m = _ISO_DAY.match(s)
    t = _ISO_TIME.match(s[m.end():]) if m else None
    return f"{day} {t.group(1)}" if t else day


def date_cell(iso):
    """For an Excel cell a person reads: a real date (give the cell number_format
    DATE_NUMBER_FORMAT) when `iso` is a whole day, so the column sorts and filters as dates;
    otherwise the dd/mm/yyyy (or month, year, as-is) text."""
    s = str(iso or "")
    m = _ISO_DAY.match(s)
    if m and len(s) == 10:
        try:
            return _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return dmy(s)


# AnalysisMode values (shared.repositories.codex_repository) -> reader-facing label
MODE_LABELS = {
    "codex_full": "Codex Full",
    "pantheon_only": "Pantheon Only",
}


def mode_label(mode):
    """'codex_full' or AnalysisMode.CODEX_FULL -> 'Codex Full'; unknown values unchanged."""
    value = getattr(mode, "value", mode)
    return MODE_LABELS.get(str(value or ""), str(value or ""))
