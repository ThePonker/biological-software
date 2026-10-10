"""add_filter_indexes.py -- indexes that make Observatum's slow queries fast (speed review,
10 Oct 2026). Indexes change no data and no figure: only how SQLite finds rows.

    py -3.14 scripts\\add_filter_indexes.py            # dry run: what it would add, timed
    py -3.14 scripts\\add_filter_indexes.py --apply    # add them, after a backup

What was measured
-----------------
The record tabs' filter queries were checked with EXPLAIN QUERY PLAN: they already use the
indexes observatum.db has (species, TVK, date, VC, family on each table), and the species /
location / recorder boxes match text inside names (LIKE '%...%'), which no index can serve.
So no index is needed for filtering -- the filter slowness was in the program (fixed there).

One query is slow for want of an index: the Recording Scheme statistics' "county firsts"
(services/recording_scheme_stats_service.py) joins every first record back to the records
of its vice-county -- about 5 s each time Stats > Recording Scheme is opened or refreshed.
An index on (species_tvk, vc_number, date) makes it a direct look-up.

The dry run copies observatum.db into memory (nothing is written anywhere), adds the
indexes to that copy, times the query before and after, checks the results are identical
row for row, and prints "Nothing has been changed". --apply backs observatum.db up with
SQLite's backup API, then runs CREATE INDEX IF NOT EXISTS. Close Observatum first.
"""
import argparse
import os
import re
import sqlite3
import sys
import time
from datetime import datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_ROOT, os.path.join(_ROOT, "Observatum")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import paths  # noqa: E402

BACKUP_DIR = os.path.join(r"C:\BiologicalSoftware_Backups", "reference")
STATS_SERVICE = os.path.join(_ROOT, "Observatum", "src", "services",
                             "recording_scheme_stats_service.py")

# (name, table, columns, why)
INDEXES = [
    ("idx_scheme_tvk_vc_date", "recording_scheme", ("species_tvk", "vc_number", "date"),
     "Stats > Recording Scheme: county firsts"),
]


def create_sql(name, table, cols) -> str:
    return f"CREATE INDEX IF NOT EXISTS {name} ON {table}({', '.join(cols)})"


def county_firsts_query() -> str:
    """The county-firsts query exactly as the stats service runs it (no exclusions set)."""
    with open(STATS_SERVICE, encoding="utf-8") as f:
        src = f.read()
    m = re.search(r'county_firsts_query = f"""(.*?)"""', src, re.S)
    if not m:
        raise RuntimeError("county firsts query not found in recording_scheme_stats_service.py")
    return m.group(1).replace("{exclusion}{family_clause}", "")


def existing_indexes(conn) -> dict:
    return {r[0]: r[1] for r in conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type = 'index' AND sql IS NOT NULL")}


def timed(conn, sql, repeat=1):
    best, rows = None, None
    for _ in range(repeat):
        t = time.perf_counter()
        rows = conn.execute(sql).fetchall()
        d = time.perf_counter() - t
        best = d if best is None else min(best, d)
    return best, rows


def dry_run(db_path) -> list:
    """Time the slow query on an in-memory copy, before and after; returns the indexes
    still to add."""
    src = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        have = existing_indexes(src)
        mem = sqlite3.connect(":memory:")
        src.backup(mem)
    finally:
        src.close()
    todo = [ix for ix in INDEXES if ix[0] not in have]
    print("")
    print("Indexes")
    for name, table, cols, why in INDEXES:
        state = "already there" if name in have else "to add"
        print(f"  {create_sql(name, table, cols)};")
        print(f"      for: {why}  ({state})")
    if not todo:
        return todo
    q = county_firsts_query()
    print("")
    print("Measured on an in-memory copy of observatum.db")
    before, rows_before = timed(mem, q)
    for name, table, cols, _ in todo:
        mem.execute(create_sql(name, table, cols))
    after, rows_after = timed(mem, q, repeat=3)
    plan = [r[3] for r in mem.execute("EXPLAIN QUERY PLAN " + q)]
    print(f"  county firsts: {before:.2f} s before, {after:.3f} s after "
          f"({len(rows_after)} rows; identical to before: {rows_before == rows_after})")
    print("  plan after: " + "; ".join(plan))
    mem.close()
    return todo


def backup(db_path, backup_dir=BACKUP_DIR) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    dest = os.path.join(backup_dir, f"observatum_pre_add_filter_indexes_{stamp}.db")
    os.makedirs(backup_dir, exist_ok=True)
    if os.path.exists(dest):                     # never overwrite an earlier backup
        raise FileExistsError(f"backup already exists: {dest}")
    s = sqlite3.connect(str(db_path))
    d = sqlite3.connect(dest)
    try:
        s.backup(d)                              # online backup API -- safe on a WAL database
    finally:
        d.close()
        s.close()
    return dest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true", help="add the indexes (after a backup)")
    ap.add_argument("--db", default=str(paths.OBSERVATUM_DB), help=argparse.SUPPRESS)
    ap.add_argument("--backup-dir", default=BACKUP_DIR, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)

    print("")
    print("Indexes for Observatum's slow queries (no data or figure changes)")
    print("=" * 74)
    print(f"  observatum.db: {a.db}")
    todo = dry_run(a.db)
    if not todo:
        print("")
        print("  every index is already there. Nothing has been changed.")
        return 0
    if not a.apply:
        print("")
        print("DRY RUN. Nothing has been changed. Run with --apply to add them.")
        return 0
    print("")
    dest = backup(a.db, a.backup_dir)
    print(f"  backed up to {dest}")
    conn = sqlite3.connect(a.db)
    try:
        with conn:
            for name, table, cols, _ in todo:
                conn.execute(create_sql(name, table, cols))
                print(f"  added {name}")
        have = existing_indexes(conn)
    finally:
        conn.close()
    missing = [n for n, *_ in todo if n not in have]
    print("  done." if not missing else f"  NOT added: {missing}")
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
