"""The import wizards' species lookup gives the answers recorded in the golden file.

tests/golden/species_lookup_golden.json holds, for 559 name strings against the real uksi.db,
what the observation, specimen and scheme validation workers (six import modes) produce: the
species columns after the lookup, and each finished row's species fields, status and messages.
First recorded from the three original lookups (C4, 9 Oct 2026); re-recorded for the one rule
set the same evening (fix round 13-15). Needs data/uksi.db (git-ignored; skipped without it),
read-only.
Takes ~25 s.

A deliberate change to matching, or a new uksi.db: regenerate the golden file with
    py -3.14 tests\\species_lookup_harness.py --write
and say in the commit what moved.
"""
import os

import pytest

import species_lookup_harness as h

pytestmark = pytest.mark.skipif(not os.path.exists(h.UKSI_DB), reason="needs data/uksi.db")


@pytest.fixture(scope="module")
def golden():
    with open(h.GOLDEN, encoding="utf-8") as f:
        return h.loads(f.read())


@pytest.fixture(scope="module")
def now(golden):
    pytest.importorskip("pandas")
    pytest.importorskip("PySide6")
    if h.uksi_fingerprint() != golden["uksi"]:
        pytest.skip("uksi.db is not the one the golden file was recorded on -- regenerate it "
                    "(tests/species_lookup_harness.py --write)")
    return h.capture_all(names=golden["names"])


# A missing value reaches the table as NaN, None or "" depending on the pandas version
# (recorded here on pandas 3.0, which turns a None written into a text column into NaN;
# 9 Oct, Wil's PC gave None / "" for 'Bombus lucorum AGG.'). All three mean "no value".
_MISSING = ("<NaN>", None, "")


def _norm(row):
    return {k: (None if v in _MISSING else v) for k, v in row.items()}


WORKERS = ["specimen", "observation_personal", "observation_irecord",
           "scheme_generic", "scheme_irecord", "scheme_nbn"]


@pytest.mark.parametrize("worker", WORKERS)
@pytest.mark.parametrize("part", ["frame", "rows"])
def test_same_as_recorded(golden, now, worker, part):
    was, got = golden[worker][part], now[worker][part]
    assert len(got) == len(was)
    diffs = []
    for name, a, b in zip(golden["names"], was, got):
        a, b = _norm(a), _norm(b)
        if a != b:
            keys = sorted(k for k in set(a) | set(b) if a.get(k, "<absent>") != b.get(k, "<absent>"))
            diffs.append(f"{name!r}: " + "; ".join(f"{k}: {a.get(k, '<absent>')!r} -> "
                                                   f"{b.get(k, '<absent>')!r}" for k in keys))
    assert not diffs, f"{len(diffs)} names differ, e.g.\n" + "\n".join(diffs[:15])
