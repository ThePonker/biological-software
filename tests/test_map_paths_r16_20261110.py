"""Mapping tab, Round 16 (10 Nov 2026), A4: the vice-county polygons and lines are built as paths
in metres (numpy, shared/maps/layer_bin.py) and turned into QPolygonF through layer_transform by
Qt, not one QPointF per point -- and the picture is pixel for pixel what the old drawing gave.

The "before" is the old drawing written out here (a QPolygonF of QPointF per ring, drawPolygon /
drawPolyline), drawn on one image; the "after" is GridMap's own draw. Small purpose-made geojson
and gb_outline.json in tmp_path.
"""
import json
import os
import random

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPolygonF  # noqa: E402

W, H = 300, 380


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _ring(lat0, lon0, lat1, lon1, seed, n=40):
    rnd = random.Random(seed)
    pts = ([[lat0, lon0 + (lon1 - lon0) * i / n] for i in range(n)]
           + [[lat0 + (lat1 - lat0) * i / n, lon1] for i in range(n)]
           + [[lat1, lon1 - (lon1 - lon0) * i / n] for i in range(n)]
           + [[lat1 - (lat1 - lat0) * i / n, lon0] for i in range(n)])
    pts = [[a + rnd.uniform(-0.0006, 0.0006), b + rnd.uniform(-0.0006, 0.0006)] for a, b in pts]
    return pts + [pts[0]]


def _data(tmp_path, outline):
    boxes = {1: (51.0, -2.0, 51.5, -1.4), 2: (51.0, -1.4, 51.5, -0.8),
             3: (51.5, -2.0, 52.0, -1.4), 4: (51.5, -1.4, 52.0, -0.8)}
    feats = [{"type": "Feature", "properties": {"VCNUMBER": vc, "VCNAME": f"V{vc}"},
              "geometry": {"type": "Polygon", "coordinates": [_ring(*b, seed=vc)]}}
             for vc, b in boxes.items()]
    feats.append({"type": "Feature", "properties": {"VCNUMBER": 5, "VCNAME": "Isles"},
                  "geometry": {"type": "MultiPolygon", "coordinates": [
                      [_ring(50.6, -1.2, 50.8, -0.9, 9, 20)], [_ring(50.85, -1.2, 50.95, -1.0, 10, 20)]]}})
    gj = tmp_path / "vc.geojson"
    gj.write_text(json.dumps({"type": "FeatureCollection", "features": feats}), encoding="utf-8")
    maps = tmp_path / "maps"
    maps.mkdir()
    if outline:       # two districts sharing a border (gb_outline.json: the districts and the coast)
        a = [[400000, 100000], [460000, 100000], [460000, 140000], [461000, 180000], [460000, 260000],
             [400000, 260000], [400000, 100000]]
        b = [[460000, 100000], [520000, 100000], [520000, 260000], [460000, 260000], [461000, 180000],
             [460000, 140000], [460000, 100000]]
        (maps / "gb_outline.json").write_text(json.dumps({"rings": [a, b], "bounds": [0, 0, 7e5, 13e5]}),
                                              encoding="utf-8")
    return str(gj), str(maps)


def _map(tmp_path, outline):
    from shared.maps.grid_map import GridMap
    gj, maps = _data(tmp_path, outline)
    m = GridMap(geojson_path=gj, maps_dir=maps)
    m.resize(W, H)
    m.set_vc_labels(False)              # no text: no fonts needed
    m.highlight_vcs([1, 4])
    m.set_outlined_vc(2)
    m._districts_on = True
    return m


# ---------------------------------------------------------------- the picture before R16

def _poly(fit, ring):
    return QPolygonF([QPointF(*fit.to_px(e, n)) for e, n in ring])


def _draw_before(m, p, fit, k):
    """What draw_base and draw drew before R16 for the VC / land / coast / districts parts."""
    from shared.maps.map_layers import DISTRICT_W, TINT_ALPHA, district_pen
    from shared.maps.species_dist_map import _COAST_C, _LAND_C
    from shared.maps.vc_labels import boundary_colour, BOUNDARY_W, OUTLINE_W
    from shared.maps._theme import theme
    land = [_poly(fit, r) for r in m._land]
    vcs = {vc: [_poly(fit, r) for r in rings] for vc, rings in m._topo().items()}
    land_c = QColor(_LAND_C)
    p.setPen(QPen(land_c, 0.8 * k))
    p.setBrush(QBrush(land_c))
    for poly in land:
        p.drawPolygon(poly)
    hi = QColor(theme.MOSS)
    hi.setAlpha(TINT_ALPHA)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(hi))
    for vc in m._vc_highlight:
        for poly in vcs.get(vc, ()):
            p.drawPolygon(poly)

    def lines(name):
        return [QPolygonF([QPointF(*fit.to_px(e, n)) for e, n in c]) for c in m._chains(name)]
    p.setPen(QPen(QColor(_COAST_C), 0.7 * k))
    p.setBrush(Qt.BrushStyle.NoBrush)
    for line in lines("coast"):
        p.drawPolyline(line)
    m._draw_grid(p, fit, k)
    pen = QPen(boundary_colour(), BOUNDARY_W * k)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    for line in lines("vc_inland"):
        p.drawPolyline(line)
    if m.has_districts():
        assert DISTRICT_W
        p.setPen(district_pen(k))
        for line in lines("districts"):
            p.drawPolyline(line)
    pen = QPen(QColor(theme.MOSS_HOVER), OUTLINE_W * k)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    for poly in vcs.get(m._vc_outline, ()):
        p.drawPolygon(poly)


