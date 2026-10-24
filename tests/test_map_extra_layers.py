"""18 Oct 2026: the Mapping tab's six extra background layers (place names, railways, national
parks, foreshore, parks and green space, relief): the Layers menu, drawing, the labels, the
credit and the warm-up. Small purpose-made layer files in tmp_path; nothing from Wil's data."""
# ruff: noqa: F811  (pytest fixtures imported from test_map_layers_r11)
import json
import os

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from shared.maps import layers, place_classes, place_names  # noqa: E402
from tests.test_map_layers_r11 import (ATTR, BOX, _map, _pixel, _sq, _write,  # noqa: E402,F401
                                       qapp, settings_sandbox)

NEW = ("names", "rail", "national_parks", "foreshore", "greenspace", "relief")
LAND_C = "#e7ece3"
PLACES_GB = [("City", "Oxford", 50000, 50000)]
PLACES_CO = [("Town", "Banbury", 20000, 70000), ("Village", "Adderbury", 75000, 30000),
             ("Hamlet", "Nethercote", 25000, 25000), ("Suburban Area", "Headington", 52000, 50500)]


def _pt(t, n, e, nn):
    return {"bbox": [e, nn, e, nn], "pt": [e, nn], "n": n, "t": t}


def _write_names(tmp_path):
    _write(tmp_path, "names", "gb", [_pt(*p) for p in PLACES_GB], "point")
    _write(tmp_path, "names", "county", [_pt(*p) for p in PLACES_CO], "point")


def _relief(tmp_path, grey, alpha=None, extent=(0, 0, 100000, 100000), cell=250):
    """relief_gb.png + .json made the way the build makes them."""
    from scripts import build_map_relief as br
    d = tmp_path / "layers"
    d.mkdir(exist_ok=True)
    h, w = grey.shape
    br.write_png_la(d / "relief_gb.png", grey, np.full((h, w), 255, np.uint8) if alpha is None else alpha)
    (d / "relief_gb.json").write_text(json.dumps(
        {"layer": "relief", "kind": "image", "image": "relief_gb.png", "extent": list(extent),
         "cell_m": cell, "width": w, "height": h, "attribution": ATTR}), encoding="utf-8")


# ---------------------------------------------------------------- the menu

def test_new_items_off_by_default_greyed_when_missing_remembered_and_reset(qapp, tmp_path,
                                                                           settings_sandbox):
    from PySide6.QtCore import QSettings
    from src.views.mapping.display_bar import MapDisplayBar, saved_layers
    assert layers.defaults() == {"water"} and all(not t.default for t in layers.TOGGLES if t.key in NEW)
    _write_names(tmp_path)
    _write(tmp_path, "rail", "gb", [{"bbox": [0, 0, 9, 9], "line": [[0, 0], [9, 9]]}], "line")
    _relief(tmp_path, np.full((4, 4), 200, np.uint8))
    m = _map(tmp_path)
    bar = MapDisplayBar()
    bar.attach_map(m)
    acts = bar.layer_actions
    assert all(k in acts and acts[k].isCheckable() and not acts[k].isChecked() for k in NEW)
    assert bar.layers() == {"water"} and saved_layers() == {"water"}
    assert {k for k in NEW if acts[k].isEnabled()} == {"names", "rail", "relief"}
    for k in ("national_parks", "foreshore", "greenspace"):
        assert acts[k].toolTip() == "Not installed: run scripts\\build_map_layers.py"
    for k in NEW:
        acts[k].setChecked(True)
    assert saved_layers() == {"water", *NEW} and m._layers_on == {"water", *NEW}
    assert QSettings().value("mapping/layers/greenspace", False, type=bool) is True
    assert MapDisplayBar().layers() == {"water", *NEW}                       # remembered
    bar.reset_layers()
    assert bar.layers() == {"water"} and m._layers_on == {"water"} and saved_layers() == {"water"}
    assert QSettings().value("mapping/layers/names", True, type=bool) is False


