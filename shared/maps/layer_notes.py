"""A small note in a corner of the map when a layer file could not be loaded (layers.load_errors()).
The layer is drawn empty; this says so instead of leaving the gap unexplained."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter


_NOTE_BG = "#fff4d6"
_NOTE_FG = "#7a4b00"


def note_lines(errors) -> list:
    """One line per layer: 'Layer <name> could not be loaded' (the key's name before its level of detail)."""
    names = []
    for k in sorted(errors or {}):
        name = k.rsplit("_", 1)[0] if k.rsplit("_", 1)[-1] in ("gb", "county") else k
        name = name.replace("_", " ")
        if name not in names:
            names.append(name)
    return [f"Layer {n} could not be loaded" for n in names]


def draw_load_errors(painter: QPainter, rect, errors) -> None:
    """Draw the note in the bottom-left corner of `rect` (a QRect/QRectF); nothing when no errors."""
    lines = note_lines(errors)
    if not lines:
        return
    painter.save()
    try:
        f = QFont(painter.font())
        f.setPixelSize(11)
        painter.setFont(f)
        fm = QFontMetrics(f)
        w = max(fm.horizontalAdvance(t) for t in lines) + 12
        h = fm.height() * len(lines) + 8
        r = QRectF(rect)
        box = QRectF(r.left() + 8, r.bottom() - h - 8, w, h)
        painter.setPen(QColor(_NOTE_FG))
        painter.setBrush(QColor(_NOTE_BG))
        painter.drawRoundedRect(box, 3, 3)
        painter.setPen(QColor(_NOTE_FG))
        for i, t in enumerate(lines):
            painter.drawText(QRectF(box.left() + 6, box.top() + 4 + i * fm.height(), w, fm.height()),
                             int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), t)
    finally:
        painter.restore()
