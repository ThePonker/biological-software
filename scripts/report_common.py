"""report_common -- the small pieces the read-only report scripts share (10 Oct 2026, round 2).

    report_scheme_duplicates.py, report_tetrad_mapping.py, report_specimen_observation_links.py,
    link_specimens_to_observations.py, report_commercial_embargo.py and
    _oneoff/fix_irecord_format_sort_keys_20261010.py

Nothing here writes a database. CSV reports go to scripts\\_oneoff\\ (git-ignored, where the
other check scripts write theirs), named <report>_<YYYYMMDD>.csv unless --csv is given.
"""
import csv
import os
import sqlite3
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (ROOT, os.path.join(ROOT, "Observatum")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPORT_DIR = os.path.join(ROOT, "scripts", "_oneoff")
BACKUP_DIR = os.path.join(r"C:\BiologicalSoftware_Backups", "reference")


def connect_ro(db_path) -> sqlite3.Connection:
    """Read-only connection (a stray write fails loudly)."""
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def default_csv(name: str) -> str:
    return os.path.join(REPORT_DIR, f"{name}_{datetime.now():%Y%m%d}.csv")


def write_csv(path: str, header, rows) -> int:
    """Write rows (sequences, in header order) as UTF-8 CSV with a BOM (opens cleanly in
    Excel). Returns the number of rows written."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    n = 0
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow(["" if v is None else v for v in r])
            n += 1
    return n


# The comparison rules live in shared/record_match.py (the Edit Specimen dialog uses them
# too); re-exported here so the report scripts keep calling rc.blank, rc.same_person, ...
from shared.record_match import (  # noqa: E402,F401
    blank, comparable_people, name_words, norm_ref, norm_text, same_person)


def backup(db_path, what: str, backup_dir=BACKUP_DIR) -> str:
    """conn.backup() of the database into backup_dir, named for what it precedes. Never
    overwrites an earlier backup."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    dest = os.path.join(backup_dir, f"observatum_pre_{what}_{stamp}.db")
    os.makedirs(backup_dir, exist_ok=True)
    if os.path.exists(dest):
        raise FileExistsError(f"backup already exists: {dest}")
    src = sqlite3.connect(str(db_path))
    d = sqlite3.connect(dest)
    try:
        src.backup(d)                            # online backup API -- safe on a WAL database
    finally:
        d.close()
        src.close()
    return dest
