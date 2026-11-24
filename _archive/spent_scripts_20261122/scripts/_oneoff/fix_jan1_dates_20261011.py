"""fix_jan1_dates_20261011.py -- year-only scheme records padded to 1 January.

    py -3.14 scripts\\_oneoff\\fix_jan1_dates_20261011.py            # dry run: report only
    py -3.14 scripts\\_oneoff\\fix_jan1_dates_20261011.py --apply    # back up, then write

Why
---
The NBN Atlas writes a year-only record as 1 January of its year, and the scheme import
(before 11 Oct 2026) stored that as an exact day (date type D). On the 10 Oct data copy
11,363 of the 110,510 recording_scheme records sit on 1 January as exact days, mostly from
a few NBN datasets, and they fill every January bar (Recording Scheme Monthly Distribution,
species phenology, the month list).

How a dataset is judged
-----------------------
For each dataset (dataset_name, else source), among its records with date type D (or none):
    on 1 Jan        records dated 1 January (any year)
    other-Jan avg   records dated 2-31 January, divided by 30 (an ordinary January day)
A dataset is PADDING when  on-1-Jan >= MIN_RECORDS (20)  and
                           on-1-Jan > RATIO (20) x other-Jan avg   (avg 0 counts as passing).
A real New Year's Day count is a few times an ordinary January day at most; padding is
hundreds or thousands of times. Left alone and listed: GENUINE (1 Jan no more than 5x an
ordinary January day), UNCLEAR (20 or more, between 5x and 20x) and TOO FEW (under 20 on
1 January -- too few to judge, though most look like padding too).

What it changes
---------------
recording_scheme rows of the PADDING datasets dated 1 January with date type D or blank:
    date_type     D -> Y (a year: the date '1985-01-01' is kept, as the suite stores a year)
    import_notes  a note appended saying what was changed and why
    updated_at    now
Nothing else. observations and specimens are not touched (their 1 January records are Wil's
own -- see the report). Each UPDATE is guarded (only a row still dated 1 Jan with type D or
blank changes), so running it twice changes nothing the second time.

--apply backs observatum.db up with SQLite's backup API into
C:\\BiologicalSoftware_Backups\\reference\\ first, then writes in one transaction. Run it with
the apps closed.
"""
import argparse
import os
import sqlite3
import sys
from datetime import datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (_ROOT, os.path.join(_ROOT, "Observatum")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import paths  # noqa: E402

MIN_RECORDS = 20
RATIO = 20
UNCLEAR_RATIO = 5
BACKUP_DIR = os.path.join(r"C:\BiologicalSoftware_Backups", "reference")
TODAY = datetime.now().strftime("%Y-%m-%d")
NOTE = (f"[Date type corrected {TODAY}: 1 January in a dataset that writes year-only "
        f"records as 1 January; date type D -> Y (year)]")

DATASET = "COALESCE(NULLIF(TRIM(dataset_name), ''), source, '(no dataset)')"
EXACT = "COALESCE(NULLIF(date_type, ''), 'D') = 'D'"
JAN1 = "substr(date, 6, 5) = '01-01' AND length(date) >= 10"


def survey(conn) -> list:
    """Per dataset with any 1 January record: dict(dataset, jan1, other_jan, avg, ratio, verdict)."""
    rows = conn.execute(f"""
        SELECT {DATASET} AS ds,
               SUM({JAN1}) AS jan1,
               SUM(substr(date, 6, 2) = '01' AND substr(date, 9, 2) <> '01'
                   AND length(date) >= 10) AS other_jan
        FROM recording_scheme
        WHERE {EXACT} AND date IS NOT NULL
        GROUP BY ds HAVING jan1 > 0
        ORDER BY jan1 DESC, ds""").fetchall()
    out = []
    for ds, jan1, other in rows:
        avg = (other or 0) / 30
        ratio = (jan1 / avg) if avg else float("inf")
        if ratio <= UNCLEAR_RATIO:
            verdict = "genuine"
        elif jan1 < MIN_RECORDS:
            verdict = "too few"
        elif ratio > RATIO:
            verdict = "padding"
        else:
            verdict = "unclear"
        out.append({"dataset": ds, "jan1": jan1, "other_jan": other or 0, "avg": avg,
                    "ratio": ratio, "verdict": verdict})
    return out


def report(found: list) -> int:
    print(f"  Rule: PADDING when on-1-Jan >= {MIN_RECORDS} and on-1-Jan > {RATIO} x the "
          f"average other January day")
    print(f"        (records dated 2-31 Jan / 30). Left alone: GENUINE (<= {UNCLEAR_RATIO}x), "
          f"UNCLEAR ({UNCLEAR_RATIO}x-{RATIO}x), TOO FEW (< {MIN_RECORDS} on 1 Jan).")
    print("")
    print(f"  {'dataset':62} {'1 Jan':>6} {'Jan avg':>8} {'ratio':>7}  verdict   change")
    print("  " + "-" * 104)
    total = 0
    for f in found:
        ratio = "-" if f["ratio"] == float("inf") else f"{f['ratio']:.0f}x"
        change = f"{f['jan1']:,} D -> Y" if f["verdict"] == "padding" else "none"
        if f["verdict"] == "padding":
            total += f["jan1"]
        print(f"  {f['dataset'][:62]:62} {f['jan1']:6,} {f['avg']:8.2f} {ratio:>7}  "
              f"{f['verdict']:8}  {change}")
    left = [f for f in found if f["verdict"] != "padding"]
    print("")
    print(f"  padding datasets: {sum(f['verdict'] == 'padding' for f in found)}, "
          f"records to change: {total:,}")
    print(f"  left alone: {len(left)} datasets, {sum(f['jan1'] for f in left):,} records on "
          f"1 January:")
    for v in ("unclear", "too few", "genuine"):
        some = [f for f in left if f["verdict"] == v]
        print(f"      {v:8} {len(some):3} datasets, {sum(f['jan1'] for f in some):,} records")
    return total


def month_totals(conn) -> list:
    """The scheme Monthly Distribution as the Stats tab counts it (day dates only)."""
    got = dict(conn.execute(f"""
        SELECT CAST(strftime('%m', date) AS INTEGER), COUNT(*) FROM recording_scheme
        WHERE date IS NOT NULL AND {EXACT} GROUP BY 1""").fetchall())
    return [got.get(m, 0) for m in range(1, 13)]


def backup(db_path, backup_dir=BACKUP_DIR) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    dest = os.path.join(backup_dir, f"observatum_pre_fix_jan1_dates_{stamp}.db")
    os.makedirs(backup_dir, exist_ok=True)
    if os.path.exists(dest):
        raise FileExistsError(f"backup already exists: {dest}")
    src = sqlite3.connect(str(db_path))
    d = sqlite3.connect(dest)
    try:
        src.backup(d)
    finally:
        d.close()
        src.close()
    return dest


def apply(conn, found: list) -> int:
    names = [f["dataset"] for f in found if f["verdict"] == "padding"]
    if not names:
        return 0
    marks = ",".join("?" * len(names))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with conn:
        n = conn.execute(f"""
            UPDATE recording_scheme
            SET date_type = 'Y',
                import_notes = CASE WHEN COALESCE(import_notes, '') = '' THEN ?
                                    ELSE import_notes || ' ' || ? END,
                updated_at = ?
            WHERE {JAN1} AND {EXACT} AND {DATASET} IN ({marks})""",
                         (NOTE, NOTE, now, *names)).rowcount
    return n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Year-only scheme records padded to 1 January")
    ap.add_argument("--apply", action="store_true", help="write (after a backup)")
    ap.add_argument("--db", default=str(paths.OBSERVATUM_DB), help=argparse.SUPPRESS)
    ap.add_argument("--backup-dir", default=BACKUP_DIR, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)

    print("")
    print("1 January placeholder dates in recording_scheme -- " + ("APPLY" if a.apply else "DRY RUN"))
    print("=" * 106)
    print(f"  observatum.db: {a.db}")
    ro = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    try:
        n_all = ro.execute("SELECT COUNT(*) FROM recording_scheme").fetchone()[0]
        n_jan1 = ro.execute(f"SELECT COUNT(*) FROM recording_scheme WHERE {JAN1} AND {EXACT}"
                            ).fetchone()[0]
        print(f"  {n_jan1:,} of {n_all:,} scheme records are dated 1 January as an exact day")
        print("")
        found = survey(ro)
        months = month_totals(ro)
    finally:
        ro.close()
    total = report(found)
    after_jan = months[0] - total
    print("")
    print(f"  Monthly Distribution, January (day dates, all families, before the counting "
          f"switches): {months[0]:,} now, {after_jan:,} after")
    if not a.apply:
        print("")
        print("DRY RUN. Nothing has been changed. Run with --apply to write.")
        return 0
    if not total:
        print("  nothing to do. Nothing has been changed.")
        return 0
    dest = backup(a.db, a.backup_dir)
    print(f"  backed up to {dest}")
    conn = sqlite3.connect(a.db)
    try:
        done = apply(conn, found)
        left = sum(f["jan1"] for f in survey(conn) if f["verdict"] == "padding")
        jan = month_totals(conn)[0]
    finally:
        conn.close()
    print(f"  updated {done:,} records (expected {total:,}); padding left: {left} (should be 0)")
    print(f"  Monthly Distribution, January now {jan:,}")
    print("  done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
