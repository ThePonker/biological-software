"""backup_service -- one correct way to copy the suite's databases.

Why this exists
---------------
Copying a live SQLite database with shutil.copy2 is not safe. observatum.db runs in
WAL mode, so recent commits live in a -wal side-file until checkpointed; a raw file
copy can capture a main file that is missing them, or that does not match its WAL.
SQLite's online backup API (conn.backup) takes a transactionally consistent snapshot
of a live database and handles WAL correctly. Everything here goes through it.

Layout (single location, outside OneDrive):

    C:\\BiologicalSoftware_Backups\\
        current\\    the newest copy of each database
        previous\\   the one before it
        reference\\  codex / pantheon / uksi / vc_lookup -- on demand only
        kept\\       named, dated copies taken before an action (see below)
        _expired\\   failed partial copies and bad "current" files, moved aside

Two tiers, because the databases change at very different rates:

    WORKING    observatum, munia, examen, gamification   ~115 MB
               changes daily -> copied on close and before every commit
    REFERENCE  codex, pantheon, uksi, vc_lookup          ~172 MB
               changes once or twice a year -> copied on demand after a rebuild

Rotation is current -> previous before each write, so two generations exist and the
footprint is fixed. One generation is not enough: if a database is damaged and the
damage is not noticed before the next backup, a single copy would be overwritten by
the bad one.

Verify, then rotate (9 Oct 2026, review INF2)
--------------------------------------------
A failed copy used to leave a 0-byte "current", and the next good backup rotated that
over the last good "previous". Now every copy goes to a temporary file first and is
checked -- not empty, opens as SQLite, PRAGMA quick_check says ok -- and only then is
current moved to previous and the new copy put in its place. A failed copy touches
neither generation, and a "current" that fails the same check is never rotated over
"previous" (it is moved to _expired instead).

Kept copies (9 Oct 2026, review INF3 / IMP-17)
---------------------------------------------
Rotation means current/previous cover minutes on a busy day. So every pre-action
backup -- backup_main_only(label), and any backup whose label starts "pre-" --
ALSO writes a named, dated copy that rotation never touches:

    kept\\<db>_<label>_<YYYYMMDD_HHMMSS>.db

The newest KEEP_PER_LABEL of each database+label are kept; older ones are MOVED to
kept\\_expired\\ (never deleted -- CLAUDE.md rule 1; empty it by hand when wanted).
Pruning is by the timestamp in the file name, not mtime (OneDrive rewrites mtimes).

BACKUP_ROOT is C:\\BiologicalSoftware_Backups unless the environment variable
BIOSOFT_BACKUP_ROOT names another folder (tests set it, or patch BACKUP_ROOT).
"""
from __future__ import annotations

import os
import re
import sqlite3
from datetime import datetime
from typing import Iterable, Optional

BACKUP_ROOT = os.environ.get("BIOSOFT_BACKUP_ROOT") or r"C:\BiologicalSoftware_Backups"
CURRENT = "current"
PREVIOUS = "previous"
REFERENCE = "reference"
KEPT = "kept"
EXPIRED = "_expired"          # retired files: moved here, never deleted
KEEP_PER_LABEL = 5          # ~120 MB each for observatum.db; 5 x labels keeps disk use modest

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


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def copy_database(src: str, dest: str, source_is_live: bool = True) -> bool:
    """Consistent copy of a live SQLite database via the online backup API.

    source_is_live=False only for copying one of our own backup files: it is then
    opened read-write so no -wal/-shm files are left beside it.
    """
    src_conn = dest_conn = None
    try:
        mode = "ro" if source_is_live else "rw"
        src_conn = sqlite3.connect(f"file:{src}?mode={mode}", uri=True)
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


def verify_copy(path: str) -> Optional[str]:
    """None if `path` is a sound SQLite database, else the reason it is not.

    Not empty, opens as SQLite, and PRAGMA quick_check returns 'ok'. Only ever
    called on backup copies, never on a live database.
    """
    try:
        if not os.path.isfile(path):
            return "missing"
        if os.path.getsize(path) == 0:
            return "empty (0 bytes)"
    except OSError as e:
        return f"unreadable: {e}"
    conn = None
    try:
        # Opened read-write on purpose: it is our own copy, and a read-only open of a
        # WAL-mode copy leaves -wal/-shm files behind that it cannot clean up.
        conn = sqlite3.connect(f"file:{path}?mode=rw", uri=True)
        rows = conn.execute("PRAGMA quick_check").fetchall()
        if not rows or rows[0][0] != "ok":
            return f"quick_check: {rows[0][0] if rows else 'no result'}"
        return None
    except Exception as e:
        return f"not a readable SQLite database: {e}"
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _retire(path: str, why: str) -> None:
    """Move a file we will not use to BACKUP_ROOT/_expired/ (never delete it)."""
    if not os.path.exists(path):
        return
    d = _ensure(EXPIRED)
    if d is None:
        return
    dest = os.path.join(d, f"{_stamp()}_{why}_{os.path.basename(path)}")
    n = 1
    while os.path.exists(dest):
        n += 1
        dest = os.path.join(d, f"{_stamp()}_{why}-{n}_{os.path.basename(path)}")
    try:
        os.replace(path, dest)
    except OSError as e:
        print(f"[backup] could not retire {path}: {e}")


def _verified_copy(src: str, dest: str, source_is_live: bool = True) -> bool:
    """Copy src to a temporary file beside dest, verify it, then move it to dest.

    On any failure dest is untouched and the partial file is retired to _expired.
    """
    tmp = f"{dest}.{_stamp()}.partial"
    ok = copy_database(src, tmp, source_is_live)
    problem = None if ok else "copy failed"
    if ok:
        problem = verify_copy(tmp)
    if problem:
        print(f"[backup] {os.path.basename(dest)}: {problem} -- previous copies left as they were")
        _retire(tmp, "failed")
        return False
    try:
        os.replace(tmp, dest)
        return True
    except OSError as e:
        print(f"[backup] could not place {dest}: {e}")
        _retire(tmp, "failed")
        return False


