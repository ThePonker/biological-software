"""report_tvks_not_in_uksi.py -- records whose TVK is not in uksi.db, and the current UKSI
taxon each name matches (decision 4, Round 9 / Round 3, 11 Oct 2026). READ ONLY.

    py -3.14 scripts\\report_tvks_not_in_uksi.py
    py -3.14 scripts\\report_tvks_not_in_uksi.py --csv somewhere.csv

Why
---
The cleaning report lists about 42 records (7 TVKs, e.g. Forficula auricularia on
NHMSYS0021898013) under "TVK ... not found in UKSI": iRecord gave them keys newer than the
July 2025 UKSI extract that uksi.db is built from.

What it lists
-------------
For every table that holds records (observations, recording_scheme, specimens,
contributed_observations, where present): each stored species_tvk that is not a taxon in
uksi.db, with its record count per table and the names on those records. For each name, the
best current UKSI taxon, by shared/species_lookup.py (the import wizards' rule, no close
spellings):
    exact     the name is a current UKSI scientific name
    synonym   the name is a UKSI synonym of a current taxon
    no match  neither (an "agg." with no UKSI aggregate, "cf.", ambiguous, or unknown).
              Suggestions are listed -- UKSI's own candidates and any taxon whose preferred
              English name is the record's common name -- but never used.
"UKSI map" is where uksi.db's name_map / tvk_remap sends the TVK itself (the cleaning report
treats a TVK placed that way as found, so it may list fewer TVKs than this report).

Only exact and synonym matches are remapped, by
scripts\\_oneoff\\fix_tvks_not_in_uksi_20261011.py (dry run by default), which uses find()
below, so the two always agree.

CSV: scripts\\_oneoff\\tvks_not_in_uksi_<date>.csv, one row per table + TVK + name.

Second section (decision 5): "hybrids" with no hybrid in the name
-------------------------------------------------------------------
The cleaning report's Hybrid list holds a few plant records named just "Armeria",
"Dactylorhiza", "Helianthemum", "Rubus". They are not cut-short names: each is stored on
the GENUS TVK (UKSI rank Genus) but with taxon_rank "Species hybrid" (so it came from
iRecord). shared/record_kinds.classify lets the record's own rank win over the name (the
rule, for e.g. "Xanthogramma pedissequum" held on an s.l. TVK), so the stored rank makes
them hybrids. This section lists every record whose hybrid kind comes only from its stored
rank (the name has no " x " / "\u00d7"), with UKSI's name and rank for its TVK, for Wil to
fix by hand (in iRecord, then re-import -- or a later decision to set the rank from UKSI).
CSV: scripts\\_oneoff\\hybrid_by_rank_only_<date>.csv.
"""
import argparse
import sys
from collections import Counter, defaultdict

try:
    from scripts import report_common as rc
except ImportError:                       # run as py scripts\<name>.py
    import report_common as rc

import paths  # noqa: E402
from shared.species_filter import current_tvk_map  # noqa: E402
from shared.irecord_links import irecord_url  # noqa: E402
from shared.record_kinds import classify  # noqa: E402
from shared.species_lookup import NO_AGGREGATE, LookupFailure, lookup_names  # noqa: E402

TABLES = ("observations", "recording_scheme", "specimens", "contributed_observations")
REMAPPABLE = ("exact", "synonym")
HEADER = ["table", "tvk", "records", "species_name", "match", "new_tvk", "new_name",
          "new_rank", "new_family", "uksi_map_tvk", "uksi_map_name", "suggestions_not_used",
          "record_ids"]


def _cols(conn, table) -> set:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def tables_with_records(conn) -> list:
    have = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return [t for t in TABLES if t in have and {"species_tvk", "species_name"} <= _cols(conn, t)]


def _uksi_taxa(u, tvks) -> dict:
    """{tvk: (scientific_name, rank, family)} for the TVKs uksi.db holds as taxa."""
    out, tvks = {}, [t for t in dict.fromkeys(tvks) if t]
    for i in range(0, len(tvks), 900):
        part = tvks[i:i + 900]
        for tvk, name, rank, fam in u.execute(
                f"SELECT tvk, scientific_name, rank, family FROM taxa "
                f"WHERE tvk IN ({','.join('?' * len(part))})", part):
            out[tvk] = (name, rank, fam)
    return out


def _by_common_name(u, common: str) -> list:
    """Current taxa whose preferred English name is `common` (suggestions only)."""
    if not (common or "").strip():
        return []
    return [f"{n} {t} (English name)" for t, n in u.execute(
        "SELECT DISTINCT t.tvk, t.scientific_name FROM common_names c JOIN taxa t ON t.tvk = c.tvk "
        "WHERE LOWER(c.common_name) = LOWER(?) AND c.preferred IN (1, '1', 'Y', 'y', 'True') "
        "ORDER BY t.sort_code LIMIT 3", (common.strip(),))]


