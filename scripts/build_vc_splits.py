"""Build data/vc_splits.db: the 1 km squares a vice-county boundary or the coast runs through (F29, I3b).

    py -3.14 -m pip install shapely pyshp          (once; only this script needs them)
    py -3.14 scripts\\build_vc_splits.py            (about 5-10 minutes; writes a NEW file)

vc_lookup.db gives each 1 km square the VC containing the square's centre. That is wrong for a
point near a boundary (SO539092 is in VC34 but its square SO5309 is listed as VC35), and leaves
out coastal squares whose centre is in the sea. This script reads the BRC vice-county boundary
shapefile (data/maps/vc_brc.shp, British National Grid metres) and, for every 1 km square that
is not wholly inside one VC, stores each VC's share of the square's land and -- where more
than one VC is present -- the outline of each VC's part, so the app can test a point with
plain Python (no shapely at run time).

    vc_split_squares(grid_1km, vc_number, area_fraction, rings_json)
        area_fraction: the VC's share of the whole 1 km square (0-1); land shares of a coastal
                       square add up to less than 1
        rings_json:    NULL when the square has only one VC; otherwise a list of rings, each a
                       list of [e, n] in metres from the square's south-west corner. A point is
                       inside if an odd number of the VC's rings contain it (holes work).
    coastal squares with one VC and no vc_lookup row are stored with rings_json NULL.

vc_lookup.db is not changed.
"""
import json
import os
import sqlite3
import sys
import time

import shapefile                                   # pyshp
import shapely
from shapely.geometry import shape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHP = os.path.join(ROOT, "data", "maps", "vc_brc.shp")
LOOKUP = os.path.join(ROOT, "data", "vc_lookup.db")
OUT = os.path.join(ROOT, "data", "vc_splits.db")
if "--out" in sys.argv:
    OUT = sys.argv[sys.argv.index("--out") + 1]
if "--root" in sys.argv:
    r = sys.argv[sys.argv.index("--root") + 1]
    SHP, LOOKUP = os.path.join(r, "data", "maps", "vc_brc.shp"), os.path.join(r, "data", "vc_lookup.db")

SQ = 1000.0
FULL = SQ * SQ
SLIVER = 1000.0          # m2 (0.1% of a square): pieces this small are digitising slop, ignored
SIMPLIFY = 2.0           # m
LETTERS = "ABCDEFGHJKLMNOPQRSTUVWXYZ"


def gridref_1km(e, n):
    e100, n100 = int(e // 100000), int(n // 100000)
    l1 = (19 - n100) - (19 - n100) % 5 + (e100 + 10) // 5
    l2 = (19 - n100) * 5 % 25 + e100 % 5
    return f"{LETTERS[l1]}{LETTERS[l2]}{int(e % 100000) // 1000:02d}{int(n % 100000) // 1000:02d}"


def rings_of(geom, e0, n0):
    out = []
    polys = getattr(geom, "geoms", [geom])
    for p in polys:
        if p.geom_type != "Polygon" or p.is_empty:
            continue
        for ring in [p.exterior, *p.interiors]:
            pts = [[round(x - e0, 1), round(y - n0, 1)] for x, y in ring.coords[:-1]]
            if len(pts) >= 3:
                out.append(pts)
    return out


def main():
    if os.path.exists(OUT):
        sys.exit(f"{OUT} already exists -- move it to _archive first; nothing changed.")
    t0 = time.time()
    rd = shapefile.Reader(SHP)
    fields = [f[0] for f in rd.fields[1:]]
    vc_col = fields.index("VCNUMBER")
    parts = {}                                      # grid_1km -> {vc: [area, geom]}
    for i, sr in enumerate(rd.iterShapeRecords()):
        vc = int(sr.record[vc_col])
        g = shapely.make_valid(shape(sr.shape.__geo_interface__))
        g = g.buffer(0) if g.geom_type not in ("Polygon", "MultiPolygon") else g
        x0, y0, x1, y1 = g.bounds
        for te in range(int(x0 // 10000) * 10000, int(x1) + 1, 10000):
            for tn in range(int(y0 // 10000) * 10000, int(y1) + 1, 10000):
                tile = shapely.clip_by_rect(g, te, tn, te + 10000, tn + 10000)
                if tile.is_empty or tile.area < SLIVER:
                    continue
                if abs(tile.area - 1e8) < 1:
                    continue                        # whole 10 km square inside this VC
                for e in range(te, te + 10000, 1000):
                    for n in range(tn, tn + 10000, 1000):
                        p = shapely.clip_by_rect(tile, e, n, e + 1000, n + 1000)
                        if p.is_empty:
                            continue
                        a = p.area
                        if a >= FULL - 1:
                            continue                # wholly inside
                        if a < SLIVER:
                            continue
                        d = parts.setdefault((e, n), {})
                        if vc in d:
                            d[vc][0] += a
                            d[vc][1] = d[vc][1].union(p)
                        else:
                            d[vc] = [a, p]
        print(f"  VC{vc:<4} {sr.record[fields.index('VCNAME')]:28} squares so far {len(parts):,}   "
              f"{time.time() - t0:.0f} s", flush=True)

    lk = sqlite3.connect(f"file:{LOOKUP}?mode=ro", uri=True)
    in_lookup = dict(lk.execute("SELECT grid_1km, vc_number FROM vc_lookup"))
    lk.close()

    out = sqlite3.connect(OUT)
    out.execute("""CREATE TABLE vc_split_squares (grid_1km TEXT NOT NULL, vc_number INTEGER NOT NULL,
                   area_fraction REAL NOT NULL, rings_json TEXT, PRIMARY KEY (grid_1km, vc_number))""")
    out.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    n_split = n_coast = n_same = 0
    rows = []
    for (e, n), d in parts.items():
        gr = gridref_1km(e, n)
        if len(d) == 1:
            (vc, (a, _)), = d.items()
            if gr in in_lookup:
                n_same += 1                         # coastal, centre on land: vc_lookup is right
                continue
            rows.append((gr, vc, round(a / FULL, 4), None))
            n_coast += 1
            continue
        n_split += 1
        for vc, (a, g) in d.items():
            g = g.simplify(SIMPLIFY, preserve_topology=True)
            rows.append((gr, vc, round(a / FULL, 4), json.dumps(rings_of(g, e, n), separators=(",", ":"))))
    out.executemany("INSERT INTO vc_split_squares VALUES (?, ?, ?, ?)", rows)
    out.executemany("INSERT INTO meta VALUES (?, ?)", [
        ("source", "data/maps/vc_brc.shp (BRC vice-county boundaries, British National Grid)"),
        ("built", time.strftime("%Y-%m-%d %H:%M")),
        ("split_squares", str(n_split)), ("coastal_squares_added", str(n_coast)),
        ("sliver_m2", str(SLIVER)), ("simplify_m", str(SIMPLIFY))])
    out.commit()
    out.execute("VACUUM")
    out.close()
    print(f"\nSquares with more than one VC: {n_split:,}")
    print(f"Coastal squares missing from vc_lookup, added: {n_coast:,}")
    print(f"Coastal squares already right in vc_lookup: {n_same:,}")
    print(f"Wrote {OUT} ({os.path.getsize(OUT) / 1e6:.1f} MB) in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
