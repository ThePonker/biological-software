"""The base layers of the Mapping tab's map, under the recorded squares (R5, 11 Oct 2026; split
out of grid_map.py, a mixin for GridMap).

Bottom to top: land, the light tint of the VCs holding records, the coast, the grid, the VC boundary lines, then the modern districts when switched on.
GridMap.draw() puts the recorded squares, the selected VC's outline and the labels on top.

R5, from Wil's 300 dpi Atlas page of VC23 and the screen:
- every border two VCs share was stroked twice (once per VC), as two grey lines side by side,
  because the two VCs' rings were thinned separately. The VC rings are now made to share their
  border points (vc_topology.snap_rings) and every edge is drawn once (unique_chains).
- faint pale lines inside the counties with the districts off: seams and slivers where the
  tinted VCs did not meet (and doubled tint where they overlapped). The tint is now filled from
  the shared-border rings, so neighbours meet exactly: no gap, no overlap. (One path for the
  whole tint was tried: a path that big fills 5-10 times slower in Qt, and with the borders
  shared the per-VC fill leaves nothing to see: at most 0.6 % less tint on an edge pixel.)
- the districts were drawn under the VC tint and boundaries and were lost: now above both, in
  a thin dashed grey so the VC boundaries still read as the main lines.
- VC boundaries and districts sit under the recorded squares (Wil's choice: squares solid).

Display only.
"""
from __future__ import annotations

from typing import Dict, List

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPolygonF

from shared.maps._theme import theme
from shared.maps.coast import split_edges_cached
from shared.maps.species_dist_map import _COAST_C, _GRID10_C, _GRID100_C, _LAND_C
from shared.maps.vc_labels import draw_boundaries
from shared.maps.vc_map import _SIMPLIFY_TOL
from shared.maps.vc_topology import snap_rings_cached, unique_chains

DISTRICT_W = 0.8            # the district lines, in screen pixels (x k on the page)
DISTRICT_DASH = [4.0, 3.0]  # dash, gap: in line widths
TINT_ALPHA = 40             # the VCs-with-records tint over the land


def district_pen(k: float = 1.0) -> QPen:
    """Thin dashed grey: plainly not a VC boundary (solid), and lighter than one."""
    a, b = QColor(theme.MUTED), QColor(theme.CARD)
    c = QColor(round(a.red() * 0.6 + b.red() * 0.4), round(a.green() * 0.6 + b.green() * 0.4),
               round(a.blue() * 0.6 + b.blue() * 0.4))
    pen = QPen(c, DISTRICT_W * k)
    pen.setDashPattern(DISTRICT_DASH)
    pen.setCapStyle(Qt.PenCapStyle.FlatCap)
    return pen


