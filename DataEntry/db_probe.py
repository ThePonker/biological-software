"""DB probe functions for DataEntry -- pure SQLite, NO Qt import.

Kept separate from the widget so the database logic can be unit-tested without a GUI
and so the read/write path has one clear home. Step 1 uses read-only functions only.
"""
from __future__ import annotations

import sqlite3


def table_columns(conn: sqlite3.Connection, table: str) -> set:
    """Return the set of column names for a table, or empty set if it doesn't exist."""
    try:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    except sqlite3.Error:
        return set()


def gather_proof_stats(conn: sqlite3.Connection) -> dict:
    """Read-only proof-of-life stats from the observations table.

    Defensive: checks column existence before each query so it can't crash on an
    unexpected schema. Issues no writes. Returns a dict:

        {
          "ok": bool,
          "error": str | None,
          "observations": int | None,
          "sites": int | None,
          "recorders": int | None,
          "by_type": {record_type: count, ...},
          "new_columns": {"sub_location": bool, "trap_number": bool, "visit_number": bool},
        }
    """
    stats = {
        "ok": False,
        "error": None,
        "observations": None,
        "sites": None,
        "recorders": None,
        "by_type": {},
        "new_columns": {},
    }
    try:
        cols = table_columns(conn, "observations")
        if not cols:
            stats["error"] = "no 'observations' table found"
            return stats

        stats["observations"] = conn.execute(
            "SELECT COUNT(*) FROM observations"
        ).fetchone()[0]

        if "site_name" in cols:
            stats["sites"] = conn.execute(
                "SELECT COUNT(DISTINCT site_name) FROM observations "
                "WHERE site_name IS NOT NULL AND site_name != ''"
            ).fetchone()[0]

        if "recorder" in cols:
            stats["recorders"] = conn.execute(
                "SELECT COUNT(DISTINCT recorder) FROM observations "
                "WHERE recorder IS NOT NULL AND recorder != ''"
            ).fetchone()[0]

        if "record_type" in cols:
            for rtype, n in conn.execute(
                "SELECT record_type, COUNT(*) FROM observations "
                "GROUP BY record_type ORDER BY record_type"
            ):
                stats["by_type"][rtype or "(blank)"] = n

        for c in ("sub_location", "trap_number", "visit_number"):
            stats["new_columns"][c] = c in cols

        stats["ok"] = True
    except sqlite3.Error as e:
        stats["error"] = str(e)
    return stats


def distinct_values(conn: sqlite3.Connection, column: str, limit: int = 500) -> list:
    """Distinct, non-blank values of an observations column, most-used first.

    Returns [] if the column doesn't exist. The column name is validated against the live
    table's actual columns before interpolation, so it cannot be an injection vector.
    Read-only.
    """
    cols = table_columns(conn, "observations")
    if column not in cols:
        return []
    try:
        rows = conn.execute(
            f"SELECT {column}, COUNT(*) AS n FROM observations "
            f"WHERE {column} IS NOT NULL AND TRIM({column}) != '' "
            f"GROUP BY {column} ORDER BY n DESC, {column} ASC LIMIT ?",
            (limit,),
        ).fetchall()
        return [r[0] for r in rows]
    except sqlite3.Error:
        return []
