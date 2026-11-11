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
time (map_timing.py). (18 Oct, later: the screen now keeps the whole static picture, squares and
labels too, with a margin, map_picture.py; this file only draws the layers.)

18 Oct 2026 (six more layers, all off by default): relief (an image, multiplied, just over the
land: relief.py), foreshore and parks and green space (pale fills), national parks (outline
only), railways (thin dashed) and, last of all, over the squares, the place names
(place_names.py; GridMap.draw() calls _draw_place_names).

Display only.
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Dict, List

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QPolygonF, QTransform

from shared.maps import env_classes, grid_overlay, layer_bin, layer_opacity, layers, place_names, relief, value_grid
from shared.maps import env_registry as env
from shared.maps.map_ahead import bytes_bin, bytes_feats, layer_parts
from shared.maps.map_timing import timed
from shared.maps._theme import theme
from shared.maps.coast import split_edges_cached
from shared.maps.species_dist_map import _COAST_C, _GRID10_C, _GRID100_C, _LAND_C
from shared.maps.vc_labels import draw_boundaries
from shared.maps.vc_map import _SIMPLIFY_TOL
from shared.maps.vc_topology import snap_rings_cached, unique_chains

DISTRICT_W = 0.8            # the district lines, in screen pixels (x k on the page)
DISTRICT_DASH = [4.0, 3.0]  # dash, gap: in line widths
TINT_ALPHA = 40             # the VCs-with-records tint over the land
SNAP = 25000                # metres: county-detail areas are cut on this grid (cache reuse)
OUTLINE_W = 0.6             # the thin outline of designated sites and access land, px at k = 1
OUTLINED_SECTIONS = (env.DESIG, env.ACC)    # their fills are pale: a darker edge makes them read


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


class _VcPolygons(Mapping):
    """{vc: [QPolygonF in pixels]} that makes a VC's polygons the first time it is looked up."""

    def __init__(self, owner, transform: QTransform):
        self._owner, self._tr, self._done = owner, transform, {}

    def __getitem__(self, vc):
        got = self._done.get(vc)
        if got is None:
            got = self._done[vc] = self._owner._metre_vc(vc).toSubpathPolygons(self._tr)
        return got

    def __contains__(self, vc):
        return vc in self._owner._topo()

    def __iter__(self):
        return iter(self._owner._topo())

    def __len__(self):
        return len(self._owner._topo())


