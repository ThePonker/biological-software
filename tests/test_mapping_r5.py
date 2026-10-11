"""Mapping tab, Round 5 (11 Oct 2026): each VC border drawn once (no doubled grey lines), no
pale slivers in the VC tint, districts above the VC layers, boundaries and districts under the
recorded squares, the selected VC's outline on top.

Geometry and draw-order tests; no font metrics (offscreen Qt on Windows has no fonts).
"""
import collections
import math
import os

import pytest

import paths

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HAVE_VC = paths.VC_GEOJSON.exists()
needs_vc = pytest.mark.skipif(not HAVE_VC, reason="needs the vice-county geojson")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _key(a, b):
    a, b = tuple(a), tuple(b)
    return (a, b) if a <= b else (b, a)


def _edge_counts(chains):
    return collections.Counter(_key(c[i], c[i + 1]) for c in chains for i in range(len(c) - 1))


def _wiggly_pair():
    """Two 'VCs' side by side whose common border (x = 110 km) each holds with its OWN points,
    a few tens of metres apart, as the thinned geojson gives them."""
    ys = list(range(100000, 110001, 500))
    west_border = [(110000 + (40 if i % 2 else -30), y) for i, y in enumerate(ys)]
    east_border = [(110000 + (-25 if i % 3 else 35), y + 170) for i, y in enumerate(ys[:-1])]
    west = [(100000, 100000)] + west_border + [(110000, 110000), (100000, 110000),
                                               (100000, 100000)]
    east = [(110000, 100000), (120000, 100000), (120000, 110000), (110000, 110000)] + \
        list(reversed(east_border)) + [(110000, 100000)]
    return {1: [west], 2: [east]}


# ---------------------------------------------------------------- 1: each border once

def test_unique_chains_emits_a_shared_edge_once():
    from shared.maps.vc_topology import unique_chains
    west = [(0, 0), (0, 10), (10, 10), (10, 0), (0, 0)]
    east = [(10, 0), (10, 10), (20, 10), (20, 0), (10, 0)]
    counts = _edge_counts(unique_chains([west, east]))
    assert set(counts.values()) == {1}
    assert len(counts) == 7                       # 4 + 4 edges, the shared one once
    assert _key((10, 0), (10, 10)) in counts


def test_snap_makes_neighbours_share_their_border_points():
    """Before: no edge in common (two lines side by side). After: the later VC holds the
    earlier VC's own points along the border, so the border is emitted once."""
    from shared.maps.vc_topology import snap_rings, unique_chains
    vcs = _wiggly_pair()
    before = _edge_counts([r for rs in vcs.values() for r in rs])
    assert max(before.values()) == 1
    snapped = snap_rings(vcs)
    edges = _edge_counts([r for rs in snapped.values() for r in rs])
    shared = [k for k, n in edges.items() if n == 2]
    assert len(shared) >= 20                      # the whole border, edge for edge
    assert all(abs(a[0] - 110000) < 50 and abs(b[0] - 110000) < 50 for a, b in shared)
    assert max(_edge_counts(unique_chains(r for rs in snapped.values() for r in rs)).values()) == 1
    assert snapped[1] == vcs[1]                   # the first VC is never changed


@needs_vc
def test_real_vc_borders_drawn_once(qapp):
    """The real VCs: no edge of the boundary layer twice, and about half the line the R4
    layer drew (it stroked every border once per neighbour)."""
    from shared.maps.coast import split_edges
    from shared.maps.grid_map import GridMap
    m = GridMap(geojson_path=str(paths.VC_GEOJSON))
    inland = m._chains("vc_inland")
    assert max(_edge_counts(inland).values()) == 1
    km = sum(math.dist(c[i], c[i + 1]) for c in inland for i in range(len(c) - 1)) / 1000
    old = split_edges([r for rs in m._vc_rings.values() for r in rs])[1]
    old_km = sum(math.dist(c[i], c[i + 1]) for c in old for i in range(len(c) - 1)) / 1000
    # How much shorter depends on the outline file's detail: about 0.6 with the 14 MB
    # rebuild of vc_brc_wgs84.geojson, about 0.75 with the older 2 MB file (every 5th
    # point) still on Wil's PC. Each edge once (above) is the real check.
    assert km < 0.85 * old_km
    # Oxfordshire / Buckinghamshire: their border is now the same points in both rings
    topo = m._topo()
    e23 = _edge_counts(topo[23])
    e24 = _edge_counts(topo[24])
    assert len(set(e23) & set(e24)) > 50
    # and each VC keeps its shape (area within 0.5 %)
    from shared.maps.vc_map import ring_area
    for vc in (23, 24, 57, 112):
        a = sum(abs(ring_area(r)) for r in m._vc_rings[vc])
        b = sum(abs(ring_area(r)) for r in topo[vc])
        assert abs(b - a) / a < 0.005


