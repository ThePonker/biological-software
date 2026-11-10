"""The Mapping tab's map background layers: registry and loader (17 Oct 2026).

The layer files are made by scripts/build_map_layers.py into data/maps/layers/, one JSON file
per layer and level of detail, `<key>_<lod>.json` (lod "gb" or "county"; coordinates are
integer OSGB metres; each feature carries its bbox). Any of them may be missing: nothing here
fails then, and the map draws as it did before the layers existed.

18 Oct 2026: six more layers, all off by default: place names (points), railways, national
parks, foreshore, parks and green space, and relief (an image: relief.py). A names feature is
{"bbox", "pt": [e, n], "n": name, "t": class}; place_classes.py is the table of classes.

Display only. Colours come from theme() (blended; the sea blue is the map's own _SEA_C), never typed in;
the Layers menu's "Colours..." can override each toggle's colour (QSettings, hex), else these defaults.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

import numpy as np

from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor

from shared import crash_log
from shared.maps import env_registry as env
from shared.maps import layer_bin
from shared.maps._theme import theme
from shared.maps.species_dist_map import _SEA_C

LAYERS_SUBDIR = "layers"
COUNTY_SPAN = 250000.0      # a view this wide or less (metres) uses the county detail; the 10 km grid's rule
YEAR = env.YEAR             # the credits' year (from date.today().year)
OS_CREDIT = env.OS_PART
LODS = ("county", "gb")


@dataclass(frozen=True)
class Layer:
    """One drawn layer. toggle: the menu switch that turns it on (None: land and districts,
    which have their own place)."""
    key: str
    kind: str                   # "polygon", "line", "point" (place names) or "image" (relief)
    toggle: Optional[str] = None


@dataclass(frozen=True)
class Toggle:
    """One tick-able item of the Layers menu; `files` are the layer keys it turns on."""
    key: str
    label: str
    default: bool
    files: Tuple[str, ...]
    colour: bool = True         # False: nothing to choose in Colours... (the relief is grey)
    group: str = ""             # "Environment": the Layers menu's sub-menu (env_registry.py)
    section: str = ""           # its heading inside that sub-menu
    short: str = ""             # what Identify calls it (else the label)
    credits: Tuple[str, ...] = ()   # shown with the map when the layer is drawn (credits_for)
    hidden_unless: str = ""     # a QSettings key that must be on for the toggle to exist


# bottom to top: land, relief, foreshore, parks and green space, woodland, towns, water areas,
# rivers, national parks, railways, main roads (the VC tint, coast, grid, VC boundaries and
# districts are drawn between and above them by map_layers.py). The place names are text: GridMap
# draws them last of all, over the squares (place_names.py).
_BASE_LAYERS = (
    Layer("land", "polygon"),
    Layer("relief", "image", "relief"),
    Layer("foreshore", "polygon", "foreshore"),
    Layer("greenspace", "polygon", "greenspace"),
    Layer("woodland", "polygon", "woodland"),
    Layer("towns", "polygon", "towns"),
    Layer("water", "polygon", "water"),
    Layer("rivers", "line", "water"),
    Layer("national_parks", "polygon", "national_parks"),
    Layer("rail", "line", "rail"),
    Layer("roads", "line", "roads"),
    Layer("districts", "polygon"),
    Layer("names", "point", "names"),
)
_BASE_TOGGLES = (           # the menu
    Toggle("woodland", "Woodland", False, ("woodland",)),
    Toggle("towns", "Towns", False, ("towns",)),
    Toggle("water", "Rivers and lakes", True, ("water", "rivers")),
    Toggle("roads", "Main roads", False, ("roads",)),
    Toggle("names", "Place names", False, ("names",)),
    Toggle("rail", "Railways", False, ("rail",)),
    Toggle("national_parks", "National parks", False, ("national_parks",)),
    Toggle("foreshore", "Foreshore", False, ("foreshore",)),
    Toggle("greenspace", "Parks and green space", False, ("greenspace",)),
    Toggle("relief", "Relief", False, ("relief",), colour=False),
)


def _env_layers(place: str):
    return tuple(Layer(e.key, e.kind, e.key) for e in env.ENV_LAYERS if e.place == place)


def _stack():
    """The base stack with the Environment layers slotted in (env_registry.py): the under ones
    just above the land (the relief shades them), the mid ones after woodland, the top ones
    after the national parks."""
    out = []
    for lay in _BASE_LAYERS:
        out.append(lay)
        if lay.key == "land":
            out.extend(_env_layers(env.UNDER))
        elif lay.key == "woodland":
            out.extend(_env_layers(env.MID))
        elif lay.key == "national_parks":
            out.extend(_env_layers(env.TOP))
    return tuple(out)


LAYERS = _stack()
TOGGLES = _BASE_TOGGLES + tuple(      # all off; grids and Soilscapes have no colour to choose
    Toggle(e.key, e.label, False, (e.key,), colour=(e.kind != "grid"), group=env.GROUP,
           section=e.section, short=e.short, credits=e.credits, hidden_unless=e.hidden_unless)
    for e in env.ENV_LAYERS)
DASHES = {"rail": (4.0, 3.0)}   # dash, gap (in line widths) of a dashed line layer
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
    if lod == "gb" and key in env.COUNTY_ONLY:
        return None                 # county detail only: nothing to draw at GB scale
    for one in (lod,) + tuple(x for x in LODS if x != lod):
        p = d / f"{key}_{one}.json"
        if p.is_file():
            return p
    return None


def kind_of(key: str) -> str:
    return next((lay.kind for lay in LAYERS if lay.key == key), "")


def available(maps_dir) -> Set[str]:
    """Layer keys with at least one file in data/maps/layers/ (the relief needs its image too, a
    value grid its .bin)."""
    d = layers_dir(maps_dir)
    ext = {"image": ".png", "grid": ".bin"}
    return {lay.key for lay in LAYERS if file_path(maps_dir, lay.key, "county") is not None
            and (lay.kind not in ext or (d / f"{lay.key}_gb{ext[lay.kind]}").is_file())}


def setting_on(name: str) -> bool:
    """A yes/no setting (QSettings), False when missing or unreadable."""
    try:
        return QSettings().value(name, False, type=bool)
    except Exception:
        return False


def toggle_visible(toggle: Toggle) -> bool:
    """False for a toggle whose setting is off (Soilscapes: env_registry.SOILSCAPES_SETTING)."""
    return not toggle.hidden_unless or setting_on(toggle.hidden_unless)


def visible_toggles() -> Tuple[Toggle, ...]:
    return tuple(t for t in TOGGLES if toggle_visible(t))


def credits_for(keys) -> List[str]:
    """The data credits of the Environment layers among `keys` (layer keys, as GridMap.layers_drawn()
    gives, or toggle keys), each text once, in the registry's order. The OS credit is not here: the
    caller still adds OS_CREDIT for any layer file drawn."""
    want = set(keys or ())
    out: List[str] = []
    for t in TOGGLES:
        if t.credits and (t.key in want or any(f in want for f in t.files)):
            out.extend(c for c in t.credits if c not in out)
    return out


def legend_notes(maps_dir, keys) -> List[str]:
    """One legend line for each value grid among `keys` (palest to darkest)."""
    from shared.maps import value_grid
    notes = []
    for lay in LAYERS:
        if lay.kind == "grid" and lay.key in set(keys or ()):
            g = value_grid.load(maps_dir, lay.key)
            if g is not None:
                notes.append(g.legend_text())
    return notes


def credit_lines(maps_dir, keys, os_always: bool = False, extra: Sequence[str] = ()) -> List[str]:
    """The data credits for what is drawn, each text once, in order: the OS credit (when any layer
    file is drawn, or `os_always`), the ticked Environment layers' credits, the value grids' legend
    notes (with a full stop), then `extra`. One helper for the atlas page and the 3D export."""
    out: List[str] = []
    keys = list(keys or ())
    parts = ([OS_CREDIT] if keys or os_always else []) + credits_for(keys) + \
        [n.rstrip(".") + "." for n in legend_notes(maps_dir, keys)] + list(extra)
    for c in parts:
        if c and c not in out:
            out.append(c)
    return out


def toggle_available(avail: Set[str], toggle: Toggle) -> bool:
    return any(f in avail for f in toggle.files)


_CACHE: Dict[tuple, object] = {}    # (json path, mtime) -> list of feature dicts, or a layer_bin.LayerBin
_BOXES: Dict[int, tuple] = {}       # id(feature list) -> (the list, its (F, 4) bbox array)
_LOCK = threading.RLock()


def forget(key: str) -> None:
    """Drop a layer's features from the cache (both levels of detail): called when its toggle is
    unticked, so big county layers (PHI, NFI, Living England) do not stay in memory."""
    names = {f"{key}_{lod}.json" for lod in LODS}
    with _LOCK:
        for ck in [c for c in _CACHE if Path(c[0]).name in names]:
            _BOXES.pop(id(_CACHE[ck]), None)
            del _CACHE[ck]


_ERRORS: Dict[str, str] = {}        # "key_lod" -> why that layer file could not be loaded (load_errors())
_NOTED: Set[tuple] = set()          # (json path, mtime) already written to the crash log


def load_errors() -> Dict[str, str]:
    """The layer files that could not be loaded, as {"<key>_<lod>": message}; a file that later
    loads is removed. The map draws the layer as empty and shows these in a corner note."""
    with _LOCK:
        return dict(_ERRORS)


def _failed(path: Path, ck, name: str, exc: BaseException) -> None:
    """Remember the failure (shown by load_errors) and write it to the crash log once per file."""
    try:
        with _LOCK:
            _ERRORS[name] = f"{type(exc).__name__}: {exc}"[:200]
            if ck in _NOTED:
                return
            _NOTED.add(ck)
        crash_log.note(f"Map layer {path.name} could not be loaded", exc)
    except Exception:
        pass


def load(maps_dir, key: str, lod: str):
    """The layer's features, cached per file: a list of dicts ("bbox" and "rings", "line" or "pt",
    OSGB metres) read from the JSON, or, when the binary form is there and matches
    (layer_bin.py), a LayerBin: a sequence of dict-like features made only when asked for. []
    when there is no file or it cannot be read."""
    path = file_path(maps_dir, key, lod)
    if path is None:
        return []
    ck = None
    try:
        ck = (str(path), path.stat().st_mtime_ns)
        with _LOCK:             # the map's warm-up may be reading it: wait, do not read twice
            if ck not in _CACHE:
                data = layer_bin.read(path)
                if data is None:
                    with open(path, encoding="utf-8") as fh:
                        doc = json.load(fh)
                    data = [f for f in doc.get("features", [])
                            if isinstance(f, dict) and (f.get("rings") or f.get("line") or f.get("pt"))]
                _CACHE[ck] = data
            _ERRORS.pop(f"{key}_{lod}", None)
            return _CACHE[ck]
    except Exception as e:          # MemoryError too: the map still draws, without this layer
        _failed(path, ck or (str(path), -1), f"{key}_{lod}", e)
        return []


def features_in(features: Sequence, view_bbox: Sequence[float]) -> list:
    """The features whose bbox meets the view box (OSGB e0, n0, e1, n1); one with no bbox is kept."""
    if isinstance(features, layer_bin.LayerBin):
        return [features[int(i)] for i in features.in_box(view_bbox)]
    e0, n0, e1, n1 = view_bbox
    out = []
    for f in features:
        b = f.get("bbox")
        if b is None or (b[0] <= e1 and b[2] >= e0 and b[1] <= n1 and b[3] >= n0):
            out.append(f)
    return out


def candidates(features: Sequence, e: float, n: float) -> list:
    """The features whose bbox holds the point (e, n), in order: a numpy test on a (F, 4) array
    kept per loaded list (identify's prefilter); the exact ring test is still the caller's."""
    if isinstance(features, layer_bin.LayerBin):
        return [features[int(i)] for i in features.containing(e, n)]
    if not len(features):
        return []
    with _LOCK:
        hit = _BOXES.get(id(features))
        if hit is None or hit[0] is not features:
            hit = (features, layer_bin.bbox_array([f.get("bbox") for f in features]))
            _BOXES[id(features)] = hit
    b = hit[1]
    ok = (b[:, 0] <= e) & (b[:, 2] >= e) & (b[:, 1] <= n) & (b[:, 3] >= n)
    return [features[int(i)] for i in np.nonzero(ok)[0]]


def _mix(a: str, b: str, t: float) -> QColor:
    """a blended toward b by t (0-1)."""
    ca, cb = QColor(a), QColor(b)
    return QColor(*(round(x * (1 - t) + y * t) for x, y in
                    ((ca.red(), cb.red()), (ca.green(), cb.green()), (ca.blue(), cb.blue()))))


COLOUR_SETTING = "mapping/layers/{}/colour"     # + the toggle key: the remembered colour (hex)


def toggle_key(layer_key: str) -> Optional[str]:
    """The Layers menu switch whose colour a layer uses (water areas and rivers share one)."""
    return next((t.key for t in TOGGLES if layer_key in t.files), None)


_COLOURS: Optional[Dict[str, Optional[str]]] = None     # toggle key -> remembered hex, read once


def _colour_cache() -> Dict[str, Optional[str]]:
    """Every toggle's remembered colour (hex or None), read from QSettings once and kept: the setters
    below keep it current, so a paint never reads QSettings (25 Oct 2026)."""
    global _COLOURS
    if _COLOURS is None:
        out: Dict[str, Optional[str]] = {}
        try:
            s = QSettings()
            for t in TOGGLES:
                text = s.value(COLOUR_SETTING.format(t.key), "")
                c = QColor(str(text)) if text else QColor()
                out[t.key] = c.name() if c.isValid() else None
        except Exception:
            pass
        _COLOURS = out
    return _COLOURS


def reload_settings() -> None:
    """Forget the in-memory colours: the next use reads QSettings again (a test that clears them)."""
    global _COLOURS
    _COLOURS = None


def saved_colour(tkey: str) -> Optional[QColor]:
    """The colour remembered for a toggle, or None (the default is used)."""
    hx = _colour_cache().get(tkey)
    return QColor(hx) if hx else None


def set_colour(tkey: str, colour) -> None:
    """Remember a toggle's colour (a QColor / hex); None forgets it."""
    _colour_cache()[tkey] = None if colour is None else QColor(colour).name()
    try:
        s = QSettings()
        if colour is None:
            s.remove(COLOUR_SETTING.format(tkey))
        else:
            s.setValue(COLOUR_SETTING.format(tkey), QColor(colour).name())
    except Exception as e:
        print(f"[map layers] colour {tkey} not saved: {e}")


def reset_colours() -> None:
    for t in TOGGLES:
        set_colour(t.key, None)


def saved_colours() -> Tuple[Optional[str], ...]:
    """Every toggle's remembered colour as hex (None: default), in TOGGLES order; a cheap
    key for 'have the colours changed'."""
    cache = _colour_cache()
    return tuple(cache.get(t.key) for t in TOGGLES)


def default_style(key: str) -> Tuple[Optional[QColor], Optional[QColor], float]:
    """(fill, line, line width in px at k = 1) for a layer key from the theme: pale, so the
    squares stay the strongest thing on the map."""
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
    if key == "rail":
        return None, _mix(theme.MUTED, theme.CARD, 0.3), 0.7
    if key == "national_parks":
        return None, _mix(theme.MOSS_HOVER, theme.CARD, 0.15), 1.0
    if key == "foreshore":
        return _mix(_mix(theme.GOLD, theme.MOSS, 0.4).name(), theme.CARD, 0.72), None, 0.3
    if key == "greenspace":
        return _mix(_mix(theme.MOSS, theme.GOLD, 0.15).name(), theme.CARD, 0.6), None, 0.3
    if key in env.ENV_BY_KEY and env.ENV_BY_KEY[key].kind == "polygon":
        return env_style(key)
    if key == "names":      # the ink of the place names (a line colour: they have no fill)
        return None, _mix(theme.INK, theme.MUTED, 0.5), 0.0
    return None, None, 0.0


def _token(name: str) -> str:
    return _SEA_C if name == "SEA" else getattr(theme, name)


def env_style(key: str) -> Tuple[Optional[QColor], Optional[QColor], float]:
    """An Environment polygon layer's pale fill: its two theme tokens mixed, toward the card colour;
    designations and access land are see-through (alpha) so what lies under them still reads."""
    a, b, t, alpha = env.ENV_BY_KEY[key].style
    c = _mix(_mix(_token(a), _token(b), t).name(), theme.CARD, 0.55)
    c.setAlpha(alpha)
    return c, None, 0.3


def grid_ramp(key: str) -> List[QColor]:
    """The colour stops of a value grid (palest to darkest), theme tokens softened toward the card."""
    return [_mix(_token(n), theme.CARD, 0.3 if i else 0.0) for i, n in
            enumerate(env.ENV_BY_KEY[key].style)]


def default_colour(tkey: str) -> QColor:
    """A toggle's default colour: its first layer's fill (or line)."""
    first = next(f for t in TOGGLES if t.key == tkey for f in t.files)
    fill, line, _w = default_style(first)
    return fill or line


def style(key: str) -> Tuple[Optional[QColor], Optional[QColor], float]:
    """default_style(key), with the remembered colour of its toggle in place of the fill (water
    areas, woodland, towns ...) or the line (rivers, roads, rail, national parks, place names)."""
    fill, line, w = default_style(key)
    tk = toggle_key(key)
    c = saved_colour(tk) if tk else None
    if c is None:
        return fill, line, w
    if fill is not None and fill.alpha() < 255:     # keep a see-through layer see-through
        c.setAlpha(fill.alpha())
    return (c, None, w) if fill is not None else (None, c, w)
