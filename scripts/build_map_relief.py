"""The Mapping tab's "Relief" layer: a hillshade made from OS Terrain 50 (ASCII Grid), for
scripts/build_map_layers.py (18 Oct 2026).

Terrain 50 comes as one zip (about 157 MB) holding a zip per 100 km square, each holding the
10 km .asc tiles at 50 m. They are read WITHOUT extracting anything (zipfile; a zip inside a zip
is opened from memory), averaged down to a 250 m grid for the whole of GB, shaded (the standard
hillshade, light from 315 degrees at 45 degrees up) and written as relief_gb.png (greyscale with
alpha) + relief_gb.json (OSGB extent, cell size, attribution) in the layers folder.

The grey is scaled so level ground is white (255): the map draws it MULTIPLIED at low opacity,
so only slopes away from the light darken the land. Sea (no data, or exactly 0.0 m) is clear.
Read only on the source; the only files written are the two in the output folder.
"""
import io
import json
import os
import struct
import zipfile
import zlib
from datetime import date
from pathlib import Path

import numpy as np

TERRAIN_URL = "https://osdatahub.os.uk/downloads/open/Terrain50"
CELL_M = 250                      # the grid the shading is made on
AZIMUTH, ALTITUDE = 315.0, 45.0   # the light, degrees (compass bearing; up from the horizon)
Z_FACTOR = 2.0                    # height exaggeration: at 250 m cells UK slopes are gentle
GB_E, GB_N = 700000, 1300000      # the grid's top right corner (OSGB, metres); its origin is 0, 0
MAX_ZIP_DEPTH = 4
NAME = "relief"


# ---- finding and reading the source (nothing is extracted) ----
def _squash(name):
    return "".join(ch for ch in name.lower() if ch.isalnum())


def find_terrain(source):
    """A Terrain 50 zip (its name has "terr50" / "terrain50") or a folder holding .asc files,
    searched for under `source` (which may itself be one); None if there is none."""
    src = Path(source)
    if src.is_file() and src.suffix.lower() == ".zip":
        return src
    if not src.is_dir():
        return None
    for z in sorted(src.rglob("*.zip")):
        if any(w in _squash(z.name) for w in ("terr50", "terrain50")):
            return z
    for asc in sorted(src.rglob("*.asc")):
        return asc.parent
    return None


def _walk_zip(zf, depth=0):
    for info in zf.infolist():
        low = info.filename.lower()
        if low.endswith(".asc"):
            yield info.filename, zf.read(info)
        elif low.endswith(".zip") and depth < MAX_ZIP_DEPTH:
            with zipfile.ZipFile(io.BytesIO(zf.read(info))) as inner:
                yield from _walk_zip(inner, depth + 1)


def iter_tiles(path):
    """(name, bytes) of every .asc tile in a zip, a folder of zips / .asc files, nested or not."""
    p = Path(path)
    if p.is_file():
        with zipfile.ZipFile(p) as zf:
            yield from _walk_zip(zf)
        return
    for f in sorted(p.rglob("*")):
        if f.suffix.lower() == ".asc":
            yield f.name, f.read_bytes()
        elif f.suffix.lower() == ".zip":
            with zipfile.ZipFile(f) as zf:
                yield from _walk_zip(zf)


def parse_asc(data):
    """(heights as a float32 array [rows, cols] with NaN for no data, xll, yll, cellsize) of an
    ESRI ASCII grid tile."""
    head, hdr = {}, 0
    parts = data.split(b"\n", 12)
    for line in parts[:-1]:
        tok = line.split()
        if len(tok) != 2 or not tok[0][:1].isalpha():
            break
        head[tok[0].decode("ascii").lower()] = float(tok[1])
        hdr += 1
    body = b"\n".join(parts[hdr:])
    ncols, nrows, cell = int(head["ncols"]), int(head["nrows"]), head["cellsize"]
    xll = head["xllcorner"] if "xllcorner" in head else head["xllcenter"] - cell / 2
    yll = head["yllcorner"] if "yllcorner" in head else head["yllcenter"] - cell / 2
    z = np.fromstring(body, dtype=np.float32, sep=" ")
    if z.size != ncols * nrows:
        raise ValueError(f"{z.size} values, expected {ncols * nrows}")
    z = z.reshape(nrows, ncols)
    nodata = head.get("nodata_value", -9999.0)
    z[z == nodata] = np.nan
    return z, xll, yll, cell


