"""The 3D view as its own program (Round 16, 10 Nov 2026):

    python -m <package>.view3d_child <view3d.json>

Started by view3d_launch.py with the heights, drape picture, record squares and colours the parent
wrote. A graphics or Qt Quick failure here ends only this process (and is written to
data\\logs\\crash_view3d_<month>.log); Observatum carries on.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


class SnapshotMap:
    """What the window asks of a map widget, from the saved data (no map is drawn here)."""

    def __init__(self, squares):
        self._squares = squares


def load_inputs(json_path):
    """(extent, heights, drape QImage, squares, credits, colours) from the parent's json."""
    import numpy as np
    from PySide6.QtGui import QImage
    from shared.maps import terrain
    folder = Path(json_path).parent
    doc = json.loads(Path(json_path).read_text(encoding="utf-8"))
    grid = np.load(folder / doc["grid"], allow_pickle=False)
    heights = terrain.Heights(grid, tuple(doc["heights_extent"]), float(doc["cell_m"]),
                              doc["label"], np.zeros(grid.shape, dtype=bool))
    image = QImage(str(folder / doc["drape"]))
    if image.isNull():
        raise OSError("the drape picture could not be read")
    return (tuple(doc["extent"]), heights, image, doc.get("squares") or {},
            doc.get("credits"), doc.get("colours"))


GRAPHICS_BACKEND = "opengl"


def choose_backend(env) -> str:
    """Qt Quick's graphics backend for this process: OpenGL unless QSG_RHI_BACKEND is already set.
    On Wil's PC the default (Direct3D) crashed natively in the 3D view; OpenGL opened (10 Nov 2026).
    Must be set before the QApplication is made."""
    return env.setdefault("QSG_RHI_BACKEND", GRAPHICS_BACKEND)


def main(argv) -> int:
    import os
    choose_backend(os.environ)
    from shared import crash_log                 # data\logs\crash_view3d_<month>.log
    crash_log.install("view3d")
    from shared import light_scheme              # always light, even on a dark-mode PC
    light_scheme.prepare()
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    light_scheme.install(app)
    if len(argv) < 2:
        crash_log.note("view3d_child: no settings file given")
        return 2
    try:
        from .view3d import View3DWindow
        extent, heights, image, squares, credits, colours = load_inputs(argv[1])
        win = View3DWindow(SnapshotMap(squares), extent, None, heights=heights, drape_image=image,
                           credits=credits, colours=colours)
    except Exception as e:
        crash_log.note("view3d_child: the window could not be made", e)
        return 1
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
