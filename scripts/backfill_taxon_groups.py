"""backfill_taxon_groups.py -- fill blank taxon groups (and the other blank UKSI taxonomy) on
observations, recording_scheme and specimens, from UKSI by each record's TVK (backlog item 3,
review SRCH14 / MAP10 / OBS-11, 10 Oct 2026).

    py -3.14 scripts\\backfill_taxon_groups.py                 # dry run: report, change nothing
    py -3.14 scripts\\backfill_taxon_groups.py --apply         # fill blanks, after a backup
    py -3.14 scripts\\backfill_taxon_groups.py --apply --relabel   # also correct OUR old labels

    Only correct our wrong labels, fill nothing (Q63, 12 Oct: the 42 butterflies filed as
    "insect - moth"; --tables observations keeps it to those):
    py -3.14 scripts\\backfill_taxon_groups.py --relabel-only --tables observations
    py -3.14 scripts\\backfill_taxon_groups.py --relabel-only --tables observations --apply

    Only some tables / columns (decision 8, 11 Oct: kingdom and taxon group on observations):
    py -3.14 scripts\\backfill_taxon_groups.py --tables observations --columns kingdom,taxon_group
    py -3.14 scripts\\backfill_taxon_groups.py --tables observations --columns kingdom,taxon_group --apply

    Only rewrite sort keys not in our number format (the old UKSI sort_order strings, e.g.
    '000204010603030I02...' on Isoaeschna isoceles ids 10743-4; 13 Oct, Round 10 C4):
    py -3.14 scripts\\backfill_taxon_groups.py --fix-odd-keys
    py -3.14 scripts\\backfill_taxon_groups.py --fix-odd-keys --apply

Why
---
`taxon_group` was blank on 1,440 observations (every Data Entry commit until 9 Oct), 430
specimens and 68% of scheme rows, so the Stats group curves under-counted (Commercial Beetles
552 against Coleoptera 651) and nothing could filter or map by group. The rule is
shared/taxon_groups.py, the same one the import wizards, Data Entry and Quick Entry now use.

What it writes
--------------
- Blanks only (NULL or empty), and only where UKSI gives a value: taxon_group, kingdom,
  taxon_rank, superfamily, taxonomic_sort_key -- each where the table has the column. This
  is what the 9 Oct one-off (scripts/_oneoff/backfill_taxonomy_20261009.py) did for
  observations; on a database that already ran it, the observation counts will be small.
  The sort key is the import wizards' formula (shared.import_core); only a NULL key is
  filled -- unlike backfill_sort_keys.py --apply, no existing key is ever rewritten.
- A label already on a record is never changed, except with --relabel: then labels WE wrote
  that disagree with the rule (butterflies filed as 'insect - moth' by the old wizard map,
  specimens filed as plain 'insect') are corrected. Records from iRecord or from a scheme
  source keep their label whatever it says; where it differs from ours it is only listed.
  "Ours" = specimens, and observations with no `source` (wizard imports, Data Entry,
  Quick Entry); scheme rows are never relabelled.

--apply backs observatum.db up first with SQLite's backup API, then writes in one
transaction, each UPDATE guarded so it only touches a value that is still blank (or, for a
relabel, still the old label).

For the records with no kingdom or no taxon group, the dry run also shows what they get, by
kingdom and group, and how many cannot be resolved and why (no TVK, TVK not in UKSI, UKSI
gives no kingdom / no group for the TVK). --tables / --columns narrow what is written (and
--relabel needs taxon_group among the columns).

The dry run shows, per table and column, how many blanks it fills and how many values are
already there (kept), with 5 sample records before -> after. Sort keys that are not our
number (order position x 1,000,000 + UKSI sort code) -- e.g. 41 iRecord-era UKSI
sort_order strings on observations -- are counted and left alone, as they sort after every
number. --fix-odd-keys lists each one (id, name, old key -> new key from UKSI for the TVK)
and, with --apply, rewrites just those (nothing else is filled); one whose TVK is not in
UKSI is listed and left.
"""
import argparse
import os
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_ROOT, os.path.join(_ROOT, "Observatum")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import paths  # noqa: E402
from shared.taxon_groups import taxonomy_for_tvks  # noqa: E402

