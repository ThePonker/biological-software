"""The suite's tick mark: a white tick on a filled, rounded box (one look everywhere).

Observatum's record tables draw it in their tick column (Observatum tick_column.py,
9 Oct 2026); a style-sheeted QCheckBox cannot be painted, so checkbox_qss() gives its
indicator the same tick as an image, drawn here once per colour into a small PNG
(plus an @2x copy for scaled screens) in the temp folder.

    paint_tick(painter, QRectF(...), QColor("#ffffff"))       # a delegate's paint()
    widget.setStyleSheet(checkbox_qss(fill="#4F6D8A", mark="#FFFFFF", border="#9A9A9A"))
    widget.setStyleSheet(radio_qss(fill=..., mark=..., border=..., background=...))

radio_qss (13 Oct 2026, F74) is the same for radio buttons: a round box, filled in the
colour with a white dot when chosen.
"""
import tempfile
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen

BOX = 14                    # px: the tick box of the record tables
CACHE = Path(tempfile.gettempdir()) / "biosoft_ui"


def paint_tick(painter, box, colour, width=2.0):
    """Draw the tick inside box (QRectF, about 14 px square) in colour."""
    s = box.width() / BOX                       # the shape was drawn for a 14 px box
    mark = QPainterPath(QPointF(box.left() + 3.2 * s, box.center().y() + 0.2 * s))
    mark.lineTo(box.left() + 6 * s, box.bottom() - 3.6 * s)
    mark.lineTo(box.right() - 3 * s, box.top() + 3.8 * s)
    pen = QPen(QColor(colour), width * s)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.save()
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(mark)
    painter.restore()


def _draw(path, size, fill, mark, radius):
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(fill))
    box = QRectF(0, 0, size, size)
    p.drawRoundedRect(box, radius * size / 16, radius * size / 16)
    paint_tick(p, box, mark, 2.0 * 14 / 16)
    p.end()
    img.save(str(path), "PNG")


def tick_image(fill, mark, size=16, radius=3):
    """Path (forward slashes, for a style sheet) of a PNG of the ticked box, made on
    first use; an @2x copy beside it is picked up on scaled screens."""
    name = f"tick_{QColor(fill).name()[1:]}_{QColor(mark).name()[1:]}_{size}"
    path = CACHE / f"{name}.png"
    if not path.exists() or not (CACHE / f"{name}@2x.png").exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        _draw(path, size, fill, mark, radius)
        _draw(CACHE / f"{name}@2x.png", size * 2, fill, mark, radius)
    return path.as_posix()


def _draw_dot(path, size, fill, mark):
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(fill))
    p.drawEllipse(QRectF(0, 0, size, size))
    p.setBrush(QColor(mark))
    r = size * 5 / 16
    p.drawEllipse(QRectF(size / 2 - r / 2, size / 2 - r / 2, r, r))
    p.end()
    img.save(str(path), "PNG")


def dot_image(fill, mark, size=16):
    """Path of a PNG of the chosen radio button (filled circle, a dot in the mark colour)."""
    name = f"dot_{QColor(fill).name()[1:]}_{QColor(mark).name()[1:]}_{size}"
    path = CACHE / f"{name}.png"
    if not path.exists() or not (CACHE / f"{name}@2x.png").exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        _draw_dot(path, size, fill, mark)
        _draw_dot(CACHE / f"{name}@2x.png", size * 2, fill, mark)
    return path.as_posix()


def radio_qss(fill, mark, border, background, hover=None, size=16, selector="QRadioButton"):
    """Style sheet for radio buttons: an empty round box, or the box filled with a dot."""
    img = dot_image(fill, mark, size)
    return f"""
        {selector}::indicator {{ width: {size}px; height: {size}px; border-radius: {size // 2}px;
            border: 1px solid {border}; background-color: {background}; }}
        {selector}::indicator:hover {{ border-color: {hover or fill}; }}
        {selector}::indicator:checked {{ border: 1px solid {fill}; background-color: {fill};
            image: url("{img}"); }}
    """


def checkbox_qss(fill, mark, border, background, hover=None, size=16, selector="QCheckBox"):
    """Style sheet for check boxes: an empty box, or the box filled with a tick."""
    img = tick_image(fill, mark, size)
    return f"""
        {selector}::indicator {{ width: {size}px; height: {size}px; border-radius: 3px;
            border: 1px solid {border}; background-color: {background}; }}
        {selector}::indicator:hover {{ border-color: {hover or fill}; }}
        {selector}::indicator:checked {{ border: 1px solid {fill}; background-color: {fill};
            image: url("{img}"); }}
    """
