"""The atlas page's extras panel (26 Oct 2026): short stat lines and the phenology chart,
drawn under the map with the page's fonts, theme() colours and mm/dpi scaling.

`extras` is an Extras: `lines` (already worded, see map_stats) and `months` (12 counts) with
its `chart_note`, or None for no chart. Nothing here touches the map, so a page with no extras
is unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen

from shared.maps._theme import theme
from shared.maps.map_stats import MONTH_INITIALS

CHART_W_MM = 78.0
CHART_H_MM = 25.0
GAP_MM = 6.0
MAX_FRACTION = 0.15          # the strip takes at most about this share of the map's height


@dataclass
class Extras:
    lines: List[str] = field(default_factory=list)
    months: Optional[Sequence[int]] = None
    chart_title: str = "Records by month"
    chart_note: str = ""

    def __bool__(self):
        return bool(self.lines) or self.months is not None


def _font(pt: int, bold: bool = False) -> QFont:
    f = QFont()
    f.setPointSize(pt)
    f.setBold(bold)
    return f


def _text_width_mm(w_px: float, mm: float, extras: Extras) -> float:
    margin = 12 * mm
    avail = (w_px - 2 * margin) / mm
    return avail - (CHART_W_MM + GAP_MM if extras.months is not None else 0)


def height_mm(extras: Optional[Extras], w_px: int, dpi: int, dev) -> float:
    """Millimetres the strip needs (0 for no extras): the taller of the chart and the wrapped
    text lines, measured with the page's own font and width."""
    if not extras:
        return 0.0
    mm = dpi / 25.4
    h = CHART_H_MM if extras.months is not None else 0.0
    if extras.lines:
        fm = QFontMetricsF(_font(8), dev)
        width = _text_width_mm(w_px, mm, extras) * mm
        text = "\n".join(extras.lines)
        r = fm.boundingRect(QRectF(0, 0, width, 10 ** 6),
                            int(Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap), text)
        h = max(h, r.height() / mm + len(extras.lines) * 1.2)
    return h + 3.0


def draw(p: QPainter, extras: Extras, x: float, y: float, w_px: float, mm: float, k: float):
    """Draw the strip with its top-left at (x, y); the page is w_px wide."""
    right = w_px - 12 * mm
    text_right = right
    if extras.months is not None:
        cw = CHART_W_MM * mm
        _chart(p, extras, QRectF(right - cw, y, cw, CHART_H_MM * mm), mm, k)
        text_right = right - cw - GAP_MM * mm
    if extras.lines:
        p.setFont(_font(8))
        p.setPen(QColor(theme.INK))
        y0 = y
        for line in extras.lines:
            fm = p.fontMetrics()
            r = fm.boundingRect(QRectF(x, y0, text_right - x, 10 ** 6).toRect(),
                                int(Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap), line)
            p.drawText(QRectF(x, y0, text_right - x, r.height()),
                       int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
                           | Qt.TextFlag.TextWordWrap), line)
            y0 += r.height() + 1.2 * mm


def _chart(p: QPainter, extras: Extras, box: QRectF, mm: float, k: float):
    """Bars of records per month with month initials under them, a title above and a small
    note ("n = ...") below."""
    months = list(extras.months)
    p.setFont(_font(8, bold=True))
    p.setPen(QColor(theme.INK))
    p.drawText(QRectF(box.x(), box.y(), box.width(), 4 * mm),
               int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), extras.chart_title)
    note_h, init_h, title_h = 3.2 * mm, 3.4 * mm, 4.2 * mm
    plot = QRectF(box.x(), box.y() + title_h, box.width(),
                  box.height() - title_h - init_h - note_h)
    top = max(months) if months and max(months) else 1
    slot = plot.width() / 12
    p.setPen(QPen(QColor(theme.LINE), 0.5 * k))
    p.drawLine(plot.bottomLeft(), plot.bottomRight())
    p.setFont(_font(7))
    for i, n in enumerate(months):
        bx = plot.x() + i * slot
        if n:
            bh = plot.height() * 0.88 * n / top
            bar = QRectF(bx + slot * 0.15, plot.bottom() - bh, slot * 0.7, bh)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(theme.MOSS))
            p.drawRect(bar)
            p.setPen(QColor(theme.INK))
            p.drawText(QRectF(bx - slot * 0.2, bar.top() - 3 * mm, slot * 1.4, 3 * mm),
                       int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom),
                       f"{n:,}")
        p.setPen(QColor(theme.MUTED))
        p.drawText(QRectF(bx, plot.bottom() + 0.4 * mm, slot, init_h),
                   int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
                   MONTH_INITIALS[i])
    p.setFont(_font(6))
    p.setPen(QColor(theme.MUTED))
    p.drawText(QRectF(box.x(), box.bottom() - note_h, box.width(), note_h),
               int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), extras.chart_note)
