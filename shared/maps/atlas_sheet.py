"""The atlas page of the Mapping tab's map (H5): split out of grid_map.py (R9, 11 Oct 2026)
to keep that file under 400 lines. A mixin for GridMap: it uses the map's _extent, _zoom,
_squares, _vc_rings, visible_extent(), full_extent() and draw().

An A4 page at 300 dpi: title, subtitle, the map (the full extent, the current view or a
given box), legend and credits. sheet_view() gives the box the page's map really shows, so
the Mapping tab can count the squares and records in view for the footer (R9-6).
"""
from __future__ import annotations

from datetime import date
from typing import Sequence, Tuple

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPen, QPolygonF

from shared.maps import grid_squares as gs
from shared.maps._theme import theme
from shared.maps.species_dist_map import _SEA_C


# R4: gb_outline.json is the 2013 ONS local-authority districts (martinjc/UK-GeoJSON, whose
# README: "Contains Ordnance Survey, Office of National Statistics ... data. (c) Crown copyright
# and database right. Data licensed under the terms of the Open Government Licence").
COAST_CREDIT = ("Coastline: ONS boundaries, contains OS data \u00a9 Crown copyright and database "
                "right, Open Government Licence v3.0.")


class AtlasSheetMixin:
    """render_sheet / sheet_view / squares_in for GridMap."""

    def resolve_extent(self, extent=None):
        """An OSGB box from "full" / None (the whole view), "current" (on screen) or a box."""
        if extent is None or extent == "full":
            return self.full_extent()
        if extent == "current":
            return self.visible_extent() if self._zoom > 1.0 else self._extent
        return tuple(extent)

    @staticmethod
    def _sheet_size(ext, paper: str, dpi: int):
        landscape = (ext[2] - ext[0]) > 1.2 * (ext[3] - ext[1])
        w, h = gs.print_size_px(paper, dpi, landscape)
        return w, h, landscape

    @staticmethod
    def _sheet_box(w: int, h: int, dpi: int) -> QRectF:
        """The map's box on the page: under the title, above the legend and credits."""
        mm = dpi / 25.4
        margin = 12 * mm
        top, bottom = margin + 20 * mm, h - margin - 22 * mm
        return QRectF(margin, top, w - 2 * margin, bottom - top)

    def sheet_view(self, extent=None, paper: str = "A4", dpi: int = 300):
        """(the extent asked for, the OSGB box the page's map really shows). The page's box
        has its own shape, so it shows a little more than the extent one way (R9-6)."""
        ext = self.resolve_extent(extent)
        w, h, _l = self._sheet_size(ext, paper, dpi)
        box = self._sheet_box(w, h, dpi)
        fit = gs.MapFit(ext, box.width(), box.height(), pad=0)
        e0, n1 = fit.to_en(0.0, 0.0)
        e1, n0 = fit.to_en(box.width(), box.height())
        return ext, (e0, n0, e1, n1)

    def squares_in(self, box) -> list:
        """Labels of the mapped squares that show (wholly or in part) inside an OSGB box."""
        e0, n0, e1, n1 = box
        out = []
        for label in self._squares:
            b = gs.square_bounds(label)
            if b and b[0] < e1 and b[2] > e0 and b[1] < n1 and b[3] > n0:
                out.append(label)
        return out

    def render_sheet(self, title: str, subtitle: str = "",
                     legend: Sequence[Tuple[str, str]] = (), footer: str = "",
                     paper: str = "A4", dpi: int = 300, extent=None) -> QImage:
        """An atlas page: title, map, legend and credits, at `dpi`. `extent`: an OSGB box,
        "full" / None (the whole view's extent, L14/L32: the default) or "current" (what is
        on screen after zooming and panning). The clicked square's outline is never drawn."""
        ext = self.resolve_extent(extent)
        w, h, landscape = self._sheet_size(ext, paper, dpi)
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
        box = self._sheet_box(w, h, dpi)
        bottom = box.bottom()
        p.fillRect(box, QColor(_SEA_C))
        p.save()
        p.setClipRect(box)
        self.draw(p, gs.MapFit(ext, box.width(), box.height(), pad=0, x0=box.x(), y0=box.y()), k,
                  selected=False)
        p.restore()
        p.setPen(QPen(QColor(theme.LINE), 0.8 * k))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(box)
        self._draw_legend(p, legend, margin, bottom + 4 * mm, mm, k, w - margin)
        p.setFont(_font(7))
        p.setPen(QColor(theme.MUTED))
        credit = self.credit_line(footer)
        # R4: two lines when it needs them (the coastline credit made it too long for one)
        p.drawText(QRectF(margin, h - margin - 10 * mm, w - 2 * margin, 10 * mm),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom
                       | Qt.TextFlag.TextWordWrap), credit)
        p.end()
        return img

    def credit_line(self, footer: str = "") -> str:
        """The page's last line(s): the footer, then the data credits for what is drawn."""
        return (footer + "   " if footer else "") + \
            ("Vice-county boundaries: BRC. " if self._vc_rings else "") + \
            (COAST_CREDIT + " " if self.has_districts() else "") + \
            f"Produced {date.today():%d %B %Y} with Observatum."

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

