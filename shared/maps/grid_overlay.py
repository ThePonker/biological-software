"""The grid-square overlay of the map (R19, 11 Nov 2026): lines and labels for the National Grid's
100 km, 10 km and 1 km squares ("Grid lines" tick) and the 2 km tetrads ("Tetrads" tick).

One drawing function, used by the screen's picture and the atlas page alike (map_layers.draw_base
calls it), so the export shows what the screen shows. What is drawn follows the scale: `plan()`
takes the pixels per metre of a 96 dpi screen (fit.scale / k) and returns which levels are drawn,
so no lines are ever denser than about one per 8 pixels:

    100 km lines                      always (they are 8 px apart or more below ~1:100 of GB)
    10 km lines                       when 25 px or more apart, labelled SP52 when 50 px or more
    1 km lines                        when 25 px or more apart, labelled SP5220 when 70 px or more
    tetrad (2 km) lines               when ticked and 20 px or more apart, DINTY letters at 40 px
    100 km letters (SP, SU ...)       at the top left corner of the part of each square in view

Each level is ONE QPainterPath in OSGB metres drawn through layer_transform (the layers' way), cut
to the visible area. Thin, see-through lines in the theme's slate so the recorded squares stay the
strongest thing; labels are the caption text size with a light halo (vc_labels' own), in device
pixels. Square names come from grid_squares / shared.osgb (the one grid-reference code).

Display only.
"""
from __future__ import annotations

import math
from functools import lru_cache
from typing import NamedTuple

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainterPath, QPen

from shared.maps import grid_squares as gs
from shared.maps._theme import theme
from shared.maps.place_names import _glyph, _view_box
from shared.osgb import en_to_gridref
from shared.text_sizes import font_px

GB_E, GB_N = 700000, 1300000                  # the grid's extent in metres
KM100, KM10, KM1, KM2 = 100000, 10000, 1000, 2000
MIN_PX = {KM100: 8.0, KM10: 25.0, KM1: 25.0, KM2: 20.0}     # a level's lines need this much room
LABEL_PX = {KM100: 40.0, KM10: 50.0, KM1: 70.0, KM2: 40.0}  # ... and its labels this much
INSET = 3.0                                   # a label's distance from its corner, px


class Plan(NamedTuple):
    km100: bool
    km10: bool
    km1: bool
    tetrad: bool
    label100: bool
    label10: bool
    label1: bool
    letters: bool


def plan(eff: float, lines: bool = True, tetrads: bool = False) -> Plan:
    """What to draw at `eff` pixels per metre (96 dpi pixels): lines levels, labels, letters."""
    def room(step, table):
        return step * eff >= table[step]
    k100 = lines and room(KM100, MIN_PX)
    k10 = lines and room(KM10, MIN_PX)
    k1 = lines and room(KM1, MIN_PX)
    tet = tetrads and room(KM2, MIN_PX)
    return Plan(k100, k10, k1, tet,
                k100 and room(KM100, LABEL_PX), k10 and room(KM10, LABEL_PX),
                k1 and room(KM1, LABEL_PX), tet and room(KM2, LABEL_PX))


@lru_cache(maxsize=20000)
def square_name(e: float, n: float, step: int):
    """Name of the square of `step` metres holding (e, n): SP, SP52, SP5220 or the tetrad SP52V."""
    if step == KM100:
        return en_to_gridref(e, n, 0)
    return gs.square_for_point(e, n, {KM10: gs.HECTAD, KM1: gs.MONAD, KM2: gs.TETRAD}[step])


def line_path(box, step: int, skip: int = 0) -> QPainterPath:
    """The grid lines every `step` metres inside box (e0, n0, e1, n1) cut to the grid, as one path
    in metres (one subpath per line); lines on a multiple of `skip` are left out (a coarser level
    draws them)."""
    e0, n0 = max(box[0], 0.0), max(box[1], 0.0)
    e1, n1 = min(box[2], float(GB_E)), min(box[3], float(GB_N))
    path = QPainterPath()
    if e1 <= e0 or n1 <= n0:
        return path
    for e in range(math.ceil(e0 / step) * step, int(e1) + 1, step):
        if not (skip and e % skip == 0):
            path.moveTo(e, n0)
            path.lineTo(e, n1)
    for n in range(math.ceil(n0 / step) * step, int(n1) + 1, step):
        if not (skip and n % skip == 0):
            path.moveTo(e0, n)
            path.lineTo(e1, n)
    return path


def _line_colour(alpha: int) -> QColor:
    c = QColor(theme.SLATE)
    c.setAlpha(alpha)
    return c


def _label_font(bold: bool, device) -> QFont:
    """The caption size at the device's resolution (the page is drawn at 300 dpi), unhinted."""
    u = (float(device.logicalDpiY()) if device is not None else 96.0) / 96.0
    f = QFont()
    f.setPixelSize(max(1, round(font_px("caption") * (u if u > 0 else 1.0))))
    f.setBold(bold)
    f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    f.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return f


