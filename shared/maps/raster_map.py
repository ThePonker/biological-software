"""Detailed raster mini-map from the OS 1:250k colour raster tiles (OS OpenData, OGL).

Moved from DataEntry/raster_map.py (backlog H2, 9 Oct 2026); that module is now a shim.

Each tile is a 100 km National-Grid square named by its two-letter code (SP.tif, TQ.tif, ...),
4000x4000 px at 25 m/px, NW-origin at the square. Given a record's grid ref we pick the right
tile, crop a window around the point, and draw it with the record's dot on top -- so you can
recognise a site by its nearby town/river/coast, not just its county.

Tiles are decoded with Pillow (Qt's TIFF plugin isn't guaranteed present). If Pillow or the tiles
are missing, the info panel falls back to the vector VC map.
"""
from __future__ import annotations

import os
from collections import OrderedDict
from typing import Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QPixmap, QImage
from PySide6.QtWidgets import QWidget

from shared.maps._theme import theme

_LETTERS = "ABCDEFGHJKLMNOPQRSTUVWXYZ"  # no 'I'
TILE_PX = 4000
TILE_SCALE_M = 25.0          # metres per pixel
TILE_SPAN_M = 100000         # 100 km square


def en_to_100km_code(E: float, N: float) -> Optional[str]:
    x = int(E // 100000)
    y = int(N // 100000)
    try:
        first = _LETTERS[(3 - y // 5) * 5 + (x // 5 + 2)]
        second = _LETTERS[(4 - (y % 5)) * 5 + (x % 5)]
    except IndexError:
        return None
    return first + second


def pillow_available() -> bool:
    try:
        import PIL  # noqa: F401
        return True
    except Exception:
        return False


def find_tiles_dir(maps_dir: str) -> Optional[str]:
    """Locate a folder holding {CODE}.tif tiles: maps_dir/ras250, else maps_dir itself."""
    if not maps_dir:
        return None
    for cand in (os.path.join(maps_dir, "ras250"), os.path.join(maps_dir, "ras250_gb"), maps_dir):
        if os.path.isdir(cand):
            for f in os.listdir(cand):
                if len(f) == 6 and f[:2].isalpha() and f.lower().endswith(".tif"):
                    return cand
    return None


class _TileCache:
    """Small LRU of decoded RGB PIL images, keyed by tile code."""
    def __init__(self, cap=4):
        self._cap = cap
        self._d: "OrderedDict[str, object]" = OrderedDict()

    def get(self, tiles_dir, code):
        if code in self._d:
            self._d.move_to_end(code)
            return self._d[code]
        path = os.path.join(tiles_dir, f"{code}.tif")
        if not os.path.exists(path):
            return None
        try:
            from PIL import Image
            Image.MAX_IMAGE_PIXELS = None
            img = Image.open(path).convert("RGB")
        except Exception:
            return None
        self._d[code] = img
        self._d.move_to_end(code)
        while len(self._d) > self._cap:
            self._d.popitem(last=False)
        return img


_CACHE = _TileCache()


from shared.maps.panzoom import PanZoomMixin


class RasterMiniMap(PanZoomMixin, QWidget):
    """OS 1:250k raster window around the record's location, with a dot. Display only."""

    def __init__(self, tiles_dir: Optional[str], vc_service=None, window_m: int = 5000,
                 resizable: bool = False, parent=None):
        super().__init__(parent)
        self._tiles_dir = tiles_dir
        self._vc_service = vc_service
        self._window_m = window_m
        self._ok = self._check_ok(tiles_dir)
        self._pix: Optional[QPixmap] = None
        self._dot_in_crop: Optional[Tuple[float, float]] = None
        self._crop_px: int = 1
        self._code: str = ""
        self._msg = "no location"
        self._last_row = None
        if resizable:
            self.setMinimumSize(240, 240)
        else:
            self.setFixedSize(148, 148)
        self._init_panzoom(resizable)
        self.setToolTip("Location on OS 1:250k. Contains OS data \u00a9 Crown copyright & database right.")

    @staticmethod
    def _check_ok(tiles_dir) -> bool:
        if not tiles_dir or not os.path.isdir(tiles_dir) or not pillow_available():
            return False
        for f in os.listdir(tiles_dir):
            if len(f) == 6 and f[:2].isalpha() and f.lower().endswith(".tif"):
                return True
        return False

    def has_data(self) -> bool:
        return self._ok

    def update_for_row(self, row: Optional[dict]):
        self._last_row = row
        self._pix = None
        self._dot_in_crop = None
        self._code = ""
        self._msg = "no location"
        if row and self._vc_service is not None:
            gr = (row.get("grid_ref") or "").strip()
            if gr:
                try:
                    parsed = self._vc_service.parse_grid_ref(gr)
                except Exception:
                    parsed = None
                if parsed:
                    self._build(float(parsed[0]), float(parsed[1]))
                else:
                    self._msg = "grid ref not recognised"
        self.update()

    def refresh(self):
        self.update_for_row(self._last_row)

    def _build(self, E: float, N: float):
        code = en_to_100km_code(E, N)
        if not code:
            self._msg = "off-grid"
            return
        self._code = code
        img = _CACHE.get(self._tiles_dir, code)
        if img is None:
            self._msg = f"no tile {code}"
            return
        E_tl = (int(E // 100000)) * 100000
        N_tl = (int(N // 100000) + 1) * 100000
        cx = (E - E_tl) / TILE_SCALE_M
        cy = (N_tl - N) / TILE_SCALE_M
        half = int((self._window_m / TILE_SCALE_M) / 2)
        crop = 2 * half
        left = max(0, min(int(cx - half), TILE_PX - crop))
        top = max(0, min(int(cy - half), TILE_PX - crop))
        try:
            sub = img.crop((left, top, left + crop, top + crop))
            data = sub.tobytes("raw", "RGB")
            qimg = QImage(data, sub.width, sub.height, sub.width * 3, QImage.Format.Format_RGB888)
            self._pix = QPixmap.fromImage(qimg.copy())
        except Exception:
            self._pix = None
            self._msg = "tile read error"
            return
        self._crop_px = crop
        self._dot_in_crop = (cx - left, cy - top)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        p.fillRect(self.rect(), QColor(theme.CARD))
        if self._pix is None:
            p.setPen(QColor(theme.MUTED))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._msg)
            p.end()
            return
        side = min(self.width(), self.height())
        ox = (self.width() - side) / 2.0
        oy = (self.height() - side) / 2.0
        p.save(); self._apply_pan_zoom(p)
        p.drawPixmap(int(ox), int(oy), side, side, self._pix)
        if self._dot_in_crop is not None:
            s = side / self._crop_px
            x = ox + self._dot_in_crop[0] * s
            y = oy + self._dot_in_crop[1] * s
            p.setPen(QPen(QColor(theme.PAPER), 1.4))
            p.setBrush(QBrush(QColor(theme.CLAY)))
            p.drawEllipse(int(x - 4), int(y - 4), 8, 8)
        p.restore()
        p.setPen(QColor(theme.INK))
        f = p.font(); f.setPointSize(7); f.setBold(True); p.setFont(f)
        p.drawText(4, 14, self._code)
        p.setPen(QColor(80, 80, 80))
        f2 = p.font(); f2.setPointSize(6); f2.setBold(False); p.setFont(f2)
        p.drawText(2, self.height() - 2, "\u00a9 Crown copyright OS")
        p.end()
