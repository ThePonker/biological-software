"""Look-ahead for the Mapping tab's county view (R16, 10 Nov 2026).

County-detail layers are built per 25 km area round the view (map_layers._layer_shape). Panning into
an area not built yet cost its numpy work (box test, point gathering, the serialised path) plus
the QPainterPath in the paint that needs it. After a paint in county view (a re-render or a pan blit) the map now works out
where the pan is heading (the view's centre against its last request's) and has ONE worker thread do
the numpy half for the ticked layers' areas there: layer_parts() gives each path as bytes (Qt's own
serialised form, layer_bin.polyline_bytes). The next paint that needs one only makes the
QPainterPath from the bytes (layer_bin.path_from_bytes), on the GUI thread.

- The worker makes no Qt object (no QPainterPath), so nothing Qt happens off the GUI thread, and
  the cyclic collector is off while it runs (gc_pause).
- It reads the layer data the paint already loaded (handed over on the GUI thread; it never reads
  a file) and writes only to its own store, behind a lock. A newer request replaces an older one
  that has not finished.
- Limits: only areas the GUI cache does not hold; the store is cut down to the areas now wanted at
  each request and held to MAX_BYTES; the GUI's own limit (a few areas per layer, _layer_shape)
  still applies when a prepared area is taken into the cache.
Display only.
"""
from __future__ import annotations

import os
import threading
from typing import Dict, List, Optional, Tuple

from shared import gc_pause
from shared.maps import env_classes, layer_bin, layer_opacity, layers
from shared.maps.map_timing import timed
from shared.maps.vc_topology import unique_chains

ENABLED = False                 # off by default (no measurable gain on Wil's files); BIOSOFT_MAP_AHEAD=1 turns it on
MAX_BYTES = 64_000_000          # prepared path bytes held at once (20 bytes a point)
STEPS = (0.5, 1.0)              # how far on, in views, the pan is expected to go
MIN_MOVE = 0.02                 # of a view: less than this is a zoom, not a pan
Parts = Dict[Optional[str], layer_bin.PathBytes]


# ---------------------------------------------------------------- the numpy half of a layer's paths

def bytes_bin(key: str, data, idx) -> layer_bin.PathBytes:
    """The path bytes of features `idx` of a binary layer (see map_layers._build_path_bin)."""
    if key == "districts":
        return layer_bin.lists_bytes(unique_chains(data.rings_of(idx)), False, False)
    return data.path_bytes(idx, closed=layers.kind_of(key) != "line")


def bytes_feats(key: str, feats) -> layer_bin.PathBytes:
    """The path bytes of feature dicts (see map_layers._build_path)."""
    if key == "districts":      # each shared edge once (the dashes would double up)
        return layer_bin.lists_bytes(unique_chains([r for f in feats for r in f.get("rings", ())]),
                                     False, False)
    if layers.kind_of(key) == "line":
        return layer_bin.lists_bytes([f["line"] for f in feats if f.get("line")], False, False)
    # WindingFill: build_map_layers.py writes outer rings one way round and holes the other
    return layer_bin.lists_bytes([r for f in feats for r in f.get("rings", ())], True)


def layer_parts(key: str, data, box, classed: bool) -> Tuple[Parts, List[str]]:
    """({class or None: path bytes}, the classes in the order first met) of a layer in `box`.
    Not classed: one whole-layer path under None. Classed (an Environment layer drawn one colour
    per class): one path per class "t". Pure numpy / Python, no Qt object."""
    if isinstance(data, layer_bin.LayerBin):
        idx = data.in_box(box)
        if not classed:
            return {None: bytes_bin(key, data, idx)}, []
        groups: Dict[str, list] = {}
        for pos, name in enumerate(data.classes(idx).tolist()):
            groups.setdefault(name, []).append(pos)
        return {c: bytes_bin(key, data, idx[pos]) for c, pos in groups.items()}, list(groups)
    feats = layers.features_in(data, box)
    if not classed:
        return {None: bytes_feats(key, feats)}, []
    by_class: Dict[str, list] = {}
    for f in feats:
        by_class.setdefault(str(f.get("t") or ""), []).append(f)
    return {c: bytes_feats(key, g) for c, g in by_class.items()}, list(by_class)


def enabled() -> bool:
    return bool(ENABLED) or os.environ.get("BIOSOFT_MAP_AHEAD") == "1"


def is_classed(key: str) -> bool:
    """Drawn one colour per class (map_layers._draw_env_polygon)."""
    return layer_opacity.has_opacity(key) and env_classes.is_classed(key)


