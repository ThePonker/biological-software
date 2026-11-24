"""Rounding for published indices (SQI and the like): exact, and halves round UP.

Python's round() sends a half to the even number (182.5 -> 182) and works on binary floats
(73 / 40 * 100 is 182.49999999999997), so an SQI that is exactly .5 could round down. Indices
are ratios of whole numbers, so they are rounded here from the fraction itself: 73 / 40 x 100
= 182.5 -> 183 (Wil, 24 Nov 2026).
"""


def ratio_half_up(numerator: int, denominator: int, scale: int = 100, ndigits: int = 0):
    """numerator / denominator x scale, rounded half up to `ndigits` places (non-negative values).

    ndigits 0 gives an int; otherwise a float with that many decimal places."""
    if not denominator:
        raise ZeroDivisionError("ratio_half_up: denominator is 0")
    step = 10 ** ndigits
    q = (2 * numerator * scale * step + denominator) // (2 * denominator)
    return q if ndigits == 0 else q / step