def block_mean(z, f):
    """z averaged over f x f blocks (NaN ignored; all-NaN block: NaN)."""
    r, c = (z.shape[0] // f) * f, (z.shape[1] // f) * f
    b = z[:r, :c].reshape(r // f, f, c // f, f)
    ok = ~np.isnan(b)
    n = ok.sum(axis=(1, 3))
    tot = np.where(ok, b, 0.0).sum(axis=(1, 3), dtype=np.float64)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(n > 0, tot / np.maximum(n, 1), np.nan).astype(np.float32)


def mosaic(tiles, cell=CELL_M, report=print):
    """(grid [rows, cols] of heights at `cell` metres with NaN for no data, extent (e0, n0, e1, n1),
    tiles used, tiles skipped), cropped to the tiles read."""
    grid = np.full((GB_N // cell, GB_E // cell), np.nan, np.float32)
    used = skipped = 0
    box = [10 ** 9, 10 ** 9, -1, -1]            # col0, row0, col1, row1
    for name, data in tiles:
        try:
            z, xll, yll, csize = parse_asc(data)
            f = round(cell / csize)
            if abs(f * csize - cell) > 1e-6:
                raise ValueError(f"cell {csize} m does not divide {cell} m")
            m = block_mean(z, f)
            c0 = round(xll / cell)
            r0 = round((GB_N - (yll + z.shape[0] * csize)) / cell)
            if c0 < 0 or r0 < 0 or c0 + m.shape[1] > grid.shape[1] or r0 + m.shape[0] > grid.shape[0]:
                raise ValueError("outside the GB grid")
        except Exception as e:
            skipped += 1
            report(f"  skipped {name}: {e}")
            continue
        grid[r0:r0 + m.shape[0], c0:c0 + m.shape[1]] = m
        box = [min(box[0], c0), min(box[1], r0), max(box[2], c0 + m.shape[1]),
               max(box[3], r0 + m.shape[0])]
        used += 1
        if used % 500 == 0:
            report(f"      ... {used} tiles read")
    if not used:
        return None, None, 0, skipped
    c0, r0, c1, r1 = box
    return (grid[r0:r1, c0:c1].copy(), (c0 * cell, GB_N - r1 * cell, c1 * cell, GB_N - r0 * cell),
            used, skipped)


# ---- shading ----
def hillshade(z, cell=CELL_M, azimuth=AZIMUTH, altitude=ALTITUDE, z_factor=Z_FACTOR):
    """(grey uint8, alpha uint8) for heights z (NaN: no data). The standard hillshade (3 x 3
    Horn gradients), divided by the shade of level ground so that is 255; alpha 0 where there
    is no data or the height is exactly 0.0 (sea)."""
    land = ~np.isnan(z) & (z != 0.0)
    zp = np.pad(np.where(np.isnan(z), 0.0, z).astype(np.float64), 1, mode="edge")
    a, b, c = zp[:-2, :-2], zp[:-2, 1:-1], zp[:-2, 2:]
    d, f = zp[1:-1, :-2], zp[1:-1, 2:]
    g, h, i = zp[2:, :-2], zp[2:, 1:-1], zp[2:, 2:]
    dx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * cell)
    dy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8 * cell)
    slope = np.arctan(z_factor * np.hypot(dx, dy))
    aspect = np.arctan2(dy, -dx)
    zen = np.radians(90.0 - altitude)
    az = np.radians((360.0 - azimuth + 90.0) % 360.0)
    shade = np.cos(zen) * np.cos(slope) + np.sin(zen) * np.sin(slope) * np.cos(az - aspect)
    grey = np.clip(shade / np.cos(zen), 0.0, 1.0)
    return (np.where(land, np.round(grey * 255), 255).astype(np.uint8),
            np.where(land, 255, 0).astype(np.uint8))


def write_png_la(path, grey, alpha):
    """An 8-bit greyscale + alpha PNG (filter "Sub"), written to a temporary file then moved."""
    h, w = grey.shape
    rows = np.stack([grey, alpha], axis=2).reshape(h, w * 2)
    sub = rows.copy()
    sub[:, 2:] = rows[:, 2:] - rows[:, :-2]
    raw = np.empty((h, w * 2 + 1), np.uint8)
    raw[:, 0] = 1
    raw[:, 1:] = sub

    def chunk(kind, body):
        return (struct.pack(">I", len(body)) + kind + body
                + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF))
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 4, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw.tobytes(), 6)) + chunk(b"IEND", b""))
    tmp = Path(str(path) + ".tmp")
    tmp.write_bytes(png)
    os.replace(tmp, path)


# ---- the build ----
def build_relief(source, out_dir, attribution, apply, explicit=True) -> int:
    """Make relief_gb.png + relief_gb.json from the Terrain 50 found under `source`. Returns
    1 for a problem, else 0 (a missing source is only a problem when relief was asked for)."""
    src = find_terrain(source)
    if src is None:
        print(f"\n{'Missing source' if explicit else 'Relief skipped'}: OS Terrain 50 (ASCII Grid; no "
              f"terr50 / terrain50 zip or folder of .asc files in {source}).\n  Download: {TERRAIN_URL}"
              f"\n  Put the zip in {source} (do not unzip it) and run this again.")
        return 1 if explicit else 0
    print(f"\n  OS Terrain 50: {src}")
    if not apply:
        print(f"  relief_gb: would read it without extracting, {CELL_M} m grid, hillshade "
              f"{AZIMUTH:.0f} deg / {ALTITUDE:.0f} deg")
        return 0
    print(f"\n[relief / gb] {CELL_M} m grid, light {AZIMUTH:.0f} deg at {ALTITUDE:.0f} deg", flush=True)
    grid, extent, used, skipped = mosaic(iter_tiles(src))
    if grid is None:
        print("  relief_gb: no usable tiles found.")
        return 1
    grey, alpha = hillshade(grid)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_png_la(out / f"{NAME}_gb.png", grey, alpha)
    doc = {"layer": NAME, "lod": "gb", "kind": "image", "image": f"{NAME}_gb.png",
           "extent": list(extent), "cell_m": CELL_M, "width": int(grid.shape[1]),
           "height": int(grid.shape[0]), "azimuth": AZIMUTH, "altitude": ALTITUDE,
           "z_factor": Z_FACTOR, "source": f"OS Terrain 50 ({Path(src).name}), {used} tiles",
           "attribution": attribution, "built": date.today().isoformat()}
    target = out / f"{NAME}_gb.json"
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps(doc, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, target)
    print(f"  relief_gb: {used} tiles read ({skipped} skipped), {grid.shape[1]} x {grid.shape[0]} cells, "
          f"{(out / (NAME + '_gb.png')).stat().st_size:,} bytes png", flush=True)
    return 0
