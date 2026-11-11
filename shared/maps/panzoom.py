"""Scroll-to-zoom + drag-to-pan for pop-out maps (gated by self._zoomable).

Moved from DataEntry/_panzoom.py (backlog H2, 9 Oct 2026); that name is now a shim.

Both mini-maps mix this in. It only activates when _init_panzoom(True) is called (pop-outs);
inline maps stay fixed. paintEvent wraps its map+dots drawing between p.save()/apply/restore,
so overlays (attribution) drawn afterwards stay put.
"""
from PySide6.QtCore import Qt, QPointF

_ZOOM_MIN = 1.0
_ZOOM_MAX = 8.0
CLOSEST_VIEW_M = 1000.0     # R18: the closest view is about 1 km across the shorter side


def zoom_limit(extent, floor=_ZOOM_MAX, size=None, pad=5.0):
    """The zoom limit for a map fitted to `extent` (e0, n0, e1, n1 in metres): the zoom at which
    the shorter side of the widget spans CLOSEST_VIEW_M, but never less than `floor`.
    With size=(w, h) in pixels the fit is worked out as grid_squares.MapFit does (equal aspect,
    `pad` px round); without it the extent's own shorter side is used: max(8, short_side_m / 1000).
    GB: ~640x, a vice-county: ~60x."""
    if not extent:
        return float(floor)
    ew, eh = abs(extent[2] - extent[0]), abs(extent[3] - extent[1])
    short = min(ew, eh)
    if size and min(size) > 2 * pad + 1 and ew > 0 and eh > 0:
        w, h = float(size[0]), float(size[1])
        scale = min((w - 2 * pad) / ew, (h - 2 * pad) / eh)        # px per metre at zoom 1
        short = min(w, h) / scale
    return max(float(floor), short / CLOSEST_VIEW_M)


class PanZoomMixin:
    def _init_panzoom(self, enabled, zoom_max=_ZOOM_MAX):
        """zoom_max: this widget's lowest limit; the real one is _zoom_limit() (R18)."""
        self._zoomable = enabled
        self._zoom_max = float(zoom_max)
        self._zoom = 1.0
        self._pan = QPointF(0, 0)
        self._drag = None
        if enabled:
            self.setCursor(Qt.CursorShape.OpenHandCursor)

    def _zoom_extent(self):
        """The extent the map is fitted to (e0, n0, e1, n1, metres); a widget overrides this."""
        return getattr(self, "_extent", None)

    def _zoom_limit(self):
        """How far this map may zoom: down to about 1 km across, from the current fitted extent."""
        try:
            return zoom_limit(self._zoom_extent(), getattr(self, "_zoom_max", _ZOOM_MAX),
                              (self.width(), self.height()))
        except (TypeError, ValueError, IndexError):
            return float(getattr(self, "_zoom_max", _ZOOM_MAX))

    def _apply_pan_zoom(self, p):
        if getattr(self, "_zoomable", False):
            p.translate(self._pan)
            p.scale(self._zoom, self._zoom)

    def _clamp_pan(self):
        w, h = float(self.width()), float(self.height())
        z = self._zoom
        minx = min(0.0, w - z * w)
        miny = min(0.0, h - z * h)
        x = max(minx, min(0.0, self._pan.x()))
        y = max(miny, min(0.0, self._pan.y()))
        self._pan = QPointF(x, y)

    def _epos(self, e):
        try:
            return e.position()
        except Exception:
            return QPointF(e.pos())

    def wheelEvent(self, e):
        if not getattr(self, "_zoomable", False):
            return
        old = self._zoom
        step = e.angleDelta().y() / 120.0
        new = max(_ZOOM_MIN, min(self._zoom_limit(), old * (1.25 ** step)))
        if new == old:
            return
        c = self._epos(e)
        # keep the point under the cursor fixed: s = pan + zoom*w
        self._pan = QPointF(c.x() - (c.x() - self._pan.x()) * (new / old),
                            c.y() - (c.y() - self._pan.y()) * (new / old))
        self._zoom = new
        self._clamp_pan()
        self.update()

    def mousePressEvent(self, e):
        if getattr(self, "_zoomable", False) and e.button() == Qt.MouseButton.LeftButton:
            self._drag = self._epos(e)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, e):
        if getattr(self, "_zoomable", False) and self._drag is not None:
            c = self._epos(e)
            self._pan = QPointF(self._pan.x() + (c.x() - self._drag.x()),
                                self._pan.y() + (c.y() - self._drag.y()))
            self._drag = c
            self._clamp_pan()
            self.update()

    def mouseReleaseEvent(self, e):
        if getattr(self, "_zoomable", False):
            self._drag = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mouseDoubleClickEvent(self, e):
        if getattr(self, "_zoomable", False):
            self._zoom = 1.0
            self._pan = QPointF(0, 0)
            self.update()
