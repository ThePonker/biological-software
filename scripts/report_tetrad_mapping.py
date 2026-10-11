"""report_tetrad_mapping.py -- what the 2 km tetrad records would add to the maps (note 36
decision 10, 10 Oct 2026). READ ONLY: a dry run of the figure changes, before the mapping flag
is switched on (another branch adds the flag; this only reports).

    py -3.14 scripts\\report_tetrad_mapping.py
    py -3.14 scripts\\report_tetrad_mapping.py --csv D:\\somewhere\\tetrads.csv

A tetrad reference (SP46Q: a 10 km square + a DINTY letter) is a 2 km square. Wil's rule:
map it on hectad (10 km) and tetrad (2 km) grids, never on a 1 km grid. The grid-ref parsing
used here is the suite's own: shared/osgb.gridref_to_en and shared/maps/grid_squares (the
Mapping tab's squares); the older VCLookupService.parse_grid_ref, behind the Species lookup
and VC maps, does not read tetrads at all today -- the count of those it drops is shown.

Per species (TVK), per table: how many tetrad records, and how many NEW squares they add:
  new hectads  hectads where that species has no other record (any reference other than a
               tetrad that places it in the hectad: 10 km, 1 km or finer);
  new tetrads  tetrads where that species has no record of 1 km or finer.
"All sources" repeats the sums with every table's records together (the Mapping tab's
"All records"). CSV: scripts\\_oneoff\\tetrad_mapping_<date>.csv.
"""
import argparse
import sys
from collections import defaultdict

try:
    from scripts import report_common as rc
except ImportError:                       # run as py scripts\<name>.py
    import report_common as rc

import paths  # noqa: E402
from shared.maps.grid_squares import HECTAD, TETRAD, square_for_point  # noqa: E402
from shared.osgb import gridref_to_en  # noqa: E402

# (table, species column, name column, grid ref column)
TABLES = (("recording_scheme", "species_tvk", "species_name", "grid_ref"),
          ("observations", "species_tvk", "species_name", "grid_ref"),
          ("specimens", "species_tvk", "species_name", "grid_ref"),
          ("contributed_observations", "species_tvk", "species_name", "grid_ref"))
HEADER = ["table", "species_name", "species_tvk", "tetrad_records", "tetrads", "hectads",
          "new_tetrads", "new_hectads", "new_tetrads_all_sources", "new_hectads_all_sources",
          "tetrad_refs"]


def squares(ref):
    """(size_m, hectad, tetrad or None) for a grid reference, or None if it doesn't parse."""
    p = gridref_to_en(ref)
    if not p:
        return None
    e, n, size = p
    if size > HECTAD:
        return None
    return size, square_for_point(e, n, HECTAD), (square_for_point(e, n, TETRAD)
                                                  if size <= TETRAD else None)


def load(conn) -> dict:
    """{table: [(species key, name, grid ref)]} for the tables this database has."""
    out = {}
    have = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    for table, sp, name, gr in TABLES:
        if table not in have:
            continue
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        if gr not in cols:
            continue
        nm = name if name in cols else "NULL"
        tv = sp if sp in cols else "NULL"
        out[table] = [(t or n or "", n, g) for t, n, g in conn.execute(
            f"SELECT {tv}, {nm}, {gr} FROM {table} WHERE COALESCE({gr}, '') <> ''")]
    return out


def analyse(data: dict) -> dict:
    """{"tables": {table: {species: {...}}}, "all": {...}, "vc_dropped": n}"""
    occ = {}                                       # (table) -> species -> {"h": set, "t": set}
    occ_all = defaultdict(lambda: {"h": set(), "t": set()})
    tet = defaultdict(lambda: defaultdict(list))   # table -> species -> [(name, ref, h, t)]
    for table, rows in data.items():
        o = occ[table] = defaultdict(lambda: {"h": set(), "t": set()})
        for sp, name, ref in rows:
            s = squares(ref)
            if not s:
                continue
            size, h, t = s
            if size == TETRAD:
                tet[table][sp].append((name, rc.norm_ref(ref), h, t))
                continue
            for occupied in (o[sp], occ_all[sp]):
                occupied["h"].add(h)
                if size < TETRAD:
                    occupied["t"].add(t)
    out = {"tables": {}, "vc_dropped": 0}
    all_new_h, all_new_t = set(), set()
    try:
        from src.services.vc_lookup_service import VCLookupService
    except ImportError:
        from Observatum.src.services.vc_lookup_service import VCLookupService
    for table, by_sp in tet.items():
        res = out["tables"][table] = {}
        for sp, recs in by_sp.items():
            hs, ts = {r[2] for r in recs}, {r[3] for r in recs}
            out["vc_dropped"] += sum(1 for r in recs if VCLookupService.parse_grid_ref(r[1]) is None)
            new_h = hs - occ[table][sp]["h"]
            new_t = ts - occ[table][sp]["t"]
            new_h_all = hs - occ_all[sp]["h"]
            new_t_all = ts - occ_all[sp]["t"]
            all_new_h |= {(sp, h) for h in new_h_all}
            all_new_t |= {(sp, t) for t in new_t_all}
            res[sp] = {"name": recs[0][0], "records": len(recs), "tetrads": ts, "hectads": hs,
                       "new_t": new_t, "new_h": new_h, "new_t_all": new_t_all,
                       "new_h_all": new_h_all, "refs": sorted({r[1] for r in recs})}
    any_h = {h for v in occ_all.values() for h in v["h"]}
    any_t = {t for v in occ_all.values() for t in v["t"]}
    tet_h = {r[2] for by_sp in tet.values() for recs in by_sp.values() for r in recs}
    tet_t = {r[3] for by_sp in tet.values() for recs in by_sp.values() for r in recs}
    out["all"] = {"new_h": len(all_new_h), "new_t": len(all_new_t),
                  "empty_h": len(tet_h - any_h), "empty_t": len(tet_t - any_t)}
    return out


