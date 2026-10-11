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
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPolygonF

Point = Tuple[float, float]
CELL = 250.0                 # metres per pixel of the land raster
GB_E, GB_N = 700000.0, 1300000.0


def split_edges(rings: List[List[Point]], cell: float = CELL,
                lines: Optional[List[List[Point]]] = None):
    """(coast, inland): runs of consecutive ring edges with sea on one side, and the rest
    (OSGB metres). An edge whose two sides, 2.4 cells out from its middle, are both land is
    an inland border. Used for the land's coast (inland: the modern districts of
    gb_outline.json, or the VC borders again) and for the VC boundary lines (R4).

    lines: the polylines to split, if not the rings' own edges (R5: the rings' edges each
    once, vc_topology.unique_chains, so a border two rings share is not split out twice);
    the land is always the rings."""
    w, h = int(GB_E / cell) + 2, int(GB_N / cell) + 2
    img = QImage(w, h, QImage.Format.Format_Grayscale8)
    img.fill(0)
    p = QPainter(img)
    p.setPen(QPen(QColor(255, 255, 255), 1.5 * cell))    # closes slivers between polygons
    p.setBrush(QColor(255, 255, 255))
    p.scale(1 / cell, -1 / cell)
    p.translate(0, -GB_N)
    for r in rings:
        p.drawPolygon(QPolygonF([QPointF(e, n) for e, n in r]))
    p.end()
    bits, bpl = bytes(img.constBits()), img.bytesPerLine()

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


_SPLIT_CACHE: Dict[tuple, tuple] = {}


def split_edges_cached(key, rings: List[List[Point]], lines=None):
    """split_edges, kept per key (the source file and its simplification) for the process:
    the Mapping tab and the batch renderer share one result. lines: a callable giving the
    polylines to split (split_edges' `lines`), called only when the key is new."""
    if key not in _SPLIT_CACHE:
        _SPLIT_CACHE[key] = split_edges(rings, lines=lines() if lines else None)
    return _SPLIT_CACHE[key]


def coast_chains(rings: List[List[Point]], cell: float = CELL) -> List[List[Point]]:
    """The sea-facing runs only (split_edges' first part)."""
    return split_edges(rings, cell)[0]
