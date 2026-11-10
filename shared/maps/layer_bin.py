"""Binary form of the map layer files, and paths built from plain arrays (25 Oct 2026).

Next to each data/maps/layers/<key>_<lod>.json the build scripts (and scripts/convert_layers_bin.py)
write the same layer as a handful of numpy files:
    <key>_<lod>.coords.npy  (P, 2) the points, int32 OSGB metres (float64 if any is not whole)
    <key>_<lod>.ring.npy    (R+1)  where each ring / line / point starts in coords
    <key>_<lod>.feat.npy    (F+1)  where each feature's rings start in ring
    <key>_<lod>.bbox.npy    (F, 4) e0, n0, e1, n1
    <key>_<lod>.cls.npy     (F)    uint16 index into the meta's classes (65535: the feature has no "t")
    <key>_<lod>.kind.npy    (F)    uint8: 0 polygon rings, 1 line, 2 point
    <key>_<lod>.meta.json   the JSON header fields, "classes", and the per-feature lists "n", "name",
                            "a", "u" (each F long, null where the feature has none; [] when no feature has one),
                            "src_size" (bytes of the JSON it was made from: a changed JSON is not matched)
The JSON stays the master and the fallback: a missing, partial or stale binary is ignored.

Why: json.load of a big county layer took 0.7-3.8 s, held 300 MB of Python lists and froze the screen;
building a QPainterPath from one QPointF per point also crashed Python 3.14.0's garbage collector on
Wil's PC. Here a path is built from the arrays in one go: Qt's own serialised QPainterPath written with
numpy and read back with QDataStream (element type, x, y, then the last sub-path's start and the fill rule).
Display only.
"""
from __future__ import annotations

import json
import os
import struct
from collections.abc import Mapping
from itertools import chain
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
from PySide6.QtCore import QByteArray, QDataStream, QIODevice, Qt
from PySide6.QtGui import QPainterPath

ARRAYS = ("coords", "ring", "feat", "bbox", "cls", "kind")
NO_CLASS = 65535
POLY, LINE, POINT = 0, 1, 2
_GEOM = {POLY: "rings", LINE: "line", POINT: "pt"}
_REC = np.dtype([("t", ">i4"), ("x", ">f8"), ("y", ">f8")])
_WINDING = int(Qt.FillRule.WindingFill.value)
_ODD = int(Qt.FillRule.OddEvenFill.value)


def array_path(json_path, name: str) -> Path:
    p = Path(json_path)
    return p.with_name(f"{p.stem}.{name}.npy")


def meta_path(json_path) -> Path:
    p = Path(json_path)
    return p.with_name(f"{p.stem}.meta.json")


def all_paths(json_path) -> List[Path]:
    return [array_path(json_path, a) for a in ARRAYS] + [meta_path(json_path)]


def _tight(a: np.ndarray) -> np.ndarray:
    """int32 when every value is a whole number that fits, else float64."""
    a = np.asarray(a, dtype=np.float64)
    if a.size == 0 or (np.array_equal(a, np.rint(a)) and np.abs(a).max() < 2 ** 31):
        return a.astype(np.int32)
    return a


def bbox_array(boxes: Sequence) -> np.ndarray:
    """(F, 4) of boxes (None: no box, which meets every test), int32 when they are whole numbers."""
    miss = [b is None for b in boxes]
    if any(miss):
        a = np.array([[-np.inf, -np.inf, np.inf, np.inf] if b is None else b for b in boxes],
                     dtype=np.float64)
        return a
    return _tight(np.array(boxes, dtype=np.float64).reshape(-1, 4))


def _kind_of(f: dict) -> int:
    return POLY if f.get("rings") else LINE if f.get("line") else POINT


def _geometry(f: dict, kind: int) -> List[list]:
    if kind == POLY:
        return list(f["rings"])
    return [f["line"]] if kind == LINE else [[f["pt"]]]


