"""Figures for the atlas page's extras (26 Oct 2026): pure functions, no Qt.

The population is the records the map is drawn from (MappingTab._records) that sit in a mapped
square -- the same records the footer counts (atlas_export.atlas_footer): a record whose
r["square"] is in `squares`. On a zoomed "Current view" page `squares` is only the squares on
the page, so every figure counts what the page shows, "(in view)" (R9-6). With several taxa
mapped the figures are for the whole selection.

Definitions
  records        records in the population (equals the footer's sum of the squares' counts)
  species        distinct r["species"] (the tab's species key, map_taxa.species_key); records
                 without one (named only above species) are not counted -- as the footer
  squares        distinct squares holding a record, at the map's grid size
  vice_counties  distinct r["vc"] (blank / None not counted)
  recorders      distinct recorder names: each r["person"] is split on ";", " & " and " and "
                 (recording_scheme holds "A;B;C" lists), trimmed, empty ones dropped, compared
                 ignoring case. Names as given: "Lyons, G." and "Graeme Lyons" stay two.
  first / last   earliest / latest record date, from records dated to a single day (D), a
                 month (O, or "1956-06") or a year (Y, or "1956") only. A range (DD/OO/YY, stored
                 from its first day) or a before/after date (-Y, Y-) is left out -- it would
                 give a false first or last -- and counted in `ranged`. A day gives day
                 precision, a month gives month, a year gives its year, never a made-up day.
                 Ordered by (year, month, day) with an unknown month or day sorting first, so
                 "1898" sorts before "May 1898".
  decades        by year, from the same records as first / last: pre-1950, 1950-79, 1980-99,
                 2000-09, 2010-19, 2020-; records with no date at all are `undated`
  months         records per month, Jan-Dec, from single-day dates only (date_type D), as the
                 suite's month charts do (decision 9); `no_month` = every other record in the
                 population (month, year, range, before/after and undated), so
                 months + no_month = records
"""
from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass, field
from typing import Iterable, Optional, Tuple

DECADES = (("pre-1950", None, 1949), ("1950–79", 1950, 1979), ("1980–99", 1980, 1999),
           ("2000–09", 2000, 2009), ("2010–19", 2010, 2019), ("2020–", 2020, None))
MONTH_NAMES = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
MONTH_INITIALS = "JFMAMJJASOND"

_ISO = re.compile(r"^\s*(\d{4})(?:-(\d{1,2})(?:-(\d{1,2}))?)?")


def parse_when(date, date_type=None) -> Optional[Tuple[int, Optional[int], Optional[int]]]:
    """(year, month or None, day or None) for a stored date, no more precise than its date
    type and its text allow; None if there is no usable year (1000-2999, as map_selection)."""
    m = _ISO.match(str(date or ""))
    if not m:
        return None
    y = int(m.group(1))
    if not 1000 <= y <= 2999:
        return None
    mo = int(m.group(2)) if m.group(2) else None
    d = int(m.group(3)) if m.group(3) else None
    if mo is not None and not 1 <= mo <= 12:
        mo = d = None
    if mo is None:
        d = None
    if d is not None:
        try:
            _dt.date(y, mo, d)
        except ValueError:
            d = None
    dt = (date_type or "").strip().upper() or ("D" if d else "O" if mo else "Y")
    if dt != "D":
        d = None
    if dt not in ("D", "O"):
        mo = None
    return y, mo, d


def is_single_period(date_type) -> bool:
    """True for a day, a month or a year (D, O, Y or blank); False for a range (DD, OO, YY) or
    a before/after date (-Y, Y-), which stay out of first / last and decades."""
    return (date_type or "").strip().upper() in ("", "D", "O", "Y")


_SPLIT = re.compile(r"\s*;\s*|\s+&\s+|\s+and\s+", re.IGNORECASE)


def recorder_names(text) -> list:
    """The names in one recorder field, split on ";", " & " and " and ", trimmed, no blanks."""
    return [n for n in (" ".join(p.split()) for p in _SPLIT.split(str(text or ""))) if n]


