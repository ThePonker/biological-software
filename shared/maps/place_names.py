"""The Mapping tab's Place names layer (18 Oct 2026): settlement names from OS Open Zoomstack
(data/maps/layers/names_gb.json = the cities, names_county.json = the rest; features
{"pt": [e, n], "n": name, "t": class}; place_classes.py is the table of classes).

Drawn like the vice-county labels (vc_labels.py): in DEVICE pixels at a whole-pixel size, never
scaled by the zoom, as one path (a halo in the land colour stroked, the letters filled). Shown
progressively by how wide the view is (place_classes: cities everywhere, towns from 250 km,
villages from 60 km, hamlets from 20 km, small settlements from 8 km). Placed biggest class
first; a name that would touch one already placed or a vice-county label is left out, and so is
one that would touch a recorded square while the squares are fully solid (opacity 100 %); with
see-through squares (below 100 %, GridMap.set_square_opacity) the names are drawn over them.
Only the points inside the view are looked at (a numpy index per file, made once), and each name is drawn
into a small image once (halo and letters; kept per size and colour) which is then just
blitted, as stroking the outlines of a hundred names took 60 ms on every redraw. Display only.
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np
from math import ceil, floor

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFontMetricsF, QImage, QPainter, QPen

from shared.maps import layers, place_classes
from shared.maps.species_dist_map import _LAND_C
from shared.maps.vc_labels import label_font, label_path

PAD = 2.0                   # px kept clear round every name (x the dpi scale)
HALO_W = 2.2                # the halo's width in screen pixels
_CELL = 64                  # the collision grid's cell, device pixels
_INDEX: Dict[int, tuple] = {}
_GLYPHS: Dict[tuple, tuple] = {}     # (name, size, bold, colours, scales) -> (image, dx, dy)
MAX_GLYPHS = 3000


class _Index:
    """The points of one loaded layer file as arrays: easting, northing, class rank."""

    def __init__(self, feats):
        self.feats = feats
        self.e = np.array([f["pt"][0] for f in feats], dtype=np.float64)
        self.n = np.array([f["pt"][1] for f in feats], dtype=np.float64)
        self.rank = np.array([place_classes.rank_of(f.get("t")) for f in feats], dtype=np.int8)

    def query(self, box, ranks):
        """Indices (placing order: class, then file order) of the points in `box` of these classes."""
        e0, n0, e1, n1 = box
        hit = (self.e >= e0) & (self.e <= e1) & (self.n >= n0) & (self.n <= n1)
        out = []
        for r in ranks:
            out += np.nonzero(hit & (self.rank == r))[0].tolist()
        return out


def _index(feats) -> _Index:
    hit = _INDEX.get(id(feats))
    if hit is None or hit[0] is not feats:      # keeps the list alive, so its id cannot be reused
        hit = (feats, _Index(feats))
        _INDEX[id(feats)] = hit
    return hit[1]


def feature_lists(maps_dir, lod: str) -> List[list]:
    """The loaded layer files to draw from: the cities file, plus the county one when zoomed in
    (loaded once each; if only one file exists it is returned once)."""
    first = layers.load(maps_dir, "names", "gb")
    if lod != "county":
        return [first]
    second = layers.load(maps_dir, "names", "county")
    return [first] if second is first else [first, second]


def _glyph(name, font, ink: QColor, halo: QColor, u: float, dpr: float):
    """(image, dx, dy): the name with its halo drawn once, centred on (0, 0); blit it at the
    label's whole-pixel centre + (dx, dy)."""
    key = (name, font.pixelSize(), font.bold(), ink.rgba(), halo.rgba(), u, dpr)
    hit = _GLYPHS.get(key)
    if hit is None:
        path = label_path(name, font, QPointF(0.0, 0.0))
        pen = QPen(halo, HALO_W * u)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        br = path.boundingRect().adjusted(-HALO_W * u - 1, -HALO_W * u - 1, HALO_W * u + 1, HALO_W * u + 1)
        dx, dy = floor(br.left()), floor(br.top())
        w, h = ceil(br.right()) - dx, ceil(br.bottom()) - dy
        img = QImage(round(w * dpr), round(h * dpr), QImage.Format.Format_ARGB32_Premultiplied)
        img.setDevicePixelRatio(dpr)
        img.fill(0)
        q = QPainter(img)
        q.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        q.translate(-dx, -dy)
        q.strokePath(path, pen)
        q.fillPath(path, ink)
        q.end()
        if len(_GLYPHS) >= MAX_GLYPHS:
            _GLYPHS.pop(next(iter(_GLYPHS)))
        hit = _GLYPHS[key] = (img, dx, dy)
    return hit


