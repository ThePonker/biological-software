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


# --- commercial projects: one job per project, reopened to add records ---------
# Examen and Commercial Reports group records by the exact project and client
# strings, so a job added to later must carry them exactly (8 Oct 2026).

def _norm_key(v) -> str:
    return " ".join(str(v or "").split()).casefold()


def known_projects(conn: sqlite3.Connection) -> List[Dict]:
    """[{project, client}] used anywhere -- committed records and jobs -- most frequent first."""
    seen: Dict[tuple, Dict] = {}

    def add(project, client, n):
        project = (project or "").strip()
        if not project:
            return
        key = (project, (client or "").strip())
        d = seen.setdefault(key, {"project": key[0], "client": key[1], "n": 0})
        d["n"] += n

    try:
        for p, c, n in conn.execute(
                "SELECT project_name, client, COUNT(*) FROM observations "
                "WHERE record_type='Commercial' GROUP BY project_name, client"):
            add(p, c, n)
    except sqlite3.Error:
        pass                      # a staging-only database (tests, dev copy)
    for p, c in conn.execute("SELECT project, client FROM entry_jobs WHERE mode='Commercial'"):
        add(p, c, 0)
    return sorted(seen.values(), key=lambda d: (-d["n"], d["project"].casefold()))


def canonical_name(typed: Optional[str], existing) -> Optional[str]:
    """The existing spelling when `typed` differs from one only by case or spacing."""
    t = " ".join(str(typed or "").split())
    if not t:
        return None
    for e in existing:
        if e and _norm_key(e) == _norm_key(t):
            return e
    return t


def find_project_job(conn: sqlite3.Connection, project: str, client: Optional[str]) -> Optional[Dict]:
    """The Commercial job for this exact project + client: an active one first, else the latest."""
    rows = conn.execute(
        "SELECT * FROM entry_jobs WHERE mode='Commercial' "
        "AND COALESCE(TRIM(project),'')=? AND COALESCE(TRIM(client),'')=? "
        "ORDER BY (status='active') DESC, updated_at DESC, id DESC",
        ((project or "").strip(), (client or "").strip())).fetchall()
    return dict(rows[0]) if rows else None


def reopen_job(conn: sqlite3.Connection, job_id: int) -> None:
    """Set a committed job back to active so more records can be entered under it.
    Its committed records stay in Observatum; the grid starts empty."""
    update_job(conn, job_id, status="active")


def open_project_job(conn: sqlite3.Connection, project: str, client: Optional[str],
                     embargo_until: Optional[str] = None):
    """(job_id, how) for adding records to a commercial project.

    how: 'open' (an active job exists), 'reopened' (a committed one was reopened) or
    'created' (no job yet -- e.g. records that came in by import). The job carries the
    project and client exactly as the records do; a current embargo is carried too.
    """
    job = find_project_job(conn, project, client)
    if job is None:
        job_id = create_job(conn, (project or "").strip(), "Commercial",
                            (client or "").strip() or None, (project or "").strip())
        how = "created"
    else:
        job_id = job["id"]
        how = "open"
        if (job.get("status") or "active") != "active":
            reopen_job(conn, job_id)
            how = "reopened"
    if embargo_until:
        update_job(conn, job_id, embargo_until=embargo_until)
    return job_id, how


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
