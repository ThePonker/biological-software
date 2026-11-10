"""The picture draped over the 3D surface, and the export page (footer) of the 3D view."""
from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFontMetrics, QImage, QPainter

from shared import osgb
from shared.maps import terrain
from shared.maps.grid_squares import MapFit
from shared.maps.layers import OS_CREDIT, credit_lines
from shared.maps.species_dist_map import _SEA_C

DRAPE_PX = 2048
EXPORT_SIZE = (3000, 2000)


def drape_size(extent, long_px=DRAPE_PX):
    """(w, h) pixels with the extent's aspect ratio, the long side long_px."""
    w, h = extent[2] - extent[0], extent[3] - extent[1]
    if w >= h:
        return long_px, max(1, round(long_px * h / w))
    return max(1, round(long_px * w / h)), long_px


def make_drape(map_widget, extent, long_px=DRAPE_PX) -> QImage:
    """The map drawn for exactly `extent` (north up) into a QImage; the relief layer is left out
    (the 3D surface is its own relief) and put back afterwards."""
    w, h = drape_size(extent, long_px)
    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(QColor(_SEA_C))
    keys = set(getattr(map_widget, "_layers_on", ()) or ())
    swap = "relief" in keys
    if swap:
        map_widget.set_layers(keys - {"relief"})
    p = QPainter(img)
    try:
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        fit = MapFit(extent, w, h, pad=0.0)
        k = max(1.0, long_px / max(1, max(map_widget.width(), map_widget.height())))
        map_widget.draw(p, fit, k=k, selected=False, zoom=1.0)
    finally:
        p.end()
        if swap:
            map_widget.set_layers(keys)
    return img


def export_credits(map_widget, label):
    """The credit lines of an exported 3D picture: the OS one, the EA one when LiDAR was used,
    and the credits and grid legends of the layers draped on it (the atlas page's helper)."""
    extra = [terrain.EA_CREDIT] if "LiDAR" in label else []
    keys = map_widget.layers_drawn() if hasattr(map_widget, "layers_drawn") else []
    return credit_lines(getattr(map_widget, "_maps_dir", None), keys, os_always=True, extra=extra)


def footer_lines(extent, exaggeration, label, cell_m, credits=None):
    """The lines under an exported 3D picture (`credits`: export_credits(); else the OS one,
    plus the EA one for LiDAR)."""
    sw = osgb.en_to_gridref(extent[0] + 1, extent[1] + 1, 4) or f"{extent[0]:.0f} {extent[1]:.0f}"
    ne = osgb.en_to_gridref(extent[2] - 1, extent[3] - 1, 4) or f"{extent[2]:.0f} {extent[3]:.0f}"
    lines = [f"Area {sw} to {ne}. Vertical exaggeration {exaggeration:g}x. "
             f"Heights: {label} ({cell_m:g} m cells)."]
    if credits is None:
        credits = [OS_CREDIT] + ([terrain.EA_CREDIT] if "LiDAR" in label else [])
    return lines + list(credits)


def compose_export(scene_img: QImage, lines, bg, fg) -> QImage:
    """The 3D picture with a footer band of text under it; long lines wrap and the band grows."""
    w = scene_img.width() - 32
    flags = int(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap)
    probe = QImage(1, 1, QImage.Format.Format_RGB32)
    p = QPainter(probe)
    f = p.font()
    f.setPixelSize(20)
    p.setFont(f)
    heights = [max(28, QFontMetrics(f).boundingRect(QRect(0, 0, w, 100000), flags, line).height())
               for line in lines]
    p.end()
    out = QImage(scene_img.width(), scene_img.height() + sum(heights) + 16, QImage.Format.Format_RGB32)
    out.fill(QColor(bg))
    p = QPainter(out)
    p.drawImage(0, 0, scene_img)
    p.setPen(QColor(fg))
    p.setFont(f)
    y = scene_img.height() + 8
    for line, hh in zip(lines, heights):
        p.drawText(QRect(16, y, w, hh), flags, line)
        y += hh
    p.end()
    return out
