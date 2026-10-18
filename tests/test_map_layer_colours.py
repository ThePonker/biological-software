"""Mapping tab, 18 Oct 2026: remembered layer colours (Layers > Colours...), drawing the layers
through a metres-to-pixels transform (the speed work) and the kept background. Small
purpose-made layer files in tmp_path; nothing from Wil's data."""
# ruff: noqa: F811  (pytest fixtures imported from test_map_layers_r11)
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from shared.maps import layers  # noqa: E402
from tests.test_map_layers_r11 import (BOX, _map, _pixel, _sq, _write,  # noqa: E402,F401
                                       qapp, settings_sandbox)

WOOD = _sq(12000, 12000, 38000, 38000)     # clear of the 10 km grid lines (every 10000 m)
ROAD = {"bbox": [12000, 45000, 90000, 45000], "line": [[12000, 45000], [90000, 45000]]}


# ---------------------------------------------------------------- colours

def test_style_uses_the_remembered_colour_else_the_default(qapp, settings_sandbox):
    from PySide6.QtGui import QColor
    defaults = {k: layers.style(k) for k in ("woodland", "towns", "water", "rivers", "roads")}
    assert layers.saved_colour("woodland") is None
    layers.set_colour("woodland", QColor("#336699"))
    layers.set_colour("roads", "#aa1100")
    assert layers.saved_colour("woodland").name() == "#336699"
    fill, line, w = layers.style("woodland")
    assert fill.name() == "#336699" and line is None and w == defaults["woodland"][2]
    fill, line, w = layers.style("roads")
    assert fill is None and line.name() == "#aa1100" and w == defaults["roads"][2]
    assert layers.style("towns")[0].name() == defaults["towns"][0].name()    # untouched
    layers.reset_colours()
    assert layers.saved_colour("woodland") is None and layers.saved_colour("roads") is None
    assert layers.style("woodland")[0].name() == defaults["woodland"][0].name()


def test_rivers_and_water_areas_share_the_rivers_and_lakes_colour(qapp, settings_sandbox):
    layers.set_colour("water", "#123456")
    assert layers.style("water")[0].name() == "#123456"        # areas: fill
    assert layers.style("rivers")[1].name() == "#123456"       # rivers: line
    assert layers.style("rivers")[0] is None
    assert layers.toggle_key("rivers") == "water" and layers.toggle_key("land") is None


def test_a_bad_remembered_value_falls_back(qapp, settings_sandbox):
    from PySide6.QtCore import QSettings
    QSettings().setValue("mapping/layers/towns/colour", "not a colour")
    assert layers.saved_colour("towns") is None
    assert layers.style("towns")[0].name() == layers.default_style("towns")[0].name()


def test_the_map_repaints_with_the_chosen_colour_and_batch_follows(qapp, tmp_path, monkeypatch,
                                                                  settings_sandbox):
    import paths
    from src.services.batch_maps import BatchSettings
    from src.views.mapping.batch_render import BatchRenderer
    _write(tmp_path, "land", "county", [_sq(0, 0, 100000, 100000)])
    _write(tmp_path, "woodland", "county", [_sq(10000, 10000, 40000, 40000)])
    m = _map(tmp_path)
    m.set_layers({"woodland"})
    before = _pixel(m, 25500, 25500)
    layers.set_colour("woodland", "#ff0000")
    m.refresh_layer_colours()
    assert _pixel(m, 25500, 25500) == "#ff0000" != before
    monkeypatch.setattr(paths, "MAPS_DIR", tmp_path)
    r = BatchRenderer(BatchSettings())
    r.map.set_layers({"woodland"})
    r.map.resize(300, 300)
    r.map.set_extent(BOX)
    assert _pixel(r.map, 25500, 25500) == "#ff0000"             # the batch maps use it too
    layers.reset_colours()
    m.refresh_layer_colours()
    assert _pixel(m, 25500, 25500) == before


def test_colours_menu_item_dialog_and_reset(qapp, tmp_path, settings_sandbox, monkeypatch):
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QColorDialog
    from src.views.mapping.display_bar import MapDisplayBar
    from src.views.mapping.layer_colours import LayerColoursDialog
    _write(tmp_path, "woodland", "county", [_sq(10000, 10000, 40000, 40000)])
    m = _map(tmp_path)
    bar = MapDisplayBar()
    bar.attach_map(m)
    texts = [a.text() for a in bar.layers_menu.actions() if a.text()]
    assert texts.index("Colours…") == texts.index("Reset to defaults") - 1
    dlg = LayerColoursDialog()
    assert list(dlg.swatches) == ["woodland", "towns", "water", "roads"]
    seen = []
    dlg.colours_changed.connect(lambda: seen.append(1))
    monkeypatch.setattr(QColorDialog, "getColor", lambda *a, **k: QColor("#00aa00"))
    dlg.choose("towns")
    assert layers.saved_colour("towns").name() == "#00aa00" and seen == [1]
    assert "#00aa00" in dlg.swatches["towns"].styleSheet()
    dlg.reset()
    assert layers.saved_colour("towns") is None and seen == [1, 1]
    # the bar: the dialog's signal repaints the map; "Reset to defaults" resets colours too
    called = []
    monkeypatch.setattr(m, "refresh_layer_colours", lambda: called.append(1))
    bar.layer_colours_changed.disconnect()
    bar.layer_colours_changed.connect(m.refresh_layer_colours)
    layers.set_colour("roads", "#010203")
    bar.reset_layers()
    assert layers.saved_colour("roads") is None and called


