"""unlink_specimens_from_observations.py -- clear specimens.observation_id (the link from a
specimen to its field record), for chosen specimens or for everything the link script set.
11 Oct 2026.

    py -3.14 scripts\\unlink_specimens_from_observations.py --id 812 813          # dry run
    py -3.14 scripts\\unlink_specimens_from_observations.py --code WJH-0412       # dry run
    py -3.14 scripts\\unlink_specimens_from_observations.py --csv scripts\\_oneoff\\specimen_links_set_20261011_101500.csv
    ... add --apply to write, after a backup

--id / --code    unlink these specimens, whatever observation they are linked to.
--csv            a list written by link_specimens_to_observations.py --apply: unlink each
                 specimen in it, but only while it still points at the observation the
                 script set (a link Wil has since changed by hand is kept and listed).
Several of each may be given together. One specimen's link can also be cleared in the app:
Edit Specimen -> Field record -> Clear.

Only observation_id is changed; nothing else on the specimen, and no observation. A
"Checked: no field record exists" mark is left as it is (an unlinked specimen has none).

--apply backs observatum.db up with conn.backup() first, writes in one transaction, then
lists what it cleared in scripts\\_oneoff\\specimen_links_removed_<date_time>.csv.

Effect on figures: Mapping's "All records" counts an unlinked specimen as its observation
again only through the same TVK + date + grid ref; nothing else reads the link.
"""
import argparse
import csv
import os
import sys
from datetime import datetime

try:
    from scripts import report_common as rc
except ImportError:                       # run as py scripts\<name>.py
    import report_common as rc

import paths  # noqa: E402

SAMPLES = 15
REMOVED_HEADER = ["specimen_id", "specimen_code", "observation_id", "species_name", "date",
                  "grid_ref", "removed_at", "backup"]


def read_set_csv(path) -> list:
    """[(specimen id, observation id)] from a link script CSV."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [(int(r["specimen_id"]), int(r["observation_id"])) for r in csv.DictReader(f)
                if (r.get("specimen_id") or "").strip() and (r.get("observation_id") or "").strip()]


def plan(conn, ids=(), codes=(), csv_pairs=()) -> dict:
    """{"unlink": [(specimen row)], "kept": [(row, expected obs id)], "missing": [what]}.
    Rows: (id, specimen_code, observation_id, species_name, date_collected, grid_ref)."""
    cols = "id, specimen_code, observation_id, species_name, date_collected, grid_ref"
    out = {"unlink": {}, "kept": [], "missing": [], "not_linked": []}

    def take(row, what):
        if row is None:
            out["missing"].append(what)
        elif row[2] is None:
            out["not_linked"].append(row)
        else:
            out["unlink"][row[0]] = row

    for i in ids:
        take(conn.execute(f"SELECT {cols} FROM specimens WHERE id = ?", (int(i),)).fetchone(),
             f"specimen id {i}")
    for c in codes:
        rows = conn.execute(f"SELECT {cols} FROM specimens WHERE specimen_code = ?",
                            (c,)).fetchall()
        if not rows:
            out["missing"].append(f"specimen code {c}")
        for r in rows:
            take(r, c)
    for sid, oid in csv_pairs:
        r = conn.execute(f"SELECT {cols} FROM specimens WHERE id = ?", (sid,)).fetchone()
        if r is not None and r[2] is not None and int(r[2]) != oid:
            out["kept"].append((r, oid))
        else:
            take(r, f"specimen id {sid} (from the CSV)")
    out["unlink"] = list(out["unlink"].values())
    return out


def apply(conn, rows) -> list:
    """Clear the links, each guarded on the observation it had when planned."""
    done = []
    with conn:
        for r in rows:
            if conn.execute("UPDATE specimens SET observation_id = NULL WHERE id = ? "
                            "AND observation_id = ?", (r[0], r[2])).rowcount:
                done.append(r)
    return done


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--id", nargs="+", type=int, default=[], help="specimen id(s)")
    ap.add_argument("--code", nargs="+", default=[], help="specimen code(s)")
    ap.add_argument("--csv", nargs="+", default=[],
                    help="link script list(s) (specimen_links_set_<date_time>.csv)")
    ap.add_argument("--apply", action="store_true", help="write (after a backup)")
    ap.add_argument("--out", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--db", default=str(paths.OBSERVATUM_DB), help=argparse.SUPPRESS)
    ap.add_argument("--backup-dir", default=rc.BACKUP_DIR, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    if not (a.id or a.code or a.csv):
        ap.error("say which specimens: --id, --code or --csv")

    print("")
    print("Unlink specimens from their observation (specimens.observation_id)")
    print("=" * 74)
    print(f"  observatum.db: {a.db}")
    pairs = []
    for p in a.csv:
        got = read_set_csv(p)
        print(f"  {p}: {len(got):,} links listed")
        pairs += got
    ro = rc.connect_ro(a.db)
    try:
        found = plan(ro, a.id, a.code, pairs)
        before = ro.execute("SELECT COUNT(*) FROM specimens WHERE observation_id IS NOT NULL"
                            ).fetchone()[0]
    finally:
        ro.close()
    rows = found["unlink"]
    print(f"  specimens linked now: {before:,}")
    print(f"  links to clear: {len(rows):,}")
    for r in rows[:SAMPLES]:
        print(f"    specimen {r[0]:<6} {str(r[1] or ''):<12} {str(r[3] or '')[:30]:<30} "
              f"{r[4]} {r[5] or ''} -> observation {r[2]}")
    if len(rows) > SAMPLES:
        print(f"    ... and {len(rows) - SAMPLES:,} more")
    if found["kept"]:
        print(f"  kept, linked since to a different observation than the CSV says: "
              f"{len(found['kept']):,}")
        for r, oid in found["kept"][:SAMPLES]:
            print(f"    specimen {r[0]}: now observation {r[2]}, CSV says {oid}")
    if found["not_linked"]:
        print(f"  not linked already (nothing to do): {len(found['not_linked']):,}")
    for m in found["missing"]:
        print(f"  not found: {m}")

    if not a.apply:
        print("")
        print("DRY RUN. Nothing has been changed. Run with --apply to write.")
        return 0
    if not rows:
        print("  nothing to do. Nothing has been changed.")
        return 0
    print("")
    dest = rc.backup(a.db, "unlink_specimens", a.backup_dir)
    print(f"  backed up to {dest}")
    conn = rc.sqlite3.connect(a.db)
    try:
        done = apply(conn, rows)
        after = conn.execute("SELECT COUNT(*) FROM specimens WHERE observation_id IS NOT NULL"
                             ).fetchone()[0]
    finally:
        conn.close()
    stamp = datetime.now()
    out = a.out or os.path.join(rc.REPORT_DIR,
                                f"specimen_links_removed_{stamp:%Y%m%d_%H%M%S}.csv")
    rc.write_csv(out, REMOVED_HEADER, ([r[0], r[1], r[2], r[3], r[4], r[5],
                                        stamp.isoformat(timespec="seconds"), dest] for r in done))
    print(f"  links cleared: {len(done):,} of {len(rows):,}")
    print(f"  specimens linked: before {before:,}, after {after:,}")
    print(f"  the links cleared are listed in {out}")
    print("  done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
