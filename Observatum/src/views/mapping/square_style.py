"""How the Mapping tab colours its squares, and the legend that says so (backlog H3; item 4).

Display styles (the Style list above the map):
    presence  -- every recorded square the same colour
    density   -- classes by number of records
    richness  -- classes by number of distinct species in the selection (e.g. all Cerambycidae:
                 longhorn species per hectad / tetrad / monad)
    date      -- the time-period band of the square's most recent dated record; squares with
                 only undated records are their own class (MAP5)
    taxon     -- each chosen taxon (chip) its own colour; a square holding records of more
                 than one is drawn split between their colours ("overlap"). Wil, 10 Oct 2026:
                 "at the minute there is no distinction between what you are mapping".
With one taxon chosen, Presence uses that taxon's colour (e.g. one species in green).

Legend entries are (colour, label); the overlap entry's colour is a tuple of colours, drawn
as a split swatch.
"""
from typing import Dict, Optional, Sequence, Tuple

DENSITY_CLASSES = [(1, 1, "1 record"), (2, 4, "2–4"), (5, 19, "5–19"),
                   (20, None, "20 or more")]
RICHNESS_CLASSES = [(1, 1, "1 species"), (2, 4, "2–4 species"), (5, 9, "5–9"),
                    (10, 19, "10–19"), (20, 49, "20–49"), (50, 99, "50–99"),
                    (100, None, "100 or more")]
STYLES = [("presence", "Presence (filled squares)"), ("taxon", "By taxon (colour each)"),
          ("density", "Density (records)"), ("richness", "Species richness"),
          ("date", "Date classes (time period)")]

# Default colours for the chosen taxa, in order: Okabe & Ito's colour-blind-safe set (no
# black; yellow late, it is faint on the pale land), then two more.
TAXON_PALETTE = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#D55E00", "#56B4E9",
                 "#F0E442", "#7F3C8D", "#5A5A5A"]
MAX_SPLIT = 4            # a square is split between at most this many taxa's colours


def default_taxon_colour(used: Sequence[str]) -> str:
    """The first palette colour not already used by another chip (case-insensitive)."""
    taken = {c.lower() for c in used if c}
    for c in TAXON_PALETTE:
        if c.lower() not in taken:
            return c
    return TAXON_PALETTE[len(taken) % len(TAXON_PALETTE)]

# The time-period palette (was MapDataService.get_band_config's)
BAND_PALETTE = {"historical": "#e8d5c4", "recent": "#c2956e", "current": "#9a7555"}


def band_colours(band_names, undated_colour: str) -> Dict[str, str]:
    """{band: colour} for the bands in order, then 'undated'."""
    out = {b: BAND_PALETTE.get(b, "#c2956e") for b in band_names if b != "undated"}
    out["undated"] = undated_colour
    return out


def _mix(a: str, b: str, t: float) -> str:
    """Blend two #rrggbb colours: t = 0 gives a, 1 gives b."""
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


def style_key(combo_text: str) -> str:
    t = (combo_text or "").lower()
    for key, label in STYLES:
        if t == label.lower() or t.startswith(key):
            return key
    if t.startswith("species"):
        return "richness"
    return "presence"


def _class_of(n: int, classes) -> int:
    for i, (lo, hi, _label) in enumerate(classes):
        if n >= lo and (hi is None or n <= hi):
            return i
    return 0


def density_class(count: int) -> int:
    return _class_of(count, DENSITY_CLASSES)


def richness_class(species: int) -> int:
    return _class_of(species, RICHNESS_CLASSES)


def _ramp_style(squares, classes, field, light, dark):
    """Colour by class; the ramp spans the classes actually used, light to dark."""
    used = sorted({_class_of(sq.get(field, 0), classes) for sq in squares.values()})
    if not used:
        return []
    steps = len(used)
    ramp = {c: _mix(light, dark, 0.35 + 0.65 * (i / (steps - 1) if steps > 1 else 1.0))
            for i, c in enumerate(used)}
    for sq in squares.values():
        sq["fill"] = ramp[_class_of(sq.get(field, 0), classes)]
    return [(ramp[c], classes[c][2]) for c in used]


def colour_squares(squares: Dict[str, dict], style: str, band_colours: Dict[str, str],
                   band_labels: Dict[str, str], light: str, dark: str,
                   taxa: Optional[Sequence[Tuple[str, str]]] = None) -> list:
    """Set each square's 'fill' (and, By taxon, 'fills' for a split square) for the style;
    return the legend [(colour, label)]. taxa: the chips as (name, colour), in chip order;
    a square's 'chips' index them."""
    taxa = list(taxa or [])
    for sq in squares.values():
        sq.pop("fills", None)
    if style == "taxon" and taxa:
        return _taxon_style(squares, taxa)
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
    if style == "richness":
        with_species = {k: sq for k, sq in squares.items() if sq.get("species")}
        legend = _ramp_style(with_species, RICHNESS_CLASSES, "species", light, dark)
        if len(with_species) < len(squares):   # records named only to genus or above
            pale = _mix(light, dark, 0.15)
            for k, sq in squares.items():
                if k not in with_species:
                    sq["fill"] = pale
            legend = [(pale, "No species-level record")] + legend
        return legend
    colour, label = (taxa[0][1], taxa[0][0]) if len(taxa) == 1 else (dark, "Recorded")
    for sq in squares.values():
        sq["fill"] = colour
    return [(colour, label)] if squares else []


def _taxon_style(squares, taxa) -> list:
    """By taxon: one colour per chip; a square with several chips' records is split."""
    used, overlap = set(), []
    for sq in squares.values():
        idx = [i for i in sq.get("chips") or () if 0 <= i < len(taxa)]
        if not idx:                         # cannot happen with chips chosen; keep it visible
            sq["fill"] = "#9e9e9e"
            continue
        used.update(idx)
        sq["fill"] = taxa[idx[0]][1]
        if len(idx) > 1:
            sq["fills"] = [taxa[i][1] for i in idx[:MAX_SPLIT]]
            overlap.append(sq["fills"])
    legend = [(taxa[i][1], taxa[i][0]) for i in range(len(taxa)) if i in used]
    if overlap:
        n = max(len(f) for f in overlap)
        cols = tuple(next(f for f in overlap if len(f) == n))
        legend.append((cols, "Overlap (square split between taxa)"))
    return legend
