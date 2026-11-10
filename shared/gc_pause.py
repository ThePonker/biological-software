"""Switch Python's cyclic garbage collector off while a worker thread runs (R16, 10 Nov 2026).

A collection triggered by an allocation in a worker thread can finalise a Qt wrapper (a widget or
a path) that was made on the GUI thread and has become garbage: Qt objects must be destroyed on
their own thread, and the interpreter crashed in a test when it happened. views/background_loader.py
does the same while the app loads. Calls nest (the Mapping tab's Generate thread and the map's
look-ahead may overlap): the collector goes off at the first acquire() and back on, if it was on,
at the last release(). Reference counting is not affected, only the collection of reference
cycles, which is delayed by the length of a job (well under a second).
"""
from __future__ import annotations

import gc
import threading

_LOCK = threading.Lock()
_holds = 0
_was_on = False


def acquire() -> None:
    global _holds, _was_on
    with _LOCK:
        if _holds == 0:
            _was_on = gc.isenabled()
            gc.disable()
        _holds += 1


def release() -> None:
    global _holds
    with _LOCK:
        if _holds == 0:
            return
        _holds -= 1
        if _holds == 0 and _was_on:
            gc.enable()
