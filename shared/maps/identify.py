"""The Mapping tab's Identify tool, the map's half (25 Oct 2026): what lies under a point.

IdentifyMixin gives GridMap an Identify mode (a left click, not a drag, emits
identify_requested(e, n, global_pos) instead of selecting a square) and identify_at(e, n),
which lists what the TICKED layers hold at a point: the polygon layers (woodland, towns, water
areas, parks and green space, foreshore, national parks, and the Environment ones: designated
sites, ancient woodland, geology ...) whose built geometry covers it, with the feature's name "n"
and class "t" if it carries them ("SSSI: Ashen Bank"); the value grids (HadUK-Grid) give their
value and units ("Mean annual rainfall: 680 mm"), and for the Place names layer the nearest name
within 2 km. Line layers and the relief are skipped. It uses the layer files the map has
already loaded (layers.load is cached); nothing is read from disk that drawing did not read.
No Observatum imports: the Mapping tab builds the pop-up (views/mapping/identify_popup.py).
Display only.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from PySide6.QtCore import Qt

from shared.maps import grid_squares as gs
from shared.maps import layers, place_names, value_grid
from shared.maps.vc_labels import point_in_ring

MAX_ITEMS = 3               # features listed per layer by identify_details
PLACE_RADIUS_M = 2000.0     # the nearest place name is looked for this far round the point


def feature_covers(f: dict, e: float, n: float) -> bool:
    """Is (e, n) inside the polygon feature: in its outer ring and in none of its holes."""
    b = f.get("bbox")
    if b is not None and not (b[0] <= e <= b[2] and b[1] <= n <= b[3]):
        return False
    rings = f.get("rings") or ()
    if not rings or not point_in_ring(e, n, rings[0]):
        return False
    return not any(point_in_ring(e, n, h) for h in rings[1:])


def feature_text(hits, label: str) -> str:
    """What the features under a point say: each one's name "n" (or "name") and class "t", as
    "Ashen Bank", "Foo Wood (ASNW)" or just the class; a class equal to the layer's label (the
    designations carry their type) is not repeated; repeats are dropped; joined with ", "."""
    seen: List[str] = []
    for f in hits:
        nm = str(f.get("n") or f.get("name") or "").strip()
        cl = str(f.get("t") or "").strip()
        if cl.lower() == label.lower():
            cl = ""
        text = f"{nm} ({cl})" if nm and cl else nm or cl
        if text and text not in seen:
            seen.append(text)
    return ", ".join(seen)


class _NoGrid:
    @staticmethod
    def identify(_e, _n):
        return None


def _distance_text(d: float) -> str:
    return f"{d / 1000:.1f} km"


class IdentifyMixin:
    """Uses GridMap's _layers_on, _layer_files, _maps_dir, _size, _zoom, _pan, fit(), _epos()."""

    def _init_identify(self):
        self._identify = False

    def set_identify_mode(self, on: bool):
        """Identify on: a click reports the point (identify_requested) instead of selecting a
        square, and the cursor says so. Off: clicks behave as before."""
        self._identify = bool(on)
        self._apply_cursor()

    def identify_mode(self) -> bool:
        return self._identify

    def _apply_cursor(self):
        if self._identify:
            self.setCursor(Qt.CursorShape.WhatsThisCursor)
        elif getattr(self, "_zoomable", False):
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.unsetCursor()

    def en_at(self, pos) -> Tuple[float, float]:
        """OSGB (e, n) of a widget position, through the pan and zoom."""
        ux, uy = gs.unpan(pos.x(), pos.y(), self._pan.x(), self._pan.y(), self._zoom)
        return self.fit().to_en(ux, uy)

    def square_label_at(self, e: float, n: float) -> Optional[str]:
        """The label of the square (at the current square size) holding the point."""
        return gs.square_for_point(e, n, self._size)

    def _ticked_layers(self, lod: str):
        """[(layer, short name)] of the ticked, installed layers in the registry's order: the
        rules identify_at and identify_details share."""
        out = []
        for lay in layers.LAYERS:
            if lay.toggle is None or lay.toggle not in self._layers_on \
                    or lay.key not in self._layer_files:
                continue
            tg = next((t for t in layers.TOGGLES if t.key == lay.toggle), None)
            if tg is not None and not layers.toggle_visible(tg):
                continue                # Soilscapes while its setting is off
            label = tg.label if tg else lay.key
            out.append((lay, (tg.short or label) if tg else label))
        return out

    def _nearest_place(self, e: float, n: float, lod: str):
        fit = self.fit()
        span = max(fit.w, fit.h) / fit.scale / max(self._zoom, 1.0)   # as draw()
        lists = place_names.feature_lists(self._maps_dir, lod)
        near = place_names.nearest(lists, e, n, span, PLACE_RADIUS_M)
        if not near:
            return None
        name, d, compass = near
        return f"{name}, " + (f"{_distance_text(d)} {compass}" if d >= 50 else "here")

    def identify_at(self, e: float, n: float) -> List[Tuple[str, str]]:
        """[(layer label, feature name / class / value text)] for the ticked polygon and grid layers that cover
        the point, in the registry's order; then ("Place", "Name, 0.6 km NE") if the Place names
        layer is ticked and a name lies within 2 km. Names shown are the classes drawn now."""
        view = getattr(self, "_layer_view", None) or self.visible_extent()
        lod = layers.lod_for_extent(view)
        out: List[Tuple[str, str]] = []
        for lay, short in self._ticked_layers(lod):
            if lay.kind == "polygon":
                hits = [f for f in layers.candidates(layers.load(self._maps_dir, lay.key, lod), e, n)
                        if feature_covers(f, e, n)]
                if hits:
                    out.append((short, feature_text(hits, short)))
            elif lay.kind == "grid":
                one = (value_grid.load(self._maps_dir, lay.key) or _NoGrid).identify(e, n)
                if one:
                    out.append(one)
            elif lay.kind == "point":
                near = self._nearest_place(e, n, lod)
                if near:
                    out.append(("Place", near))
        return out

    def identify_details(self, e: float, n: float) -> List[dict]:
        """identify_at with more: [{"label": short, "items": [{"text", "details", "link"}, ...]}]
        for the same layers in the same order. A polygon layer gives one item per feature under
        the point (at most 3): "text" as feature_text says it, "details" the feature's "a"
        [(label, text), ...] and "link" its "u" (a web page) or None. A grid or the nearest
        place gives one item with just the text."""
        view = getattr(self, "_layer_view", None) or self.visible_extent()
        lod = layers.lod_for_extent(view)
        out: List[dict] = []
        for lay, short in self._ticked_layers(lod):
            items: List[dict] = []
            label = short
            if lay.kind == "polygon":
                for f in (f for f in layers.candidates(layers.load(self._maps_dir, lay.key, lod), e, n)
                          if feature_covers(f, e, n)):
                    item = {"text": feature_text([f], short),
                            "details": [(str(x[0]), str(x[1])) for x in (f.get("a") or ())
                                        if isinstance(x, (list, tuple)) and len(x) >= 2],
                            "link": str(f["u"]) if f.get("u") else None}
                    if item not in items:
                        items.append(item)
                    if len(items) == MAX_ITEMS:
                        break
            elif lay.kind == "grid":
                one = (value_grid.load(self._maps_dir, lay.key) or _NoGrid).identify(e, n)
                if one:
                    label = one[0]
                    items.append({"text": one[1], "details": [], "link": None})
            elif lay.kind == "point":
                near = self._nearest_place(e, n, lod)
                if near:
                    label = "Place"
                    items.append({"text": near, "details": [], "link": None})
            if items:
                out.append({"label": label, "items": items})
        return out