@dataclass
class MapStats:
    records: int = 0
    species: int = 0
    squares: int = 0
    vice_counties: int = 0
    recorders: int = 0
    first: Optional[Tuple[int, Optional[int], Optional[int]]] = None
    last: Optional[Tuple[int, Optional[int], Optional[int]]] = None
    decades: list = field(default_factory=list)       # [(label, n)] in DECADES order
    undated: int = 0                                  # records with no year
    ranged: int = 0                                   # date range or before/after date
    months: list = field(default_factory=lambda: [0] * 12)
    no_month: int = 0


def compute(records: Iterable[dict], squares: Optional[Iterable[str]]) -> MapStats:
    """Figures for the records whose r["square"] is in `squares` (None: every record that has
    a square). Pass the page's squares for a Current view page."""
    keep = None if squares is None else set(squares)
    st = MapStats()
    sp, sq, vcs, rec = set(), set(), set(), set()
    counts = [0] * len(DECADES)
    for r in records:
        s = r.get("square")
        if not s or (keep is not None and s not in keep):
            continue
        st.records += 1
        sq.add(s)
        if r.get("species"):
            sp.add(r["species"])
        if r.get("vc"):
            vcs.add(r["vc"])
        rec.update(n.lower() for n in recorder_names(r.get("person")))
        w = parse_when(r.get("date"), r.get("date_type"))
        if w is not None and not is_single_period(r.get("date_type")):
            st.ranged += 1
            st.no_month += 1
            continue
        if w is None and r.get("year"):
            w = (int(r["year"]), None, None)
        if w is None:
            st.undated += 1
            st.no_month += 1
            continue
        key = (w[0], w[1] or 0, w[2] or 0)
        if st.first is None or key < (st.first[0], st.first[1] or 0, st.first[2] or 0):
            st.first = w
        if st.last is None or key > (st.last[0], st.last[1] or 0, st.last[2] or 0):
            st.last = w
        for i, (_l, lo, hi) in enumerate(DECADES):
            if (lo is None or w[0] >= lo) and (hi is None or w[0] <= hi):
                counts[i] += 1
                break
        if w[2] is not None:
            st.months[w[1] - 1] += 1
        else:
            st.no_month += 1
    st.species, st.squares, st.vice_counties, st.recorders = len(sp), len(sq), len(vcs), len(rec)
    st.decades = [(d[0], n) for d, n in zip(DECADES, counts)]
    return st


def when_text(w) -> str:
    """'12 May 1898', 'May 1898' or '1898'."""
    y, m, d = w
    if d:
        return f"{d} {MONTH_NAMES[m - 1]} {y}"
    return f"{MONTH_NAMES[m - 1]} {y}" if m else str(y)


def counts_line(st: MapStats, grid: str = "10 km", in_view: bool = False) -> str:
    """'Records 1,234 · Species 12 · Squares 87 (10 km) · Vice counties 9 · Recorders 41'."""
    tail = " (in view)" if in_view else ""
    return (f"Records {st.records:,} · Species {st.species:,} · Squares {st.squares:,} "
            f"({grid}) · Vice counties {st.vice_counties:,} · Recorders (names as given) {st.recorders:,}{tail}")


def first_last_line(st: MapStats, in_view: bool = False) -> str:
    tail = " (in view)" if in_view else ""
    if st.first is None:
        return "No dated records" + tail
    return f"First record {when_text(st.first)} · Last record {when_text(st.last)}{tail}"


def decades_line(st: MapStats, in_view: bool = False) -> str:
    parts = [f"{lab} {n:,}" for lab, n in st.decades]
    if st.undated:
        parts.append(f"undated {st.undated:,}")
    return "Records by decade: " + " · ".join(parts) + (" (in view)" if in_view else "")


def month_note(st: MapStats) -> str:
    n = sum(st.months)
    return (f"n = {n:,}; {st.no_month:,} record{'s' if st.no_month != 1 else ''} "
            f"not dated to a single day")


def range_note(st: MapStats) -> str:
    """Said when ranges / before-after dates were left out of first / last and decades."""
    n = st.ranged
    if not n:
        return ""
    return (f"{n:,} record{'s' if n != 1 else ''} with a date range or 'before/after' date "
            f"{'are' if n != 1 else 'is'} not in first/last or decades")
