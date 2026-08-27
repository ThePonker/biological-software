"""Approximate WGS84 lon/lat -> OSGB National Grid easting/northing.

Standard OS transverse-Mercator forward formulas on the Airy 1830 ellipsoid. The OSGB36<->WGS84
datum shift is deliberately skipped: at the county-thumbnail scale used here the error is ~100 m
(well under a pixel), and it keeps this dependency-free and fast. Grid refs already parse to
easting/northing, so only the VC polygons (WGS84) are converted, once, at load time.
"""
from __future__ import annotations

import math

_a = 6377563.396          # Airy 1830 semi-major
_b = 6356256.909          # Airy 1830 semi-minor
_F0 = 0.9996012717        # central meridian scale
_lat0 = math.radians(49.0)
_lon0 = math.radians(-2.0)
_N0 = -100000.0
_E0 = 400000.0
_e2 = 1.0 - (_b * _b) / (_a * _a)
_n = (_a - _b) / (_a + _b)


def lonlat_to_en(lon_deg: float, lat_deg: float):
    """Return (easting, northing) in metres for a WGS84 lon/lat (approx, no datum shift)."""
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    sl = math.sin(lat)
    cl = math.cos(lat)
    tl = math.tan(lat)

    nu = _a * _F0 / math.sqrt(1 - _e2 * sl * sl)
    rho = _a * _F0 * (1 - _e2) / (1 - _e2 * sl * sl) ** 1.5
    eta2 = nu / rho - 1

    Ma = (1 + _n + 1.25 * _n * _n + 1.25 * _n ** 3) * (lat - _lat0)
    Mb = (3 * _n + 3 * _n * _n + 2.625 * _n ** 3) * math.sin(lat - _lat0) * math.cos(lat + _lat0)
    Mc = (1.875 * _n * _n + 1.875 * _n ** 3) * math.sin(2 * (lat - _lat0)) * math.cos(2 * (lat + _lat0))
    Md = (35 / 24) * _n ** 3 * math.sin(3 * (lat - _lat0)) * math.cos(3 * (lat + _lat0))
    M = _b * _F0 * (Ma - Mb + Mc - Md)

    I = M + _N0
    II = (nu / 2) * sl * cl
    III = (nu / 24) * sl * cl ** 3 * (5 - tl ** 2 + 9 * eta2)
    IIIA = (nu / 720) * sl * cl ** 5 * (61 - 58 * tl ** 2 + tl ** 4)
    IV = nu * cl
    V = (nu / 6) * cl ** 3 * (nu / rho - tl ** 2)
    VI = (nu / 120) * cl ** 5 * (5 - 18 * tl ** 2 + tl ** 4 + 14 * eta2 - 58 * tl ** 2 * eta2)

    dlon = lon - _lon0
    N = I + II * dlon ** 2 + III * dlon ** 4 + IIIA * dlon ** 6
    E = _E0 + IV * dlon + V * dlon ** 3 + VI * dlon ** 5
    return (E, N)