class BasemapLayersMixin:
    """Uses GridMap's _land, _land_source, _vc_rings, _geojson, _vc_highlight, _districts_on,
    _vc_bounds_on and has_districts()."""

    def _init_layers(self):
        self._poly_cache = None                    # (fit key, land polygons, {vc: polygons}) in pixels
        self._line_cache: Dict[str, tuple] = {}    # name -> (fit key, projected polylines)
        self._metre_polys = None                   # (land path, {vc: path}): the rings in metres, once
        self._metre_lines: Dict[str, QPainterPath] = {}     # name -> its chains in metres, once
        self._fast_fill = False                    # the screen's picture only (not the atlas page)
        self._grid_force = None                    # render_sheet: the page's own grid choice
        self._layer_cache: Dict[tuple, QPainterPath] = {}   # (layer, lod, area, class) -> path in metres
        self._class_index: Dict[tuple, List[str]] = {}      # (layer, lod, area) -> its classes
        self._init_ahead()                         # R16: the look-ahead worker (map_ahead.py)

    def _use_layer_land(self) -> bool:
        return "land" in self._layer_files

    def _layer_ck(self, fit, key: str, view=None):
        """(level of detail, area box) the layer is built for: what is on screen decides the
        level of detail; county detail is only taken for the area round the view, snapped to
        25 km so panning reuses it (17 Oct 2026)."""
        view = view or getattr(self, "_layer_view", None) or fit.extent
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
        return lod, box

    def _layer_shape(self, fit, key: str, view=None, cls=None) -> QPainterPath:
        """A layer round the view as one QPainterPath in OSGB metres (draw it through
        layer_transform(fit)), kept per (layer, level of detail, area, class): a polygon layer
        (WindingFill, so holes are holes), a line layer (one subpath per line) or the
        districts (each shared edge once). cls: for a classed Environment layer, the path of
        the features of that class "t" only (see _layer_classes)."""
        cache = self._layer_cache
        lod, box = self._layer_ck(fit, key, view)
        ck = (key, lod, box, cls)
        if ck not in cache:
            areas = list(dict.fromkeys((c[1], c[2]) for c in cache if c[0] == key))
            if (lod, box) not in areas and len(areas) >= 4:      # keep a few areas per layer
                for old in areas[:-3]:
                    for c in [c for c in cache if c[0] == key and (c[1], c[2]) == old]:
                        cache.pop(c, None)
                        self._class_index.pop(c[:3], None)
            classed = cls is not None
            pre = self._ahead_take(key, lod, box, classed)      # the numpy half, done ahead (map_ahead.py)
            if pre is None:
                with timed("build", f"{key} {lod}"):
                    pre = layer_parts(key, layers.load(self._maps_dir, key, lod), box, classed)
            with timed("build", f"{key} {lod} path"):
                for c, pb in pre[0].items():
                    cache[(key, lod, box, c)] = layer_bin.path_from_bytes(pb)
            if classed:
                self._class_index[(key, lod, box)] = pre[1]
        hit = cache.get(ck)
        return QPainterPath() if hit is None else hit

    def _layer_classes(self, fit, key: str) -> List[str]:
        """The classes of a classed layer present round the view."""
        lod, box = self._layer_ck(fit, key)
        if (key, lod, box) not in self._class_index:
            self._layer_shape(fit, key, cls="")
        return self._class_index.get((key, lod, box), [])

    @staticmethod
    def _build_path_bin(key, data, idx) -> QPainterPath:
        """The path of a LayerBin's features `idx` (map_ahead.bytes_bin, then the Qt step)."""
        return layer_bin.path_from_bytes(bytes_bin(key, data, idx))

    @staticmethod
    def _build_path(key, feats) -> QPainterPath:
        """One path from feature dicts, built through numpy (layer_bin), not one QPointF per point."""
        return layer_bin.path_from_bytes(bytes_feats(key, feats))

    def _paint_path(self, p: QPainter, fit, path: QPainterPath, pen, brush, label: str):
        """Draw a metres path through layer_transform(fit) with `pen` (widths in metres)."""
        with timed("paint", label):
            p.save()
            p.setWorldTransform(layer_transform(fit), True)
            if self._fast_fill and brush != Qt.BrushStyle.NoBrush:
                # screen only: the fill without antialiasing (about 3x faster for woodland;
                # measured: no pixel differs by more than 7/255), the outline antialiased
                p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(brush)
                p.drawPath(path)
                p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(pen)
                p.drawPath(path)
            else:
                p.setPen(pen)
                p.setBrush(brush)
                p.drawPath(path)
            p.restore()

    def _topo(self) -> Dict[int, list]:
        """The VC rings with their shared borders made common (vc_topology), once."""
        if not self._vc_rings:
            return {}
        return snap_rings_cached(("vc", self._geojson, _SIMPLIFY_TOL), self._vc_rings,
                                 source=self._geojson)

    def _split_disk(self, which: str):
        """(source file, cache name) for the on-disk copy of a coast / inland split (R16,
        map_disk_cache): which "topo" is the VC rings' split, "land" the land's."""
        if which == "topo":
            return (self._geojson, "vc_topo") if self._geojson else None
        src = self._land_source
        if not src:
            return None
        if src[0] == "outline":
            return os.path.join(src[1], "gb_outline.json"), "land_outline"
        return src[1], "land_vc"

    @staticmethod
    def _fit_key(fit):
        return (fit.extent, fit.w, fit.h, fit.x0, fit.y0)

    def _polygons(self, fit):
        """(the land polygons, {vc: its shared-border polygons}) as QPolygonF in the pixels of
        `fit`; the last projection is kept (paint is hot). R16: the rings are built once as ONE
        path in OSGB metres (numpy, layer_bin.lists_path: no QPointF per point, the pattern that
        crashed Python 3.14.0's GC), and Qt turns it into the polygons for each fit
        (toSubpathPolygons through layer_transform(fit): the same sums as MapFit.to_px, in C++).
        Drawn as before, a polygon at a time, so the picture is unchanged. A VC's path is only
        built when asked for (the tint, the selected outline: a few VCs, not 112)."""
        key = self._fit_key(fit)
        if self._poly_cache and self._poly_cache[0] == key:
            return self._poly_cache[1], self._poly_cache[2]
        if self._metre_polys is None:
            land = None if self._use_layer_land() else layer_bin.lists_path(self._land, False, False)
            self._metre_polys = (land, {})
        tr = layer_transform(fit)
        land = [] if self._metre_polys[0] is None else self._metre_polys[0].toSubpathPolygons(tr)
        self._poly_cache = (key, land, _VcPolygons(self, tr))
        return self._poly_cache[1], self._poly_cache[2]

    def _metre_vc(self, vc) -> QPainterPath:
        """One VC's shared-border rings as a path in metres (built once); KeyError if it has none."""
        got = self._metre_polys[1].get(vc)
        if got is None:
            got = self._metre_polys[1][vc] = layer_bin.lists_path(self._topo()[vc], False, False)
        return got

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
                                      lambda: unique_chains(topo), disk=self._split_disk("topo"))[1]
        if not self._land_source:
            return []
        coast, inland = split_edges_cached(self._land_source + ("r5",), self._land,
                                           lambda: unique_chains(self._land),
                                           disk=self._split_disk("land"))
        return coast if name == "coast" else inland

    def _lines(self, name, fit) -> List[QPolygonF]:
        """_chains(name) as one QPolygonF per chain in the pixels of `fit` (kept until the fit
        changes): built once as one path in metres (numpy) and turned into polygons by Qt for
        each fit (see _polygons), drawn a polyline at a time as before (R16)."""
        key = self._fit_key(fit)
        hit = self._line_cache.get(name)
        if hit is None or hit[0] != key:
            metres = self._metre_lines.get(name)
            if metres is None:
                metres = self._metre_lines[name] = layer_bin.lists_path(self._chains(name), False, False)
            hit = (key, metres.toSubpathPolygons(layer_transform(fit)))
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
        lines_on, tetrads_on = self._grid_state()
        if not lines_on:                # the grid overlay's lines replace these faint ones
            self._draw_grid(p, fit, k)
        if self._vc_bounds_on and self._vc_rings:
            draw_boundaries(p, [self._lines("vc_inland", fit)], k)  # the coast is drawn already
        if self._districts_on and self.has_districts():
            self._draw_districts(p, fit, k)
        if lines_on or tetrads_on:      # R19: above the layers, under the squares
            with timed("paint", "grid overlay"):
                grid_overlay.draw(p, fit, k, layer_transform(fit), lines_on, tetrads_on)

    def _grid_state(self):
        """(grid lines, tetrads) to draw: the Layers window's two ticks on the screen; the atlas
        page's own choice (render_sheet sets _grid_force) so its "Grid" tick decides there."""
        force = getattr(self, "_grid_force", None)
        if force is not None:
            return force
        return "grid_lines" in self._layers_on, "grid_tetrads" in self._layers_on

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
        """The ticked layers that have a file, in the registry's order (pale, under the tint).
        The place names are text, drawn later (_draw_place_names)."""
        for lay in layers.LAYERS:
            if lay.toggle is None or lay.toggle not in self._layers_on \
                    or lay.key not in self._layer_files or lay.kind == "point":
                continue
            if lay.kind == "image":
                rel = relief.load(self._maps_dir)
                if rel is not None:
                    with timed("paint", lay.key):
                        relief.draw(p, rel, layer_transform(fit))
                continue
            if lay.kind == "grid":      # HadUK-Grid averages: a shaded image (value_grid.py)
                grid = value_grid.load(self._maps_dir, lay.key)
                if grid is not None:
                    with timed("paint", lay.key):
                        value_grid.draw(p, grid, layers.grid_ramp(lay.key), layer_transform(fit))
                continue
            if layer_opacity.has_opacity(lay.key):
                self._draw_env_polygon(p, fit, k, lay.key)
                continue
            fill, line, w = layers.style(lay.key)
            shape = self._layer_shape(fit, lay.key)
            if fill is not None:
                self._paint_path(p, fit, shape, QPen(fill, w * k / fit.scale), QBrush(fill), lay.key)
                continue
            pen = QPen(line, w * k / fit.scale)
            dash = layers.DASHES.get(lay.key)
            if dash:
                pen.setDashPattern(list(dash))
                pen.setCapStyle(Qt.PenCapStyle.FlatCap)
            else:
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            self._paint_path(p, fit, shape, pen, Qt.BrushStyle.NoBrush, lay.key)

    def _draw_env_polygon(self, p: QPainter, fit, k: float, key: str):
        """An Environment polygon layer at its remembered opacity: one colour per class when the
        layer is classed (env_classes), else its single colour. Designated sites and access
        land also get a thin outline (the fill darkened, solid) so a pale fill still shows."""
        fill, _line, w = layers.style(key)
        a = layer_opacity.alpha(key)
        outlined = env.ENV_BY_KEY[key].section in OUTLINED_SECTIONS
        if env_classes.is_classed(key):
            todo = [(env_classes.class_colour(key, c), c) for c in self._layer_classes(fit, key)]
            todo = [(QColor(hx), c) for hx, c in todo]
        else:
            todo = [(QColor(fill), None)]
        for col, cls in todo:
            col.setAlpha(a)
            shape = self._layer_shape(fit, key, cls=cls)
            self._paint_path(p, fit, shape, QPen(col, w * k / fit.scale), QBrush(col), key)
            if outlined:
                edge = col.darker(160)
                edge.setAlpha(255)
                self._paint_path(p, fit, shape, QPen(edge, OUTLINE_W * k / fit.scale),
                                 Qt.BrushStyle.NoBrush, key)

    def _draw_place_names(self, p: QPainter, fit, zoom: float, vc_labels=()):
        """The place names, when ticked and installed: over everything, after the VC labels
        (`vc_labels`: what draw_labels returned) so they never cover those. A name that would touch a
        recorded square is left out only while the squares are solid (opacity 100 %); with
        see-through squares (set_square_opacity) it is drawn over them. Screen and page alike."""
        if "names" not in self._layers_on or "names" not in self._layer_files:
            return
        view = getattr(self, "_layer_view", None) or fit.extent
        lists = place_names.feature_lists(self._maps_dir, layers.lod_for_extent(view))
        span = max(fit.w, fit.h) / fit.scale / max(zoom, 1.0)       # metres across the view
        occupied, _inside = self._label_tests(p, fit)
        if self._square_opacity < 1.0:      # see-through squares: names are drawn over them
            occupied = None
        taken = [r.adjusted(-2, -2, 2, 2) for _vc, _t, r, _s in vc_labels]
        with timed("paint", "names"):
            place_names.draw_place_names(p, fit, lists, span, layers.style("names")[1], taken,
                                         occupied)

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
        # the 10 km lines follow what is on screen (zoomed in on the GB view too; 18 Oct 2026)
        v = getattr(self, "_layer_view", None) or fit.extent
        span = max(v[2] - v[0], v[3] - v[1])
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