def next_views(prev, cur, steps=STEPS) -> list:
    """Where the view is heading: `cur` moved on in the direction its centre moved since `prev`
    (an axis that hardly moved is left alone), `steps` views on; [] when it was a zoom."""
    cw, ch = cur[2] - cur[0], cur[3] - cur[1]
    dx = (cur[0] + cur[2] - prev[0] - prev[2]) / 2
    dy = (cur[1] + cur[3] - prev[1] - prev[3]) / 2
    big = max(abs(dx), abs(dy))
    if big < MIN_MOVE * max(cw, ch):
        return []
    sx = (dx > 0) - (dx < 0) if abs(dx) >= 0.25 * big else 0
    sy = (dy > 0) - (dy < 0) if abs(dy) >= 0.25 * big else 0
    return [(cur[0] + sx * k * cw, cur[1] + sy * k * ch, cur[2] + sx * k * cw, cur[3] + sy * k * ch)
            for k in steps]


# ---------------------------------------------------------------- the worker, for GridMap

class LookAheadMixin:
    """For GridMap: uses its fit-independent _layer_ck(), _layer_cache, _class_index, layers_drawn()
    and _maps_dir (map_layers.py), and visible_extent()."""

    def _init_ahead(self):
        self._ahead_lock = threading.Lock()
        self._ahead_store: Dict[tuple, tuple] = {}   # (layer, lod, box, classed) -> (parts, classes, bytes)
        self._ahead_pending: Optional[list] = None   # the newest request, not started
        self._ahead_thread: Optional[threading.Thread] = None
        self._ahead_prev = None                      # the view at the last paint
        self.ahead_built = 0                         # areas prepared (tests)
        self.ahead_used = 0                          # ... and taken by a paint (tests)

    def _look_ahead(self, fit):
        """Called after a paint: ask for the areas the pan is heading into (county view only).
        The direction is the move of the view's centre since the last request; moves under
        MIN_MOVE of a view add up until they count, and a change of zoom starts again."""
        if not enabled():                  # off: no thread, no GC pause, nothing kept
            return
        view = self.visible_extent()
        prev = self._ahead_prev
        if layers.lod_for_extent(view) != "county":
            self._ahead_prev = None
            return
        if prev is None:
            self._ahead_prev = view
            return
        w = view[2] - view[0]
        if abs(w - (prev[2] - prev[0])) > 0.01 * w:      # zoomed: a new starting point
            self._ahead_prev = view
            return
        views = next_views(prev, view)
        if not views:
            return
        self._ahead_prev = view
        tasks, wanted = [], set()
        for key in self.layers_drawn():
            if key != "districts" and layers.kind_of(key) not in ("polygon", "line"):
                continue
            classed = is_classed(key)
            for v in views:
                lod, box = self._layer_ck(fit, key, v)
                ck = (key, lod, box, classed)
                if lod != "county" or ck in wanted:
                    continue
                wanted.add(ck)
                built = ((key, lod, box) in self._class_index if classed
                         else (key, lod, box, None) in self._layer_cache)
                if not built:
                    tasks.append((ck, layers.load(self._maps_dir, key, lod)))
        with self._ahead_lock:
            for ck in [c for c in self._ahead_store if c not in wanted]:
                del self._ahead_store[ck]
            self._ahead_pending = [t for t in tasks if t[0] not in self._ahead_store and len(t[1])]
            if self._ahead_pending and self._ahead_thread is None:
                self._ahead_thread = threading.Thread(target=self._ahead_run, daemon=True,
                                                      name="map-look-ahead")
                self._ahead_thread.start()

    def _ahead_run(self):
        gc_pause.acquire()
        try:
            while True:
                with self._ahead_lock:
                    job, self._ahead_pending = self._ahead_pending, None
                    if not job:
                        self._ahead_thread = None
                        return
                for ck, data in job:
                    with self._ahead_lock:
                        if self._ahead_pending is not None:     # a newer request: start on that
                            break
                        used = sum(v[2] for v in self._ahead_store.values())
                    if used >= MAX_BYTES:
                        break
                    try:
                        key, lod, box, classed = ck
                        with timed("ahead", f"{key} {lod}"):
                            parts, order = layer_parts(key, data, box, classed)
                        size = sum(len(b) for b, _w in parts.values() if b)
                    except Exception:
                        continue
                    with self._ahead_lock:
                        self._ahead_store[ck] = (parts, order, size)
                        self.ahead_built += 1
        except BaseException:
            with self._ahead_lock:
                self._ahead_thread = None
            raise
        finally:
            gc_pause.release()

    def _ahead_take(self, key: str, lod: str, box, classed: bool):
        """(parts, classes) prepared for this area, handed over once; None when not prepared."""
        with self._ahead_lock:
            hit = self._ahead_store.pop((key, lod, box, classed), None)
            if hit is not None:
                self.ahead_used += 1
        return None if hit is None else (hit[0], hit[1])
