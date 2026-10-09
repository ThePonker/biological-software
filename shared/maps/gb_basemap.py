"""Whole-GB basemap by stitching the OS 1:250k tiles into one cached image.

Moved from DataEntry/gb_basemap.py (backlog H2, 9 Oct 2026); that module is now a shim.

The distribution map needs all of GB at once; the location map only ever shows one 100 km tile.
This composites every {CODE}.tif into a single downscaled national image (OSGB extent), saved to
data/maps/gb_basemap_250k.png and reused thereafter. Built with Pillow; falls back to the vector
GB when tiles/Pillow aren't present.
"""
from __future__ import annotations

import os
from typing import Optional, Tuple

from shared.maps.raster_map import en_to_100km_code

GB_EXTENT: Tuple[float, float, float, float] = (0.0, 0.0, 700000.0, 1300000.0)  # OSGB E/N
_PX_PER_TILE = 200                      # each 100 km tile -> 200 px (=> 500 m/px)
_MOSAIC_W = 7 * _PX_PER_TILE            # 1400 px  (E 0..700 km)
_MOSAIC_H = 13 * _PX_PER_TILE           # 2600 px  (N 0..1300 km)
_BASENAME = "gb_basemap_250k.png"

# code -> 100 km square origin (E0, N0), computed once
_ORIGIN_CACHE = {}


def _origin_for_code(code: str):
    if code in _ORIGIN_CACHE:
        return _ORIGIN_CACHE[code]
    for E0 in range(0, 700000, 100000):
        for N0 in range(0, 1300000, 100000):
            if en_to_100km_code(E0 + 50000, N0 + 50000) == code:
                _ORIGIN_CACHE[code] = (E0, N0)
                return (E0, N0)
    _ORIGIN_CACHE[code] = None
    return None


def gb_basemap_path(tiles_dir: Optional[str], maps_dir: Optional[str]) -> Optional[str]:
    """Path to the cached GB mosaic, building it once if missing. None if it can't be built."""
    if not maps_dir:
        maps_dir = os.path.dirname(tiles_dir) if tiles_dir else None
    if not maps_dir:
        return None
    out = os.path.join(maps_dir, _BASENAME)
    if os.path.exists(out):
        return out
    if not tiles_dir or not os.path.isdir(tiles_dir):
        return None
    try:
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
    except Exception:
        return None
    canvas = Image.new("RGB", (_MOSAIC_W, _MOSAIC_H), (255, 255, 255))
    pasted = 0
    for f in sorted(os.listdir(tiles_dir)):
        if len(f) == 6 and f[:2].isalpha() and f.lower().endswith(".tif"):
            org = _origin_for_code(f[:2].upper())
            if not org:
                continue
            E0, N0 = org
            try:
                im = Image.open(os.path.join(tiles_dir, f)).convert("RGB").resize(
                    (_PX_PER_TILE, _PX_PER_TILE), Image.LANCZOS)
            except Exception:
                continue
            x = int(E0 / 100000) * _PX_PER_TILE
            y = int((1300000 - (N0 + 100000)) / 100000) * _PX_PER_TILE
            if 0 <= x <= _MOSAIC_W - _PX_PER_TILE and 0 <= y <= _MOSAIC_H - _PX_PER_TILE:
                canvas.paste(im, (x, y))
                pasted += 1
    if pasted == 0:
        return None
    try:
        os.makedirs(maps_dir, exist_ok=True)
        canvas.save(out)
    except Exception:
        return None
    return out
