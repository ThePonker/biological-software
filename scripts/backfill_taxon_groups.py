"""backfill_taxon_groups.py -- fill blank taxon groups (and the other blank UKSI taxonomy) on
observations, recording_scheme and specimens, from UKSI by each record's TVK (backlog item 3,
review SRCH14 / MAP10 / OBS-11, 10 Oct 2026).

    py -3.14 scripts\\backfill_taxon_groups.py                 # dry run: report, change nothing
    py -3.14 scripts\\backfill_taxon_groups.py --apply         # fill blanks, after a backup
    py -3.14 scripts\\backfill_taxon_groups.py --apply --relabel   # also correct OUR old labels

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

The dry run shows, per table and column, how many blanks it fills and how many values are
already there (kept), with 5 sample records before -> after. Sort keys that are not our
number (order position x 1,000,000 + UKSI sort code) -- e.g. 41 iRecord-era UKSI
sort_order strings on observations -- are counted and left alone: a decision for Wil.
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


def plan(conn, uksi_path) -> dict:
    """What a backfill would do, per table:
    {table: {"rows": n, "fill": {col: [(id, new, tvk)]}, "relabel": [(id, old, new)],
             "differ": Counter((order, stored, ours)) on labels that came with the record,
             "not_in_uksi": n, "no_tvk": n, "kept": {col: n already filled},
             "samples": {col: [(id, name, before, after)]} (first SAMPLES fills),
             "odd_keys": [(id, name, key)] sort keys not in our number format}}"""
    out = {}
    for table in TABLES:
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        if "species_tvk" not in cols:
            continue
        fill_cols = [c for c in FILL_COLUMNS if c in cols]
        src = "source" if "source" in cols else "NULL"
        name = "species_name" if "species_name" in cols else "NULL"
        rows = conn.execute(
            f"SELECT id, species_tvk, {src}, order_name, {name}, {', '.join(fill_cols)} "
            f"FROM {table}").fetchall()
        tax = taxonomy_for_tvks({r[1] for r in rows if not _blank(r[1])}, uksi_path)
        t = {"rows": len(rows), "fill": {c: [] for c in fill_cols}, "relabel": [],
             "differ": Counter(), "not_in_uksi": 0, "no_tvk": 0,
             "kept": Counter(), "samples": {c: [] for c in fill_cols}, "odd_keys": []}
        for r in rows:
            rid, tvk, source, order, sp = r[0], r[1], r[2], r[3], r[4]
            stored = dict(zip(fill_cols, r[5:]))
            for c in fill_cols:
                if not _blank(stored[c]):
                    t["kept"][c] += 1
            key = stored.get("taxonomic_sort_key")
            if not _blank(key) and not _is_our_key(key):
                t["odd_keys"].append((rid, sp, key))
            if _blank(tvk):
                t["no_tvk"] += 1
                continue
            x = tax.get(tvk)
            if x is None:
                t["not_in_uksi"] += 1
                continue
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


def report(found) -> None:
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
            print(f"  taxonomic_sort_key values not in our number format: {len(t['odd_keys']):,} "
                  f"(left as they are -- a decision for Wil; they sort after every number)")
            for rid, sp, key in t["odd_keys"][:SAMPLES]:
                print(f"      e.g. id {rid:<7} {str(sp or '')[:34]:<34} {key!r}")
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


def apply(conn, found, relabel: bool = False) -> dict:
    """Write the plan in one transaction; returns {table: {col: rows changed}}."""
    done = defaultdict(Counter)
    with conn:
        for table, t in found.items():
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
    ap.add_argument("--db", default=str(paths.OBSERVATUM_DB), help=argparse.SUPPRESS)
    ap.add_argument("--uksi", default=str(paths.UKSI_DB), help=argparse.SUPPRESS)
    ap.add_argument("--backup-dir", default=BACKUP_DIR, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)

    print("")
    print("Taxon groups and UKSI taxonomy -- blanks filled from UKSI by TVK")
    print("=" * 74)
    print(f"  observatum.db: {a.db}")
    print(f"  uksi.db:       {a.uksi}")
    ro = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    try:
        found = plan(ro, a.uksi)
    finally:
        ro.close()
    report(found)
    total = sum(len(v) for t in found.values() for v in t["fill"].values())
    relabels = sum(len(t["relabel"]) for t in found.values())
    print("")
    print(f"  in all: {total:,} blank values to fill; {relabels:,} of our own labels to correct "
          f"(--relabel)")

    if not a.apply:
        print("")
        print("DRY RUN. Nothing has been changed. Run with --apply to write.")
        return 0
    if not total and not (a.relabel and relabels):
        print("  nothing to do. Nothing has been changed.")
        return 0
    print("")
    dest = backup(a.db, a.backup_dir)
    print(f"  backed up to {dest}")
    conn = sqlite3.connect(a.db)
    try:
        done = apply(conn, found, relabel=a.relabel)
    finally:
        conn.close()
    for table, cols in done.items():
        print(f"  {table}: " + ", ".join(f"{c} {n:,}" for c, n in cols.items()))
    print("  done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
