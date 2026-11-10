"""The background-layer legend on the atlas page (R17, 10 Nov 2026).

build() lists the layers that are switched on and drawn at the exported extent's scale: one
swatch and name per plain layer; per classed layer (env_classes: geology, soils, NFI ...) one swatch
per class whose features meet the exported box, at most MAX_CLASSES then "+N more". The colours
and names are the map's and the Layers window's own (layers.style / saved_colour,
env_classes.class_colour, Toggle.label): nothing is copied. layout() places the swatches in rows
and is used both to measure the page (rows_mm) and to draw it (draw), so they cannot disagree.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QPen

from shared.maps import env_classes, env_registry as env, layers, place_classes
from shared.maps._theme import theme

MAX_CLASSES = 12
ROW_MM = 6.0
SWATCH_MM = 4.0
GAP_MM = 8.0


@dataclass(frozen=True)
class LegendGroup:
    name: str                                   # the layer's name (Toggle.label)
    swatches: Tuple[Tuple[str, str], ...]       # (hex colour, label); a plain layer has one
    more: int = 0                               # classes left out beyond MAX_CLASSES
    classed: bool = False


def _plain_colour(tg) -> Optional[str]:
    """The colour the layer is drawn in (remembered, else default); None when it has none."""
    c = layers.saved_colour(tg.key) or None
    if c is None:
        fill, line, _w = layers.default_style(tg.files[0])
        c = fill or line
    if c is None:                                # the relief is a grey picture
        return QColor(theme.MUTED).name()
    return QColor(c).name()


def _classes_in(maps_dir, key: str, box) -> List[str]:
    feats = layers.load(maps_dir, key, layers.lod_for_extent(box))
    found = set()
    for f in layers.features_in(feats, box):
        found.add(str(f.get("t") or ""))
    return list(found)


def build(maps_dir, layers_on, layer_files, box) -> List[LegendGroup]:
    """The legend groups for the ticked, installed layers drawn at `box` (OSGB e0, n0, e1, n1)."""
    lod = layers.lod_for_extent(box)
    span = max(box[2] - box[0], box[3] - box[1])
    out: List[LegendGroup] = []
    for tg in layers.visible_toggles():
        if tg.key not in layers_on or not any(f in layer_files for f in tg.files):
            continue
        if not any(layers.file_path(maps_dir, f, lod) is not None for f in tg.files):
            continue                             # county-only layer at GB scale: not drawn
        if tg.key == "names" and not place_classes.shown_at(span):
            continue
        if env_classes.is_classed(tg.key):
            entries = env_classes.key_entries(tg.key, _classes_in(maps_dir, tg.key, box))
            if not entries:
                continue
            shown = tuple((hx, cls or "(no class)") for cls, hx in entries[:MAX_CLASSES])
            out.append(LegendGroup(tg.label, shown, max(0, len(entries) - MAX_CLASSES), True))
        else:
            colour = _plain_colour(tg)
            if tg.key in {e.key for e in env.ENV_LAYERS if e.kind == "grid"}:
                colour = QColor(layers.grid_ramp(tg.key)[-1]).name()
            out.append(LegendGroup(tg.label, ((colour, tg.label),)))
    return out


def _font(bold: bool = False) -> QFont:
    f = QFont()
    f.setPointSize(8)
    f.setBold(bold)
    return f


def layout(groups: Sequence[LegendGroup], dev, mm: float, width_px: float):
    """([(x, row, kind, text, colour)], rows): plain layers share rows; each classed layer starts
    a row with its bold name, then its class swatches, wrapping. x is from the left margin."""
    fm, fmb = QFontMetricsF(_font(), dev), QFontMetricsF(_font(True), dev)
    items, x, row = [], 0.0, 0

    def newline():
        nonlocal x, row
        if x > 0:
            x, row = 0.0, row + 1

    def put(kind, text, colour, advance):
        nonlocal x, row
        if x > 0 and x + advance > width_px:
            x, row = 0.0, row + 1
        items.append((x, row, kind, text, colour))
        x += advance + GAP_MM * mm

    for g in (g for g in groups if not g.classed):
        put("swatch", g.name, g.swatches[0][0], (SWATCH_MM + 1.5) * mm + fm.horizontalAdvance(g.name))
    for g in (g for g in groups if g.classed):
        newline()
        put("head", g.name + ":", None, fmb.horizontalAdvance(g.name + ":"))
        for hexcol, label in g.swatches:
            put("swatch", label, hexcol, (SWATCH_MM + 1.5) * mm + fm.horizontalAdvance(label))
        if g.more:
            txt = f"+{g.more} more"
            put("text", txt, None, fm.horizontalAdvance(txt))
    return items, (row + 1 if items else 0)


def rows_mm(groups: Sequence[LegendGroup], dev, mm: float, width_px: float) -> float:
    """The height the legend needs on the page, in millimetres (0 for none)."""
    return layout(groups, dev, mm, width_px)[1] * ROW_MM


def draw(p, groups: Sequence[LegendGroup], x0: float, y0: float, mm: float, k: float,
         width_px: float) -> None:
    """Paint the legend at (x0, y0); rows are ROW_MM apart."""
    items, _rows = layout(groups, p.device(), mm, width_px)
    for x, row, kind, text, colour in items:
        x, y = x0 + x, y0 + row * ROW_MM * mm
        if kind == "swatch":
            p.setFont(_font())
            p.setPen(QPen(QColor(theme.INK), 0.4 * k))
            p.setBrush(QBrush(QColor(colour)))
            p.drawRect(QRectF(x, y, SWATCH_MM * mm, SWATCH_MM * mm))
            tx = x + (SWATCH_MM + 1.5) * mm
        else:
            p.setFont(_font(kind == "head"))
            tx = x
        p.setPen(QColor(theme.INK if kind != "text" else theme.MUTED))
        w = p.fontMetrics().horizontalAdvance(text) + 2 * mm
        p.drawText(QRectF(tx, y - 1 * mm, w, ROW_MM * mm),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), text)
