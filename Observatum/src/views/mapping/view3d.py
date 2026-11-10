"""The Mapping tab's 3D view: a window showing the area on screen as a lit surface of OS Terrain 50
(or LiDAR) heights with the map draped over it. Controls: vertical exaggeration, columns for the
records, reset view, export a picture. Display only; never touches a database.

Since Round 16 (10 Nov 2026) the window runs in its OWN PROCESS (view3d_child.py, started by
view3d_launch.py): Qt Quick / the graphics driver can fail hard, and that must not take Observatum
down. open_view3d() here only checks the size and launches it. View3DWindow is what the child shows.

If QtGraphs cannot be used (or there are no heights) the window says so instead of failing.
"""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (QCheckBox, QFileDialog, QHBoxLayout, QLabel, QMessageBox,
                               QPushButton, QSlider, QVBoxLayout, QWidget)

from shared import crash_log
from shared.maps import terrain
from . import view3d_drape as drape
from . import view3d_launch
from . import view3d_scene as scene3d
from ...themes import theme

launch_view3d = view3d_launch.launch_view3d      # the name open_view3d (and the tests) use

WIDE_M = 25_000                  # wider than this: no 3D view, zoom in first (25 Oct 2026; was a
                                 # warning at 120 km, and England-wide views fell back to 5 km cells)
EX_MIN, EX_MAX = 1, 10
COLOUR_KEYS = ("background", "text_heading", "text_secondary", "surface")


def too_wide(extent) -> bool:
    return max(extent[2] - extent[0], extent[3] - extent[1]) > WIDE_M


def wide_message(extent) -> str:
    km = max(extent[2] - extent[0], extent[3] - extent[1]) / 1000
    return (f"The 3D view is for an area up to {WIDE_M // 1000} km across; this view is about "
            f"{km:,.0f} km across.\n\nZoom in on the area you want and press 3D view again.")


