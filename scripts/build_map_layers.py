"""build_map_layers.py -- turn two OS OpenData GeoPackages into the compact map layer files.

    py -3.14 scripts\\build_map_layers.py                 # dry run: finds sources, says what it would build
    py -3.14 scripts\\build_map_layers.py --apply         # build the layer files (long: Zoomstack is 11.8 GB)
    py -3.14 scripts\\build_map_layers.py --apply --only woodland,rivers
    py -3.14 scripts\\build_map_layers.py --check         # size / features / points of files already built
    py -3.14 scripts\\build_map_layers.py --describe names,rail   # read-only: columns, rows, common types

Reads OS Open Zoomstack and OS Boundary-Line (both GeoPackage, EPSG:27700) read-only from
--source (default ~/OS data) and writes data/maps/layers/<key>_<lod>.json (--out overrides).
The "relief" layer is made from OS Terrain 50 (ASCII Grid zip, read without extracting; see
build_map_relief.py) into relief_gb.png + relief_gb.json. If it is not found, it is skipped.
Nothing but the output folder is ever written; the sources are only read.
"""
import argparse
import json
import os
import sqlite3
import sys
from datetime import date
from pathlib import Path

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import paths  # noqa: E402
import shapely  # noqa: E402
import shapely.wkb  # noqa: E402
from shapely.geometry import Polygon  # noqa: E402
from shapely.geometry.polygon import orient  # noqa: E402

from scripts.map_gpkg import (Classes, Soft, count_rows, decode_gpkg, open_ro,  # noqa: E402,F401
                              point_features, read_rows, table_info)
from shared.maps import place_classes  # noqa: E402

ZOOMSTACK_URL = "https://osdatahub.os.uk/downloads/open/OpenZoomstack"
BOUNDARY_URL = "https://osdatahub.os.uk/downloads/open/BoundaryLine"
ATTRIBUTION = "Contains OS data © Crown copyright and database right 2026."
LODS = ("gb", "county")
ZOOM, BOUND = "zoomstack", "boundary"
_NAMES = {ZOOM: "OS Open Zoomstack", BOUND: "OS Boundary-Line"}
_PROBE = {ZOOM: "woodland", BOUND: "district_borough_unitary"}

RELIEF = "relief"


# ---- THE TABLE: per layer and lod -> (tables [(table, types or None)], tolerance m, min area m2) ----
_GB_TOL, _GB_AREA, _CO_TOL, _CO_AREA = 250, 500000, 25, 10000


def _scaled(table, soft=False):
    """Zoomstack scale versions: National for the GB view, Regional for the county view."""
    one = Soft if soft else list
    return {"gb": ([(table, one(["National"]))], _GB_TOL, _GB_AREA),
            "county": ([(table, one(["Regional"]))], _CO_TOL, _CO_AREA)}


def _place_names():
    """Cities in the GB file, the rest in the county file (place_classes.py is the one table)."""
    out = {}
    for lod in LODS:
        classes = Classes(place_classes.source_values(lod))
        classes.detect = [v for c in place_classes.PLACE_CLASSES for v in c.values]
        out[lod] = ([("names", classes)], 0, 0)
    return out


LAYERS = {
    "land": ("polygon", ZOOM, {"gb": ([("land", None)], _GB_TOL, _GB_AREA),
                               "county": ([("land", None)], _CO_TOL, _CO_AREA)}),
    "water": ("polygon", ZOOM, _scaled("surfacewater")),
    "rivers": ("line", ZOOM, _scaled("waterlines")),
    "woodland": ("polygon", ZOOM, _scaled("woodland")),
    "towns": ("polygon", ZOOM, _scaled("urban_areas")),
    "roads": ("line", ZOOM, {
        "gb": ([("roads_national", None)], _GB_TOL, 0),
        "county": ([("roads_national", None), ("roads_regional", ["A Road"])], _CO_TOL, 0)}),
    "districts": ("polygon", BOUND, {
        "gb": ([("district_borough_unitary", None)], _GB_TOL, 0),
        "county": ([("district_borough_unitary", None)], _CO_TOL, 0)}),
    # 18 Oct 2026 (table and column names to be checked with --describe)
    "rail": ("line", ZOOM, _scaled("rail", soft=True)),
    "national_parks": ("polygon", ZOOM, _scaled("national_parks", soft=True)),
    "foreshore": ("polygon", ZOOM, _scaled("foreshore", soft=True)),
    "greenspace": ("polygon", ZOOM, _scaled("greenspace", soft=True)),
    "names": ("point", ZOOM, _place_names()),
}
# layers merged into one shape before simplifying: the land comes in pieces whose shared edges
# would otherwise be drawn as coast (and simplified apart, leaving slivers)
MERGE = ("land",)