TABLES = ("observations", "recording_scheme", "specimens")
FILL_COLUMNS = ("taxon_group", "kingdom", "taxon_rank", "superfamily", "taxonomic_sort_key")
SAMPLES = 5
BACKUP_DIR = os.path.join(r"C:\BiologicalSoftware_Backups", "reference")


def _blank(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def _ours(table: str, source) -> bool:
    """A label this suite wrote (relabel allowed), not one that came with the record."""
    if table == "specimens":
        return True
    if table == "observations":
        return _blank(source)
    return False


def _is_our_key(v) -> bool:
    """Our sort key: a whole number (order position x 1,000,000 + UKSI sort code)."""
    if isinstance(v, int):
        return True
    return isinstance(v, str) and v.strip().isdigit() and len(v.strip()) <= 9


def _current_tvks(uksi_path, tvks) -> dict:
    """{old tvk: current tvk} through uksi.db's name_map / tvk_remap, for TVKs not in taxa
    (an odd key on a record whose TVK is a superseded one: the key comes from the current
    taxon; the record's own TVK is not changed here -- that is remap_record_tvks.py)."""
    tvks = [t for t in tvks if t]
    if not tvks:
        return {}
    from shared.db_open import connect_ro
    u = connect_ro(uksi_path)
    try:
        tables = {r[0] for r in u.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        ph = ",".join("?" * len(tvks))
        found = {}
        if "name_map" in tables:
            found = dict(u.execute(
                f"SELECT tvk, recommended_tvk FROM name_map WHERE tvk IN ({ph}) "
                f"AND recommended_tvk IS NOT NULL AND recommended_tvk <> tvk", tvks))
        if "tvk_remap" in tables:
            for o, n in u.execute(f"SELECT old_tvk, new_tvk FROM tvk_remap WHERE old_tvk IN ({ph}) "
                                  f"AND new_tvk IS NOT NULL", tvks):
                found.setdefault(o, n)
        return found
    finally:
        u.close()


def plan(conn, uksi_path, tables=TABLES, columns=FILL_COLUMNS) -> dict:
    """What a backfill would do, per table:
    {table: {"rows": n, "fill": {col: [(id, new, tvk)]}, "relabel": [(id, old, new)],
             "differ": Counter((order, stored, ours)) on labels that came with the record,
             "not_in_uksi": n, "no_tvk": n, "kept": {col: n already filled},
             "samples": {col: [(id, name, before, after)]} (first SAMPLES fills),
             "odd_keys": [(id, name, key, new, via)] sort keys not in our number format and
                         the UKSI key for the TVK (None when it cannot be resolved); via is
                         the current TVK when the record's is a superseded one, else None,
             "kg": {"rows": n with no kingdom or no taxon group, "fills": Counter((kingdom,
                    group)) they would get, "unresolved": Counter(reason)}}}"""
    out = {}
    for table in tables:
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        if "species_tvk" not in cols:
            continue
        fill_cols = [c for c in FILL_COLUMNS if c in cols and c in columns]
        kg_cols = [c for c in ("kingdom", "taxon_group") if c in cols and c in columns]
        if not fill_cols:
            continue
        src = "source" if "source" in cols else "NULL"
        name = "species_name" if "species_name" in cols else "NULL"
        rows = conn.execute(
            f"SELECT id, species_tvk, {src}, order_name, {name}, {', '.join(fill_cols)} "
            f"FROM {table}").fetchall()
        tax = taxonomy_for_tvks({r[1] for r in rows if not _blank(r[1])}, uksi_path)
        odd_tvks = {r[1] for r in rows if not _blank(r[1]) and r[1] not in tax
                    and "taxonomic_sort_key" in fill_cols
                    and not _blank(r[5 + fill_cols.index("taxonomic_sort_key")])
                    and not _is_our_key(r[5 + fill_cols.index("taxonomic_sort_key")])}
        via = _current_tvks(uksi_path, odd_tvks)
        via_tax = taxonomy_for_tvks(set(via.values()), uksi_path)
        t = {"rows": len(rows), "fill": {c: [] for c in fill_cols}, "relabel": [],
             "differ": Counter(), "not_in_uksi": 0, "no_tvk": 0,
             "kept": Counter(), "samples": {c: [] for c in fill_cols}, "odd_keys": [],
             "kg": {"rows": 0, "fills": Counter(), "unresolved": Counter()}}
        for r in rows:
            rid, tvk, source, order, sp = r[0], r[1], r[2], r[3], r[4]
            stored = dict(zip(fill_cols, r[5:]))
            for c in fill_cols:
                if not _blank(stored[c]):
                    t["kept"][c] += 1
            key = stored.get("taxonomic_sort_key")
            if not _blank(key) and not _is_our_key(key):
                new, cur = None, None
                if not _blank(tvk):
                    cur = via.get(tvk) if tvk not in tax else None
                    new = (tax.get(tvk) or via_tax.get(cur) or {}).get("taxonomic_sort_key")
                t["odd_keys"].append((rid, sp, key, new if _is_our_key(new) else None, cur))
            kg_blank = [c for c in kg_cols if _blank(stored[c])]
            if kg_blank:
                t["kg"]["rows"] += 1
            if _blank(tvk):
                t["no_tvk"] += 1
                if kg_blank:
                    t["kg"]["unresolved"]["no TVK"] += 1
                continue
            x = tax.get(tvk)
            if x is None:
                t["not_in_uksi"] += 1
                if kg_blank:
                    t["kg"]["unresolved"]["TVK not in UKSI"] += 1
                continue
            if kg_blank:                         # each record counted once
                missing = [c.replace("_", " ") for c in kg_blank if _blank(x.get(c))]
                if missing:
                    t["kg"]["unresolved"][f"UKSI gives no {' or '.join(missing)} for the TVK"
                                          + (" (the rest is filled)" if len(missing) < len(kg_blank)
                                             else "")] += 1
                else:
                    t["kg"]["fills"][tuple(
                        (x.get(c) if c in kg_blank else stored[c]) or "(none)"
                        for c in ("kingdom", "taxon_group") if c in kg_cols)] += 1
            for c in fill_cols:
                if _blank(stored[c]) and not _blank(x.get(c)):
                    t["fill"][c].append((rid, x[c], tvk))
                    if len(t["samples"][c]) < SAMPLES:
                        t["samples"][c].append((rid, sp, stored[c], x[c]))
            old, new = stored.get("taxon_group"), x.get("taxon_group")
            if "taxon_group" in stored and not _blank(old) and new and old.strip() != new:
                if _ours(table, source):
                    t["relabel"].append((rid, old, new))
                else:
                    t["differ"][(order or "", old, new)] += 1
        out[table] = t
    return out


def report(found, odd_keys_all: bool = False) -> None:
    for table, t in found.items():
        print("")
        print(f"{table}: {t['rows']:,} records  (no TVK {t['no_tvk']:,}; TVK not in UKSI "
              f"{t['not_in_uksi']:,} -- left as they are)")
        print("  per column: blanks this fills / values already there (never changed)")
        for c, items in t["fill"].items():
            print(f"  {c:<20} fill {len(items):>7,}   kept {t['kept'][c]:>7,}")
            for rid, sp, before, after in t["samples"][c]:
                print(f"      e.g. id {rid:<7} {str(sp or '')[:34]:<34} "
                      f"{'NULL' if before is None else repr(before)} -> {after!r}")
        if t["odd_keys"]:
            fixable = sum(1 for *_, new, _cur in t["odd_keys"] if new is not None)
            print(f"  taxonomic_sort_key values not in our number format: {len(t['odd_keys']):,} "
                  f"(they sort after every number; {fixable:,} can be rewritten from UKSI"
                  + (")" if odd_keys_all else " with --fix-odd-keys)"))
            for rid, sp, key, new, cur in (t["odd_keys"] if odd_keys_all
                                           else t["odd_keys"][:SAMPLES]):
                print(f"      {'' if odd_keys_all else 'e.g. '}id {rid:<7} {str(sp or '')[:34]:<34} "
                      f"{key!r} -> {new if new is not None else '(TVK not in UKSI: left)'}"
                      + (f"  (superseded TVK; key of the current taxon {cur})" if cur else ""))
        kg = t["kg"]
        if kg["rows"]:
            print(f"  records with no kingdom or no taxon group: {kg['rows']:,}")
            for key, n in sorted(kg["fills"].items(), key=lambda kv: (-kv[1], kv[0])):
                print(f"    {n:>7,}  get  {' / '.join(key)}")
            if kg["unresolved"]:
                for why, n in kg["unresolved"].most_common():
                    print(f"    {n:>7,}  cannot be resolved: {why}")
            else:
                print("    every one of them can be resolved")
        groups = Counter(new for _, new, _ in t["fill"].get("taxon_group", []))
        if groups:
            print("  taxon_group fills by group:")
            for g, n in groups.most_common():
                print(f"    {n:>7,}  {g}")
        if t["relabel"]:
            print(f"  our own labels that disagree with the rule (changed only with --relabel): "
                  f"{len(t['relabel']):,}")
            for (old, new), n in Counter((o, nw) for _, o, nw in t["relabel"]).most_common():
                print(f"    {n:>7,}  '{old}' -> '{new}'")
        if t["differ"]:
            print("  labels that came with the record and differ from ours (never changed; "
                  "for review):")
            for (order, old, new), n in t["differ"].most_common():
                print(f"    {n:>7,}  {order or '(no order)'}: '{old}' (ours '{new}')")


def backup(db_path, backup_dir=BACKUP_DIR) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    dest = os.path.join(backup_dir, f"observatum_pre_backfill_taxon_groups_{stamp}.db")
    os.makedirs(backup_dir, exist_ok=True)
    if os.path.exists(dest):                     # never overwrite an earlier backup
        raise FileExistsError(f"backup already exists: {dest}")
    src = sqlite3.connect(str(db_path))
    d = sqlite3.connect(dest)
    try:
        src.backup(d)                            # online backup API -- safe on a WAL database
    finally:
        d.close()
        src.close()
    return dest


def apply(conn, found, relabel: bool = False, fix_odd_keys: bool = False) -> dict:
    """Write the plan in one transaction; returns {table: {col: rows changed}}."""
    done = defaultdict(Counter)
    with conn:
        for table, t in found.items():
            if fix_odd_keys:
                for rid, _, old, new, _cur in t["odd_keys"]:
                    if new is not None:              # guarded: still the odd key
                        done[table]["odd_keys"] += conn.execute(
                            f"UPDATE {table} SET taxonomic_sort_key = ? WHERE id = ? "
                            f"AND taxonomic_sort_key = ?", (new, rid, old)).rowcount
            for c, items in t["fill"].items():
                guard = f"({c} IS NULL OR TRIM({c}) = '')"     # still blank
                for rid, new, _ in items:
                    done[table][c] += conn.execute(
                        f"UPDATE {table} SET {c} = ? WHERE id = ? AND {guard}", (new, rid)).rowcount
            if relabel:
                for rid, old, new in t["relabel"]:
                    done[table]["relabel"] += conn.execute(
                        f"UPDATE {table} SET taxon_group = ? WHERE id = ? AND taxon_group = ?",
                        (new, rid, old)).rowcount
    return done


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true", help="write (after a backup)")
    ap.add_argument("--relabel", action="store_true",
                    help="with --apply: also correct labels this suite wrote that disagree")
    ap.add_argument("--relabel-only", action="store_true",
                    help="correct labels this suite wrote that disagree; fill no blanks")
    ap.add_argument("--fix-odd-keys", action="store_true",
                    help="rewrite sort keys not in our number format from UKSI; fill no blanks")
    ap.add_argument("--tables", default=",".join(TABLES),
                    help=f"comma-separated, from {', '.join(TABLES)} (default all)")
    ap.add_argument("--columns", default=",".join(FILL_COLUMNS),
                    help=f"comma-separated, from {', '.join(FILL_COLUMNS)} (default all)")
    ap.add_argument("--db", default=str(paths.OBSERVATUM_DB), help=argparse.SUPPRESS)
    ap.add_argument("--uksi", default=str(paths.UKSI_DB), help=argparse.SUPPRESS)
    ap.add_argument("--backup-dir", default=BACKUP_DIR, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    tables = [t.strip() for t in a.tables.split(",") if t.strip()]
    columns = [c.strip() for c in a.columns.split(",") if c.strip()]
    bad = [t for t in tables if t not in TABLES] + [c for c in columns if c not in FILL_COLUMNS]
    if bad or not tables or not columns:
        ap.error(f"unknown or missing table / column: {', '.join(bad) or '(none given)'}")
    if a.relabel_only:
        a.relabel = True
    if a.relabel and "taxon_group" not in columns:
        ap.error("--relabel needs taxon_group among --columns")

    print("")
    print("Taxon groups and UKSI taxonomy -- blanks filled from UKSI by TVK")
    print("=" * 74)
    print(f"  observatum.db: {a.db}")
    print(f"  uksi.db:       {a.uksi}")
    if tables != list(TABLES) or columns != list(FILL_COLUMNS):
        print(f"  only tables:   {', '.join(tables)}")
        print(f"  only columns:  {', '.join(columns)}")
    ro = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    try:
        found = plan(ro, a.uksi, tables, columns)
    finally:
        ro.close()
    if a.relabel_only or a.fix_odd_keys:     # labels / keys only: no blank is filled
        for t in found.values():
            t["fill"] = {c: [] for c in t["fill"]}
            t["samples"] = {c: [] for c in t["samples"]}
            t["kg"] = {"rows": 0, "fills": Counter(), "unresolved": Counter()}
            if a.fix_odd_keys:
                t["relabel"] = []
    if a.relabel_only:
        print("  --relabel-only: our own wrong labels are corrected; no blank is filled")
    if a.fix_odd_keys:
        print("  --fix-odd-keys: only sort keys not in our number format are rewritten")
    report(found, odd_keys_all=a.fix_odd_keys)
    total = sum(len(v) for t in found.values() for v in t["fill"].values())
    relabels = sum(len(t["relabel"]) for t in found.values())
    odd = sum(1 for t in found.values() for *_, new, _cur in t["odd_keys"] if new is not None)
    print("")
    if a.fix_odd_keys:
        print(f"  in all: {odd:,} odd sort keys to rewrite")
    else:
        print(f"  in all: {total:,} blank values to fill; {relabels:,} of our own labels to "
              f"correct (--relabel)")

    if not a.apply:
        print("")
        print("DRY RUN. Nothing has been changed. Run with --apply to write.")
        return 0
    if not total and not (a.relabel and relabels) and not (a.fix_odd_keys and odd):
        print("  nothing to do. Nothing has been changed.")
        return 0
    print("")
    dest = backup(a.db, a.backup_dir)
    print(f"  backed up to {dest}")
    conn = sqlite3.connect(a.db)
    try:
        done = apply(conn, found, relabel=a.relabel, fix_odd_keys=a.fix_odd_keys)
    finally:
        conn.close()
    for table, cols in done.items():
        print(f"  {table}: " + ", ".join(f"{c} {n:,}" for c, n in cols.items()))
    print("  done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