def warm(maps_dir):
    """Load both files and make their indexes (the map's warm-up; no Qt painting)."""
    for feats in feature_lists(maps_dir, "county"):
        _index(feats)


def _view_box(p: QPainter, fit, tr, clip):
    """The OSGB box (e0, n0, e1, n1) of the painter's device (inside the clip, if any)."""
    inv, _ok = tr.inverted()
    win = QRectF(p.window())
    if clip is not None:
        win = win.intersected(clip)
    a, b = inv.map(win.topLeft()), inv.map(win.bottomRight())
    (e0, n1), (e1, n0) = fit.to_en(a.x(), a.y()), fit.to_en(b.x(), b.y())
    return min(e0, e1), min(n0, n1), max(e0, e1), max(n0, n1)


def draw_place_names(p: QPainter, fit, feature_lists_, span_m: float, ink, taken=(),
                     occupied=None) -> list:
    """Draw the names through `fit`. span_m: the width in metres of what is shown (picks the
    classes). ink: the letters' colour. taken: device rects already used (the VC labels).
    occupied(QRectF) -> bool: does this device rect cover a recorded square (left out if so;
    GridMap passes None when the squares are see-through, so the names are drawn over them).
    Returns [(name, device QRectF)] of those drawn."""
    ranks = place_classes.shown_at(span_m)
    dev = p.device()
    u = (float(dev.logicalDpiY()) if dev is not None else 96.0) / 96.0
    tr = p.transform()
    clip = tr.mapRect(p.clipBoundingRect()) if p.hasClipping() else None
    box = _view_box(p, fit, tr, clip)
    win = QRectF(p.window())
    fonts = {}
    grid: Dict[tuple, list] = {}

    def cells(r):
        for cx in range(int(r.left() // _CELL), int(r.right() // _CELL) + 1):
            for cy in range(int(r.top() // _CELL), int(r.bottom() // _CELL) + 1):
                yield cx, cy

    def free(r) -> bool:
        return not any(r.intersects(o) for c in cells(r) for o in grid.get(c, ()))

    def take(r):
        for c in cells(r):
            grid.setdefault(c, []).append(r)
    for r in taken:
        take(r)
    pad = PAD * u
    halo = QColor(_LAND_C)
    halo.setAlpha(225)
    ink = QColor(ink)
    dpr = float(dev.devicePixelRatioF()) if dev is not None else 1.0
    placed = []
    p.save()
    p.resetTransform()
    for feats in feature_lists_:
        idx = _index(feats)
        for i in idx.query(box, ranks):
            f = feats[i]
            cls = place_classes.PLACE_CLASSES[idx.rank[i]]
            if cls.key not in fonts:
                font = label_font(cls.pt, cls.bold, dev)
                fonts[cls.key] = (font, QFontMetricsF(font))
            font, fm = fonts[cls.key]
            name = f["n"]
            x, y = fit.to_px(*f["pt"])
            home = tr.map(QPointF(x, y))
            w, h = fm.horizontalAdvance(name), fm.height()
            rect = QRectF(home.x() - w / 2, home.y() - h / 2, w, h)
            grown = rect.adjusted(-pad, -pad, pad, pad)
            if (clip is not None and not clip.contains(rect)) or not win.intersects(rect) \
                    or not free(grown) or (occupied is not None and occupied(rect)):
                continue
            take(grown)
            placed.append((name, rect))
            img, dx, dy = _glyph(name, font, ink, halo, u, dpr)
            p.drawImage(QPointF(round(home.x()) + dx, round(home.y()) + dy), img)
    p.restore()
    return placed


_COMPASS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")


def nearest(feature_lists_, e: float, n: float, span_m: float, radius: float = 2000.0):
    """The place name nearest the point (e, n) within `radius` metres, among the classes drawn
    when the view is `span_m` across: (name, distance in metres, compass point of the name as
    seen from the point), or None. Uses the loaded files' indexes (no new reading); Identify."""
    ranks = place_classes.shown_at(span_m)
    best = None
    for feats in feature_lists_:
        idx = _index(feats)
        for i in idx.query((e - radius, n - radius, e + radius, n + radius), ranks):
            dx, dy = idx.e[i] - e, idx.n[i] - n
            d = float(np.hypot(dx, dy))
            if d <= radius and (best is None or d < best[1]):
                best = (feats[i]["n"], d, _COMPASS[int(((np.degrees(np.arctan2(dx, dy)) + 22.5) % 360) // 45)])
    return best
