"""backup_settings -- names, per-computer settings, the drive scan, the password and the status line.

Used by shared/nightly_backup.py (which re-exports these names) and the home screen.
"""
from __future__ import annotations

import json
import os
import re
import socket
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import paths
from shared.away_mode import away_active

KEYRING_SERVICE = "BiologicalSoftware Backup"
MARKER_NAME = ".backup_drive.json"
STATUS_NAME = "backup_status.json"
DEFAULTS = {"folder_name": "BiologicalSoftware_Backups", "time": "19:00",
            "keep_nightly": 14, "keep_monthly": 12, "stale_days": 3, "set_up_at": None}
_TIME_RE = re.compile(r"^\d{2}:\d{2}$")


# --- places, names, settings -------------------------------------------------------------------

def local_dir() -> Path:
    """%LOCALAPPDATA%\\BiologicalSoftware: per computer, never in the OneDrive data folder."""
    base = os.environ.get("LOCALAPPDATA")
    return (Path(base) if base else Path.home() / "AppData" / "Local") / "BiologicalSoftware"


def settings_path() -> Path:
    return local_dir() / "backup_settings.json"


def local_log_path() -> Path:
    return local_dir() / "backup_log.txt"


def computer_name() -> str:
    raw = os.environ.get("COMPUTERNAME") or socket.gethostname()
    return re.sub(r"[^A-Za-z0-9_-]", "_", raw) or "COMPUTER"


def load_settings() -> dict:
    """The defaults, with whatever the settings file gives. Unreadable file -> the defaults."""
    out = dict(DEFAULTS)
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return out
    if not isinstance(data, dict):
        return out
    for key, default in DEFAULTS.items():
        val = data.get(key)
        if key == "set_up_at":
            try:
                datetime.fromisoformat(val)
                out[key] = val
            except (TypeError, ValueError):
                pass
        elif key == "time":
            if isinstance(val, str) and _TIME_RE.match(val.strip()):
                hh, mm = val.strip().split(":")
                if int(hh) < 24 and int(mm) < 60:
                    out[key] = val.strip()
        elif isinstance(default, int):
            if isinstance(val, int) and not isinstance(val, bool) and val >= 1:
                out[key] = val
        elif isinstance(val, str) and val.strip():
            out[key] = val.strip()
    return out


def status_path() -> Path:
    return Path(paths.DATA_DIR) / STATUS_NAME


# --- the parts that only work on Windows (tests patch these) -----------------------------------

def _filter_drive_roots(mask: int, drive_type) -> list:
    """Roots for the set bits of GetLogicalDrives(), skipping network (4) and CD/DVD (5) drives."""
    roots = []
    for i in range(26):
        if mask >> i & 1:
            root = f"{chr(65 + i)}:\\"
            if drive_type(root) not in (4, 5):
                roots.append(root)
    return roots


def _drive_roots() -> list:
    """Drive roots to look at. On Windows: no 'insert a disk' pop-ups, no network or CD drives."""
    if sys.platform == "win32":
        import ctypes
        k32 = ctypes.windll.kernel32
        old = k32.SetErrorMode(0x0001 | 0x8000)      # SEM_FAILCRITICALERRORS | SEM_NOOPENFILEERRORBOX
        try:
            return _filter_drive_roots(k32.GetLogicalDrives(), k32.GetDriveTypeW)
        finally:
            k32.SetErrorMode(old)
    return [f"{letter}:\\" for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"]


def find_backup_drive(folder_name: Optional[str] = None) -> Optional[str]:
    """The drive root (such as D:\\) holding <folder>\\.backup_drive.json."""
    folder = folder_name or load_settings()["folder_name"]
    for root in _drive_roots():
        try:
            if os.path.isfile(os.path.join(root, folder, MARKER_NAME)):
                return root
        except OSError:
            continue
    return None


def get_password() -> Optional[str]:
    """The stored password, or None. A keyring failure is logged apart from 'nothing stored'."""
    try:
        import keyring
        return keyring.get_password(KEYRING_SERVICE, computer_name()) or None
    except Exception as e:
        log_local(f"keyring error: {type(e).__name__}: {e}", datetime.now())
        return None


# --- logging -----------------------------------------------------------------------------------


def line(msg: str, now: datetime) -> str:
    return f"{now.strftime('%Y-%m-%d %H:%M:%S')}  {msg}\n"


def append(path: Path, text: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(text)
    except OSError:
        pass


def log_local(msg: str, now: datetime) -> None:
    append(local_log_path(), line(msg, now))


def _read_stamp() -> Optional[dict]:
    try:
        data = json.loads(status_path().read_text(encoding="utf-8"))
        datetime.fromisoformat(data["last_ok"])
        return data
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _days(n: int) -> str:
    return f"{n} day" if n == 1 else f"{n} days"


def status_text(now: Optional[datetime] = None) -> tuple:
    """(text, level) for the home screen; level is 'ok', 'grey' or 'red'."""
    now = now or datetime.now()
    if away_active():
        return ("Backups: not needed on an away copy", "grey")
    stamp = _read_stamp()
    settings = load_settings()
    if stamp is None:
        if not settings_path().is_file():
            return ("Backups: not set up -- see docs\\Backups.md", "grey")
        try:
            since = (now.date() - datetime.fromisoformat(settings["set_up_at"]).date()).days
        except (TypeError, ValueError):
            since = 0
        if since > settings["stale_days"]:
            return ("No backup made since setup -- check the backup drive and log", "red")
        return ("Backups: set up, none made yet", "grey")
    last = datetime.fromisoformat(stamp["last_ok"])
    if last.tzinfo is not None:
        last = last.astimezone().replace(tzinfo=None)
    where = ""
    if stamp.get("computer") and str(stamp["computer"]).casefold() != computer_name().casefold():
        where = f" (on {stamp['computer']})"
    if last > now + timedelta(days=1):
        return ("Backup date is in the future -- check the computer clock" + where, "red")
    if stamp.get("warning"):
        return (str(stamp["warning"]) + where, "red")
    age = (now.date() - last.date()).days
    if age > settings["stale_days"]:
        return (f"Last backed up {_days(age)} ago -- check the backup drive" + where, "red")
    return (f"Last backed up: {last.strftime('%a')} {last.day} {last.strftime('%b, %H:%M')}" + where, "ok")
