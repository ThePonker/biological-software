"""report_scheme_duplicates.py -- Recording Scheme records held twice (item L12 / backlog E,
10 Oct 2026). READ ONLY: lists the pairs, changes nothing; removing copies is a later decision.

    py -3.14 scripts\\report_scheme_duplicates.py
    py -3.14 scripts\\report_scheme_duplicates.py --csv D:\\somewhere\\dupes.csv

Why
---
The same record often came in twice: once from iRecord (irecord_id, with the recorder) and once
from the NBN Atlas (nbn_atlas_id, no recorder), e.g. the NBN dataset "Longhorn beetle
(Cerambycidae) data from iRecord" is iRecord's own records re-served by the Atlas.

Tiers (each pair of records is put in its best tier only)
-----
  same iRecord id  an NBN Atlas row whose occurrence ID is an iRecord row's irecord_id, with
                   the same TVK and date -- the same iRecord record for certain (the Atlas may
                   blur the grid ref of a sensitive record, so the grid ref is not required).
  exact            same TVK + date + grid ref (case and spaces ignored) + recorder (same text).
  likely           same TVK + date + grid ref, and one recorder blank, or the two recorders
                   are spellings of the same person ('Heeney, W.J.' / 'Wil Heeney'), or both
                   blank but from different import routes or datasets.
  possible         same TVK + date + grid ref but two different recorders, or both blank in
                   the same dataset -- could be two genuine records; listed for completeness.
Rows with no TVK, date or grid ref are not compared.

CSV: every pair, both ids, routes, datasets, irecord_id / nbn_atlas_id / occurrence_id, dates,
grid refs, sites and recorders (scripts\\_oneoff\\scheme_duplicates_<date>.csv).
"""
import argparse
import sys
from collections import Counter, defaultdict
from itertools import combinations

try:
    from scripts import report_common as rc
except ImportError:                       # run as py scripts\<name>.py
    import report_common as rc

import paths  # noqa: E402  (report_common has set sys.path)

TIERS = ("same iRecord id", "exact", "likely", "possible")
SAMPLES = 20
COLS = ("id", "irecord_id", "nbn_atlas_id", "occurrence_id", "source", "dataset_name",
        "species_name", "species_tvk", "date", "grid_ref", "site_name", "recorder")
HEADER = ["tier", "species_name", "species_tvk",
          "id_a", "id_b", "route_a", "route_b", "dataset_a", "dataset_b",
          "irecord_id_a", "irecord_id_b", "nbn_atlas_id_a", "nbn_atlas_id_b",
          "occurrence_id_a", "occurrence_id_b", "date_a", "date_b", "grid_ref_a", "grid_ref_b",
          "site_a", "site_b", "recorder_a", "recorder_b"]
_ROUTE_ORDER = {"iRecord": 0, "NBN Atlas": 1, "Other": 2}


def route(r: dict) -> str:
    """The import route, as the Scheme filter bar's Source (filter_builder.SCHEME_SOURCES)."""
    if not rc.blank(r["irecord_id"]):
        return "iRecord"
    if not rc.blank(r["nbn_atlas_id"]):
        return "NBN Atlas"
    return "Other"


def dataset(r: dict) -> str:
    return (r.get("dataset_name") or r.get("source") or "").strip()


def tier_for(a: dict, b: dict) -> str:
    """exact / likely / possible for two rows already sharing TVK, date and grid ref."""
    ra, rb = a["recorder"], b["recorder"]
    if not rc.blank(ra) and not rc.blank(rb):
        if rc.norm_text(ra) == rc.norm_text(rb):
            return "exact"
        return "likely" if rc.same_person(ra, rb) else "possible"
    if rc.blank(ra) != rc.blank(rb):
        return "likely"
    return "likely" if (route(a), dataset(a)) != (route(b), dataset(b)) else "possible"


def load(conn) -> list:
    have = {r[1] for r in conn.execute("PRAGMA table_info(recording_scheme)")}
    sel = ", ".join(c if c in have else f"NULL AS {c}" for c in COLS)
    conn.row_factory = None
    return [dict(zip(COLS, r)) for r in conn.execute(f"SELECT {sel} FROM recording_scheme")]


def find_pairs(rows: list) -> dict:
    """{(id_a, id_b): (tier, row_a, row_b)}, id_a/id_b ordered iRecord first, then by id."""
    pairs = {}

    def put(a, b, tier):
        if (_ROUTE_ORDER[route(b)], b["id"]) < (_ROUTE_ORDER[route(a)], a["id"]):
            a, b = b, a
        key = (a["id"], b["id"])
        if key not in pairs or TIERS.index(tier) < TIERS.index(pairs[key][0]):
            pairs[key] = (tier, a, b)

    by_irecord = {}
    for r in rows:
        if route(r) == "iRecord":
            by_irecord.setdefault(str(r["irecord_id"]).strip(), []).append(r)
    for r in rows:
        if route(r) != "NBN Atlas" or rc.blank(r["occurrence_id"]):
            continue
        for i in by_irecord.get(str(r["occurrence_id"]).strip(), ()):
            if i["species_tvk"] == r["species_tvk"] and i["date"] == r["date"]:
                put(i, r, "same iRecord id")

    groups = defaultdict(list)
    for r in rows:
        if rc.blank(r["species_tvk"]) or rc.blank(r["date"]) or rc.blank(r["grid_ref"]):
            continue
        groups[(r["species_tvk"], r["date"], rc.norm_ref(r["grid_ref"]))].append(r)
    for members in groups.values():
        for a, b in combinations(members, 2):
            put(a, b, tier_for(a, b))
    return pairs


