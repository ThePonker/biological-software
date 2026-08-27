"""Staging repository for the data-entry grid -- pure sqlite, NO Qt import.

CRUD over entry_jobs (the durable named-jobs registry) and entry_staging (in-progress rows).
Connection-based so it's unit-testable without a GUI. Includes ensure_schema (idempotent
self-heal, same DDL as scripts/add_entry_staging.py) and ensure_personal_job.
"""
from __future__ import annotations

import sqlite3
from typing import List, Dict, Optional

PERSONAL_JOB_NAME = "Personal"

_CREATE_JOBS = """
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

_CREATE_STAGING = """
CREATE TABLE IF NOT EXISTS entry_staging (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    row_order INTEGER,
    species_name TEXT, species_tvk TEXT, common_name TEXT, order_name TEXT, family TEXT, taxon_rank TEXT,
    stage TEXT, sex TEXT, quantity INTEGER,
    determiner TEXT, sub_location TEXT, trap_number TEXT, visit_number TEXT,
    date TEXT, site_name TEXT, grid_ref TEXT, vice_county TEXT, vc_number INTEGER,
    recorder TEXT, method TEXT, certainty TEXT, comment TEXT,
    project_name TEXT, client TEXT, embargo_until TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES entry_jobs(id)
);
"""

_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_entry_staging_job ON entry_staging(job_id);",
    "CREATE INDEX IF NOT EXISTS idx_entry_jobs_status ON entry_jobs(status);",
)


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Idempotently create the staging tables/indexes if absent (self-heal)."""
    conn.execute(_CREATE_JOBS)
    conn.execute(_CREATE_STAGING)
    for idx in _INDEXES:
        conn.execute(idx)
    conn.commit()


def ensure_personal_job(conn: sqlite3.Connection) -> int:
    """Guarantee a canonical Personal job exists; return its id."""
    row = conn.execute(
        "SELECT id FROM entry_jobs WHERE name=? AND mode='Personal' AND status='active' "
        "ORDER BY id LIMIT 1",
        (PERSONAL_JOB_NAME,),
    ).fetchone()
    if row:
        return row[0]
    return create_job(conn, PERSONAL_JOB_NAME, "Personal")


def create_job(conn: sqlite3.Connection, name: str, mode: str,
               client: Optional[str] = None, project: Optional[str] = None) -> int:
    cur = conn.execute(
        "INSERT INTO entry_jobs (name, mode, client, project) VALUES (?,?,?,?)",
        (name.strip(), mode.strip() or "Personal", (client or None), (project or None)),
    )
    conn.commit()
    return cur.lastrowid


def get_job(conn: sqlite3.Connection, job_id: int) -> Optional[Dict]:
    r = conn.execute("SELECT * FROM entry_jobs WHERE id=?", (job_id,)).fetchone()
    return dict(r) if r else None


def update_job(conn: sqlite3.Connection, job_id: int, **fields) -> None:
    allowed = {"name", "mode", "client", "project", "embargo_until", "status", "notes"}
    sets = {k: v for k, v in fields.items() if k in allowed}
    if not sets:
        return
    cols = ", ".join(f"{k}=?" for k in sets)
    conn.execute(
        f"UPDATE entry_jobs SET {cols}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (*sets.values(), job_id),
    )
    conn.commit()


def touch_job(conn: sqlite3.Connection, job_id: int) -> None:
    conn.execute("UPDATE entry_jobs SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (job_id,))
    conn.commit()


def row_count(conn: sqlite3.Connection, job_id: int) -> int:
    return conn.execute("SELECT COUNT(*) FROM entry_staging WHERE job_id=?", (job_id,)).fetchone()[0]


def delete_job(conn: sqlite3.Connection, job_id: int) -> None:
    """Hard-delete a job and its staging rows."""
    conn.execute("DELETE FROM entry_staging WHERE job_id=?", (job_id,))
    conn.execute("DELETE FROM entry_jobs WHERE id=?", (job_id,))
    conn.commit()


def is_personal(job: Dict) -> bool:
    return (job.get("name") == PERSONAL_JOB_NAME) and (job.get("mode") == "Personal")


def list_jobs(conn: sqlite3.Connection, include_done: bool = False) -> List[Dict]:
    """Active jobs (canonical Personal pinned first, then most-recently-edited), with row counts."""
    where = "" if include_done else "WHERE j.status='active'"
    rows = conn.execute(
        f"""
        SELECT j.*, COALESCE(c.n, 0) AS row_count
        FROM entry_jobs j
        LEFT JOIN (SELECT job_id, COUNT(*) AS n FROM entry_staging GROUP BY job_id) c
          ON c.job_id = j.id
        {where}
        """
    ).fetchall()
    jobs = [dict(r) for r in rows]
    jobs.sort(key=lambda j: ((j.get("updated_at") or ""), j.get("id") or 0), reverse=True)
    jobs.sort(key=lambda j: 0 if is_personal(j) else 1)  # Personal pinned (stable)
    return jobs


# --- staging rows (grid) -----------------------------------------------------

# Columns the grid may edit + persist (guards update_row against typos/unknown keys).
STAGING_EDITABLE = [
    "species_name", "species_tvk", "common_name", "order_name", "family", "taxon_rank",
    "stage", "sex", "quantity",
    "determiner", "sub_location", "trap_number", "visit_number",
    "date", "site_name", "grid_ref", "vice_county", "vc_number",
    "recorder", "method", "certainty", "comment",
]


def fetch_rows(conn: sqlite3.Connection, job_id: int) -> List[Dict]:
    rows = conn.execute(
        "SELECT * FROM entry_staging WHERE job_id=? ORDER BY COALESCE(row_order, id), id",
        (job_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def insert_row(conn: sqlite3.Connection, job_id: int, data: Optional[Dict] = None) -> int:
    data = {k: v for k, v in (data or {}).items() if k in STAGING_EDITABLE}
    next_order = conn.execute(
        "SELECT COALESCE(MAX(row_order), 0) + 1 FROM entry_staging WHERE job_id=?", (job_id,)
    ).fetchone()[0]
    cols = ["job_id", "row_order"] + list(data.keys())
    vals = [job_id, next_order] + list(data.values())
    ph = ",".join("?" for _ in cols)
    cur = conn.execute(f"INSERT INTO entry_staging ({','.join(cols)}) VALUES ({ph})", vals)
    conn.commit()
    return cur.lastrowid


def update_row(conn: sqlite3.Connection, row_id: int, data: Dict) -> None:
    sets = {k: v for k, v in data.items() if k in STAGING_EDITABLE}
    if not sets:
        return
    cols = ", ".join(f"{k}=?" for k in sets)
    conn.execute(
        f"UPDATE entry_staging SET {cols}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (*sets.values(), row_id),
    )
    conn.commit()


def delete_row(conn: sqlite3.Connection, row_id: int) -> None:
    conn.execute("DELETE FROM entry_staging WHERE id=?", (row_id,))
    conn.commit()
