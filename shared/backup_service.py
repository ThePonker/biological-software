"""backup_service -- one correct way to copy the suite's databases.

Why this exists
---------------
Copying a live SQLite database with shutil.copy2 is not safe. observatum.db runs in
WAL mode, so recent commits live in a -wal side-file until checkpointed; a raw file
copy can capture a main file that is missing them, or that does not match its WAL.
SQLite's online backup API (conn.backup) takes a transactionally consistent snapshot
of a live database and handles WAL correctly. Everything here goes through it.

Layout (single location, outside OneDrive, never grows):

    C:\\BiologicalSoftware_Backups\\
        current\\    the newest copy of each database
        previous\\   the one before it
        reference\\  codex / pantheon / uksi / vc_lookup -- on demand only

Two tiers, because the databases change at very different rates:

    WORKING    observatum, munia, examen, gamification   ~115 MB
               changes daily -> copied on close and before every commit
    REFERENCE  codex, pantheon, uksi, vc_lookup          ~172 MB
               changes once or twice a year -> copied on demand after a rebuild

Rotation is current -> previous before each write, so two generations exist and the
footprint is fixed. One generation is not enough: if a database is damaged and the
damage is not noticed before the next backup, a single copy would be overwritten by
the bad one.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
from datetime import datetime
from typing import Iterable, Optional

BACKUP_ROOT = r"C:\BiologicalSoftware_Backups"
CURRENT = "current"
PREVIOUS = "previous"
REFERENCE = "reference"

# Databases that change with use.
WORKING_DBS = ("OBSERVATUM_DB", "MUNIA_DB", "EXAMEN_DB", "GAMIFICATION_DB")

# Databases that only change on a rebuild.
REFERENCE_DBS = ("CODEX_DB", "PANTHEON_DB", "UKSI_DB", "VC_LOOKUP_DB")


def _paths_module():
    import paths
    return paths


def _resolve(name: str) -> Optional[str]:
    """paths.NAME as a string, or None if absent / missing on disk."""
    try:
        p = getattr(_paths_module(), name, None)
    except Exception:
        return None
    if p is None:
        return None
    s = str(p)
    return s if os.path.exists(s) else None


def _ensure(*parts) -> Optional[str]:
    d = os.path.join(BACKUP_ROOT, *parts)
    try:
        os.makedirs(d, exist_ok=True)
        return d
    except OSError as e:
        print(f"[backup] cannot create {d}: {e}")
        return None


def copy_database(src: str, dest: str) -> bool:
    """Consistent copy of a live SQLite database via the online backup API."""
    src_conn = dest_conn = None
    try:
        src_conn = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
        dest_conn = sqlite3.connect(dest)
        src_conn.backup(dest_conn)
        return True
    except Exception as e:
        print(f"[backup] FAILED {os.path.basename(src)}: {e}")
        return False
    finally:
        for c in (dest_conn, src_conn):
            try:
                if c is not None:
                    c.close()
            except Exception:
                pass


def _rotate(filename: str) -> None:
    """Move current/<filename> to previous/, replacing what was there."""
    cur_dir = _ensure(CURRENT)
    prev_dir = _ensure(PREVIOUS)
    if not cur_dir or not prev_dir:
        return
    cur = os.path.join(cur_dir, filename)
    prev = os.path.join(prev_dir, filename)
    if not os.path.exists(cur):
        return
    try:
        if os.path.exists(prev):
            os.remove(prev)
        shutil.move(cur, prev)
    except OSError as e:
        print(f"[backup] rotate failed for {filename}: {e}")


def backup_databases(names: Iterable[str], label: str = "") -> bool:
    """Rotate and copy the named paths.py databases. True only if all succeeded."""
    cur_dir = _ensure(CURRENT)
    if cur_dir is None:
        return False

    done, failed = [], []
    for name in names:
        src = _resolve(name)
        if src is None:
            continue                      # not configured, or not on disk yet
        filename = os.path.basename(src)
        _rotate(filename)
        if copy_database(src, os.path.join(cur_dir, filename)):
            done.append(filename)
        else:
            failed.append(filename)

    stamp = datetime.now().strftime("%H:%M:%S")
    tag = f" ({label})" if label else ""
    if failed:
        print(f"[backup]{tag} {len(done)} copied, FAILED: {', '.join(failed)} at {stamp}")
        return False
    print(f"[backup]{tag} {len(done)} database(s) at {stamp}")
    return True


def backup_working(label: str = "") -> bool:
    """The databases that change with use. Cheap enough to run on every close."""
    return backup_databases(WORKING_DBS, label or "working")


def backup_main_only(label: str = "") -> bool:
    """observatum.db alone -- for the moment before a commit."""
    return backup_databases(("OBSERVATUM_DB",), label or "pre-commit")


def backup_reference() -> bool:
    """The rebuild-only databases. Run after a Codex / UKSI / Pantheon rebuild.

    Written to reference/ rather than current/: these are not session backups and
    should not be rotated out by daily use.
    """
    dest_dir = _ensure(REFERENCE)
    if dest_dir is None:
        return False
    done, failed = [], []
    for name in REFERENCE_DBS:
        src = _resolve(name)
        if src is None:
            continue
        if copy_database(src, os.path.join(dest_dir, os.path.basename(src))):
            done.append(os.path.basename(src))
        else:
            failed.append(os.path.basename(src))
    if failed:
        print(f"[backup] reference: {len(done)} copied, FAILED: {', '.join(failed)}")
        return False
    print(f"[backup] reference: {len(done)} database(s)")
    return True


def status() -> str:
    """One line per backed-up file: size and age. For a Settings display."""
    lines = []
    for sub in (CURRENT, PREVIOUS, REFERENCE):
        d = os.path.join(BACKUP_ROOT, sub)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            p = os.path.join(d, f)
            mb = os.path.getsize(p) / 1048576
            when = datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d %H:%M")
            lines.append(f"  {sub:9} {f:22} {mb:8.1f} MB   {when}")
    return "\n".join(lines) if lines else "  (no backups yet)"


if __name__ == "__main__":
    import sys
    _R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, _R)
    arg = sys.argv[1] if len(sys.argv) > 1 else "working"
    if arg == "reference":
        backup_reference()
    elif arg == "status":
        print(status())
    else:
        backup_working("manual")
    print()
    print(status())
