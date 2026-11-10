"""R17 A7c: the soil parent-material GB level is simplified, not a copy of the county level.
A tiny made-up staircase of 1 km cells; nothing is built from real data and no file is written."""
import pytest

shapely = pytest.importorskip("shapely")

from scripts.build_map_layers import to_features  # noqa: E402
from scripts.env_sources import LAYER_SPECS, SPEC_BY_KEY  # noqa: E402


def _staircase(steps=30, cell=1000.0):
    """One polygon: the union of 1 km cells along a diagonal (a staircase edge on both sides)."""
    cells = [shapely.box(i * cell, i * cell, (i + 1) * cell, (i + 1) * cell) for i in range(steps)]
    cells += [shapely.box((i + 1) * cell, i * cell, (i + 2) * cell, (i + 1) * cell) for i in range(steps)]
    return shapely.unary_union(cells)


def _points(feats):
    return sum(len(r) for f in feats for r in f["rings"])


def test_soil_pm_has_its_own_gb_simplification():
    spec = SPEC_BY_KEY["soil_pm"]
    default_gb = next(s for s in LAYER_SPECS if s.key == "sssi").gb         # the other layers' GB rule
    assert spec.gb is not None and spec.gb[0] > default_gb[0] and spec.gb[0] > spec.county[0]
    assert spec.dissolve


def test_gb_level_is_smaller_than_the_county_level_for_a_1km_staircase():
    spec = SPEC_BY_KEY["soil_pm"]
    geom = _staircase()
    gb = to_features(geom, "polygon", *spec.gb)
    county = to_features(geom, "polygon", *spec.county)
    assert gb and county
    assert _points(gb) < _points(county) / 2           # the steps are smoothed at GB scale
    assert gb != county


def test_a_single_cell_survives_at_gb_level():
    spec = SPEC_BY_KEY["soil_pm"]
    one = shapely.box(500000, 200000, 501000, 201000)
    assert len(to_features(one, "polygon", *spec.gb)) == 1