def summarise(rows: list, pairs: dict) -> dict:
    s = {"rows": len(rows), "not_compared": sum(
        1 for r in rows if rc.blank(r["species_tvk"]) or rc.blank(r["date"])
        or rc.blank(r["grid_ref"])),
        "routes": Counter(route(r) for r in rows),
        "pairs": Counter(), "records": defaultdict(set), "routes_by_tier": defaultdict(Counter),
        "copies": Counter()}
    for (ia, ib), (tier, a, b) in pairs.items():
        s["pairs"][tier] += 1
        s["records"][tier].update((ia, ib))
        s["routes_by_tier"][tier][f"{route(a)} + {route(b)}"] += 1
    # cumulative: merge every pair at this tier or better into one find (union-find), and
    # count how many rows are copies (records in a cluster beyond its first)
    parent = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for tier in TIERS:
        for (ia, ib), (t, a, b) in pairs.items():
            if t == tier:
                ra, rb = find(ia), find(ib)
                if ra != rb:
                    parent[rb] = ra
        members = len(parent)
        clusters = len({find(x) for x in parent})
        s["copies"][tier] = members - clusters
    return s


def csv_rows(pairs: dict):
    for (ia, ib), (tier, a, b) in sorted(pairs.items(),
                                         key=lambda kv: (TIERS.index(kv[1][0]), kv[0])):
        yield [tier, a["species_name"], a["species_tvk"], ia, ib, route(a), route(b),
               dataset(a), dataset(b), a["irecord_id"], b["irecord_id"],
               a["nbn_atlas_id"], b["nbn_atlas_id"], a["occurrence_id"], b["occurrence_id"],
               a["date"], b["date"], a["grid_ref"], b["grid_ref"], a["site_name"],
               b["site_name"], a["recorder"], b["recorder"]]


def samples(pairs: dict, n: int = SAMPLES) -> list:
    """n pairs spread over the tiers (evenly spaced within each tier, so not all one species)."""
    by = defaultdict(list)
    for k, v in sorted(pairs.items()):
        by[v[0]].append(v)
    present = [t for t in TIERS if by[t]]
    out = []
    for i, t in enumerate(present):
        want = (n - len(out)) // (len(present) - i)
        items = by[t]
        step = max(1, len(items) // max(1, want))
        out += items[::step][:want]
    return out


def report(s: dict, pairs: dict) -> None:
    print(f"  scheme records: {s['rows']:,}  (" + ", ".join(
        f"{k} {v:,}" for k, v in s["routes"].most_common()) + ")")
    print(f"  not compared (no TVK, date or grid ref): {s['not_compared']:,}")
    print("")
    print(f"  {'tier':<16}{'pairs':>9}{'records in a pair':>19}{'extra copies (this tier and above)':>36}")
    for t in TIERS:
        print(f"  {t:<16}{s['pairs'][t]:>9,}{len(s['records'][t]):>19,}{s['copies'][t]:>36,}")
    print("  (extra copies = if every pair at that tier or a better one were one find, how many")
    print("   rows would be surplus: records in each set of copies beyond the first.)")
    for t in TIERS:
        if s["routes_by_tier"][t]:
            print(f"    {t}: " + ", ".join(f"{k} {v:,}" for k, v
                                           in s["routes_by_tier"][t].most_common()))
    print("")
    print(f"  {SAMPLES} sample pairs:")
    for tier, a, b in samples(pairs):
        print(f"    [{tier}] {str(a['species_name'] or '')[:28]:<28} {a['date']}  "
              f"id {a['id']} {route(a)} {str(a['grid_ref'])} '{a['recorder'] or ''}'  |  "
              f"id {b['id']} {route(b)} {str(b['grid_ref'])} '{b['recorder'] or ''}'"
              f"  ({dataset(b)[:40]})")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--csv", default=rc.default_csv("scheme_duplicates"))
    ap.add_argument("--db", default=str(paths.OBSERVATUM_DB), help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    print("")
    print("Recording Scheme -- records held twice (READ ONLY)")
    print("=" * 74)
    print(f"  observatum.db: {a.db}")
    conn = rc.connect_ro(a.db)
    try:
        rows = load(conn)
    finally:
        conn.close()
    pairs = find_pairs(rows)
    report(summarise(rows, pairs), pairs)
    n = rc.write_csv(a.csv, HEADER, csv_rows(pairs))
    print("")
    print(f"  CSV: {n:,} pairs -> {a.csv}")
    print("")
    print("READ ONLY. Nothing has been changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
