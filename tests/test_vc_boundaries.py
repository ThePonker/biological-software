"""Vice counties on boundaries, at the coast and for coarse refs (F29, I3b, 9 Oct 2026)."""
import json
import sqlite3

import pytest

import paths
from shared import osgb
from Observatum.src.services.vc_lookup_service import VCLookupService, _in_rings


def test_tetrads_parse_in_dinty_letters():
    assert osgb.gridref_to_en("SP58A") == (450000, 280000, 2000)
    assert osgb.gridref_to_en("SP58E") == (450000, 288000, 2000)
    assert osgb.gridref_to_en("SP58I") == (452000, 286000, 2000)       # I is a tetrad letter
    assert osgb.gridref_to_en("SP58Z") == (458000, 288000, 2000)
    assert osgb.gridref_to_en("SP58O") is None                          # O is not


def test_ray_cast_with_a_hole():
    outer = [[0, 0], [1000, 0], [1000, 1000], [0, 1000]]
    hole = [[400, 400], [600, 400], [600, 600], [400, 600]]
    assert _in_rings(100, 100, [outer, hole])
    assert not _in_rings(500, 500, [outer, hole])
    assert not _in_rings(1500, 500, [outer])


@pytest.fixture
def toy(tmp_path):
    """SP5820 split down x = 300 m: VC23 to the west, VC24 to the east; SP5920 all VC24;
    SP5720 coastal (half land, VC23) and missing from vc_lookup."""
    lk = sqlite3.connect(tmp_path / "vc_lookup.db")
    lk.execute("CREATE TABLE vc_lookup (grid_1km TEXT PRIMARY KEY, vc_number INTEGER NOT NULL)")
    lk.executemany("INSERT INTO vc_lookup VALUES (?, ?)", [("SP5820", 24), ("SP5920", 24)])
    lk.commit(); lk.close()
    sp = sqlite3.connect(tmp_path / "vc_splits.db")
    sp.execute("CREATE TABLE vc_split_squares (grid_1km TEXT, vc_number INTEGER, area_fraction REAL, "
               "rings_json TEXT)")
    west = [[[0, 0], [300, 0], [300, 1000], [0, 1000]]]
    east = [[[300, 0], [1000, 0], [1000, 1000], [300, 1000]]]
    sp.executemany("INSERT INTO vc_split_squares VALUES (?, ?, ?, ?)", [
        ("SP5820", 23, 0.3, json.dumps(west)), ("SP5820", 24, 0.7, json.dumps(east)),
        ("SP5720", 23, 0.5, None)])
    sp.commit(); sp.close()
    return VCLookupService(str(tmp_path / "vc_lookup.db"))


def test_points_take_the_vc_they_are_in(toy):
    assert toy.assess("SP58102050")["vc_number"] == 23                  # 10 m ref, west part
    assert toy.assess("SP58802050")["vc_number"] == 24
    a = toy.assess("SP582205")                                          # 100 m square across x=300
    assert a["boundary"] and {v for v, _ in a["vcs"]} == {23, 24}
    assert not toy.assess("SP585205")["boundary"]                       # 100 m square wholly east


def test_1km_square_on_a_boundary_gives_shares(toy):
    a = toy.assess("SP5820")
    assert a["boundary"] and a["vc_number"] == 24 and a["vcs"] == [(24, 70), (23, 30)]
    assert "VC24 70%" in a["note"]
    assert toy.get_vc_from_grid_ref("SP5820")[0] == 24


def test_coastal_square_missing_from_vc_lookup_now_has_a_vc(toy):
    a = toy.assess("SP5720")
    assert a["vc_number"] == 23 and not a["boundary"]


def test_batch_carries_the_boundary(toy):
    res = toy.get_vc_batch(["SP5820", "SP5920"])
    assert res["SP5820"]["boundary"] and "boundary" in res["SP5820"]["warning"]
    assert not res["SP5920"]["boundary"] and res["SP5920"]["vc_number"] == 24


real = pytest.mark.skipif(not (paths.DATA_DIR / "vc_splits.db").exists(),
                          reason="data/vc_splits.db not built")


@real
@pytest.mark.parametrize("ref, vc, boundary", [
    ("SO539092", 34, False),        # Highbury Wood: square SO5309 is listed as VC35 (F29)
    ("SO539069", 34, False),
    ("SO5309", 35, True),           # 54% VC35, 46% VC34
    ("SO50", 34, True),             # 10 km: not just its south-west square
    ("TQ530773", 16, False),
    ("NS9982", 84, False),          # centre in the sea: no vc_lookup row
])
def test_real_boundaries(ref, vc, boundary):
    a = VCLookupService(str(paths.VC_LOOKUP_DB)).assess(ref)
    assert (a["vc_number"], a["boundary"]) == (vc, boundary)
