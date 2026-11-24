"""R18 B6 (backlog INF9): every grid-reference converter in the suite over a corpus of references
and points (tests/osgb_corpus.py), compared with what each answered BEFORE the copies were made to
import shared/osgb.py (tests/golden/osgb_converters_r18.json). A wrapper must return exactly what
its old version returned.

Converters left as they were because two old copies disagree on a valid input (reported, not
silently picked) are in the same recording: they must go on answering as before too.
"""
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import osgb_corpus as oc  # noqa: E402

with open(oc.GOLDEN, encoding="utf-8") as _f:
    GOLD = json.load(_f)
CONVERTERS = oc.converters()


def test_the_recording_covers_every_converter():
    assert set(GOLD) == set(CONVERTERS)
    assert sum(len(v) for v in GOLD.values()) > 20000
    kinds = {n: k for n, (k, _f) in CONVERTERS.items()}
    assert set(kinds.values()) == {"ref", "en", "ll"}


# Converters whose wrapper answers differently ONLY for a point off the National Grid (invalid input;
# reported in the R18 B6 notes): the old private copies indexed letters with negative or too-large
# numbers and returned a made-up square; shared/osgb.py answers None.
INVALID_ONLY = {"raster_map.en_to_100km_code", "build_vc_splits.gridref_1km"}


def _same(old, new):
    """Equal, or the same numbers to within floating-point rounding. Windows and Linux maths
    libraries can differ in the last digit of a trig result (seen 11 Nov 2026: 1e-15 degrees,
    1e-10 m), which is not a change in behaviour."""
    if old == new:
        return True
    try:
        a, b = eval(old), eval(new)       # the recorded answers are repr()s of numbers / tuples
    except Exception:
        return False
    a = a if isinstance(a, tuple) else (a,)
    b = b if isinstance(b, tuple) else (b,)
    return (len(a) == len(b) and all(isinstance(x, float) and isinstance(y, float) for x, y in zip(a, b))
            and all(abs(x - y) <= 1e-9 * max(1.0, abs(x)) for x, y in zip(a, b)))


def _off_grid(key):
    e, n = eval(key)                      # the corpus keys are repr()s of (e, n)
    return not (0 <= e < 700000 and 0 <= n < 1300000)


# R19 (Wil, 11 Nov 2026): the Recording Scheme statistics now use the Observation statistics' squares,
# so their tetrad letters change from the old rows-first order to DINTY (SP5820: SP52E -> SP52V).
# Their answers must now equal the Observation statistics' recorded answers exactly.
NOW_MATCHES = {"RecordingSchemeStatsService._extract_grid_squares": "ObservationStatsService._extract_grid_squares"}

# Round 3 (Wil, 24 Nov 2026): one grid-square rule. The statistics' squares are now exactly the map's
# squares (shared/maps/grid_squares.square_for_ref at 10 km / 2 km / 1 km, as recorded): letter tetrads
# such as SP42N now count as tetrads, and refs the map rejects give no squares.
MAP_SQUARES = {"ObservationStatsService._extract_grid_squares", "RecordingSchemeStatsService._extract_grid_squares"}
_MAP_SIZES = (("hectad", "10000"), ("tetrad", "2000"), ("monad", "1000"))
# ...and the VC lookup reads letters with shared/osgb.py, which knows every 100 km square (the old private
# table had 66 of the 91): a ref it used to refuse now gives what shared/osgb.py gives; nothing else moves.
NOW_READ_BY_OSGB = {"VCLookupService.parse_grid_ref": "osgb.gridref_to_en",
                    "VCLookupService.get_1km_square": "osgb.gridref_to_en"}


def _off_gb(key):
    import re
    ref = eval(key)
    return isinstance(ref, str) and bool(
        re.match(r"^(?:[A-HJ-Z]|W[AV])(\d{2}|\d{4}|\d{6}|\d{8}|\d{10})$", ref.upper().replace(" ", "")))


def _map_squares(key):
    out = {}
    for name, size in _MAP_SIZES:
        v = eval(GOLD[f"grid_squares.square_for_ref/{size}"][key])
        if v:
            out[name] = v
    return repr(out)


@pytest.mark.parametrize("name", sorted(GOLD))
def test_converter_answers_are_unchanged(name):
    kind, fn = CONVERTERS[name]
    if kind == "ref":
        now = {repr(r): oc._run(fn, r) for r in oc.ref_corpus()}
    elif kind == "en":
        now = {repr(p): oc._run(fn, *p) for p in oc.point_corpus()}
    else:
        now = {repr(p): oc._run(fn, *p) for p in oc.latlon_corpus()}
    differ = {k: (GOLD[name][k], now[k]) for k in GOLD[name] if not _same(GOLD[name][k], now.get(k))}
    if name in MAP_SQUARES:
        off = {k for k in GOLD[name] if now[k] != _map_squares(k)}
        # The only refs allowed to differ from the map: Irish Grid / Channel Islands, which the map
        # cannot draw and the statistics count exactly as before.
        assert all(_off_gb(k) and _map_squares(k) == "{}" for k in off), sorted(off)[:10]
        if name == "ObservationStatsService._extract_grid_squares":
            assert all(now[k] == GOLD[name][k] for k in off), sorted(off)[:10]
        return
    if name in NOW_READ_BY_OSGB:
        canon = GOLD[NOW_READ_BY_OSGB[name]]
        assert all(old == "None" and canon[k] != "None" for k, (old, _new) in differ.items()), differ
        if name == "VCLookupService.parse_grid_ref":
            assert all(new == canon[k] for k, (_old, new) in differ.items()), differ
        else:                             # the 1 km square holding the reference's south-west corner
            from shared.osgb import en_to_gridref
            for k, (_old, new) in differ.items():
                e, n, _p = eval(canon[k])
                assert new == repr(en_to_gridref(e // 1000 * 1000, n // 1000 * 1000, 4)), (k, new)
        return
    if name in NOW_MATCHES:
        ref = GOLD[NOW_MATCHES[name]]
        assert {k: now[k] for k in ref} == ref
        return
    if name in INVALID_ONLY:
        assert all(_off_grid(k) and v[1] == "None" for k, v in differ.items()), differ
        return
    assert not differ, f"{name}: {len(differ)} answers changed, e.g. {list(differ.items())[:5]}"


def test_corpus_has_the_cases_asked_for():
    refs = [r for r in oc.ref_corpus() if isinstance(r, str)]
    for want in ("SP58", "SP5820", "SP580207", "SP58052075", "SP5805020750", "SP 58 20", "sp580207",
                 "SP42N", "sp42n", "SP00", "SP99", "SP0000", "SP9999", "SP", "XX1234", ""):
        assert want in refs