def from_features(feats: Sequence[dict], header: dict) -> tuple:
    """(arrays, meta) for a list of feature dicts (those with rings, line or pt)."""
    feats = [f for f in feats if isinstance(f, dict) and (f.get("rings") or f.get("line") or f.get("pt"))]
    kinds = np.array([_kind_of(f) for f in feats], dtype=np.uint8)
    rings: List[list] = []
    feat_off = [0]
    for f, k in zip(feats, kinds):
        rings.extend(_geometry(f, int(k)))
        feat_off.append(len(rings))
    ring_off = np.zeros(len(rings) + 1, dtype=np.int64)
    ring_off[1:] = np.cumsum([len(r) for r in rings], dtype=np.int64)
    flat = list(chain.from_iterable(rings))
    coords = _tight(np.array(flat, dtype=np.float64).reshape(-1, 2) if flat else np.empty((0, 2)))
    boxes = [f.get("bbox") for f in feats]
    if any(b is None for b in boxes):                   # worked out from the points
        for i, b in enumerate(boxes):
            if b is None:
                pts = coords[ring_off[feat_off[i]]:ring_off[feat_off[i + 1]]]
                boxes[i] = [pts[:, 0].min(), pts[:, 1].min(), pts[:, 0].max(), pts[:, 1].max()]
    classes: Dict[str, int] = {}
    cls = np.full(len(feats), NO_CLASS, dtype=np.uint16)
    for i, f in enumerate(feats):
        if f.get("t") is not None:
            cls[i] = classes.setdefault(str(f["t"]), len(classes))
    meta = dict(header)
    meta["features"], meta["points"], meta["classes"] = len(feats), int(len(coords)), list(classes)
    for k in ("n", "name", "a", "u"):
        vals = [f.get(k) for f in feats]
        meta[k] = vals if any(v is not None for v in vals) else []
    arrays = {"coords": coords, "ring": ring_off, "feat": np.array(feat_off, dtype=np.int64),
              "bbox": bbox_array(boxes), "cls": cls, "kind": kinds}
    return arrays, meta


def write(json_path, feats: Sequence[dict], header: dict) -> None:
    """Write the binary form next to `json_path` (which must already exist: its size is kept to
    tell later that the binary still matches). Arrays first, the meta last; each through a .tmp and
    os.replace. The JSON is only read for its size."""
    arrays, meta = from_features(feats, header)
    meta["src_size"] = Path(json_path).stat().st_size
    for name, arr in arrays.items():
        target = array_path(json_path, name)
        tmp = target.with_name(target.name + ".tmp")
        with open(tmp, "wb") as fh:
            np.save(fh, arr)
        os.replace(tmp, target)
    target = meta_path(json_path)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps(meta, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, target)


def exists(json_path) -> bool:
    return all(p.is_file() for p in all_paths(json_path))


def read(json_path) -> Optional["LayerBin"]:
    """The binary form of a layer file, or None when it is missing, unreadable or made from a
    different JSON (then the caller reads the JSON)."""
    try:
        if not exists(json_path):
            return None
        meta = json.loads(meta_path(json_path).read_text(encoding="utf-8"))
        if meta.get("src_size") != Path(json_path).stat().st_size:
            return None
        arrays = {a: np.load(array_path(json_path, a), allow_pickle=False) for a in ARRAYS}
        lb = LayerBin(arrays, meta)
        return lb if lb.consistent() else None
    except Exception:
        return None


def _ranges(starts: np.ndarray, ends: np.ndarray):
    """The indices starts[0]..ends[0], starts[1]..ends[1] ... in one array, and the lengths."""
    lens = ends - starts
    tot = int(lens.sum())
    if tot == 0:
        return np.empty(0, dtype=np.int64), lens
    offs = np.cumsum(lens) - lens
    return np.repeat(starts - offs, lens) + np.arange(tot), lens


PathBytes = Tuple[Optional[bytes], bool]        # (the serialised path, or None when empty; winding fill)