def csv_rows(res: dict):
    for table, by_sp in res["tables"].items():
        for sp, x in sorted(by_sp.items(), key=lambda kv: (kv[1]["name"] or "")):
            yield [table, x["name"], sp, x["records"], len(x["tetrads"]), len(x["hectads"]),
                   len(x["new_t"]), len(x["new_h"]), len(x["new_t_all"]), len(x["new_h_all"]),
                   " ".join(x["refs"])]


def report(data: dict, res: dict) -> None:
    for table, rows in data.items():
        by_sp = res["tables"].get(table, {})
        n = sum(x["records"] for x in by_sp.values())
        print(f"  {table}: {len(rows):,} records with a grid ref; tetrad refs {n:,}")
    for table, by_sp in res["tables"].items():
        if not by_sp:
            continue
        tot = defaultdict(int)
        for x in by_sp.values():
            tot["records"] += x["records"]
            tot["t"] += len(x["tetrads"])
            tot["h"] += len(x["hectads"])
            for k in ("new_t", "new_h", "new_t_all", "new_h_all"):
                tot[k] += len(x[k])
        print("")
        print(f"  {table} -- {len(by_sp):,} species with tetrad records")
        print(f"  {'species':<34}{'records':>8}{'tetrads':>8}{'new':>5}"
              f"{'hectads':>9}{'new':>5}   new (all sources) tetrads / hectads")
        for sp, x in sorted(by_sp.items(), key=lambda kv: (-kv[1]["records"], kv[1]["name"] or "")):
            print(f"  {str(x['name'] or sp)[:33]:<34}{x['records']:>8}{len(x['tetrads']):>8}"
                  f"{len(x['new_t']):>5}{len(x['hectads']):>9}{len(x['new_h']):>5}"
                  f"   {len(x['new_t_all']):>4} / {len(x['new_h_all'])}")
        print(f"  {'TOTAL':<34}{tot['records']:>8}{tot['t']:>8}{tot['new_t']:>5}{tot['h']:>9}"
              f"{tot['new_h']:>5}   {tot['new_t_all']:>4} / {tot['new_h_all']}")
    print("")
    print(f"  All sources together: {res['all']['new_t']:,} new species-tetrads, "
          f"{res['all']['new_h']:,} new species-hectads")
    print(f"  Squares with no record of any species until now (the 'no taxon chosen' map): "
          f"{res['all']['empty_t']:,} tetrads, {res['all']['empty_h']:,} hectads")
    print(f"  Tetrad records the VC lookup's parse_grid_ref drops today (Species lookup / VC "
          f"maps): {res['vc_dropped']:,}")
    print("  1 km (monad) maps: no change -- a tetrad is never put on a 1 km grid.")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--csv", default=rc.default_csv("tetrad_mapping"))
    ap.add_argument("--db", default=str(paths.OBSERVATUM_DB), help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    print("")
    print("Tetrad (2 km) records -- what they would add to the hectad and tetrad maps (READ ONLY)")
    print("=" * 74)
    print(f"  observatum.db: {a.db}")
    conn = rc.connect_ro(a.db)
    try:
        data = load(conn)
    finally:
        conn.close()
    res = analyse(data)
    report(data, res)
    n = rc.write_csv(a.csv, HEADER, csv_rows(res))
    print("")
    print(f"  CSV: {n:,} species rows -> {a.csv}")
    print("")
    print("READ ONLY. Nothing has been changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
