"""Spread over time (R9-7, 11 Oct 2026): date-class maps and year-by-year / decade frames,
worked out from a map's squares (map_square_service.squares_for: each square's first_year,
last_year and undated count). Pure Python, no Qt, no database.

Date classes: each square coloured by the period of its FIRST record (when the taxon
arrived there) or its MOST RECENT record (the Mapping tab's Date classes style). Classes
are given as the first years of the later periods: (1970, 2000, 2020) ->
Pre-1970 / 1970–1999 / 2000–2019 / 2020+. A square with only undated records is "Undated".

Frames: one per year or decade, cumulative -- a frame shows every square with a dated record
up to the end of its period; the squares new in that period are marked. Undated-only
squares never appear in a frame (they are counted, to say so).
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

UNDATED = "undated"
DEFAULT_BREAKS = (1970, 2000, 2020)

# Sequential, light (old) to dark (recent): one warm hue family, so the order reads without
# a key; the palest still stands out on the map's pale green land. Ramp extended by mixing.
DATE_RAMP = ["#f3d27a", "#e39a3b", "#b5562a", "#6b2412"]
FRAME_OLD = "#9a7555"          # squares from earlier frames (the Mapping tab's dark accent)
FRAME_NEW = "#0072B2"          # squares new in this frame (first of square_style.TAXON_PALETTE)


def parse_breaks(text: str) -> Tuple[int, ...]:
    """'1970,2000,2020' -> (1970, 2000, 2020): sorted, distinct. Raises ValueError."""
    years = sorted({int(t) for t in str(text).replace(";", ",").split(",") if t.strip()})
    if not years:
        raise ValueError("give at least one year, e.g. 1970,2000,2020")
    if any(y < 1000 or y > 2999 for y in years):
        raise ValueError("years must be four digits")
    return tuple(years)


def date_classes(breaks: Sequence[int] = DEFAULT_BREAKS) -> List[dict]:
    """[{name, label, first, last}] oldest first; first/last None = open-ended."""
    b = sorted(breaks)
    out = [{"name": "c0", "label": f"Pre-{b[0]}", "first": None, "last": b[0] - 1}]
    for i, y in enumerate(b):
        nxt = b[i + 1] if i + 1 < len(b) else None
        label = f"{y}+" if nxt is None else f"{y}–{nxt - 1}"
        out.append({"name": f"c{i + 1}", "label": label, "first": y,
                    "last": None if nxt is None else nxt - 1})
    return out


def class_of(year: Optional[int], classes: Sequence[dict]) -> str:
    if year is None:
        return UNDATED
    for c in classes:
        if c["last"] is None or year <= c["last"]:
            return c["name"]
    return classes[-1]["name"]


def _mix(a: str, b: str, t: float) -> str:
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


def ramp(n: int, stops: Sequence[str] = DATE_RAMP) -> List[str]:
    """n colours along the stops, light to dark."""
    if n <= 1:
        return [stops[-1]]
    out = []
    for i in range(n):
        x = i * (len(stops) - 1) / (n - 1)
        j = min(int(x), len(stops) - 2)
        out.append(_mix(stops[j], stops[j + 1], x - j))
    return out


def colour_by_date_class(squares: Dict[str, dict], breaks: Sequence[int] = DEFAULT_BREAKS,
                         by: str = "first", undated_colour: str = "#9e9e9e") -> list:
    """Set each square's 'fill' (and 'date_class') by the period of its first (by='first')
    or most recent (by='last') dated record; return the legend [(colour, label)] for the
    classes present, oldest first, then Undated."""
    if by not in ("first", "last"):
        raise ValueError("by must be 'first' or 'last'")
    classes = date_classes(breaks)
    colours = dict(zip((c["name"] for c in classes), ramp(len(classes))))
    colours[UNDATED] = undated_colour
    used = set()
    for sq in squares.values():
        sq.pop("fills", None)
        name = class_of(sq.get(f"{by}_year"), classes)
        sq["date_class"] = name
        sq["fill"] = colours[name]
        used.add(name)
    word = "First record" if by == "first" else "Latest record"
    legend = [(colours[c["name"]], f"{word} {c['label']}") for c in classes if c["name"] in used]
    if UNDATED in used:
        legend.append((undated_colour, "Undated only"))
    return legend


# ---------------------------------------------------------------- frames

def periods(first: int, last: int, step: str = "decade",
            start: Optional[int] = None) -> List[Tuple[int, int, str]]:
    """[(from, to, label)] covering first..last: decades ('1980s') or single years. `start`
    moves the first period (earlier records then fall into it: 'to 1969')."""
    if step not in ("decade", "year"):
        raise ValueError("step must be 'decade' or 'year'")
    out = []
    if step == "year":
        y0 = max(first, start) if start else first
        if y0 > first:
            out.append((first, y0 - 1, f"to {y0 - 1}"))
        for y in range(y0, last + 1):
            out.append((y, y, str(y)))
        return out
    d0 = (max(first, start) if start else first) // 10 * 10
    if d0 > first:
        out.append((first, d0 - 1, f"to {d0 - 1}"))
    for d in range(d0, last // 10 * 10 + 1, 10):
        out.append((d, d + 9, f"{d}s"))
    return out


def frames(squares: Dict[str, dict], step: str = "decade", start: Optional[int] = None
           ) -> Tuple[List[dict], int]:
    """([{from, to, label, squares: {label: 'old'|'new'}, total, new}], undated-only squares).
    Cumulative: a square appears in the frame of its first dated record and every later
    frame ('new' in the first, 'old' after)."""
    dated = {k: sq["first_year"] for k, sq in squares.items() if sq.get("first_year") is not None}
    undated_only = len(squares) - len(dated)
    if not dated:
        return [], undated_only
    out = []
    for a, b, label in periods(min(dated.values()), max(dated.values()), step, start):
        shown = {k: ("new" if y >= a else "old") for k, y in dated.items() if y <= b}
        out.append({"from": a, "to": b, "label": label, "squares": shown, "total": len(shown),
                    "new": sum(1 for v in shown.values() if v == "new")})
    return out, undated_only


def frame_squares(squares: Dict[str, dict], frame: dict, old: str = FRAME_OLD,
                  new: str = FRAME_NEW) -> Tuple[Dict[str, dict], list]:
    """(the frame's squares, coloured -- copies, the map's own are untouched; legend)."""
    out = {}
    for k, state in frame["squares"].items():
        sq = dict(squares[k])
        sq.pop("fills", None)
        sq["fill"] = new if state == "new" else old
        out[k] = sq
    legend = []
    if any(v == "old" for v in frame["squares"].values()):
        legend.append((old, f"Recorded before {frame['from']}"))
    legend.append((new, f"New {frame['label']}" if not frame["label"].startswith("to ")
                   else f"Recorded {frame['label']}"))
    return out, legend
