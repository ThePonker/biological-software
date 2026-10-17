"""copy_job_for_test.py -- copy a Data Entry job's rows into a new job for trying a feature.

    py -3.14 scripts\\copy_job_for_test.py                         # lists the jobs
    py -3.14 scripts\\copy_job_for_test.py --job "RWE Wales Coedely"   # dry run
    py -3.14 scripts\\copy_job_for_test.py --job "RWE Wales Coedely" --apply

Makes "TEST copy of <job>" holding copies of the job's rows marked to check (--all: every
row), with their marks and notes. Photos and specimens are NOT linked to the copies, so the
original job and the photo library are untouched. The test job can never be committed or
exported for iRecord (Data Entry refuses it); when finished, discard it in Data Entry (Discard
job). --job matches part of a job name; it must match one job. --apply only runs on
observatum.db and backs it up first (conn.backup). Close Observatum and Data Entry first.
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
from DataEntry import staging_repo as repo  # noqa: E402

try:
    from scripts import report_common as rc
except ImportError:                       # run as py scripts\<name>.py
    import report_common as rc

# copied as they are; job_id, row_order, id and the time stamps are the new job's own
SKIP = ("id", "job_id", "row_order", "created_at", "updated_at")


def find_jobs(conn, text):
    jobs = [j for j in repo.list_jobs(conn) if not repo.is_test_copy(j)]
    if not text:
        return jobs
    t = text.casefold()
    return [j for j in jobs if t in (j.get("name") or "").casefold()]


def rows_to_copy(conn, job_id, everything=False):
    rows = repo.fetch_rows(conn, job_id)
    return rows if everything else [r for r in rows if r.get("check_flag")]


def copy_rows(conn, job, rows) -> int:
    """Create the test job and copy `rows` into it (one transaction); returns the new job id."""
    with conn:
        new_id = repo.create_job(conn, repo.TEST_COPY_PREFIX + (job.get("name") or "job"),
                                 "Personal", commit=False)
        conn.execute("UPDATE entry_jobs SET notes=? WHERE id=?", (repo.TEST_COPY_NOTE, new_id))
        for r in rows:
            repo.insert_row(conn, new_id, {k: v for k, v in r.items() if k not in SKIP},
                            commit=False)
    return new_id


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--job", default="", help="part of the job's name")
    ap.add_argument("--all", action="store_true", help="every row, not only those marked to check")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--db", default=str(paths.OBSERVATUM_DB), help=argparse.SUPPRESS)
    ap.add_argument("--backup-dir", default=rc.BACKUP_DIR, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    print("\nData Entry: copy a job for testing")
    print("=" * 40)
    if a.apply and os.path.basename(str(a.db)).lower() != "observatum.db":
        print(f"  refusing: --apply only runs on observatum.db, not {os.path.basename(str(a.db))}. "
              "Nothing has been changed.")
        return 1
    ro = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    ro.row_factory = sqlite3.Row
    try:
        if not repo.has_check_columns(ro):
            print("  run scripts\\add_staging_check_columns.py first. Nothing has been changed.")
            return 1
        jobs = find_jobs(ro, a.job)
        if not a.job or len(jobs) != 1:
            print("  jobs:" if not a.job else f"  '{a.job}' matches {len(jobs)} job(s); it must match one:")
            for j in jobs:
                print(f"    {j['id']:>5}  {j.get('name')}  ({repo.row_count(ro, j['id'])} rows)")
            print("\nNothing has been changed.")
            return 0 if not a.job else 1
        job = jobs[0]
        rows = rows_to_copy(ro, job["id"], a.all)
        total = ro.execute("SELECT COUNT(*) FROM entry_staging").fetchone()[0]
    finally:
        ro.close()
    name = repo.TEST_COPY_PREFIX + (job.get("name") or "job")
    print(f"  from job: {job['id']}  {job.get('name')}")
    print(f"  rows to copy: {len(rows)} ({'all rows' if a.all else 'marked to check'})")
    for r in rows[:10]:
        print(f"    {r.get('species_name') or '?':<34} {r.get('date') or '':<11} "
              f"{(r.get('check_note') or '')[:30]}")
    print(f"  new job: {name}")
    if not rows:
        print("\nNo rows to copy. Nothing has been changed.")
        return 1
    if not a.apply:
        print("\nDRY RUN. Run with --apply to make the test job. Nothing has been changed.")
        return 0
    dest = rc.backup(a.db, "copy_job_for_test", a.backup_dir)
    print(f"  backed up to {dest}")
    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row
    try:
        new_id = copy_rows(conn, job, rows)
        n_new = repo.row_count(conn, new_id)
        n_old = len(rows_to_copy(conn, job["id"], a.all))
        total2 = conn.execute("SELECT COUNT(*) FROM entry_staging").fetchone()[0]
    finally:
        conn.close()
    ok = n_new == len(rows) and n_old == len(rows) and total2 == total + len(rows)
    print(f"  made job {new_id} with {n_new} row(s); the original job is unchanged "
          f"({n_old} rows {'marked' if not a.all else 'in all'}); staged rows {total:,} -> {total2:,}")
    print("  done. Open Data Entry and choose the job '" + name + "'." if ok
          else "  NOT as expected -- check the database.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