def _image(draw):
    img = QImage(W, H, QImage.Format.Format_ARGB32)
    img.fill(0xFFFFFFFF)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    draw(p)
    p.end()
    return img


def _differing(a: QImage, b: QImage) -> int:
    return sum(1 for y in range(a.height()) for x in range(a.width()) if a.pixel(x, y) != b.pixel(x, y))


VIEWS = {"gb": None, "county": (380000, 90000, 540000, 280000), "tight": (430000, 120000, 480000, 190000)}


@pytest.mark.parametrize("outline", [False, True], ids=["vc land", "gb_outline land"])
@pytest.mark.parametrize("view", list(VIEWS))
def test_picture_is_pixel_identical_to_the_qpolygonf_drawing(qapp, tmp_path, outline, view):
    m = _map(tmp_path, outline)
    if VIEWS[view]:
        m.set_extent(VIEWS[view])
    fit = m.fit()
    before = _image(lambda p: _draw_before(m, p, fit, 1.0))
    after = _image(lambda p: m.draw(p, fit, 1.0, selected=False))
    assert _differing(before, after) == 0
    assert before != _image(lambda p: None)              # the comparison is of a real picture


def test_picture_is_identical_with_the_page_scale_and_without_boundaries(qapp, tmp_path):
    m = _map(tmp_path, True)
    m.set_extent(VIEWS["county"])
    fit = m.fit()
    for k in (0.5, 3.0, 5.0):
        before = _image(lambda p: _draw_before(m, p, fit, k))
        after = _image(lambda p: m.draw(p, fit, k, selected=False))
        assert _differing(before, after) == 0
    m.set_vc_boundaries(False)
    after = _image(lambda p: m.draw(p, fit, 1.0, selected=False))
    assert _differing(_image(lambda p: _draw_before(m, p, fit, 1.0)), after) > 0   # the switch still works


# ---------------------------------------------------------------- how it is built

def test_no_qpointf_is_made_for_the_vc_rings(qapp, tmp_path, monkeypatch):
    """The point of A4: no Python QPointF per point (the pattern that crashed Python 3.14.0's GC)."""
    m = _map(tmp_path, False)
    m.set_extent(VIEWS["county"])
    m._topo()
    for name in ("coast", "vc_inland"):
        m._chains(name)                 # the coast split's land raster is Qt painting, once: not under test
    calls = []
    real = QPointF.__init__
    monkeypatch.setattr(QPointF, "__init__", lambda self, *a, **k: (calls.append(1), real(self, *a, **k))[1])
    land, vcs = m._polygons(m.fit())
    m._lines("coast", m.fit())
    m._lines("vc_inland", m.fit())
    assert sum(len(vcs[v]) for v in vcs) > 0
    assert not calls


def test_vc_polygons_are_made_only_for_the_vcs_asked_for(qapp, tmp_path):
    m = _map(tmp_path, False)
    fit = m.fit()
    _land, vcs = m._polygons(fit)
    assert m._metre_polys[1] == {}                      # nothing built yet
    assert 3 in vcs and 99 not in vcs and len(vcs) == 5 and vcs.get(99, ()) == ()
    assert vcs[3] and set(m._metre_polys[1]) == {3}
    assert m._polygons(fit)[1] is vcs                    # kept while the fit is the same
    m.resize(W + 40, H)
    assert m._polygons(m.fit())[1] is not vcs and set(m._metre_polys[1]) == {3}   # metres kept, mapped again


def test_the_polygons_are_the_rings_through_layer_transform(qapp, tmp_path):
    from shared.maps.map_layers import layer_transform
    m = _map(tmp_path, False)
    fit = m.fit()
    _land, vcs = m._polygons(fit)
    for vc in (1, 3):
        assert len(vcs[vc]) == len(m._topo()[vc])
        for ring, poly in zip(m._topo()[vc], vcs[vc]):
            assert poly.size() == len(ring)
            for i, (e, n) in enumerate(ring):
                x, y = fit.to_px(e, n)
                assert abs(poly[i].x() - x) < 1e-6 and abs(poly[i].y() - y) < 1e-6
    chains = m._chains("coast")
    for chain, poly in zip(chains, m._lines("coast", fit)):
        assert poly.size() == len(chain)
    assert layer_transform(fit).m11() == fit.scale


# ---------------------------------------------------------------- the corner note for layers that failed to load

def test_the_load_error_note_is_drawn_last_when_its_module_exists_and_skipped_when_not(qapp, tmp_path, monkeypatch):
    """shared/maps/layer_notes.py is written separately: without it nothing is drawn (and nothing
    fails); with it, draw_load_errors(painter, rect, errors) is called after the map is drawn."""
    import sys
    import types
    from shared.maps import layers
    m = _map(tmp_path, False)
    import shared.maps as maps_pkg
    monkeypatch.setitem(sys.modules, "shared.maps.layer_notes", None)      # not there: ImportError
    monkeypatch.delattr(maps_pkg, "layer_notes", raising=False)            # (an earlier import sets it)
    m.grab()
    calls = []
    fake = types.ModuleType("shared.maps.layer_notes")
    fake.draw_load_errors = lambda p, rect, errors: calls.append((rect.width(), list(errors)))
    monkeypatch.setitem(sys.modules, "shared.maps.layer_notes", fake)
    monkeypatch.setattr(maps_pkg, "layer_notes", fake, raising=False)
    monkeypatch.setattr(layers, "load_errors", lambda: ["woodland: unreadable"], raising=False)
    m.grab()
    assert calls == [(m.width(), ["woodland: unreadable"])]
    calls.clear()
    monkeypatch.setattr(layers, "load_errors", lambda: [], raising=False)
    m.grab()
    assert calls == []                                          # nothing failed: no note
