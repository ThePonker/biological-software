"""add_photo_links_table.py -- photos B2 (13 Oct 2026): the record <-> photo link table.

    py -3.14 scripts\\add_photo_links_table.py              # dry run: report only
    py -3.14 scripts\\add_photo_links_table.py --apply      # backup, then add

Adds the table photo_links and its three indexes (definition: shared/photo_links.py) if they
are missing. No other table is touched and no row anywhere is changed, so no figure moves.
Idempotent: a second run finds nothing to do.

--apply backs observatum.db up first with SQLite's backup API into
C:\\BiologicalSoftware_Backups\\reference\\ (observatum_pre_add_photo_links_<time>.db), then
writes in one transaction. Close Observatum first.
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
from shared import photo_links as pl  # noqa: E402

BACKUP_DIR = os.path.join(r"C:\BiologicalSoftware_Backups", "reference")


def backup(db_path, backup_dir=BACKUP_DIR) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    dest = os.path.join(backup_dir, f"observatum_pre_add_photo_links_{stamp}.db")
    os.makedirs(backup_dir, exist_ok=True)
    if os.path.exists(dest):                     # never overwrite an earlier backup
        raise FileExistsError(f"backup already exists: {dest}")
    src = sqlite3.connect(str(db_path))
    d = sqlite3.connect(dest)
    try:
        src.backup(d)
    finally:
        d.close()
        src.close()
    return dest


def tables(conn) -> dict:
    out = {}
    for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        out[name] = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true", help="write (after a backup)")
    ap.add_argument("--db", default=str(paths.OBSERVATUM_DB), help=argparse.SUPPRESS)
    ap.add_argument("--backup-dir", default=BACKUP_DIR, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)

    print("\nPhotos -- the photo_links table (record <-> photo)")
    print("=" * 52)
    print(f"  observatum.db: {a.db}")
    ro = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    try:
        present = pl.has_table(ro)
        indexes = {r[0] for r in ro.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=?", (pl.TABLE,))}
        present = present and all(f"idx_{pl.TABLE}_{k}" in indexes
                                  for k in ("specimen", "observation", "path"))
        before = tables(ro)
    finally:
        ro.close()
    print(f"  table {pl.TABLE} and its indexes: {'present' if present else 'not (all) there yet'}")
    print(f"  other tables and their rows: {len(before)} tables, "
          f"{sum(v for k, v in before.items() if k != pl.TABLE):,} rows (none will change)")
    if not a.apply:
        print("\nDRY RUN. Nothing has been changed. Run with --apply to write.")
        return 0
    if present:
        print("  nothing to do. Nothing has been changed.")
        return 0
    dest = backup(a.db, a.backup_dir)
    print(f"  backed up to {dest}")
    conn = sqlite3.connect(a.db)
    try:
        with conn:
            pl.ensure_schema(conn)
        after = tables(conn)
    finally:
        conn.close()
    same = all(after.get(k) == v for k, v in before.items())
    ok = pl.TABLE in after and same
    print(f"  {pl.TABLE} present: {pl.TABLE in after}; other tables unchanged: {same}")
    print("  done." if ok else "  NOT as expected -- check the database.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
