"""Re-export from shared library for backward compatibility (moved to shared/maps/gb_basemap.py, H2)."""
from shared.maps.gb_basemap import *  # noqa: F401,F403
from shared.maps.gb_basemap import _PX_PER_TILE, _MOSAIC_W, _MOSAIC_H, _BASENAME, _ORIGIN_CACHE, _origin_for_code  # noqa: F401  (private names some callers use)
