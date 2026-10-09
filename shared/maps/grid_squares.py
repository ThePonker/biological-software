"""Hectad / tetrad / monad squares for the Mapping tab -- pure geometry, no Qt (backlog H3-H5).

Every conversion goes through shared/osgb.py (the one grid-reference implementation).
A record maps to a square only if its grid reference is at least as fine as the square:
a hectad-only record (SP58) has no tetrad or monad, and a tetrad (SP58A) has no monad.
Those are counted as "too coarse" rather than placed in a guessed square.

    square_for_ref("SP580207", 2000)  -> "SP58J"      (DINTY: A-E up the first column)
    square_for_point(458050, 220750, 1000) -> "SP5820"
    square_polygon("SP58J")           -> [(e0, n0), (e1, n0), (e1, n1), (e0, n1)]
    MapFit(extent, w, h).to_px(e, n)  -> widget pixels (north up, equal aspect)
    print_size_px("A4", 300)          -> (2480, 3508)
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

from shared.osgb import en_to_gridref, gridref_to_en

_DINTY = "ABCDEFGHIJKLMNPQRSTUVWXYZ"         # tetrad letters: no O (as shared/osgb)

HECTAD, TETRAD, MONAD = 10000, 2000, 1000
GRID_SIZES = {"hectad": HECTAD, "tetrad": TETRAD, "monad": MONAD}
GRID_LABELS = {HECTAD: "Hectad (10 km)", TETRAD: "Tetrad (2 km)", MONAD: "Monad (1 km)"}

GB_EXTENT = (0.0, 0.0, 700000.0, 1300000.0)
GB_LAND = (13000.0, 5000.0, 654000.0, 1211000.0)   # as species_dist_map's crop

PAPER_MM = {"A4": (210.0, 297.0), "A3": (297.0, 420.0)}


# ---------------------------------------------------------------- squares

def square_for_point(e: float, n: float, size: int) -> Optional[str]:
    """Label of the hectad / tetrad / monad containing the point, or None off the grid."""
    if size == TETRAD:
        hectad = en_to_gridref(e, n, 2)
        if not hectad:
            return None
        k = int((e % 10000) // 2000) * 5 + int((n % 10000) // 2000)
        return hectad + _DINTY[k]
    digits = {HECTAD: 2, MONAD: 4}.get(size)
    if digits is None:
        raise ValueError(f"unsupported square size {size}")
    return en_to_gridref(e, n, digits)


def square_for_ref(ref, size: int) -> Optional[str]:
    """The square of `size` holding the grid reference, or None if unparseable or too coarse."""
    p = gridref_to_en(ref)
    if not p:
        return None
    e, n, ref_size = p
    if ref_size > size:
        return None
    return square_for_point(e, n, size)


def square_bounds(label) -> Optional[Tuple[float, float, float, float]]:
    """(e0, n0, e1, n1) of a square label (any precision shared/osgb accepts)."""
    p = gridref_to_en(label)
    if not p:
        return None
    e, n, s = p
    return float(e), float(n), float(e + s), float(n + s)


def square_polygon(label) -> Optional[List[Tuple[float, float]]]:
    """The square's four corners, anticlockwise from the south-west, in OSGB metres."""
    b = square_bounds(label)
    if not b:
        return None
    e0, n0, e1, n1 = b
    return [(e0, n0), (e1, n0), (e1, n1), (e0, n1)]


def aggregate(records: Iterable[Tuple[str, Optional[int]]], size: int):
    """Group (grid_ref, year) pairs into squares.

    Returns (squares, too_coarse, unparsed): squares maps label -> {count, first_year,
    last_year}; the other two count records left out, so the map can say why.
    """
    squares: Dict[str, dict] = {}
    too_coarse = unparsed = 0
    for ref, year in records:
        p = gridref_to_en(ref)
        if not p:
            unparsed += 1
            continue
        if p[2] > size:
            too_coarse += 1
            continue
        label = square_for_point(p[0], p[1], size)
        if not label:
            unparsed += 1
            continue
        sq = squares.setdefault(label, {"count": 0, "first_year": None, "last_year": None})
        sq["count"] += 1
        if year is not None:
            if sq["first_year"] is None or year < sq["first_year"]:
                sq["first_year"] = year
            if sq["last_year"] is None or year > sq["last_year"]:
                sq["last_year"] = year
    return squares, too_coarse, unparsed


