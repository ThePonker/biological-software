"""add_staging_check_columns.py -- add the "To check" columns to Data Entry's staging table.

    py -3.14 scripts\\add_staging_check_columns.py            # dry run: says what it would add
    py -3.14 scripts\\add_staging_check_columns.py --apply    # backup, then add them

entry_staging gets check_flag (INTEGER: 1 = marked "To check") and check_note (TEXT), used by
the Check column in the Data Entry grid. Existing rows are untouched (both start empty). Safe to
run twice: a column already there is left alone. --apply only runs on observatum.db and backs it
up first (conn.backup). Close Observatum and Data Entry before --apply.
"""
import argparse
import os
import sqlite3
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_ROOT, os.path.join(_ROOT, "Observatum")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import paths  # noqa: E402

try:
    from scripts import report_common as rc
except ImportError:                       # run as py scripts\<name>.py
    import report_common as rc

COLUMNS = (("check_flag", "INTEGER"), ("check_note", "TEXT"))


def missing_columns(conn) -> list:
    """The (name, type) pairs of COLUMNS that entry_staging does not have yet."""
    have = {r[1] for r in conn.execute("PRAGMA table_info(entry_staging)")}
    return [c for c in COLUMNS if c[0] not in have]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--db", default=str(paths.OBSERVATUM_DB), help=argparse.SUPPRESS)
    ap.add_argument("--backup-dir", default=rc.BACKUP_DIR, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    print("\nData Entry: 'To check' columns on entry_staging")
    print("=" * 40)
    if a.apply and os.path.basename(str(a.db)).lower() != "observatum.db":
        print(f"  refusing: --apply only runs on observatum.db, not {os.path.basename(str(a.db))}. "
              "Nothing has been changed.")
        return 1
    ro = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    try:
        if not ro.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='entry_staging'").fetchone():
            print("  there is no entry_staging table in this database. Nothing has been changed.")
            return 1
        todo = missing_columns(ro)
        rows = ro.execute("SELECT COUNT(*) FROM entry_staging").fetchone()[0]
    finally:
        ro.close()
    print(f"  staged rows: {rows:,}")
    if not todo:
        print("  check_flag and check_note are both there already. Nothing has been changed.")
        return 0
    for name, typ in todo:
        print(f"  would add: {name} {typ}")
    if not a.apply:
        print("\nDRY RUN. Run with --apply to add them. Nothing has been changed.")
        return 0
    dest = rc.backup(a.db, "add_staging_check_columns", a.backup_dir)
    print(f"  backed up to {dest}")
    conn = sqlite3.connect(a.db)
    try:
        with conn:
            for name, typ in missing_columns(conn):
                conn.execute(f"ALTER TABLE entry_staging ADD COLUMN {name} {typ}")
        left = missing_columns(conn)
        rows2 = conn.execute("SELECT COUNT(*) FROM entry_staging").fetchone()[0]
    finally:
        conn.close()
    ok = not left and rows2 == rows
    print(f"  added {len(todo)} column(s); staged rows {rows2:,}")
    print("  done." if ok else "  NOT as expected -- check the database.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
