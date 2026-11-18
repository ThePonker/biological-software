"""add_report_tables.py -- add the tables the report tools use (Round A, Nov 2026).

    py -3.14 scripts\\add_report_tables.py            # dry run: says what it would add
    py -3.14 scripts\\add_report_tables.py --apply    # backup, then add them

observatum.db gets
    visit_weather          weather for each survey date of a project (typed in Data Entry):
                           temperature, wind, cloud as short text ("30-32 °C", "Beaufort 1-2",
                           "1-3 oktas"), one row per project + client + date.
examen.db gets
    status_downgrades           species whose published status is out of date and likely to be
                                downgraded on review (the [square brackets]), with a reason.
                                Applies to every job.
    status_downgrade_overrides  a job's exception to that list: bracket = 1 brackets a species
                                there only, bracket = 0 leaves a listed species unbracketed there.
    benchmark_choices           which surveys count in the author's Key Species benchmark
                                (included 1 / 0); surveys with no row follow the default rule.

Only new, empty tables: nothing existing is changed. Safe to run twice (a table already there is
left alone). --apply backs up each database it changes first (conn.backup). Close Observatum,
Data Entry and Examen before --apply.
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

OBSERVATUM_TABLES = {
    "visit_weather": """CREATE TABLE visit_weather (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_name TEXT NOT NULL,
        client TEXT NOT NULL DEFAULT '',
        date TEXT NOT NULL,
        temperature TEXT NOT NULL DEFAULT '',
        wind TEXT NOT NULL DEFAULT '',
        cloud TEXT NOT NULL DEFAULT '',
        notes TEXT NOT NULL DEFAULT '',
        updated_at TEXT,
        UNIQUE(project_name, client, date))""",
}

EXAMEN_TABLES = {
    "status_downgrades": """CREATE TABLE status_downgrades (
        tvk TEXT PRIMARY KEY,
        species_name TEXT NOT NULL,
        reason TEXT NOT NULL DEFAULT '',
        created_at TEXT,
        updated_at TEXT)""",
    "status_downgrade_overrides": """CREATE TABLE status_downgrade_overrides (
        project_name TEXT NOT NULL,
        client TEXT NOT NULL DEFAULT '',
        survey_year TEXT NOT NULL DEFAULT '',
        tvk TEXT NOT NULL,
        species_name TEXT NOT NULL DEFAULT '',
        bracket INTEGER NOT NULL,
        updated_at TEXT,
        PRIMARY KEY(project_name, client, survey_year, tvk))""",
    "benchmark_choices": """CREATE TABLE benchmark_choices (
        project_name TEXT NOT NULL,
        client TEXT NOT NULL DEFAULT '',
        survey_year TEXT NOT NULL DEFAULT '',
        included INTEGER NOT NULL,
        updated_at TEXT,
        PRIMARY KEY(project_name, client, survey_year))""",
}


def missing_tables(conn, wanted) -> list:
    have = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return [t for t in wanted if t not in have]


def _plan(db, wanted, label):
    if not os.path.exists(db):
        print(f"  {label}: not found at {db}. Nothing has been changed.")
        return None
    ro = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        todo = missing_tables(ro, wanted)
    finally:
        ro.close()
    if not todo:
        print(f"  {label}: all tables there already.")
    for t in todo:
        print(f"  {label}: would add table {t}")
    return todo


def _backup(db, backup_dir):
    """rc.backup for observatum.db (its usual name); the same conn.backup() for examen.db, but
    named examen_pre_... so the file says which database it holds."""
    if os.path.basename(str(db)).lower() == "observatum.db":
        return rc.backup(db, "add_report_tables", backup_dir)
    from datetime import datetime
    from shared.away_mode import away_active
    if away_active():
        raise RuntimeError("away mode: this is a read-only copy; nothing may be changed or backed up here")
    stem = os.path.splitext(os.path.basename(str(db)))[0]
    dest = os.path.join(backup_dir, f"{stem}_pre_add_report_tables_{datetime.now():%Y%m%d_%H%M%S_%f}.db")
    os.makedirs(backup_dir, exist_ok=True)
    if os.path.exists(dest):
        raise FileExistsError(f"backup already exists: {dest}")
    src, d = sqlite3.connect(str(db)), sqlite3.connect(dest)
    try:
        src.backup(d)
    finally:
        d.close()
        src.close()
    return dest


def _apply(db, wanted, todo, label, backup_dir):
    dest = _backup(db, backup_dir)
    print(f"  {label}: backed up to {dest}")
    conn = sqlite3.connect(db)
    try:
        with conn:
            for t in missing_tables(conn, wanted):
                conn.execute(wanted[t])
        left = missing_tables(conn, wanted)
    finally:
        conn.close()
    print(f"  {label}: added {len(todo) - len(left)} table(s)" + ("" if not left else f"; MISSING {left}"))
    return not left


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--observatum-db", default=str(paths.OBSERVATUM_DB), help=argparse.SUPPRESS)
    ap.add_argument("--examen-db", default=str(paths.EXAMEN_DB), help=argparse.SUPPRESS)
    ap.add_argument("--backup-dir", default=rc.BACKUP_DIR, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    print("\nReport tables (visit weather, status brackets, benchmark)")
    print("=" * 40)
    jobs = [(a.observatum_db, OBSERVATUM_TABLES, "observatum.db"),
            (a.examen_db, EXAMEN_TABLES, "examen.db")]
    plans = [(db, wanted, label, _plan(db, wanted, label)) for db, wanted, label in jobs]
    if any(todo is None for *_, todo in plans):
        return 1
    if not any(todo for *_, todo in plans):
        print("\nNothing to add. Nothing has been changed.")
        return 0
    if not a.apply:
        print("\nDRY RUN. Run with --apply to add them. Nothing has been changed.")
        return 0
    ok = all(_apply(db, wanted, todo, label, a.backup_dir)
             for db, wanted, label, todo in plans if todo)
    print("  done." if ok else "  NOT as expected -- check the databases.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