def test_relief_needs_its_image_and_loader_accepts_points(tmp_path):
    d = tmp_path / "layers"
    d.mkdir()
    (d / "relief_gb.json").write_text("{}", encoding="utf-8")
    assert "relief" not in layers.available(tmp_path)                          # no png: not installed
    _relief(tmp_path, np.full((2, 2), 9, np.uint8))
    assert "relief" in layers.available(tmp_path)
    _write_names(tmp_path)
    got = layers.load(tmp_path, "names", "gb")
    assert got and got[0]["pt"] == [50000, 50000] and got[0]["n"] == "Oxford"
    assert len(layers.features_in(got, (0, 0, 10, 10))) == 0


# ---------------------------------------------------------------- the area layers and rail

def test_foreshore_and_green_space_are_pale_fills_national_parks_an_outline(qapp, tmp_path):
    _write(tmp_path, "land", "county", [_sq(0, 0, 100000, 100000)])
    _write(tmp_path, "foreshore", "county", [_sq(12000, 12000, 38000, 38000)])
    _write(tmp_path, "greenspace", "county", [_sq(62000, 12000, 88000, 38000)])
    _write(tmp_path, "woodland", "county", [_sq(62000, 62000, 88000, 88000)])
    _write(tmp_path, "national_parks", "county", [_sq(12000, 62000, 38000, 88000)])
    m = _map(tmp_path)
    inside = {k: (25500, 25500) for k in ("foreshore",)}
    inside.update(greenspace=(75500, 25500), woodland=(75500, 75500), national_parks=(25500, 75500))
    plain = {k: _pixel(m, *xy) for k, xy in inside.items()}
    assert set(plain.values()) == {LAND_C} and m.layers_drawn() == ["land"]
    m.set_layers({"foreshore", "greenspace", "woodland", "national_parks"})
    assert m.layers_drawn() == ["land", "foreshore", "greenspace", "woodland", "national_parks"]
    now = {k: _pixel(m, *xy) for k, xy in inside.items()}
    assert len({now["foreshore"], now["greenspace"], now["woodland"]}) == 3      # three different fills
    assert now["foreshore"] == layers.style("foreshore")[0].name()
    assert now["greenspace"] == layers.style("greenspace")[0].name() != now["woodland"]
    assert now["national_parks"] == LAND_C                                       # outline only
    assert _pixel(m, 12000, 75500) != LAND_C or _pixel(m, 12300, 75500) != LAND_C   # its edge is drawn
    fill, line, w = layers.style("national_parks")
    assert fill is None and line is not None and w <= 1.0


def test_rail_is_a_thin_dashed_line(qapp, tmp_path):
    _write(tmp_path, "land", "county", [_sq(0, 0, 100000, 100000)])
    _write(tmp_path, "rail", "county", [{"bbox": [5000, 55000, 95000, 55000],
                                         "line": [[5000, 55000], [95000, 55000]]}], "line")
    m = _map(tmp_path)
    m.set_layers({"rail"})
    img = m.grab().toImage()
    x0, y = m.fit().to_px(10000, 55000)
    x1, _y = m.fit().to_px(90000, 55000)
    row = [min(img.pixelColor(x, yy).lightness() for yy in (int(y) - 1, int(y), int(y) + 1))
           for x in range(int(x0), int(x1))]
    ground = img.pixelColor(int(x0), int(y) + 6).lightness()
    marked = [v < ground - 4 for v in row]
    assert any(marked) and not all(marked)                      # dashes with gaps
    assert layers.DASHES["rail"] and layers.style("rail")[2] <= 0.8


# ---------------------------------------------------------------- the place names

def _image(m, size=600):
    from PySide6.QtGui import QColor, QImage, QPainter
    img = QImage(size, size, QImage.Format.Format_RGB32)
    img.fill(QColor(LAND_C))
    p = QPainter(img)
    return img, p, m.fit()


def _names_at(tmp_path, span, box=BOX, lod="county", **kw):
    from shared.maps import grid_squares as gs
    m = _map(tmp_path)
    fit = gs.MapFit(box, 600, 600)
    img, p, _f = _image(m)
    out = place_names.draw_place_names(p, fit, place_names.feature_lists(tmp_path, lod), span,
                                       layers.style("names")[1], **kw)
    p.end()
    return out, img


