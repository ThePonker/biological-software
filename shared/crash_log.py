"""A crash record for every app (25 Oct 2026): when an app is started from Atrium there is no
console, so a crash left nothing to read (Observatum closed while loading the NNR layer on Wil's
PC and the cause was lost).

    from shared import crash_log
    crash_log.install("observatum")          # first thing, before QApplication

writes to data\\logs\\crash_<app>_<YYYY-MM>.log (one file a month per app, appended to; nothing is
ever removed):
- a hard crash (segfault, abort, a Qt fatal error): Python's faulthandler dumps every thread's stack;
- an exception nobody caught (main thread or another thread), with its traceback;
- Qt's own critical and fatal messages (e.g. Qt Quick failing on the graphics card).
Each entry starts with the date and time. Everything still goes to the console as before. Nothing
here can stop an app starting: any problem setting it up is ignored.
"""
from __future__ import annotations

import faulthandler
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path

_FILE = None        # kept open for faulthandler, which writes to the file descriptor directly
_PATH = None


def log_dir() -> Path:
    try:
        import paths
        return Path(paths.DATA_DIR) / "logs"
    except Exception:
        return Path.home() / "BiologicalSoftware_logs"


def log_path(app: str, when: datetime | None = None) -> Path:
    when = when or datetime.now()
    return log_dir() / f"crash_{app}_{when:%Y-%m}.log"


def _write(text: str) -> None:
    if _FILE is None:
        return
    try:
        _FILE.write(f"\n=== {datetime.now():%Y-%m-%d %H:%M:%S} ===\n{text.rstrip()}\n")
        _FILE.flush()
    except Exception:
        pass


def note(text: str, exc: BaseException | None = None) -> None:
    """Append a dated entry (with the traceback when `exc` is given) to this app's log. Does nothing
    if install() was not called or the log cannot be written; never raises."""
    try:
        if _FILE is None:
            return
        if exc is not None:
            text = f"{text}\n" + "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        _write(text)
    except Exception:
        pass


def _excepthook(kind, value, tb):
    _write("Uncaught exception:\n" + "".join(traceback.format_exception(kind, value, tb)))
    sys.__excepthook__(kind, value, tb)


def _thread_hook(args):
    _write(f"Uncaught exception in thread {getattr(args.thread, 'name', '?')}:\n"
           + "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)))
    threading.__excepthook__(args)


def _qt_handler(mode, context, message):
    try:
        from PySide6.QtCore import QtMsgType
        if mode in (QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
            where = f" ({context.file}:{context.line})" if getattr(context, "file", None) else ""
            _write(f"Qt {'fatal' if mode == QtMsgType.QtFatalMsg else 'critical'}{where}: {message}")
    except Exception:
        pass
    if sys.stderr is not None:          # still on the console, as Qt's own handler would
        try:
            print(message, file=sys.stderr)
        except Exception:
            pass


def install(app: str) -> Path | None:
    """Start recording crashes for `app`; the log file's path, or None if it could not be set up."""
    global _FILE, _PATH
    if _FILE is not None:
        return _PATH
    try:
        path = log_path(app)
        path.parent.mkdir(parents=True, exist_ok=True)
        _FILE = open(path, "a", encoding="utf-8", buffering=1)
        _PATH = path
        faulthandler.enable(file=_FILE, all_threads=True)
        sys.excepthook = _excepthook
        threading.excepthook = _thread_hook
        try:
            from PySide6.QtCore import qInstallMessageHandler
            qInstallMessageHandler(_qt_handler)
        except Exception:
            pass
        _write(f"{app} started (Python {sys.version.split()[0]})")
        return path
    except Exception:
        return None
