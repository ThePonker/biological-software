"""25 Oct 2026: the 3D view came out as a thin wedge on Wil's PC (QtGraphs' two aspect ratios were
set the wrong way round) and was opened on most of England (5 km cells). The ratios follow Qt's
definitions now, and a view wider than 25 km is refused with a message. No GPU needed."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from Observatum.src.views.mapping import view3d, view3d_scene  # noqa: E402


def test_horizontal_ratio_is_east_west_over_north_south():
    assert view3d_scene.horizontal_ratio(20000, 10000) == 2.0      # wide view: x twice z
    assert view3d_scene.horizontal_ratio(10000, 20000) == 0.5


def test_vertical_ratio_is_longest_horizontal_over_height_and_bounded():
    assert view3d_scene.vertical_ratio(25000, 20000, 500) == 50.0
    assert view3d_scene.vertical_ratio(25000, 20000, 1) == 1000.0     # flat: capped
    assert view3d_scene.vertical_ratio(100, 100, 5000) == 1.0         # never taller than wide


def test_views_over_25_km_are_refused_with_the_size(monkeypatch):
    shown = []
    monkeypatch.setattr(view3d.QMessageBox, "information", lambda *a: shown.append(a[2]))

    class Map:
        def visible_extent(self):
            return (400000.0, 200000.0, 700000.0, 400000.0)       # 300 km

    sentinel = object()
    assert view3d.open_view3d(sentinel, Map()) is sentinel
    assert shown and "25 km" in shown[0] and "300 km" in shown[0]
    assert not view3d.too_wide((0, 0, 25000, 25000)) and view3d.too_wide((0, 0, 25001, 100))


def test_arrow_keys_pan_the_view_through_the_scene():
    """Panning (26 Oct 2026): the window's arrow-key shortcuts call Scene3D.pan, which moves the
    camera target within -1..1; Reset view puts it back. A fake scene: no GPU needed."""
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])

    class Scene:
        def __init__(self):
            self.moves = []

        def pan(self, e, n):
            self.moves.append((e, n))

    w = view3d.View3DWindow.__new__(view3d.View3DWindow)
    w._scene = Scene()
    view3d.View3DWindow.pan(w, 1, 0)
    view3d.View3DWindow.pan(w, 0, -1)
    assert w._scene.moves == [(1, 0), (0, -1)]


def test_scene_pan_clamps_the_target():
    from PySide6.QtGui import QVector3D

    class Item:
        t = QVector3D(0.95, 0.0, -0.95)

        def cameraTargetPosition(self):
            return self.t

        def setCameraTargetPosition(self, v):
            self.t = v

    s = view3d_scene.Scene3D.__new__(view3d_scene.Scene3D)
    s.item = Item()
    view3d_scene.Scene3D.pan(s, 1, -1)
    assert (s.item.t.x(), s.item.t.z()) == (1.0, -1.0)
    view3d_scene.Scene3D.pan(s, -1, 0)
    assert abs(s.item.t.x() - (1.0 - view3d_scene.PAN_STEP)) < 1e-6
