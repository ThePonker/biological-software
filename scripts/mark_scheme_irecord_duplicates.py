"""mark_scheme_irecord_duplicates.py -- flag the Recording Scheme rows that are the NBN Atlas
copy of an iRecord record, so each record counts once (fault F53, Wil's answer Q59, 12 Oct
2026: count once, keep the iRecord copy, flag not delete, reversible).

    py -3.14 scripts\\mark_scheme_irecord_duplicates.py              # dry run: report only
    py -3.14 scripts\\mark_scheme_irecord_duplicates.py --apply      # backup, then mark
    py -3.14 scripts\\mark_scheme_irecord_duplicates.py --undo       # dry run of the undo
    py -3.14 scripts\\mark_scheme_irecord_duplicates.py --undo --apply   # backup, clear marks

What it does
------------
- Adds the column recording_scheme.duplicate_of (INTEGER, NULL) if it is not there yet.
- Sets duplicate_of = <id of the iRecord row> on every NBN Atlas row that re-supplies an
  iRecord record: its occurrence ID is the iRecord row's irecord_id, same TVK, same date
  (the "same iRecord id" tier of report_scheme_duplicates.py; the rule is
  shared/scheme_duplicates.py). The iRecord row is never marked. Nothing is deleted.
- The exact / likely / possible tiers (910 / 11,269 / 7,694 pairs on 10 Oct) are NOT touched.
- Only a row whose duplicate_of is still NULL is written; a row already marked is left.
- --undo sets duplicate_of back to NULL on every marked row (the column stays, empty).

Every count, map, chart and export of the scheme then leaves the marked rows out
(shared/scheme_duplicates.live_sql, through shared/species_counting); the Scheme tab's
"Show duplicates" toggle lists them. SO THE SCHEME FIGURES CHANGE: the dry run shows the
record and species counts, and a few species, before and after.

--apply backs observatum.db up first with SQLite's backup API into
C:\\BiologicalSoftware_Backups\\reference\\ (observatum_pre_mark_scheme_duplicates_<time>.db or
..._pre_unmark_..., for --undo), then writes in one transaction. Close Observatum first.
"""
import argparse
import os
import sqlite3
import sys
from collections import Counter
from datetime import datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_ROOT, os.path.join(_ROOT, "Observatum")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import paths  # noqa: E402
from shared.scheme_duplicates import COLUMN, TABLE, copies, load_rows  # noqa: E402

BACKUP_DIR = os.path.join(r"C:\BiologicalSoftware_Backups", "reference")
EXAMPLES = ("Rutpela maculata", "Leiopus linnei/nebulosus", "Stenocorus meridianus",
            "Clytus arietis")


def has_column(conn) -> bool:
    return COLUMN in {r[1] for r in conn.execute(f"PRAGMA table_info({TABLE})")}


def plan(conn) -> dict:
    """What a run would do: {"copies": {nbn id: irecord id}, "already": {id: kept id},
    "new": {id: kept id} (to write), "stale": [ids marked but no longer matching],
    "datasets": Counter of the copies' NBN datasets}."""
    rows = load_rows(conn)
    found = copies(rows)
    already = {}
    if has_column(conn):
        already = dict(conn.execute(
            f"SELECT id, {COLUMN} FROM {TABLE} WHERE {COLUMN} IS NOT NULL").fetchall())
    new = {i: k for i, k in found.items() if i not in already}
    stale = sorted(i for i in already if i not in found)
    have = {r[1] for r in conn.execute(f"PRAGMA table_info({TABLE})")}
    parts = [f"NULLIF(TRIM({c}), '')" for c in ("dataset_name", "source") if c in have]
    ds = dict(conn.execute(f"SELECT id, COALESCE({', '.join(parts + [repr('')])}) "
                           f"FROM {TABLE}").fetchall())
    return {"copies": found, "already": already, "new": new, "stale": stale,
            "datasets": Counter(ds.get(i, "") for i in found)}


def figures(conn, left_out) -> dict:
    """Record and species counts with `left_out` (a set of ids) not counted. Raw figures:
    no species-counting switches, no family scope."""
    rows = conn.execute(f"SELECT id, species_name, species_tvk FROM {TABLE}").fetchall()
    kept = [r for r in rows if r[0] not in left_out]
    tvks_of = {n: {r[2] for r in rows if r[1] == n and r[2]} for n in EXAMPLES}
    by_tvk = Counter(r[2] for r in kept)
    return {"records": len(kept),
            "species_tvk": len({r[2] for r in kept if r[2]}),
            "species_name": len({r[1] for r in kept if r[1]}),
            # by the name's TVK, so "Leiopus linnei/nebulosus" includes its "agg." spelling
            "examples": {n: sum(by_tvk.get(t, 0) for t in tvks_of[n]) for n in EXAMPLES}}


