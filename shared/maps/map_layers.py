"""The base layers of the Mapping tab's map, under the recorded squares (R5, 11 Oct 2026; split
out of grid_map.py, a mixin for GridMap).

Bottom to top: land, woodland, towns, water areas, rivers, main roads (the last five from
data/maps/layers/, layers.py, when ticked in the Layers menu), the light tint of the VCs holding
records, the coast, the grid, the VC boundary lines, then the districts when switched on.
GridMap.draw() puts the recorded squares, the selected VC's outline and the labels on top.
With data/maps/layers/land_*.json the land comes from it (polygons with holes, WindingFill) and
the coast is every edge of it; without, gb_outline.json / the VC rings as before (17 Oct 2026).

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

18 Oct 2026 (speed, Wil: panning and zooming "a little bit laggy" with the real files): each
layer is built once per (layer, level of detail, area) as ONE QPainterPath in OSGB metres and
drawn through a QTransform equal to MapFit.to_px (scale and offset, y flipped), instead of
projecting every point again whenever the view changed; line widths are divided by the scale
so they stay in screen pixels (x k on the page). The finished background (everything under
the squares) is kept as a pixmap for as long as the view and the switches are unchanged, so a
hover or a selection repaints from it. BIOSOFT_MAP_TIMING=1 prints each layer's build and paint
time (map_timing.py).

Display only.
"""
from __future__ import annotations

from typing import Dict, List

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import (QBrush, QColor, QPainter, QPainterPath, QPen, QPixmap, QPolygonF,
                           QTransform)

from shared.maps import layers
from shared.maps.map_timing import note, timed
from shared.maps._theme import theme
from shared.maps.coast import split_edges_cached
from shared.maps.species_dist_map import _SEA_C, _COAST_C, _GRID10_C, _GRID100_C, _LAND_C
from shared.maps.vc_labels import draw_boundaries
from shared.maps.vc_map import _SIMPLIFY_TOL
from shared.maps.vc_topology import snap_rings_cached, unique_chains

DISTRICT_W = 0.8            # the district lines, in screen pixels (x k on the page)
DISTRICT_DASH = [4.0, 3.0]  # dash, gap: in line widths
TINT_ALPHA = 40             # the VCs-with-records tint over the land
SNAP = 25000                # metres: county-detail areas are cut on this grid (cache reuse)


def layer_transform(fit) -> QTransform:
    """OSGB metres -> the pixels of `fit`: exactly MapFit.to_px (a scale, an offset, y flipped)."""
    s = fit.scale
    return QTransform(s, 0.0, 0.0, -s, fit.x0 + fit.offx - fit.extent[0] * s,
                      fit.y0 + fit.h - fit.offy + fit.extent[1] * s)


def district_pen(k: float = 1.0, scale: float = 1.0) -> QPen:
    """Thin dashed grey: plainly not a VC boundary (solid), and lighter than one. `scale`:
    pixels per unit of the coordinates it is drawn in (metres through layer_transform)."""
    a, b = QColor(theme.MUTED), QColor(theme.CARD)
    c = QColor(round(a.red() * 0.6 + b.red() * 0.4), round(a.green() * 0.6 + b.green() * 0.4),
               round(a.blue() * 0.6 + b.blue() * 0.4))
    pen = QPen(c, DISTRICT_W * k / scale)
    pen.setDashPattern(DISTRICT_DASH)
    pen.setCapStyle(Qt.PenCapStyle.FlatCap)
    return pen


