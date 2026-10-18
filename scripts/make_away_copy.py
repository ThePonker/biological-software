"""Make the away copy: the databases that change, for reading on the laptop (18 Oct 2026).

    py -3.14 scripts\\make_away_copy.py                      make it
    py -3.14 scripts\\make_away_copy.py --if-older-than 20   only if the last copy is over 20 h old
    py -3.14 scripts\\make_away_copy.py --dry-run            say what it would do, write nothing
    py -3.14 scripts\\make_away_copy.py --show-task-command  print the scheduled-task command

Each live database is copied with SQLite's backup API (the source is opened read-only), set to
journal mode DELETE so a read-only open needs no -wal/-shm, and checked. manifest.json is
written last. The set goes into the slot folder A or B that the current manifest does not use
(written as "<name>.tmp" and os.replace()d, retried), is verified by sha256, and only then does
manifest.json (naming the slot) replace the old one. Reference databases are copied only when
they changed since the last manifest. The away copy is a disposable copy, replaced
each time; C:\\BiologicalSoftware_Backups is never touched. Nothing is deleted.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import sqlite3
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import paths  # noqa: E402
from shared import away_mode  # noqa: E402

TASK_NAME = "Observatum away copy"
WORK_DIR_NAME = "observatum_away_copy_work"


def refusal_reason(data_dir=None) -> str:
    """Why this machine must not make the away copy, or '' when it may."""
    if away_mode.is_away_machine() or getattr(paths, "AWAY_MODE", False):
        return "this is an away machine; the away copy is made on the desktop only"
    data = Path(data_dir) if data_dir else Path(paths.DATA_DIR)
    if data.resolve() != (Path(paths.ROOT) / "data").resolve():
        return f"{data} is not the live data folder ({Path(paths.ROOT) / 'data'})"
    return ""


def task_command() -> str:
    script = Path(paths.ROOT) / "scripts" / "make_away_copy.py"
    root = str(paths.ROOT)
    return "\n".join([
        f"$action = New-ScheduledTaskAction -Execute 'py' -Argument '-3.14 \"{script}\" "
        f"--if-older-than 20' -WorkingDirectory '{root}'",
        "$trigger = New-ScheduledTaskTrigger -Daily -At 2:00AM",
        "$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable",
        f"Register-ScheduledTask -TaskName '{TASK_NAME}' -Action $action -Trigger $trigger "
        "-Settings $settings",
    ])


def _age_hours(manifest: dict):
    try:
        made = datetime.fromisoformat(manifest["made_at"])
        now = datetime.now(made.tzinfo) if made.tzinfo else datetime.now()
        return (now - made).total_seconds() / 3600
    except (KeyError, TypeError, ValueError):
        return None


def _copy_one(src: Path, dest: Path) -> dict:
    """Backup-API copy of src to dest, journal mode DELETE, quick_check. Returns file facts."""
    s = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    d = sqlite3.connect(str(dest))
    try:
        s.backup(d)
        mode = d.execute("PRAGMA journal_mode=DELETE").fetchone()[0]
        d.commit()
        check = d.execute("PRAGMA quick_check").fetchone()[0]
        rows = None
        try:
            rows = d.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
        except sqlite3.Error:
            pass
    finally:
        d.close()
        s.close()
    if str(mode).lower() != "delete":
        raise RuntimeError(f"{dest.name}: journal mode is {mode}, not delete")
    if check != "ok":
        raise RuntimeError(f"{dest.name}: integrity check said {check}")
    return {"name": src.name, "size": dest.stat().st_size, "observations": rows}


LOCK_STALE_HOURS = 2


def default_work_dir() -> Path:
    return Path(tempfile.gettempdir()) / WORK_DIR_NAME


def take_lock(work: Path) -> bool:
    """<work>/lock via O_CREAT|O_EXCL. False if another run holds it (younger than 2 hours).
    A stale lock is overwritten, never deleted; the content 'free' means unlocked."""
    lock = work / "lock"
    token = f"{os.getpid()} {datetime.now().isoformat()} {time.time_ns()}"
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w") as f:
            f.write(token)
        return True
    except FileExistsError:
        pass
    try:
        held = lock.read_text(encoding="utf-8", errors="replace").strip() != "free"
        age_h = (time.time() - lock.stat().st_mtime) / 3600
    except OSError:
        held, age_h = False, 0
    if held and age_h < LOCK_STALE_HOURS:
        return False
    lock.write_text(token, encoding="utf-8")
    time.sleep(0.2)                                  # two takers of a free lock: last write wins
    return lock.read_text(encoding="utf-8", errors="replace") == token


def release_lock(work: Path) -> None:
    try:
        (work / "lock").write_text("free", encoding="utf-8")
    except OSError:
        pass


def _replace_retry(src: Path, dest: Path, tries: int = 5) -> None:
    """os.replace, retried with a short back-off (OneDrive may hold the target open)."""
    for i in range(tries):
        try:
            os.replace(src, dest)
            return
        except OSError:
            if i == tries - 1:
                raise
            time.sleep(0.5 * (i + 1))


def _publish(src: Path, dest: Path) -> str:
    """Write src to dest via <name>.tmp; return the sha256 of the PUBLISHED bytes."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp")
    shutil.copyfile(src, tmp)
    _replace_retry(tmp, dest)
    return away_mode.sha256_of(dest)


