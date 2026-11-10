"""Mapping tab, Round 16 (10 Nov 2026), B3: after a paint in county view the numpy half of the
ticked layers' paths for the area the pan is heading into is prepared in one worker thread
(shared/maps/map_ahead.py); the next paint only makes the QPainterPath from the bytes.
Small purpose-made layer files in tmp_path.
"""
# ruff: noqa: F811  (pytest fixtures imported from test_map_layers_r11)
import os
import threading
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from shared.maps import layer_bin, layers, map_ahead, map_layers  # noqa: E402
from tests.test_layer_bin_20261026 import _make, _same  # noqa: E402
from tests.test_map_layers_r11 import (_map, _sq, _write, qapp,  # noqa: E402,F401
                                       settings_sandbox)

VIEW = 60000


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setattr(map_ahead, "ENABLED", True)     # the look-ahead is off by default


def _tiles(n=14, step=30000, size=9000, t=None):
    """A grid of squares over 0..420 km, so every 25 km area holds something different."""
    out = []
    for i in range(n):
        for j in range(n):
            f = _sq(i * step, j * step, i * step + size, j * step + size,
                    hole=(i * step + 2000, j * step + 2000, i * step + 5000, j * step + 5000))
            if t:
                f["t"] = t[(i + j) % len(t)]
            out.append(f)
    return out


def _lines(n=14, step=30000):
    return [{"bbox": [i * step, 0, i * step + 20000, 420000],
             "line": [[i * step, 0], [i * step + 10000, 200000], [i * step + 20000, 420000]]} for i in range(n)]


def _maps(tmp_path, binary, keys=("woodland", "water", "ancient_woodland")):
    write = _make if binary else _write
    write(tmp_path, "land", "county", _tiles())
    write(tmp_path, "woodland", "county", _tiles())
    write(tmp_path, "ancient_woodland", "county", _tiles(t=("Ancient", "Replanted", "")))
    write(tmp_path, "rivers", "county", _lines(), kind="line")
    m = _map(tmp_path)
    m.resize(400, 400)
    m.set_layers(set(keys))
    return m


def _view(e, n):
    return (e, n, e + VIEW, n + VIEW)


def _paint_at(m, e, n):
    m.set_extent(_view(e, n))
    m.grab()


