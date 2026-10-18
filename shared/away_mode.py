"""Away mode -- read the records on a laptop, never writing (Wil, 18 Oct 2026).

The desktop makes a nightly "away copy" of the databases that change (scripts/make_away_copy.py)
into OneDrive\\Observatum away copy. A laptop marked as an away machine (the marker file
%LOCALAPPDATA%\\Flauna\\away_machine.json, local, never in OneDrive) reads a local copy of
everything in %LOCALAPPDATA%\\Flauna\\away_data. paths.py points DATA_DIR there on such a
machine, so the live, synced ROOT\\data folder is never opened for writing. Records made away go
into workbooks and are imported at home.

    py -3.14 -m shared.away_mode        refresh the local copy, then start Observatum

Nothing here deletes anything. The local copy is a copy of copies, replaced in place.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import paths

# The databases that change with use: made nightly on the desktop, copied here from AWAY_DIR.
CHANGING_DBS = ("observatum.db", "examen.db", "gamification.db", "munia.db", "lector.db")
# Reference data: put in the away copy only when changed (the laptop opens nothing in
# ROOT\data with SQLite).
STATIC_DBS = ("codex.db", "uksi.db", "pantheon.db", "vc_lookup.db", "vc_splits.db")
ALL_DBS = CHANGING_DBS + STATIC_DBS
# Plain files read from ROOT\data on the laptop (OneDrive keeps them current).
STATIC_FILES = ("saved_filters.json",)
STATIC_DIRS = ("maps", "conservation-designations-20260609")
MANIFEST = "manifest.json"
STATE_FILE = "_static_state.json"
_SKIP_NAMES = ("_backups", "_expired")
_SKIP_SUFFIXES = (".db", ".mdb", ".tmp", ".partial", "-wal", "-shm")
NO_COPY_ENV = "BIOSOFT_NO_AWAY_COPY"


def away_dir() -> Path:
    """The nightly away copy in OneDrive. Computed on call so tests can move the home folder."""
    return Path.home() / "OneDrive" / "Observatum away copy"


def marker_path() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    return (Path(base) if base else Path.home() / "AppData" / "Local") / "Flauna" / "away_machine.json"


def local_data_dir() -> Path:
    return marker_path().parent / "away_data"


def is_away_machine() -> bool:
    """True when the marker file exists (read now, not at import)."""
    try:
        return marker_path().is_file()
    except OSError:
        return False


def read_manifest(folder: Path) -> Optional[dict]:
    try:
        return json.loads((Path(folder) / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def format_made_at(made_at: str) -> str:
    """'2026-10-18T02:00:05+01:00' -> 'Sun 18 Oct 2026 02:00'."""
    try:
        return datetime.fromisoformat(made_at).strftime("%a %d %b %Y %H:%M")
    except (TypeError, ValueError):
        return str(made_at)


def banner_text(made_at: str) -> str:
    return (f"Read-only copy from {format_made_at(made_at)}. Nothing you do here is saved; "
            "record in a workbook and import at home.")


def current_made_at() -> Optional[str]:
    m = read_manifest(Path(paths.AWAY_MANIFEST).parent)
    return m.get("made_at") if m else None


def start_away_copy_in_background() -> bool:
    """Start make_away_copy.py --if-older-than 20 detached. Never blocks, never raises.

    Not in away mode, and not when BIOSOFT_NO_AWAY_COPY is set (tests). True if started.
    """
    try:
        if os.environ.get(NO_COPY_ENV) or getattr(paths, "AWAY_MODE", False):
            return False
        script = Path(paths.ROOT) / "scripts" / "make_away_copy.py"
        if not script.is_file():
            return False
        cmd = [sys.executable, str(script), "--if-older-than", "20"]
        kw = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                  stderr=subprocess.DEVNULL, cwd=str(paths.ROOT))
        if sys.platform == "win32":
            kw["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
        else:
            kw["start_new_session"] = True
        subprocess.Popen(cmd, **kw)
        return True
    except Exception as e:
        print(f"[away copy] not started: {e}")
        return False


# --- the local copy on the laptop -------------------------------------------------------------

def away_active() -> bool:
    """True on an away machine (paths.AWAY_MODE, or the marker file)."""
    return bool(getattr(paths, "AWAY_MODE", False)) or is_away_machine()


def refuse_if_away(what: str) -> None:
    """For scripts that write: stop with a message on an away laptop (read-only copy)."""
    if away_active():
        print(f"{what}: refused -- this is an away machine (a read-only copy). Nothing changed.")
        raise SystemExit(1)


def sha256_of(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def quick_check(path) -> str:
    """PRAGMA quick_check on a copy, opened read-only. 'ok' or the problem."""
    c = sqlite3.connect(f"file:{Path(path).as_posix()}?mode=ro", uri=True)
    try:
        return str(c.execute("PRAGMA quick_check").fetchone()[0])
    finally:
        c.close()


def _copy_file(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp")
    shutil.copy2(src, tmp)
    os.replace(tmp, dest)


def _skipped(name: str) -> bool:
    low = name.lower()
    return (name in _SKIP_NAMES or low.startswith("observatum_pre_")
            or low.endswith(_SKIP_SUFFIXES))


def _static_items(src_data: Path):
    """(relative path, source file) for every non-database static file to carry over.

    Databases are never taken from ROOT\\data (the laptop must not open anything there with
    SQLite): they all come from the away copy.
    """
    for n in STATIC_FILES:
        if (src_data / n).is_file():
            yield n, src_data / n
    for d in STATIC_DIRS:
        base = src_data / d
        if not base.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [x for x in dirnames if not _skipped(x)]
            for f in filenames:
                if not _skipped(f):
                    p = Path(dirpath) / f
                    yield p.relative_to(src_data).as_posix(), p


def _refresh_static(src_data: Path, dest_data: Path) -> int:
    state_path = dest_data / STATE_FILE
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    copied = 0
    for rel, src in _static_items(src_data):
        dest = dest_data / rel
        st = src.stat()
        sig = [st.st_size, st.st_mtime_ns]
        if dest.is_file() and state.get(rel) == sig:
            continue
        _copy_file(src, dest)
        state[rel] = sig
        copied += 1
    state_path.write_text(json.dumps(state), encoding="utf-8")
    return copied


class StillArriving(Exception):
    """The newest away copy does not verify yet (OneDrive is still syncing it)."""


def manifest_folder(away: Path, manifest: dict) -> Path:
    slot = manifest.get("slot")
    return Path(away) / slot if slot else Path(away)


def _refresh_databases(away: Path, dest_data: Path, manifest: dict) -> int:
    """All databases from the away copy's slot. All-or-nothing: every file is copied to a
    .tmp beside its target and its sha256 and quick_check verified before any is replaced,
    and the new manifest is written last. Raises StillArriving on any mismatch."""
    mine = read_manifest(dest_data)
    if mine and mine.get("made_at") == manifest.get("made_at"):
        return 0
    folder = manifest_folder(away, manifest)
    staged = []
    for f in manifest.get("files", []):
        name, want = f["name"], f.get("sha256")
        src = folder / name
        tmp = dest_data / (name + ".tmp")
        try:
            if not src.is_file():
                raise StillArriving(f"{name} is missing")
            shutil.copyfile(src, tmp)
            if want and sha256_of(tmp) != want:
                raise StillArriving(f"{name} does not match its checksum")
            problem = quick_check(tmp)
            if problem != "ok":
                raise StillArriving(f"{name}: quick_check said {problem}")
        except (OSError, sqlite3.Error) as e:
            raise StillArriving(f"{name}: {e}")
        staged.append((tmp, dest_data / name))
    for tmp, final in staged:
        os.replace(tmp, final)
    mtmp = dest_data / (MANIFEST + ".tmp")
    mtmp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    os.replace(mtmp, dest_data / MANIFEST)
    return len(staged)


def refresh_local_copy(root: Optional[Path] = None, away: Optional[Path] = None,
                       dest: Optional[Path] = None) -> str:
    """Build or refresh away_data. Returns the made_at of the copy now in use.

    When the newest away copy does not verify (OneDrive still syncing) the previous local copy
    is kept and made_at is not recorded. Raises FileNotFoundError when there is no away copy
    and no earlier local copy, RuntimeError when the first copy cannot be verified.
    """
    root = Path(root) if root else Path(paths.ROOT)
    away = Path(away) if away else away_dir()
    dest = Path(dest) if dest else local_data_dir()
    if dest.resolve() == (root / "data").resolve():
        raise RuntimeError("the local copy must not be the live data folder")
    dest.mkdir(parents=True, exist_ok=True)
    manifest = read_manifest(away)
    mine = read_manifest(dest)
    if manifest is None and mine is None:
        raise FileNotFoundError(f"No away copy found in {away} (no manifest.json)")
    n_dyn = 0
    if manifest is None:
        print(f"The away copy is not reachable; using the copy from "
              f"{format_made_at(mine['made_at'])}.")
    else:
        try:
            n_dyn = _refresh_databases(away, dest, manifest)
        except StillArriving as e:
            if mine is None:
                raise RuntimeError(f"the away copy is still arriving ({e}); try again later")
            print("the newest away copy is still arriving; using the copy from "
                  f"{format_made_at(mine['made_at'])}.")
            manifest = None
    n_static = _refresh_static(root / "data", dest)
    print(f"Local copy: {n_static} file(s) updated, {n_dyn} database(s) updated.")
    return (manifest or read_manifest(dest))["made_at"]


def main() -> int:
    if not is_away_machine():
        print(f"This is not an away machine (no {marker_path()}). Nothing done.")
        return 1
    try:
        made_at = refresh_local_copy()
        print(f"Away copy from {format_made_at(made_at)}.")
    except Exception as e:
        if read_manifest(local_data_dir()) is None:
            print(f"Cannot refresh the local copy: {e}")
            return 1
        print(f"Could not refresh ({e}); starting on the earlier local copy.")
    import runpy
    runpy.run_module("src.main", run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