def match_name(name: str, hit, u) -> dict:
    """{'match', 'tvk', 'name', 'rank', 'family', 'suggestions'} for one stored name."""
    out = {"match": "no match", "tvk": "", "name": "", "rank": "", "family": "",
           "suggestions": []}
    if hit is None:
        return out
    if isinstance(hit, LookupFailure):
        out["suggestions"] = [f"{c.scientific_name} {c.tvk} ({c.rank})" for c in hit.candidates[:3]]
        if hit.kind == "ambiguous":
            out["match"] = "no match (more than one UKSI taxon)"
        return out
    if hit.how not in REMAPPABLE or hit.qualifier == "cf." or NO_AGGREGATE in hit.warnings:
        why = ("cf." if hit.qualifier == "cf." else "agg. with no UKSI aggregate"
               if NO_AGGREGATE in hit.warnings else hit.how)
        out["match"] = f"no match ({why})"
        out["suggestions"] = [f"{hit.taxon.scientific_name} {hit.taxon.tvk} ({hit.taxon.rank})"]
        return out
    t = hit.taxon
    out.update(match=hit.how, tvk=t.tvk, name=t.scientific_name, rank=t.rank or "",
               family=t.family or "")
    return out


def find(conn, uksi_path) -> dict:
    """Everything the report and the fix script need:
    {"tables": [...],
     "groups": [{"table", "tvk", "name", "records", "ids", "common", "match": match_name(),
                 "uksi_map": (tvk, name) or None}],     one per table + TVK + stored name
     "by_tvk": {tvk: Counter(table -> records)}}"""
    tables = tables_with_records(conn)
    rows = defaultdict(list)                    # (table, tvk, name) -> [(id, common)]
    for table in tables:
        common = "common_name" if "common_name" in _cols(conn, table) else "NULL"
        for rid, tvk, name, cn in conn.execute(
                f"SELECT id, species_tvk, species_name, {common} FROM {table} "
                f"WHERE COALESCE(TRIM(species_tvk), '') != '' ORDER BY id"):
            rows[(table, tvk.strip(), name or "")].append((rid, cn or ""))
    u = rc.connect_ro(uksi_path)
    try:
        known = _uksi_taxa(u, {k[1] for k in rows})
        missing = sorted({k[1] for k in rows} - set(known))
        keys = [k for k in rows if k[1] in missing]
        mapped = current_tvk_map(missing, str(uksi_path)) if missing else {}
        map_names = _uksi_taxa(u, [v for v in mapped.values() if v])
        hits = lookup_names([k[2] for k in keys], u) if keys else {}
        groups = []
        for table, tvk, name in sorted(keys, key=lambda k: (k[1], k[0], k[2].lower())):
            items = rows[(table, tvk, name)]
            m = match_name(name, hits.get(name), u)
            commons = sorted({cn for _, cn in items if cn})
            if m["match"] not in REMAPPABLE:
                for cn in commons:
                    seen = " ".join(m["suggestions"])          # one line per taxon
                    m["suggestions"] += [s for s in _by_common_name(u, cn)
                                         if s.split(" (")[0].split()[-1] not in seen]
            cur = mapped.get(tvk)
            groups.append({"table": table, "tvk": tvk, "name": name, "records": len(items),
                           "ids": [rid for rid, _ in items], "common": ", ".join(commons),
                           "match": m,
                           "uksi_map": (cur, map_names.get(cur, ("",))[0]) if cur else None})
    finally:
        u.close()
    by_tvk = defaultdict(Counter)
    for g in groups:
        by_tvk[g["tvk"]][g["table"]] += g["records"]
    return {"tables": tables, "groups": groups, "by_tvk": by_tvk}


def csv_rows(found):
    for g in found["groups"]:
        m, um = g["match"], g["uksi_map"] or ("", "")
        yield [g["table"], g["tvk"], g["records"], g["name"], m["match"], m["tvk"], m["name"],
               m["rank"], m["family"], um[0], um[1], "; ".join(m["suggestions"]),
               " ".join(str(i) for i in g["ids"])]


def report(found) -> None:
    print(f"  tables checked: {', '.join(found['tables'])}")
    groups = found["groups"]
    if not groups:
        print("  every stored TVK is a taxon in uksi.db")
        return
    print("")
    print(f"  {len(found['by_tvk'])} TVKs not in uksi.db, on "
          f"{sum(g['records'] for g in groups):,} records")
    for tvk, per in found["by_tvk"].items():
        print("")
        print(f"  {tvk}   " + ", ".join(f"{t} {n:,}" for t, n in per.items()))
        um = next((g["uksi_map"] for g in groups if g["tvk"] == tvk and g["uksi_map"]), None)
        if um:
            print(f"      UKSI map: {um[0]} {um[1]}  (the cleaning report counts this TVK as found)")
        for g in (g for g in groups if g["tvk"] == tvk):
            m = g["match"]
            target = f"-> {m['name']} {m['tvk']} [{m['family']}]" if m["tvk"] else ""
            print(f"      {g['records']:>4}  {g['name'][:40]:<40} {m['match']:<9} {target}")
            if m["suggestions"]:
                print(f"            suggestions (not used): {'; '.join(m['suggestions'])}")
    by = Counter()
    for g in groups:
        by["remap" if g["match"]["match"] in REMAPPABLE else "no match"] += g["records"]
    print("")
    print(f"  records an exact or synonym match would remap: {by['remap']:,}   "
          f"no match (for Wil): {by['no match']:,}")
    print("  remap them with: py -3.14 scripts\\_oneoff\\fix_tvks_not_in_uksi_20261011.py   (dry run)")


