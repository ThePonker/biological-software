"""Heights for the Mapping tab's 3D view (no Qt): OS Terrain 50, or a finer LiDAR DTM if the
folder data/maps/lidar/ holds GeoTIFF tiles covering the whole view.

    heights_for_extent(extent) -> Heights(grid, extent, cell_m, source_label, sea)

grid is float32, rows north to south, square cells of cell_m metres, covering `extent` (the
asked-for box widened to whole cells). Sea / no-data cells are 0 m and True in `sea`.

Terrain 50 is read exactly as scripts/build_map_relief.py reads it (its parse_asc), without
extracting: only the 10 km tiles touching the view are opened, each averaged down by a whole
number of cells when the view is big (so GB-wide asks stay small), and kept in a small LRU of
parsed tiles. Smaller Terrain 50 views are enlarged (bilinear, at most 4x) so the surface is not blocky.
"""
from __future__ import annotations

import io
import re
import threading
import zipfile
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple

import numpy as np

import paths
from shared import osgb
from shared.maps import grid_squares as gs

LIDAR_DIR = Path(paths.MAPS_DIR) / "lidar"          # GeoTIFF DTM tiles (EA 1 m / 2 m, OSGB)
DEFAULT_SOURCE = Path.home() / "OS data"            # where build_map_layers looks for Terrain 50
TILE_M = 10000
CELL_M = 50
TILE_CELLS = TILE_M // CELL_M                       # 200
_FACTORS = [f for f in range(1, TILE_CELLS + 1) if TILE_CELLS % f == 0]
LRU_TILES = 64
MAX_UPSAMPLE = 4
EA_CREDIT = "Contains Environment Agency information © Environment Agency and/or database right."
OS_TERRAIN_NOTE = "OS Terrain 50"


class TerrainUnavailable(Exception):
    """No height data for the view (the message says what to install or where to put it)."""


def _br():
    """scripts/build_map_relief.py, imported when first needed (the Mapping tab must import
    without the scripts folder; the 3D view then says Terrain 50 cannot be read)."""
    try:
        from scripts import build_map_relief
    except ImportError as e:
        raise TerrainUnavailable(f"Terrain 50 cannot be read here: scripts/build_map_relief.py "
                                 f"is not installed ({e}).")
    return build_map_relief


class Heights(NamedTuple):
    grid: np.ndarray                  # float32 [rows, cols], row 0 at the north edge
    extent: Tuple[float, float, float, float]
    cell_m: float
    source_label: str
    sea: np.ndarray                   # bool, same shape: sea / no data


_TILES: "OrderedDict[tuple, Optional[tuple]]" = OrderedDict()
_LOCK = threading.RLock()
cache_hits = 0                        # parsed tiles served from the LRU (tests)


def clear_cache():
    with _LOCK:
        _TILES.clear()


# ---------------------------------------------------------------- Terrain 50 tiles
def _want(name: str, code: str) -> bool:
    """Should a zip called `name` be opened to find tile `code` (e.g. 'su42')?"""
    stem = re.sub(r"\.zip$", "", name.rsplit("/", 1)[-1].lower())
    m = re.match(r"^([a-z]{2})(\d\d)?", stem)
    if not m:
        return True
    return (m.group(1) + (m.group(2) or "")) == code if m.group(2) else m.group(1) == code[:2]


def _find_asc(zf, codes, depth=0):
    for info in zf.infolist():
        low = info.filename.lower()
        stem = low.rsplit("/", 1)[-1][:-4]
        if low.endswith(".asc"):
            if stem in codes:
                yield stem, zf.read(info)
        elif low.endswith(".zip") and depth < _br().MAX_ZIP_DEPTH and any(_want(low, c) for c in codes):
            with zipfile.ZipFile(io.BytesIO(zf.read(info))) as inner:
                yield from _find_asc(inner, codes, depth + 1)


def _read_codes(src: Path, codes):
    """{code: asc bytes} for the tiles wanted, from a zip or a folder (nothing extracted)."""
    out: Dict[str, bytes] = {}
    if src.is_file():
        with zipfile.ZipFile(src) as zf:
            for code, data in _find_asc(zf, codes):
                out[code] = data
        return out
    for f in sorted(src.rglob("*")):
        low = f.name.lower()
        if low.endswith(".asc") and low[:-4] in codes:
            out[low[:-4]] = f.read_bytes()
        elif low.endswith(".zip") and any(_want(low, c) for c in codes):
            with zipfile.ZipFile(f) as zf:
                for code, data in _find_asc(zf, codes):
                    out[code] = data
    return out


