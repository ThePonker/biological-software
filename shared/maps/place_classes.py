"""The place-name classes of the Mapping tab's "Place names" layer: the ONE table (18 Oct 2026).

Used by scripts/build_map_layers.py (which classes go in which layer file) and by place_names.py
(which are drawn at which zoom, and how big). No Qt, no shapely: plain Python.

Zoomstack's class values are matched ignoring case; any other value (a road, a landform, a
building ...) is not a place name here and is left out. `--describe names` lists what the
file really holds.
"""
from __future__ import annotations

from typing import Dict, NamedTuple, Optional, Tuple


class PlaceClass(NamedTuple):
    key: str                     # "city" ...
    values: Tuple[str, ...]      # the source's class values, lower case
    max_span_m: Optional[float]  # drawn when the view is this wide or narrower (None: always)
    pt: float                    # label size in points (device pixels, never scaled by zoom)
    bold: bool
    lod: str                     # the layer file that holds it: "gb" (whole country) or "county"


# biggest first: this is also the order labels are placed in (a village never hides a city)
PLACE_CLASSES = (
    PlaceClass("city", ("city", "capital"), None, 10.0, True, "gb"),
    PlaceClass("town", ("town",), 250_000.0, 9.0, False, "county"),
    PlaceClass("village", ("village",), 60_000.0, 8.0, False, "county"),
    PlaceClass("hamlet", ("hamlet", "suburban area", "other settlement"),
               20_000.0, 7.5, False, "county"),
    # Zoomstack spells this type "Small Settlements" (plural); both spellings are matched
    PlaceClass("small settlement", ("small settlements", "small settlement"),
               8_000.0, 7.0, False, "county"),
)

_BY_VALUE: Dict[str, int] = {v: i for i, c in enumerate(PLACE_CLASSES) for v in c.values}


def rank_of(raw) -> int:
    """Index into PLACE_CLASSES of a source class value, or -1 if it is not a place class."""
    return _BY_VALUE.get(str(raw or "").strip().lower(), -1)


def source_values(lod: str) -> Tuple[str, ...]:
    """The (lower case) source values the layer file for `lod` holds."""
    return tuple(v for c in PLACE_CLASSES if c.lod == lod for v in c.values)


def shown_at(span_m: float):
    """The classes (in placing order) drawn when the view is `span_m` metres across."""
    return [i for i, c in enumerate(PLACE_CLASSES) if c.max_span_m is None or span_m <= c.max_span_m]
