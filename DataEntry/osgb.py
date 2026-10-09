"""WGS84 lon/lat -> OSGB National Grid easting/northing, for the Data Entry maps.

Now a shim over shared.osgb (9 Oct 2026, I3c), which applies the OSGB36 <-> WGS84 datum
shift. The old version here skipped it, so VC outlines drawn from the WGS84 boundary file
sat ~100 m off the grid squares.
"""
from __future__ import annotations

from shared.osgb import wgs84_to_osgb_en


def lonlat_to_en(lon_deg: float, lat_deg: float):
    """Return (easting, northing) in metres for a WGS84 lon/lat."""
    return wgs84_to_osgb_en(lat_deg, lon_deg)
