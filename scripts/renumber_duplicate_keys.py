"""renumber_duplicate_keys.py -- give every record its own Observatum key (14 Oct 2026).

    py -3.14 scripts\\renumber_duplicate_keys.py              # dry run: report only
    py -3.14 scripts\\renumber_duplicate_keys.py --apply      # backup, then renumber

Why: three generators picked "the next number" by sorting key TEXT, so from 25 Mar 2026
keys repeated (13 Oct copy: 3,712 records under 993 keys). The key goes to iRecord as the
External key and must name one record. Checked 14 Oct: none of these keys is in iRecord (the
full download of Wil's records holds no Observatum key but the 46 test ones), so changing
them is safe.

For each repeated key the record with the lowest id keeps it; every other record gets a NEW
key from today's prefix, numbered after the highest in use (shared/observatum_keys.py, THE
rule). A record whose key is its iRecord External key (it came from iRecord carrying it) is
never changed: it is listed instead. Nothing else is touched; no figure moves.
--apply backs observatum.db up first (C:\\BiologicalSoftware_Backups\\reference\\
observatum_pre_renumber_keys_<time>.db) and writes one CSV of old -> new keys to
scripts\\_oneoff\\renumbered_keys_<date>.csv. Close Observatum first.
"""
import argparse
import csv
import os
import sqlite3
import sys
from datetime import datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_ROOT, os.path.join(_ROOT, "Observatum")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import paths  # noqa: E402
from shared.observatum_keys import last_sequence, make_key, prefix_for  # noqa: E402

BACKUP_DIR = os.path.join(r"C:\BiologicalSoftware_Backups", "reference")


def plan(conn, initials: str):
    """([(id, old key, new key)], [(id, key) left because it is the record's External key])."""
    # in each group the record that carries the key as its iRecord External key keeps it
    # (first in this order); otherwise the lowest id
    rows = conn.execute(
        "SELECT id, observatum_key, COALESCE(external_key, '') FROM observations "
        "WHERE observatum_key IN (SELECT observatum_key FROM observations "
        "WHERE observatum_key LIKE 'OBS-%' GROUP BY observatum_key HAVING COUNT(*) > 1) "
        "ORDER BY observatum_key, (COALESCE(external_key, '') = observatum_key) DESC, id").fetchall()
    prefix = prefix_for(initials)
    seq = last_sequence(conn, prefix)
    changes, left, seen = [], [], set()
    for rid, key, ext in rows:
        if key not in seen:
            seen.add(key)                      # the lowest id keeps the key
            continue
        if ext == key:
            left.append((rid, key))
            continue
        seq += 1
        changes.append((rid, key, make_key(prefix, seq)))
    return changes, left


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--initials", default="WJH")
    ap.add_argument("--db", default=str(paths.OBSERVATUM_DB), help=argparse.SUPPRESS)
    ap.add_argument("--backup-dir", default=BACKUP_DIR, help=argparse.SUPPRESS)
    ap.add_argument("--csv", default=None)
    a = ap.parse_args(argv)
    print("\nObservatum keys -- one record per key")
    print("=" * 40)
    ro = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    try:
        total = ro.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
        changes, left = plan(ro, a.initials)
        shared_keys = ro.execute("SELECT COUNT(*) FROM (SELECT observatum_key FROM observations WHERE "
                                 "observatum_key LIKE 'OBS-%' GROUP BY observatum_key HAVING COUNT(*) > 1)"
                                 ).fetchone()[0]
    finally:
        ro.close()
    print(f"  observations: {total:,}; keys held by more than one record: {shared_keys:,}")
    print(f"  records to get a new key: {len(changes):,}; left (key is their iRecord External key): {len(left)}")
    for rid, old, new in changes[:10]:
        print(f"    id {rid}: {old} -> {new}")
    if len(changes) > 10:
        print(f"    ... and {len(changes) - 10:,} more")
    if not a.apply:
        print("\nDRY RUN. Nothing has been changed. Run with --apply to renumber.")
        return 0
    if not changes:
        print("  nothing to do. Nothing has been changed.")
        return 0
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    os.makedirs(a.backup_dir, exist_ok=True)
    dest = os.path.join(a.backup_dir, f"observatum_pre_renumber_keys_{stamp}.db")
    src, d = sqlite3.connect(a.db), sqlite3.connect(dest)
    try:
        src.backup(d)
    finally:
        d.close()
        src.close()
    print(f"  backed up to {dest}")
    conn = sqlite3.connect(a.db)
    try:
        with conn:
            for rid, old, new in changes:
                conn.execute("UPDATE observations SET observatum_key = ? WHERE id = ? AND observatum_key = ?",
                             (new, rid, old))
        still = conn.execute("SELECT COUNT(*) FROM (SELECT observatum_key FROM observations WHERE "
                             "observatum_key LIKE 'OBS-%' GROUP BY observatum_key HAVING COUNT(*) > 1)"
                             ).fetchone()[0]
        total2 = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    finally:
        conn.close()
    out = a.csv or os.path.join(_ROOT, "scripts", "_oneoff",
                                f"renumbered_keys_{datetime.now():%Y%m%d}.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "old_key", "new_key"])
        w.writerows(changes)
    ok = still == len({k for _, k in left}) and total2 == total
    print(f"  keys still repeated: {still} (expected {len({k for _, k in left})}); records {total2:,}")
    print(f"  old -> new list: {out}")
    print("  done." if ok else "  NOT as expected -- check the database.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