def draw(p, fit, k: float, transform, lines: bool, tetrads: bool) -> dict:
    """Draw the overlay through `fit` (k: the painter's line-width factor, as for the layers;
    transform: map_layers.layer_transform(fit)). Returns what was drawn: {"plan", "labels"}."""
    pl = plan(fit.scale / k, lines, tetrads)
    out = {"plan": pl, "labels": 0}
    if not any(pl[:4]):
        return out
    tr = p.transform()
    clip = tr.mapRect(p.clipBoundingRect()) if p.hasClipping() else None
    box = _view_box(p, fit, tr, clip)
    w_m = k / fit.scale                          # one pixel (96 dpi) in metres
    levels = ((KM1, pl.km1, KM10, 0.4, 70), (KM2, pl.tetrad, KM10, 0.6, 100),
              (KM10, pl.km10, KM100, 0.6, 110), (KM100, pl.km100, 0, 0.9, 150))
    p.save()
    p.setWorldTransform(transform, True)
    p.setBrush(Qt.BrushStyle.NoBrush)
    for step, on, skip, width, alpha in levels:
        if on:
            pen = QPen(_line_colour(alpha), width * w_m)
            pen.setCapStyle(Qt.PenCapStyle.FlatCap)
            p.setPen(pen)
            p.drawPath(line_path(box, step, skip))
    p.restore()
    out["labels"] = _labels(p, fit, box, pl, tr, clip)
    return out


def _labels(p, fit, box, pl: Plan, tr, clip) -> int:
    """The squares' names, in device pixels with a light halo; returns how many were drawn."""
    if not (pl.label100 or pl.label10 or pl.label1 or pl.letters):
        return 0
    dev = p.device()
    u = (float(dev.logicalDpiY()) if dev is not None else 96.0) / 96.0
    win = QRectF(p.window())
    view = win.intersected(clip) if clip is not None else win
    ink = QColor(theme.SLATE)
    done = 0
    halo = QColor(theme.CARD)
    halo.setAlpha(210)
    dpr = float(dev.devicePixelRatioF()) if dev is not None else 1.0
    p.save()
    p.resetTransform()              # labels are drawn in device pixels, from cached images

    def home(e, n):
        return tr.map(QPointF(*fit.to_px(e, n)))

    def put(text, rect) -> int:
        if text is None or not view.contains(rect):
            return 0
        c = rect.center()
        img, dx, dy = _glyph(text, font, ink, halo, u, dpr)
        p.drawImage(QPointF(round(c.x()) + dx, round(c.y()) + dy), img)
        return 1

    def sized(text):
        fm = QFontMetricsF(font)
        return fm.horizontalAdvance(text), fm.height()

    e0, n0, e1, n1 = max(box[0], 0.0), max(box[1], 0.0), min(box[2], float(GB_E)), min(box[3], float(GB_N))
    pad = INSET * u
    if pl.label100:         # the top left corner of the part of each square that is in view
        font = _label_font(True, dev)
        for e in range(int(e0 // KM100) * KM100, int(e1) + 1, KM100):
            for n in range(int(n0 // KM100) * KM100, int(n1) + 1, KM100):
                text = square_name(e + 1, n + 1, KM100)
                if text is None:
                    continue
                tw, th = sized(text)
                a = home(max(e, e0), min(n + KM100, n1))
                done += put(text, QRectF(a.x() + pad, a.y() + pad, tw, th))
    font = _label_font(False, dev)
    for step, on in ((KM10, pl.label10), (KM1, pl.label1)):
        if not on:
            continue
        for e in range(math.ceil(e0 / step) * step, int(e1), step):
            for n in range(math.ceil(n0 / step) * step, int(n1), step):
                if step == KM1 and e % KM10 == 0 and n % KM10 == 0:
                    continue                      # the 10 km label is there
                text = square_name(e + 1, n + 1, step)
                if text is None:
                    continue
                tw, th = sized(text)
                a = home(e, n)
                done += put(text, QRectF(a.x() + pad, a.y() - pad - th, tw, th))
    if pl.letters:          # the tetrad's letter, in the middle of it (or beside the middle)
        for e in range(math.ceil(e0 / KM2) * KM2, int(e1), KM2):
            for n in range(math.ceil(n0 / KM2) * KM2, int(n1), KM2):
                text = square_name(e + 1, n + 1, KM2)
                if text is None:
                    continue
                tw, th = sized(text[-1])
                a = home(e + KM2 / 2, n + KM2 / 2)
                if pl.label1:       # the middle is where a 1 km label starts: sit in the SE corner
                    r = QRectF(a.x() + pad, a.y() + pad, tw, th)
                else:
                    r = QRectF(a.x() - tw / 2, a.y() - th / 2, tw, th)
                done += put(text[-1], r)
    p.restore()
    return done
