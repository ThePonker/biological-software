"""Native grid-square distribution map: the Mapping tab's map (backlog H1, H3-H5).

Built from the Data Entry map parts in this package: the same vector GB basemap (complete
coastline from data/maps/gb_outline.json, else the BRC vice-county polygons), the same
palette, and the same scroll-zoom / drag-pan. On top it draws hectad / tetrad / monad
squares as polygons (geometry in grid_squares.py), reports the square under a click, and
renders the current view to a print-resolution PNG (an atlas page).

No WebEngine, no tiles, no internet. Display only: it never touches a database.
"""
from __future__ import annotations

from datetime import date
from typing import Dict, Optional, Sequence, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QToolTip, QWidget

from shared.maps import grid_squares as gs
from shared.maps._theme import theme
from shared.maps.panzoom import PanZoomMixin
from shared.maps.species_dist_map import (_COAST_C, _GRID10_C, _GRID100_C, _LAND_C, _SEA_C,
                                          _VCLINE_C, _load_gb_outline)
from shared.maps.vc_map import load_vc_polygons

_CLICK_SLOP = 4          # px of movement still counted as a click, not a drag


class GridMap(PanZoomMixin, QWidget):
    """GB basemap with coloured grid squares. Scroll to zoom, drag to pan, double-click resets.

    Signals:
        square_clicked(str)   label of a square holding records, when clicked
    """

    square_clicked = Signal(str)

    def __init__(self, geojson_path: Optional[str] = None, maps_dir: Optional[str] = None,
                 parent=None):
        super().__init__(parent)
        land, _b = _load_gb_outline(maps_dir) if maps_dir else ({}, None)
        vc_rings, _b = load_vc_polygons(geojson_path) if geojson_path else ({}, None)
        if not land and geojson_path:
            land, _b = load_vc_polygons(geojson_path, tol=100.0)
        self._land = [ring for rings in land.values() for ring in rings]
        self._vc_rings: Dict[int, list] = vc_rings
        self._extent = gs.GB_LAND
        self._size = gs.HECTAD
        self._squares: Dict[str, dict] = {}       # label -> {count, fill, ...}
        self._selected: Optional[str] = None
        self._vc_highlight: set = set()
        self._message = ""
        self._press = None
        self._poly_cache = None
        self._init_panzoom(True)
        self.setMouseTracking(True)
        self.setMinimumSize(300, 360)

    # ---------------------------------------------------------------- data in
    def has_basemap(self) -> bool:
        return bool(self._land)

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
        self.draw(p, self.fit(), k=1.0 / max(self._zoom, 1.0))
        p.restore()
        self._draw_overlay(p)
        p.end()

    def draw(self, p: QPainter, fit: gs.MapFit, k: float = 1.0):
        """Basemap, grid and squares through `fit`. k scales line widths (print > 1)."""
        land, coast = QColor(_LAND_C), QColor(_COAST_C)
        polys, vc_polys = self._polygons(fit)
        p.setPen(QPen(land, 0.8 * k))
        p.setBrush(QBrush(land))
        for poly in polys:
            p.drawPolygon(poly)
        hi = QColor(theme.MOSS)
        hi.setAlpha(40)
        p.setPen(QPen(QColor(_VCLINE_C), 0.5 * k))
        for vc, vpolys in vc_polys.items():
            p.setBrush(QBrush(hi) if vc in self._vc_highlight else Qt.BrushStyle.NoBrush)
            for poly in vpolys:
                p.drawPolygon(poly)
        p.setPen(QPen(coast, 0.7 * k))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for poly in polys:
            p.drawPolyline(poly)
        self._draw_grid(p, fit, k)
        self._draw_squares(p, fit, k)

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

    def _draw_squares(self, p, fit, k):
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
        if self._selected:
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
    def render_sheet(self, title: str, subtitle: str = "",
                     legend: Sequence[Tuple[str, str]] = (), footer: str = "",
                     paper: str = "A4", dpi: int = 300, extent=None) -> QImage:
        """The current view as an atlas page: title, map, legend and credits, at `dpi`."""
        if extent is None:   # what is on screen; unzoomed, the whole chosen extent
            extent = self.visible_extent() if self._zoom > 1.0 else self._extent
        ext = extent
        landscape = (ext[2] - ext[0]) > 1.2 * (ext[3] - ext[1])
        w, h = gs.print_size_px(paper, dpi, landscape)
        img = QImage(w, h, QImage.Format.Format_RGB32)
        img.setDotsPerMeterX(gs.dots_per_metre(dpi))
        img.setDotsPerMeterY(gs.dots_per_metre(dpi))
        img.fill(QColor("#ffffff"))
        mm = dpi / 25.4
        k = dpi / 96.0
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        margin = 12 * mm
        p.setPen(QColor(theme.INK))
        p.setFont(_font(16, bold=True, italic=True))
        p.drawText(QRectF(margin, margin, w - 2 * margin, 10 * mm),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), title)
        p.setFont(_font(9))
        p.setPen(QColor(theme.MUTED))
        p.drawText(QRectF(margin, margin + 10 * mm, w - 2 * margin, 7 * mm),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), subtitle)
        top, bottom = margin + 20 * mm, h - margin - 22 * mm
        box = QRectF(margin, top, w - 2 * margin, bottom - top)
        p.fillRect(box, QColor(_SEA_C))
        p.save()
        p.setClipRect(box)
        self.draw(p, gs.MapFit(ext, box.width(), box.height(), pad=0, x0=box.x(), y0=box.y()), k)
        p.restore()
        p.setPen(QPen(QColor(theme.LINE), 0.8 * k))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(box)
        self._draw_legend(p, legend, margin, bottom + 4 * mm, mm, k, w - margin)
        p.setFont(_font(7))
        p.setPen(QColor(theme.MUTED))
        credit = (footer + "   " if footer else "") + \
            ("Vice-county boundaries: BRC. " if self._vc_rings else "") + \
            f"Produced {date.today():%d %B %Y} with Observatum."
        p.drawText(QRectF(margin, h - margin - 6 * mm, w - 2 * margin, 6 * mm),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), credit)
        p.end()
        return img

    @staticmethod
    def _draw_legend(p, legend, x, y, mm, k, right=None):
        """Swatches in a row, wrapping onto a second row (y + 6 mm) past `right`."""
        p.setFont(_font(8))
        x0 = x
        for colour, label in legend:
            need = 5.5 * mm + p.fontMetrics().horizontalAdvance(label)
            if right is not None and x > x0 and x + need > right:
                x, y = x0, y + 6 * mm
            sw = QRectF(x, y, 4 * mm, 4 * mm)
            if isinstance(colour, (tuple, list)):       # a split (overlap) swatch
                draw_split(p, sw, colour, QPen(QColor(theme.INK), 0.4 * k))
            else:
                p.setPen(QPen(QColor(theme.INK), 0.4 * k))
                p.setBrush(QBrush(QColor(colour)))
                p.drawRect(sw)
            p.setPen(QColor(theme.INK))
            text_w = p.fontMetrics().horizontalAdvance(label)
            p.drawText(QRectF(x + 5.5 * mm, y - 1 * mm, text_w + 2 * mm, 6 * mm),
                       int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), label)
            x += 5.5 * mm + text_w + 8 * mm


def draw_split(p: QPainter, r: QRectF, colours, pen):
    """A square shared by several taxa: two colours as diagonal halves (upper left, lower
    right), three or more as equal upright stripes; then the outline (pen) round it all."""
    cols = [QColor(c) for c in colours] or [QColor(theme.CLAY)]
    p.setPen(Qt.PenStyle.NoPen)
    if len(cols) == 2:
        tl, tr, bl, br = r.topLeft(), r.topRight(), r.bottomLeft(), r.bottomRight()
        p.setBrush(QBrush(cols[0]))
        p.drawPolygon(QPolygonF([tl, tr, bl]))
        p.setBrush(QBrush(cols[1]))
        p.drawPolygon(QPolygonF([tr, br, bl]))
    else:
        w = r.width() / len(cols)
        for i, c in enumerate(cols):
            p.setBrush(QBrush(c))
            p.drawRect(QRectF(r.x() + i * w, r.y(), w, r.height()))
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(r)


def _font(pt: int, bold: bool = False, italic: bool = False) -> QFont:
    f = QFont()
    f.setPointSize(pt)
    f.setBold(bold)
    f.setItalic(italic)
    return f