class BasemapLayersMixin:
    """Uses GridMap's _land, _land_source, _vc_rings, _geojson, _vc_highlight, _districts_on,
    _vc_bounds_on and has_districts()."""

    def _init_layers(self):
        self._poly_cache = None                    # (fit key, land polygons, {vc: polygons})
        self._line_cache: Dict[str, tuple] = {}    # name -> (fit key, projected polylines)
        self._layer_cache: Dict[tuple, QPainterPath] = {}   # (layer, lod, area) -> path in metres
        self._base_cache: tuple = (None, None)     # (view state, the background's pixmap)

    def _use_layer_land(self) -> bool:
        return "land" in self._layer_files

    def _layer_shape(self, fit, key: str) -> QPainterPath:
        """A layer round the view as one QPainterPath in OSGB metres (draw it through
        layer_transform(fit)), kept per (layer, level of detail, area): a polygon layer
        (WindingFill, so holes are holes), a line layer (one subpath per line) or the
        districts (each shared edge once)."""
        cache = self._layer_cache
        # the level of detail follows what is on screen (zoomed in on the GB view: county
        # detail); county detail is only taken for the area round the view, snapped to 25 km
        # so panning reuses it (17 Oct 2026)
        view = getattr(self, "_layer_view", None) or fit.extent
        lod = layers.lod_for_extent(view)
        if lod == "county":
            e0, n0, e1, n1 = view
            m = max(e1 - e0, n1 - n0) * 0.5
            box = tuple(int(v // SNAP * SNAP) + (SNAP if i >= 2 else 0) for i, v in
                        enumerate((e0 - m, n0 - m, e1 + m, n1 + m)))
        else:
            e0, n1 = fit.to_en(fit.x0, fit.y0)
            e1, n0 = fit.to_en(fit.x0 + fit.w, fit.y0 + fit.h)
            box = (e0, n0, e1, n1)
        ck = (key, lod, box)
        if ck not in cache:
            if sum(1 for c in cache if c[0] == key) >= 4:        # keep a few areas per layer
                for old in [c for c in cache if c[0] == key][:-3]:
                    cache.pop(old, None)
            with timed("build", f"{key} {lod}"):
                feats = layers.features_in(layers.load(self._maps_dir, key, lod), box)
                cache[ck] = self._build_path(key, feats)
        return cache[ck]

    @staticmethod
    def _build_path(key, feats) -> QPainterPath:
        def poly(pts):
            return QPolygonF([QPointF(e, n) for e, n in pts])
        path = QPainterPath()
        if key == "districts":      # each shared edge once (the dashes would double up)
            for c in unique_chains([r for f in feats for r in f.get("rings", ())]):
                path.addPolygon(poly(c))
        elif next((lay.kind for lay in layers.LAYERS if lay.key == key), "") == "line":
            for f in feats:
                if f.get("line"):
                    path.addPolygon(poly(f["line"]))
        else:
            # WindingFill: build_map_layers.py writes outer rings one way round and holes the
            # other, so a hole is a hole and two features that touch or overlap do not cancel
            path.setFillRule(Qt.FillRule.WindingFill)
            for f in feats:
                for ring in f.get("rings", ()):
                    path.addPolygon(poly(ring))
                    path.closeSubpath()
        return path

    def _paint_path(self, p: QPainter, fit, path: QPainterPath, pen, brush, label: str):
        """Draw a metres path through layer_transform(fit) with `pen` (widths in metres)."""
        with timed("paint", label):
            p.save()
            p.setWorldTransform(layer_transform(fit), True)
            p.setPen(pen)
            p.setBrush(brush)
            p.drawPath(path)
            p.restore()

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
        land = [] if self._use_layer_land() else [poly(r) for r in self._land]
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
        """Land, layers, VC tint, coast, grid, VC boundaries, districts (see the module's notes)."""
        land, vc_polys = self._polygons(fit)
        own_land = self._use_layer_land()
        if own_land:
            self._draw_layer_land(p, fit, k)
        else:
            self._draw_land(p, land, k)
        self._draw_layers(p, fit, k)
        self._draw_tint(p, vc_polys)
        # R4: the coast is the land's sea-facing edges only (coast.py); the layers' land has
        # no districts inside it, so every edge of it is coast
        if own_land:
            self._paint_path(p, fit, self._layer_shape(fit, "land"),
                             QPen(QColor(_COAST_C), 0.7 * k / fit.scale), Qt.BrushStyle.NoBrush,
                             "coast")
        else:
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

    def _draw_layer_land(self, p: QPainter, fit, k: float):
        land_c = QColor(_LAND_C)
        self._paint_path(p, fit, self._layer_shape(fit, "land"),
                         QPen(land_c, 0.8 * k / fit.scale), QBrush(land_c), "land")

    def _draw_layers(self, p: QPainter, fit, k: float):
        """The ticked layers that have a file, in the registry's order (pale, under the tint)."""
        for lay in layers.LAYERS:
            if lay.toggle is None or lay.toggle not in self._layers_on \
                    or lay.key not in self._layer_files:
                continue
            fill, line, w = layers.style(lay.key)
            shape = self._layer_shape(fit, lay.key)
            if lay.kind == "polygon":
                self._paint_path(p, fit, shape, QPen(fill, w * k / fit.scale), QBrush(fill),
                                 lay.key)
            else:
                pen = QPen(line, w * k / fit.scale)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                self._paint_path(p, fit, shape, pen, Qt.BrushStyle.NoBrush, lay.key)

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
        """Districts (the layer file's, else gb_outline.json's inland edges; each edge once):
        thin dashed grey."""
        if "districts" in self._layer_files:
            self._paint_path(p, fit, self._layer_shape(fit, "districts"),
                             district_pen(k, fit.scale), Qt.BrushStyle.NoBrush, "districts")
            return
        p.setPen(district_pen(k))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for line in self._lines("districts", fit):
            p.drawPolyline(line)

    def _draw_grid(self, p, fit, k):
        minE, minN, maxE, maxN = fit.extent
        span = max(maxE - minE, maxN - minN)
        steps = [(100000, QColor(_GRID100_C), 0.5)]
        if span <= layers.COUNTY_SPAN:
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

    # ---------------------------------------------------------------- the kept background
    def _base_key(self, fit, k: float, zoom: float):
        """Everything the background (land .. districts, under the squares) depends on."""
        return (self._fit_key(fit), self._pan.x(), self._pan.y(), zoom, k,
                self.devicePixelRatioF(), self.width(), self.height(),
                frozenset(self._layers_on), self._districts_on, self._vc_bounds_on,
                frozenset(self._vc_highlight), layers.saved_colours())

    def base_pixmap(self, fit, k: float, zoom: float) -> QPixmap:
        """The background drawn as the screen shows it (pan and zoom applied), kept until the
        view, a switch, the highlighted VCs or a layer colour changes: a hover or a selected
        square repaints from it (the squares, outline and labels are drawn over it)."""
        key = self._base_key(fit, k, zoom)
        if self._base_cache[0] == key:
            note("base", "reused")
            return self._base_cache[1]
        dpr = self.devicePixelRatioF()
        pm = QPixmap(max(1, round(self.width() * dpr)), max(1, round(self.height() * dpr)))
        pm.setDevicePixelRatio(dpr)
        pm.fill(QColor(_SEA_C))
        q = QPainter(pm)
        q.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._apply_pan_zoom(q)
        self.set_layer_view(fit, zoom)
        with timed("base", "all layers drawn"):
            self.draw_base(q, fit, k)
        q.end()
        self._base_cache = (key, pm)
        return pm