def _tile_array(src: Path, key, codes: List[str], f: int):
    """{code: (block-meaned array, xll, yll, cell) or None} for tiles at reduction f, via the LRU."""
    global cache_hits
    res, need = {}, []
    with _LOCK:
        for c in codes:
            k = key + (c, f)
            if k in _TILES:
                _TILES.move_to_end(k)
                res[c] = _TILES[k]
                cache_hits += 1
            else:
                need.append(c)
    if need:
        br = _br()
        found = _read_codes(src, need)
        for c in need:
            val = None
            if c in found:
                try:
                    z, xll, yll, cs = br.parse_asc(found[c])
                    val = (br.block_mean(z, f) if f > 1 else z, xll, yll, cs * f)
                except Exception:
                    val = None
            res[c] = val
            with _LOCK:
                _TILES[key + (c, f)] = val
                while len(_TILES) > LRU_TILES:
                    _TILES.popitem(last=False)
    return res


def _snap(extent, cell):
    e0, n0, e1, n1 = (float(v) for v in extent)
    return (np.floor(e0 / cell) * cell, np.floor(n0 / cell) * cell,
            max(np.ceil(e1 / cell), np.floor(e0 / cell) + 1) * cell,
            max(np.ceil(n1 / cell), np.floor(n0 / cell) + 1) * cell)


