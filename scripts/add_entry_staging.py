"""Add the data-entry staging tables (entry_jobs, entry_staging) to an EXISTING database.

ADDITIVE and IDEMPOTENT: uses CREATE TABLE IF NOT EXISTS, so it never touches existing rows
and is safe to re-run. This is how the tables reach a live/dev observatum.db WITHOUT the
destructive reset_database.py.

Keep the CREATE statements below in sync with scripts/reset_database.py
(CREATE_ENTRY_JOBS / CREATE_ENTRY_STAGING) -- the audit at the end checks both tables exist.

Usage:
    python scripts/add_entry_staging.py                 # newest data/observatum_dev_*.db, else live
    python scripts/add_entry_staging.py --db PATH       # explicit database
"""
import argparse
import glob
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    import paths
    DATA_DIR = str(paths.DATA_DIR)
    LIVE_DB = str(paths.OBSERVATUM_DB)
except Exception:
    DATA_DIR = os.path.join(os.getcwd(), "data")
    LIVE_DB = os.path.join(DATA_DIR, "observatum.db")


CREATE_ENTRY_JOBS = """
CREATE TABLE IF NOT EXISTS entry_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    mode TEXT DEFAULT 'Personal',
    client TEXT,
    project TEXT,
    embargo_until TEXT,
    status TEXT DEFAULT 'active',
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_ENTRY_STAGING = """
CREATE TABLE IF NOT EXISTS entry_staging (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    row_order INTEGER,
    species_name TEXT,
    species_tvk TEXT,
    common_name TEXT,
    order_name TEXT,
    family TEXT,
    taxon_rank TEXT,
    stage TEXT,
    sex TEXT,
    quantity INTEGER,
    determiner TEXT,
    sub_location TEXT,
    trap_number TEXT,
    visit_number TEXT,
    date TEXT,
    site_name TEXT,
    grid_ref TEXT,
    vice_county TEXT,
    vc_number INTEGER,
    recorder TEXT,
    method TEXT,
    certainty TEXT,
    comment TEXT,
    project_name TEXT,
    client TEXT,
    embargo_until TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES entry_jobs(id)
);
"""

CREATE_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_entry_staging_job ON entry_staging(job_id);",
    "CREATE INDEX IF NOT EXISTS idx_entry_jobs_status ON entry_jobs(status);",
)

EXPECTED_STAGING_COLS = {
    "id", "job_id", "row_order", "species_name", "species_tvk", "common_name", "order_name",
    "family", "taxon_rank", "stage", "sex", "quantity", "determiner", "sub_location",
    "trap_number", "visit_number", "date", "site_name", "grid_ref", "vice_county", "vc_number",
    "recorder", "method", "certainty", "comment", "project_name", "client", "embargo_until",
    "created_at", "updated_at",
}


def resolve_default_db() -> str:
    dev = sorted(glob.glob(os.path.join(DATA_DIR, "observatum_dev_*.db")))
    return dev[-1] if dev else LIVE_DB


def audit(conn: sqlite3.Connection) -> bool:
    ok = True
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for t in ("entry_jobs", "entry_staging"):
        present = t in tables
        print(f"  {t:16s} {'PRESENT' if present else 'MISSING <<<'}")
        ok = ok and present
    if "entry_staging" in tables:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(entry_staging)")}
        missing = EXPECTED_STAGING_COLS - cols
        if missing:
            print(f"  entry_staging missing columns: {sorted(missing)} <<<")
            ok = False
        else:
            print(f"  entry_staging columns: {len(cols)} (all expected present)")
    return ok


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Add entry_jobs + entry_staging to an existing DB (additive).")
    parser.add_argument("--db", default=None, help="Path to the database (default: newest dev copy, else live).")
    args = parser.parse_args(argv)

    db_path = args.db or resolve_default_db()
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return 1

    is_live = os.path.basename(db_path).lower() == "observatum.db"
    print("=" * 60)
    print("ADD DATA-ENTRY STAGING TABLES (additive, idempotent)")
    print("=" * 60)
    print(f"Target: {db_path}" + ("   [LIVE DATABASE]" if is_live else "   [dev copy]"))

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(CREATE_ENTRY_JOBS)
        conn.execute(CREATE_ENTRY_STAGING)
        for idx in CREATE_INDEXES:
            conn.execute(idx)
        conn.commit()
        print("\nApplied CREATE TABLE IF NOT EXISTS (+ indexes). No existing rows touched.")
        print("\n[Audit]")
        ok = audit(conn)
    finally:
        conn.close()

    print("\n" + ("DONE - staging tables present." if ok else "PROBLEM - see MISSING markers above."))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
