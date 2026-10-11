"""add_specimen_link_check_column.py -- add specimens.no_field_record_checked, the mark for
"I have checked: this specimen has no field record" (11 Oct 2026).

    py -3.14 scripts\\add_specimen_link_check_column.py            # dry run: change nothing
    py -3.14 scripts\\add_specimen_link_check_column.py --apply    # add it, after a backup

The column holds the date and time Wil ticked "Checked: no field record exists" in the Edit
Specimen dialog's Field record box (e.g. '2026-10-11T14:05:12'); empty means not checked.
It is kept apart from the link: ticking it clears specimens.observation_id, and choosing a
field record clears it. The links report (report_specimen_observation_links.py) shows these
specimens as their own group, so the specimens still to decide get fewer as Wil works.

Until this has run, Observatum shows "run scripts\\add_specimen_link_check_column.py" in
place of the tick box; everything else in the Field record box works.

Adds one empty column (ALTER TABLE ... ADD COLUMN); no row is changed and no figure moves.
Running it again does nothing. --apply backs observatum.db up with conn.backup() first.
Close Observatum first.
"""
import argparse
import sys

try:
    from scripts import report_common as rc
except ImportError:                       # run as py scripts\<name>.py
    import report_common as rc

import paths  # noqa: E402
from shared.specimen_links import CHECK_COLUMN, has_check_column  # noqa: E402

ADD_SQL = f"ALTER TABLE specimens ADD COLUMN {CHECK_COLUMN} TEXT"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true", help="add the column (after a backup)")
    ap.add_argument("--db", default=str(paths.OBSERVATUM_DB), help=argparse.SUPPRESS)
    ap.add_argument("--backup-dir", default=rc.BACKUP_DIR, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)

    print("")
    print(f"Add specimens.{CHECK_COLUMN} (checked: no field record)")
    print("=" * 74)
    print(f"  observatum.db: {a.db}")
    ro = rc.connect_ro(a.db)
    try:
        there = has_check_column(ro)
        n_cols = len(ro.execute("PRAGMA table_info(specimens)").fetchall())
        n_spec, n_linked = ro.execute(
            "SELECT COUNT(*), COUNT(observation_id) FROM specimens").fetchone()
    finally:
        ro.close()
    print(f"  specimens: {n_spec:,} ({n_linked:,} linked to an observation); "
          f"{n_cols} columns")
    if there:
        print(f"  {CHECK_COLUMN} is already there. Nothing to do. Nothing has been changed.")
        return 0
    print(f"  to run: {ADD_SQL};")

    if not a.apply:
        print("")
        print("DRY RUN. Nothing has been changed. Run with --apply to write.")
        return 0
    dest = rc.backup(a.db, "add_specimen_link_check_column", a.backup_dir)
    print(f"  backed up to {dest}")
    conn = rc.sqlite3.connect(a.db)
    try:
        with conn:
            conn.execute(ADD_SQL)
        ok = has_check_column(conn)
        after = conn.execute(f"SELECT COUNT(*), COUNT({CHECK_COLUMN}) FROM specimens").fetchone()
    finally:
        conn.close()
    print(f"  column added: {ok}; specimens {after[0]:,}, marked checked {after[1]:,}")
    print("  done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
