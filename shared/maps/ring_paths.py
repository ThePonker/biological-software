"""Rings of (easting, northing) points as ONE QPainterPath, projected to pixels with numpy
(Round 16, A4): the mini-maps used to make a QPointF per point and a QPolygonF per ring.
Built with layer_bin.polyline_path (the same QDataStream route the Mapping tab's layers use)."""
from __future__ import annotations

from itertools import chain
from typing import Callable, Iterable

import numpy as np
from PySide6.QtGui import QPainterPath

from shared.maps import layer_bin


def rings_path(rings: Iterable, to_px: Callable, closed: bool = True,
               winding: bool = True) -> QPainterPath:
    """One path holding every ring. `to_px(e, n)` takes numpy arrays of eastings and northings and
    returns (x, y) arrays. closed=True: each ring is a closed subpath (drawPolygon's shape, for
    filling); closed=False: open polylines (drawPolyline's). Rings of under two points are left out.
    winding=True (non-zero) keeps a ring lying inside another one filled, as the old one-polygon-a-ring
    drawing did when the rings run the same way; odd-even would punch it out as a hole."""
    lines = [r for r in rings]
    lens = np.fromiter((len(r) for r in lines), dtype=np.int64, count=len(lines))
    flat = list(chain.from_iterable(lines))
    if not flat:
        return layer_bin.polyline_path(np.empty((0, 2)), lens[:0], lens[:0], closed, winding)
    src = np.array(flat, dtype=np.float64).reshape(-1, 2)
    x, y = to_px(src[:, 0], src[:, 1])
    px = np.column_stack((np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)))
    ends = np.cumsum(lens)
    return layer_bin.polyline_path(px, ends - lens, ends, closed, winding)
