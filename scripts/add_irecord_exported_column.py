"""add_irecord_exported_column.py -- remember which records were exported for iRecord (14 Oct
2026), so a second export before the sync cannot send them twice (shared/irecord_exported.py).

    py -3.14 scripts\\add_irecord_exported_column.py              # dry run: report only
    py -3.14 scripts\\add_irecord_exported_column.py --apply      # backup, then add

Adds the column observations.irecord_exported_on (TEXT) if it is missing. Every row starts
NULL ("not exported by Observatum yet"); records already uploaded have an iRecord ID and are
left out of the iRecord export anyway. No row's values change, so no figure moves. Idempotent.

--apply backs observatum.db up first with SQLite's backup API into
C:\\BiologicalSoftware_Backups\\reference\\ (observatum_pre_add_irecord_exported_<time>.db).
Close Observatum first.
"""
import argparse
import os
import sqlite3
import sys
from datetime import datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_ROOT, os.path.join(_ROOT, "Observatum")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import paths  # noqa: E402
from shared import irecord_exported as sc  # noqa: E402

BACKUP_DIR = os.path.join(r"C:\BiologicalSoftware_Backups", "reference")


def backup(db_path, backup_dir=BACKUP_DIR) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    dest = os.path.join(backup_dir, f"observatum_pre_add_irecord_exported_{stamp}.db")
    os.makedirs(backup_dir, exist_ok=True)
    if os.path.exists(dest):
        raise FileExistsError(f"backup already exists: {dest}")
    src, d = sqlite3.connect(str(db_path)), sqlite3.connect(dest)
    try:
        src.backup(d)
    finally:
        d.close()
        src.close()
    return dest


def counts(conn):
    n = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    cols = len(conn.execute("PRAGMA table_info(observations)").fetchall())
    return n, cols


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--db", default=str(paths.OBSERVATUM_DB), help=argparse.SUPPRESS)
    ap.add_argument("--backup-dir", default=BACKUP_DIR, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    print("\nObservations -- irecord_exported_on (no record sent to iRecord twice)")
    print("=" * 72)
    print(f"  observatum.db: {a.db}")
    ro = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    try:
        present = sc.has_column(ro)
        n, cols = counts(ro)
    finally:
        ro.close()
    print(f"  observations: {n:,} ({cols} columns); column {sc.COLUMN}: "
          f"{'present' if present else 'not there yet'}")
    print("  No row's values change: every record starts as 'not exported by Observatum yet'.")
    if not a.apply:
        print("\nDRY RUN. Nothing has been changed. Run with --apply to write.")
        return 0
    if present:
        print("  nothing to do. Nothing has been changed.")
        return 0
    print(f"  backed up to {backup(a.db, a.backup_dir)}")
    conn = sqlite3.connect(a.db)
    try:
        with conn:
            sc.ensure_schema(conn)
        n2, cols2 = counts(conn)
        set_rows = conn.execute(f"SELECT COUNT(*) FROM observations WHERE {sc.COLUMN} IS NOT NULL").fetchone()[0]
    finally:
        conn.close()
    ok = n2 == n and cols2 == cols + 1 and set_rows == 0
    print(f"  observations: {n2:,} ({cols2} columns); rows with a value: {set_rows}")
    print("  done." if ok else "  NOT as expected -- check the database.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
