"""Set up the nightly encrypted backup to a USB drive (see docs\\Backups.md).

    py -3.14 scripts\\setup_nightly_backup.py                 dry run: shows what it would do, changes nothing
    py -3.14 scripts\\setup_nightly_backup.py --drive D: --apply
    py -3.14 scripts\\setup_nightly_backup.py --remove        removes the scheduled task only (dry run unless --apply)
"""
from __future__ import annotations

import argparse
import getpass
import json
import ntpath
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import paths  # noqa: E402
from shared import nightly_backup as nb  # noqa: E402
from shared.away_mode import away_active  # noqa: E402

TASK_NAME = "BiologicalSoftware Nightly Backup"
RESTORE_NAME = "HOW TO RESTORE.txt"
INSTALL_HINT = "py -3.14 -m pip install pyzipper keyring"

RESTORE_TEXT = """HOW TO RESTORE
==============

What is on this drive
---------------------
Each computer that backs up here has its own folder, named after the computer:

    <COMPUTER>\\nightly\\YYYY-MM-DD.zip    the working databases, one zip per night (the most recent ones are kept)
    <COMPUTER>\\monthly\\YYYY-MM.zip       every database in the data folder, one zip per month (the most recent ones are kept)
    <COMPUTER>\\backup_log.txt             what happened each night
    <COMPUTER>\\_failed\\                   leftovers of a failed night, kept aside; safe to empty by hand

The zips are password protected. Without the password they cannot be opened.

Restoring is always done by hand
--------------------------------
1. Close all the apps (Observatum, Examen, Codex, Munia, Atrium, Lector, Data Entry).
2. Install 7-Zip (free, from 7-zip.org). Windows' own zip tool cannot open
   AES-encrypted zips.
3. Right-click the zip you want, choose 7-Zip > Extract to..., and type the password.
   Extract into a new empty folder, not straight into the data folder.
4. Open manifest.json in the extracted folder. It lists every file, its size, and the
   computer and time the backup was made. Check the file you need is there.
5. In the suite's data folder (the folder called "data"), RENAME the current database
   rather than deleting it, e.g. observatum.db -> observatum_before_restore.db.
   If there are files called observatum.db-wal or observatum.db-shm beside it, rename
   those the same way (observatum_before_restore.db-wal, and so on).
6. Copy the restored .db file into the data folder.
7. Open the app and check the records are what you expect. Keep the renamed
   "before_restore" file until you are sure.
"""


# --- Task Scheduler (Windows only; tests patch the two small functions below) ------------------

def pythonw_path() -> str:
    exe = sys.executable
    if os.path.basename(exe).lower() == "python.exe":
        cand = os.path.join(os.path.dirname(exe), "pythonw.exe")
        if os.path.exists(cand):
            return cand
    return exe


def build_task_xml(time_str: str, python_exe: str, working_dir: str, user: str = "") -> str:
    """Task Scheduler XML: daily, catch up if missed, only when logged on (Credential Manager)."""
    user_xml = f"      <UserId>{escape(user)}</UserId>\n" if user else ""
    logon_user = f"\n      <UserId>{escape(user)}</UserId>" if user else ""
    start = f"{datetime.now().strftime('%Y-%m-%d')}T{time_str}:00"
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Nightly encrypted backup of the Biological Software databases to the USB drive.</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>{start}</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
    </CalendarTrigger>
    <LogonTrigger>
      <Enabled>true</Enabled>{logon_user}
      <Delay>PT10M</Delay>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
{user_xml}      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <ExecutionTimeLimit>PT2H</ExecutionTimeLimit>
    <Enabled>true</Enabled>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{escape(python_exe)}</Command>
      <Arguments>-m shared.nightly_backup</Arguments>
      <WorkingDirectory>{escape(working_dir)}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""


def run_schtasks(args: list) -> int:
    return subprocess.call(["schtasks", *args])


def create_task(xml: str) -> int:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        f = os.path.join(tmp, "task.xml")
        with open(f, "w", encoding="utf-16") as fh:
            fh.write(xml)
        return run_schtasks(["/Create", "/TN", TASK_NAME, "/XML", f, "/F"])


def delete_task() -> int:
    return run_schtasks(["/Delete", "/TN", TASK_NAME, "/F"])


# --- small helpers -----------------------------------------------------------------------------

def write_if_absent_or_same(path: Path, text: str) -> str:
    """'written', 'already there', or 'already there (different; left alone)'. Never overwrites."""
    if path.exists():
        if path.read_text(encoding="utf-8") == text:
            return "already there"
        return "already there (different; left alone)"
    path.write_text(text, encoding="utf-8")
    return "written"


def marker_text(note: str = "Backup drive for the Biological Software suite.") -> str:
    return json.dumps({"created": datetime.now().isoformat(timespec="seconds"), "note": note}, indent=2)


def task_user() -> str:
    """DOMAIN\\user for the scheduled task (the computer name when there is no domain)."""
    name = os.environ.get("USERNAME", "")
    dom = os.environ.get("USERDOMAIN", "")
    return f"{dom}\\{name}" if name and dom else name


def validate_drive(drive: str) -> str | None:
    """None if `drive` is a plain letter like D: that is not the data drive or the system drive."""
    if not re.fullmatch(r"[A-Za-z]:\\?", drive.strip()):
        return f"'{drive}' is not a drive letter such as D:"
    letter = drive.strip()[0].upper()
    if ntpath.splitdrive(str(paths.DATA_DIR))[0][:1].upper() == letter:
        return f"{letter}: holds the data folder; the backup must go to a different drive"
    if os.environ.get("SystemDrive", "C:")[:1].upper() == letter:
        return f"{letter}: is the system drive; the backup must go to a different drive"
    return None


