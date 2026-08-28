"""csv_backup -- rolling CSV safety net for staging and observations.

A defence against database-level accidents (corruption, a bad script, a mistaken
bulk delete) that SQLite's WAL durability cannot cover. Not a substitute for the
pre-live .db backups; a complement to them.

Writes four files to BACKUP_DIR, overwritten in place -- no growing folder:

    staging_backup.csv          all entry_staging rows, all jobs, with job name
    staging_backup_prev.csv     the version before that
    observations_backup.csv     the observations table
    observations_backup_prev.csv

Every write goes to a temp file and is renamed over the target, so an interrupted
write cannot destroy the good copy. The previous version is rotated first, so a
corrupt write still leaves one readable generation behind.

Call sites (see wiring in entry_grid / data_entry_widget):
    backup_staging(conn)        -- on a timer, on job close, on tab close
    backup_observations(path)   -- after a commit
"""
from __future__ import annotations

import csv
import os
import sqlite3
import traceback
from datetime import datetime
from typing import Optional

BACKUP_DIR = r"C:\BiologicalSoftware_Backups"

STAGING_FILE = "staging_backup.csv"
OBSERVATIONS_FILE = "observations_backup.csv"


def _ensure_dir() -> Optional[str]:
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        return BACKUP_DIR
    except OSError as e:
        print(f"[DataEntry] CSV backup directory unavailable: {e}")
        return None


def _write_rows(filename: str, header, rows) -> Optional[str]:
    """Rotate previous, write temp, rename over target. Returns path or None."""
    d = _ensure_dir()
    if d is None:
        return None

    target = os.path.join(d, filename)
    stem, ext = os.path.splitext(filename)
    previous = os.path.join(d, f"{stem}_prev{ext}")
    temp = os.path.join(d, f"{stem}.tmp")

    try:
        with open(temp, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh)
            w.writerow(header)
            w.writerows(rows)
    except Exception:
        print("[DataEntry] CSV backup failed while writing temp file:")
        traceback.print_exc()
        return None

    try:
        if os.path.exists(target):
            if os.path.exists(previous):
                os.remove(previous)
            os.replace(target, previous)   # keep one generation back
        os.replace(temp, target)           # atomic on Windows
    except OSError:
        print("[DataEntry] CSV backup failed while rotating files:")
        traceback.print_exc()
        return None

    return target


def backup_staging(conn: sqlite3.Connection) -> Optional[str]:
    """Every entry_staging row, all jobs, with the job name and mode alongside."""
    try:
        cur = conn.execute(
            """SELECT j.name AS job_name, j.mode AS job_mode, s.*
               FROM entry_staging s
               LEFT JOIN entry_jobs j ON j.id = s.job_id
               ORDER BY s.job_id, s.row_order"""
        )
        header = [d[0] for d in cur.description]
        rows = cur.fetchall()
    except sqlite3.Error as e:
        print(f"[DataEntry] CSV backup could not read staging: {e}")
        return None

    path = _write_rows(STAGING_FILE, header, rows)
    if path:
        stamp = datetime.now().strftime("%H:%M:%S")
        print(f"[DataEntry] staging backed up ({len(rows)} rows) at {stamp}")
    return path


def backup_observations(db_path: str) -> Optional[str]:
    """The observations table, in full. Called after a commit, not on the timer."""
    try:
        c = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cur = c.execute("SELECT * FROM observations ORDER BY id")
        header = [d[0] for d in cur.description]
        rows = cur.fetchall()
        c.close()
    except sqlite3.Error as e:
        print(f"[DataEntry] CSV backup could not read observations: {e}")
        return None

    path = _write_rows(OBSERVATIONS_FILE, header, rows)
    if path:
        print(f"[DataEntry] observations backed up ({len(rows)} rows)")
    return path


if __name__ == "__main__":
    # Manual run: python -m DataEntry.csv_backup
    import sys
    _R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, _R)
    import paths

    main_db = str(paths.OBSERVATUM_DB)
    conn = sqlite3.connect(main_db)
    print("staging      ->", backup_staging(conn))
    print("observations ->", backup_observations(main_db))
    conn.close()