# ---------------------------------------------------------------- the transform and the kept background

def _reference_pixel(m, ex, ny):
    """The old way: every point projected with fit.to_px, drawn as polylines / polygons."""
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPolygonF
    img = QImage(m.width(), m.height(), QImage.Format.Format_RGB32)
    from shared.maps.species_dist_map import _SEA_C
    img.fill(QColor(_SEA_C))
    fit = m.fit()
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    def poly(pts):
        return QPolygonF([QPointF(*fit.to_px(e, n)) for e, n in pts])
    fill, _l, w = layers.style("woodland")
    p.setPen(QPen(fill, w))
    p.setBrush(QBrush(fill))
    p.drawPolygon(poly(WOOD["rings"][0]))
    _f, line, w = layers.style("roads")
    pen = QPen(line, w)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPolyline(poly(ROAD["line"]))
    p.end()
    x, y = fit.to_px(ex, ny)
    return img.pixelColor(int(x), int(y))


def test_drawing_through_the_transform_gives_the_old_pixels(qapp, tmp_path, settings_sandbox):
    _write(tmp_path, "woodland", "county", [WOOD])
    _write(tmp_path, "roads", "county", [ROAD], "line")
    m = _map(tmp_path)
    m.set_layers({"woodland", "roads"})
    fit = m.fit()
    img = m.grab().toImage()
    # the transform is MapFit.to_px
    from PySide6.QtCore import QPointF
    from shared.maps.map_layers import layer_transform
    mapped = layer_transform(fit).map(QPointF(12345, 67890))
    assert (mapped.x(), mapped.y()) == pytest.approx(fit.to_px(12345, 67890))
    # sample points: inside the wood, on the road line (and its antialiased edge), on the
    # wood's edge; the grid lines are at 0 and 100 km, well away
    half = 0.5 / fit.scale                                  # half a pixel, in metres
    for e, n in [(25000, 25000), (55000, 45000), (55000, 45000 + half), (55000, 45000 - half),
                 (12000, 25000), (25000, 38000), (25000, 38000 - half)]:
        ref = _reference_pixel(m, e, n)
        x, y = fit.to_px(e, n)
        got = img.pixelColor(int(x), int(y))
        assert (abs(got.red() - ref.red()), abs(got.green() - ref.green()),
                abs(got.blue() - ref.blue())) <= (3, 3, 3), (e, n, got.name(), ref.name())
    assert img.pixelColor(*map(int, fit.to_px(55000, 45000))).name() != _pixel(m, 55000, 60000)


def test_the_kept_background_is_reused_while_the_view_is_unchanged(qapp, tmp_path, monkeypatch,
                                                                  settings_sandbox):
    _write(tmp_path, "land", "county", [_sq(0, 0, 100000, 100000)])
    _write(tmp_path, "woodland", "county", [_sq(10000, 10000, 40000, 40000)])
    m = _map(tmp_path)
    m.set_layers({"woodland"})
    calls = []
    real = m.draw_base
    monkeypatch.setattr(m, "draw_base", lambda *a, **k: (calls.append(1), real(*a, **k))[1])
    m.grab()
    assert len(calls) == 1
    m.set_selected(None)                                    # hover / selection ...
    m.update()
    m.grab()
    assert len(calls) == 1                                  # ... repaint from the kept picture
    m.set_squares({"SP5020": {"count": 1, "fill": "#a63d40"}}, 10000)     # squares are in it (R10)
    m.grab()
    assert len(calls) == 2
    m.set_selected("SP5020")                                # the clicked outline is drawn live
    m.grab()
    assert len(calls) == 2
    assert _pixel(m, 25500, 25500) != _pixel(m, 55500, 55500)
    m.set_layers({"woodland", "water"})                     # a switch changes it
    m.grab()
    assert len(calls) == 3
    m.highlight_vcs([23])                                   # so does the tint ...
    m.grab()
    assert len(calls) == 4
    layers.set_colour("woodland", "#ff0000")                # ... and a colour
    m.grab()
    assert len(calls) == 5
    m.grab()
    assert len(calls) == 5
    m.resize(320, 310)                                      # ... and the size
    m.grab()
    assert len(calls) == 6
