"""Round 16 (A2, A3, A5, A6): the 3D view in its own process, the crash-log note, and layer load errors.
All data is small and made here."""
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "Observatum")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from shared import crash_log  # noqa: E402
from shared.maps import layer_notes, layers, terrain  # noqa: E402
from tests.test_map_view3d import FakeMap  # noqa: E402

@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


EXT = (440000.0, 120000.0, 441000.0, 120500.0)


def _heights():
    g = np.linspace(0, 80, 20 * 40, dtype=np.float32).reshape(20, 40)
    return terrain.Heights(g, EXT, 25.0, "OS Terrain 50, test", np.zeros_like(g, bool))


# ---------------------------------------------------------------- A6: crash_log.note
def test_note_is_a_no_op_before_install_and_never_raises(monkeypatch):
    monkeypatch.setattr(crash_log, "_FILE", None)
    crash_log.note("nothing", ValueError("x"))                     # no log: silently nothing


def test_note_writes_text_and_traceback(tmp_path, monkeypatch):
    f = open(tmp_path / "log.txt", "a", encoding="utf-8")
    monkeypatch.setattr(crash_log, "_FILE", f)
    try:
        raise MemoryError("too big")
    except MemoryError as e:
        crash_log.note("Layer failed", e)
    crash_log.note("plain")
    f.close()
    text = (tmp_path / "log.txt").read_text(encoding="utf-8")
    assert "Layer failed" in text and "MemoryError: too big" in text and "Traceback" in text
    assert "plain" in text and text.count("=== 20") == 2
    crash_log.note("after close")                                  # a closed file: still no exception


# ---------------------------------------------------------------- A5: layer load errors
def test_layer_load_error_is_recorded_once_and_exposed(tmp_path, monkeypatch):
    d = tmp_path / "layers"
    d.mkdir()
    (d / "woodland_county.json").write_text("{not json", encoding="utf-8")
    noted = []
    monkeypatch.setattr(crash_log, "note", lambda text, exc=None: noted.append((text, exc)))
    layers._ERRORS.clear()
    layers._NOTED.clear()
    assert layers.load(tmp_path, "woodland", "county") == []
    assert layers.load(tmp_path, "woodland", "county") == []
    assert len(noted) == 1 and "woodland_county.json" in noted[0][0]
    assert list(layers.load_errors()) == ["woodland_county"]
    (d / "woodland_county.json").write_text(json.dumps({"features": []}), encoding="utf-8")
    assert layers.load(tmp_path, "woodland", "county") == []
    assert layers.load_errors() == {}                              # a file that loads again is cleared


def test_layer_load_memory_error_still_returns_empty(tmp_path, monkeypatch):
    d = tmp_path / "layers"
    d.mkdir()
    (d / "heath_county.json").write_text("{}", encoding="utf-8")

    def boom(*a, **k):
        raise MemoryError()
    monkeypatch.setattr(layers.layer_bin, "read", boom)
    monkeypatch.setattr(crash_log, "note", lambda *a, **k: None)
    layers._ERRORS.clear()
    assert layers.load(tmp_path, "heath", "county") == []
    assert "heath_county" in layers.load_errors()


def test_corner_note_lines_and_drawing(qapp):
    from PySide6.QtCore import QRect
    from PySide6.QtGui import QColor, QImage, QPainter
    assert layer_notes.note_lines({"ancient_woodland_county": "x", "ancient_woodland_gb": "y"}) == \
        ["Layer ancient woodland could not be loaded"]
    img = QImage(200, 100, QImage.Format.Format_RGB32)
    img.fill(QColor("white"))
    p = QPainter(img)
    layer_notes.draw_load_errors(p, QRect(0, 0, 200, 100), {})
    p.end()
    assert all(img.pixel(x, y) == 0xFFFFFFFF for x in range(0, 200, 7) for y in range(0, 100, 7))
    p = QPainter(img)
    layer_notes.draw_load_errors(p, QRect(0, 0, 200, 100), {"heath_county": "x"})
    p.end()
    assert img.pixel(12, 92) != 0xFFFFFFFF or img.pixel(20, 85) != 0xFFFFFFFF


# ---------------------------------------------------------------- A2: the launcher
def test_prepare_writes_what_the_child_reads(qapp, tmp_path, monkeypatch):
    from Observatum.src.views.mapping import view3d_child, view3d_launch
    monkeypatch.setattr(terrain, "heights_for_extent", lambda *a, **k: _heights())
    m = FakeMap()
    m._squares = {"SU4020": {"count": 4, "fill": "#336699", "other": object()}}
    path = view3d_launch.prepare(m, EXT, tmp_path)
    extent, h, image, squares, credits, colours = view3d_child.load_inputs(path)
    assert extent == EXT and h.grid.shape == (20, 40) and h.cell_m == 25.0
    assert (image.width(), image.height()) == (2048, 1024)
    assert squares == {"SU4020": {"count": 4, "fill": "#336699"}} and credits and colours["background"]