def _idle(m, seconds=15.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        with m._ahead_lock:
            if m._ahead_thread is None and m._ahead_pending is None:
                return
        time.sleep(0.005)
    raise AssertionError("the look-ahead did not finish")


def _store_boxes(m, key):
    with m._ahead_lock:
        return {ck[2] for ck in m._ahead_store if ck[0] == key}


# ---------------------------------------------------------------- the direction

def test_next_views_follow_the_pan_and_ignore_a_zoom():
    a = (100000, 100000, 160000, 160000)
    east = (120000, 100000, 180000, 160000)
    ahead = map_ahead.next_views(a, east)
    assert ahead == [(150000, 100000, 210000, 160000), (180000, 100000, 240000, 160000)]
    ne = map_ahead.next_views(a, (120000, 120000, 180000, 180000))
    assert ne[0] == (150000, 150000, 210000, 210000)                  # both axes moved
    south = map_ahead.next_views(a, (100000, 80000, 160000, 140000))
    assert south[0] == (100000, 50000, 160000, 110000)
    assert map_ahead.next_views(a, a) == []                            # nothing moved
    assert map_ahead.next_views(a, (110000, 110000, 150000, 150000)) == []      # a zoom about the centre
    assert map_ahead.next_views(a, (100000, 100000, 160000, 160000)) == []
    nearly_x = map_ahead.next_views(a, (120000, 101000, 180000, 161000))        # y barely moved: x only
    assert nearly_x[0][1] == 101000


# ---------------------------------------------------------------- the worker

@pytest.mark.parametrize("binary", [False, True], ids=["json", "binary"])
def test_areas_in_the_pan_direction_are_prepared_and_then_taken(qapp, tmp_path, settings_sandbox, binary):
    m = _maps(tmp_path, binary)
    _paint_at(m, 100000, 100000)
    assert m.ahead_built == 0                                  # first paint: no direction yet
    _paint_at(m, 120000, 100000)                               # panned east
    _idle(m)
    assert m.ahead_built > 0
    here = {lod_box[1] for lod_box in {(ck[1], ck[2]) for ck in m._layer_cache if ck[0] == "woodland"}}
    prepared = _store_boxes(m, "woodland")
    assert prepared and not prepared & here                    # only areas the GUI has not built
    assert all(box[0] > max(b[0] for b in here) for box in prepared)    # east of where we are
    assert _store_boxes(m, "rivers") and _store_boxes(m, "ancient_woodland")
    assert not [ck for ck in m._ahead_store if ck[0] == "districts"]   # not ticked / not on

    # the next area: taken from the store, equal to a path built the ordinary way
    m.set_extent(_view(180000, 100000))
    m._layer_view = _view(180000, 100000)
    used = m.ahead_used
    got = m._layer_shape(m.fit(), "woodland")
    other = _map(tmp_path)                                     # a map that never looked ahead
    other.resize(400, 400)
    other.set_extent(_view(180000, 100000))
    other._layer_view = _view(180000, 100000)
    assert m.ahead_used == used + 1
    _same(got, other._layer_shape(other.fit(), "woodland"))
    assert got.elementCount() > 0
    classes = m._layer_classes(m.fit(), "ancient_woodland")
    assert classes == other._layer_classes(other.fit(), "ancient_woodland") and len(classes) == 3


def test_a_classed_layer_is_prepared_per_class_and_equal(qapp, tmp_path, settings_sandbox):
    m = _maps(tmp_path, False, keys=("ancient_woodland",))
    _paint_at(m, 100000, 100000)
    _paint_at(m, 120000, 100000)
    _idle(m)
    (ck,) = [c for c in m._ahead_store if c[0] == "ancient_woodland" and c[2] == m._layer_ck(
        m.fit(), "ancient_woodland", _view(150000, 100000))[1]]
    assert ck[3] is True                                       # classed: one path a class
    parts, order, _n = m._ahead_store[ck]
    assert set(parts) == set(order) == {"Ancient", "Replanted", ""}
    other = _map(tmp_path)
    other.resize(400, 400)
    other.set_layers({"ancient_woodland"})
    for mm in (m, other):
        mm.set_extent(_view(150000, 100000))
        mm._layer_view = _view(150000, 100000)
    used = m.ahead_used
    assert m._layer_classes(m.fit(), "ancient_woodland") == order
    assert m.ahead_used == used + 1
    for c in other._layer_classes(other.fit(), "ancient_woodland"):
        _same(m._layer_shape(m.fit(), "ancient_woodland", cls=c),
              other._layer_shape(other.fit(), "ancient_woodland", cls=c))


def test_no_qt_object_is_made_off_the_gui_thread(qapp, tmp_path, settings_sandbox, monkeypatch):
    seen = {"paths": set(), "parts": set()}
    real_path, real_parts = layer_bin.path_from_bytes, map_ahead.layer_parts
    monkeypatch.setattr(layer_bin, "path_from_bytes",
                        lambda pb: (seen["paths"].add(threading.get_ident()), real_path(pb))[1])
    spy = lambda *a: (seen["parts"].add(threading.get_ident()), real_parts(*a))[1]  # noqa: E731
    monkeypatch.setattr(map_ahead, "layer_parts", spy)           # the worker's
    monkeypatch.setattr(map_layers, "layer_parts", spy)          # the GUI's own builds
    m = _maps(tmp_path, True)
    _paint_at(m, 100000, 100000)
    _paint_at(m, 120000, 100000)
    _idle(m)
    m.set_extent(_view(180000, 100000))
    m._layer_view = _view(180000, 100000)
    m._layer_shape(m.fit(), "woodland")
    main = threading.get_ident()
    assert seen["paths"] == {main}                             # every QPainterPath on the GUI thread
    assert main in seen["parts"] and len(seen["parts"]) == 2    # and the numpy half in a worker too


def test_the_worker_runs_with_the_collector_off_and_leaves_it_on(qapp, tmp_path, settings_sandbox, monkeypatch):
    import gc
    states = []
    real = map_ahead.layer_parts
    monkeypatch.setattr(map_ahead, "layer_parts", lambda *a: (states.append(gc.isenabled()), real(*a))[1])
    was = gc.isenabled()
    m = _maps(tmp_path, True)
    _paint_at(m, 100000, 100000)
    _paint_at(m, 120000, 100000)
    _idle(m)
    assert False in states and gc.isenabled() == was


def test_only_ticked_layers_and_only_in_county_view(qapp, tmp_path, settings_sandbox):
    m = _maps(tmp_path, True, keys=("woodland",))
    _paint_at(m, 100000, 100000)
    _paint_at(m, 120000, 100000)
    _idle(m)
    assert {ck[0] for ck in m._ahead_store} == {"land", "woodland"}     # land is always drawn, rivers are not ticked
    m2 = _maps(tmp_path, True)
    m2.set_extent((0, 0, 300000, 300000))                       # wider than a county: the GB level
    m2.grab()
    m2.set_extent((50000, 0, 350000, 300000))
    m2.grab()
    time.sleep(0.05)
    assert m2.ahead_built == 0 and m2._ahead_thread is None


def test_the_store_is_cut_to_the_areas_now_wanted(qapp, tmp_path, settings_sandbox):
    m = _maps(tmp_path, True, keys=("woodland",))
    _paint_at(m, 100000, 100000)
    _paint_at(m, 120000, 100000)
    _idle(m)
    east = _store_boxes(m, "woodland")
    _paint_at(m, 120000, 120000)                               # now heading north
    _idle(m)
    wanted = {m._layer_ck(m.fit(), "woodland", v)[1]
              for v in map_ahead.next_views(_view(120000, 100000), _view(120000, 120000))}
    north = _store_boxes(m, "woodland")
    assert north and north <= wanted                           # nothing left over from the eastward guess
    assert east - wanted and not (east - wanted) & north


def test_the_store_is_held_to_its_size_limit(qapp, tmp_path, settings_sandbox, monkeypatch):
    monkeypatch.setattr(map_ahead, "MAX_BYTES", 1)
    m = _maps(tmp_path, True)
    _paint_at(m, 100000, 100000)
    _paint_at(m, 120000, 100000)
    _idle(m)
    assert 0 < len(m._ahead_store) <= 1                        # one went in, then the limit stopped it


def test_the_guis_cache_limit_still_holds_with_areas_taken_from_the_store(qapp, tmp_path, settings_sandbox):
    m = _maps(tmp_path, True, keys=("woodland",))
    e = 100000
    for step in range(8):
        _paint_at(m, e + step * 20000, 100000)
        _idle(m)
        areas = {(c[1], c[2]) for c in m._layer_cache if c[0] == "woodland"}
        assert len(areas) <= 4
    assert m.ahead_used > 0


def test_a_look_ahead_that_fails_leaves_the_paint_alone(qapp, tmp_path, settings_sandbox, monkeypatch):
    monkeypatch.setattr(map_ahead, "layer_parts", lambda *a: (_ for _ in ()).throw(RuntimeError("no")))
    m = _maps(tmp_path, True)
    _paint_at(m, 100000, 100000)
    _paint_at(m, 120000, 100000)
    _idle(m)
    assert m.ahead_built == 0 and m._ahead_store == {}
    assert layers.load(str(tmp_path), "woodland", "county")       # the data is untouched


def test_off_by_default_starts_no_worker_and_pauses_no_gc(qapp, tmp_path, settings_sandbox, monkeypatch):
    import gc
    monkeypatch.setattr(map_ahead, "ENABLED", False)
    monkeypatch.delenv("BIOSOFT_MAP_AHEAD", raising=False)
    m = _maps(tmp_path, True)
    _paint_at(m, 100000, 100000)
    _paint_at(m, 120000, 100000)
    assert m._ahead_thread is None and m.ahead_built == 0 and gc.isenabled()
    monkeypatch.setenv("BIOSOFT_MAP_AHEAD", "1")
    assert map_ahead.enabled()
