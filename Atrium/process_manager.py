"""Atrium — Process Manager

Launches suite applications and knows when one is already open.

One copy of each app (ATR-1, 10 Oct 2026): before launching, Atrium looks for the
app's own window (by its title, on Windows) and for the process it started
itself. If either is found the window is brought forward instead of a second
copy being started -- including a copy opened from run.bat or a launcher.

Lector is a console tool: it is started in a new console window, titled so it
can be found again (Atrium/console_launch.py).

The Tabella workbook code (open / regenerate, which deleted the old .xlsm files)
was removed 10 Oct 2026 (ATR-2); Tabella was retired 7 Oct.

Data Entry is not here (review, 10 Oct 2026): it is used inside Observatum, and its
standalone launcher is a development tool that only opens a development copy. A
launch that ends at once with an error code is reported (early_exit_code), so a
failed start is never silent.
"""

import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

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
    module: str           # python -m module name
    colour: str           # hex colour for the icon background
    colour_light: str     # lighter shade for icon bg
    window_title: str = ""   # the start of the app's main window title (how it is found)
    args: tuple = ()         # extra command-line arguments
    console: bool = False    # a console tool: own console window, titled window_title
    process: subprocess.Popen | None = field(default=None, repr=False)


# Lector's console window title: set by console_launch, found by this.
LECTOR_TITLE = "Lector — BHL literature (Atrium)"

APPS = [
    AppDef("Observatum", "Biological recording", "beetle.png",
           "src.main", "#6b4c8a", "#f0eaf5", window_title="Observatum V2"),
    AppDef("Examen", "Species assessment", "beetle.png",
           "Examen", "#5a4d78", "#f0edf5",
           window_title="Examen — Species Assessment Tool"),
    AppDef("Codex", "Conservation manager", "mushroom.png",
           "Codex", "#2d5016", "#e8f0e2",
           window_title="Codex — Conservation Status Manager"),
    AppDef("Curator", "Collection organiser", "mushroom.png",
           "Curator", "#4a7c59", "#e6f0ea", window_title="Collection Layout Planner"),
    AppDef("Munia", "Capacity planner", "bat.png",
           "Munia", "#4a6580", "#e4ecf2", window_title="Munia — Capacity Planner"),
    AppDef("Lector", "BHL literature (console)", "bat.png",
           "Lector", "#8b8178", "#f3f1ee", window_title=LECTOR_TITLE, console=True),
]

# launch_app results
LAUNCHED, FOCUSED, ALREADY_RUNNING, FAILED = "launched", "focused", "running", "failed"


def _python(console: bool = False) -> str:
    """The Python to run an app with. Atrium itself runs under pythonw; a console
    tool needs python.exe, or its console window stays empty."""
    exe = sys.executable
    if console:
        p = Path(exe)
        if p.name.lower() == "pythonw.exe":
            candidate = p.with_name("python.exe")
            if candidate.exists():
                return str(candidate)
    return exe


def _env() -> dict:
    """Return environment with PYTHONPATH set for the suite."""
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT), str(ROOT / "Observatum")])
    return env


def command_for(app: AppDef) -> list:
    """The command line that starts the app."""
    if app.console:
        return [_python(True), "-m", "Atrium.console_launch", app.module,
                app.window_title, *app.args]
    return [_python(), "-m", app.module, *app.args]


def creation_flags(app: AppDef) -> int:
    if sys.platform != "win32":
        return 0
    return subprocess.CREATE_NEW_CONSOLE if app.console else subprocess.CREATE_NO_WINDOW


# ---------------------------------------------------------------------------
# Finding an app's window (Windows only; elsewhere nothing is found)
# ---------------------------------------------------------------------------

# Explorer windows are titled with the folder name ("Codex", "Lector") and must
# never be mistaken for the app.
_IGNORED_CLASSES = {"CabinetWClass", "ExploreWClass"}


def _visible_windows():
    """[(hwnd, title, class name)] of visible top-level windows."""
    if sys.platform != "win32":
        return []
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _cb(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                cls = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(hwnd, cls, 256)
                found.append((hwnd, buf.value, cls.value))
        return True

    try:
        user32.EnumWindows(_cb, 0)
    except Exception:  # noqa: BLE001 -- no window search is not fatal
        return []
    return found


def find_window(app: AppDef, windows=None):
    """The app's main window handle, or None."""
    if not app.window_title:
        return None
    for hwnd, title, cls in (windows if windows is not None else _visible_windows()):
        if cls in _IGNORED_CLASSES:
            continue
        if title == app.window_title or title.startswith(app.window_title + " "):
            return hwnd
    return None


def bring_to_front(hwnd) -> bool:
    if sys.platform != "win32" or not hwnd:
        return False
    import ctypes
    user32 = ctypes.windll.user32
    try:
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)          # SW_RESTORE
        return bool(user32.SetForegroundWindow(hwnd))
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# Launching
# ---------------------------------------------------------------------------

def launch_app(app: AppDef):
    """Start the app, or bring the open copy forward. Returns (result, message):
    LAUNCHED, FOCUSED (an open copy was brought forward), ALREADY_RUNNING (it is
    starting or its window could not be raised) or FAILED with the reason."""
    hwnd = find_window(app)
    if hwnd:
        bring_to_front(hwnd)
        return FOCUSED, f"{app.name} is already open."
    if _process_alive(app):
        return ALREADY_RUNNING, f"{app.name} is already running (it may still be starting)."
    try:
        app.process = subprocess.Popen(
            command_for(app), cwd=str(ROOT), env=_env(),
            creationflags=creation_flags(app))
        return LAUNCHED, ""
    except Exception as e:  # noqa: BLE001
        return FAILED, f"{app.name} could not be started: {e}"


# A process that ends this soon after launch with a non-zero code failed to start.
EARLY_EXIT_SECONDS = 3.0


def early_exit_code(app: AppDef):
    """The exit code if the process Atrium started has already ended with an error,
    else None (still running, never started, or closed normally with 0)."""
    proc = app.process
    if proc is None:
        return None
    code = proc.poll()
    return code if code not in (None, 0) else None


def _process_alive(app: AppDef) -> bool:
    return app.process is not None and app.process.poll() is None


def is_running(app: AppDef, windows=None) -> bool:
    """Open: started by Atrium and still alive, or its window is on screen."""
    return _process_alive(app) or find_window(app, windows) is not None


def running_count() -> int:
    """Count how many apps are currently running."""
    windows = _visible_windows()
    return sum(1 for a in APPS if is_running(a, windows))
