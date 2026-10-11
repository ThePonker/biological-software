"""project_many -- WGS84 (lat, lon) points to OSGB36 easting/northing, many at once.

The same sums as shared/osgb.wgs84_to_osgb_en (Helmert WGS84 -> OSGB36, then the National
Grid transverse Mercator), done on numpy arrays. Projecting the vice-county outlines one
point at a time took about 10 s of the Mapping tab's 13 s first opening (241,436 points,
review R4, 11 Oct 2026). Results agree with the one-point function to well under a
millimetre (tests/test_review_r4.py). Without numpy it falls back to the one-point function.
"""
from __future__ import annotations

import math
from typing import List, Sequence, Tuple

from shared.osgb import (_AIRY, _E0, _F0, _LAT0, _LON0, _N0, _TO_WGS84, _WGS84,
                         wgs84_to_osgb_en)

try:
    import numpy as _np
except Exception:          # numpy missing: the one-point function does the work
    _np = None


def project_many(points: Sequence[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """[(lat, lon) in degrees] -> [(easting, northing)], as wgs84_to_osgb_en on each."""
    if _np is None or len(points) < 16:
        return [wgs84_to_osgb_en(lat, lon) for lat, lon in points]
    np = _np
    arr = np.asarray(points, dtype=float)
    lat = np.radians(arr[:, 0])
    lon = np.radians(arr[:, 1])

    # Helmert WGS84 -> OSGB36 (osgb._helmert with sign=-1)
    tx, ty, tz, s, rx, ry, rz = (-p for p in _TO_WGS84)
    a, b = _WGS84
    e2 = 1 - b * b / (a * a)
    nu = a / np.sqrt(1 - e2 * np.sin(lat) ** 2)
    x = nu * np.cos(lat) * np.cos(lon)
    y = nu * np.cos(lat) * np.sin(lon)
    z = (1 - e2) * nu * np.sin(lat)
    s *= 1e-6
    rx, ry, rz = (math.radians(r / 3600) for r in (rx, ry, rz))
    x2 = tx + (1 + s) * x - rz * y + ry * z
    y2 = ty + rz * x + (1 + s) * y - rx * z
    z2 = tz - ry * x + rx * y + (1 + s) * z
    a, b = _AIRY
    e2 = 1 - b * b / (a * a)
    p = np.hypot(x2, y2)
    la = np.arctan2(z2, p * (1 - e2))
    for _ in range(10):
        nu = a / np.sqrt(1 - e2 * np.sin(la) ** 2)
        la = np.arctan2(z2 + e2 * nu * np.sin(la), p)
    lo = np.arctan2(y2, x2)

    # National Grid (osgb._latlon_airy_to_en)
    n = (a - b) / (a + b)
    sn, c, t = np.sin(la), np.cos(la), np.tan(la)
    nu = a * _F0 / np.sqrt(1 - e2 * sn * sn)
    rho = a * _F0 * (1 - e2) / (1 - e2 * sn * sn) ** 1.5
    eta2 = nu / rho - 1
    m = b * _F0 * ((1 + n + 1.25 * n ** 2 + 1.25 * n ** 3) * (la - _LAT0)
                   - (3 * n + 3 * n ** 2 + 2.625 * n ** 3) * np.sin(la - _LAT0) * np.cos(la + _LAT0)
                   + (1.875 * n ** 2 + 1.875 * n ** 3) * np.sin(2 * (la - _LAT0)) * np.cos(2 * (la + _LAT0))
                   - (35 / 24) * n ** 3 * np.sin(3 * (la - _LAT0)) * np.cos(3 * (la + _LAT0)))
    i = m + _N0
    ii = nu / 2 * sn * c
    iii = nu / 24 * sn * c ** 3 * (5 - t * t + 9 * eta2)
    iiia = nu / 720 * sn * c ** 5 * (61 - 58 * t * t + t ** 4)
    iv = nu * c
    v = nu / 6 * c ** 3 * (nu / rho - t * t)
    vi = nu / 120 * c ** 5 * (5 - 18 * t * t + t ** 4 + 14 * eta2 - 58 * t * t * eta2)
    dl = lo - _LON0
    e_out = _E0 + iv * dl + v * dl ** 3 + vi * dl ** 5
    n_out = i + ii * dl ** 2 + iii * dl ** 4 + iiia * dl ** 6
    return list(zip(e_out.tolist(), n_out.tolist()))
