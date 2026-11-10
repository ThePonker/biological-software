"""On-disk cache for the Mapping tab's slow, deterministic vice-county work (R16, 10 Nov 2026).

Every start of the app re-read and re-projected data/maps/vc_brc_wgs84.geojson (15.7 MB, ~2 s) and
re-worked out the shared-border rings, the unique chains and the coast / inland split (~2.3 s).
The results never change unless the source file or the code does, so they are kept as .npz files
(numpy arrays only, no pickle) in a `cache` folder next to the source file (data/maps/cache/, under
data/, which git ignores).

A file is used only when the stamp inside it matches: the source file's size and modification time
in nanoseconds, CODE_VERSION (raise it whenever load_vc_polygons, snap_rings, unique_chains or the
coast split change what they return) and the settings that went into the result (the thinning
tolerance, ...). A missing, stale, damaged or unreadable file is ignored and the work is done
again; the new file is written through a temporary file and os.replace, so a reader never sees half
a file and a failed write (read-only folder) is silently skipped. BIOSOFT_NO_MAP_CACHE=1 turns the
cache off (tests that compare two computed results).

Points come back as the same floats the computed lists held (float64 arrays), as tuples, in the
same order, so a cached result equals the computed one exactly. Display only.
"""
from __future__ import annotations

import os
import threading
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

CODE_VERSION = 1            # raise when the cached algorithms change what they return
CACHE_DIRNAME = "cache"
_LOCK = threading.Lock()


def enabled() -> bool:
    return os.environ.get("BIOSOFT_NO_MAP_CACHE", "") not in ("1", "true", "yes")


def stamp(source, *extra) -> Optional[str]:
    """The text a cache file must carry to match `source` (a file) and the settings `extra`;
    None when the source cannot be read (then nothing is cached)."""
    try:
        st = os.stat(source)
    except OSError:
        return None
    return "|".join(["v%d" % CODE_VERSION, str(st.st_size), str(st.st_mtime_ns), *map(str, extra)])


def cache_path(source, name: str) -> Path:
    p = Path(source)
    return p.parent / CACHE_DIRNAME / f"{p.stem}.{name}.npz"


def load(source, name: str, *extra) -> Optional[Dict[str, np.ndarray]]:
    """The arrays saved by save() for this source and settings, or None."""
    if not enabled():
        return None
    want = stamp(source, *extra)
    if want is None:
        return None
    try:
        with np.load(cache_path(source, name), allow_pickle=False) as z:
            if str(z["stamp"][0]) != want:
                return None
            return {k: z[k] for k in z.files if k != "stamp"}
    except Exception:
        return None


def save(source, name: str, arrays: Dict[str, np.ndarray], *extra) -> bool:
    """Write the arrays (atomically). True when written; never raises."""
    if not enabled():
        return False
    want = stamp(source, *extra)
    if want is None:
        return False
    target = cache_path(source, name)
    tmp = target.with_name(f"{target.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        with _LOCK:
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(tmp, "wb") as fh:
                np.savez(fh, stamp=np.array([want]), **arrays)
            os.replace(tmp, target)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- lists of points <-> arrays

def _points(arr: np.ndarray) -> List[Tuple[float, float]]:
    return list(zip(arr[:, 0].tolist(), arr[:, 1].tolist()))


def pack_lines(lines: Sequence[Sequence]) -> Dict[str, np.ndarray]:
    """Polylines / rings (lists of (e, n)) as {"off": (L+1,), "xy": (P, 2) float64}."""
    off = np.zeros(len(lines) + 1, dtype=np.int64)
    if lines:
        off[1:] = np.cumsum([len(ln) for ln in lines], dtype=np.int64)
    flat = [pt for ln in lines for pt in ln]
    xy = np.array(flat, dtype=np.float64).reshape(-1, 2) if flat else np.empty((0, 2))
    return {"off": off, "xy": xy}


def unpack_lines(off: np.ndarray, xy: np.ndarray) -> List[List[Tuple[float, float]]]:
    pts = _points(xy)
    o = off.tolist()
    return [pts[o[i]:o[i + 1]] for i in range(len(o) - 1)]


def pack_groups(groups: Dict[int, List[list]]) -> Dict[str, np.ndarray]:
    """{vc: rings} as the arrays of pack_lines plus "vc" (the vc of each ring, in order)."""
    rings, ids = [], []
    for vc, rs in groups.items():
        for r in rs:
            rings.append(r)
            ids.append(vc)
    out = pack_lines(rings)
    out["vc"] = np.array(ids, dtype=np.int64)
    return out


def unpack_groups(a: Dict[str, np.ndarray], prefix: str = "") -> Dict[int, List[list]]:
    rings = unpack_lines(a[prefix + "off"], a[prefix + "xy"])
    out: Dict[int, List[list]] = {}
    for vc, r in zip(a[prefix + "vc"].tolist(), rings):
        out.setdefault(vc, []).append(r)
    return out


def pack_split(coast: Sequence, inland: Sequence) -> Dict[str, np.ndarray]:
    a, b = pack_lines(coast), pack_lines(inland)
    return {"c_off": a["off"], "c_xy": a["xy"], "i_off": b["off"], "i_xy": b["xy"]}


def unpack_split(a: Dict[str, np.ndarray]):
    return unpack_lines(a["c_off"], a["c_xy"]), unpack_lines(a["i_off"], a["i_xy"])