def test_names_shown_by_the_span_thresholds(qapp, tmp_path):
    _write_names(tmp_path)
    assert place_classes.shown_at(1_300_000) == [0] and place_classes.shown_at(250_000) == [0, 1]
    assert place_classes.shown_at(250_001) == [0] and place_classes.shown_at(60_000) == [0, 1, 2]
    assert place_classes.shown_at(20_000) == [0, 1, 2, 3] and place_classes.shown_at(20_001) == [0, 1, 2]
    seen = lambda span, lod="county": [n for n, _r in _names_at(tmp_path, span, lod=lod)[0]]    # noqa: E731
    assert seen(1_300_000, "gb") == ["Oxford"]                  # the whole-country view: gb file
    assert seen(200_000) == ["Oxford", "Banbury"]
    assert seen(50_000) == ["Oxford", "Banbury", "Adderbury"]
    # all four classes; Headington sits on Oxford, so it is left out
    assert seen(15_000) == ["Oxford", "Banbury", "Adderbury", "Nethercote"]


def test_names_are_the_same_size_in_pixels_at_any_zoom(qapp, tmp_path):
    _write_names(tmp_path)
    near, _i = _names_at(tmp_path, 15_000, box=(40000, 40000, 60000, 60000))
    far, _j = _names_at(tmp_path, 15_000, box=BOX)
    a, b = dict(near)["Oxford"], dict(far)["Oxford"]
    assert (a.width(), a.height()) == (b.width(), b.height()) and a.height() > 6
    big_town, _k = _names_at(tmp_path, 200_000)
    city, town = dict(big_town)["Oxford"], dict(big_town)["Banbury"]
    assert city.height() > town.height() > 0                    # sized by class


def test_names_are_drawn_with_ink_and_a_land_coloured_halo(qapp, tmp_path):
    _write_names(tmp_path)
    out, img = _names_at(tmp_path, 200_000)
    r = dict(out)["Oxford"]
    px = [img.pixelColor(x, y) for x in range(int(r.left()), int(r.right()) + 1)
          for y in range(int(r.top()), int(r.bottom()) + 1)]
    ink = layers.style("names")[1]
    dark = min(px, key=lambda c: c.lightness())
    assert abs(dark.red() - ink.red()) + abs(dark.green() - ink.green()) + abs(dark.blue() - ink.blue()) < 60
    assert layers.style("names")[1].lightness() < 160           # muted ink, not pale


def test_names_avoid_each_other_vc_labels_and_recorded_squares(qapp, tmp_path):
    from PySide6.QtCore import QRectF
    _write(tmp_path, "names", "gb", [_pt("City", "Oxford", 50000, 50000)], "point")
    _write(tmp_path, "names", "county", [_pt("Town", "Headington", 50300, 50000),
                                         _pt("Town", "Banbury", 20000, 70000)], "point")
    out, _i = _names_at(tmp_path, 50_000)
    assert [n for n, _r in out] == ["Oxford", "Banbury"]        # Headington would touch Oxford
    free, _i = _names_at(tmp_path, 50_000, taken=[QRectF(0, 0, 600, 600)])
    assert free == []                                           # a VC label region everywhere
    sq, _i = _names_at(tmp_path, 50_000, occupied=lambda rect: rect.center().y() < 250)
    assert [n for n, _r in sq] == ["Oxford"]                    # Banbury is on a recorded square


