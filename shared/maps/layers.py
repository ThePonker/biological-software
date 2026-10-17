"""The Mapping tab's map background layers: registry and loader (17 Oct 2026).

The layer files are made by scripts/build_map_layers.py into data/maps/layers/, one JSON file
per layer and level of detail, `<key>_<lod>.json` (lod "gb" or "county"; coordinates are
integer OSGB metres; each feature carries its bbox). Any of them may be missing: nothing here
fails then, and the map draws as it did before the layers existed.

Display only. Colours come from theme() (blended; the sea blue is the map's own _SEA_C), never typed in.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

from PySide6.QtGui import QColor

from shared.maps._theme import theme
from shared.maps.species_dist_map import _SEA_C

LAYERS_SUBDIR = "layers"
COUNTY_SPAN = 250000.0      # a view this wide or less (metres) uses the county detail; the 10 km grid's rule
OS_CREDIT = "Contains OS data © Crown copyright and database right 2026."
LODS = ("county", "gb")


@dataclass(frozen=True)
class Layer:
    """One drawn layer. toggle: the menu switch that turns it on (None: land and districts,
    which have their own place)."""
    key: str
    kind: str                   # "polygon" or "line"
    toggle: Optional[str] = None


@dataclass(frozen=True)
class Toggle:
    """One tick-able item of the Layers menu; `files` are the layer keys it turns on."""
    key: str
    label: str
    default: bool
    files: Tuple[str, ...]


# bottom to top: land, woodland, towns, water areas, rivers, main roads (the VC tint, coast,
# grid, VC boundaries and districts are drawn between and above them by map_layers.py)
LAYERS = (
    Layer("land", "polygon"),
    Layer("woodland", "polygon", "woodland"),
    Layer("towns", "polygon", "towns"),
    Layer("water", "polygon", "water"),
    Layer("rivers", "line", "water"),
    Layer("roads", "line", "roads"),
    Layer("districts", "polygon"),
)
TOGGLES = (                 # the menu, in draw order
    Toggle("woodland", "Woodland", False, ("woodland",)),
    Toggle("towns", "Towns", False, ("towns",)),
    Toggle("water", "Rivers and lakes", True, ("water", "rivers")),
    Toggle("roads", "Main roads", False, ("roads",)),
)
NOT_INSTALLED = "Not installed: run scripts\\build_map_layers.py"


def defaults() -> Set[str]:
    """The toggles that are on until the user chooses otherwise."""
    return {t.key for t in TOGGLES if t.default}


def lod_for_extent(extent: Sequence[float]) -> str:
    """"county" when the view spans <= 250 km (the 10 km grid's rule), else "gb"."""
    e0, n0, e1, n1 = extent
    return "county" if max(e1 - e0, n1 - n0) <= COUNTY_SPAN else "gb"


def layers_dir(maps_dir) -> Optional[Path]:
    return Path(maps_dir) / LAYERS_SUBDIR if maps_dir else None


def file_path(maps_dir, key: str, lod: str) -> Optional[Path]:
    """The file for a layer at a level of detail; the other level's file if that one is
    missing; None when neither exists."""
    d = layers_dir(maps_dir)
    if d is None:
        return None
    for one in (lod,) + tuple(x for x in LODS if x != lod):
        p = d / f"{key}_{one}.json"
        if p.is_file():
            return p
    return None


def available(maps_dir) -> Set[str]:
    """Layer keys with at least one file in data/maps/layers/."""
    return {lay.key for lay in LAYERS if file_path(maps_dir, lay.key, "gb") is not None}


def toggle_available(avail: Set[str], toggle: Toggle) -> bool:
    return any(f in avail for f in toggle.files)


_CACHE: Dict[tuple, List[dict]] = {}


def load(maps_dir, key: str, lod: str) -> List[dict]:
    """The layer's features (dicts with "bbox" and "rings" or "line", OSGB metres), cached per
    file. [] when there is no file or it cannot be read."""
    path = file_path(maps_dir, key, lod)
    if path is None:
        return []
    try:
        ck = (str(path), path.stat().st_mtime_ns)
        if ck not in _CACHE:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            _CACHE[ck] = [f for f in data.get("features", [])
                          if isinstance(f, dict) and (f.get("rings") or f.get("line"))]
        return _CACHE[ck]
    except Exception:
        return []


def features_in(features: Sequence[dict], view_bbox: Sequence[float]) -> List[dict]:
    """The features whose bbox meets the view box (OSGB e0, n0, e1, n1); one with no bbox is kept."""
    e0, n0, e1, n1 = view_bbox
    out = []
    for f in features:
        b = f.get("bbox")
        if b is None or (b[0] <= e1 and b[2] >= e0 and b[1] <= n1 and b[3] >= n0):
            out.append(f)
    return out


def _mix(a: str, b: str, t: float) -> QColor:
    """a blended toward b by t (0-1)."""
    ca, cb = QColor(a), QColor(b)
    return QColor(*(round(x * (1 - t) + y * t) for x, y in
                    ((ca.red(), cb.red()), (ca.green(), cb.green()), (ca.blue(), cb.blue()))))


def style(key: str) -> Tuple[Optional[QColor], Optional[QColor], float]:
    """(fill, line, line width in px at k = 1) for a layer key: pale, so the squares stay the
    strongest thing on the map."""
    if key == "woodland":
        return _mix(_mix(theme.MOSS, theme.MUTED, 0.3).name(), theme.CARD, 0.72), None, 0.3
    if key == "towns":
        return _mix(_mix(theme.MUTED, theme.GOLD, 0.25).name(), theme.CARD, 0.78), None, 0.3
    if key == "water":
        return _mix(_SEA_C, theme.SLATE, 0.2), None, 0.3
    if key == "rivers":
        return None, _mix(_SEA_C, theme.SLATE, 0.4), 0.6
    if key == "roads":
        return None, _mix(theme.MUTED, theme.CARD, 0.5), 0.6
    return None, None, 0.0
