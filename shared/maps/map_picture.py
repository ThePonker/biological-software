"""The Mapping tab's map is drawn into one picture and panned by moving it (18 Oct 2026; Wil's
timings: every pan step re-rendered the whole background, 150-190 ms on the GB view, and each
repaint still redrew the squares, the VC outline and the labels, 60-220 ms).

The picture holds everything but the clicked square's outline: land .. districts, the recorded
squares, the selected VC's outline and the VC labels. It covers the view plus a margin (half a
view each side, less when the view is large) at the zoom it was drawn at, so a pan step only
blits it at an offset ("pan blit" in BIOSOFT_MAP_TIMING=1). It is drawn again ("re-render")
when the view would leave the margin, the zoom changes or anything drawn in it changes.
While the wheel is turning the saved picture is drawn scaled (a soft preview) and the sharp
picture follows SETTLE_MS after the last wheel event. The clicked square's outline is drawn
live over the picture. The atlas page does not use any of this (render_sheet -> draw()).
Also here: the warm-up started when the map is first shown (map_warmup.py).
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QTimer
from PySide6.QtGui import QColor, QPainter, QPixmap

from shared.maps import layers
from shared.maps.map_timing import timed
from shared.maps.map_warmup import WarmUp, warm_steps
from shared.maps.species_dist_map import _SEA_C

MARGIN = 0.5                # of the view, each side (halved, then none, for a huge picture)
MAX_PIXELS = 36_000_000     # the most a picture may hold (device pixels)
SETTLE_MS = 200             # the sharp picture follows the last wheel event by this long


class _Picture:
    def __init__(self, static, zoom, pan, mx, my, pm):
        self.static, self.zoom, self.pan, self.mx, self.my, self.pm = static, zoom, pan, mx, my, pm


class StaticPictureMixin:
    """For GridMap: uses its fit(), draw(), _fit_key(), _apply_pan_zoom(), _draw_selected_outline()."""

    def _init_picture(self):
        self._pic = None
        self.picture_renders = 0                 # how many times the picture was drawn (tests)
        self._zoom_timer = QTimer(self)
        self._zoom_timer.setSingleShot(True)
        self._zoom_timer.setInterval(SETTLE_MS)
        self._zoom_timer.timeout.connect(self.update)
        self._warm = None

    # ---------------------------------------------------------------- the picture
    def _static_key(self, fit):
        """Everything the picture depends on except the zoom and the pan."""
        return (self._fit_key(fit), self.devicePixelRatioF(), self.width(), self.height(),
                frozenset(self._layers_on), self._districts_on, self._vc_bounds_on,
                frozenset(self._vc_highlight), layers.saved_colours(), self._sq_ver, self._size,
                self._square_opacity, self._vc_labels_on, self._vc_outline)

    def _margins(self, dpr: float):
        if self._zoom <= 1.0:                    # at 1x the map cannot be panned
            return 0, 0
        w, h = self.width(), self.height()
        for f in (MARGIN, MARGIN / 2):
            mx, my = round(w * f), round(h * f)
            if (w + 2 * mx) * (h + 2 * my) * dpr * dpr <= MAX_PIXELS:
                return mx, my
        return 0, 0

    def _render_picture(self, fit, static) -> _Picture:
        dpr = self.devicePixelRatioF()
        mx, my = self._margins(dpr)
        pm = QPixmap(round((self.width() + 2 * mx) * dpr), round((self.height() + 2 * my) * dpr))
        pm.setDevicePixelRatio(dpr)
        pm.fill(QColor(_SEA_C))
        q = QPainter(pm)
        q.setRenderHint(QPainter.RenderHint.Antialiasing)
        q.translate(mx, my)
        self._apply_pan_zoom(q)
        self._fast_fill = True                   # polygon fills not antialiased (map_layers.py)
        try:
            with timed("paint", "re-render"):
                self.draw(q, fit, k=1.0 / max(self._zoom, 1.0), selected=False, zoom=self._zoom)
        finally:
            self._fast_fill = False
        q.end()
        self.picture_renders += 1
        return _Picture(static, self._zoom, QPointF(self._pan), mx, my, pm)

    def _blit_offset(self, pic: _Picture):
        """Where the picture's top left goes (whole device pixels), or None when the view
        has left its margin."""
        dpr = self.devicePixelRatioF()
        dx = round((self._pan.x() - pic.pan.x()) * dpr) / dpr
        dy = round((self._pan.y() - pic.pan.y()) * dpr) / dpr
        if abs(dx) > pic.mx or abs(dy) > pic.my:
            return None
        return QPointF(dx - pic.mx, dy - pic.my)

    def _draw_preview(self, p: QPainter, pic: _Picture):
        """The saved picture scaled to the zoom now (soft), while the wheel is turning."""
        p.fillRect(self.rect(), QColor(_SEA_C))
        r = self._zoom / pic.zoom
        p.save()
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.translate(self._pan)
        p.scale(r, r)
        p.translate(-pic.pan.x(), -pic.pan.y())
        p.drawPixmap(QPointF(-pic.mx, -pic.my), pic.pm)
        p.restore()

    def _paint_map(self, p: QPainter):
        """The picture (blitted, previewed or drawn again), then the clicked square's outline."""
        fit = self.fit()
        static = self._static_key(fit)
        pic = self._pic
        same = pic is not None and pic.static == static
        pos = self._blit_offset(pic) if same and pic.zoom == self._zoom else None
        if pos is not None:
            with timed("paint", "pan blit"):
                p.drawPixmap(pos, pic.pm)
        elif same and self._zoom_timer.isActive():
            with timed("paint", "zoom preview"):
                self._draw_preview(p, pic)
        else:
            self._pic = self._render_picture(fit, static)
            p.drawPixmap(self._blit_offset(self._pic), self._pic.pm)
        if self._selected:
            p.save()
            self._apply_pan_zoom(p)
            self._draw_selected_outline(p, fit, 1.0 / max(self._zoom, 1.0))
            p.restore()

    # ---------------------------------------------------------------- wheel and warm-up
    def wheelEvent(self, e):
        old = self._zoom
        super().wheelEvent(e)
        if self._zoom != old:
            self._zoom_timer.start()             # restarted on each event

    def showEvent(self, e):
        super().showEvent(e)
        if self._warm is None:
            self._warm = WarmUp(warm_steps(self), self)
            self._warm.start()
