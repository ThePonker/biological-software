"""Home > Year list: a small line chart (QPainter, no matplotlib) of the cumulative number of
species on the Personal year list at the end of each month, this year (solid, theme primary,
stops at the current month) and last year (thinner, theme secondary). Colours from theme();
sizes from shared/text_sizes."""
from typing import List, Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QSizePolicy, QWidget

from shared.text_sizes import font_px
from ...themes import theme

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def nice_max(v: int) -> int:
    """A round top for the y axis: four gridline steps of 1, 2, 5 or 10 x a power of ten."""
    q = -(-max(int(v), 4) // 4)
    base = 1
    while True:
        for k in (1, 2, 5):
            if q <= k * base:
                return 4 * k * base
        base *= 10


class YearListChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._this: List[Optional[int]] = [None] * 12
        self._last: List[Optional[int]] = [None] * 12
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_data(self, this: List[Optional[int]], last: List[Optional[int]]):
        self._this, self._last = list(this), list(last)
        self.update()

    def values(self):
        return self._this, self._last

    def paintEvent(self, _event):
        t = theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont(self.font())
        font.setPixelSize(font_px("caption"))
        p.setFont(font)
        fm = p.fontMetrics()
        top = max((v for v in (*self._this, *self._last) if v is not None), default=0)
        ymax = nice_max(top)
        left = fm.horizontalAdvance(str(ymax)) + 8
        plot = QRectF(left, fm.height() / 2 + 2, self.width() - left - fm.horizontalAdvance("Mmm") / 2 - 4,
                      self.height() - fm.height() * 1.6 - 6)
        grid, text = QColor(t.get("border")), QColor(t.get("text_secondary"))
        p.setPen(QPen(grid, 1))
        for i in range(5):                                   # light horizontal gridlines
            y = plot.bottom() - plot.height() * i / 4
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
        p.setPen(text)
        for i in range(5):
            y = plot.bottom() - plot.height() * i / 4
            p.drawText(QRectF(0, y - fm.height() / 2, left - 5, fm.height()),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, str(ymax * i // 4))
        step = plot.width() / 11
        for m, name in enumerate(MONTHS):
            x = plot.left() + step * m
            p.drawText(QRectF(x - step / 2, plot.bottom() + 3, step, fm.height()),
                       Qt.AlignmentFlag.AlignCenter, name[0] if step < fm.horizontalAdvance("Mmm") + 2 else name)

        def line(values, colour, width):
            pts = [QPointF(plot.left() + step * m, plot.bottom() - plot.height() * v / ymax)
                   for m, v in enumerate(values) if v is not None]
            p.setPen(QPen(QColor(colour), width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                          Qt.PenJoinStyle.RoundJoin))
            p.setBrush(Qt.BrushStyle.NoBrush)
            if len(pts) > 1:
                p.drawPolyline(QPolygonF(pts))
            return pts

        line(self._last, t.get("secondary"), 1.2)
        pts = line(self._this, t.get("primary"), 2.4)
        if pts:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(t.get("primary")))
            p.drawEllipse(pts[-1], 3.5, 3.5)
        p.end()
