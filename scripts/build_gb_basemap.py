"""Optional one-off: pre-build the GB OS-tile basemap so the Data Entry distribution map is
instant on first use. Safe to run anytime; re-run after adding tiles by deleting the old PNG.

    py -3.14 scripts\build_gb_basemap.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import paths
    maps_dir = str(paths.MAPS_DIR)
except Exception:
    maps_dir = os.path.join("data", "maps")
from shared.maps.raster_map import find_tiles_dir
from shared.maps.gb_basemap import gb_basemap_path, _BASENAME

tiles = find_tiles_dir(maps_dir)
if not tiles:
    print(f"No OS 250k tiles found under {maps_dir}\\ras250\\ -- copy the .tif tiles there first.")
    raise SystemExit(1)
out = os.path.join(maps_dir, _BASENAME)
if os.path.exists(out):
    print(f"Basemap already exists: {out}\n(delete it and re-run to rebuild from current tiles.)")
    raise SystemExit(0)
print(f"Building GB basemap from tiles in {tiles} ... (a few seconds)")
p = gb_basemap_path(tiles, maps_dir)
print("Done:", p if p else "FAILED (need Pillow and tiles present)")