def polyline_bytes(src: np.ndarray, starts: np.ndarray, ends: np.ndarray, closed: bool,
                   winding: bool = True) -> PathBytes:
    """The numpy half of polyline_path: Qt's serialised QPainterPath of the polylines
    src[starts[i]:ends[i]] (src: (P, 2)) as bytes. No Qt object is made, so it may run off the GUI
    thread (the map's look-ahead, map_ahead.py); path_from_bytes() makes the path (R16)."""
    starts, ends = np.asarray(starts, dtype=np.int64), np.asarray(ends, dtype=np.int64)
    ok = (ends - starts) >= 2
    if not ok.all():
        starts, ends = starts[ok], ends[ok]
    if len(starts) == 0:
        return None, winding
    idx, lens = _ranges(starts, ends)
    if closed:                                  # closeSubpath adds a line back to the start of an open ring
        open_ = (src[starts] != src[ends - 1]).any(axis=1)
        if open_.any():
            idx = np.insert(idx, np.cumsum(lens)[open_], starts[open_])
            lens = lens + open_
    first = np.cumsum(lens) - lens
    rec = np.empty(len(idx), dtype=_REC)
    rec["t"] = 1
    rec["t"][first] = 0
    xy = src[idx]
    rec["x"], rec["y"] = xy[:, 0], xy[:, 1]
    buf = struct.pack(">i", len(idx)) + rec.tobytes() + struct.pack(
        ">ii", int(first[-1]), _WINDING if winding else _ODD)
    return buf, winding


def path_from_bytes(pb: PathBytes) -> QPainterPath:
    """The QPainterPath of polyline_bytes' result."""
    buf, winding = pb
    path = QPainterPath()
    if buf is None:
        path.setFillRule(Qt.FillRule.WindingFill if winding else Qt.FillRule.OddEvenFill)
        return path
    ba = QByteArray(buf)        # kept in a variable: a QDataStream on a temporary one segfaults
    stream = QDataStream(ba, QIODevice.OpenModeFlag.ReadOnly)
    stream >> path
    del stream
    return path


def polyline_path(src: np.ndarray, starts: np.ndarray, ends: np.ndarray, closed: bool,
                  winding: bool = True) -> QPainterPath:
    """One QPainterPath of the polylines src[starts[i]:ends[i]] (src: (P, 2)), the same elements as
    addPolygon of each (and closeSubpath when `closed`); fewer than two points are left out."""
    return path_from_bytes(polyline_bytes(src, starts, ends, closed, winding))


def lists_bytes(polylines: Iterable, closed: bool, winding: bool = True) -> PathBytes:
    """polyline_bytes for lists of [e, n] points (the JSON route)."""
    lines = [ln for ln in polylines]
    lens = np.fromiter((len(ln) for ln in lines), dtype=np.int64, count=len(lines))
    flat = list(chain.from_iterable(lines))
    src = np.array(flat, dtype=np.float64).reshape(-1, 2) if flat else np.empty((0, 2))
    ends = np.cumsum(lens)
    return polyline_bytes(src, ends - lens, ends, closed, winding)


def lists_path(polylines: Iterable, closed: bool, winding: bool = True) -> QPainterPath:
    """polyline_path for lists of [e, n] points (the JSON route): one numpy array, no object per point."""
    return path_from_bytes(lists_bytes(polylines, closed, winding))


class LazyFeature(Mapping):
    """One feature of a LayerBin, read like the dict it stands for ("bbox", "rings" / "line" / "pt",
    "t", "n", "a", "u", "name"); the points are made only when asked for."""
    __slots__ = ("_d", "_i")

    def __init__(self, data: "LayerBin", i: int):
        self._d, self._i = data, i

    def _keys(self) -> List[str]:
        d, i = self._d, self._i
        ks = ["bbox", _GEOM[int(d.kind[i])]]
        if d.cls[i] != NO_CLASS:
            ks.append("t")
        ks.extend(k for k in ("n", "name", "a", "u") if d.meta[k] and d.meta[k][i] is not None)
        return ks

    def __getitem__(self, key):
        d, i = self._d, self._i
        if key == "bbox":
            return d.bbox[i].tolist()
        kind = int(d.kind[i])
        if key == _GEOM[kind]:
            r0, r1 = int(d.feat[i]), int(d.feat[i + 1])
            pts = [d.coords[d.ring[r]:d.ring[r + 1]].tolist() for r in range(r0, r1)]
            return pts if kind == POLY else pts[0] if kind == LINE else pts[0][0]
        if key == "t" and d.cls[i] != NO_CLASS:
            return d.meta["classes"][int(d.cls[i])]
        if key in ("n", "name", "a", "u") and d.meta[key] and d.meta[key][i] is not None:
            return d.meta[key][i]
        raise KeyError(key)

    def __iter__(self):
        return iter(self._keys())

    def __len__(self):
        return len(self._keys())


