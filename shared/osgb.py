"""osgb -- the one place grid references, eastings/northings and lat/long are converted (I3c).

Pure Python, no dependencies. OSGB36 transverse Mercator on the Airy 1830 ellipsoid, and the
OS 7-parameter Helmert transformation between OSGB36 and WGS84. Checked against Ordnance
Survey's 40 published test points: within 5 m (median about 2 m), which the OS gives as the
accuracy of a Helmert transformation; OSTN15 (0.1 m) is not needed for 100 m squares.

A grid reference is a SQUARE. Its point is the CENTRE of that square (agreed 9 Oct 2026):
SP580207 is the 100 m square whose south-west corner is 458000, 220700, so its point is
458050, 220750. The import wizard used the corner and no datum shift, which put 3,332 records
up to ~150 m out (fault F30). The old `grid_converter_service` (OSGridConverter) gets the
longitude wrong by up to 1.4 km away from 2 deg W and is not used.

    gridref_to_en("SP580207")        -> (458000, 220700, 100)    south-west corner + size
    gridref_centre("SP580207")       -> (458050.0, 220750.0)
    gridref_to_wgs84("SP580207")     -> (lat, lon) of the centre
    en_to_gridref(458050, 220750, 6) -> "SP580207"
    osgb_en_to_wgs84(e, n)           -> (lat, lon)
    wgs84_to_osgb_en(lat, lon)       -> (e, n)
"""
from __future__ import annotations

import math
import re
from typing import Optional, Tuple

_LETTERS = "ABCDEFGHJKLMNOPQRSTUVWXYZ"       # no I
_DINTY = "ABCDEFGHIJKLMNPQRSTUVWXYZ"         # tetrad letters: no O

# Airy 1830 (OSGB36) and GRS80 / WGS84 ellipsoids
_AIRY = (6377563.396, 6356256.909)
_WGS84 = (6378137.000, 6356752.3141)
# National Grid projection
_F0 = 0.9996012717
_LAT0 = math.radians(49.0)
_LON0 = math.radians(-2.0)
_N0, _E0 = -100000.0, 400000.0
# OSGB36 -> WGS84 Helmert (OS guide); WGS84 -> OSGB36 is the same with every sign flipped
_TO_WGS84 = (446.448, -125.157, 542.060, -20.4894, 0.1502, 0.2470, 0.8421)


# ---------------------------------------------------------------- grid references