# ---- geometry -> compact features ----
def _clean(coords):
    """Round to integer metres and drop consecutive duplicate points."""
    out = []
    for x, y in coords:
        p = [int(round(x)), int(round(y))]
        if not out or out[-1] != p:
            out.append(p)
    return out


def _bbox(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return [min(xs), min(ys), max(xs), max(ys)]


def merge_lines(geoms):
    """The line geometries joined end to end where exactly two meet (shapely.line_merge), so
    a road cut into thousands of segments becomes a few long lines; None if there are none."""
    parts = [p for g in geoms if g is not None for p in shapely.get_parts(g)
             if p.geom_type == "LineString" and not p.is_empty]
    return shapely.line_merge(shapely.MultiLineString(parts)) if parts else None


def to_features(geom, kind, tol, min_area, name=None, typ=None):
    """Simplify a geometry and return its compact feature dicts ("t": the source type, lines)."""
    if geom is None or geom.is_empty:
        return []
    geom = geom.simplify(tol, preserve_topology=True)
    wanted = "Polygon" if kind == "polygon" else "LineString"
    feats = []
    for part in shapely.get_parts(geom):
        if part.is_empty or part.geom_type != wanted:
            continue
        if kind == "line":
            pts = _clean(part.coords)
            if len(pts) >= 2:
                feats.append({"bbox": _bbox(pts), "line": pts})
            continue
        if Polygon(part.exterior).area < min_area:
            continue
        part = orient(part, 1.0)          # outer anticlockwise, holes clockwise: the map fills
        outer = _clean(part.exterior.coords)    # with WindingFill, so touching parts never cancel
        if len(outer) < 4:
            continue
        rings = [outer]
        for hole in part.interiors:
            h = _clean(hole.coords)
            if len(h) >= 4 and Polygon(hole).area >= min_area:
                rings.append(h)
        feats.append({"bbox": _bbox(outer), "rings": rings})
    if name is not None:
        for f in feats:
            f["name"] = name
    if typ is not None:
        for f in feats:
            f["t"] = typ
    return feats


def count_points(feature):
    if "pt" in feature:
        return 1
    return len(feature["line"]) if "line" in feature else sum(len(r) for r in feature["rings"])


# ---- sources ----
def find_gpkg(source, kind):
    """First *.gpkg under source whose gpkg_contents lists the probe table for this source kind."""
    for path in sorted(Path(source).rglob("*.gpkg")) if Path(source).is_dir() else []:
        try:
            conn = open_ro(path)
            try:
                hit = conn.execute("SELECT 1 FROM gpkg_contents WHERE lower(table_name)=?",
                                   (_PROBE[kind],)).fetchone()
            finally:
                conn.close()
        except sqlite3.Error:
            continue
        if hit:
            return path
    return None


def _types_text(types):
    return "all types" if not types else "types " + json.dumps(types)


def _source_text(kind, path, tables):
    parts = ", ".join(f"table {t}, {_types_text(ty)}" for t, ty in tables)
    return f"{_NAMES[kind]} ({Path(path).name}, {parts})"


# ---- build ----
def build_layer(conn, gpkg, key, lod, out_dir):
    kind, src, lods = LAYERS[key]
    tables, tol, min_area = lods[lod]
    feats, rows = [], 0
    merge = key in MERGE                      # land: one shape, so no seams or inner coast
    join = kind == "line"                     # lines: joined end to end per type, then simplified
    pieces, groups = [], {}
    if kind == "point":
        feats, rows = point_features(conn, tables)
    for table, types in (() if kind == "point" else tables):
        for geom, name, typ in read_rows(conn, table, types, want_name=(key == "districts"),
                                         want_type=join):
            rows += 1
            if join:
                if geom is not None and not geom.is_empty:
                    groups.setdefault(typ, []).append(geom)
            elif merge:
                if geom is not None and not geom.is_empty:
                    pieces.append(geom)
            else:
                feats.extend(to_features(geom, kind, tol, min_area, name))
            if rows % 20000 == 0:
                print(f"      ... {rows} rows read, {len(feats)} features kept", flush=True)
    if merge and pieces:
        print(f"      merging {len(pieces)} pieces ...", flush=True)
        feats = to_features(shapely.unary_union(pieces), kind, tol, min_area)
    for typ, geoms in sorted(groups.items(), key=lambda kv: str(kv[0])):
        print(f"      joining {len(geoms)} {typ or 'untyped'} lines ...", flush=True)
        feats.extend(to_features(merge_lines(geoms), kind, tol, min_area, typ=typ))
    doc = {"layer": key, "lod": lod, "kind": kind, "source": _source_text(src, gpkg, tables),
           "attribution": ATTRIBUTION, "built": date.today().isoformat(),
           "tolerance_m": tol, "min_area_m2": min_area, "features": feats}
    target = Path(out_dir) / f"{key}_{lod}.json"
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, target)
    pts = sum(count_points(f) for f in feats)
    print(f"  {key}_{lod}: {rows} rows read, {len(feats)} features kept, {pts} points, "
          f"{target.stat().st_size:,} bytes", flush=True)


