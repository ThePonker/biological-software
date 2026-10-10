"""Check the vice-county outlines the maps draw against the BRC shapefile (read-only).

For every VC in data/maps/vc_brc.shp: the area of the outline the maps draw (shared/maps/
vc_map.load_vc_polygons from data/maps/vc_brc_wgs84.geojson) against the shapefile's own
area, and the drawn extent (what County view zooms to) against the shapefile's. A VC whose
drawn area is off by more than 10 %, or whose extent is off by more than 5 km on any side,
is listed. Written 10 Oct 2026 for the County view bug (VC1 drawn as one triangle).

Needs pyshp (pip install pyshp), as scripts/convert_vc_shapefile.py does.

Usage:
    python scripts/check_vc_outlines.py            # report only; nothing is written
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "Observatum")]

import paths  # noqa: E402
from shared.maps.vc_map import load_vc_polygons, ring_area  # noqa: E402

AREA_TOL = 0.10          # drawn area within 10 % of the shapefile's
EXTENT_TOL = 5000.0      # drawn extent within 5 km of the shapefile's on every side


def shapefile_truth(shp_path):
    """{vc: (area m2, (minE, minN, maxE, maxN), parts)} from the shapefile (outer rings
    clockwise, holes anticlockwise, so the area is minus the summed signed areas)."""
    import shapefile
    out = {}
    for sr in shapefile.Reader(str(shp_path)).iterShapeRecords():
        s = sr.shape
        vc = int(sr.record["VCNUMBER"])
        parts = list(s.parts) + [len(s.points)]
        rings = [s.points[parts[i]:parts[i + 1]] for i in range(len(parts) - 1)]
        area = -sum(ring_area(r) for r in rings)
        old = out.get(vc)
        bb = tuple(s.bbox)
        if old:                                  # a VC in more than one record
            area += old[0]
            bb = (min(bb[0], old[1][0]), min(bb[1], old[1][1]),
                  max(bb[2], old[1][2]), max(bb[3], old[1][3]))
        out[vc] = (area, bb, len(rings) + (old[2] if old else 0))
    return out


def check(shp_path=None, geojson_path=None, tol=300.0):
    """[(vc, parts, area ratio, worst extent difference m, ok)] for every VC."""
    truth = shapefile_truth(shp_path or paths.MAPS_DIR / "vc_brc.shp")
    rings, _b = load_vc_polygons(str(geojson_path or paths.VC_GEOJSON), tol=tol)
    rows = []
    for vc, (area, bb, parts) in sorted(truth.items()):
        drawn = rings.get(vc, [])
        d_area = sum(abs(ring_area(r)) for r in drawn)
        ratio = d_area / area if area else 0.0
        if drawn:
            es = [e for r in drawn for e, _n in r]
            ns = [n for r in drawn for _e, n in r]
            ext = (min(es), min(ns), max(es), max(ns))
            off = max(abs(a - b) for a, b in zip(ext, bb))
        else:
            off = float("inf")
        ok = abs(ratio - 1) <= AREA_TOL and off <= EXTENT_TOL
        rows.append((vc, parts, ratio, off, ok))
    return rows


def main():
    rows = check()
    bad = [r for r in rows if not r[4]]
    print(f"{len(rows)} vice-counties checked; {len(bad)} drawn wrongly.")
    for vc, parts, ratio, off, _ok in bad:
        print(f"  VC{vc}: {parts} parts in the shapefile, drawn area {ratio:.1%} of the "
              f"true area, extent off by {off / 1000:,.1f} km")
    print("Nothing has been changed.")


if __name__ == "__main__":
    main()
