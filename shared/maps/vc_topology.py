"""Shared vice-county borders for the Mapping tab's map: each border between two VCs as ONE
line, used for both VCs' fill and for the boundary layer (R5, 11 Oct 2026).

Why: data/maps/vc_brc_wgs84.geojson keeps every 5th point of the BRC shapefile, and the map
thins each ring again (300 m), each VC on its own. So two neighbours' rings no longer share
their points: along a common border they cross and part every few hundred metres, in thin
"lenses" up to about 100 m wide. Wil saw both at 300 dpi: every shared border stroked twice,
as two grey lines side by side, and pale slivers inside the tinted VCs where neither
neighbour's tint reached.

snap_rings() gives each VC's rings with the borders made common: VCs are taken in number
order, and where a ring's points lie within SNAP_M of an earlier VC's (already final) ring,
that run of points is replaced by the earlier VC's own points between the same two places.
Two neighbours then hold the very same points along their border. unique_chains() walks
rings and keeps each edge the first time it is met, so a shared border is emitted once.

Worked out once per (geojson, simplification), the first time it is needed. Display only.
"""
from __future__ import annotations

import math
from typing import Dict, Iterable, List, Tuple


Point = Tuple[float, float]
SNAP_M = 200.0          # a point this near an earlier VC's ring is on their common border
_CELL = 2000.0          # the segment index's cell (metres)


def _open(ring: List[Point]) -> List[Point]:
    """The ring without its closing point (geojson rings repeat the first point last)."""
    return ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else list(ring)