def check_folder(out_dir):
    files = sorted(Path(out_dir).glob("*.json")) if Path(out_dir).is_dir() else []
    print(f"\nLayer files in {out_dir}")
    if not files:
        print("  (none)")
    for f in files:
        doc = json.loads(f.read_text(encoding="utf-8"))
        feats = doc.get("features", [])
        pts = sum(count_points(x) for x in feats)
        if doc.get("kind") == "image":
            print(f"  {f.name}: {f.stat().st_size:,} bytes, image {doc.get('width')} x {doc.get('height')} "
                  f"cells of {doc.get('cell_m')} m")
            continue
        print(f"  {f.name}: {f.stat().st_size:,} bytes, {len(feats)} features, {pts} points")
    print("\nREAD ONLY. Nothing has been changed.")
    return 0


def main(argv=None) -> int:
    from shared.away_mode import refuse_if_away; refuse_if_away("build_map_layers")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true", help="build the files (default is a dry run)")
    ap.add_argument("--only", default="", help="comma list of layers: " + ",".join([*LAYERS, RELIEF]))
    ap.add_argument("--check", action="store_true", help="describe files already built")
    ap.add_argument("--describe", default="", metavar="TABLE[,TABLE]",
                    help="read-only: each table's columns, rows, geometry type and commonest types")
    ap.add_argument("--source", default=str(Path.home() / "OS data"))
    ap.add_argument("--out", default=str(Path(paths.ROOT) / "data" / "maps" / "layers"))
    a = ap.parse_args(argv)
    if a.check:
        return check_folder(a.out)
    if a.describe:
        from scripts.build_map_describe import describe
        return describe(a.source, [t.strip() for t in a.describe.split(",") if t.strip()])
    keys = [k.strip() for k in a.only.split(",") if k.strip()] or [*LAYERS, RELIEF]
    bad = [k for k in keys if k not in LAYERS and k != RELIEF]
    if bad:
        print(f"Unknown layer(s) {bad}; choose from {[*LAYERS, RELIEF]}. Nothing has been changed.")
        return 1
    found, missing = {}, False
    for kind in (ZOOM, BOUND):
        if any(k in LAYERS and LAYERS[k][1] == kind for k in keys):
            found[kind] = find_gpkg(a.source, kind)
            if found[kind] is None:
                missing = True
                url = ZOOMSTACK_URL if kind == ZOOM else BOUNDARY_URL
                print(f"\nMissing source: {_NAMES[kind]} GeoPackage (no .gpkg with table "
                      f"{_PROBE[kind]} in {a.source}).\n  Download (GeoPackage): {url}\n"
                      f"  Unzip it into {a.source} and run this again.")
    if missing:
        print("\nNothing has been changed.")
        return 1
    print(f"\nMap layers ({'BUILD' if a.apply else 'DRY RUN'}) -> {a.out}")
    for kind, path in found.items():
        print(f"  {_NAMES[kind]}: {path}")
    if a.apply:
        Path(a.out).mkdir(parents=True, exist_ok=True)
    conns = {k: open_ro(p) for k, p in found.items()}
    problems = 0
    try:
        for key in (k for k in keys if k != RELIEF):
            src = LAYERS[key][1]
            for lod in LODS:
                tables, tol, min_area = LAYERS[key][2][lod]
                try:
                    if a.apply:
                        print(f"\n[{key} / {lod}] tolerance {tol} m, min area {min_area} m2", flush=True)
                        build_layer(conns[src], found[src], key, lod, a.out)
                    else:
                        for table, types in tables:
                            n = count_rows(conns[src], table, types)
                            print(f"  {key}_{lod}: table {table}, {_types_text(types)}, {n} rows "
                                  f"(tolerance {tol} m, min area {min_area} m2)")
                except ValueError as e:
                    problems += 1
                    print(f"  {key}_{lod}: {e}")
    finally:
        for c in conns.values():
            c.close()
    if RELIEF in keys:
        from scripts.build_map_relief import build_relief
        problems += build_relief(a.source, a.out, ATTRIBUTION, a.apply, explicit=(RELIEF in a.only))
    print("\n" + ("Done." if a.apply and not problems else
                  "Nothing has been changed." if not a.apply else "Finished with problems."))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