def _drive_root(drive: str) -> str:
    d = drive.strip().rstrip("\\/")
    return d + "\\" if len(d) == 2 and d[1] == ":" else d


def _ask_password() -> str:
    while True:
        a = getpass.getpass("Choose a backup password (at least 8 characters): ")
        if len(a) < 8:
            print("Too short.")
            continue
        if a != getpass.getpass("Type it again: "):
            print("They do not match.")
            continue
        return a


def _yes(prompt: str) -> bool:
    return input(prompt).strip().lower() in ("", "y", "yes")


def _keyring_get() -> str | None:
    return nb.get_password()


def _keyring_set(pw: str) -> None:
    import keyring
    keyring.set_password(nb.KEYRING_SERVICE, nb.computer_name(), pw)


def _imports_ok() -> bool:
    try:
        import keyring  # noqa: F401
        import pyzipper  # noqa: F401
        return True
    except ImportError:
        return False


# --- main --------------------------------------------------------------------------------------

def plan_lines(drive: str | None) -> list:
    s = nb.load_settings()
    base = (Path(_drive_root(drive)) / s["folder_name"]) if drive else Path("<drive>") / s["folder_name"]
    return [
        f"Folder on the drive:  {base}",
        f"Marker file:          {base / nb.MARKER_NAME}",
        f"Instructions:         {base / RESTORE_NAME}",
        f"This computer:        {base / nb.computer_name()}",
        f"Settings file:        {nb.settings_path()}",
        f"Password:             stored in Windows Credential Manager ({nb.KEYRING_SERVICE})",
        f"Scheduled task:       {TASK_NAME}, daily at {s['time']}, run only when logged on",
    ]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Set up the nightly encrypted backup.")
    ap.add_argument("--drive", help="the backup drive, e.g. D:")
    ap.add_argument("--apply", action="store_true", help="make the changes (otherwise a dry run)")
    ap.add_argument("--remove", action="store_true", help="remove the scheduled task only")
    args = ap.parse_args(argv)

    if args.remove:
        if not args.apply:
            print(f"Dry run: would remove the scheduled task '{TASK_NAME}'. Nothing has been changed.")
            return 0
        rc = delete_task()
        print("Scheduled task removed." if rc == 0 else f"schtasks returned {rc}.")
        return 0 if rc == 0 else 1

    if args.drive:
        bad = validate_drive(args.drive)
        if bad:
            print(bad)
            return 1

    if not args.apply:
        print("Dry run: this is what --apply would do.")
        for line in plan_lines(args.drive):
            print("  " + line)
        if not args.drive:
            print("Give the drive with --drive D: (the drive must be plugged in).")
        print("Nothing has been changed.")
        return 0

    if not args.drive:
        print("--apply needs --drive D:")
        return 1
    if away_active():
        print("This is an away copy: it does not hold the master data, so no backup is set up here.")
        return 1
    if not _imports_ok():
        print("Two Python packages are missing. Run this, then try again:")
        print("  " + INSTALL_HINT)
        return 1

    root = Path(_drive_root(args.drive))
    if not root.is_dir():
        print(f"Cannot see {args.drive}. Is the drive plugged in?")
        return 1
    s = nb.load_settings()

    if _keyring_get():
        if _yes("A backup password is already stored. Keep existing? [Y/n] "):
            print("Keeping the existing password.")
        else:
            _keyring_set(_ask_password())
            print("Password stored.")
    else:
        _keyring_set(_ask_password())
        print("Password stored.")

    base = root / s["folder_name"]
    try:
        base.mkdir(exist_ok=True)
        print(f"Marker file: {write_if_absent_or_same_marker(base)}")
        print(f"{RESTORE_NAME}: {write_if_absent_or_same(base / RESTORE_NAME, RESTORE_TEXT)}")
        (base / nb.computer_name()).mkdir(exist_ok=True)
        sp = nb.settings_path()
        sp.parent.mkdir(parents=True, exist_ok=True)
        if sp.exists():
            print("Settings file: already there")
        else:
            conf = dict(nb.DEFAULTS, set_up_at=datetime.now().isoformat(timespec="seconds"))
            sp.write_text(json.dumps(conf, indent=2), encoding="utf-8")
            print("Settings file: written")
    except OSError as e:
        print(f"Stopped: {e}")
        return 1

    xml = build_task_xml(s["time"], pythonw_path(), str(paths.ROOT), task_user())
    rc = create_task(xml)
    print("Scheduled task created." if rc == 0 else f"schtasks returned {rc}: the task was not created.")

    print("Write the password down and keep it somewhere safe away from the computer. "
          "Without it the backups cannot be opened.")
    if rc == 0 and _yes("Run the first backup now? [Y/n] "):
        code = nb.run()
        print("First backup made." if code == 0 else "The first backup did not complete; see backup_log.txt on the drive.")
    return 0 if rc == 0 else 1


def write_if_absent_or_same_marker(base: Path) -> str:
    """The marker holds a creation time, so an existing marker is always left alone."""
    p = base / nb.MARKER_NAME
    if p.exists():
        return "already there"
    p.write_text(marker_text(), encoding="utf-8")
    return "written"


if __name__ == "__main__":
    sys.exit(main())
