"""The QtGraphs side of the Mapping tab's 3D view (Qt 6.12 QtGraphs; QtDataVisualization is
deprecated and not used).

A Q3DSurfaceWidgetItem (a QObject) is attached to a QQuickWidget; it holds one QSurface3DSeries
(heights in a QSurfaceDataProxy, x = easting, z = northing, y = height x exaggeration, the map
picture as its texture) and QCustom3DItem boxes for the record columns.
Nothing here is checked by tests with a GPU: the objects are built and fed, never rendered.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt

from shared.maps import terrain
from shared.maps._theme import theme

COLUMN_MESH = "#Cube"             # a Quick3D primitive; needs checking on a machine with a GPU
COLUMN_TALLEST = 0.10             # tallest column, as a fraction of the view width
TEXTURE_FLIP_V = True             # texture row 0 is taken to sit at the lowest z (south); flip if the drape is upside down
CAMERA_DEFAULT = (0.0, 35.0, 100.0)   # x rotation (0: seen from the south), y rotation, zoom
PAN_STEP = 0.08                   # an arrow key moves the view this much (the scene spans -1..1)


def horizontal_ratio(dx: float, dz: float) -> float:
    """QtGraphs' horizontalAspectRatio is x-axis length over z-axis length (Qt docs: "the ratio of
    the graph scaling between the x-axis and z-axis"): east-west span over north-south span.
    (Until 25 Oct 2026 this was inverted, and the scene came out as a thin wedge.)"""
    return max(dx, 1.0) / max(dz, 1.0)


def vertical_ratio(dx: float, dz: float, dy: float) -> float:
    """QtGraphs' aspectRatio is the longest horizontal axis over the height axis (Qt docs: "the
    ratio of the graph scaling between the longest axis on the horizontal plane and the y-axis"),
    so heights (already exaggerated) are to the same scale as distances. Kept within 1-1000: a
    flat area would otherwise be drawn as a sheet with no height at all."""
    return min(max(max(dx, dz, 1.0) / max(dy, 1.0), 1.0), 1000.0)


class Graphs3DUnavailable(Exception):
    """QtGraphs cannot be used here (not in the wheel, or no QtQuick widgets)."""


def load_qtgraphs():
    """(QtGraphs, Q3DSurfaceWidgetItem, QQuickWidget) or raise Graphs3DUnavailable."""
    try:
        import PySide6.QtGraphs as g
        from PySide6.QtGraphsWidgets import Q3DSurfaceWidgetItem
        from PySide6.QtQuickWidgets import QQuickWidget
    except Exception as e:
        raise Graphs3DUnavailable(f"3D graphs are not available in this installation ({e}).")
    return g, Q3DSurfaceWidgetItem, QQuickWidget


class Scene3D:
    """Owns the QQuickWidget (`.widget`) and the surface item; fed with a Heights and a drape."""

    def __init__(self, parent=None, on_error=None):
        """`on_error(text)` is called when Qt Quick reports a scene graph failure (no usable GPU /
        driver); it is connected before anything else so Qt does not end the application."""
        self.g, item_cls, quick = load_qtgraphs()
        self._on_error = on_error
        self.failed = None
        try:
            self.widget = quick(parent)
            self.widget.sceneGraphError.connect(self._scene_error)
            self.widget.setResizeMode(quick.ResizeMode.SizeRootObjectToView)
            self.item = item_cls()
            self.item.setWidget(self.widget)
            self.proxy = self.g.QSurfaceDataProxy()
            self.series = self.g.QSurface3DSeries(self.proxy)
            self.series.setShading(self.g.QSurface3DSeries.Shading.Smooth)
            try:    # the surface only: a wireframe over hundreds of cells hides the draped map
                self.series.setDrawMode(self.g.QSurface3DSeries.DrawFlag.DrawSurface)
            except Exception:
                pass
            self.item.addSeries(self.series)
        except Exception as e:
            w = self.__dict__.get("widget")
            if w is not None:           # a half-built widget must not stay on the window: no calls on it
                w.deleteLater()
            raise Graphs3DUnavailable(f"the 3D scene could not be created ({e}).")
        self._columns = []
        self.heights = None
        self.exaggeration = 1.0
        try:    # right-drag moves the view (Qt 6.12; left-drag still rotates, the wheel zooms)
            self.item.setPanEnabled(True)
            self.item.setPanButton(Qt.MouseButton.RightButton)
        except Exception:
            pass
        for axis in (self.item.axisX(), self.item.axisY(), self.item.axisZ()):
            axis.setLabelsVisible(False)
            axis.setTitleVisible(False)
        self.reset_camera()

    def _scene_error(self, *args):
        """sceneGraphError(error, message): remember it and tell the window."""
        text = str(args[-1]) if args else "unknown error"
        self.failed = text
        if self._on_error:
            self._on_error(f"The 3D display failed on this computer's graphics ({text}).")

    def apply_theme(self, background, text):
        """Plain background and no grid, from the app theme (hex strings)."""
        from PySide6.QtGui import QColor
        try:
            th = self.item.activeTheme() or self.g.QGraphsTheme()
            th.setBackgroundColor(QColor(background))
            th.setLabelTextColor(QColor(text))
            th.setGridVisible(False)
            self.item.setActiveTheme(th)
        except Exception:
            pass

    def reset_camera(self):
        from PySide6.QtGui import QVector3D
        x, y, z = CAMERA_DEFAULT
        self.item.setCameraXRotation(x)
        self.item.setCameraYRotation(y)
        self.item.setCameraZoomLevel(z)
        self.item.setCameraTargetPosition(QVector3D(0.0, 0.0, 0.0))

    def pan(self, east: float, north: float):
        """Move the view: `east`, `north` in steps (an arrow key is 1). The target stays within
        the scene (Qt clamps it to -1..1). Screen-up is north when seen from the south (x
        rotation 0); north is +z in the scene."""
        from PySide6.QtGui import QVector3D
        t = self.item.cameraTargetPosition()
        self.item.setCameraTargetPosition(QVector3D(
            max(-1.0, min(1.0, t.x() + east * PAN_STEP)), t.y(),
            max(-1.0, min(1.0, t.z() + north * PAN_STEP))))

    def set_texture(self, image):
        self.series.setTexture(image.flipped(Qt.Orientation.Vertical) if TEXTURE_FLIP_V else image)

    def set_heights(self, heights, exaggeration):
        """(Re)fill the surface; also the axes and aspect so the scene is to scale."""
        self.heights, self.exaggeration = heights, float(exaggeration)
        e0, n0, e1, n1 = heights.extent
        c = heights.cell_m
        y = (heights.grid[::-1] * self.exaggeration).astype(np.float32)   # rows south -> north
        ny, nx = y.shape
        self.proxy.resetArrayNp(e0 + c / 2, c, n0 + c / 2, c, np.ascontiguousarray(y))
        top = max(float(y.max()), 1.0)
        self.item.axisX().setRange(e0 + c / 2, e1 - c / 2)
        self.item.axisZ().setRange(n0 + c / 2, n1 - c / 2)
        low = min(0.0, float(y.min()))        # ground below sea level is not clipped
        self.item.axisY().setRange(low, top)
        self.item.setHorizontalAspectRatio(horizontal_ratio(e1 - e0 - c, n1 - n0 - c))
        self.item.setAspectRatio(vertical_ratio(e1 - e0 - c, n1 - n0 - c, top - low))

    def set_columns(self, squares, on):
        """Boxes standing on the recorded squares (height proportional to the count)."""
        from PySide6.QtGui import QColor, QImage, QQuaternion, QVector3D
        for c in self._columns:
            self.item.removeCustomItem(c)
        self._columns = []
        h = self.heights
        if not on or h is None or not squares:
            return
        cols = terrain.columns_for_squares(squares, h.grid, h.extent, h.cell_m, detail=True)
        if not cols:
            return
        e0, n0, e1, n1 = h.extent
        dx, dz = e1 - e0, n1 - n0
        low = min(0.0, float(h.grid.min()) * self.exaggeration)
        top = max(float(h.grid.max()) * self.exaggeration, 1.0) - low      # the height axis span
        most = max(c[3] for c in cols)
        for e, n, ground, count, label, size in cols:
            height = COLUMN_TALLEST * max(dx, dz) * count / most
            tex = QImage(1, 1, QImage.Format.Format_RGB32)
            tex.fill(QColor((squares[label] or {}).get("fill") or theme.CLAY))
            item = self.g.QCustom3DItem(
                COLUMN_MESH, QVector3D(e, ground * self.exaggeration + height / 2, n),
                QVector3D(size * 0.6 / dx, height / top, size * 0.6 / dz), QQuaternion(), tex)
            self.item.addCustomItem(item)
            self._columns.append(item)

    def render_image(self, size):
        """The scene as a QImage of `size` (needs a GPU), or None."""
        try:
            img = self.item.renderToImage(0, size)
        except Exception:
            return None
        return img if img is not None and not img.isNull() else None
