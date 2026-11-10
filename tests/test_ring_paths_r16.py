"""Round 16 (A4): the mini-maps draw each layer of rings as ONE path built with numpy instead of a
QPolygonF of QPointF per ring. The pictures must be the same as the old per-point drawing: each
test renders a small purpose-made map both ways (offscreen) and compares every pixel."""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "Observatum")):
    if p not in sys.path:
        sys.path.insert(0, p)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPolygonF  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from shared.maps import ring_paths  # noqa: E402
from shared.maps.species_dist_map import DistributionMiniMap  # noqa: E402
from shared.maps.vc_map import MiniMap  # noqa: E402

TOLERANCE = 0     # differing pixels allowed (the pictures are expected to be identical)

# small purpose-made rings (OSGB metres): two counties side by side, one ring left open (first != last)
RINGS = {
    1: [[(0, 0), (400, 0), (400, 600), (0, 600), (0, 0)],
        [(100, 100), (150, 100), (150, 150), (100, 150)]],               # an open islet ring
    2: [[(400, 0), (900, 100), (850, 700), (400, 600), (400, 0)],
        [(920, 20), (1000, 20), (1000, 80)]],
}
BOUNDS = (0.0, 0.0, 1000.0, 700.0)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def differing(a: QImage, b: QImage) -> int:
    assert a.size() == b.size()
    a, b = a.convertToFormat(QImage.Format.Format_ARGB32), b.convertToFormat(QImage.Format.Format_ARGB32)
    return sum(1 for y in range(a.height()) for x in range(a.width()) if a.pixel(x, y) != b.pixel(x, y))


def test_rings_path_counts_and_drops_short_rings(qapp):
    path = ring_paths.rings_path([[(0, 0), (10, 0), (10, 10)], [(1, 1)], []], lambda e, n: (e, n))
    assert path.elementCount() == 4          # 3 points + the closing line; the 1-point and empty rings are left out
    assert ring_paths.rings_path([], lambda e, n: (e, n)).isEmpty()


def test_vc_minimap_picture_is_unchanged(qapp):
    m = MiniMap(None)
    m._vc_rings, m._bounds, m._active_vc = RINGS, BOUNDS, 2
    new = m.grab().toImage()
    ref = QImage(m.size(), new.format())
    ref.setDevicePixelRatio(new.devicePixelRatio())
    ref.fill(QColor(m.palette().window().color()))
    # the old code, point by point
    from shared.maps._theme import theme
    img = QImage(m.size(), QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor(theme.CARD))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(QColor(theme.LINE))
    pen.setWidthF(0.6)
    for vc, rings in RINGS.items():
        p.setPen(pen)
        p.setBrush(QBrush(QColor(74, 124, 89, 90)) if vc == 2 else Qt.BrushStyle.NoBrush)
        for ring in rings:
            p.drawPolygon(QPolygonF([m._to_px(e, n) for e, n in ring]))
    p.setPen(QColor(theme.MUTED))
    f = p.font()
    f.setPointSize(6)
    p.setFont(f)
    p.drawText(2, m.height() - 2, "© OS/BRC")
    p.end()
    assert differing(new.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied), img) <= TOLERANCE


def test_species_land_picture_is_unchanged(qapp):
    m = DistributionMiniMap(None, resizable=True)
    m._rings, m._bounds, m._extent = RINGS, BOUNDS, BOUNDS
    m.resize(220, 300)
    m._zoom = 2.0
    m._build_land_pixmap()
    new = m._land_pix.toImage()
    from PySide6.QtGui import QPixmap
    pm = QPixmap(m.size())
    pm.fill(QColor(m._SEA))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    land, coast = QColor(m._LAND), QColor(m._COAST)
    polys = [QPolygonF([QPointF(*m._to_px(e, n)) for e, n in ring]) for rs in RINGS.values() for ring in rs]
    p.setPen(QPen(land, 0.8))
    p.setBrush(QBrush(land))
    for poly in polys:
        p.drawPolygon(poly)
    vc_w = 0.35 + 0.20 * min(2.0, 4.0)
    p.setPen(QPen(QColor(m._VCLINE), vc_w))
    p.setBrush(Qt.BrushStyle.NoBrush)
    for poly in polys:
        p.drawPolyline(poly)
    p.setPen(QPen(coast, 0.7))
    for poly in polys:
        p.drawPolyline(poly)
    m._draw_grid(p, 2.0)
    p.end()
    assert differing(new, pm.toImage()) <= TOLERANCE