# ------------------------------------------------------------------ decision 5

HYBRID_HEADER = ["table", "id", "species_name", "taxon_rank", "species_tvk", "uksi_name",
                 "uksi_rank", "source", "dataset_name", "import_notes", "date", "site_name",
                 "irecord_id", "irecord_link"]


def hybrids_by_rank_only(conn, uksi_path) -> list:
    """[dict] records the cleaning report calls hybrids only because of their stored rank:
    classify(name, rank) has 'hybrid', classify(name) alone does not."""
    out = []
    for table in tables_with_records(conn):
        cols = _cols(conn, table)
        if "taxon_rank" not in cols:
            continue
        want = ["id", "species_name", "taxon_rank", "species_tvk", "source", "dataset_name",
                "import_notes", "date", "site_name", "irecord_id"]
        sel = ", ".join(c if c in cols else f"NULL AS {c}" for c in want)
        for r in conn.execute(f"SELECT {sel} FROM {table} "
                              "WHERE LOWER(TRIM(COALESCE(taxon_rank, ''))) LIKE '%hybrid%'"):
            d = dict(zip(want, r))
            if "hybrid" in classify(d["species_name"], d["taxon_rank"]) and \
                    "hybrid" not in classify(d["species_name"]):
                d["table"] = table
                out.append(d)
    if out:
        u = rc.connect_ro(uksi_path)
        try:
            taxa = _uksi_taxa(u, {d["species_tvk"] for d in out})
        finally:
            u.close()
        for d in out:
            name, rank, _fam = taxa.get(d["species_tvk"], ("", "", ""))
            d["uksi_name"], d["uksi_rank"] = name, rank
    out.sort(key=lambda d: (d["table"], (d["species_name"] or "").lower(), d["id"]))
    return out


def hybrid_rows(items):
    for d in items:
        yield [d["table"], d["id"], d["species_name"], d["taxon_rank"], d["species_tvk"],
               d["uksi_name"], d["uksi_rank"], d["source"], d["dataset_name"],
               d["import_notes"], d["date"], d["site_name"], d["irecord_id"],
               irecord_url(d["irecord_id"]) or ""]


def report_hybrids(items) -> None:
    print("")
    print("Decision 5 -- 'hybrids' whose name has no hybrid in it (stored rank only)")
    print("-" * 74)
    if not items:
        print("  none")
        return
    for d in items:
        print(f"  {d['table']:<13} id {d['id']:<7} {str(d['species_name'])[:22]:<22} "
              f"rank {d['taxon_rank']!r:<17} {d['species_tvk']} = UKSI {d['uksi_name']} "
              f"({d['uksi_rank'] or 'not in UKSI'})")
        print(f"      {d['date'] or ''}  {str(d['site_name'] or '')[:40]}  "
              f"[{d['source'] or d['dataset_name'] or ''}]  iRecord {d['irecord_id'] or '-'}"
              + (f"  notes: {d['import_notes']}" if d["import_notes"] else ""))
    print(f"  {len(items)} record{'s' if len(items) != 1 else ''}: the name is the genus and so "
          "is the TVK; only the stored rank says hybrid.")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--csv", default=rc.default_csv("tvks_not_in_uksi"))
    ap.add_argument("--hybrids-csv", default=rc.default_csv("hybrid_by_rank_only"))
    ap.add_argument("--db", default=str(paths.OBSERVATUM_DB), help=argparse.SUPPRESS)
    ap.add_argument("--uksi", default=str(paths.UKSI_DB), help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    print("")
    print("Records whose TVK is not in uksi.db (READ ONLY)")
    print("=" * 74)
    print(f"  observatum.db: {a.db}")
    print(f"  uksi.db:       {a.uksi}")
    conn = rc.connect_ro(a.db)
    try:
        found = find(conn, a.uksi)
        hybrids = hybrids_by_rank_only(conn, a.uksi)
    finally:
        conn.close()
    report(found)
    n = rc.write_csv(a.csv, HEADER, csv_rows(found))
    print("")
    print(f"  CSV: {n:,} rows -> {a.csv}")
    report_hybrids(hybrids)
    n = rc.write_csv(a.hybrids_csv, HYBRID_HEADER, hybrid_rows(hybrids))
    print("")
    print(f"  CSV: {n:,} rows -> {a.hybrids_csv}")
    print("")
    print("READ ONLY. Nothing has been changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
