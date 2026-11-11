"""R18 B6: a corpus of grid references and points, and every grid-reference converter in the suite
run over it, so a change to where the arithmetic lives can be proved to change no answer.

    py -3.14 tests\\osgb_corpus.py --write     record tests/golden/osgb_converters_r18.json (from the CURRENT code)

tests/test_r18_osgb_converters.py compares the converters' answers with that recording. Read-only."""
from __future__ import annotations

import json
import math
import os
import sys
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (ROOT, os.path.join(ROOT, "Observatum")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

GOLDEN = os.path.join(ROOT, "tests", "golden", "osgb_converters_r18.json")


# ---------------------------------------------------------------- the corpus
def ref_corpus():
    refs = [
        # 2-, 4-, 6-, 8-, 10-figure
        "SP58", "SP5820", "SP580207", "SP58052075", "SP5805020750", "TQ 53083 77347", "SU1234", "NT2573",
        "TL4458", "HU4141", "HP6000", "NZ2563", "SH6054", "SV0000", "TV5000", "TA0000", "OV0000",
        "NA0000", "NF7500", "HW6000", "SX9090", "ND2000", "NC9000", "TM5499", "TG5014", "SD3333",
        # spaces, lower case, mixed
        "SP 58 20", "SP 580 207", "sp580207", "Sp5820", " SP5820 ", "SP  5820", "sp 58", "tq5307",
        # tetrads (DINTY) on both sides of the letter changes
        "SP42N", "sp42n", "SP58A", "SP58B", "SP58E", "SP58F", "SP58J", "SP58K", "SP58L", "SP58P",
        "SP58Q", "SP58Y", "SP58Z", "SP42O", "TQ37Y", "SP 42 N", "SP00A", "SP99Z", "SV00A", "HU44K",
        # 1 km and 100 km edges
        "SP00", "SP99", "SP0000", "SP9999", "SP000000", "SP999999", "SP0099", "SP9900", "SP5000",
        "SP0050", "SP", "sp", "TQ", "SV", "HP", "OV", "TV", "TA", "TW", "HV", "NQ", "SA", "SB", "TB",
        "SP4999", "SP5099", "SP50", "SP49",
        # invalid
        "", None, " ", "XX1234", "SP5", "SP512", "SP58020", "S1234", "12345", "SPABCD", "SP58AA",
        "SI0000", "ZZ99", "SP 5 8", "SP12345678901", "SP-5820", "SP58.20", "SP5820X", "SP58 2O",
        "H1234", "O5050", "SPSP", "5820", "SP58O", "SP58I", "S", 5820, 580207,
    ]
    # every pair of letters at 4 figures (valid squares and not), 100 km origins either side
    import string
    for a in string.ascii_uppercase:
        for b in string.ascii_uppercase:
            refs.append(f"{a}{b}0000")
            refs.append(f"{a}{b}99")
            refs.append(f"{a}{b}5050")
    return refs


def point_corpus():
    pts = [(0, 0), (1, 1), (99999.9, 99999.9), (100000, 0), (0, 100000), (99999, 99999), (400000, 200000),
           (458050, 220750), (458000, 220700), (458999.9, 220999.9), (459000, 221000), (458000, 220000),
           (653000, 1209000), (13000, 5000), (699999, 1299999), (699999.9, 1299999.9), (700000, 0),
           (0, 1300000), (700000, 1300000), (-1, 0), (0, -1), (-100000, 5), (3500, 1250000),
           (530830, 177340), (539000, 209000), (310000, 1198000), (50000, 50000), (600000, 0),
           (500000, 100000), (399999.5, 199999.5), (400000.5, 200000.5), (123456, 654321),
           (451234.5, 227890.25), (610000, 1)]
    for e in range(0, 700000, 100000):
        for n in range(0, 1300000, 100000):
            pts.append((e + 50000, n + 50000))
            pts.append((e, n))
    return pts


def latlon_corpus():
    return [(51.7520, -1.2577), (51.5, -0.1), (50.0, -5.7), (58.6, -3.0), (60.8, -0.8), (54.0, -2.0),
            (53.4, -6.2), (54.6, -5.9), (55.0, -6.5), (55.0, -5.5), (51.3, -6.0), (48.0, 2.0),
            (0.0, 0.0), (None, 1.0), (1.0, None), (49.9, -6.4), (55.45, -5.45), (52.0, 1.75), (57.0, -7.5)]


# ---------------------------------------------------------------- the converters
def _scripts():
    """The two scripts' converters, imported with their heavy GIS imports stubbed."""
    # geopandas too: where it is installed (Wil's PC) it would import for real and read the stubbed
    # shapely's __version__, which fails (11 Nov 2026). patch.dict restores sys.modules afterwards.
    stubs = {n: mock.MagicMock() for n in ("shapefile", "shapely", "shapely.geometry", "geopandas")}
    with mock.patch.dict(sys.modules, stubs):
        import importlib
        vc_db = importlib.import_module("scripts.create_vc_lookup_db")
        splits = importlib.import_module("scripts.build_vc_splits")
    return vc_db, splits


def converters():
    """{name: (kind, callable)}; kind is "ref", "en" or "ll" (what the callable takes)."""
    from shared import osgb, photo_intake
    from shared.maps import grid_squares as gs
    from shared.maps import raster_map
    from src.services.observation_stats_service import ObservationStatsService
    from src.services.recording_scheme_stats_service import RecordingSchemeStatsService
    from src.services.vc_lookup_service import VCLookupService
    vc_db, splits = _scripts()
    c = {
        "osgb.gridref_to_en": ("ref", osgb.gridref_to_en),
        "osgb.gridref_centre": ("ref", osgb.gridref_centre),
        "osgb.gridref_to_wgs84": ("ref", osgb.gridref_to_wgs84),
        "grid_squares.square_for_ref/10000": ("ref", lambda r: gs.square_for_ref(r, 10000)),
        "grid_squares.square_for_ref/2000": ("ref", lambda r: gs.square_for_ref(r, 2000)),
        "grid_squares.square_for_ref/1000": ("ref", lambda r: gs.square_for_ref(r, 1000)),
        "grid_squares.is_tetrad_ref": ("ref", gs.is_tetrad_ref),
        "grid_squares.square_bounds": ("ref", gs.square_bounds),
        "grid_squares.square_polygon": ("ref", gs.square_polygon),
        "VCLookupService.parse_grid_ref": ("ref", VCLookupService.parse_grid_ref),
        "VCLookupService.get_1km_square": ("ref", VCLookupService.get_1km_square),
        "ObservationStatsService._extract_grid_squares":
            ("ref", lambda r: ObservationStatsService._extract_grid_squares(None, r)),
        "RecordingSchemeStatsService._extract_grid_squares":
            ("ref", lambda r: RecordingSchemeStatsService._extract_grid_squares(None, r)),
        "osgb.osgb_en_to_wgs84": ("en", osgb.osgb_en_to_wgs84),
        "raster_map.en_to_100km_code": ("en", raster_map.en_to_100km_code),
        "create_vc_lookup_db.easting_northing_to_gridref":
            ("en", lambda e, n: vc_db.easting_northing_to_gridref(int(e), int(n))),
        "build_vc_splits.gridref_1km": ("en", splits.gridref_1km),
        "osgb.wgs84_to_osgb_en": ("ll", osgb.wgs84_to_osgb_en),
        "photo_intake.grid_ref": ("ll", photo_intake.grid_ref),
    }
    for d in (0, 2, 4, 6, 8, 10):
        c[f"osgb.en_to_gridref/{d}"] = ("en", lambda e, n, d=d: osgb.en_to_gridref(e, n, d))
    for s in (10000, 2000, 1000):
        c[f"grid_squares.square_for_point/{s}"] = ("en", lambda e, n, s=s: gs.square_for_point(e, n, s))
    return c


def _show(v):
    if isinstance(v, float):
        return "nan" if math.isnan(v) else repr(v)
    if isinstance(v, (tuple, list)):
        return "(" + ", ".join(_show(x) for x in v) + ")"
    if isinstance(v, dict):
        return "{" + ", ".join(f"{k!r}: {_show(x)}" for k, x in v.items()) + "}"
    return repr(v)


def _run(fn, *args):
    try:
        return _show(fn(*args))
    except Exception as e:                      # an exception IS an answer to compare
        return f"EXC {type(e).__name__}"


def record() -> dict:
    out = {}
    for name, (kind, fn) in converters().items():
        if kind == "ref":
            rows = [(repr(r), _run(fn, r)) for r in ref_corpus()]
        elif kind == "en":
            rows = [(repr(p), _run(fn, *p)) for p in point_corpus()]
        else:
            rows = [(repr(p), _run(fn, *p)) for p in latlon_corpus()]
        out[name] = dict(rows)
    return out


if __name__ == "__main__":
    if "--write" in sys.argv:
        data = record()
        with open(GOLDEN, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=0, sort_keys=True)
        print(f"wrote {GOLDEN}: {sum(len(v) for v in data.values())} answers from {len(data)} converters")
    else:
        print("use --write")
