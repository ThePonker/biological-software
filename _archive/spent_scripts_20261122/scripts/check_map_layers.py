"""Which files the Mapping tab's map draws its layers from (read-only). Written 11 Oct 2026
(Round 4) to settle what the thin lines under the vice-counties were.

The land (and its coast line) comes from data/maps/gb_outline.json when that file exists,
else from the vice-county polygons themselves (data/maps/vc_brc_wgs84.geojson, simplified
to 100 m). In that second case the old map stroked every VC ring as "coast", so each VC
border was drawn twice: once by the VC layer and once, finer and darker, by the coast.

Usage:
    py -3.14 scripts\\check_map_layers.py
"""
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "Observatum")]

import paths  # noqa: E402
from shared.maps.species_dist_map import _load_gb_outline  # noqa: E402
from shared.maps.vc_map import load_vc_polygons  # noqa: E402


def describe(name, rings):
    pts = Counter((round(e), round(n)) for r in rings for e, n in r[:-1])
    shared = sum(1 for c in pts.values() if c > 1)
    print(f"  {name}: {len(rings):,} rings, {sum(len(r) for r in rings):,} points, "
          f"{shared:,} points shared by two or more rings"
          + ("  -> it has inland borders, not just a coast" if shared > 100 else ""))


def main():
    outline = os.path.join(str(paths.MAPS_DIR), "gb_outline.json")
    print(f"Maps folder: {paths.MAPS_DIR}")
    print(f"  gb_outline.json:       {'present' if os.path.exists(outline) else 'not present'}")
    print(f"  vc_brc_wgs84.geojson:  {'present' if paths.VC_GEOJSON.exists() else 'not present'}")
    land, _b = _load_gb_outline(str(paths.MAPS_DIR))
    if land:
        print("Land and coast come from gb_outline.json:")
        describe("gb_outline.json", [r for rings in land.values() for r in rings])
        print("  (On Wil's PC: the 2013 ONS local-authority districts.) The old map stroked every "
              "ring as coast: every district border. Since Round 4 only the seaward edge shows; "
              "the district borders are the 'Districts (modern)' switch, off by default.")
    elif paths.VC_GEOJSON.exists():
        print("Land and coast come from the vice-county polygons (no gb_outline.json):")
        vcs, _b = load_vc_polygons(str(paths.VC_GEOJSON), tol=100.0)
        describe("VC polygons at 100 m", [r for rings in vcs.values() for r in rings])
        print("  The old map stroked each of these rings as coast: every VC border drawn a "
              "second time. Since Round 4 only the seaward edge shows.")
    else:
        print("No land file: the map draws grid squares only.")
    print("READ ONLY. Nothing has been changed.")


if __name__ == "__main__":
    main()
