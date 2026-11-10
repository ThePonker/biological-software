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
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetricsF, QImage, QPainter, QPen,
                           QPolygonF)

from shared.maps import extras_panel, layer_legend
from shared.maps import grid_squares as gs
from shared.maps._theme import theme
from shared.maps.layers import credit_lines
from shared.maps.species_dist_map import _SEA_C


# R4: gb_outline.json is the 2013 ONS local-authority districts (martinjc/UK-GeoJSON, whose
# README: "Contains Ordnance Survey, Office of National Statistics ... data. (c) Crown copyright
# and database right. Data licensed under the terms of the Open Government Licence").
COAST_CREDIT = ("Coastline: ONS boundaries, contains OS data \u00a9 Crown copyright and database "
                "right, Open Government Licence v3.0.")


MIN_RESERVE_MM = 22.0          # the least room under the map for the legend and credits


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
    def _sheet_box(w: int, h: int, dpi: int, reserve_mm: float = MIN_RESERVE_MM) -> QRectF:
        """The map's box on the page: under the title, above the legend and credits, which
        need `reserve_mm` above the bottom margin (more when there are many credits)."""
        mm = dpi / 25.4
        margin = 12 * mm
        top, bottom = margin + 20 * mm, h - margin - reserve_mm * mm
        return QRectF(margin, top, w - 2 * margin, bottom - top)

    def _reserve_mm(self, w: int, dpi: int, legend, footer: str, dev=None, layer_groups=()) -> float:
        """Millimetres under the map for the legend rows and the credit text, measured with the
        page's own fonts and width, so the credits never overlap the legend or the map."""
        if dev is None:
            dev = QImage(1, 1, QImage.Format.Format_RGB32)
            dev.setDotsPerMeterX(gs.dots_per_metre(dpi))
            dev.setDotsPerMeterY(gs.dots_per_metre(dpi))
        mm = dpi / 25.4
        margin = 12 * mm
        rows = self._legend_rows(legend, w, mm, dev)
        credit_h = QFontMetricsF(_font(7), dev).boundingRect(
            QRectF(0, 0, w - 2 * margin, 10 ** 6), int(Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap),
            self.credit_line(footer)).height()
        return (max(MIN_RESERVE_MM, credit_h / mm + 10 + (rows - 1) * 6)
                + layer_legend.rows_mm(layer_groups, dev, mm, w - 2 * margin))

    @staticmethod
    def _legend_rows(legend, w: int, mm: float, dev) -> int:
        """How many rows the squares' legend wraps onto (the same rule _draw_legend follows)."""
        fm8 = QFontMetricsF(_font(8), dev)
        margin = 12 * mm
        x0, right, x, rows = margin, w - margin, margin, 1
        for _c, label in legend:
            need = 5.5 * mm + fm8.horizontalAdvance(label)
            if x > x0 and x + need > right:
                x, rows = x0, rows + 1
            x += need + 8 * mm
        return rows

    def layer_legend_groups(self, box):
        """The background-layer legend for the ticked layers drawn in `box` (layer_legend.py)."""
        return layer_legend.build(self._maps_dir, self._layers_on, self._layer_files, box)

    def sheet_view(self, extent=None, paper: str = "A4", dpi: int = 300, legend=(), footer: str = "",
                   extras=None, layer_groups=()):
        """(the extent asked for, the OSGB box the page's map really shows). The page's box
        has its own shape, so it shows a little more than the extent one way (R9-6); pass the
        page's legend and footer to get the box when many credits make the map box shorter, and
        its extras (the panel under the map) when it has any."""
        ext = self.resolve_extent(extent)
        w, h, _l = self._sheet_size(ext, paper, dpi)
        reserve = (self._reserve_mm(w, dpi, legend, footer, layer_groups=layer_groups)
                   + self._extras_mm(extras, w, dpi))
        box = self._sheet_box(w, h, dpi, reserve)
        fit = gs.MapFit(ext, box.width(), box.height(), pad=0)
        e0, n1 = fit.to_en(0.0, 0.0)
        e1, n0 = fit.to_en(box.width(), box.height())
        return ext, (e0, n0, e1, n1)

    @staticmethod
    def _extras_mm(extras, w: int, dpi: int, dev=None) -> float:
        if not extras:
            return 0.0
        if dev is None:
            dev = QImage(1, 1, QImage.Format.Format_RGB32)
            dev.setDotsPerMeterX(gs.dots_per_metre(dpi))
            dev.setDotsPerMeterY(gs.dots_per_metre(dpi))
        return extras_panel.height_mm(extras, w, dpi, dev)

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
                     paper: str = "A4", dpi: int = 300, extent=None, extras=None,
                     layer_groups=()) -> QImage:
        """An atlas page: title, map, legend and credits, at `dpi`. `extent`: an OSGB box,
        "full" / None (the whole view's extent, L14/L32: the default) or "current" (what is
        on screen after zooming and panning). The clicked square's outline is never drawn.
        `extras`: an extras_panel.Extras (stat lines, phenology chart) drawn between the map
        and the legend; None or empty leaves the page exactly as it was. `layer_groups`: the
        background-layer legend (layer_legend.build), drawn under the squares' legend."""
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
        extras_mm = self._extras_mm(extras, w, dpi, img)
        reserve = self._reserve_mm(w, dpi, legend, footer, img, layer_groups) + extras_mm
        box = self._sheet_box(w, h, dpi, reserve)
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
        if extras:
            extras_panel.draw(p, extras, margin, bottom + 3 * mm, w, mm, k)
        legend_y = bottom + 4 * mm + extras_mm * mm
        self._draw_legend(p, legend, margin, legend_y, mm, k, w - margin)
        if layer_groups:
            rows = self._legend_rows(legend, w, mm, img)
            layer_legend.draw(p, layer_groups, margin, legend_y + rows * 6 * mm, mm, k, w - 2 * margin)
        p.setFont(_font(7))
        p.setPen(QColor(theme.MUTED))
        credit = self.credit_line(footer)
        # as many lines as the credits need (the box above was shortened to make room for them)
        credit_h = h - margin - bottom - 10 * mm
        p.drawText(QRectF(margin, h - margin - credit_h, w - 2 * margin, credit_h),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom
                       | Qt.TextFlag.TextWordWrap), credit)
        p.end()
        return img

    def credit_line(self, footer: str = "") -> str:
        """The page's last line(s): the footer, then the data credits for what is drawn: the OS
        line once if any layers-folder file is drawn, the credits and grid legends of the ticked
        Environment layers (layers.credits_for), the ONS one only while gb_outline.json is."""
        parts = ["Vice-county boundaries: BRC."] if self._vc_rings else []
        parts += credit_lines(self._maps_dir, self.layers_drawn())
        parts += [COAST_CREDIT] if self.outline_drawn() else []
        parts.append(f"Produced {date.today():%d %B %Y} with Observatum.")
        return (footer + "   " if footer else "") + " ".join(parts)

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

