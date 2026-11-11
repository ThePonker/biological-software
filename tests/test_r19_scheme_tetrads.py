"""R19: the Recording Scheme statistics name tetrads as DINTY, like Mapping and the Observation
statistics; the counts of distinct tetrads do not change (the old letters were a reordering within
each 10 km square)."""
import random

from src.services.observation_stats_service import extract_grid_squares
from src.services.recording_scheme_stats_service import RecordingSchemeStatsService


def _old_tetrad(gr):
    """The scheme statistics' letters before R19 (rows first), for the count check."""
    s = gr.upper().replace(" ", "")
    letters = "".join(c for c in s[:2] if c.isalpha())
    digits = s[len(letters):]
    e, n = int(digits[1]), int(digits[len(digits) // 2 + 1])
    ch = chr(ord("A") + (n // 2) * 5 + (e // 2))
    if ch > "O":
        ch = chr(ord(ch) + 1)
    return f"{letters}{digits[0]}{digits[len(digits) // 2]}{ch}"


def test_sp5820_is_sp52v_in_both_statistics():
    assert extract_grid_squares("SP5820")["tetrad"] == "SP52V"
    assert RecordingSchemeStatsService._extract_grid_squares(None, "SP 58 20")["tetrad"] == "SP52V"


def test_distinct_tetrad_counts_are_unchanged():
    rng = random.Random(19)
    for _ in range(50):
        refs = [f"{rng.choice(['SP', 'SU', 'TQ', 'NY'])}{rng.randrange(10000):04d}" for _ in range(rng.randrange(1, 400))]
        new = {RecordingSchemeStatsService._extract_grid_squares(None, r)["tetrad"] for r in refs}
        old = {_old_tetrad(r) for r in refs}
        assert len(new) == len(old)


def test_hectad_and_monad_unchanged():
    sq = RecordingSchemeStatsService._extract_grid_squares(None, "TL 03812 26834")
    assert (sq["hectad"], sq["monad"]) == ("TL02", "TL0326")
