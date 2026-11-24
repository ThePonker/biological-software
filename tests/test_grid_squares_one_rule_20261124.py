"""The stats dashboards and the Mapping tab read grid squares by one rule (24 Nov 2026).

extract_grid_squares (Observation / Recording Scheme statistics) goes through the map's
shared/maps/grid_squares.square_for_ref, so a square counted on a dashboard is the square drawn
on the map. Purpose-made references only.
"""
import pytest

from shared.maps import grid_squares as gs
from src.services.observation_stats_service import extract_grid_squares
from src.services.vc_lookup_service import VCLookupService

REFS = ["SP58A", "sp58a", "SP5182", "SP518823", "sp 518 823", "SP51828232", "SP5182082320",
        "TL1", "TL12", "TL 12 34", "SP518", "SP51882", "SP", "S", "XX1234", "SP58O", "SP58Z",
        "", None, "   ", "SP58A0", "1234", "SP 51 82 A"]


def _map_squares(ref):
    out = {}
    for name, size in gs.GRID_SIZES.items():
        label = gs.square_for_ref(ref, size)
        if label:
            out[name] = label
    return out


@pytest.mark.parametrize("ref", REFS)
def test_stats_and_map_agree(ref):
    assert extract_grid_squares(ref) == _map_squares(ref)


def test_letter_form_tetrad_is_counted_as_a_tetrad():
    assert extract_grid_squares("SP58A") == {"hectad": "SP58", "tetrad": "SP58A"}
    assert extract_grid_squares("sp58a") == {"hectad": "SP58", "tetrad": "SP58A"}


def test_four_figure_gives_all_three_squares():
    sq = extract_grid_squares("SP5182")
    assert sq == {"hectad": "SP58", "tetrad": "SP58B", "monad": "SP5182"}


@pytest.mark.parametrize("ref", ["SP518823", "sp 518 823", "SP 518823"])
def test_six_figure_with_spaces_and_case(ref):
    assert extract_grid_squares(ref) == {"hectad": "SP58", "tetrad": "SP58B", "monad": "SP5182"}


def test_ten_figure_ref():
    assert extract_grid_squares("SP5182082320")["monad"] == "SP5182"


def test_hectad_only_has_no_finer_squares():
    assert extract_grid_squares("TL1") == {}                 # odd digits: not a reference
    assert extract_grid_squares("TL12") == {"hectad": "TL12"}


@pytest.mark.parametrize("ref", ["SP518", "SP51882", "XX1234", "SP58O", "1234", "SP", ""])
def test_odd_or_invalid_gives_nothing(ref):
    assert extract_grid_squares(ref) == {}


@pytest.mark.parametrize("ref", [None, "", "   "])
def test_empty_and_none(ref):
    assert extract_grid_squares(ref) == {}


def test_vc_lookup_uses_the_shared_letter_rule():
    assert not hasattr(VCLookupService, "GRID_LETTERS")
    assert VCLookupService.parse_grid_ref("SP580207") == (458000, 220700, 100)
    assert VCLookupService.parse_grid_ref("HU4039") == (440000, 1139000, 1000)
    assert VCLookupService.parse_grid_ref("XX5820") is None
    assert VCLookupService.get_1km_square("SP580207") == "SP5820"
    assert VCLookupService.get_1km_square("SV9010") == "SV9010"


@pytest.mark.parametrize("ref, want", [
    ("C445129", {"hectad": "C41", "tetrad": "C41L", "monad": "C4412"}),   # Irish Grid
    ("WV6050", {"hectad": "WV65", "tetrad": "WV65A", "monad": "WV6050"}),  # Channel Islands
    ("J3040", {"hectad": "J34", "tetrad": "J34A", "monad": "J3040"}),
])
def test_irish_and_channel_islands_squares_still_counted(ref, want):
    """Off the GB grid, so the map leaves them out; the scheme statistics go on counting them."""
    assert extract_grid_squares(ref) == want


def test_off_grid_fallback_does_not_read_gb_letters_or_odd_digits():
    assert extract_grid_squares("XX1234") == {}
    assert extract_grid_squares("C4451") == {"hectad": "C45", "tetrad": "C45K", "monad": "C4451"}
    assert extract_grid_squares("C44512") == {}      # odd digit count
    assert extract_grid_squares("C44") == {}         # too short, as before
    assert extract_grid_squares(5820) == {}
