"""How the Mapping tab colours its squares, and the legend that says so (backlog H3).

Three display styles, matching the filter panel's Display Style list:
    presence  -- every recorded square the same colour
    density   -- four classes by number of records
    date      -- the time-period band of the square's most recent record
"""
from typing import Dict, List, Tuple

DENSITY_CLASSES = [(1, 1, "1 record"), (2, 4, "2–4"), (5, 19, "5–19"),
                   (20, None, "20 or more")]


def _mix(a: str, b: str, t: float) -> str:
    """Blend two #rrggbb colours: t = 0 gives a, 1 gives b."""
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


def style_key(combo_text: str) -> str:
    t = (combo_text or "").lower()
    if t.startswith("density"):
        return "density"
    if t.startswith("date"):
        return "date"
    return "presence"


def density_class(count: int) -> int:
    for i, (lo, hi, _label) in enumerate(DENSITY_CLASSES):
        if count >= lo and (hi is None or count <= hi):
            return i
    return 0


def colour_squares(squares: Dict[str, dict], style: str, band_colours: Dict[str, str],
                   band_labels: Dict[str, str], light: str, dark: str
                   ) -> List[Tuple[str, str]]:
    """Set each square's 'fill' for the style; return the legend [(colour, label)]."""
    if style == "date":
        for sq in squares.values():
            sq["fill"] = band_colours.get(sq.get("band"), dark)
        used = {sq.get("band") for sq in squares.values()}
        return [(band_colours[b], band_labels.get(b, b)) for b in band_colours if b in used]
    if style == "density":
        ramp = [_mix(light, dark, t) for t in (0.35, 0.6, 0.8, 1.0)]
        for sq in squares.values():
            sq["fill"] = ramp[density_class(sq.get("count", 0))]
        used = {density_class(sq.get("count", 0)) for sq in squares.values()}
        return [(ramp[i], DENSITY_CLASSES[i][2]) for i in range(len(ramp)) if i in used]
    for sq in squares.values():
        sq["fill"] = dark
    return [(dark, "Recorded")] if squares else []
