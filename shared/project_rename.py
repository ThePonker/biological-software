"""project_rename -- change a commercial project's name or client everywhere, in one place.

A commercial survey is identified by its (project_name, client) pair in three tables:
observations, contributed_observations (a collaborator's records for the same survey)
and the Data Entry jobs (entry_jobs). Examen and Commercial Reports group by the exact
pair, so a rename must change all three together or the project splits. Used by
Commercial Reports' "Edit project / client" (8 Oct 2026). Pure sqlite, no Qt.

    counts = plan(conn, "Glory Park", "BAM")            # what would change
    n = rename(conn, ("Glory Park", "BAM"), ("BAM Glory Park", "Nicholsons"))
"""
from __future__ import annotations

import sqlite3
from typing import Dict, Tuple

# table -> (project column, client column, extra condition)
TARGETS = {
    "observations": ("project_name", "client", "record_type = 'Commercial'"),
    "contributed_observations": ("project_name", "client", "1 = 1"),
    "entry_jobs": ("project", "client", "mode = 'Commercial'"),
}


def _tables(conn: sqlite3.Connection):
    have = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return [t for t in TARGETS if t in have]


def _where(table):
    p, c, extra = TARGETS[table]
    return f"{extra} AND COALESCE(TRIM({p}),'') = ? AND COALESCE(TRIM({c}),'') = ?"


def plan(conn: sqlite3.Connection, project: str, client: str) -> Dict[str, int]:
    """{table: rows carrying this exact project + client}."""
    key = ((project or "").strip(), (client or "").strip())
    return {t: conn.execute(f"SELECT COUNT(*) FROM {t} WHERE {_where(t)}", key).fetchone()[0]
            for t in _tables(conn)}


def rename(conn: sqlite3.Connection, old: Tuple[str, str], new: Tuple[str, str]) -> Dict[str, int]:
    """Set project and client from `old` to `new` in every table, in one transaction.

    Blank client is stored as NULL. Returns {table: rows changed}. Raises ValueError for a
    blank new project; the caller backs up first and confirms with the user.
    """
    new_p = " ".join(str(new[0] or "").split())
    new_c = " ".join(str(new[1] or "").split()) or None
    if not new_p:
        raise ValueError("a commercial project needs a name")
    key = ((old[0] or "").strip(), (old[1] or "").strip())
    done = {}
    with conn:
        for t in _tables(conn):
            p, c, _ = TARGETS[t]
            done[t] = conn.execute(f"UPDATE {t} SET {p} = ?, {c} = ? WHERE {_where(t)}",
                                   (new_p, new_c, *key)).rowcount
    return done
