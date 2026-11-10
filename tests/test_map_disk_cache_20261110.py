"""Mapping tab, Round 16 (10 Nov 2026), B1: the vice-county polygons, the shared-border rings and
the coast / inland split are kept on disk (shared/maps/map_disk_cache.py) and read back next run.
A small purpose-made geojson in tmp_path; nothing from Wil's data.
"""
import json
import os
import random

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from shared.maps import coast, map_disk_cache, vc_map, vc_topology  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _ring(lat0, lon0, lat1, lon1, seed, n=30):
    rnd = random.Random(seed)
    pts = ([[lat0, lon0 + (lon1 - lon0) * i / n] for i in range(n)]
           + [[lat0 + (lat1 - lat0) * i / n, lon1] for i in range(n)]
           + [[lat1, lon1 - (lon1 - lon0) * i / n] for i in range(n)]
           + [[lat1 - (lat1 - lat0) * i / n, lon0] for i in range(n)])
    pts = [[a + rnd.uniform(-0.0006, 0.0006), b + rnd.uniform(-0.0006, 0.0006)] for a, b in pts]
    return pts + [pts[0]]


def _geojson(tmp_path, name="vc.geojson"):
    boxes = {1: (51.0, -2.0, 51.5, -1.4), 2: (51.0, -1.4, 51.5, -0.8), 3: (51.5, -2.0, 52.0, -1.4)}
    feats = [{"type": "Feature", "properties": {"VCNUMBER": vc, "VCNAME": f"County {vc}"},
              "geometry": {"type": "Polygon", "coordinates": [_ring(*b, seed=vc)]}}
             for vc, b in boxes.items()]
    feats.append({"type": "Feature", "properties": {"VCNUMBER": 4, "VCNAME": "Isles"},
                  "geometry": {"type": "MultiPolygon", "coordinates": [
                      [_ring(50.6, -1.2, 50.8, -0.9, 9, 20)], [_ring(50.85, -1.2, 50.95, -1.0, 10, 20)]]}})
    path = tmp_path / name
    path.write_text(json.dumps({"type": "FeatureCollection", "features": feats}), encoding="utf-8")
    return str(path)


@pytest.fixture()
def fresh(monkeypatch):
    """The process's own caches left alone; the disk cache on."""
    monkeypatch.delenv("BIOSOFT_NO_MAP_CACHE", raising=False)
    monkeypatch.setattr(vc_map, "_CACHE", {})
    monkeypatch.setattr(vc_map, "_NAMES", {})
    monkeypatch.setattr(vc_topology, "_SNAP_CACHE", {})
    monkeypatch.setattr(coast, "_SPLIT_CACHE", {})


def _cache_files(tmp_path):
    d = tmp_path / "cache"
    return sorted(p.name for p in d.iterdir()) if d.is_dir() else []


# ---------------------------------------------------------------- the polygons

def test_polygons_from_disk_equal_the_computed_ones(tmp_path, fresh):
    gj = _geojson(tmp_path)
    computed = vc_map.load_vc_polygons(gj)
    names = dict(vc_map._NAMES[gj])
    assert _cache_files(tmp_path) == ["vc.vcpoly_300.npz"]
    vc_map._CACHE.clear()
    vc_map._NAMES.clear()
    again = vc_map.load_vc_polygons(gj)
    assert again is not computed
    assert again == computed                                   # points, bounds, exactly
    assert list(again[0]) == list(computed[0])                 # the VCs in the same order
    assert vc_map._NAMES[gj] == names == {1: "County 1", 2: "County 2", 3: "County 3", 4: "Isles"}
    assert all(isinstance(pt, tuple) for rings in again[0].values() for r in rings for pt in r)


def test_the_disk_copy_is_really_what_is_read(tmp_path, fresh, monkeypatch):
    gj = _geojson(tmp_path)
    vc_map.load_vc_polygons(gj)
    vc_map._CACHE.clear()
    monkeypatch.setattr(vc_map.json, "load", lambda *a, **k: pytest.fail("the geojson was read"))
    assert vc_map.load_vc_polygons(gj)[0]


def test_each_tolerance_has_its_own_file(tmp_path, fresh):
    gj = _geojson(tmp_path)
    fine = vc_map.load_vc_polygons(gj, tol=100.0)
    coarse = vc_map.load_vc_polygons(gj)
    assert _cache_files(tmp_path) == ["vc.vcpoly_100.npz", "vc.vcpoly_300.npz"]
    vc_map._CACHE.clear()
    assert vc_map.load_vc_polygons(gj, tol=100.0) == fine
    assert vc_map.load_vc_polygons(gj) == coarse


def test_a_changed_source_is_not_matched(tmp_path, fresh):
    gj = _geojson(tmp_path)
    first = vc_map.load_vc_polygons(gj)
    vc_map._CACHE.clear()
    feats = json.loads(open(gj, encoding="utf-8").read())
    feats["features"] = feats["features"][:2]                  # a different file (size and time)
    open(gj, "w", encoding="utf-8").write(json.dumps(feats))
    second = vc_map.load_vc_polygons(gj)
    assert set(second[0]) == {1, 2} and second != first