def test_names_are_in_the_kept_picture_off_by_default_and_follow_the_colour(qapp, tmp_path,
                                                                             settings_sandbox):
    _write(tmp_path, "land", "county", [_sq(0, 0, 100000, 100000)])
    _write_names(tmp_path)
    m = _map(tmp_path)
    plain = m.grab().toImage()
    assert m.layers_drawn() == ["land"] and m._layers_on == {"water"}
    renders = m.picture_renders
    m.set_layers({"names"})
    on = m.grab().toImage()
    assert m.picture_renders == renders + 1 and m.layers_drawn() == ["land", "names"]
    x, y = m.fit().to_px(50000, 50000)
    box = [(i, j) for i in range(int(x) - 25, int(x) + 25) for j in range(int(y) - 8, int(y) + 8)]
    assert sum(plain.pixel(i, j) != on.pixel(i, j) for i, j in box) > 30      # the name is there
    m.grab()
    assert m.picture_renders == renders + 1                      # a repaint reuses the picture
    layers.set_colour("names", "#aa0000")
    m.refresh_layer_colours()
    red = m.grab().toImage()
    assert any(red.pixelColor(i, j).red() > 140 > red.pixelColor(i, j).green() for i, j in box)


def test_names_on_the_atlas_page_and_credit(qapp, tmp_path):
    _write(tmp_path, "land", "gb", [_sq(0, 0, 100000, 100000)])
    _write_names(tmp_path)
    m = _map(tmp_path)
    m.set_layers({"names"})
    assert m.credit_line().count(ATTR) == 1
    img = m.render_sheet("T", dpi=60)
    assert img.width() > 100


# ---------------------------------------------------------------- relief

def test_relief_is_over_the_land_and_under_the_other_layers(qapp, tmp_path, settings_sandbox):
    _write(tmp_path, "land", "county", [_sq(0, 0, 100000, 100000)])
    _write(tmp_path, "woodland", "county", [_sq(12000, 12000, 38000, 38000)])
    grey = np.full((40, 40), 255, np.uint8)
    grey[:, :20] = 60                                            # the west half is in shadow
    _relief(tmp_path, grey)
    m = _map(tmp_path)
    m.set_layers({"woodland"})
    wood, shadow_off, clear_off = (_pixel(m, 25500, 25500), _pixel(m, 25500, 75500),
                                   _pixel(m, 75500, 75500))
    assert shadow_off == clear_off == LAND_C
    m.set_layers({"woodland", "relief"})
    assert m.layers_drawn() == ["land", "relief", "woodland"]
    shadow, clear = _pixel(m, 25500, 75500), _pixel(m, 75500, 75500)
    assert clear == LAND_C                                       # white = no change
    from PySide6.QtGui import QColor
    assert QColor(shadow).lightness() < QColor(LAND_C).lightness() - 15      # darker, but pale
    assert QColor(shadow).lightness() > 120                                  # (low opacity)
    assert _pixel(m, 25500, 25500) == wood                       # woodland is drawn over it


def test_relief_clear_cells_leave_the_sea_alone(qapp, tmp_path):
    grey = np.full((40, 40), 60, np.uint8)
    alpha = np.zeros((40, 40), np.uint8)
    alpha[:, 20:] = 255
    _relief(tmp_path, grey, alpha)
    _write(tmp_path, "land", "county", [_sq(0, 0, 100000, 100000)])
    m = _map(tmp_path)
    m.set_layers({"relief"})
    from PySide6.QtGui import QColor
    assert _pixel(m, 25500, 55500) == LAND_C
    assert QColor(_pixel(m, 75500, 55500)).lightness() < QColor(LAND_C).lightness() - 15


# ---------------------------------------------------------------- the warm-up

def test_warm_up_does_not_build_paths_for_names_or_relief(qapp, tmp_path):
    from shared.maps.map_warmup import warm_steps
    _write(tmp_path, "land", "gb", [_sq(0, 0, 100000, 100000)])
    _write(tmp_path, "rail", "gb", [{"bbox": [0, 0, 9, 9], "line": [[0, 0], [9, 9]]}], "line")
    _write_names(tmp_path)
    _relief(tmp_path, np.full((4, 4), 200, np.uint8))
    m = _map(tmp_path)
    m.set_layers({"names", "rail", "relief"})
    built = []
    real = m._layer_shape
    m._layer_shape = lambda fit, key, view=None: (built.append(key), real(fit, key, view=view))[1]
    for _kind, fn in warm_steps(m):
        fn()
    assert sorted(built) == ["land", "rail"]
