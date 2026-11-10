"""The parent's side of the 3D view (Round 16, 10 Nov 2026): Observatum prepares what the view needs
(heights, the drape picture, the record squares, colours) in a temporary folder and starts
view3d_child.py in its own process, so a graphics / Qt Quick failure cannot take Observatum down.

If the child ends with a non-zero code, a short message points to its crash log.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QMessageBox

from shared import crash_log
from shared.maps import terrain
from . import view3d_drape as drape
from ...themes import theme

COLOUR_KEYS = ("background", "text_heading", "text_secondary", "surface")
CHILD_MODULE = f"{__package__}.view3d_child"
_slot = [0]                       # two folders used in turn: the previous child may still be starting


def work_dir() -> Path:
    _slot[0] = (_slot[0] + 1) % 2
    d = Path(tempfile.gettempdir()) / "biosoft_view3d" / f"v{_slot[0]}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def prepare(map_widget, extent, folder: Path) -> Path:
    """Write the heights (.npy), the drape (.png) and settings (.json) into `folder`; the json's path.
    Raises terrain.TerrainUnavailable (no heights) or whatever reading them raises."""
    h = terrain.heights_for_extent(extent)
    img = drape.make_drape(map_widget, h.extent)
    np.save(folder / "grid.npy", np.asarray(h.grid, dtype=np.float32))
    if not img.save(str(folder / "drape.png"), "PNG"):
        raise OSError("the drape picture could not be saved")
    squares = {str(k): {"count": (v or {}).get("count", 0), "fill": (v or {}).get("fill")}
               for k, v in (getattr(map_widget, "_squares", {}) or {}).items()}
    t = theme()
    doc = {"extent": [float(v) for v in extent], "heights_extent": [float(v) for v in h.extent],
           "cell_m": float(h.cell_m), "label": h.source_label, "grid": "grid.npy",
           "drape": "drape.png", "squares": squares,
           "credits": drape.export_credits(map_widget, h.source_label),
           "colours": {k: t.get(k) for k in COLOUR_KEYS}}
    out = folder / "view3d.json"
    out.write_text(json.dumps(doc), encoding="utf-8")
    return out


def child_command(json_path) -> list:
    """python -m <package>.view3d_child <json>; pythonw has no console, python.exe gets none either."""
    return [sys.executable, "-m", CHILD_MODULE, str(json_path)]


def child_env() -> dict:
    env = os.environ.copy()
    try:
        import paths
        root = Path(paths.ROOT)
        env["PYTHONPATH"] = os.pathsep.join(
            [str(root), str(root / "Observatum")] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    except Exception:
        pass
    return env


def creation_flags() -> int:
    return subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


class View3DProcess(QObject):
    """The running 3D view: close() ends it; a non-zero exit shows the 'closed unexpectedly' message."""

    def __init__(self, proc, parent_widget=None):
        super().__init__(None)
        self.proc, self._parent_widget, self._closed = proc, parent_widget, False
        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

    def _poll(self):
        code = self.proc.poll()
        if code is None:
            return
        self._timer.stop()
        if code != 0 and not self._closed:
            QMessageBox.warning(self._parent_widget, "3D view", crash_message())

    def close(self):
        self._closed = True
        self._timer.stop()
        try:
            if self.proc.poll() is None:
                self.proc.terminate()
        except OSError:
            pass


def crash_message() -> str:
    name = crash_log.log_path("view3d").name
    return f"The 3D view closed unexpectedly; details are in data\\logs\\{name}"


def launch_view3d(map_widget, extent, parent=None):
    """Prepare and start the 3D view process; its View3DProcess, or None when it could not start
    (a message says why)."""
    try:
        path = prepare(map_widget, extent, work_dir())
    except terrain.TerrainUnavailable as e:
        QMessageBox.information(parent, "3D view", str(e))
        return None
    except Exception as e:
        crash_log.note("3D view: could not prepare the data", e)
        QMessageBox.warning(parent, "3D view", f"The 3D view could not be prepared: {type(e).__name__}: {e}")
        return None
    try:
        proc = subprocess.Popen(child_command(path), env=child_env(), creationflags=creation_flags())
    except OSError as e:
        crash_log.note("3D view: could not start the process", e)
        QMessageBox.warning(parent, "3D view", f"The 3D view could not be started: {e}")
        return None
    return View3DProcess(proc, parent)
