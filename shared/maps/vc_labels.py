"""Vice-county labels, boundaries and the selected VC's outline for the Mapping tab's map
(R9-5, 11 Oct 2026; R4 the same day: device-pixel labels, nudged off squares, boundary lines).

Labels: at national scale (more than NAMES_SPAN_M across) each VC shows its number; zoomed
in (County view, or the national map zoomed well in) it shows "Oxfordshire (VC23)", or its
number where the name does not fit. Bigger VCs are placed first and a label that would
overlap one already placed is left out, so GB never clutters; the selected VC goes first. The same rule runs on screen
and on the atlas page (render_sheet), so the PNG shows what the screen shows.

Display only: names come from the vice-county GeoJSON (vc_map.vc_names), never a database.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen

from shared.maps._theme import theme
from shared.maps.vc_map import ring_area

NAMES_SPAN_M = 300000.0     # a view narrower than this (metres) shows names, wider: numbers
NUMBER_PT = 7.0             # label sizes in points (screen and page alike)
NAME_PT = 8.0
OUTLINE_W = 2.4             # the selected VC's outline, in screen pixels (x k on the page)
BOUNDARY_W = 1.0            # R4: every VC's boundary line, in screen pixels (x k on the page)

Point = Tuple[float, float]


def _inside(e: float, n: float, ring: List[Point]) -> bool:
    """Ray-casting point-in-ring test."""
    hit = False
    j = len(ring) - 1
    for i in range(len(ring)):
        (xi, yi), (xj, yj) = ring[i], ring[j]
        if (yi > n) != (yj > n) and e < (xj - xi) * (n - yi) / ((yj - yi) or 1e-12) + xi:
            hit = not hit
        j = i
    return hit


point_in_ring = _inside


def interior_point(ring: List[Point]) -> Point:
    """A point inside the ring for its label: the centroid when it lies inside, else the
    middle of the widest stretch of the ring along the centroid's northing (a crescent or
    a C-shaped county keeps its label on its own land)."""
    a = ring_area(ring)
    if abs(a) < 1e-6:
        es = [e for e, _n in ring]
        ns = [n for _e, n in ring]
        return (min(es) + max(es)) / 2, (min(ns) + max(ns)) / 2
    cx = cy = 0.0
    for i in range(len(ring)):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % len(ring)]
        c = x1 * y2 - x2 * y1
        cx += (x1 + x2) * c
        cy += (y1 + y2) * c
    cx, cy = cx / (6 * a), cy / (6 * a)
    if _inside(cx, cy, ring):
        return cx, cy
    xs = []
    for i in range(len(ring)):
        (x1, y1), (x2, y2) = ring[i], ring[(i + 1) % len(ring)]
        if (y1 > cy) != (y2 > cy):
            xs.append(x1 + (cy - y1) * (x2 - x1) / (y2 - y1))
    xs.sort()
    spans = [(xs[i + 1] - xs[i], (xs[i] + xs[i + 1]) / 2) for i in range(0, len(xs) - 1, 2)]
    return (max(spans)[1], cy) if spans else (cx, cy)


def label_points(vc_rings: Dict[int, list]) -> List[Tuple[int, Point, float]]:
    """[(vc, (e, n), area)] on each VC's largest ring, biggest VC first (placing order)."""
    out = []
    for vc, rings in vc_rings.items():
        if not rings:
            continue
        ring = max(rings, key=lambda r: abs(ring_area(r)))
        out.append((vc, interior_point(ring), abs(ring_area(ring))))
    out.sort(key=lambda t: -t[2])
    return out


def label_font(pt: float, bold: bool, device) -> QFont:
    """The label font at a whole pixel size for `device` (screen: its logical dpi, the page:
    its dpi), unhinted so its glyph positions do not depend on the size."""
    dpi = float(device.logicalDpiY()) if device is not None else 96.0
    f = QFont()
    f.setPixelSize(max(1, round(pt * (dpi if dpi > 0 else 96.0) / 72.0)))
    f.setBold(bold)
    f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    f.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return f


def label_path(text: str, font: QFont, centre: QPointF) -> QPainterPath:
    """The text as one outline centred on `centre` (device pixels): the halo is this path
    stroked and the letters are this path filled, so the two can never drift apart."""
    path = QPainterPath()
    path.addText(0.0, 0.0, font, text)
    fm = QFontMetricsF(font)
    br = path.boundingRect()
    # baseline from the font's ascent/descent (a steady line for every label), centred across
    path.translate(round(centre.x() - br.center().x()),
                   round(centre.y() + (fm.ascent() - fm.descent()) / 2.0))
    return path


def _nudges(w: float, h: float):
    """Offsets (device pixels) tried for a label sitting on recorded squares: none first,
    then just above / below / beside it, then a little further."""
    out = [(0.0, 0.0)]
    for f in (1.0, 2.0):
        dy, dx = 1.1 * h * f, 0.5 * w + 0.6 * h * f
        out += [(0.0, -dy), (0.0, dy), (-dx, 0.0), (dx, 0.0),
                (-dx, -dy), (dx, -dy), (-dx, dy), (dx, dy)]
    return out