def _rotate_in(new_copy: str, filename: str) -> bool:
    """Put a verified copy in current/, moving a sound current/ to previous/ first.

    A current/ that fails verification is retired, not rotated over previous/.
    """
    cur_dir = _ensure(CURRENT)
    prev_dir = _ensure(PREVIOUS)
    if not cur_dir or not prev_dir:
        return False
    cur = os.path.join(cur_dir, filename)
    prev = os.path.join(prev_dir, filename)
    try:
        if os.path.exists(cur):
            if verify_copy(cur) is None:
                os.replace(cur, prev)        # rotation: previous gives way to current
            else:
                _retire(cur, "bad-current")  # never rotate a bad file over a good one
        os.replace(new_copy, cur)
        return True
    except OSError as e:
        print(f"[backup] rotate failed for {filename}: {e}")
        return False


def _safe_label(label: str) -> str:
    s = re.sub(r"[^A-Za-z0-9-]+", "-", (label or "").strip()).strip("-")
    return s or "backup"


def kept_name(filename: str, label: str, stamp: Optional[str] = None) -> str:
    """'observatum.db', 'pre-import' -> 'observatum_pre-import_20261009_183012.db'."""
    stem, ext = os.path.splitext(filename)
    return f"{stem}_{_safe_label(label)}_{stamp or _stamp()}{ext or '.db'}"


def _kept_pattern(filename: str, label: str):
    stem, ext = os.path.splitext(filename)
    return re.compile(rf"^{re.escape(stem)}_{re.escape(_safe_label(label))}_"
                      rf"(\d{{8}}_\d{{6}})(?:-(\d+))?{re.escape(ext or '.db')}$")


def prune_kept(filename: str, label: str, keep: int = KEEP_PER_LABEL) -> int:
    """Move all but the newest `keep` kept copies of this db+label to kept/_expired/.

    Newest by the timestamp in the name. Returns how many were moved.
    """
    kept_dir = os.path.join(BACKUP_ROOT, KEPT)
    if not os.path.isdir(kept_dir):
        return 0
    pat = _kept_pattern(filename, label)
    found = []
    for f in os.listdir(kept_dir):
        m = pat.match(f)
        if m:
            found.append(((m.group(1), int(m.group(2) or 1)), f))
    found.sort(reverse=True)
    old = found[keep:]
    if not old:
        return 0
    exp_dir = _ensure(KEPT, EXPIRED)
    if exp_dir is None:
        return 0
    moved = 0
    for _, f in old:
        try:
            os.replace(os.path.join(kept_dir, f), os.path.join(exp_dir, f))
            moved += 1
        except OSError as e:
            print(f"[backup] could not expire {f}: {e}")
    return moved


def write_kept_copy(src: str, label: str, source_is_live: bool = True) -> Optional[str]:
    """A named, dated, verified copy of src in kept/, then prune that label. Path or None."""
    kept_dir = _ensure(KEPT)
    if kept_dir is None:
        return None
    filename = os.path.basename(src)
    stamp = _stamp()
    dest = os.path.join(kept_dir, kept_name(filename, label, stamp))
    n = 1
    while os.path.exists(dest):                       # two in the same second
        n += 1
        dest = os.path.join(kept_dir, kept_name(filename, label, f"{stamp}-{n}"))
    if not _verified_copy(src, dest, source_is_live):
        return None
    prune_kept(filename, label)
    return dest


def backup_databases(names: Iterable[str], label: str = "",
                     keep: Optional[bool] = None) -> bool:
    """Copy, verify and rotate the named paths.py databases. True only if all succeeded.

    keep: also write a kept/ copy. Default: when the label starts with 'pre-'.
    """
    cur_dir = _ensure(CURRENT)
    if cur_dir is None:
        return False
    if keep is None:
        keep = (label or "").lower().startswith("pre-")

    done, failed = [], []
    for name in names:
        src = _resolve(name)
        if src is None:
            continue                      # not configured, or not on disk yet
        filename = os.path.basename(src)
        tmp = os.path.join(cur_dir, f"{filename}.{_stamp()}.partial")
        ok = copy_database(src, tmp)
        problem = verify_copy(tmp) if ok else "copy failed"
        if problem:
            print(f"[backup] {filename}: {problem} -- current and previous left as they were")
            _retire(tmp, "failed")
            failed.append(filename)
            continue
        if not _rotate_in(tmp, filename):
            _retire(tmp, "failed")
            failed.append(filename)
            continue
        if keep:
            # From the verified current copy: the same snapshot, no second read of the live db
            if write_kept_copy(os.path.join(cur_dir, filename), label,
                               source_is_live=False) is None:
                failed.append(f"{filename} (kept copy)")
                continue
        done.append(filename)

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
    """observatum.db alone -- for the moment before a commit, import or other change.

    Always also writes a kept/ copy named for the label.
    """
    return backup_databases(("OBSERVATUM_DB",), label or "pre-commit", keep=True)


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
        # Verified before it replaces the last reference copy (a failed copy used to
        # overwrite it with a 0-byte file)
        if _verified_copy(src, os.path.join(dest_dir, os.path.basename(src))):
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
    for sub in (CURRENT, PREVIOUS, REFERENCE, KEPT):
        d = os.path.join(BACKUP_ROOT, sub)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            p = os.path.join(d, f)
            if not os.path.isfile(p):
                continue                  # the _expired folder
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