@pytest.mark.skipif(not (paths.MAPS_DIR / "gb_outline.json").exists(),
                    reason="needs data/maps/gb_outline.json")
def test_real_districts_drawn_once(qapp):
    from shared.maps.grid_map import GridMap
    m = GridMap(geojson_path=str(paths.VC_GEOJSON) if HAVE_VC else None,
                maps_dir=str(paths.MAPS_DIR))
    assert m.has_districts()
    assert max(_edge_counts(m._chains("districts")).values()) == 1


# ---------------------------------------------------------------- 2-4: draw order

def _order(m, monkeypatch):
    import shared.maps.grid_map as gm
    import shared.maps.map_layers as ml
    seen = []

    def spy(owner, name, tag):
        real = getattr(owner, name)
        monkeypatch.setattr(owner, name, lambda *a, **k: (seen.append(tag), real(*a, **k))[1])
    spy(m, "_draw_land", "land")
    spy(m, "_draw_tint", "tint")
    spy(m, "_draw_districts", "districts")
    spy(m, "_draw_squares", "squares")
    spy(ml, "draw_boundaries", "bounds")
    spy(gm, "draw_outline", "outline")
    spy(gm, "draw_labels", "labels")
    return seen


@needs_vc
def test_draw_order_bottom_to_top(qapp, monkeypatch):
    """land, tint, VC boundaries, districts, squares, the selected VC's outline, labels."""
    from shared.maps.grid_map import GridMap
    m = GridMap(geojson_path=str(paths.VC_GEOJSON), maps_dir=str(paths.MAPS_DIR))
    monkeypatch.setattr(m, "has_districts", lambda: True)
    m.resize(400, 500)
    m.set_extent(m.vc_extent(23))
    m.highlight_vcs([23, 24])
    m.set_outlined_vc(23)
    m.set_districts(True)
    seen = _order(m, monkeypatch)
    m.render_sheet("T", dpi=60)
    assert seen == ["land", "tint", "bounds", "districts", "squares", "outline", "labels"]
    seen.clear()
    m.grab()
    assert seen == ["land", "tint", "bounds", "districts", "squares", "outline", "labels"]


@needs_vc
def test_recorded_square_covers_the_boundary_and_the_outline_covers_the_square(qapp):
    """Pixels, no fonts: a recorded square lying across a VC boundary shows its own colour
    where the boundary runs (boundaries are under the squares); the selected VC's green
    outline still shows across a square (on top)."""
    from PySide6.QtGui import QColor
    from shared.maps import grid_squares as gs
    from shared.maps._theme import theme
    from shared.maps.grid_map import GridMap
    from shared.maps.vc_labels import point_in_ring
    m = GridMap(geojson_path=str(paths.VC_GEOJSON))
    m.resize(600, 600)
    m.set_vc_labels(False)
    ext = m.vc_extent(23)
    m.set_extent(ext)
    # a point on a border inside the view that is not VC23's own (VC23 gets the outline)
    pt = next(p for c in m._chains("vc_inland") for p in c
              if ext[0] + 5000 < p[0] < ext[2] - 5000 and ext[1] + 5000 < p[1] < ext[3] - 5000
              and not any(point_in_ring(p[0], p[1], r) for r in m._vc_rings[23])
              and all(math.dist(p, q) > 3000 for r in m._vc_rings[23] for q in r))
    lab = gs.square_for_point(pt[0], pt[1], gs.HECTAD)
    m.set_squares({lab: {"count": 1, "fill": "#ff0000"}}, gs.HECTAD)
    img = m.grab().toImage()
    x, y = m.fit().to_px(*pt)
    c = img.pixelColor(round(x), round(y))
    assert (c.red(), c.green(), c.blue()) == (255, 0, 0)
    # the selected VC's outline across a square: a square on VC23's own outline
    e, n = m._topo()[23][0][len(m._topo()[23][0]) // 3]
    lab2 = gs.square_for_point(e, n, gs.HECTAD)
    m.set_squares({lab2: {"count": 1, "fill": "#ff0000"}}, gs.HECTAD)
    m.set_outlined_vc(23)
    img = m.grab().toImage()
    x, y = m.fit().to_px(e, n)
    c = img.pixelColor(round(x), round(y))
    # an antialiased mix of the outline's green and the square's red: never the bare square
    assert c.red() < 160 and c.green() > 60
    assert QColor(theme.MOSS_HOVER).green() > 60


def test_district_pen_is_dashed_thin_and_lighter_than_boundaries(qapp):
    from shared.maps.map_layers import district_pen
    from shared.maps.vc_labels import BOUNDARY_W
    pen = district_pen(1.0)
    assert pen.dashPattern() and pen.widthF() < BOUNDARY_W
    c = pen.color()
    from shared.maps.vc_labels import boundary_colour
    assert c.lightness() > boundary_colour().lightness()
