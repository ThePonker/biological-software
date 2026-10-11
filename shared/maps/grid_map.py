"""Native grid-square distribution map: the Mapping tab's map (backlog H1, H3-H5).

Built from the Data Entry map parts in this package: the same vector GB basemap (complete
coastline from data/maps/gb_outline.json, else the BRC vice-county polygons), the same
palette, and the same scroll-zoom / drag-pan. On top it draws hectad / tetrad / monad
squares as polygons (geometry in grid_squares.py), reports the square under a click, and
renders the current view to a print-resolution PNG (an atlas page).

R9-5 (11 Oct 2026): vice-county labels (numbers at national scale, names zoomed in; a switch
turns them off) and a thicker outline round the selected VC, on screen and on the page
(vc_labels.py). R9-6: sheet_view() gives the area an atlas page really shows, so its footer
can count what is in view. R4: labels drawn in device pixels (no more garbled names when
zoomed), nudged off recorded squares; VC boundary lines with their own switch; the coast
line is only the sea-facing edges (coast.py): it no longer strokes every district border of
gb_outline.json (or every VC border without it); the districts have their own switch.

No WebEngine, no tiles, no internet. Display only: it never touches a database.
"""
from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QToolTip, QWidget

from shared.maps import grid_squares as gs
from shared.maps.coast import split_edges_cached
from shared.maps.atlas_sheet import AtlasSheetMixin, draw_split  # noqa: F401 (draw_split: old import path)
from shared.maps._theme import theme
from shared.maps.panzoom import PanZoomMixin
from shared.maps.species_dist_map import (_COAST_C, _GRID10_C, _GRID100_C, _LAND_C, _SEA_C,
                                          _load_gb_outline)
from shared.maps.vc_labels import (draw_boundaries, draw_labels, draw_outline, label_points,
                                   point_in_ring)
from shared.maps.vc_map import load_vc_polygons, vc_names

_CLICK_SLOP = 4          # px of movement still counted as a click, not a drag