def test_command_and_flags_for_the_child(monkeypatch):
    from Observatum.src.views.mapping import view3d_launch
    cmd = view3d_launch.child_command("x.json")
    assert cmd[0] == sys.executable and cmd[1] == "-m" and cmd[2].endswith(".view3d_child") and cmd[3] == "x.json"
    monkeypatch.setattr(view3d_launch.sys, "platform", "linux")
    assert view3d_launch.creation_flags() == 0


def test_nonzero_exit_shows_the_crash_log_message(qapp, monkeypatch):
    from Observatum.src.views.mapping import view3d_launch
    shown = []
    monkeypatch.setattr(view3d_launch.QMessageBox, "warning", lambda *a: shown.append(a[2]))

    class Proc:
        def __init__(self, code):
            self.code = code

        def poll(self):
            return self.code

        def terminate(self):
            self.code = -15
    h = view3d_launch.View3DProcess(Proc(3))
    h._poll()
    assert len(shown) == 1 and "closed unexpectedly" in shown[0] and "crash_view3d_" in shown[0]
    ok = view3d_launch.View3DProcess(Proc(0))
    ok._poll()
    closed = view3d_launch.View3DProcess(Proc(None))
    closed.close()
    closed._poll()                                                  # ended by us: no message
    assert len(shown) == 1


def test_launch_failure_to_prepare_is_a_message(qapp, monkeypatch):
    from Observatum.src.views.mapping import view3d_launch
    shown = []
    monkeypatch.setattr(view3d_launch.QMessageBox, "information", lambda *a: shown.append(a[2]))
    monkeypatch.setattr(view3d_launch.QMessageBox, "warning", lambda *a: shown.append(a[2]))

    def no_heights(*a, **k):
        raise terrain.TerrainUnavailable("no terrain here")
    monkeypatch.setattr(terrain, "heights_for_extent", no_heights)
    assert view3d_launch.launch_view3d(FakeMap(), EXT) is None and shown == ["no terrain here"]


def test_child_with_a_bad_file_exits_nonzero_and_logs(tmp_path):
    """A real child process: the settings file is missing, so it must end with a non-zero code and
    leave a crash_view3d log (the parent then shows its message)."""
    code = ("import sys; sys.path[:0] = [%r, %r]\n"
            "from pathlib import Path\n"
            "from shared import crash_log\n"
            "crash_log.log_dir = lambda: Path(%r)\n"
            "from Observatum.src.views.mapping import view3d_child\n"
            "sys.exit(view3d_child.main(['x', %r]))\n"
            % (str(ROOT), str(ROOT / "Observatum"), str(tmp_path), str(tmp_path / "missing.json")))
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=180, cwd=str(ROOT),
                       env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8"})
    assert r.returncode == 1, r.stderr[-800:]
    logs = list(tmp_path.glob("crash_view3d_*.log"))
    assert logs and "the window could not be made" in logs[0].read_text(encoding="utf-8")


# ---------------------------------------------------------------- A3: no calls on a failed widget
def test_failure_after_heights_deletes_the_widget_not_calls_it(qapp, monkeypatch):
    from PySide6.QtWidgets import QLabel
    from Observatum.src.views.mapping import view3d, view3d_scene
    noted, events = [], []
    monkeypatch.setattr(crash_log, "note", lambda text, exc=None: noted.append((text, exc)))
    monkeypatch.setattr(terrain, "heights_for_extent", lambda *a, **k: _heights())
    order = []

    class Widget:
        def deleteLater(self):
            events.append("deleteLater")

        def __getattr__(self, n):
            events.append(n)
            raise AssertionError(f"called {n} on a failed widget")

    class Scene:
        def __init__(self, *a, **k):
            order.append("scene")
            self.widget = Widget()

        def apply_theme(self, *a):
            raise RuntimeError("driver exploded")
    monkeypatch.setattr(view3d_scene, "Scene3D", Scene)
    monkeypatch.setattr(view3d.drape, "make_drape", lambda *a, **k: order.append("drape") or None)
    w = view3d.View3DWindow(FakeMap(), EXT)
    assert order == ["drape", "scene"]                              # drape first, Qt Quick after
    assert noted and noted[0][1].args == ("driver exploded",) and events == ["deleteLater"]
    assert any("driver exploded" in lab.text() for lab in w.findChildren(QLabel))


def test_child_uses_opengl_unless_a_backend_is_set():
    from src.views.mapping import view3d_child as child
    env = {}
    assert child.choose_backend(env) == "opengl" and env["QSG_RHI_BACKEND"] == "opengl"
    env = {"QSG_RHI_BACKEND": "d3d11"}
    assert child.choose_backend(env) == "d3d11"
