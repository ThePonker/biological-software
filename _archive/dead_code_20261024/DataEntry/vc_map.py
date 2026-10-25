"""Re-export from shared library for backward compatibility (moved to shared/maps/vc_map.py, H2)."""
from shared.maps.vc_map import *  # noqa: F401,F403
from shared.maps.vc_map import _CACHE, _SIMPLIFY_TOL, _simplify, _rings_from_geometry  # noqa: F401  (private names some callers use)
from DataEntry.osgb import lonlat_to_en  # noqa: F401  (was importable from here)
