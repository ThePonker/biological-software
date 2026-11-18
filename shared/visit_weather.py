"""Weather for each survey visit of a project (Round A, Nov 2026).

One row per project + client + date in observatum.db visit_weather (made by
scripts/add_report_tables.py). Text is stored as typed ("30-32 C", "Beaufort 1-2", "1-3 oktas").
Reading is read-only; saving is refused on an away machine or when the table is missing.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Dict, Iterable, List, Optional

import paths

FIELDS = ("temperature", "wind", "cloud", "notes")


def _ro():
    return sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)


def _has_table(conn) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='visit_weather'"
                        ).fetchone() is not None


def table_ready() -> bool:
    """True when visit_weather exists in observatum.db."""
    try:
        conn = _ro()
        try:
            return _has_table(conn)
        finally:
            conn.close()
    except sqlite3.Error:
        return False


def weather_for(project_name: str, client: str, dates: Optional[Iterable[str]] = None) -> Dict[str, Dict]:
    """date (ISO) -> {temperature, wind, cloud, notes}; {} if the table is missing."""
    try:
        conn = _ro()
    except sqlite3.Error:
        return {}
    try:
        if not _has_table(conn):
            return {}
        rows = conn.execute(
            "SELECT date, temperature, wind, cloud, notes FROM visit_weather "
            "WHERE project_name=? AND client=?", (project_name or "", client or "")).fetchall()
    except sqlite3.Error:
        return {}
    finally:
        conn.close()
    want = set(dates) if dates is not None else None
    return {r[0]: {"temperature": r[1] or "", "wind": r[2] or "", "cloud": r[3] or "",
                   "notes": r[4] or ""}
            for r in rows if want is None or r[0] in want}


def save_weather(project_name: str, client: str, rows: List[Dict]) -> int:
    """Upsert the rows (dicts: date, temperature, wind, cloud, notes) in one transaction.
    A row with all four text fields empty is skipped (an existing row is left alone).
    Raises RuntimeError, changing nothing, if the table is missing or this is an away machine.
    Returns the number of rows written."""
    from shared.away_mode import away_active
    if away_active():
        raise RuntimeError("Away machine: weather cannot be saved here.")
    if not table_ready():
        raise RuntimeError("visit_weather table is missing: run scripts\\add_report_tables.py --apply.")
    todo = [r for r in rows if any((r.get(f) or "").strip() for f in FIELDS)]
    if not todo:
        return 0
    now = datetime.now().isoformat(timespec="seconds")
    conn = sqlite3.connect(str(paths.OBSERVATUM_DB))
    try:
        with conn:
            for r in todo:
                conn.execute(
                    "INSERT INTO visit_weather (project_name, client, date, temperature, wind, "
                    "cloud, notes, updated_at) VALUES (?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(project_name, client, date) DO UPDATE SET "
                    "temperature=excluded.temperature, wind=excluded.wind, cloud=excluded.cloud, "
                    "notes=excluded.notes, updated_at=excluded.updated_at",
                    (project_name or "", client or "", r["date"],
                     *[(r.get(f) or "").strip() for f in FIELDS], now))
    finally:
        conn.close()
    return len(todo)