def extent_of(labels: Iterable[str], margin: float = 0.15,
              min_span: float = 20000.0) -> Optional[Tuple[float, float, float, float]]:
    """Bounding box of some squares with a margin (fraction of span), at least min_span wide."""
    boxes = [b for b in (square_bounds(lab) for lab in labels) if b]
    if not boxes:
        return None
    e0 = min(b[0] for b in boxes); n0 = min(b[1] for b in boxes)
    e1 = max(b[2] for b in boxes); n1 = max(b[3] for b in boxes)
    span = max(e1 - e0, n1 - n0, min_span)
    pad = span * margin
    ce, cn = (e0 + e1) / 2, (n0 + n1) / 2
    half = span / 2 + pad
    return ce - half, cn - half, ce + half, cn + half


# ---------------------------------------------------------------- projection

class MapFit:
    """OSGB extent fitted into a w x h pixel box, equal aspect, centred, north up.

    The same formula as DistributionMiniMap._to_px, so a square lines up with the basemap.
    """

    def __init__(self, extent, w: float, h: float, pad: float = 5.0, x0: float = 0.0,
                 y0: float = 0.0):
        self.extent = tuple(float(v) for v in extent)
        minE, minN, maxE, maxN = self.extent
        self.w, self.h, self.x0, self.y0 = float(w), float(h), float(x0), float(y0)
        availw, availh = max(1.0, w - 2 * pad), max(1.0, h - 2 * pad)
        self.scale = min(availw / max(1.0, maxE - minE), availh / max(1.0, maxN - minN))
        self.offx = pad + (availw - (maxE - minE) * self.scale) / 2.0
        self.offy = pad + (availh - (maxN - minN) * self.scale) / 2.0

    def to_px(self, e: float, n: float) -> Tuple[float, float]:
        minE, minN = self.extent[0], self.extent[1]
        return (self.x0 + self.offx + (e - minE) * self.scale,
                self.y0 + self.h - self.offy - (n - minN) * self.scale)

    def to_en(self, x: float, y: float) -> Tuple[float, float]:
        minE, minN = self.extent[0], self.extent[1]
        return (minE + (x - self.x0 - self.offx) / self.scale,
                minN + (self.y0 + self.h - self.offy - y) / self.scale)


def unpan(x: float, y: float, pan_x: float, pan_y: float, zoom: float) -> Tuple[float, float]:
    """Undo PanZoomMixin's translate(pan) + scale(zoom): screen pixel -> unzoomed pixel."""
    return (x - pan_x) / zoom, (y - pan_y) / zoom


def square_at_pixel(fit: MapFit, x: float, y: float, size: int, pan=(0.0, 0.0),
                    zoom: float = 1.0) -> Optional[str]:
    """The square under a mouse click on a (possibly zoomed and panned) map."""
    ux, uy = unpan(x, y, pan[0], pan[1], zoom)
    e, n = fit.to_en(ux, uy)
    return square_for_point(e, n, size)


def visible_extent(fit: MapFit, pan=(0.0, 0.0), zoom: float = 1.0):
    """The OSGB box shown in the widget after pan/zoom (for 'export what I see')."""
    e0, n1 = fit.to_en(*unpan(0.0, 0.0, pan[0], pan[1], zoom))
    e1, n0 = fit.to_en(*unpan(fit.w, fit.h, pan[0], pan[1], zoom))
    return e0, n0, e1, n1


# ---------------------------------------------------------------- print sizing

def print_size_px(paper: str = "A4", dpi: int = 300, landscape: bool = False) -> Tuple[int, int]:
    """Pixel size of a sheet at a resolution: A4 at 300 dpi is 2480 x 3508."""
    w_mm, h_mm = PAPER_MM[paper]
    if landscape:
        w_mm, h_mm = h_mm, w_mm
    return round(w_mm / 25.4 * dpi), round(h_mm / 25.4 * dpi)


def dots_per_metre(dpi: int) -> int:
    """For QImage.setDotsPerMeterX/Y, so the PNG opens at the right physical size."""
    return round(dpi / 0.0254)