class BasemapLayersMixin:
    """Uses GridMap's _land, _land_source, _vc_rings, _geojson, _vc_highlight, _districts_on,
    _vc_bounds_on and has_districts()."""

    def _init_layers(self):
        self._poly_cache = None                    # (fit key, land polygons, {vc: polygons})
        self._line_cache: Dict[str, tuple] = {}    # name -> (fit key, projected polylines)

    def _topo(self) -> Dict[int, list]:
        """The VC rings with their shared borders made common (vc_topology), once."""
        if not self._vc_rings:
            return {}
        return snap_rings_cached(("vc", self._geojson, _SIMPLIFY_TOL), self._vc_rings)

    @staticmethod
    def _fit_key(fit):
        return (fit.extent, fit.w, fit.h, fit.x0, fit.y0)

    def _polygons(self, fit):
        """(the land polygons, {vc: its shared-border polygons}) projected through `fit`;
        the last projection is kept (paint is hot)."""
        key = self._fit_key(fit)
        if self._poly_cache and self._poly_cache[0] == key:
            return self._poly_cache[1], self._poly_cache[2]

        def poly(ring):
            return QPolygonF([QPointF(*fit.to_px(e, n)) for e, n in ring])
        land = [poly(r) for r in self._land]
        vcs = {vc: [poly(r) for r in rings] for vc, rings in self._topo().items()}
        self._poly_cache = (key, land, vcs)
        return land, vcs

    def _chains(self, name) -> List[list]:
        """OSGB polylines, each edge once: "coast" / "districts" (the land's sea-facing /
        inland edges) or "vc_inland" (VC borders that are not coast); worked out once per
        source (coast.py, vc_topology.py)."""
        if name == "vc_inland":
            # R8 review: its own key. ("vc", geojson, "r5") was also the land's key below when
            # the land is drawn from the VC rings (no gb_outline.json), so whichever was worked
            # out first was used for both: after a first paint (coast first) the VC boundary
            # layer was the land's unsnapped borders, each shared border twice (32,165 km
            # instead of 19,136 km).
            topo = [r for rs in self._topo().values() for r in rs]
            return split_edges_cached(("vc_topo", self._geojson, _SIMPLIFY_TOL, "r5"), topo,
                                      lambda: unique_chains(topo))[1]
        if not self._land_source:
            return []
        coast, inland = split_edges_cached(self._land_source + ("r5",), self._land,
                                           lambda: unique_chains(self._land))
        return coast if name == "coast" else inland

    def _lines(self, name, fit):
        """_chains(name) projected through `fit` (kept until the fit changes)."""
        key = self._fit_key(fit)
        hit = self._line_cache.get(name)
        if hit is None or hit[0] != key:
            hit = (key, [QPolygonF([QPointF(*fit.to_px(e, n)) for e, n in c])
                         for c in self._chains(name)])
            self._line_cache[name] = hit
        return hit[1]

    def draw_base(self, p: QPainter, fit, k: float = 1.0):
        """Land, VC tint, coast, grid, VC boundaries, districts (see the module's notes)."""
        land, vc_polys = self._polygons(fit)
        self._draw_land(p, land, k)
        self._draw_tint(p, vc_polys)
        # R4: the coast is the land's sea-facing edges only (coast.py)
        p.setPen(QPen(QColor(_COAST_C), 0.7 * k))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for line in self._lines("coast", fit):
            p.drawPolyline(line)
        self._draw_grid(p, fit, k)
        if self._vc_bounds_on and self._vc_rings:
            draw_boundaries(p, [self._lines("vc_inland", fit)], k)  # the coast is drawn already
        if self._districts_on and self.has_districts():
            self._draw_districts(p, fit, k)

    def _draw_land(self, p: QPainter, land, k: float):
        # gb_outline.json's districts share their border points exactly; the same-colour edge
        # covers the antialiased seam where two meet (measured R5: none left to see)
        land_c = QColor(_LAND_C)
        p.setPen(QPen(land_c, 0.8 * k))
        p.setBrush(QBrush(land_c))
        for poly in land:
            p.drawPolygon(poly)

    def _draw_tint(self, p: QPainter, vc_polys):
        """VCs holding records: a light tint, from the shared-border rings."""
        hi = QColor(theme.MOSS)
        hi.setAlpha(TINT_ALPHA)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(hi))
        for vc in self._vc_highlight:
            for poly in vc_polys.get(vc, ()):
                p.drawPolygon(poly)

    def _draw_districts(self, p: QPainter, fit, k: float):
        """Modern districts (gb_outline.json's inland edges, each once): thin dashed grey."""
        p.setPen(district_pen(k))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for line in self._lines("districts", fit):
            p.drawPolyline(line)

    def _draw_grid(self, p, fit, k):
        minE, minN, maxE, maxN = fit.extent
        span = max(maxE - minE, maxN - minN)
        steps = [(100000, QColor(_GRID100_C), 0.5)]
        if span <= 250000:
            steps.append((10000, QColor(_GRID10_C), 0.3))
        for step, col, w in steps:
            p.setPen(QPen(col, w * k))
            e = (int(minE) // step) * step
            while e <= maxE:
                if 0 <= e <= 700000:
                    x0, y0 = fit.to_px(e, max(minN, 0))
                    x1, y1 = fit.to_px(e, min(maxN, 1300000))
                    p.drawLine(QPointF(x0, y0), QPointF(x1, y1))
                e += step
            n = (int(minN) // step) * step
            while n <= maxN:
                if 0 <= n <= 1300000:
                    x0, y0 = fit.to_px(max(minE, 0), n)
                    x1, y1 = fit.to_px(min(maxE, 700000), n)
                    p.drawLine(QPointF(x0, y0), QPointF(x1, y1))
                n += step
