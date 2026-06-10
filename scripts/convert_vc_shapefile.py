"""
Convert VC Boundaries Shapefile to WGS84 GeoJSON.

Reads data/maps/vc_brc.shp (OSGB36 / British National Grid)
and produces data/maps/vc_brc_wgs84.geojson (WGS84 / lat-long)
with simplified geometry suitable for Leaflet web maps.

Prerequisites:
    pip install pyshp pyproj

Usage:
    python scripts/convert_vc_shapefile.py
"""

import json
import sys
import time
from pathlib import Path

try:
    import shapefile
except ImportError:
    print("ERROR: pyshp not installed. Run: pip install pyshp")
    sys.exit(1)

try:
    from pyproj import Transformer
except ImportError:
    print("ERROR: pyproj not installed. Run: pip install pyproj")
    sys.exit(1)


PROJECT_ROOT = Path(__file__).parent.parent
SHP_PATH = PROJECT_ROOT / "data" / "maps" / "vc_brc.shp"
OUT_PATH = PROJECT_ROOT / "data" / "maps" / "vc_brc_wgs84.geojson"

# Simplification: keep every Nth point to reduce file size
# The raw shapefile is 56MB; we want ~2-5MB GeoJSON
# Adjust this value if the output is too coarse or too large
SIMPLIFY_KEEP_EVERY = 5


def simplify_coords(coords, keep_every):
    """
    Reduce vertex count by keeping every Nth point.
    Always keeps first and last point to close polygons.
    """
    if len(coords) <= 10:
        return coords
    simplified = [coords[0]]
    for i in range(1, len(coords) - 1):
        if i % keep_every == 0:
            simplified.append(coords[i])
    simplified.append(coords[-1])
    return simplified


def transform_ring(ring, transformer, keep_every):
    """Transform a single polygon ring from OSGB36 to WGS84."""
    transformed = []
    for easting, northing in ring:
        lat, lon = transformer.transform(easting, northing)
        transformed.append([round(lon, 5), round(lat, 5)])
    return simplify_coords(transformed, keep_every)


def main():
    print("=" * 60)
    print("VC Shapefile Converter (OSGB36 → WGS84 GeoJSON)")
    print("=" * 60)

    if not SHP_PATH.exists():
        print(f"\nERROR: Shapefile not found: {SHP_PATH}")
        print("Make sure vc_brc.shp is in data/maps/")
        sys.exit(1)

    start = time.time()

    # Set up coordinate transformer: OSGB36 (EPSG:27700) → WGS84 (EPSG:4326)
    transformer = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)

    # Read shapefile
    print(f"\nReading: {SHP_PATH}")
    reader = shapefile.Reader(str(SHP_PATH))
    print(f"  Records: {len(reader)}")
    print(f"  Fields: {[f[0] for f in reader.fields[1:]]}")

    # Build GeoJSON features
    features = []
    for i, (shape_rec) in enumerate(reader.iterShapeRecords()):
        shape = shape_rec.shape
        record = shape_rec.record

        # Extract attributes
        props = {}
        for j, field in enumerate(reader.fields[1:]):
            field_name = field[0]
            value = record[j]
            props[field_name] = value

        # Transform geometry
        if shape.shapeType == shapefile.POLYGON:
            # Shapefile polygons can have multiple parts (islands, holes)
            parts = list(shape.parts) + [len(shape.points)]
            rings = []
            for p in range(len(parts) - 1):
                ring_points = shape.points[parts[p]:parts[p + 1]]
                transformed_ring = transform_ring(
                    ring_points, transformer, SIMPLIFY_KEEP_EVERY
                )
                rings.append(transformed_ring)

            if len(rings) == 1:
                geometry = {"type": "Polygon", "coordinates": rings}
            else:
                # Multiple rings — could be holes or multipart
                geometry = {"type": "Polygon", "coordinates": rings}
        else:
            print(f"  WARNING: Skipping non-polygon shape type {shape.shapeType} at record {i}")
            continue

        features.append({
            "type": "Feature",
            "properties": props,
            "geometry": geometry,
        })

        if (i + 1) % 20 == 0:
            print(f"  Converted {i + 1} features...")

    # Build GeoJSON FeatureCollection
    geojson = {
        "type": "FeatureCollection",
        "features": features,
    }

    # Write output
    print(f"\nWriting: {OUT_PATH}")
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(geojson, f, separators=(",", ":"))

    out_size = OUT_PATH.stat().st_size
    elapsed = time.time() - start

    print(f"\n{'=' * 60}")
    print("CONVERSION COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Features: {len(features)}")
    print(f"  Output size: {out_size / 1024 / 1024:.1f} MB")
    print(f"  Time: {elapsed:.1f}s")

    # Verify: print first 3 features' properties
    print(f"\n  Sample features:")
    for feat in features[:5]:
        p = feat["properties"]
        print(f"    VC{p.get('VCNUMBER', '?')}: {p.get('VCNAME', '?')}")

    # Check if simplification needs adjusting
    if out_size > 10 * 1024 * 1024:
        print(f"\n  WARNING: Output is {out_size / 1024 / 1024:.0f}MB.")
        print(f"  Consider increasing SIMPLIFY_KEEP_EVERY (currently {SIMPLIFY_KEEP_EVERY})")
    elif out_size < 500 * 1024:
        print(f"\n  NOTE: Output is only {out_size / 1024:.0f}KB.")
        print(f"  Could decrease SIMPLIFY_KEEP_EVERY for more detail.")


if __name__ == "__main__":
    main()
