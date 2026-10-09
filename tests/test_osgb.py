"""shared/osgb -- grid references, OSGB36 and WGS84 (I3c, 9 Oct 2026)."""
import csv
import os

import pytest

from shared import osgb

HERE = os.path.dirname(os.path.abspath(__file__))


def points():
    with open(os.path.join(HERE, "data", "os_test_points.csv")) as f:
        return [r for r in csv.DictReader(line for line in f if not line.startswith("#"))]


def test_os_test_points_within_5m_both_ways():
    errs, back = [], []
    for p in points():
        e, n, lat, lon = (float(p[k]) for k in ("easting", "northing", "lat", "lon"))
        la, lo = osgb.osgb_en_to_wgs84(e, n)
        errs.append(osgb.distance_m(lat, lon, la, lo))
        e2, n2 = osgb.wgs84_to_osgb_en(lat, lon)
        back.append(((e2 - e) ** 2 + (n2 - n) ** 2) ** 0.5)
    assert len(errs) == 40
    assert max(errs) < 5.0 and sorted(errs)[20] < 2.5
    assert max(back) < 5.0


def test_round_trip_is_exact():
    for e, n in ((458050, 220750), (91492, 11318), (467000, 1170000)):
        la, lo = osgb.osgb_en_to_wgs84(e, n)
        e2, n2 = osgb.wgs84_to_osgb_en(la, lo)
        assert abs(e2 - e) < 0.01 and abs(n2 - n) < 0.01


@pytest.mark.parametrize("ref, out", [
    ("SP580207", (458000, 220700, 100)), ("SP5820", (458000, 220000, 1000)),
    ("SP58", (450000, 280000, 10000)), ("TQ 53083 77347", (553083, 177347, 1)),
    ("SV9111", (91000, 11000, 1000)), ("HP61", (460000, 1210000, 10000)),
    ("NT2773", (327000, 673000, 1000)), ("SP", (400000, 200000, 100000))])
def test_gridref_to_en(ref, out):
    assert osgb.gridref_to_en(ref) == out


@pytest.mark.parametrize("ref", ["", None, "SI1234", "SP123", "XX1234", "SP58X", "12SP"])
def test_gridref_rejects(ref):
    assert osgb.gridref_to_en(ref) is None


def test_centre_not_corner():
    assert osgb.gridref_centre("SP580207") == (458050.0, 220750.0)
    c, sw = osgb.gridref_to_wgs84("SP580207"), osgb.gridref_to_wgs84("SP580207", at="corner")
    assert 65 < osgb.distance_m(*c, *sw) < 75                      # half the diagonal of 100 m


@pytest.mark.parametrize("e, n, d, ref", [(458050, 220750, 6, "SP580207"), (553083, 177347, 10, "TQ5308377347"),
                                          (327500, 673500, 4, "NT2773"), (91492, 11318, 2, "SV91")])
def test_en_to_gridref(e, n, d, ref):
    assert osgb.en_to_gridref(e, n, d) == ref