class LayerBin:
    """A layer read from its binary files. Behaves as a read-only sequence of LazyFeature."""

    def __init__(self, arrays: dict, meta: dict):
        self.coords, self.ring, self.feat = arrays["coords"], arrays["ring"], arrays["feat"]
        self.bbox, self.cls, self.kind = arrays["bbox"], arrays["cls"], arrays["kind"]
        self.meta = meta
        self.header = {k: v for k, v in meta.items()
                       if k not in ("features", "points", "classes", "n", "name", "a", "u", "src_size")}
        self._class_names = np.array(list(meta.get("classes", ())) + [""], dtype=object)

    def consistent(self) -> bool:
        f = len(self.kind)
        return (len(self.cls) == f and len(self.bbox) == f and len(self.feat) == f + 1
                and self.meta.get("features") == f and len(self.coords) == self.meta.get("points")
                and self.ring[-1] == len(self.coords) and self.feat[-1] == len(self.ring) - 1
                and all(not self.meta[k] or len(self.meta[k]) == f for k in ("n", "name", "a", "u")))

    def __len__(self):
        return len(self.kind)

    def __getitem__(self, i):
        if isinstance(i, slice):
            return [LazyFeature(self, j) for j in range(*i.indices(len(self)))]
        if i < 0:
            i += len(self)
        if not 0 <= i < len(self):
            raise IndexError(i)
        return LazyFeature(self, int(i))

    def __iter__(self):
        return (LazyFeature(self, i) for i in range(len(self)))

    def feature_dicts(self, idx: Iterable[int]) -> List[dict]:
        return [dict(LazyFeature(self, int(i))) for i in idx]

    def classes(self, idx: Optional[np.ndarray] = None) -> np.ndarray:
        """The class text of each feature (of `idx`), "" for none."""
        c = self.cls if idx is None else self.cls[idx]
        return self._class_names[np.where(c == NO_CLASS, len(self._class_names) - 1, c)]

    def in_box(self, box: Sequence[float]) -> np.ndarray:
        """Indices of the features whose bbox meets the box (e0, n0, e1, n1), in order."""
        e0, n0, e1, n1 = box
        b = self.bbox
        return np.nonzero((b[:, 0] <= e1) & (b[:, 2] >= e0) & (b[:, 1] <= n1) & (b[:, 3] >= n0))[0]

    def containing(self, e: float, n: float) -> np.ndarray:
        """Indices of the features whose bbox holds the point."""
        return self.in_box((e, n, e, n))

    def path_bytes(self, idx: Optional[np.ndarray] = None, closed: bool = True) -> PathBytes:
        """path() as polyline_bytes (no Qt object: safe off the GUI thread)."""
        if idx is None:
            rs = np.arange(len(self.ring) - 1)
        else:
            rs, _ = _ranges(self.feat[idx], self.feat[idx + 1])
        return polyline_bytes(self.coords, self.ring[rs], self.ring[rs + 1], closed, winding=closed)

    def path(self, idx: Optional[np.ndarray] = None, closed: bool = True) -> QPainterPath:
        """The features `idx` (all when None) as one path: polygon rings closed (WindingFill, holes
        are holes), lines open."""
        return path_from_bytes(self.path_bytes(idx, closed))

    def rings_of(self, idx: np.ndarray) -> List[list]:
        """The rings (lists of points) of the features `idx`."""
        out: List[list] = []
        for i in idx:
            for r in range(int(self.feat[i]), int(self.feat[i + 1])):
                out.append(self.coords[self.ring[r]:self.ring[r + 1]].tolist())
        return out