def _terrain50(extent, max_points, src: Path):
    long_m = max(extent[2] - extent[0], extent[3] - extent[1])
    f = next((x for x in _FACTORS if long_m / (CELL_M * x) <= max_points), _FACTORS[-1])
    cell = CELL_M * f
    e0, n0, e1, n1 = _snap(extent, cell)
    nx, ny = int(round((e1 - e0) / cell)), int(round((n1 - n0) / cell))
    codes = {}
    for te in range(int(e0 // TILE_M), int((e1 - 1e-6) // TILE_M) + 1):
        for tn in range(int(n0 // TILE_M), int((n1 - 1e-6) // TILE_M) + 1):
            ref = osgb.en_to_gridref(te * TILE_M + 1, tn * TILE_M + 1, 2)
            if ref:
                codes[ref.lower()] = (te * TILE_M, tn * TILE_M)
    st = src.stat()
    tiles = _tile_array(src, (str(src), st.st_mtime_ns), list(codes), f)
    grid = np.full((ny, nx), np.nan, np.float32)            # row 0 = south here; flipped below
    used = 0
    for code, (te, tn) in codes.items():
        t = tiles.get(code)
        if t is None:
            continue
        z, xll, yll, tcell = t
        c0, r0 = int(round((xll - e0) / cell)), int(round((yll - n0) / cell))
        zz = z[::-1]                                         # south first
        gc0, gr0 = max(c0, 0), max(r0, 0)
        gc1, gr1 = min(c0 + zz.shape[1], nx), min(r0 + zz.shape[0], ny)
        if gc1 <= gc0 or gr1 <= gr0:
            continue
        grid[gr0:gr1, gc0:gc1] = zz[gr0 - r0:gr1 - r0, gc0 - c0:gc1 - c0]
        used += 1
    if not used:
        raise TerrainUnavailable(f"OS Terrain 50 has no tile for this area ({src}).")
    grid = grid[::-1].copy()                                 # north first
    return grid, (e0, n0, e1, n1), float(cell), f"{OS_TERRAIN_NOTE}, {int(cell)} m cells, {used} tile(s)"


def _fill_gaps(grid, ext, cell, label, source):
    """`grid` (NaN where LiDAR has no data) with those cells taken from Terrain 50, bilinearly
    resampled to the LiDAR cell centres; unchanged if Terrain 50 is not available."""
    try:
        src = _br().find_terrain(source if source is not None else DEFAULT_SOURCE)
        if src is None:
            return grid, label
        t, text, tcell, _l = _terrain50(ext, 10 ** 9, Path(src))       # 50 m cells
    except TerrainUnavailable:
        return grid, label
    ny, nx = grid.shape
    ty, tx = t.shape
    t = np.where(np.isnan(t), 0.0, t)
    xs = ext[0] + (np.arange(nx) + 0.5) * cell
    ys = ext[3] - (np.arange(ny) + 0.5) * cell                          # row 0 = north
    fx = np.clip((xs - text[0]) / tcell - 0.5, 0, tx - 1)
    fy = np.clip((text[3] - ys) / tcell - 0.5, 0, ty - 1)               # t is north first too
    x0, y0 = np.floor(fx).astype(int), np.floor(fy).astype(int)
    x1, y1 = np.minimum(x0 + 1, tx - 1), np.minimum(y0 + 1, ty - 1)
    wx, wy = (fx - x0)[None, :], (fy - y0)[:, None]
    top = t[y0][:, x0] * (1 - wx) + t[y0][:, x1] * wx
    bot = t[y1][:, x0] * (1 - wx) + t[y1][:, x1] * wx
    fill = (top * (1 - wy) + bot * wy).astype(np.float32)
    return np.where(np.isnan(grid), fill, grid).astype(np.float32), label + "; gaps filled from OS Terrain 50"


def _finish(grid, extent, cell, label, max_points, enlarge=True):
    """Sea mask, zero fill, then bilinear enlargement for small views."""
    sea = np.isnan(grid) | (grid == 0.0)
    grid = np.where(np.isnan(grid), 0.0, grid).astype(np.float32)
    ny, nx = grid.shape
    u = int(max(1, min(MAX_UPSAMPLE, max_points // max(nx, ny)))) if enlarge else 1
    if u > 1:
        grid = _bilinear(grid, u)
        sea = np.repeat(np.repeat(sea, u, axis=0), u, axis=1)
        cell = cell / u
    return Heights(grid, tuple(float(v) for v in extent), float(cell), label, sea)


def _bilinear(z, u):
    """z enlarged u times along each axis (cell centres kept; bilinear)."""
    ny, nx = z.shape
    ys = (np.arange(ny * u) + 0.5) / u - 0.5
    xs = (np.arange(nx * u) + 0.5) / u - 0.5
    y0 = np.clip(np.floor(ys).astype(int), 0, ny - 1); y1 = np.clip(y0 + 1, 0, ny - 1)
    x0 = np.clip(np.floor(xs).astype(int), 0, nx - 1); x1 = np.clip(x0 + 1, 0, nx - 1)
    fy = np.clip(ys - y0, 0, 1)[:, None]
    fx = np.clip(xs - x0, 0, 1)[None, :]
    top = z[y0][:, x0] * (1 - fx) + z[y0][:, x1] * fx
    bot = z[y1][:, x0] * (1 - fx) + z[y1][:, x1] * fx
    return (top * (1 - fy) + bot * fy).astype(np.float32)


# ---------------------------------------------------------------- the public call
def heights_for_extent(extent, max_points: int = 512, source=None, lidar_dir=None) -> Heights:
    """Heights for an OSGB box (e0, n0, e1, n1). `source`: a Terrain 50 zip / folder (default
    ~/OS data); `lidar_dir`: GeoTIFF DTM folder (default LIDAR_DIR). Raises TerrainUnavailable."""
    from shared.maps import terrain_lidar
    note = ""
    folder = Path(lidar_dir) if lidar_dir is not None else LIDAR_DIR
    try:
        got = terrain_lidar.lidar_heights(extent, max_points, folder)
    except terrain_lidar.LidarUnavailable as e:
        got, note = None, f" (LiDAR not used: {e})"
    if got is not None:
        grid, ext, cell, label = got
        if np.isnan(grid).any():          # LiDAR no-data: Terrain 50 under it, not 0 m pits
            grid, label = _fill_gaps(grid, ext, cell, label, source)
        return _finish(grid, ext, cell, label, max_points, enlarge=False)   # LiDAR is already fine
    br = _br()
    src = br.find_terrain(source if source is not None else DEFAULT_SOURCE)
    if src is None:
        raise TerrainUnavailable(
            f"OS Terrain 50 (ASCII Grid) not found in {source or DEFAULT_SOURCE}. Download it from "
            f"{br.TERRAIN_URL} and put the zip there (see build_map_layers).")
    grid, ext, cell, label = _terrain50(extent, max_points, Path(src))
    return _finish(grid, ext, cell, label + note, max_points)


# ---------------------------------------------------------------- scale and records
def sensible_exaggeration(grid, extent) -> float:
    """Vertical exaggeration making the height range about 12 % of the view width, 1 to 10."""
    z = np.asarray(grid, dtype=np.float64)
    rng = float(np.nanmax(z) - np.nanmin(z)) if z.size else 0.0
    width = max(extent[2] - extent[0], extent[3] - extent[1])
    if rng <= 1e-6:
        return 10.0
    return float(min(10.0, max(1.0, 0.12 * width / rng)))


def columns_for_squares(squares, grid, extent, cell_m: float, detail: bool = False):
    """(e, n, ground_height, count) for each recorded square whose centre is inside the extent.
    detail=True: (e, n, ground_height, count, label, size_m). Heights from the cell under the centre."""
    e0, n0, e1, n1 = extent
    ny, nx = grid.shape
    out = []
    for label, sq in (squares or {}).items():
        b = gs.square_bounds(label)
        count = (sq or {}).get("count", 0)
        if not b or not count or count <= 0:
            continue
        e, n = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        if not (e0 <= e < e1 and n0 <= n < n1):
            continue
        col = min(nx - 1, max(0, int((e - e0) // cell_m)))
        row = min(ny - 1, max(0, int((n1 - n) // cell_m)))
        h = float(grid[row, col])
        out.append((e, n, h, count, label, b[2] - b[0]) if detail else (e, n, h, count))
    return out
