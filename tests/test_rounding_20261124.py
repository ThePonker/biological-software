"""24 Nov 2026: SQI rounds halves up from the exact ratio (shared/rounding.py)."""
import pytest

from shared.rounding import ratio_half_up


def test_exact_half_rounds_up_where_round_went_to_even():
    assert round(73 / 40 * 100) == 182          # the old behaviour (Elmley 2026)
    assert ratio_half_up(73, 40) == 183
    assert ratio_half_up(22, 16) == 138 and ratio_half_up(22, 16) != 137   # 137.5
    assert ratio_half_up(11, 8) == 138            # 137.5


def test_ordinary_values_unchanged():
    for num, den in [(144, 123), (1, 3), (2, 3), (500, 7), (0, 5), (123, 123)]:
        assert ratio_half_up(num, den) == int(num * 100 / den + 0.5)


def test_one_decimal_place():
    assert ratio_half_up(4847, 1000, ndigits=1) == 484.7
    assert ratio_half_up(9695, 20, scale=1, ndigits=1) == 484.8   # 484.75 -> 484.8


def test_zero_denominator_raises():
    with pytest.raises(ZeroDivisionError):
        ratio_half_up(1, 0)


def test_sqi_result_uses_it():
    from shared.services.pantheon_analysis_service import SQIResult
    s = SQIResult(label="x", species_with_sqs=40, sqs_sum=73, species_analysed=40)
    s.calculate()
    assert s.sqi == 183
