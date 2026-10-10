"""Offline VC mini-map for the info panel.

Moved from DataEntry/vc_map.py (backlog H2, 9 Oct 2026); that module is now a shim.

Loads the BRC vice-county boundaries (WGS84 GeoJSON) once, converts to OSGB easting/northing,
simplifies for thumbnail rendering, and paints them with QPainter. Shows the current record's
location as a dot (from the parsed grid ref) and tints the derived VC. No tiles, no internet,
no heavy dependencies -- a location sanity-check, not a precision map.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QPolygonF
from PySide6.QtWidgets import QWidget

from shared.maps._theme import theme
from shared.osgb import wgs84_to_osgb_en

# module cache: path -> (vc_rings, bounds)
_CACHE: Dict[str, Tuple[Dict[int, List[List[Tuple[float, float]]]], Tuple[float, float, float, float]]] = {}

_SIMPLIFY_TOL = 300.0  # metres between kept points (finer, so adjacent VC borders meet cleanly)


def _simplify(ring: List[Tuple[float, float]], tol: float) -> List[Tuple[float, float]]:
    if len(ring) <= 4:
        return ring
    out = [ring[0]]
    lx, ly = ring[0]
    for x, y in ring[1:-1]:
        if (x - lx) * (x - lx) + (y - ly) * (y - ly) >= tol * tol:
            out.append((x, y))
            lx, ly = x, y
    out.append(ring[-1])
    return out


def _prethin(ll: List[Tuple[float, float]], tol: float) -> List[Tuple[float, float]]:
    """Thin a (lat, lon) ring before projecting it: drop points nearer than tol / 2 metres
    to the last kept one (a degree of longitude counted as only 0.5 of a degree of latitude,
    so the distance is never over-estimated in GB)."""
    d = tol * 0.5 / 111320.0
    d2 = d * d
    out = [ll[0]]
    la, lo = ll[0]
    for lat, lon in ll[1:-1]:
        dy, dx = lat - la, (lon - lo) * 0.5
        if dy * dy + dx * dx >= d2:
            out.append((lat, lon))
            la, lo = lat, lon
    out.append(ll[-1])
    return out


def ring_area(ring) -> float:
    """Signed area (shoelace) of a ring of (x, y) points; > 0 anticlockwise."""
    a = 0.0
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return a / 2.0


def _rings_from_geometry(geom) -> List[List[Tuple[float, float]]]:
    """Every ring (as stored) of a Polygon or MultiPolygon geometry, holes included; the
    caller keeps the outer rings (see _outer_rings)."""
    if not geom:
        return []
    t = geom.get("type")
    coords = geom.get("coordinates", [])
    if t == "Polygon":
        return [r for r in coords if r]
    if t == "MultiPolygon":
        return [r for poly in coords if poly for r in poly if r]
    return []


def _outer_rings(geom, rings_en):
    """The outer rings among a feature's projected rings (holes dropped).

    MultiPolygon: the first ring of each polygon. Polygon: scripts/convert_vc_shapefile.py
    (before 10 Oct 2026) wrote EVERY part of a multi-part vice-county -- islands and holes --
    as the rings of ONE Polygon, so taking only the first ring (as this did) dropped the
    mainland of 40 of the 112 VCs (VC1 West Cornwall was drawn as one Scilly islet, a
    triangle after the converter's thinning). So for a Polygon the rings turning the same
    way as the largest ring are outer rings (islands); those turning the other way are holes.
    """
    if not rings_en:
        return []
    if geom.get("type") == "MultiPolygon":
        out, i = [], 0
        for poly in geom.get("coordinates", []):
            if not poly:
                continue
            if rings_en[i] is not None:
                out.append(rings_en[i])
            i += sum(1 for r in poly if r)
        return out
    kept = [(r, ring_area(r)) for r in rings_en if r is not None]
    if not kept:
        return []
    big = max(kept, key=lambda ra: abs(ra[1]))[1]
    return [r for r, a in kept if a * big > 0]


def load_vc_polygons(path: str, tol: float = _SIMPLIFY_TOL):
    """Load + project + simplify VC polygons. Cached per (path, tol).

    tol <= 0 keeps full resolution (a complete, hole-free GB for a solid basemap).
    Returns (vc_rings, (minE,minN,maxE,maxN)).
    """
    key = (path, tol)
    if key in _CACHE:
        return _CACHE[key]
    if not path or not os.path.exists(path):
        result = ({}, (0.0, 0.0, 700000.0, 1300000.0))
        _CACHE[key] = result
        return result

    with open(path, encoding="utf-8") as f:
        gj = json.load(f)

    vc_rings: Dict[int, List[List[Tuple[float, float]]]] = {}
    minE = minN = float("inf")
    maxE = maxN = float("-inf")
    for feat in gj.get("features", []):
        props = feat.get("properties", {})
        vc = props.get("VCNUMBER")
        try:
            vc = int(vc)
        except (TypeError, ValueError):
            continue
        geom = feat.get("geometry") or {}
        all_en: List[Optional[List[Tuple[float, float]]]] = []
        for ring in _rings_from_geometry(geom):
            ll = []
            for pt in ring:
                try:
                    # NB: this BRC GeoJSON stores [lat, lon], not the usual [lon, lat]
                    ll.append((float(pt[0]), float(pt[1])))
                except (TypeError, ValueError, IndexError):
                    continue
            if tol > 0 and len(ll) > 8:
                # thin in degrees first (projecting every point is the slow part); half the
                # tolerance, longitude under-weighted, so nothing _simplify keeps is lost
                kept = _prethin(ll, tol)
                ll = kept if len(kept) >= 4 else ll
            en = [wgs84_to_osgb_en(lat, lon) for lat, lon in ll]
            if len(en) >= 4 and tol > 0:
                thin = _simplify(en, tol)
                # an islet smaller than `tol` keeps a few of its points rather than vanish
                # (a far-off islet sets the extent County view zooms to, e.g. VC103)
                en = thin if len(thin) >= 4 else en[::max(1, len(en) // 6)] + [en[-1]]
            all_en.append(en if len(en) >= 4 else None)
        rings_en = _outer_rings(geom, all_en)
        for en in rings_en:
            for e, n in en:
                if e < minE: minE = e
                if e > maxE: maxE = e
                if n < minN: minN = n
                if n > maxN: maxN = n
        if rings_en:
            vc_rings.setdefault(vc, []).extend(rings_en)

    if minE == float("inf"):
        bounds = (0.0, 0.0, 700000.0, 1300000.0)
    else:
        bounds = (minE, minN, maxE, maxN)
    _CACHE[key] = (vc_rings, bounds)
    return _CACHE[key]


class MiniMap(QWidget):
    """Paints GB VC outlines + a record dot; tints the derived VC. Display only."""

    def __init__(self, geojson_path: Optional[str], vc_service=None, parent=None):
        super().__init__(parent)
        self._path = geojson_path or ""
        self._vc_service = vc_service
        self._vc_rings, self._bounds = load_vc_polygons(self._path)
        self._dot_en: Optional[Tuple[float, float]] = None
        self._active_vc: Optional[int] = None
        self.setFixedSize(150, 190)
        self.setToolTip("Location check (Contains OS/BRC boundary data). Not to scale.")

    def has_data(self) -> bool:
        return bool(self._vc_rings)

    def update_for_row(self, row: Optional[dict]):
        self._dot_en = None
        self._active_vc = None
        if row:
            gr = (row.get("grid_ref") or "").strip()
            if gr and self._vc_service is not None:
                try:
                    parsed = self._vc_service.parse_grid_ref(gr)
                except Exception:
                    parsed = None
                if parsed:
                    self._dot_en = (float(parsed[0]), float(parsed[1]))
            vc = row.get("vc_number")
            try:
                self._active_vc = int(vc) if vc is not None else None
            except (TypeError, ValueError):
                self._active_vc = None
        self.update()

    # -- projection to widget pixels ----------------------------------------
    def _scale(self):
        minE, minN, maxE, maxN = self._bounds
        w = self.width() - 8
        h = self.height() - 8
        span_e = max(1.0, maxE - minE)
        span_n = max(1.0, maxN - minN)
        s = min(w / span_e, h / span_n)          # equal aspect
        ox = 4 + (w - span_e * s) / 2
        oy = 4 + (h - span_n * s) / 2
        return s, ox, oy, minE, minN, span_n

    def _to_px(self, e, n):
        s, ox, oy, minE, minN, span_n = self._scale()
        x = ox + (e - minE) * s
        y = oy + (span_n - (n - minN)) * s        # invert y (north up)
        return QPointF(x, y)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.fillRect(self.rect(), QColor(theme.CARD))
        if not self._vc_rings:
            p.setPen(QColor(theme.MUTED))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "no map")
            p.end()
            return

        base_pen = QPen(QColor(theme.LINE)); base_pen.setWidthF(0.6)
        active_brush = QBrush(QColor(74, 124, 89, 90))   # moss tint for derived VC
        size = (self.width(), self.height())
        if getattr(self, "_poly_cache", (None,))[0] != size:   # every islet now: project once
            self._poly_cache = (size, {vc: [QPolygonF([self._to_px(e, n) for (e, n) in ring])
                                            for ring in rings]
                                       for vc, rings in self._vc_rings.items()})
        for vc, polys in self._poly_cache[1].items():
            active = (vc == self._active_vc)
            p.setPen(base_pen)
            p.setBrush(active_brush if active else Qt.BrushStyle.NoBrush)
            for poly in polys:
                p.drawPolygon(poly)

        if self._dot_en is not None:
            p.setPen(QPen(QColor(theme.PAPER), 1.2))
            p.setBrush(QBrush(QColor(theme.CLAY)))
            c = self._to_px(*self._dot_en)
            p.drawEllipse(c, 3.2, 3.2)

        p.setPen(QColor(theme.MUTED))
        f = p.font(); f.setPointSize(6); p.setFont(f)
        p.drawText(2, self.height() - 2, "\u00a9 OS/BRC")
        p.end()
