"""nightly_backup -- one encrypted backup a night, to a USB drive.

    py -3.14 -m shared.nightly_backup            make tonight's backup
    py -3.14 -m shared.nightly_backup --status   say when the last one was made

Set up once with scripts\\setup_nightly_backup.py (see docs\\Backups.md). The drive is found by a
marker file, so it does not matter which drive letter it has today:

    <drive>\\BiologicalSoftware_Backups\\
        HOW TO RESTORE.txt
        .backup_drive.json
        <COMPUTER>\\nightly\\YYYY-MM-DD.zip
        <COMPUTER>\\monthly\\YYYY-MM.zip
        <COMPUTER>\\backup_log.txt
        <COMPUTER>\\_failed\\          leftover partial files, moved aside, never deleted

Each database is copied with backup_service.copy_database (SQLite's online backup API) and
checked with backup_service.verify_copy, then put in a password-protected (AES) zip written as
"<name>.zip.partial", re-opened and checked, and only then renamed into place. The old zips are
pruned only after that, and only by prune() -- the one place in this module that deletes anything.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import paths
from shared import backup_service
from shared.away_mode import away_active
from shared.backup_settings import (  # noqa: F401  (re-exported: setup script, home screen, tests)
    DEFAULTS, KEYRING_SERVICE, MARKER_NAME, STATUS_NAME, computer_name, find_backup_drive,
    get_password, load_settings, local_dir, local_log_path, settings_path, status_path, status_text,
)
from shared.backup_settings import append as _append
from shared.backup_settings import line as _line
from shared.backup_settings import log_local as _log_local
from shared.backup_zip import fsync_file as _fsync_file
from shared.backup_zip import verify_zip as _verify_zip
from shared.backup_zip import write_zip as _write_zip

NIGHTLY_DBS = ("observatum", "munia", "examen", "gamification", "lector", "codex")
NIGHTLY_RE = r"^\d{4}-\d{2}-\d{2}\.zip$"
MONTHLY_RE = r"^\d{4}-\d{2}\.zip$"
LOCK_NAME = ".backup.lock"
LOCK_STALE_SECONDS = 3 * 3600
_sleep = time.sleep          # tests patch this


def _unique(folder: Path, name: str) -> Path:
    cand, n = folder / name, 1
    while cand.exists():
        n += 1
        cand = folder / f"{name}.{n}"
    return cand


def _move_partials(computer_dir: Path, now: datetime, log) -> None:
    """A .partial left by a crashed run is moved to _failed, never deleted."""
    for sub in ("nightly", "monthly"):
        folder = computer_dir / sub
        if not folder.is_dir():
            continue
        for entry in sorted(folder.iterdir()):
            if entry.is_file() and entry.name.endswith(".partial"):
                failed = computer_dir / "_failed"
                failed.mkdir(parents=True, exist_ok=True)
                dest = _unique(failed, f"{now.strftime('%Y%m%d_%H%M%S')}_{entry.name}")
                os.replace(entry, dest)
                log(f"moved leftover {entry.name} to _failed")


def acquire_lock(computer_dir: Path, now: datetime, log) -> bool:
    """Take <computer_dir>\\.backup.lock (O_EXCL). False if another backup holds it (under 3 hours old).

    An older lock is stale (a crashed run): it is moved to _failed, not deleted, and we carry on.
    """
    lock = Path(computer_dir) / LOCK_NAME
    for _attempt in range(2):
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                age = time.time() - os.path.getmtime(lock)
            except OSError:
                continue                                # it vanished: try again
            if age < LOCK_STALE_SECONDS:
                log("another backup is running")
                return False
            failed = Path(computer_dir) / "_failed"
            failed.mkdir(parents=True, exist_ok=True)
            os.replace(lock, _unique(failed, f"{now.strftime('%Y%m%d_%H%M%S')}_stale{LOCK_NAME}"))
            log("moved a stale lock file to _failed")
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"pid": os.getpid(), "time": datetime.now().isoformat(timespec="seconds")}, f)
        return True
    log("another backup is running")
    return False


def release_lock(computer_dir) -> None:
    """Remove our own lock file (only if it names this process). The only deletion besides prune()."""
    lock = Path(computer_dir) / LOCK_NAME
    try:
        if json.loads(lock.read_text(encoding="utf-8")).get("pid") == os.getpid():
            os.remove(lock)
    except (OSError, ValueError, AttributeError):
        pass


def _matching(folder, pattern: str) -> list:
    """Names in `folder` that wholly match the date pattern (files only, no symlinks), oldest first."""
    rx = re.compile(pattern, re.IGNORECASE)
    found = []
    for entry in os.scandir(folder):
        if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
            continue
        if rx.fullmatch(entry.name):
            found.append(entry.name)
    return sorted(found, key=str.casefold)


def _newer_than(folder, pattern: str, protect: str) -> Optional[str]:
    """The newest matching name if it is dated after `protect` (clock gone back), else None."""
    found = _matching(folder, pattern)
    if found and found[-1].casefold() > protect.casefold():
        return found[-1]
    return None


def prune(folder, pattern: str, keep: int, protect: str) -> list:
    """Remove the oldest dated zips from one nightly or monthly folder, keeping the newest `keep`.

    The ONE place (with release_lock) this module deletes anything. The folder must be exactly
    <drive>\\<folder_name>\\<COMPUTER>\\nightly or ...\\monthly (marker file beside it, resolved
    path), else ValueError. Only files whose whole name matches the date pattern are considered;
    everything else, subfolders and symlinks included, is ignored. Sorted by the date in the
    name, not mtime. `protect` (the zip just written) is never removed; if a matching file is
    dated after it (the clock has gone back) nothing is pruned. Returns the names removed.
    """
    folder = Path(folder).resolve()
    kind = folder.name.casefold()
    expected = {"nightly": NIGHTLY_RE, "monthly": MONTHLY_RE}.get(kind)
    if expected is None or pattern != expected:
        raise ValueError(f"prune refused: {folder} is not a nightly/monthly folder for that pattern")
    computer_dir = folder.parent
    root = computer_dir.parent
    if (computer_dir.name.casefold() != computer_name().casefold()
            or root.name.casefold() != load_settings()["folder_name"].casefold()
            or not (root / MARKER_NAME).is_file()):
        raise ValueError(f"prune refused: {folder} is not in this computer's backup folder")
    if not isinstance(keep, int) or keep < 1:
        raise ValueError("prune refused: keep must be at least 1")
    found = _matching(folder, pattern)
    if not protect or protect.casefold() not in (n.casefold() for n in found):
        raise ValueError("prune refused: protect must name a zip in the folder")
    log_path = computer_dir / "backup_log.txt"
    if found[-1].casefold() != protect.casefold():
        _append(log_path, _line(f"not pruned: {found[-1]} is dated after today -- check the computer clock",
                                datetime.now()))
        return []
    removed = []
    if len(found) < keep + 1:
        return removed
    for name in found[:-keep]:
        if name.casefold() == protect.casefold():
            continue
        os.remove(folder / name)
        removed.append(name)
        _append(log_path, _line(f"pruned {kind}/{name}", datetime.now()))
    return removed


def _write_status(stamp: dict) -> None:
    path = status_path()
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(stamp, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _write_status_retry(stamp: dict, log) -> None:
    for attempt in range(5):
        try:
            _write_status(stamp)
            return
        except OSError:
            if attempt < 4:
                _sleep(1)
    log("backup made; status stamp not written")


def run(now: Optional[datetime] = None, force: bool = False) -> int:
    """One nightly backup. Returns the exit code: 0 done or skipped, 1 failed.

    Without `force` it exits 0 early when today's nightly zip already exists.
    """
    now = now or datetime.now()
    if away_active():
        _log_local("skipped: away copy (this computer reads a copy, it does not hold the master data)", now)
        return 0
    settings = load_settings()
    root = find_backup_drive(settings["folder_name"])
    if not root:
        _log_local("skipped: backup drive not connected", now)
        return 0
    password = get_password()
    if not password:
        _log_local("not set up: no password stored", now)
        return 1

    computer = computer_name()
    computer_dir = Path(root) / settings["folder_name"] / computer
    drive_log = computer_dir / "backup_log.txt"

    def log(msg):
        _append(drive_log, _line(msg, now))
        if msg.startswith(("FAILED", "skipped")):
            _log_local(msg, now)

    day = now.strftime("%Y-%m-%d")
    try:
        if not force and (computer_dir / "nightly" / f"{day}.zip").exists():
            log("skipped: already done today")
            return 0
        computer_dir.mkdir(parents=True, exist_ok=True)
        if not acquire_lock(computer_dir, now, log):
            return 0
    except Exception as e:
        log(f"FAILED: {type(e).__name__}: {e}")
        return 1
    try:
        return _run_locked(now, settings, root, password, computer, computer_dir, log)
    except Exception as e:
        log(f"FAILED: {type(e).__name__}: {e}")
        return 1
    finally:
        release_lock(computer_dir)


SAFETY_COPY_MARKS = ("_pre_", "_prelive_")      # a database set aside before a change, not live data


def _monthly_dbs(data_dir: Path, log) -> list:
    """The *.db files in the data folder that the monthly set includes: safety copies
    (names with _pre_ or _prelive_, any case) are left out and logged by name. The glob
    matches names ending exactly in .db, so -shm / -wal side files are never included."""
    keep, skipped = [], []
    for p in sorted(data_dir.glob("*.db")):
        if not p.is_file():
            continue
        if any(m in p.name.lower() for m in SAFETY_COPY_MARKS):
            skipped.append(p.name)
        else:
            keep.append(p)
    if skipped:
        log("monthly set: safety copies not included: " + ", ".join(skipped))
    return keep


def _run_locked(now, settings, root, password, computer, computer_dir, log) -> int:
    data_dir = Path(paths.DATA_DIR)
    day, month = now.strftime("%Y-%m-%d"), now.strftime("%Y-%m")
    nightly_dir, monthly_dir = computer_dir / "nightly", computer_dir / "monthly"
    nightly_dir.mkdir(parents=True, exist_ok=True)
    monthly_dir.mkdir(parents=True, exist_ok=True)
    _move_partials(computer_dir, now, log)

    if not (data_dir / "observatum.db").is_file():
        log("FAILED: observatum.db is missing from the data folder; no backup written")
        return 1
    absent = [f"{n}.db" for n in NIGHTLY_DBS if not (data_dir / f"{n}.db").is_file()]
    if absent:
        log("not in the data folder, so not backed up: " + ", ".join(absent))
    want_monthly = not (monthly_dir / f"{month}.zip").exists()

    nightly_files = [data_dir / f"{n}.db" for n in NIGHTLY_DBS if (data_dir / f"{n}.db").is_file()]
    monthly_files = []
    if want_monthly:
        monthly_files = _monthly_dbs(data_dir, log)
        if (data_dir / "saved_filters.json").is_file():
            monthly_files.append(data_dir / "saved_filters.json")

    pid = os.getpid()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        copies = {}
        for src in dict.fromkeys(nightly_files + monthly_files):
            dest = os.path.join(tmp, src.name)
            if src.suffix == ".db":
                if not backup_service.copy_database(str(src), dest):
                    log(f"FAILED: could not copy {src.name}; no backup written")
                    return 1
                why = backup_service.verify_copy(dest)
                if why:
                    log(f"FAILED: copy of {src.name} did not verify ({why}); no backup written")
                    return 1
            else:
                shutil.copyfile(src, dest)
            copies[src] = dest

        jobs = [(nightly_dir / f"{day}.zip", [(p.name, copies[p]) for p in nightly_files])]
        if want_monthly:
            jobs.append((monthly_dir / f"{month}.zip", [(p.name, copies[p]) for p in monthly_files]))
        partials = []
        for final, members in jobs:
            partial = final.with_name(f"{final.name}.{pid}.partial")
            _write_zip(partial, members, password, computer, now)
            partials.append((partial, final))
            why = _verify_zip(partial, password)
            if why:
                log(f"FAILED: {final.name} did not verify ({why}); not kept")
                return 1
        for partial, final in partials:
            os.replace(partial, final)
            _fsync_file(final, strict=False)
            log(f"written and verified: {final.parent.name}/{final.name}")

    warning = None
    written = [(nightly_dir, NIGHTLY_RE, settings["keep_nightly"], f"{day}.zip")]
    if want_monthly:
        written.append((monthly_dir, MONTHLY_RE, settings["keep_monthly"], f"{month}.zip"))
    for folder, pattern, keep, name in written:
        newer = _newer_than(folder, pattern, name)
        if newer:
            warning = f"not pruned: {newer} is dated after today -- check the computer clock"
            log(warning)
        else:
            prune(folder, pattern, keep, name)

    log("backup complete")
    stamp = {"last_ok": now.isoformat(timespec="seconds"), "computer": computer,
             "drive": os.path.splitdrive(root)[0] or root.rstrip("\\/"),
             "nightly": f"{day}.zip", "monthly": f"{month}.zip" if want_monthly else None}
    if warning:
        stamp["warning"] = warning
    _write_status_retry(stamp, log)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Nightly encrypted backup to the USB drive.")
    ap.add_argument("--status", action="store_true", help="print the status line and exit")
    ap.add_argument("--force", action="store_true", help="back up even if today's nightly zip exists")
    args = ap.parse_args(argv)
    if args.status:
        print(status_text()[0])
        return 0
    try:
        return run(force=args.force)
    except Exception:
        import traceback
        _log_local("FAILED: unexpected error\n" + traceback.format_exc(), datetime.now())
        return 1


if __name__ == "__main__":
    sys.exit(main())
