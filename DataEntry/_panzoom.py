"""Scroll-to-zoom + drag-to-pan for pop-out maps (gated by self._zoomable).

Both mini-maps mix this in. It only activates when _init_panzoom(True) is called (pop-outs);
inline maps stay fixed. paintEvent wraps its map+dots drawing between p.save()/apply/restore,
so overlays (attribution) drawn afterwards stay put.
"""
from PySide6.QtCore import Qt, QPointF

_ZOOM_MIN = 1.0
_ZOOM_MAX = 8.0


class PanZoomMixin:
    def _init_panzoom(self, enabled):
        self._zoomable = enabled
        self._zoom = 1.0
        self._pan = QPointF(0, 0)
        self._drag = None
        if enabled:
            self.setCursor(Qt.CursorShape.OpenHandCursor)

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
        new = max(_ZOOM_MIN, min(_ZOOM_MAX, old * (1.25 ** step)))
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
