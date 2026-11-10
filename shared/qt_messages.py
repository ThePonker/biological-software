"""qt_messages -- hide Qt's harmless exit-time "QThreadStorage: entry N destroyed before end of
thread" line (R17, 10 Nov 2026).

Qt prints it when the process exits while a thread that used Qt (fonts, painting: Qt keeps a
per-thread cache for them) has not ended yet; Qt's own thread-local tables are torn down first.
Nothing is lost: the process is already closing. The suite's worker threads are daemon threads
that Python does not wait for, so Qt cannot be told earlier. I could not find a thread of ours
that should be ended and is not, and could not reproduce the line on Linux, so it is filtered,
that one message only; every other message goes to the handler that was installed before
(Data Entry's), or to stderr as before.
"""
from __future__ import annotations

import sys

_MARKER = "QThreadStorage: entry"
_TAIL = "destroyed before end of thread"
_installed = False


def is_thread_storage_exit_noise(message: str) -> bool:
    return _MARKER in message and _TAIL in message


def install() -> None:
    """Install the filter once. Safe to call from every program; later handlers that wrap it keep working."""
    global _installed
    if _installed:
        return
    from PySide6.QtCore import qInstallMessageHandler
    previous = None

    def handler(mode, context, message):
        try:
            if is_thread_storage_exit_noise(message):
                return
            if previous is not None:
                previous(mode, context, message)
            else:
                sys.stderr.write(message + "\n")
        except Exception:                   # during interpreter shutdown: say nothing, never crash
            pass

    previous = qInstallMessageHandler(handler)
    _installed = True