def test_a_new_code_version_is_not_matched(tmp_path, fresh, monkeypatch):
    gj = _geojson(tmp_path)
    vc_map.load_vc_polygons(gj)
    vc_map._CACHE.clear()
    monkeypatch.setattr(map_disk_cache, "CODE_VERSION", map_disk_cache.CODE_VERSION + 1)
    assert map_disk_cache.load(gj, "vcpoly_300", repr(300.0)) is None


@pytest.mark.parametrize("damage", [b"", b"not an npz at all", None])
def test_a_damaged_cache_is_ignored_and_rebuilt(tmp_path, fresh, damage):
    gj = _geojson(tmp_path)
    computed = vc_map.load_vc_polygons(gj)
    target = tmp_path / "cache" / "vc.vcpoly_300.npz"
    if damage is None:                                         # a good zip, the wrong arrays
        np.savez(target, stamp=np.array(["x"]))
    else:
        target.write_bytes(damage)
    vc_map._CACHE.clear()
    assert vc_map.load_vc_polygons(gj) == computed
    vc_map._CACHE.clear()                                      # and the rebuilt file is good again
    assert map_disk_cache.load(gj, "vcpoly_300", repr(300.0)) is not None


def test_writes_leave_no_temporary_file_and_survive_a_read_only_place(tmp_path, fresh):
    gj = _geojson(tmp_path)
    vc_map.load_vc_polygons(gj)
    assert not [n for n in _cache_files(tmp_path) if n.endswith(".tmp")]
    (tmp_path / "cache").rename(tmp_path / "cache_old")
    (tmp_path / "cache").write_text("a file where the folder should be")   # mkdir cannot succeed
    vc_map._CACHE.clear()
    assert vc_map.load_vc_polygons(gj)[0]                      # computed; the failed write is silent


def test_the_cache_can_be_switched_off(tmp_path, fresh, monkeypatch):
    monkeypatch.setenv("BIOSOFT_NO_MAP_CACHE", "1")
    vc_map.load_vc_polygons(_geojson(tmp_path))
    assert _cache_files(tmp_path) == []


# ---------------------------------------------------------------- snapped rings and the split

def test_snapped_rings_from_disk_equal_the_computed_ones(tmp_path, fresh):
    gj = _geojson(tmp_path)
    rings, _b = vc_map.load_vc_polygons(gj)
    key = ("vc", gj, 300.0)
    computed = vc_topology.snap_rings_cached(key, rings, source=gj)
    assert "vc.snap.npz" in _cache_files(tmp_path)
    vc_topology._SNAP_CACHE.clear()
    again = vc_topology.snap_rings_cached(key, {}, source=gj)  # no rings given: it can only be from disk
    assert again == computed == vc_topology.snap_rings(rings)
    assert list(again) == list(computed)


def test_split_from_disk_equals_the_computed_one(qapp, tmp_path, fresh):
    gj = _geojson(tmp_path)
    rings, _b = vc_map.load_vc_polygons(gj)
    topo = [r for rs in vc_topology.snap_rings(rings).values() for r in rs]
    key = ("vc_topo", gj, 300.0, "r5")
    disk = (gj, "vc_topo")
    computed = coast.split_edges_cached(key, topo, lambda: vc_topology.unique_chains(topo), disk=disk)
    assert computed == coast.split_edges(topo, lines=vc_topology.unique_chains(topo))
    assert computed[0] and computed[1]                         # coast and inland both there
    coast._SPLIT_CACHE.clear()
    assert not coast.has_split(key) and coast.load_disk(key, disk) and coast.has_split(key)
    assert coast._SPLIT_CACHE[key] == computed
    coast._SPLIT_CACHE.clear()

    def boom():
        raise AssertionError("worked out again")
    assert coast.split_edges_cached(key, topo, boom, disk=disk) == computed


def test_a_map_started_on_a_warm_cache_draws_what_a_cold_one_does(qapp, tmp_path, fresh):
    """Two GridMaps on one geojson: the second is made entirely from disk; same chains."""
    from shared.maps.grid_map import GridMap
    gj = _geojson(tmp_path)
    cold = GridMap(geojson_path=gj, maps_dir=None)
    chains = {n: cold._chains(n) for n in ("coast", "vc_inland")}
    polys = cold._topo()
    assert {"vc.vcpoly_300.npz", "vc.snap.npz", "vc.split_vc_topo.npz"} <= set(_cache_files(tmp_path))
    for module_cache in (vc_map._CACHE, vc_topology._SNAP_CACHE, coast._SPLIT_CACHE):
        module_cache.clear()
    warm = GridMap(geojson_path=gj, maps_dir=None)
    assert warm._topo() == polys
    assert {n: warm._chains(n) for n in ("coast", "vc_inland")} == chains


def test_packing_round_trips_ragged_lines():
    lines = [[(0.0, 1.5), (2.25, 3.0)], [], [(1e6, 1.3e6), (7.0, 8.0), (9.0, 10.0)]]
    a = map_disk_cache.pack_lines(lines)
    assert map_disk_cache.unpack_lines(a["off"], a["xy"]) == lines
    assert map_disk_cache.unpack_lines(*map_disk_cache.pack_lines([]).values()) == []
