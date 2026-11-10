"""Optional finer heights for the 3D view: GeoTIFF DTM tiles (Environment Agency 1 m / 2 m,
OSGB) in data/maps/lidar/ (terrain.LIDAR_DIR). Used only when the tiles cover the whole view.

Georeferencing comes from the GeoTIFF tags (ModelPixelScale + ModelTiepoint, pixel = area) or a
world file beside the tile (.tfw / .tifw / .wld; its x, y are the CENTRE of the top left pixel).
`tifffile` is imported lazily: if it is missing the view says so and uses Terrain 50.
Read only; nothing is written.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import List, NamedTuple, Optional

import numpy as np

MAX_VIEW_M = 10_000      # LiDAR is used only for a view no longer than this (longer side)
SCALE_TAG, TIEPOINT_TAG, NODATA_TAG = 33550, 33922, 42113
WORLD_SUFFIXES = (".tfw", ".tifw", ".wld")
_INDEX = {}
_LOCK = threading.RLock()


class LidarUnavailable(Exception):
    """LiDAR tiles are not usable (not installed, not covering, unreadable); say why."""


class LidarTile(NamedTuple):
    path: Path
    x0: float            # west edge
    y1: float            # north edge
    cell: float
    w: int
    h: int
    nodata: float

    @property
    def bounds(self):
        return self.x0, self.y1 - self.h * self.cell, self.x0 + self.w * self.cell, self.y1


def _tifffile():
    try:
        import tifffile
        return tifffile
    except Exception:
        return None


def _world_file(path: Path):
    for suf in WORLD_SUFFIXES:
        w = path.with_suffix(suf)
        if w.exists():
            v = [float(x) for x in w.read_text().split()[:6]]
            if len(v) == 6:
                return v
    return None


def _describe(tf, path: Path) -> Optional[LidarTile]:
    with tf.TiffFile(str(path)) as t:
        page = t.pages[0]
        h, w = page.shape[:2]
        tags = page.tags
        nodata = -9999.0
        if NODATA_TAG in tags:
            try:
                nodata = float(str(tags[NODATA_TAG].value).strip("\x00 "))
            except ValueError:
                pass
        if SCALE_TAG in tags and TIEPOINT_TAG in tags:
            sx, sy = (float(v) for v in tags[SCALE_TAG].value[:2])
            tp = [float(v) for v in tags[TIEPOINT_TAG].value[:6]]
            x0, y1 = tp[3] - tp[0] * sx, tp[4] + tp[1] * sy
        else:
            wf = _world_file(path)
            if not wf:
                return None
            sx, sy = wf[0], abs(wf[3])
            x0, y1 = wf[4] - sx / 2, wf[5] + sy / 2
        if abs(sx - sy) > 1e-6 or sx <= 0:
            return None
        return LidarTile(path, x0, y1, sx, w, h, nodata)


def index(folder: Path, tf) -> List[LidarTile]:
    """The tiles in `folder` (cached per folder and file times)."""
    files = sorted(p for p in folder.rglob("*") if p.suffix.lower() in (".tif", ".tiff"))
    key = (str(folder), tuple((p.name, p.stat().st_mtime_ns) for p in files))
    with _LOCK:
        if key not in _INDEX:
            _INDEX.clear()
            tiles = []
            for p in files:
                try:
                    d = _describe(tf, p)
                except Exception:
                    d = None
                if d:
                    tiles.append(d)
            _INDEX[key] = tiles
        return _INDEX[key]


def _bin_sum(vals, x0, y1, cell, e0, n1, c, nx, ny):
    """Add one tile's values into (sum, count) arrays of the output grid (row 0 = north)."""
    h, w = vals.shape
    cols = np.floor((x0 + (np.arange(w) + 0.5) * cell - e0) / c).astype(int)
    rows = np.floor((n1 - (y1 - (np.arange(h) + 0.5) * cell)) / c).astype(int)
    cm, rm = (cols >= 0) & (cols < nx), (rows >= 0) & (rows < ny)
    if not cm.any() or not rm.any():
        return None
    vals, cols, rows = vals[rm][:, cm], cols[cm], rows[rm]
    ok = ~np.isnan(vals)
    v = np.where(ok, vals, 0.0).astype(np.float64)
    cnt = ok.astype(np.float64)
    rs = np.r_[0, np.flatnonzero(np.diff(rows)) + 1]
    cs = np.r_[0, np.flatnonzero(np.diff(cols)) + 1]
    s = np.add.reduceat(np.add.reduceat(v, rs, axis=0), cs, axis=1)
    n = np.add.reduceat(np.add.reduceat(cnt, rs, axis=0), cs, axis=1)
    return rows[rs], cols[cs], s, n


