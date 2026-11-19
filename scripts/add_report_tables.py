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

It also adds a missing COLUMN to a table already there (ALTER TABLE ... ADD COLUMN, only when
missing): status_marked on both status tables, the status a mark was made against, '' on marks
saved before it existed (shown as "status not recorded"; they still apply).

Only new, empty tables and new columns: no existing row or value is changed. Safe to run twice (a
table or column already there is left alone). --apply backs up each database it changes first (conn.backup). Close Observatum,
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
        status_marked TEXT NOT NULL DEFAULT '',
        created_at TEXT,
        updated_at TEXT)""",
    "status_downgrade_overrides": """CREATE TABLE status_downgrade_overrides (
        project_name TEXT NOT NULL,
        client TEXT NOT NULL DEFAULT '',
        survey_year TEXT NOT NULL DEFAULT '',
        tvk TEXT NOT NULL,
        species_name TEXT NOT NULL DEFAULT '',
        bracket INTEGER NOT NULL,
        status_marked TEXT NOT NULL DEFAULT '',
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


# Columns added to tables that may already exist without them: {table: {column: definition}}.
EXAMEN_COLUMNS = {
    "status_downgrades": {"status_marked": "TEXT NOT NULL DEFAULT ''"},
    "status_downgrade_overrides": {"status_marked": "TEXT NOT NULL DEFAULT ''"},
}


def missing_columns(conn, wanted_columns) -> list:
    """[(table, column)] for tables that exist but lack a wanted column."""
    out = []
    for table, cols in wanted_columns.items():
        have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        if have:
            out += [(table, c) for c in cols if c not in have]
    return out


def missing_tables(conn, wanted) -> list:
    have = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return [t for t in wanted if t not in have]


def _plan(db, wanted, label, columns=None):
    """The tables and (table, column) pairs that are missing; None when the database is absent."""
    if not os.path.exists(db):
        print(f"  {label}: not found at {db}. Nothing has been changed.")
        return None
    ro = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        todo = missing_tables(ro, wanted) + missing_columns(ro, columns or {})
    finally:
        ro.close()
    if not todo:
        print(f"  {label}: all tables and columns there already.")
    for t in todo:
        print(f"  {label}: would add table {t}" if isinstance(t, str)
              else f"  {label}: would add column {t[1]} to {t[0]}")
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


def _apply(db, wanted, todo, label, backup_dir, columns=None):
    dest = _backup(db, backup_dir)
    print(f"  {label}: backed up to {dest}")
    columns = columns or {}
    conn = sqlite3.connect(db)
    try:
        with conn:
            for t in missing_tables(conn, wanted):
                conn.execute(wanted[t])
            for table, col in missing_columns(conn, columns):   # after the tables: new ones have it
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {columns[table][col]}")
        left = missing_tables(conn, wanted) + missing_columns(conn, columns)
    finally:
        conn.close()
    n_tables = sum(1 for t in todo if isinstance(t, str))
    left_tables = [x for x in left if isinstance(x, str)]
    print(f"  {label}: added {n_tables - len(left_tables)} table(s), "
          f"{len(todo) - n_tables - (len(left) - len(left_tables))} column(s)"
          + ("" if not left else f"; MISSING {left}"))
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
    jobs = [(a.observatum_db, OBSERVATUM_TABLES, "observatum.db", None),
            (a.examen_db, EXAMEN_TABLES, "examen.db", EXAMEN_COLUMNS)]
    plans = [(db, wanted, label, _plan(db, wanted, label, cols), cols)
             for db, wanted, label, cols in jobs]
    if any(todo is None for _, _, _, todo, _ in plans):
        return 1
    if not any(todo for _, _, _, todo, _ in plans):
        print("\nNothing to add. Nothing has been changed.")
        return 0
    if not a.apply:
        print("\nDRY RUN. Run with --apply to add them. Nothing has been changed.")
        return 0
    ok = all(_apply(db, wanted, todo, label, a.backup_dir, cols)
             for db, wanted, label, todo, cols in plans if todo)
    print("  done." if ok else "  NOT as expected -- check the databases.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
