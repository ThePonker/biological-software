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
    if name in INVALID_ONLY:
        assert all(_off_grid(k) and v[1] == "None" for k, v in differ.items()), differ
        return
    assert not differ, f"{name}: {len(differ)} answers changed, e.g. {list(differ.items())[:5]}"


def test_corpus_has_the_cases_asked_for():
    refs = [r for r in oc.ref_corpus() if isinstance(r, str)]
    for want in ("SP58", "SP5820", "SP580207", "SP58052075", "SP5805020750", "SP 58 20", "sp580207",
                 "SP42N", "sp42n", "SP00", "SP99", "SP0000", "SP9999", "SP", "XX1234", ""):
        assert want in refs