def make_copy(data_dir: Path, away: Path, dry_run: bool = False, work_dir: Path = None) -> int:
    data_dir, away = Path(data_dir), Path(away)
    present = [n for n in away_mode.ALL_DBS if (data_dir / n).is_file()]
    if not any(n in away_mode.CHANGING_DBS for n in present):
        print(f"None of the databases were found in {data_dir}.")
        return 1
    prev = away_mode.read_manifest(away) or {}
    slot = "B" if prev.get("slot") == "A" else "A"
    if dry_run:
        print(f"Dry run: would copy {', '.join(present)} (reference databases only if changed)")
        print(f"  from {data_dir}")
        print(f"  to   {away / slot}  (the folder the manifest does not use), then manifest.json")
        print("Nothing has been changed.")
        return 0
    work = Path(work_dir) if work_dir else default_work_dir()
    work.mkdir(parents=True, exist_ok=True)
    if not take_lock(work):
        print("another copy is running; nothing to do.")
        return 0
    try:
        return _make_locked(data_dir, away, present, prev, slot, work)
    finally:
        release_lock(work)


def _make_locked(data_dir, away, present, prev, slot, work) -> int:
    prev_files = {f["name"]: f for f in prev.get("files", [])}
    prev_src = prev.get("sources", {})
    files, sources, todo = [], {}, []
    for name in present:
        st = (data_dir / name).stat()
        stamp = [st.st_size, st.st_mtime_ns]
        old = away / prev["slot"] / name if prev.get("slot") else None
        if (name in away_mode.STATIC_DBS and prev_src.get(name) == stamp and old
                and old.is_file() and name in prev_files
                and away_mode.sha256_of(old) == prev_files[name]["sha256"]):
            print(f"{name} unchanged; carried over from the last copy")
            todo.append((name, old, prev_files[name]["sha256"], prev_files[name]))
        else:
            print(f"Copying {name} ...")
            info = _copy_one(data_dir / name, work / name)
            print(f"  checked ok, {info['size']:,} bytes")
            todo.append((name, work / name, away_mode.sha256_of(work / name), info))
        if name in away_mode.STATIC_DBS:
            sources[name] = stamp
    for name, src, want, info in todo:
        got = _publish(src, away / slot / name)
        if got != want:
            print(f"FAILED: {name} in {away / slot} does not match what was copied (hash).")
            return 1
        files.append({"name": name, "size": (away / slot / name).stat().st_size,
                      "sha256": got, "observations": info.get("observations")})
        print(f"Published {slot}/{name}")
    obs = next((f["observations"] for f in files if f["name"] == "observatum.db"), None)
    manifest = {"made_at": datetime.now().astimezone().isoformat(),
                "source_host": socket.gethostname(), "slot": slot, "files": files,
                "sources": sources, "observation_rows": obs}
    mtmp = away / (away_mode.MANIFEST + ".tmp")
    mtmp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _replace_retry(mtmp, away / away_mode.MANIFEST)           # last: the set is complete
    print(f"Published manifest.json (slot {slot})")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Make the away copy of the changing databases.")
    ap.add_argument("--if-older-than", type=float, metavar="HOURS",
                    help="skip when the existing away copy is younger than this")
    ap.add_argument("--dry-run", action="store_true", help="say what would be done, write nothing")
    ap.add_argument("--show-task-command", action="store_true",
                    help="print the PowerShell command for the daily 02:00 task; do not run it")
    a = ap.parse_args(argv)
    if a.show_task_command:
        print(task_command())
        return 0
    why = refusal_reason()
    if why:
        print(f"Refusing: {why}.")
        return 1
    away = away_mode.away_dir()
    if a.if_older_than is not None:
        m = away_mode.read_manifest(away)
        age = _age_hours(m) if m else None
        if age is not None and age < a.if_older_than:
            print(f"The away copy is {age:.1f} h old (under {a.if_older_than:g}); nothing to do.")
            print("done.")
            return 0
    try:
        rc = make_copy(Path(paths.DATA_DIR), away, a.dry_run)
    except Exception as e:
        print(f"FAILED: {e}")
        return 1
    if rc == 0:
        print("done.")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