def _square_origin(letters: str) -> Optional[Tuple[int, int]]:
    """South-west corner (km x100) of a 100 km square from its two letters."""
    if len(letters) != 2 or any(c not in _LETTERS for c in letters):
        return None
    l1, l2 = _LETTERS.index(letters[0]), _LETTERS.index(letters[1])
    e100 = ((l1 - 2) % 5) * 5 + (l2 % 5)
    n100 = (19 - (l1 // 5) * 5) - (l2 // 5)
    if not (0 <= e100 <= 6 and 0 <= n100 <= 12):
        return None
    return e100, n100


def gridref_to_en(ref) -> Optional[Tuple[int, int, int]]:
    """(easting, northing, size_m) of the square's SOUTH-WEST CORNER, or None.

    Accepts spaces and any even number of digits (SP58, SP5820, SP580207, 'TQ 53083 77347'),
    and 2 km tetrads in the DINTY letters (SP58A: A-E up the first column, F-K the next, no O).
    """
    if not ref:
        return None
    s = str(ref).upper().replace(" ", "")
    t = re.fullmatch(r"([A-Z]{2})(\d)(\d)([A-NP-Z])", s)
    if t:
        origin = _square_origin(t.group(1))
        if origin is None:
            return None
        k = _DINTY.index(t.group(4))
        return (origin[0] * 100000 + int(t.group(2)) * 10000 + (k // 5) * 2000,
                origin[1] * 100000 + int(t.group(3)) * 10000 + (k % 5) * 2000, 2000)
    m = re.fullmatch(r"([A-Z]{2})(\d*)", s)
    if not m or len(m.group(2)) % 2:
        return None
    origin = _square_origin(m.group(1))
    if origin is None:
        return None
    digits = m.group(2)
    half = len(digits) // 2
    size = 10 ** (5 - half)
    e = origin[0] * 100000 + (int(digits[:half]) * size if half else 0)
    n = origin[1] * 100000 + (int(digits[half:]) * size if half else 0)
    return e, n, size


def gridref_centre(ref) -> Optional[Tuple[float, float]]:
    p = gridref_to_en(ref)
    return (p[0] + p[2] / 2, p[1] + p[2] / 2) if p else None


def en_to_gridref(e: float, n: float, digits: int = 6) -> Optional[str]:
    """Grid reference of the square containing (e, n); digits = 2, 4, 6, 8 or 10."""
    if not (0 <= e < 700000 and 0 <= n < 1300000) or digits % 2 or not 0 <= digits <= 10:
        return None
    e100, n100 = int(e // 100000), int(n // 100000)
    l1 = (19 - n100) - (19 - n100) % 5 + (e100 + 10) // 5
    l2 = (19 - n100) * 5 % 25 + e100 % 5
    half = digits // 2
    size = 10 ** (5 - half)
    if not half:
        return _LETTERS[l1] + _LETTERS[l2]
    return (_LETTERS[l1] + _LETTERS[l2] + f"{int(e % 100000) // size:0{half}d}"
            + f"{int(n % 100000) // size:0{half}d}")


# ---------------------------------------------------------------- projection

def _meridional(b, n, lat):
    return b * _F0 * ((1 + n + 1.25 * n ** 2 + 1.25 * n ** 3) * (lat - _LAT0)
                      - (3 * n + 3 * n ** 2 + 2.625 * n ** 3) * math.sin(lat - _LAT0) * math.cos(lat + _LAT0)
                      + (1.875 * n ** 2 + 1.875 * n ** 3) * math.sin(2 * (lat - _LAT0)) * math.cos(2 * (lat + _LAT0))
                      - (35 / 24) * n ** 3 * math.sin(3 * (lat - _LAT0)) * math.cos(3 * (lat + _LAT0)))


def _en_to_latlon_airy(e, n_):
    a, b = _AIRY
    e2 = 1 - b * b / (a * a)
    n = (a - b) / (a + b)
    lat, m = _LAT0, 0.0
    while True:
        lat = (n_ - _N0 - m) / (a * _F0) + lat
        m = _meridional(b, n, lat)
        if abs(n_ - _N0 - m) < 1e-5:
            break
    s, c, t = math.sin(lat), math.cos(lat), math.tan(lat)
    nu = a * _F0 / math.sqrt(1 - e2 * s * s)
    rho = a * _F0 * (1 - e2) / (1 - e2 * s * s) ** 1.5
    eta2 = nu / rho - 1
    vii = t / (2 * rho * nu)
    viii = t / (24 * rho * nu ** 3) * (5 + 3 * t * t + eta2 - 9 * t * t * eta2)
    ix = t / (720 * rho * nu ** 5) * (61 + 90 * t * t + 45 * t ** 4)
    x = 1 / (c * nu)
    xi = 1 / (c * 6 * nu ** 3) * (nu / rho + 2 * t * t)
    xii = 1 / (c * 120 * nu ** 5) * (5 + 28 * t * t + 24 * t ** 4)
    xiia = 1 / (c * 5040 * nu ** 7) * (61 + 662 * t * t + 1320 * t ** 4 + 720 * t ** 6)
    de = e - _E0
    return (lat - vii * de ** 2 + viii * de ** 4 - ix * de ** 6,
            _LON0 + x * de - xi * de ** 3 + xii * de ** 5 - xiia * de ** 7)


def _latlon_airy_to_en(lat, lon):
    a, b = _AIRY
    e2 = 1 - b * b / (a * a)
    n = (a - b) / (a + b)
    s, c, t = math.sin(lat), math.cos(lat), math.tan(lat)
    nu = a * _F0 / math.sqrt(1 - e2 * s * s)
    rho = a * _F0 * (1 - e2) / (1 - e2 * s * s) ** 1.5
    eta2 = nu / rho - 1
    m = _meridional(b, n, lat)
    i = m + _N0
    ii = nu / 2 * s * c
    iii = nu / 24 * s * c ** 3 * (5 - t * t + 9 * eta2)
    iiia = nu / 720 * s * c ** 5 * (61 - 58 * t * t + t ** 4)
    iv = nu * c
    v = nu / 6 * c ** 3 * (nu / rho - t * t)
    vi = nu / 120 * c ** 5 * (5 - 18 * t * t + t ** 4 + 14 * eta2 - 58 * t * t * eta2)
    dl = lon - _LON0
    return (_E0 + iv * dl + v * dl ** 3 + vi * dl ** 5,
            i + ii * dl ** 2 + iii * dl ** 4 + iiia * dl ** 6)


def _helmert(lat, lon, src, dst, params, sign=1):
    tx, ty, tz, s, rx, ry, rz = (sign * p for p in params)
    a, b = src
    e2 = 1 - b * b / (a * a)
    nu = a / math.sqrt(1 - e2 * math.sin(lat) ** 2)
    x = nu * math.cos(lat) * math.cos(lon)
    y = nu * math.cos(lat) * math.sin(lon)
    z = (1 - e2) * nu * math.sin(lat)
    s *= 1e-6
    rx, ry, rz = (math.radians(r / 3600) for r in (rx, ry, rz))
    x2 = tx + (1 + s) * x - rz * y + ry * z
    y2 = ty + rz * x + (1 + s) * y - rx * z
    z2 = tz - ry * x + rx * y + (1 + s) * z
    a, b = dst
    e2 = 1 - b * b / (a * a)
    p = math.hypot(x2, y2)
    la = math.atan2(z2, p * (1 - e2))
    for _ in range(10):
        nu = a / math.sqrt(1 - e2 * math.sin(la) ** 2)
        la = math.atan2(z2 + e2 * nu * math.sin(la), p)
    return la, math.atan2(y2, x2)


def osgb_en_to_wgs84(e: float, n: float) -> Tuple[float, float]:
    """OSGB36 easting/northing -> WGS84 (lat, lon) in degrees."""
    lat, lon = _en_to_latlon_airy(e, n)
    lat, lon = _helmert(lat, lon, _AIRY, _WGS84, _TO_WGS84)
    return math.degrees(lat), math.degrees(lon)


def wgs84_to_osgb_en(lat: float, lon: float) -> Tuple[float, float]:
    """WGS84 (lat, lon) in degrees -> OSGB36 easting/northing."""
    la, lo = _helmert(math.radians(lat), math.radians(lon), _WGS84, _AIRY, _TO_WGS84, sign=-1)
    return _latlon_airy_to_en(la, lo)


def gridref_to_wgs84(ref, at: str = "centre") -> Optional[Tuple[float, float]]:
    """(lat, lon) of a grid reference's centre (default) or south-west corner."""
    p = gridref_to_en(ref)
    if not p:
        return None
    e, n, size = p
    if at == "centre":
        e, n = e + size / 2, n + size / 2
    lat, lon = osgb_en_to_wgs84(e, n)
    return round(lat, 6), round(lon, 6)


def distance_m(lat1, lon1, lat2, lon2) -> float:
    """Approximate ground distance in metres (fine at these scales)."""
    dl = math.radians(lat2 - lat1)
    dn = math.radians(lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
    return 6371000 * math.hypot(dl, dn)
