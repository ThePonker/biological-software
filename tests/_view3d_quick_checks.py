"""3D-view checks that build real Qt Quick / QtGraphs widgets, run in a CHILD process (25 Oct 2026).

Without a GPU, a QQuickWidget's teardown can crash the interpreter later, at an arbitrary
garbage collection (seen in the full suite: a segfault in another file's teardown). So these
checks run in their own interpreter, which leaves with os._exit(0) after printing "OK <name>",
and the tests in test_map_view3d.py / test_review_fixes_20261025.py only read that line.

    python tests/_view3d_quick_checks.py <check name>
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "Observatum"), str(ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np  # noqa: E402

EXT = (440000.0, 120000.0, 441000.0, 120500.0)


def _heights(lo=0.0, hi=80.0):
    from shared.maps import terrain
    g = np.linspace(lo, hi, 20 * 40, dtype=np.float32).reshape(20, 40)
    return terrain.Heights(g, EXT, 25.0, "OS Terrain 50, test", np.zeros_like(g, bool))


def window_builds_with_fake_heights():
    from shared.maps import terrain
    from Observatum.src.views.mapping import view3d
    from test_map_view3d import FakeMap
    h = _heights()
    terrain.heights_for_extent = lambda *a, **k: h
    m = FakeMap()
    m._squares = {"SU4020": {"count": 4, "fill": "#336699"}}
    w = view3d.View3DWindow(m, EXT)
    assert w.heights is h and "OS Terrain 50, test" in w.status.text() and "25 m" in w.status.text()
    assert 1 <= w.exaggeration() <= 10
    w.columns_check.setChecked(True)
    w.ex_slider.setValue(30)
    w._apply_exaggeration()
    assert w._scene.exaggeration == 3.0


def scene_graph_error_is_shown():
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtWidgets import QLabel, QWidget
    from shared.maps import terrain
    from Observatum.src.views.mapping import view3d, view3d_scene
    from test_map_view3d import FakeMap
    seen, par = [], QWidget()
    s = view3d_scene.Scene3D(par, on_error=seen.append)
    s.widget.sceneGraphError.emit(QQuickWindow.SceneGraphError.ContextNotAvailable, "no GPU")
    assert s.failed == "no GPU" and "no GPU" in seen[0]
    terrain.heights_for_extent = lambda *a, **k: _heights()
    w = view3d.View3DWindow(FakeMap(), EXT)
    assert w.export_btn.isEnabled() and w._scene is not None
    w._scene.widget.sceneGraphError.emit(QQuickWindow.SceneGraphError.ContextNotAvailable, "driver")
    assert not w.export_btn.isEnabled() and not w.ex_slider.isEnabled() and w._scene is None
    assert any("driver" in lab.text() for lab in w.findChildren(QLabel))


def scene_creation_failure_is_a_message():
    from PySide6.QtWidgets import QWidget
    from Observatum.src.views.mapping import view3d, view3d_scene
    from test_map_view3d import FakeMap
    g, _item, _quick = view3d_scene.load_qtgraphs()

    def boom(*a, **k):
        raise RuntimeError("no driver")
    g.QSurfaceDataProxy = boom
    par = QWidget()
    try:
        view3d_scene.Scene3D(par)
    except view3d_scene.Graphs3DUnavailable:
        pass
    else:
        raise AssertionError("Scene3D did not raise Graphs3DUnavailable")
    w = view3d.View3DWindow(FakeMap(), EXT)
    assert not w.export_btn.isEnabled()


def height_axis_not_clipped_below_sea_level():
    from PySide6.QtWidgets import QWidget
    from Observatum.src.views.mapping import view3d_scene
    par = QWidget()
    s = view3d_scene.Scene3D(par)
    s.set_heights(_heights(-6.0, 40.0), 2.0)
    assert abs(s.item.axisY().min() - (-12.0)) < 1e-6
    s.set_heights(_heights(0.0, 40.0), 2.0)
    assert s.item.axisY().min() == 0.0


CHECKS = {f.__name__: f for f in (window_builds_with_fake_heights, scene_graph_error_is_shown,
                                  scene_creation_failure_is_a_message,
                                  height_axis_not_clipped_below_sea_level)}


NO_GPU_SIGNS = ("Failed to create", "is not functional", "Could not initialize", "no usable")


def run_in_child(name: str) -> str:
    """For the tests: run one check in a fresh interpreter (QSettings sandboxed); its stdout+stderr.
    Skips the calling test when the child could not get a graphics context (no GPU, as in a
    cloud workspace): Qt Quick cannot be built there at all."""
    import subprocess
    from _sandbox_child import child_code
    code = f"import runpy, sys; sys.argv = [{str(Path(__file__))!r}, {name!r}]; " \
           f"runpy.run_path({str(Path(__file__))!r}, run_name='__main__')"
    # UTF-8 both ways: on Windows a captured child prints in cp1252, and config.py's "\u2713" fails
    r = subprocess.run([sys.executable, "-c", child_code(code)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=180, cwd=str(ROOT),
                       env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8"})
    out = r.stdout + r.stderr
    if r.returncode != 0 and f"OK {name}" not in out and any(t in out for t in NO_GPU_SIGNS):
        import pytest
        pytest.skip("needs a working graphics context (GPU) for Qt Quick")
    return out


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    name = sys.argv[1]
    try:
        CHECKS[name]()
    except Exception:
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)
    print(f"OK {name}", flush=True)
    os._exit(0)              # no Qt Quick teardown: that is what crashes without a GPU