def draw_labels(p: QPainter, fit, points, names: Dict[int, str], span_m: float,
                bold_vc: Optional[int] = None, occupied=None, inside=None) -> list:
    """Draw the VC labels through `fit`. span_m: the width (metres) of what is shown, which
    picks numbers or names. bold_vc: the selected VC (placed first, in bold).

    R4 (11 Oct 2026): labels are laid out and drawn in DEVICE pixels, the painter's zoom
    undone, at a whole pixel size (label_font), as one path (halo stroked, letters filled).
    They used to be drawText at a fractional point size (8 / zoom) under the zoom transform,
    with eight offset copies for the halo: on Windows the glyphs were hinted at the tiny size
    and then scaled up, with ClearType colour fringes, so zoomed-in names came out garbled.

    occupied(QRectF) -> bool: does this device rect cover a recorded square? A label that
    does is nudged (_nudges) to a free spot still inside its VC (inside(vc, QPointF) -> bool),
    else kept where it is with a stronger halo. Returns [(vc, text, device QRectF, strong)].
    """
    names_mode = span_m <= NAMES_SPAN_M
    ink = QColor(theme.HEADING)
    dev = p.device()
    u = (float(dev.logicalDpiY()) if dev is not None else 96.0) / 96.0   # px per screen px
    tr = p.transform()
    # on the atlas page the map is clipped to its box: a label cut by the box edge ("VC33)")
    # is left out (or falls back to its number) rather than printed half off the page
    clip = tr.mapRect(p.clipBoundingRect()) if p.hasClipping() else None
    if bold_vc is not None:     # the selected VC is placed first, so a neighbour never hides it
        points = sorted(points, key=lambda t: t[0] != bold_vc)
    placed: List[QRectF] = []
    shown = []
    pad = 2 * u
    for vc, (e, n), _a in points:
        x, y = fit.to_px(e, n)
        home = tr.map(QPointF(x, y))
        texts = [f"{names[vc]} (VC{vc})", str(vc)] if names_mode and names.get(vc) else [str(vc)]
        for i, text in enumerate(texts):
            is_name = names_mode and i == 0 and len(texts) > 1
            font = label_font(NAME_PT if is_name else NUMBER_PT, vc == bold_vc, dev)
            fm = QFontMetricsF(font)
            w, h = fm.horizontalAdvance(text), fm.height()
            best = None                     # (centre, rect, strong)
            for dx, dy in _nudges(w, h) if occupied is not None else [(0.0, 0.0)]:
                c = QPointF(home.x() + dx, home.y() + dy)
                rect = QRectF(c.x() - w / 2, c.y() - h / 2, w, h)
                ok = (not any(rect.adjusted(-pad, -pad, pad, pad).intersects(r) for r in placed)
                      and (clip is None or clip.contains(rect)))
                if not (dx or dy):
                    if not ok:              # its own spot is taken: left out, as before
                        break
                    best = (c, rect, occupied is not None and occupied(rect))
                    if not best[2]:
                        break
                elif ok and (inside is None or inside(vc, c)) and not occupied(rect):
                    best = (c, rect, False)  # a free spot nearby, still in its own VC
                    break
            if best is None:
                continue
            c, rect, strong = best
            placed.append(rect.adjusted(-pad, -pad, pad, pad))
            shown.append((vc, text, rect, strong))
            _paint_label(p, label_path(text, font, c), ink, strong, u)
            break
    return shown


def _paint_label(p: QPainter, path: QPainterPath, ink: QColor, strong: bool, u: float):
    """The halo (the path stroked in the card colour; wider and solid on a recorded square)
    then the letters (the same path filled), in device pixels, antialiased as a shape."""
    halo = QColor(theme.CARD)
    halo.setAlpha(255 if strong else 210)
    pen = QPen(halo, (4.4 if strong else 2.4) * u)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.save()
    p.resetTransform()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.strokePath(path, pen)
    p.fillPath(path, ink)
    p.restore()


def draw_outline(p: QPainter, polys, k: float = 1.0):
    """The selected VC's border: a thicker line in the theme's primary (hover) colour."""
    pen = QPen(QColor(theme.MOSS_HOVER), OUTLINE_W * k)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    for poly in polys:
        p.drawPolygon(poly)


def boundary_colour() -> QColor:
    """The VC boundary line: the theme's slate softened a third of the way towards the card
    colour (solid, so a border two VCs share is not drawn darker than a coastal one)."""
    a, b = QColor(theme.SLATE), QColor(theme.CARD)
    return QColor(round(a.red() * 0.67 + b.red() * 0.33), round(a.green() * 0.67 + b.green() * 0.33),
                  round(a.blue() * 0.67 + b.blue() * 0.33))


def draw_boundaries(p: QPainter, vc_polys, k: float = 1.0):
    """Every vice-county's boundary (R4: Wil found the shading alone confusing). vc_polys:
    an iterable of lists of QPolygonF (closed rings, or open polylines of inland borders)."""
    pen = QPen(boundary_colour(), BOUNDARY_W * k)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    for polys in vc_polys:
        for poly in polys:
            p.drawPolyline(poly)
