"""The coast line for the Mapping tab's map: the edges of the land rings that face the sea.

R4 (11 Oct 2026). With no data/maps/gb_outline.json the land is drawn from the vice-county
polygons themselves, and the map used to stroke every one of their rings as "coast", so each
VC border came out a second time, finer and darker than the VC layer: the thin lines Wil saw
under the VCs. And Wil's PC has gb_outline.json: the 2013 ONS local-authority districts
(380 of them, via martinjc/UK-GeoJSON), so there the "coast" stroke drew every district
border. split_edges() parts each ring's edges into those with sea on one side (the coast)
and the inland ones (district borders, or the VC borders again), tested against a raster of
the land at 250 m a pixel. Worked out once per source, the first time it is needed.

Display only.
"""
from __future__ import annotations

import math
import threading
from itertools import chain
from typing import Dict, List, Optional, Tuple

import numpy as np
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPolygonF

from shared.maps import layer_bin, map_disk_cache

Point = Tuple[float, float]
CELL = 250.0                 # metres per pixel of the land raster
GB_E, GB_N = 700000.0, 1300000.0


def land_raster(rings: List[List[Point]], cell: float = CELL):
    """The land as a raster at `cell` metres a pixel: (bytes, bytes per line, width, height).
    The one step of split_edges that uses Qt painting (the map's warm-up runs it on the GUI
    thread and hands the result to the geometry in classify)."""
    w, h = int(GB_E / cell) + 2, int(GB_N / cell) + 2
    img = QImage(w, h, QImage.Format.Format_Grayscale8)
    img.fill(0)
    p = QPainter(img)
    p.setPen(QPen(QColor(255, 255, 255), 1.5 * cell))    # closes slivers between polygons
    p.setBrush(QColor(255, 255, 255))
    p.scale(1 / cell, -1 / cell)
    p.translate(0, -GB_N)
    # R17: the points go to numpy once (not a QPointF each) and each ring is one path built from
    # that array (layer_bin); drawn as drawPolygon did (odd-even fill, same pen), so every pixel is
    # the same (the unread line padding aside). A ring of under two points, which has no path, is drawn the old way.
    rings = list(rings)
    lens = np.fromiter((len(r) for r in rings), dtype=np.int64, count=len(rings))
    src = np.fromiter(chain.from_iterable(chain.from_iterable(rings)), dtype=np.float64,
                      count=2 * int(lens.sum())).reshape(-1, 2)
    ends = np.cumsum(lens)
    for r, a, b in zip(rings, ends - lens, ends):
        if b - a < 2:
            p.drawPolygon(QPolygonF([QPointF(e, n) for e, n in r]))
        else:
            p.drawPath(layer_bin.polyline_path(src, np.array([a]), np.array([b]), True, False))
    p.end()
    return bytes(img.constBits()), img.bytesPerLine(), w, h


def classify(raster, rings: List[List[Point]], cell: float = CELL,
             lines: Optional[List[List[Point]]] = None):
    """split_edges' second step, pure Python (safe off the GUI thread): (coast, inland) from
    the land raster."""
    bits, bpl, w, h = raster

    def land(e: float, n: float) -> bool:
        x, y = int(e / cell), int((GB_N - n) / cell)
        return 0 <= x < w and 0 <= y < h and bits[y * bpl + x] > 127

    d = 2.4 * cell
    out: Tuple[List[List[Point]], List[List[Point]]] = ([], [])
    for r in (rings if lines is None else lines):
        chain: List[Point] = []
        kind = None                         # 0 coast, 1 inland: the run being built
        for i in range(len(r) - 1):
            (e1, n1), (e2, n2) = r[i], r[i + 1]
            de, dn = e2 - e1, n2 - n1
            length = math.hypot(de, dn) or 1.0
            me, mn = (e1 + e2) / 2, (n1 + n2) / 2
            oe, on = -dn / length * d, de / length * d
            k = 1 if (land(me + oe, mn + on) and land(me - oe, mn - on)) else 0
            if k != kind:
                if chain:
                    out[kind].append(chain)
                chain, kind = [r[i]], k
            chain.append(r[i + 1])
        if chain:
            out[kind].append(chain)
    return out


def split_edges(rings: List[List[Point]], cell: float = CELL,
                lines: Optional[List[List[Point]]] = None):
    """(coast, inland): runs of consecutive ring edges with sea on one side, and the rest
    (OSGB metres). An edge whose two sides, 2.4 cells out from its middle, are both land is
    an inland border. Used for the land's coast (inland: the modern districts of
    gb_outline.json, or the VC borders again) and for the VC boundary lines (R4).

    lines: the polylines to split, if not the rings' own edges (R5: the rings' edges each
    once, vc_topology.unique_chains, so a border two rings share is not split out twice);
    the land is always the rings."""
    return classify(land_raster(rings, cell), rings, cell, lines)


_SPLIT_CACHE: Dict[tuple, tuple] = {}
_LOCK = threading.RLock()


def has_split(key) -> bool:
    return key in _SPLIT_CACHE


def load_disk(key, disk) -> bool:
    """Take the split for `key` from the disk cache (map_disk_cache, R16) when there is a matching
    file; True when it is now in the process cache. disk: (source file, name)."""
    with _LOCK:
        if key in _SPLIT_CACHE:
            return True
        if not disk:
            return False
        a = map_disk_cache.load(disk[0], "split_" + disk[1], CELL, *key[2:])
        try:
            if a is not None:
                _SPLIT_CACHE[key] = map_disk_cache.unpack_split(a)
                return True
        except Exception:
            pass
        return False


def split_edges_cached(key, rings: List[List[Point]], lines=None, raster=None, disk=None):
    """split_edges, kept per key (the source file and its simplification) for the process:
    the Mapping tab and the batch renderer share one result. lines: a callable giving the
    polylines to split (split_edges' `lines`), called only when the key is new. raster: the
    land_raster already made. A lock makes a paint that needs it while the map's warm-up is
    still working it out wait for that result, not work it out twice. disk: (source file, name):
    the result is also kept in data/maps/cache/ and read from there next run (load_disk)."""
    with _LOCK:
        if key not in _SPLIT_CACHE and not load_disk(key, disk):
            ln = lines() if lines else None
            _SPLIT_CACHE[key] = (split_edges(rings, lines=ln) if raster is None
                                 else classify(raster, rings, CELL, ln))
            if disk:
                map_disk_cache.save(disk[0], "split_" + disk[1],
                                    map_disk_cache.pack_split(*_SPLIT_CACHE[key]), CELL, *key[2:])
        return _SPLIT_CACHE[key]


def coast_chains(rings: List[List[Point]], cell: float = CELL) -> List[List[Point]]:
    """The sea-facing runs only (split_edges' first part)."""
    return split_edges(rings, cell)[0]
