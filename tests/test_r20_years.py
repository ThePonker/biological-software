"""R20 (Wil, 11 Nov 2026): years that were written into the code now follow the calendar.
Quick Select's last five years, the decade bands, Munia's year boxes, two-digit photo years."""
import datetime as dt


def test_quick_select_last_five_years_is_five():
    from src.views.mapping.filter_panel import quick_presets
    for y in (2026, 2027, 2031):
        label, lo, hi = quick_presets(dt.date(y, 3, 1))[3]
        assert int(hi) - int(lo) + 1 == 5 and hi == str(y)
        assert label == f"{y - 4}–{str(y)[2:]}"


def test_decade_bands_extend_themselves():
    from shared.maps.map_stats import decade_bands
    assert [b[0] for b in decade_bands(2026)] == ["pre-1950", "1950–79", "1980–99", "2000–09",
                                                    "2010–19", "2020–"]
    b30 = decade_bands(2030)
    assert b30[-2:] == (("2020–29", 2020, 2029), ("2030–", 2030, None))
    # the bands still cover every year once: no gaps, no overlaps
    for year in (1800, 1949, 1950, 1999, 2000, 2029, 2030, 2045):
        hits = [lab for lab, lo, hi in decade_bands(2047)
                if (lo is None or year >= lo) and (hi is None or year <= hi)]
        assert len(hits) == 1, (year, hits)


def test_munia_year_range_follows_this_year():
    from Munia.munia_data import year_range
    lo, hi = year_range()
    this = dt.date.today().year
    assert lo <= 2020 and lo <= this - 10 and hi == this + 10


def test_two_digit_years_one_rule():
    from shared.import_core import full_year
    today = dt.date(2026, 11, 11)
    assert full_year(98, today) == 1998 and full_year(21, today) == 2021
    assert full_year(26, today) == 2026 and full_year(27, today) == 1927
