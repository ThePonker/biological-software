"""Background warm-up of the Mapping tab's map (18 Oct 2026): the work the first view of an area
waits for (vice-county topology: snap_rings, unique_chains, the coast/boundary split; the GB-level
layer files and paths) is done after the map is shown, so the first paint is not held up.

Steps alternate between the GUI thread (anything Qt: the land raster, the QPainterPath builds,
one step per tick of the event loop) and ONE worker thread that only runs pure-Python geometry
and file reads, never Qt painting. Results go into the same caches the paint reads
(vc_topology, coast, layers), each behind a lock: a paint that comes before the warm-up has
finished waits for the step in progress or does the work itself; it never gets half a result.
Display only.
"""
from __future__ import annotations

import threading
from typing import Callable, List, Tuple

from PySide6.QtCore import QObject, QTimer

from shared.maps import coast, layers, place_names, relief
from shared.maps.vc_map import _SIMPLIFY_TOL
from shared.maps.vc_topology import unique_chains

Step = Tuple[str, Callable[[], None]]       # ("gui" | "thread", function)
POLL_MS = 10


class WarmUp(QObject):
    """Runs `steps` one after the other; `done` is True when all have run (or failed: a step
    that raises is skipped, the paint then does that work itself)."""

    def __init__(self, steps: List[Step], parent=None):
        super().__init__(parent)
        self._steps = list(steps)
        self._thread = None
        self.done = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._advance)

    def start(self):
        self._timer.start(0)

    @staticmethod
    def _guarded(fn):
        try:
            fn()
        except Exception:
            pass

    def _advance(self):
        if self._thread is not None:
            if self._thread.is_alive():
                self._timer.start(POLL_MS)
                return
            self._thread = None
        if not self._steps:
            self.done = True
            return
        kind, fn = self._steps.pop(0)
        if kind == "thread":
            self._thread = threading.Thread(target=self._guarded, args=(fn,), daemon=True)
            self._thread.start()
            self._timer.start(POLL_MS)
        else:
            self._guarded(fn)
            self._timer.start(0)


def warm_steps(m) -> List[Step]:
    """The steps for a GridMap `m` (see the module's notes)."""
    st: dict = {}
    jobs = []                    # (cache key, rings, how to get the lines)
    if m._vc_rings:
        jobs.append((("vc_topo", m._geojson, _SIMPLIFY_TOL, "r5"), "topo"))
    if m._land_source and not m._use_layer_land():
        jobs.append((m._land_source + ("r5",), "land"))
    jobs = [j for j in jobs if not coast.has_split(j[0])]

    def rings_for(which):
        return st["topo"] if which == "topo" else m._land

    def topology():                                         # thread: pure Python
        if m._vc_rings:
            st["topo"] = [r for rs in m._topo().values() for r in rs]
        for key, which in jobs:
            st[key] = unique_chains(rings_for(which))

    def rasters():                                          # GUI: Qt painting
        for key, which in jobs:
            st[("raster", key)] = coast.land_raster(rings_for(which))

    def classify_and_load():                                # thread: pure Python + files
        for key, which in jobs:
            coast.split_edges_cached(key, rings_for(which), lambda k=key: st[k],
                                     raster=st[("raster", key)])
        for key in sorted(_gb_keys(m)):
            layers.load(m._maps_dir, key, "gb")
        if "relief" in _gb_keys(m):
            relief.load(m._maps_dir)
        if "names" in _gb_keys(m):
            place_names.warm(m._maps_dir)

    steps: List[Step] = [("thread", topology), ("gui", rasters), ("thread", classify_and_load)]
    for key in sorted(_gb_keys(m)):                         # GUI: one path per tick
        if layers.kind_of(key) in ("polygon", "line"):
            steps.append(("gui", lambda k=key: m._layer_shape(m.fit(), k, view=m.fit().extent)))
    return steps


def _gb_keys(m) -> set:
    """The layer files the map draws now (land, the ticked layers, districts when on)."""
    return set(m.layers_drawn())
