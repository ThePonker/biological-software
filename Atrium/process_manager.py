"""Atrium — Process Manager

Launches suite applications and monitors running state.
Special handling for Tabella: opens master .xlsm read-only in Excel.
"""

import subprocess
import stat
import sys
import os
from pathlib import Path
from dataclasses import dataclass, field

try:
    import paths
    ROOT = paths.ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent


@dataclass
class AppDef:
    """Definition of a launchable app."""
    name: str
    subtitle: str
    icon_file: str        # filename in assets/
    module: str           # python -m module name, or "" for special handling
    colour: str           # hex colour for the icon background
    colour_light: str     # lighter shade for icon bg
    process: subprocess.Popen | None = field(default=None, repr=False)
    special: str = ""     # "tabella_workbook" or "generate_workbook"


APPS = [
    AppDef("Observatum", "Biological recording", "beetle.png",
           "src.main", "#6b4c8a", "#f0eaf5"),
    AppDef("Codex", "Conservation manager", "mushroom.png",
           "Codex", "#2d5016", "#e8f0e2"),
    AppDef("Curator", "Collection organiser", "mushroom.png",
           "Curator", "#4a7c59", "#e6f0ea"),
    AppDef("Munia", "Capacity planner", "bat.png",
           "Munia", "#4a6580", "#e4ecf2"),
]


def _python() -> str:
    """Return the Python executable path."""
    return sys.executable


def _env() -> dict:
    """Return environment with PYTHONPATH set for the suite."""
    env = os.environ.copy()
    root = str(ROOT)
    obs = str(ROOT / "Observatum")
    env["PYTHONPATH"] = f"{root};{obs}"
    return env


def launch_app(app: AppDef) -> bool:
    """Launch an app. Returns True if launched, False if already running."""
    if is_running(app):
        return False

    if app.special == "tabella_workbook":
        return _open_tabella_workbook()
    elif app.special == "generate_workbook":
        return _run_generator()

    cmd = [_python(), "-m", app.module]
    try:
        app.process = subprocess.Popen(
            cmd, cwd=str(ROOT), env=_env(),
            creationflags=subprocess.CREATE_NO_WINDOW
            if sys.platform == "win32" else 0)
        return True
    except Exception as e:
        print(f"Failed to launch {app.name}: {e}")
        return False


def is_running(app: AppDef) -> bool:
    """Check if an app's process is still running."""
    if app.special == "tabella_workbook":
        return False  # Excel is external, we don't track it
    if app.process is None:
        return False
    return app.process.poll() is None


def running_count() -> int:
    """Count how many apps are currently running."""
    return sum(1 for a in APPS if is_running(a))


def _find_latest_xlsm() -> Path | None:
    """Find the most recent .xlsm in Tabella/output/."""
    output_dir = ROOT / "Tabella" / "output"
    if not output_dir.exists():
        return None
    files = sorted(output_dir.glob("*.xlsm"), key=lambda f: f.stat().st_mtime,
                   reverse=True)
    return files[0] if files else None


def _open_tabella_workbook() -> bool:
    """Open the latest .xlsm in Excel as read-only."""
    xlsm = _find_latest_xlsm()
    if not xlsm:
        return False
    if sys.platform == "win32":
        try:
            # Excel /r flag opens read-only
            subprocess.Popen(["cmd", "/c", "start", "", "excel.exe",
                              "/r", str(xlsm)])
            return True
        except Exception:
            pass
        # Fallback: just open the file
        try:
            os.startfile(str(xlsm))
            return True
        except Exception:
            return False
    return False


def _run_generator() -> bool:
    """Run the Tabella workbook generator. Removes old workbooks first."""
    # Delete existing workbooks before generating
    output_dir = ROOT / "Tabella" / "output"
    if output_dir.exists():
        for old_file in output_dir.glob("*.xlsm"):
            try:
                old_file.unlink()
            except OSError:
                pass  # File may be open in Excel
    cmd = [_python(), "-m", "Tabella.create_data_entry_workbook"]
    try:
        subprocess.run(cmd, cwd=str(ROOT), env=_env(),
                         creationflags=subprocess.CREATE_NEW_CONSOLE
                         if sys.platform == "win32" else 0)
        # Write-protect the newly generated file
        latest = _find_latest_xlsm()
        if latest:
            try:
                latest.chmod(stat.S_IREAD)
            except OSError:
                pass
        return True
    except Exception:
        return False
