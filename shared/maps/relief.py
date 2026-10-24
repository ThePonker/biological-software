"""The Mapping tab's Relief layer (18 Oct 2026): the hillshade image made by
scripts/build_map_relief.py (data/maps/layers/relief_gb.png + relief_gb.json), drawn through the
same metres-to-pixels transform as the other layers, under woodland, towns etc. and over the land.

The image is grey with alpha, level ground white, and is drawn MULTIPLIED at RELIEF_OPACITY, so
only slopes darken the land and the map stays pale. When the view is zoomed out so that a cell
is smaller than half a screen pixel, a halved copy (kept) is drawn instead, which also avoids
the speckle of sampling a big image down. Display only.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter, QTransform

from shared.maps import layers

RELIEF_OPACITY = 0.55
MAX_HALVINGS = 3
_CACHE: Dict[tuple, Optional["Relief"]] = {}
_LOCK = threading.RLock()


@dataclass
class Relief:
    image: QImage                       # premultiplied ARGB32, row 0 at the north edge
    extent: Tuple[float, float, float, float]
    cell_m: float
    _levels: Dict[int, QImage] = field(default_factory=dict)

    def level(self, n: int) -> QImage:
        """The image halved n times (smooth), made once."""
        if n <= 0:
            return self.image
        if n not in self._levels:
            w, h = max(1, self.image.width() >> n), max(1, self.image.height() >> n)
            self._levels[n] = self.image.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio,
                                                Qt.TransformationMode.SmoothTransformation)
        return self._levels[n]


def load(maps_dir) -> Optional[Relief]:
    """The relief image and its extent, cached per file; None if not installed or unreadable."""
    meta = layers.file_path(maps_dir, "relief", "gb")
    if meta is None:
        return None
    png = meta.with_suffix(".png")
    try:
        ck = (str(meta), meta.stat().st_mtime_ns, png.stat().st_mtime_ns)
        with _LOCK:
            if ck not in _CACHE:
                doc = json.loads(meta.read_text(encoding="utf-8"))
                img = QImage(str(png))
                if img.isNull():
                    raise ValueError("relief image unreadable")
                _CACHE[ck] = Relief(img.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied),
                                    tuple(float(v) for v in doc["extent"]), float(doc["cell_m"]))
            return _CACHE[ck]
    except Exception:
        return None


def draw(p: QPainter, rel: Relief, to_px: QTransform):
    """Draw the relief through `to_px` (OSGB metres -> pixels, y flipped; map_layers.layer_transform)."""
    px_per_m = abs(to_px.m11()) * abs(p.transform().m11())
    cell_px = rel.cell_m * px_per_m
    n = 0
    while n < MAX_HALVINGS and cell_px * (1 << n) < 0.5:
        n += 1
    img = rel.level(n)
    e0, n0, e1, n1 = rel.extent
    p.save()
    p.setWorldTransform(to_px, True)
    p.translate(e0, n1)
    p.scale((e1 - e0) / img.width(), -(n1 - n0) / img.height())
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
    p.setOpacity(p.opacity() * RELIEF_OPACITY)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    p.drawImage(0, 0, img)
    p.restore()