def backup(db_path, backup_dir=BACKUP_DIR, undo=False) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    what = "unmark" if undo else "mark"
    dest = os.path.join(backup_dir, f"observatum_pre_{what}_scheme_duplicates_{stamp}.db")
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


def apply_marks(conn, new: dict) -> int:
    """Add the column if needed and write the marks (guarded: still NULL). One transaction."""
    n = 0
    with conn:
        if not has_column(conn):
            conn.execute(f"ALTER TABLE {TABLE} ADD COLUMN {COLUMN} INTEGER")
        for rid, kept in sorted(new.items()):
            n += conn.execute(f"UPDATE {TABLE} SET {COLUMN} = ? WHERE id = ? AND {COLUMN} IS NULL",
                              (kept, rid)).rowcount
    return n


def clear_marks(conn) -> int:
    with conn:
        return conn.execute(f"UPDATE {TABLE} SET {COLUMN} = NULL WHERE {COLUMN} IS NOT NULL"
                            ).rowcount


def _show_figures(before, after) -> None:
    print(f"  {'':<36}{'before':>10}{'after':>10}{'change':>10}")

    def line(label, a, b):
        print(f"  {label:<36}{a:>10,}{b:>10,}{b - a:>+10,}")
    line("scheme records counted", before["records"], after["records"])
    line("species (distinct TVKs)", before["species_tvk"], after["species_tvk"])
    line("species (distinct names)", before["species_name"], after["species_name"])
    for n in EXAMPLES:
        line(n + " (by TVK)", before["examples"][n], after["examples"][n])
    print("  (raw figures: before the species-counting switches and the family scope; the")
    print("   Scheme dashboard applies those too, so its own numbers differ by the same rows.)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true", help="write (after a backup)")
    ap.add_argument("--undo", action="store_true", help="clear the marks instead")
    ap.add_argument("--db", default=str(paths.OBSERVATUM_DB), help=argparse.SUPPRESS)
    ap.add_argument("--backup-dir", default=BACKUP_DIR, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)

    print("")
    print("Recording Scheme -- NBN Atlas copies of iRecord records "
          + ("(UNDO: clear the marks)" if a.undo else "(mark, keep the iRecord copy)"))
    print("=" * 74)
    print(f"  observatum.db: {a.db}")
    ro = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    try:
        col = has_column(ro)
        p = plan(ro)
        marked_now = set(p["already"])
        if a.undo:
            before = figures(ro, marked_now)
            after = figures(ro, set())
        else:
            before = figures(ro, marked_now)
            after = figures(ro, marked_now | set(p["new"]))
    finally:
        ro.close()

    print(f"  column {TABLE}.{COLUMN}: {'present' if col else 'not there yet (added by --apply)'}")
    print(f"  rows already marked: {len(p['already']):,}")
    if a.undo:
        print(f"  marks to clear: {len(p['already']):,}")
    else:
        print(f"  NBN copies of an iRecord record found: {len(p['copies']):,}  "
              f"(iRecord rows they copy: {len(set(p['copies'].values())):,})")
        for ds, n in p["datasets"].most_common():
            print(f"    {n:>7,}  {ds or '(no dataset)'}")
        print(f"  to mark now (not marked yet): {len(p['new']):,}")
        if p["stale"]:
            print(f"  marked but no longer matching (left as they are; --undo clears all): "
                  f"{len(p['stale']):,}")
        for rid, kept in sorted(p["new"].items())[:5]:
            print(f"      e.g. id {rid} -> duplicate_of {kept}")
    print("")
    _show_figures(before, after)

    if not a.apply:
        print("")
        print("DRY RUN. Nothing has been changed. Run with --apply to write.")
        return 0
    if (a.undo and not p["already"]) or (not a.undo and not p["new"] and col):
        print("  nothing to do. Nothing has been changed.")
        return 0
    print("")
    dest = backup(a.db, a.backup_dir, undo=a.undo)
    print(f"  backed up to {dest}")
    conn = sqlite3.connect(a.db)
    try:
        n = clear_marks(conn) if a.undo else apply_marks(conn, p["new"])
        left = conn.execute(f"SELECT COUNT(*) FROM {TABLE} WHERE {COLUMN} IS NOT NULL"
                            ).fetchone()[0]
    finally:
        conn.close()
    print(f"  {'cleared' if a.undo else 'marked'}: {n:,} rows; marked rows now: {left:,}")
    print("  done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
