"""add_hidden_at_column.py -- the schema for iRecord-safe delete (F72, agreed with Wil 12 Oct
2026, late): an observation that is also in iRecord is HIDDEN here, not deleted, so the next
download cannot bring it back as a second copy.

    py -3.14 scripts\\add_hidden_at_column.py              # dry run: report only
    py -3.14 scripts\\add_hidden_at_column.py --apply      # backup, then add

What it does
------------
- Adds the column observations.hidden_at (TEXT, ISO timestamp, NULL = live) if missing.
- Adds the table hidden_irecord_ids(irecord_id TEXT PRIMARY KEY, hidden_at TEXT,
  species_name TEXT, returned_at TEXT) if missing (returned_at is set when a download
  brings a hidden record again; the cleaning report lists those).
- Rebuilds the assessment_records VIEW (the one Examen reads) so its "FROM observations"
  reads "FROM observations WHERE hidden_at IS NULL": a hidden record leaves Examen too.
  The rest of the view is kept exactly as found.
- Idempotent: run twice, the second run finds nothing to do. No row is changed, so NO
  FIGURE CHANGES until Wil hides a record in Observatum (the dry run shows how many rows
  are hidden now, 0 on a fresh column).

--apply backs observatum.db up first with SQLite's backup API into
C:\\BiologicalSoftware_Backups\\reference\\ (observatum_pre_add_hidden_at_<time>.db), then
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
from shared.hidden_records import (  # noqa: E402
    COLUMN, ID_TABLE, TABLE, VIEW, ensure_schema, ensure_view, view_skips_hidden,
)

BACKUP_DIR = os.path.join(r"C:\BiologicalSoftware_Backups", "reference")


def state(conn) -> dict:
    cols = {r[1] for r in conn.execute(f"PRAGMA table_info({TABLE})")}
    id_cols = {r[1] for r in conn.execute(f"PRAGMA table_info({ID_TABLE})")}
    out = {"column": COLUMN in cols, "table": bool(id_cols),
           "returned_at": "returned_at" in id_cols,
           "view": view_skips_hidden(conn),
           "observations": conn.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0],
           "hidden": 0, "remembered": 0}
    if out["column"]:
        out["hidden"] = conn.execute(
            f"SELECT COUNT(*) FROM {TABLE} WHERE {COLUMN} IS NOT NULL").fetchone()[0]
    if out["table"]:
        out["remembered"] = conn.execute(f"SELECT COUNT(*) FROM {ID_TABLE}").fetchone()[0]
    return out


def backup(db_path, backup_dir=BACKUP_DIR) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    dest = os.path.join(backup_dir, f"observatum_pre_add_hidden_at_{stamp}.db")
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true", help="write (after a backup)")
    ap.add_argument("--db", default=str(paths.OBSERVATUM_DB), help=argparse.SUPPRESS)
    ap.add_argument("--backup-dir", default=BACKUP_DIR, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)

    print("")
    print("Observations -- hidden_at column and hidden_irecord_ids table (iRecord-safe delete)")
    print("=" * 74)
    print(f"  observatum.db: {a.db}")
    ro = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    try:
        s = state(ro)
    finally:
        ro.close()
    todo = []
    if not s["column"]:
        todo.append(f"add column {TABLE}.{COLUMN} (TEXT)")
    if not s["table"]:
        todo.append(f"create table {ID_TABLE}")
    elif not s["returned_at"]:
        todo.append(f"add column {ID_TABLE}.returned_at (TEXT)")
    if s["view"] is False:
        todo.append(f"rebuild view {VIEW} to skip hidden rows")
    print(f"  observations: {s['observations']:,}")
    print(f"  column {TABLE}.{COLUMN}: {'present' if s['column'] else 'not there yet'}")
    print(f"  table {ID_TABLE}: "
          + ("present" if s["table"] and s["returned_at"] else
             "present, without returned_at" if s["table"] else "not there yet"))
    print(f"  view {VIEW} (Examen): "
          + {None: "not in this database (left alone)", True: "skips hidden rows",
             False: "does not skip hidden rows yet"}[s["view"]])
    print(f"  observations hidden now: {s['hidden']:,}   remembered iRecord IDs: {s['remembered']:,}")
    print("  to do: " + ("; ".join(todo) if todo else "nothing (already in place)"))
    print("  No row changes: the figures stay as they are until a record is hidden in Observatum.")

    if not a.apply:
        print("")
        print("DRY RUN. Nothing has been changed. Run with --apply to write.")
        return 0
    if not todo:
        print("  nothing to do. Nothing has been changed.")
        return 0
    print("")
    dest = backup(a.db, a.backup_dir)
    print(f"  backed up to {dest}")
    conn = sqlite3.connect(a.db)
    try:
        with conn:
            ensure_schema(conn)
            ensure_view(conn)
        after = state(conn)
    finally:
        conn.close()
    ok = after["column"] and after["table"] and after["returned_at"] and after["view"] is not False
    print(f"  column present: {after['column']}; table present: {after['table']}; "
          f"view skips hidden rows: {after['view']}; hidden now: {after['hidden']:,}")
    print("  done." if ok else "  NOT complete -- check the database.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
