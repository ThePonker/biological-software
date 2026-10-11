"""link_specimens_to_observations.py -- set specimens.observation_id for the specimens that
are certainly the same find as one observation (note 36 decision 13, review MAP2, 10 Oct 2026).

    py -3.14 scripts\\report_specimen_observation_links.py           # first: Wil checks the list
    py -3.14 scripts\\link_specimens_to_observations.py              # dry run: change nothing
    py -3.14 scripts\\link_specimens_to_observations.py --apply      # write, after a backup

Uses the matching in report_specimen_observation_links.py (imported): only the "certain" tier
is written -- one matching observation (same TVK, date and grid ref; collector and recorder
the same person where both name somebody) and no more specimens on it than its quantity.
Ambiguous, quantity-short and recorder-differs specimens are left for Wil, and a specimen
that already has an observation_id is never changed. The schema is not altered: the column
already exists (specimens.observation_id).

Effect on figures: none expected. Mapping's "All records" already treats a specimen with no
link as its observation when TVK, date and grid ref agree (map_selection._SPECIMEN_OBS); a
link to that same observation counts it the same way. The Insect Collection shows the id in
its "Obs ID" column.

--apply backs observatum.db up with conn.backup() first, then writes in one transaction,
each UPDATE guarded so it only fills an observation_id that is still empty (and never on a
specimen marked "Checked: no field record exists"). It then writes the links it set to
scripts\\_oneoff\\specimen_links_set_<date_time>.csv (or --csv), so they can be undone with

    py -3.14 scripts\\unlink_specimens_from_observations.py --csv <that file>
"""
import argparse
import sys
from datetime import datetime

try:
    from scripts import report_common as rc
    from scripts import report_specimen_observation_links as links
except ImportError:                       # run as py scripts\<name>.py
    import report_common as rc
    import report_specimen_observation_links as links

import paths  # noqa: E402

SAMPLES = 10


SET_HEADER = ["specimen_id", "specimen_code", "observation_id", "species_name", "date",
              "grid_ref", "set_at", "backup"]


def apply(conn, pairs) -> list:
    """Write the links; returns the (specimen id, observation id) pairs actually set."""
    from shared.specimen_links import CHECK_COLUMN, has_check_column
    guard = f" AND {CHECK_COLUMN} IS NULL" if has_check_column(conn) else ""
    done = []
    with conn:
        for sid, oid in pairs:
            if conn.execute("UPDATE specimens SET observation_id = ? WHERE id = ? "
                            "AND observation_id IS NULL" + guard, (oid, sid)).rowcount:
                done.append((sid, oid))
    return done


def default_set_csv() -> str:
    import os
    return os.path.join(rc.REPORT_DIR, f"specimen_links_set_{datetime.now():%Y%m%d_%H%M%S}.csv")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true", help="write (after a backup)")
    ap.add_argument("--db", default=str(paths.OBSERVATUM_DB), help=argparse.SUPPRESS)
    ap.add_argument("--backup-dir", default=rc.BACKUP_DIR, help=argparse.SUPPRESS)
    ap.add_argument("--csv", default=None,
                    help="where --apply lists the links it set (default scripts\\_oneoff\\"
                         "specimen_links_set_<date_time>.csv)")
    a = ap.parse_args(argv)

    print("")
    print("Link specimens to their observation (specimens.observation_id)")
    print("=" * 74)
    print(f"  observatum.db: {a.db}")
    ro = rc.connect_ro(a.db)
    try:
        found = links.match(*links.load(ro))
        before = ro.execute("SELECT COUNT(*) FROM specimens WHERE observation_id IS NOT NULL"
                            ).fetchone()[0]
    finally:
        ro.close()
    links.report(found)
    pairs = links.certain_links(found)
    print("")
    print(f"  specimens linked now: {before:,}")
    print(f"  links to set (certain tier only): {len(pairs):,}")
    by_id = {s["id"]: s for s in found["specimens"]}
    for sid, oid in pairs[:SAMPLES]:
        s = by_id[sid]
        print(f"    specimen {sid:<6} {str(s['name'] or '')[:30]:<30} {s['date']} {s['ref']:<12} "
              f"-> observation {oid}")

    if not a.apply:
        print("")
        print("DRY RUN. Nothing has been changed. Run with --apply to write.")
        return 0
    if not pairs:
        print("  nothing to do. Nothing has been changed.")
        return 0
    print("")
    dest = rc.backup(a.db, "link_specimens", a.backup_dir)
    print(f"  backed up to {dest}")
    conn = rc.sqlite3.connect(a.db)
    try:
        done = apply(conn, pairs)
        after = conn.execute("SELECT COUNT(*) FROM specimens WHERE observation_id IS NOT NULL"
                             ).fetchone()[0]
    finally:
        conn.close()
    stamp = datetime.now().isoformat(timespec="seconds")
    out = a.csv or default_set_csv()
    rc.write_csv(out, SET_HEADER, ([sid, by_id[sid]["code"], oid, by_id[sid]["name"],
                                    by_id[sid]["date"], by_id[sid]["ref"], stamp, dest]
                                   for sid, oid in done))
    print(f"  links set: {len(done):,} of {len(pairs):,}")
    print(f"  specimens linked: before {before:,}, after {after:,}")
    print(f"  the links set are listed in {out}")
    print("  (undo: py -3.14 scripts\\unlink_specimens_from_observations.py --csv <that file>)")
    print("  done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