class _Index:
    """The segments of the final rings so far. Each segment is listed in every _CELL cell
    its box, widened by the snap distance, touches, so a point looks in its own cell only."""

    def __init__(self, snap: float):
        self.snap = snap
        self.cells: Dict[Tuple[int, int], list] = {}
        self.rings: List[Tuple[int, List[Point]]] = []     # (vc, open ring)
        self.cum: List[List[float]] = []                   # distance round each ring

    def add(self, vc: int, ring: List[Point]):
        k = len(self.rings)
        self.rings.append((vc, ring))
        m, s, cells = len(ring), self.snap, self.cells
        cum = [0.0]
        for i in range(m):
            cum.append(cum[-1] + math.dist(ring[i], ring[(i + 1) % m]))
        self.cum.append(cum)
        for i in range(m):
            (ax, ay), (bx, by) = ring[i], ring[(i + 1) % m]
            seg = (ax, ay, bx, by, k, i, vc)
            for cx in range(int((min(ax, bx) - s) // _CELL), int((max(ax, bx) + s) // _CELL) + 1):
                for cy in range(int((min(ay, by) - s) // _CELL),
                                int((max(ay, by) + s) // _CELL) + 1):
                    c = cells.get((cx, cy))
                    if c is None:
                        cells[(cx, cy)] = [seg]
                    else:
                        c.append(seg)

    def nearest(self, x: float, y: float, vc: int):
        """(ring key, nearest vertex index) of another VC's ring within the snap distance,
        else None."""
        segs = self.cells.get((int(x // _CELL), int(y // _CELL)))
        if not segs:
            return None
        best_d2, best = self.snap * self.snap, None
        for ax, ay, bx, by, k, i, owner in segs:
            if owner == vc:
                continue
            dx, dy = bx - ax, by - ay
            ll = dx * dx + dy * dy
            t = 0.0 if ll <= 0 else ((x - ax) * dx + (y - ay) * dy) / ll
            t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
            qx, qy = ax + t * dx - x, ay + t * dy - y
            d2 = qx * qx + qy * qy
            if d2 <= best_d2:
                best_d2, best = d2, (k, i if t < 0.5 else (i + 1) % len(self.rings[k][1]))
        return best


def _path_len(pts: List[Point]) -> float:
    return sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def _fwd_len(cum: List[float], a: int, b: int) -> float:
    """Distance from vertex a forward (increasing index) round the ring to vertex b."""
    d = cum[b] - cum[a]
    return d if d >= 0 else d + cum[-1]


def _walk(ring: List[Point], a: int, b: int, step: int) -> List[Point]:
    m = len(ring)
    out = [ring[a]]
    i = a
    while i != b:
        i = (i + step) % m
        out.append(ring[i])
    return out


def _snap_ring(ring: List[Point], vc: int, index: _Index, snap: float) -> List[Point]:
    """One ring with each run of points lying on an earlier VC's ring replaced by that ring's
    own points between the run's two ends (the way round nearer the run's own length)."""
    pts = _open(ring)
    n = len(pts)
    if n < 3:
        return list(ring)
    near = [index.nearest(x, y, vc) for x, y in pts]
    keys = [h[0] if h else None for h in near]
    if all(k == keys[0] for k in keys):
        return list(ring)                   # all on one ring (or none): nothing to splice
    start = next(i for i in range(n) if keys[i] != keys[i - 1])
    order = [(start + j) % n for j in range(n)]
    out: List[Point] = []
    j = 0
    while j < n:
        i = order[j]
        k = keys[i]
        run = [i]
        while j + len(run) < n and keys[order[j + len(run)]] == k:
            run.append(order[j + len(run)])
        j += len(run)
        own = [pts[r] for r in run]
        if k is None or len(run) < 2:
            out.extend(own)
            continue
        other = index.rings[k][1]
        a, b = near[run[0]][1], near[run[-1]][1]
        if a == b:
            out.extend(own)
            continue
        want = _path_len(own)
        cum = index.cum[k]
        fwd = _fwd_len(cum, a, b)
        back = cum[-1] - fwd
        step, got = (1, fwd) if abs(fwd - want) <= abs(back - want) else (-1, back)
        if got > 3.0 * want + 2.0 * snap:
            out.extend(own)                 # not the same stretch of border after all
            continue
        out.extend(_walk(other, a, b, step))
    clean = [out[0]]
    for q in out[1:]:
        if q != clean[-1]:
            clean.append(q)
    if len(clean) > 1 and clean[-1] == clean[0]:
        clean.pop()
    if len(clean) < 3:
        return list(ring)
    return clean + [clean[0]]


def snap_rings(vc_rings: Dict[int, List[List[Point]]], snap: float = SNAP_M):
    """{vc: rings} with the borders between VCs made common (see the module's notes).
    Rings come back closed (last point = first)."""
    index = _Index(snap)
    out: Dict[int, List[List[Point]]] = {}
    boxes = {vc: _box([p for r in rings for p in r], snap) for vc, rings in vc_rings.items()
             if any(rings)}
    for vc in sorted(vc_rings):
        done = [_snap_ring(r, vc, index, snap) for r in vc_rings[vc]]
        out[vc] = done
        later = [b for w, b in boxes.items() if w > vc]
        for r in done:
            # only a ring a later VC could snap to goes in the index (most islets do not)
            box = _box(r, snap)
            if box and any(_meet(box, b) for b in later):
                index.add(vc, _open(r))
    return out


def _box(pts, pad: float):
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad


def _meet(a, b) -> bool:
    return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]


_SNAP_CACHE: Dict[tuple, dict] = {}


def snap_rings_cached(key, vc_rings):
    """snap_rings, kept per key (the geojson and its simplification) for the process."""
    if key not in _SNAP_CACHE:
        _SNAP_CACHE[key] = snap_rings(vc_rings)
    return _SNAP_CACHE[key]


def unique_chains(rings: Iterable[List[Point]]) -> List[List[Point]]:
    """Every edge of the rings once: an edge two rings share (the same two points, either
    way round) is kept the first time it is met. Runs of kept edges come back as polylines."""
    seen = set()
    chains: List[List[Point]] = []
    for ring in rings:
        pts = [tuple(p) for p in ring]
        if len(pts) > 1 and pts[0] != pts[-1]:
            pts.append(pts[0])
        mine: List[List[Point]] = []
        chain: List[Point] = []
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            key = (a, b) if a <= b else (b, a)
            if a == b or key in seen:
                if len(chain) > 1:
                    mine.append(chain)
                chain = []
                continue
            seen.add(key)
            if not chain:
                chain = [a]
            chain.append(b)
        if len(chain) > 1:
            mine.append(chain)
        # the ring's last run carrying on into its first: one polyline, no break at the start
        if len(mine) > 1 and mine[0][0] == pts[0] and mine[-1][-1] == pts[0]:
            mine[0] = mine.pop()[:-1] + mine[0]
        chains.extend(mine)
    return chains