class View3DWindow(QWidget):
    """Top-level window built from the map widget and the extent to show. The child process gives it
    a stand-in for the map and the already-made `heights`, `drape_image`, `credits` and `colours`
    (background, text_heading, text_secondary, surface); otherwise they are made here."""

    def __init__(self, map_widget, extent, parent=None, heights=None, drape_image=None,
                 credits=None, colours=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle("3D view")
        self.resize(1100, 760)
        self._map = map_widget
        self._given = (heights, drape_image)
        self._credits = credits
        t = colours or {k: theme().get(k) for k in COLOUR_KEYS}
        self._colours = t
        self._extent = tuple(float(v) for v in extent)
        self._squares = dict(getattr(map_widget, "_squares", {}) or {})
        self._scene = None
        self._message = None
        self.heights = None
        self.setStyleSheet(f"background-color: {t.get('background')}; color: {t.get('text_heading')};")
        lay = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.ex_label = QLabel("Exaggeration")
        self.ex_slider = QSlider(Qt.Orientation.Horizontal)
        self.ex_slider.setRange(EX_MIN * 10, EX_MAX * 10)         # tenths
        self.ex_slider.setFixedWidth(180)
        self.ex_value = QLabel("")
        self.columns_check = QCheckBox("Columns for records")
        self.columns_check.setEnabled(bool(self._squares))
        self.reset_btn = QPushButton("Reset view")
        self.export_btn = QPushButton("Export image…")
        for w in (self.ex_label, self.ex_slider, self.ex_value, self.columns_check):
            bar.addWidget(w)
        bar.addStretch()
        bar.addWidget(self.reset_btn)
        bar.addWidget(self.export_btn)
        lay.addLayout(bar)
        self.body = QVBoxLayout()
        lay.addLayout(self.body, 1)
        self.hint = QLabel("Left-drag: turn  ·  Right-drag or arrow keys: move  ·  Wheel: zoom  ·  "
                           "Reset view: back to the start")
        self.hint.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 11px;")
        lay.addWidget(self.hint)
        self.status = QLabel("")
        self.status.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 11px;")
        lay.addWidget(self.status)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self._apply_exaggeration)
        self.ex_slider.valueChanged.connect(self._slider_moved)
        self.columns_check.toggled.connect(self._columns_toggled)
        self.reset_btn.clicked.connect(self._reset)
        self.export_btn.clicked.connect(self.export_image)
        self._add_pan_keys()
        self._build()

    # ------------------------------------------------------------------ building
    def _show_message(self, text):
        """Replace the 3D area with a message and disable the controls."""
        for w in (self.ex_slider, self.columns_check, self.reset_btn, self.export_btn):
            w.setEnabled(False)
        if self._scene is not None:      # no calls into a Qt Quick widget that has failed (2 Nov crash)
            w = self._scene.widget
            self._scene = None
            w.deleteLater()
        self._scene, self.heights = None, None
        if self._message is None:
            self._message = QLabel(text)
            self._message.setWordWrap(True)
            self._message.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.body.addWidget(self._message)
        else:
            self._message.setText(text)
        self.status.setText("")

    def _build(self):
        try:
            self._build_scene()
        except scene3d.Graphs3DUnavailable as e:
            crash_log.note("3D view: Qt Graphs unavailable", e)
            self._show_message(f"3D view is not available: {e}")
        except terrain.TerrainUnavailable as e:
            self._show_message(str(e))
        except Exception as e:     # BadZipFile, OSError, ValueError ... never out of the constructor
            crash_log.note("3D view could not be built", e)     # the traceback first, then the message
            self._show_message(f"The 3D view could not be built: {type(e).__name__}: {e}")

    def _build_scene(self):
        # heights and the drape first: nothing from Qt Quick exists until they are ready
        given_h, given_drape = self._given
        h = given_h if given_h is not None else terrain.heights_for_extent(self._extent)
        self.drape_image = given_drape if given_drape is not None else drape.make_drape(self._map, h.extent)
        ex = terrain.sensible_exaggeration(h.grid, h.extent)
        self.heights = h
        self._scene = scene3d.Scene3D(self, on_error=self._show_message)
        t = self._colours
        self._scene.apply_theme(t.get("background"), t.get("text_heading"))
        self.body.addWidget(self._scene.widget)
        self._scene.set_texture(self.drape_image)
        self.ex_slider.blockSignals(True)
        self.ex_slider.setValue(round(ex * 10))
        self.ex_slider.blockSignals(False)
        self._scene.set_heights(h, ex)
        self._show_exaggeration()
        self.status.setText(f"Heights: {h.source_label}; cells {h.cell_m:g} m "
                            f"({h.grid.shape[1]} x {h.grid.shape[0]}).")

    def exaggeration(self) -> float:
        return self.ex_slider.value() / 10.0

    def _show_exaggeration(self):
        self.ex_value.setText(f"{self.exaggeration():g}x")

    def _slider_moved(self, _v):
        self._show_exaggeration()
        self._timer.start()

    def _apply_exaggeration(self):
        if self._scene and self.heights:
            self._scene.set_heights(self.heights, self.exaggeration())
            self._scene.set_columns(self._squares, self.columns_check.isChecked())

    def _columns_toggled(self, on):
        if self._scene:
            self._scene.set_columns(self._squares, on)

    def _reset(self):
        if self._scene:
            self._scene.reset_camera()

    def _add_pan_keys(self):
        """The arrow keys move the view (as right-drag does). Shortcuts on the window, so they
        work whichever part of it has the keyboard (the 3D widget would take a key press)."""
        self._pan_keys = []
        for key, step in ((Qt.Key.Key_Left, (-1, 0)), (Qt.Key.Key_Right, (1, 0)),
                          (Qt.Key.Key_Up, (0, 1)), (Qt.Key.Key_Down, (0, -1))):
            sc = QShortcut(QKeySequence(key), self)
            sc.setContext(Qt.ShortcutContext.WindowShortcut)
            sc.activated.connect(lambda s=step: self.pan(*s))
            self._pan_keys.append(sc)

    def pan(self, east: float, north: float):
        if self._scene:
            self._scene.pan(east, north)

    # ------------------------------------------------------------------ export
    def export_image(self):
        if not (self._scene and self.heights):
            return
        path, _f = QFileDialog.getSaveFileName(self, "Export 3D image", "3d_view.png", "PNG (*.png)")
        if not path:
            return
        img = self._scene.render_image(QSize(*drape.EXPORT_SIZE))
        if img is None:
            img = self._scene.widget.grabFramebuffer()
        if img is None or img.isNull():
            QMessageBox.warning(self, "3D view", "The picture could not be made (no 3D rendering here).")
            return
        h = self.heights
        t = self._colours
        credits = self._credits if self._credits is not None else drape.export_credits(self._map, h.source_label)
        out = drape.compose_export(img, drape.footer_lines(h.extent, self.exaggeration(),
                                                           h.source_label, h.cell_m, credits),
                                   t.get("surface"), t.get("text_heading"))
        if not out.save(path, "PNG"):
            QMessageBox.warning(self, "3D view", f"Could not save {path}.")


def open_view3d(current, map_widget, extent=None, parent=None):
    """Open the 3D view for the map's visible extent in its own process; one at a time (a previous
    one is closed). A view wider than WIDE_M is refused with a message. Returns the handle of the
    new view (None when it could not be started), or `current` when refused."""
    ext = extent or map_widget.visible_extent()
    if too_wide(ext):
        QMessageBox.information(parent, "3D view", wide_message(ext))
        return current
    if current is not None:
        try:
            current.close()
            current.deleteLater()
        except RuntimeError:
            pass
    QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        return launch_view3d(map_widget, ext, parent)
    finally:
        QGuiApplication.restoreOverrideCursor()
