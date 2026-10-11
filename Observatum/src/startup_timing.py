"""Startup phase timings, printed only when asked for.

    run.bat --timing            (or set OBSERVATUM_TIMING=1 before run.bat)

prints lines like

    [timing]   0.84 s  (+0.84)  imports done
    [timing]   3.10 s  (+0.21)  window shown
    [timing]   3.62 s  (+0.52)  Home figures filled

Seconds are counted from the moment Python started running Observatum's main module.
Added for the startup-speed work, 11 Oct 2026. Costs nothing when not switched on.
"""

import os
import sys
import time

_START = time.perf_counter()


def enabled() -> bool:
    return "--timing" in sys.argv or os.environ.get("OBSERVATUM_TIMING", "") not in ("", "0")


class _Timer:
    def __init__(self, on: bool):
        self.on = on
        self.last = _START
        self.marks = []               # (label, seconds since start), kept for tests

    def mark(self, label: str):
        now = time.perf_counter()
        self.marks.append((label, now - _START))
        if self.on:
            print(f"[timing] {now - _START:6.2f} s  (+{now - self.last:4.2f})  {label}", flush=True)
        self.last = now


_timer = None


def timer() -> _Timer:
    global _timer
    if _timer is None:
        _timer = _Timer(enabled())
    return _timer


def reset_start():
    """Count from now (main() calls this first thing)."""
    global _START
    _START = time.perf_counter()
    t = timer()
    t.last = _START
    t.marks.clear()