class GridMap(AtlasSheetMixin, PanZoomMixin, QWidget):
    """GB basemap with coloured grid squares. Scroll to zoom, drag to pan, double-click resets.

    Signals:
        square_clicked(str)   label of a square holding records, when clicked
    """

    square_clicked = Signal(str)

    def __init__(self, geojson_path: Optional[str] = None, maps_dir: Optional[str] = None,
                 parent=None):
        super().__init__(parent)
        land, _b = _load_gb_outline(maps_dir) if maps_dir else ({}, None)
        # R4: where the land comes from: "outline" (gb_outline.json: on Wil's PC the 2013 ONS
        # local-authority districts), "vc" (the VC polygons at 100 m) or None
        self._land_source = ("outline", maps_dir) if land else None
        vc_rings, _b = load_vc_polygons(geojson_path) if geojson_path else ({}, None)
        if not land and geojson_path:
            land, _b = load_vc_polygons(geojson_path, tol=100.0)
            self._land_source = ("vc", geojson_path) if land else None
        self._land = [ring for rings in land.values() for ring in rings]
        self._vc_rings: Dict[int, list] = vc_rings
        self._extent = gs.GB_LAND
        self._size = gs.HECTAD
        self._squares: Dict[str, dict] = {}       # label -> {count, fill, ...}
        self._selected: Optional[str] = None
        self._vc_highlight: set = set()
        self._vc_names: Dict[int, str] = vc_names(geojson_path) if geojson_path else {}
        self._label_pts = None                    # label_points(), worked out on first use
        self._vc_labels_on = True
        self._vc_bounds_on = True                 # R4: VC boundary lines (a switch)
        self._vc_outline: Optional[int] = None    # the selected VC, outlined (R9-5)
        self._message = ""
        self._press = None
        self._poly_cache = None
        self._geojson = geojson_path
        self._districts_on = False                # R4: modern district lines (outline only)
        self._line_cache: Dict[str, tuple] = {}   # name -> (fit key, projected polylines)
        self._init_panzoom(True)
        self.setMouseTracking(True)
        self.setMinimumSize(300, 360)

    # ---------------------------------------------------------------- data in
    def has_basemap(self) -> bool:
        return bool(self._land)

    def has_districts(self) -> bool:
        """True when the land is gb_outline.json (whose inland edges are modern districts)."""
        return bool(self._land_source) and self._land_source[0] == "outline"

    def set_districts(self, on: bool):
        """Modern district borders (gb_outline.json's inland edges), light, or none (R4)."""
        self._districts_on = bool(on)
        self.update()

    def set_squares(self, squares: Dict[str, dict], size: int):
        """squares: label -> dict with at least 'count' and 'fill' (a colour hex)."""
        self._squares = dict(squares)
        self._size = size
        if self._selected not in self._squares:
            self._selected = None
        self.update()

    def clear_squares(self):
        self.set_squares({}, self._size)

    def set_message(self, text: str):
        """A line drawn in the corner of the map (why it is empty, what was left out)."""
        self._message = text or ""
        self.update()

    def set_selected(self, label: Optional[str]):
        self._selected = label
        self.update()

    def highlight_vcs(self, vc_numbers):
        self._vc_highlight = {int(v) for v in vc_numbers or []}
        self.update()

    def set_vc_labels(self, on: bool):
        """VC numbers / names on the map (and its atlas page), or none."""
        self._vc_labels_on = bool(on)
        self.update()

    def set_vc_boundaries(self, on: bool):
        """Vice-county boundary lines on the map (and its atlas page), or none (R4)."""
        self._vc_bounds_on = bool(on)
        self.update()

    def set_outlined_vc(self, vc: Optional[int]):
        """Outline this VC (the one chosen in County view / as a filter); None: no outline."""
        self._vc_outline = int(vc) if vc else None
        self.update()

    def set_extent(self, extent):
        self._extent = tuple(extent) if extent else gs.GB_LAND
        self._zoom = 1.0
        self._pan = QPointF(0, 0)
        self.update()

    def fit_to_gb(self):
        self.set_extent(gs.GB_LAND)

    def fit_to_squares(self):
        ext = gs.extent_of(self._squares)
        if ext:
            self.set_extent(ext)

    def vc_extent(self, vc: int, margin: float = 0.05):
        rings = self._vc_rings.get(int(vc))
        if not rings:
            return None
        es = [e for r in rings for e, _n in r]
        ns = [n for r in rings for _e, n in r]
        span = max(max(es) - min(es), max(ns) - min(ns))
        ce, cn = (min(es) + max(es)) / 2, (min(ns) + max(ns)) / 2
        half = span / 2 * (1 + margin)
        return ce - half, cn - half, ce + half, cn + half

    def fit(self) -> gs.MapFit:
        return gs.MapFit(self._extent, self.width(), self.height())

    def visible_extent(self):
        return gs.visible_extent(self.fit(), (self._pan.x(), self._pan.y()), self._zoom)

    # ---------------------------------------------------------------- painting
    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(_SEA_C))
        p.save()
        self._apply_pan_zoom(p)
        self.draw(p, self.fit(), k=1.0 / max(self._zoom, 1.0), zoom=self._zoom)
        p.restore()
        self._draw_overlay(p)
        p.end()

    def draw(self, p: QPainter, fit: gs.MapFit, k: float = 1.0, selected: bool = True,
             zoom: float = 1.0):
        """Basemap, grid, squares, VC boundaries, the selected VC's outline and the VC labels
        through `fit`. k scales line widths (print > 1). selected=False leaves out the clicked
        square's outline (the atlas page, L13/L31). zoom: the screen's zoom (the labels' scale
        rule). Labels are drawn in device pixels whatever the painter's zoom (vc_labels)."""
        land, coast = QColor(_LAND_C), QColor(_COAST_C)
        polys, vc_polys = self._polygons(fit)
        p.setPen(QPen(land, 0.8 * k))             # same-colour edge closes county slivers
        p.setBrush(QBrush(land))
        for poly in polys:
            p.drawPolygon(poly)
        hi = QColor(theme.MOSS)
        hi.setAlpha(40)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(hi))
        for vc in self._vc_highlight:             # VCs holding records: a light tint
            for poly in vc_polys.get(vc, ()):
                p.drawPolygon(poly)
        # R4: the coast is the land's sea-facing edges only (coast.py). Stroking every land
        # ring drew every district border of gb_outline.json (or, without it, every VC border
        # again) in the coast colour: the thin lines Wil saw under the VCs.
        if self._districts_on and self.has_districts():
            p.setPen(QPen(QColor(theme.LINE), 0.5 * k))
            p.setBrush(Qt.BrushStyle.NoBrush)
            for line in self._lines("districts", fit):
                p.drawPolyline(line)
        p.setPen(QPen(coast, 0.7 * k))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for line in self._lines("coast", fit):
            p.drawPolyline(line)
        self._draw_grid(p, fit, k)
        self._draw_squares(p, fit, k, selected)
        if self._vc_bounds_on and self._vc_rings:
            draw_boundaries(p, [self._lines("vc_inland", fit)], k)  # the coast is drawn already
        if self._vc_outline in vc_polys:
            draw_outline(p, vc_polys[self._vc_outline], k)
        if self._vc_labels_on and self._vc_rings:
            if self._label_pts is None:
                self._label_pts = label_points(self._vc_rings)
            span = max(fit.w, fit.h) / fit.scale / max(zoom, 1.0)   # metres across the view
            occupied, inside = self._label_tests(p, fit)
            draw_labels(p, fit, self._label_pts, self._vc_names, span,
                        bold_vc=self._vc_outline, occupied=occupied, inside=inside)

    def _label_tests(self, p: QPainter, fit):
        """(occupied, inside) for draw_labels, both taking DEVICE coordinates: does a rect
        cover a recorded square; is a point inside a VC. Same rule on screen and page."""
        inv, _ok = p.transform().inverted()
        size = self._size

        def to_en(pt):
            q = inv.map(pt)
            return fit.to_en(q.x(), q.y())

        def occupied(rect) -> bool:
            if not self._squares:
                return False
            e0, n1 = to_en(rect.topLeft())
            e1, n0 = to_en(rect.bottomRight())
            if (e1 - e0) * (n1 - n0) / (size * size) > 2500:    # far too many cells to look
                return False
            e = (int(e0) // size) * size
            while e < e1:
                n = (int(n0) // size) * size
                while n < n1:
                    if gs.square_for_point(e + 1, n + 1, size) in self._squares:
                        return True
                    n += size
                e += size
            return False

        def inside(vc, pt) -> bool:
            e, n = to_en(pt)
            return any(point_in_ring(e, n, r) for r in self._vc_rings.get(vc, ()))
        return occupied, inside

    def _polygons(self, fit):
        """Basemap rings projected through `fit`; the last projection is kept (paint is hot)."""
        key = (fit.extent, fit.w, fit.h, fit.x0, fit.y0)
        if self._poly_cache and self._poly_cache[0] == key:
            return self._poly_cache[1], self._poly_cache[2]

        def poly(ring):
            return QPolygonF([QPointF(*fit.to_px(e, n)) for e, n in ring])
        land = [poly(r) for r in self._land]
        vcs = {vc: [poly(r) for r in rings] for vc, rings in self._vc_rings.items()}
        self._poly_cache = (key, land, vcs)
        return land, vcs

    def _chains(self, name):
        """OSGB polylines: "coast" / "districts" (the land's sea-facing / inland edges) or
        "vc_inland" (VC borders that are not coast); split once per source (coast.py)."""
        if name == "vc_inland":
            return split_edges_cached(("vc", self._geojson, "300"),
                                      [r for rs in self._vc_rings.values() for r in rs])[1]
        if not self._land_source:
            return []
        coast, inland = split_edges_cached(self._land_source, self._land)
        return coast if name == "coast" else inland

    def _lines(self, name, fit):
        """_chains(name) projected through `fit` (kept until the fit changes)."""
        key = (fit.extent, fit.w, fit.h, fit.x0, fit.y0)
        hit = self._line_cache.get(name)
        if hit is None or hit[0] != key:
            hit = (key, [QPolygonF([QPointF(*fit.to_px(e, n)) for e, n in c])
                         for c in self._chains(name)])
            self._line_cache[name] = hit
        return hit[1]

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
                    x0, y0 = fit.to_px(e, max(minN, 0)); x1, y1 = fit.to_px(e, min(maxN, 1300000))
                    p.drawLine(QPointF(x0, y0), QPointF(x1, y1))
                e += step
            n = (int(minN) // step) * step
            while n <= maxN:
                if 0 <= n <= 1300000:
                    x0, y0 = fit.to_px(max(minE, 0), n); x1, y1 = fit.to_px(min(maxE, 700000), n)
                    p.drawLine(QPointF(x0, y0), QPointF(x1, y1))
                n += step

    def _square_rect(self, fit, label) -> Optional[QRectF]:
        b = gs.square_bounds(label)
        if not b:
            return None
        x0, y0 = fit.to_px(b[0], b[3])
        x1, y1 = fit.to_px(b[2], b[1])
        return QRectF(QPointF(x0, y0), QPointF(x1, y1))

    def _draw_squares(self, p, fit, k, selected: bool = True):
        edge = QColor(theme.INK)
        edge.setAlpha(110)
        edge_pen = QPen(edge, 0.4 * k)
        for label, sq in self._squares.items():
            r = self._square_rect(fit, label)
            if r is not None:
                # an outline on a square a few pixels wide hides its colour: fill only
                pen = edge_pen if r.width() >= 6 * k else Qt.PenStyle.NoPen
                if sq.get("fills"):
                    draw_split(p, r, sq["fills"], pen)
                else:
                    p.setPen(pen)
                    p.setBrush(QBrush(QColor(sq.get("fill") or theme.CLAY)))
                    p.drawRect(r)
        if self._selected and selected:
            r = self._square_rect(fit, self._selected)
            if r is not None:
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor(theme.INK), 2.0 * k))
                p.drawRect(r.adjusted(-1.5 * k, -1.5 * k, 1.5 * k, 1.5 * k))

    def _draw_overlay(self, p):
        f = p.font(); f.setPointSize(8); p.setFont(f)
        p.setPen(QColor(theme.MUTED))
        if self._message:
            p.drawText(QRectF(8, 6, self.width() - 16, 40),
                       int(Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap), self._message)
        if not self._land:
            p.drawText(8, self.height() - 22, "No coastline file found -- grid squares only.")
        p.drawText(8, self.height() - 8, "Scroll to zoom, drag to pan, double-click to reset.")

    # ---------------------------------------------------------------- clicks
    def _square_under(self, e) -> Optional[str]:
        pos = self._epos(e)
        return gs.square_at_pixel(self.fit(), pos.x(), pos.y(), self._size,
                                  (self._pan.x(), self._pan.y()), self._zoom)

    def mousePressEvent(self, e):
        self._press = self._epos(e)
        PanZoomMixin.mousePressEvent(self, e)

    def mouseReleaseEvent(self, e):
        start, self._press = self._press, None
        PanZoomMixin.mouseReleaseEvent(self, e)
        if start is None or e.button() != Qt.MouseButton.LeftButton:
            return
        pos = self._epos(e)
        if abs(pos.x() - start.x()) + abs(pos.y() - start.y()) > _CLICK_SLOP:
            return
        label = self._square_under(e)
        if label and label in self._squares:
            self.set_selected(label)
            self.square_clicked.emit(label)

    def mouseMoveEvent(self, e):
        PanZoomMixin.mouseMoveEvent(self, e)
        if self._drag is None:
            label = self._square_under(e)
            sq = self._squares.get(label) if label else None
            if sq:
                n = sq.get("count", 0)
                tip = sq.get("tip") or (f"{label}: {n} record{'s' if n != 1 else ''}"
                                        + (f" ({sq['years']})" if sq.get("years") else ""))
                QToolTip.showText(e.globalPosition().toPoint(), tip, self)
            else:
                QToolTip.hideText()

    # ---------------------------------------------------------------- atlas export
    def full_extent(self):
        """The whole extent of the view, whatever the zoom: all GB in National view, the
        whole vice-county in County view (set_extent)."""
        return self._extent
