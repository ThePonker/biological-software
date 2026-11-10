"""add_data_reference.py -- a "Reference" column for records that came from a person or a
source rather than iRecord / NBN (26 Oct 2026; shared/data_reference.py).

    py -3.14 scripts\\add_data_reference.py              # dry run: report only
    py -3.14 scripts\\add_data_reference.py --apply      # backup, then add

Adds data_reference (TEXT) to observations, recording_scheme and contributed_observations,
and an index on it in each. Every row starts NULL; no value and no count changes, so no figure
moves. Idempotent. --apply backs observatum.db up first with SQLite's backup API into
C:\\BiologicalSoftware_Backups\\reference\\ (observatum_pre_add_data_reference_<time>.db), then
does the ALTERs and CREATE INDEXes in one transaction and reads the columns back.
Close Observatum first. Not on an away machine.
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
from shared import data_reference as dr  # noqa: E402

BACKUP_DIR = os.path.join(r"C:\BiologicalSoftware_Backups", "reference")


def backup(db_path, backup_dir=BACKUP_DIR) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    dest = os.path.join(backup_dir, f"observatum_pre_add_data_reference_{stamp}.db")
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


def survey(conn) -> list:
    """[(table, exists, has_column, has_index, row_count)] for the three record tables."""
    out = []
    for t in dr.TABLES:
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({t})")}
        if not cols:
            out.append((t, False, False, False, 0))
            continue
        idx = conn.execute("SELECT 1 FROM sqlite_master WHERE type='index' AND name=?",
                           (dr.INDEX_FMT.format(table=t),)).fetchone() is not None
        n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        out.append((t, True, dr.COLUMN in cols, idx, n))
    return out


def _rollback(conn):
    try:
        conn.execute("ROLLBACK")
    except sqlite3.Error:
        pass            # no transaction was open (BEGIN itself failed)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--db", default=str(paths.OBSERVATUM_DB), help=argparse.SUPPRESS)
    ap.add_argument("--backup-dir", default=BACKUP_DIR, help=argparse.SUPPRESS)
    ap.add_argument("--test-ignore-away", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    if a.apply and not a.test_ignore_away:
        from shared.away_mode import refuse_if_away
        refuse_if_away("add_data_reference")
    print("\nRecords -- data_reference (the 'Reference' column)")
    print("=" * 72)
    print(f"  observatum.db: {a.db}")
    ro = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    try:
        before = survey(ro)
    finally:
        ro.close()
    for t, exists, has, idx, n in before:
        if not exists:
            print(f"  {t}: table not found -- skipped")
            continue
        print(f"  {t}: {n:,} rows; column {dr.COLUMN}: {'present' if has else 'not there yet'}")
        if not has:
            print(f"      would run: ALTER TABLE {t} ADD COLUMN {dr.COLUMN} TEXT")
        print(f"      index {dr.INDEX_FMT.format(table=t)}: "
              f"{'present' if idx else 'would run: CREATE INDEX IF NOT EXISTS ... (' + dr.COLUMN + ')'}")
    print("  Every row starts NULL; row counts stay the same.")
    todo = [t for t, e, h, i, _n in before if e and not (h and i)]
    if not a.apply:
        print("\nDRY RUN. Nothing has been changed. Run with --apply to write.")
        return 0
    if not todo:
        print("\n  nothing to do. Nothing has been changed.")
        return 0
    print(f"\n  backed up to {backup(a.db, a.backup_dir)}")
    # One transaction: all three tables or none. isolation_level=None leaves the transaction
    # to us (sqlite3 would otherwise commit each ALTER / CREATE INDEX as it runs).
    conn = sqlite3.connect(a.db, isolation_level=None, timeout=3)
    try:
        try:
            conn.execute("BEGIN IMMEDIATE")
            dr.ensure_schema(conn)
            conn.execute("COMMIT")
        except sqlite3.OperationalError as e:
            _rollback(conn)
            if "locked" in str(e).lower() or "busy" in str(e).lower():
                print("\n  Close Observatum (and anything else using observatum.db) and run it "
                      "again. Nothing has been changed.")
                print("  (The backup above was written; it does no harm.)")
                return 1
            print(f"\n  FAILED: {e}\n  Rolled back. Nothing has been changed.")
            return 1
        except Exception as e:
            _rollback(conn)
            print(f"\n  FAILED: {e}\n  Rolled back. Nothing has been changed.")
            return 1
        after = survey(conn)
        for t, exists, has, idx, n in after:
            if exists:
                cols = [r[1] for r in conn.execute(f"PRAGMA table_info({t})")]
                print(f"  {t}: {n:,} rows; {len(cols)} columns; last: {cols[-1]}; index: {idx}")
    finally:
        conn.close()
    ok = all(b[4] == x[4] and (not x[1] or (x[2] and x[3])) for b, x in zip(before, after))
    print("  done." if ok else "  NOT as expected -- check the database.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