def read_window(tf, path, r0, r1, c0, c1):
    """Rows r0:r1, columns c0:c1 of the tile as float32. Only that window is decoded when tifffile
    can give a lazy view (zarr installed); else the tile is read whole and sliced."""
    try:
        import zarr
        with tf.TiffFile(str(path)) as t:
            arr = zarr.open(t.aszarr(), mode="r")
            return np.asarray(arr[r0:r1, c0:c1], dtype=np.float32)
    except Exception:
        return np.asarray(tf.imread(str(path)), dtype=np.float32)[r0:r1, c0:c1]


def lidar_heights(extent, max_points: int, folder: Path):
    """(grid north-first with NaN for no data, extent, cell_m, label) from tiles covering the
    whole extent, or None if the folder is absent / empty. Raises LidarUnavailable when tiles are
    there but cannot be used (tifffile missing, gaps, unreadable)."""
    folder = Path(folder)
    if max(extent[2] - extent[0], extent[3] - extent[1]) > MAX_VIEW_M:
        return None                 # too wide for LiDAR: Terrain 50 is used, quietly
    if not folder.is_dir() or not any(p.suffix.lower() in (".tif", ".tiff") for p in folder.rglob("*")):
        return None
    tf = _tifffile()
    if tf is None:
        raise LidarUnavailable("tifffile is not installed: py -3.14 -m pip install tifffile imagecodecs")
    tiles = index(folder, tf)
    ex0, en0, ex1, en1 = (float(v) for v in extent)
    hit = [t for t in tiles if t.bounds[0] < ex1 and t.bounds[2] > ex0 and t.bounds[1] < en1
           and t.bounds[3] > en0]
    if not hit:
        raise LidarUnavailable("no LiDAR tile touches this area")
    native = min(t.cell for t in hit)
    long_m = max(ex1 - ex0, en1 - en0)
    f = 1
    while long_m / (native * f) > max_points:
        f += 1
    c = native * f
    e0, n0 = np.floor(ex0 / c) * c, np.floor(en0 / c) * c
    e1, n1 = max(np.ceil(ex1 / c), np.floor(ex0 / c) + 1) * c, max(np.ceil(en1 / c), np.floor(en0 / c) + 1) * c
    nx, ny = int(round((e1 - e0) / c)), int(round((n1 - n0) / c))
    xs, ys = e0 + (np.arange(nx) + 0.5) * c, n1 - (np.arange(ny) + 0.5) * c
    covered = np.zeros((ny, nx), bool)
    for t in hit:
        b = t.bounds
        covered |= ((ys[:, None] >= b[1]) & (ys[:, None] < b[3]) & (xs[None, :] >= b[0])
                    & (xs[None, :] < b[2]))
    if not covered.all():
        raise LidarUnavailable("the LiDAR tiles do not cover the whole view")
    tot, num = np.zeros((ny, nx)), np.zeros((ny, nx))
    for t in hit:
        c0, c1 = max(0, int(np.floor((e0 - t.x0) / t.cell))), min(t.w, int(np.ceil((e1 - t.x0) / t.cell)))
        r0, r1 = max(0, int(np.floor((t.y1 - n1) / t.cell))), min(t.h, int(np.ceil((t.y1 - n0) / t.cell)))
        if c1 <= c0 or r1 <= r0:
            continue
        try:
            z = read_window(tf, t.path, r0, r1, c0, c1)      # only the part inside the view
        except Exception as e:
            raise LidarUnavailable(f"{t.path.name} unreadable ({e}); imagecodecs may be needed")
        z = np.where((z == t.nodata) | (z < -1000), np.nan, z)
        r = _bin_sum(z, t.x0 + c0 * t.cell, t.y1 - r0 * t.cell, t.cell, e0, n1, c, nx, ny)
        if r is not None:
            rows, cols, s, n = r
            tot[np.ix_(rows, cols)] += s
            num[np.ix_(rows, cols)] += n
    with np.errstate(invalid="ignore", divide="ignore"):
        grid = np.where(num > 0, tot / np.maximum(num, 1), np.nan).astype(np.float32)
    label = f"LiDAR DTM ({len(hit)} tile(s)), {c:g} m cells"
    return grid, (float(e0), float(n0), float(e1), float(n1)), float(c), label
