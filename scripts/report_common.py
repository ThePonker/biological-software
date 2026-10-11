"""report_common -- the small pieces the read-only report scripts share (10 Oct 2026, round 2).

    report_scheme_duplicates.py, report_tetrad_mapping.py, report_specimen_observation_links.py,
    link_specimens_to_observations.py, report_commercial_embargo.py and
    _oneoff/fix_irecord_format_sort_keys_20261010.py

Nothing here writes a database. CSV reports go to scripts\\_oneoff\\ (git-ignored, where the
other check scripts write theirs), named <report>_<YYYYMMDD>.csv unless --csv is given.
"""
import csv
import os
import re
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


def blank(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def norm_ref(ref) -> str:
    """A grid reference as compared: upper case, no spaces (Mapping's MAP2 rule)."""
    return "" if ref is None else str(ref).upper().replace(" ", "")


def norm_text(v) -> str:
    """Case, spacing and punctuation folded: 'Heeney, W.J.' == 'heeney  w j'."""
    return " ".join(re.sub(r"[^\w]+", " ", str(v or "")).casefold().split())


# words that are not a person: titles, fillers, and the methods that ended up in some
# observations' recorder column ('Collected', 'Net', 'Field sighting', 'Swept')
_NOT_NAMES = {"unknown", "anon", "anonymous", "and", "the", "per", "via", "mr", "mrs", "ms",
              "dr", "miss", "prof", "collected", "collection", "net", "netted", "swept",
              "sweep", "sweeping", "beaten", "beating", "field", "sighting", "trap", "trapped",
              "pitfall", "light", "malaise", "reared", "specimen", "searched"}


def name_words(v) -> set:
    """The words of a recorder / collector field that could be a surname (3+ letters)."""
    return {w for w in norm_text(v).split() if len(w) >= 3 and w.isalpha()
            and w not in _NOT_NAMES}


def comparable_people(a, b) -> bool:
    """Both fields name somebody (not blank, not just a method word like 'Collected')."""
    return bool(name_words(a)) and bool(name_words(b))


def same_person(a, b) -> bool:
    """True when two recorder / collector fields share a surname-like word: 'Heeney, W.J.',
    'Wil Heeney' and 'Heeney, Wil. Lamin, John' all agree; 'Collected' agrees with nobody."""
    return bool(name_words(a) & name_words(b))


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
