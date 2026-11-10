"""Value grids: a compact grid of numbers drawn as a shaded image (25 Oct 2026).

For the Met Office HadUK-Grid 1991-2020 averages (rainfall, temperature, sunshine, ground
frost), made from NetCDF by scripts/build_env_layers.py. The app reads only this compact form,
with numpy (already used by the place names): data/maps/layers/<key>_gb.json (the header) and
<key>_gb.bin (uint16, little-endian, row 0 = the north edge). value = raw * scale + offset;
raw == nodata (65535) is no data.

Header: layer, kind "grid", lod "gb", extent [e0, n0, e1, n1] (OSGB metres, cell edges), cell_m,
width, height, nodata, scale, offset, units, label (what Identify calls it), decimals, lo / hi (the
values the colour ramp spans), attribution, source, built. Display only.
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple

import numpy as np

NODATA = 65535
GRID_OPACITY = 0.8
_CACHE: Dict[tuple, Optional["ValueGrid"]] = {}
_IMAGES: Dict[tuple, object] = {}
_LOCK = threading.RLock()


@dataclass
class ValueGrid:
    raw: np.ndarray                         # uint16, shape (height, width), row 0 north
    extent: Tuple[float, float, float, float]
    cell_m: float
    scale: float
    offset: float
    units: str
    label: str
    decimals: int = 0
    lo: float = 0.0
    hi: float = 1.0
    nodata: int = NODATA
    attribution: str = ""
    _stamp: tuple = field(default=(), repr=False)

    def value_at(self, e: float, n: float) -> Optional[float]:
        """The value of the cell holding (e, n); None outside the grid or in a no-data cell."""
        e0, n0, e1, n1 = self.extent
        if not (e0 <= e < e1 and n0 < n <= n1):
            return None
        col = int((e - e0) // self.cell_m)
        row = int((n1 - n) // self.cell_m)
        h, w = self.raw.shape
        if not (0 <= row < h and 0 <= col < w):
            return None
        r = int(self.raw[row, col])
        return None if r == self.nodata else r * self.scale + self.offset

    def format_value(self, v: float) -> str:
        text = f"{v:,.{self.decimals}f}"
        return f"{text} {self.units}".strip()

    def identify(self, e: float, n: float) -> Optional[Tuple[str, str]]:
        """("Mean annual rainfall", "680 mm") at the point, or None when there is no value."""
        v = self.value_at(e, n)
        return None if v is None else (self.label, self.format_value(v))

    def legend_text(self) -> str:
        """e.g. "Mean annual rainfall: 500 mm (palest) to 2,800 mm (darkest)"."""
        return f"{self.label}: {self.format_value(self.lo)} (palest) to {self.format_value(self.hi)} (darkest)"


# ---- writing (the build script, tests) ----
def write(out_dir, key: str, values: np.ndarray, extent: Sequence[float], cell_m: float, *,
          scale: float, offset: float, units: str, label: str, decimals: int = 0,
          attribution: str = "", source: str = "") -> Path:
    """Write `values` (float array, NaN = no data, row 0 north) as <key>_gb.bin + <key>_gb.json in
    out_dir; returns the header path. Values that do not fit in 0..65534 raw raise ValueError."""
    vals = np.asarray(values, dtype="float64")
    ok = np.isfinite(vals)
    raw = np.full(vals.shape, NODATA, dtype="<u2")
    r = np.rint((vals[ok] - offset) / scale)
    if r.size and (r.min() < 0 or r.max() >= NODATA):
        raise ValueError(f"{key}: values {vals[ok].min()}..{vals[ok].max()} do not fit "
                         f"scale {scale}, offset {offset}")
    raw[ok] = r.astype("<u2")
    good = vals[ok]
    lo, hi = (float(np.percentile(good, 1)), float(np.percentile(good, 99))) if good.size else (0.0, 1.0)
    h, w = raw.shape
    doc = {"layer": key, "kind": "grid", "lod": "gb", "extent": [float(v) for v in extent],
           "cell_m": float(cell_m), "width": w, "height": h, "nodata": NODATA, "scale": scale,
           "offset": offset, "units": units, "label": label, "decimals": decimals,
           "lo": lo, "hi": hi, "attribution": attribution, "source": source,
           "built": date.today().isoformat(), "features": []}
    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    binp, jp = d / f"{key}_gb.bin", d / f"{key}_gb.json"
    for target, data in ((binp, raw.tobytes()), (jp, json.dumps(doc, ensure_ascii=False).encode("utf-8"))):
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, target)
    return jp


# ---- reading ----
def load(maps_dir, key: str) -> Optional[ValueGrid]:
    """The grid for a layer key, cached per file; None if not installed or unreadable."""
    from shared.maps import layers
    meta = layers.file_path(maps_dir, key, "gb")
    if meta is None:
        return None
    binp = meta.with_suffix(".bin")
    try:
        ck = (str(meta), meta.stat().st_mtime_ns, binp.stat().st_mtime_ns)
        with _LOCK:
            if ck not in _CACHE:
                doc = json.loads(meta.read_text(encoding="utf-8"))
                raw = np.fromfile(binp, dtype="<u2").reshape(int(doc["height"]), int(doc["width"]))
                _CACHE[ck] = ValueGrid(raw, tuple(float(v) for v in doc["extent"]),
                                       float(doc["cell_m"]), float(doc["scale"]), float(doc["offset"]),
                                       str(doc.get("units", "")), str(doc.get("label", key)),
                                       int(doc.get("decimals", 0)), float(doc.get("lo", 0)),
                                       float(doc.get("hi", 1)), int(doc.get("nodata", NODATA)),
                                       str(doc.get("attribution", "")), ck)
            return _CACHE[ck]
    except Exception:
        return None


def ramp_lut(stops) -> np.ndarray:
    """256 x 4 uint8 (B, G, R, A premultiplied order for ARGB32 little-endian) from colour stops
    (QColors), blended linearly."""
    cols = np.array([[c.blue(), c.green(), c.red()] for c in stops], dtype="float64")
    xs = np.linspace(0, 1, len(cols))
    t = np.linspace(0, 1, 256)
    lut = np.zeros((256, 4), dtype="uint8")
    alpha = round(255 * GRID_OPACITY)
    for i in range(3):
        lut[:, i] = np.rint(np.interp(t, xs, cols[:, i]) * alpha / 255)
    lut[:, 3] = alpha
    return lut


def image_for(grid: ValueGrid, stops):
    """The grid as a premultiplied ARGB32 QImage (cached per file and colours); no-data cells clear."""
    from PySide6.QtGui import QImage
    key = (grid._stamp, tuple(c.name() for c in stops))
    with _LOCK:
        if key not in _IMAGES:
            span = max(grid.hi - grid.lo, 1e-9)
            vals = grid.raw.astype("float64") * grid.scale + grid.offset
            idx = np.clip(np.rint((vals - grid.lo) / span * 255), 0, 255).astype(np.intp)
            px = ramp_lut(stops)[idx]                       # (h, w, 4) bytes B, G, R, A
            px[grid.raw == grid.nodata] = 0
            h, w = grid.raw.shape
            data = np.ascontiguousarray(px)
            img = QImage(data.data, w, h, w * 4, QImage.Format.Format_ARGB32_Premultiplied).copy()
            if len(_IMAGES) >= 4:                           # four grids at most are kept
                _IMAGES.pop(next(iter(_IMAGES)))
            _IMAGES[key] = img
        return _IMAGES[key]


def draw(p, grid: ValueGrid, stops, to_px):
    """Draw the grid through `to_px` (OSGB metres -> pixels, y flipped; map_layers.layer_transform)."""
    img = image_for(grid, stops)
    e0, n0, e1, n1 = grid.extent
    p.save()
    p.setWorldTransform(to_px, True)
    p.translate(e0, n1)
    p.scale((e1 - e0) / img.width(), -(n1 - n0) / img.height())
    p.setRenderHint(p.RenderHint.SmoothPixmapTransform, False)
    p.setCompositionMode(p.CompositionMode.CompositionMode_SourceOver)
    p.drawImage(0, 0, img)
    p.restore()
