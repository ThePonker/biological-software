"""gc_schedule -- the cyclic garbage collector runs from a timer, never inside a Qt handler (R17, 10 Nov 2026).

On Wil's PC (Python 3.14, PySide6 6.12) Observatum crashed with access violations whose Python
stack showed "Garbage-collecting" in the middle of Qt event handlers (a mouse release in the map's
Identify, a synchronous map fetch). Python starts a collection at an arbitrary allocation, so one
can start inside a Qt callback and free PySide wrappers while Qt is still using them.

install(app) therefore:
- switches the automatic collector off (gc.disable()) and collects from a QTimer on the GUI
  thread, i.e. from the event loop, not from inside another handler: generation 0 about every
  second, generation 1 about every 10 s, everything about every 2 minutes or sooner when
  gc.get_count()[2] passes a threshold;
- postpones a tick (tries again at the next one) while a mouse button is held (a click or a drag
  is in progress) or a worker thread has the collector held off (shared/gc_pause.py);
- freezes what the program has loaded (gc.freeze(), once) a few seconds after its first window is
  shown, so later passes skip it;
- tells gc_pause that this module owns the on/off state, so gc_pause.release() no longer switches
  automatic collection back on.

BIOSOFT_GC_AUTO=1 in the environment keeps Python's own automatic collector (for diagnosis).
"""
from __future__ import annotations

import gc
import os
import time

from shared import gc_pause

ENV_AUTO = "BIOSOFT_GC_AUTO"
TICK_MS = 1000                  # generation 0
GEN1_EVERY_S = 10.0
FULL_EVERY_S = 120.0
FULL_AT_GEN2_COUNT = 12         # gc.get_count()[2]: gen-1 passes since the last full one
FREEZE_AFTER_S = 8.0            # after the first real window is visible

_scheduler = None


def auto_requested(env=None) -> bool:
    """True when BIOSOFT_GC_AUTO=1: leave Python's automatic collection alone."""
    return (os.environ if env is None else env).get(ENV_AUTO, "").strip() == "1"


def _mouse_held() -> bool:
    from PySide6.QtWidgets import QApplication
    return bool(QApplication.mouseButtons())


def _window_visible() -> bool:
    from PySide6.QtWidgets import QApplication, QSplashScreen
    return any(w.isVisible() and not isinstance(w, QSplashScreen)
               for w in QApplication.topLevelWidgets())


class GcScheduler:
    """The timer and its policy. tick() is what the timer calls; tests call it directly."""

    def __init__(self, parent=None, clock=time.monotonic, mouse_held=_mouse_held,
                 window_visible=_window_visible):
        from PySide6.QtCore import QTimer
        self._clock = clock
        self._mouse_held = mouse_held
        self._window_visible = window_visible
        now = clock()
        self._last_gen1 = self._last_full = now
        self._seen_window_at = None
        self.frozen = False
        self.postponed = 0
        self.runs = {0: 0, 1: 0, 2: 0}
        self.timer = QTimer(parent)
        self.timer.setInterval(TICK_MS)
        self.timer.timeout.connect(self.tick)

    def start(self) -> None:
        self.timer.start()

    def stop(self) -> None:
        self.timer.stop()

    def busy(self) -> bool:
        return self._mouse_held() or gc_pause.is_held()

    def tick(self) -> int:
        """One timer tick: the generation collected (0, 1 or 2), or -1 when postponed."""
        if self.busy():
            self.postponed += 1
            return -1
        now = self._clock()
        self._maybe_freeze(now)
        if (now - self._last_full >= FULL_EVERY_S) or gc.get_count()[2] >= FULL_AT_GEN2_COUNT:
            generation = 2
            self._last_full = self._last_gen1 = now
        elif now - self._last_gen1 >= GEN1_EVERY_S:
            generation = 1
            self._last_gen1 = now
        else:
            generation = 0
        gc.collect(generation)
        self.runs[generation] += 1
        return generation

    def _maybe_freeze(self, now: float) -> None:
        if self.frozen:
            return
        if not self._window_visible():
            self._seen_window_at = None
            return
        if self._seen_window_at is None:
            self._seen_window_at = now
        elif now - self._seen_window_at >= FREEZE_AFTER_S:
            gc.collect()
            gc.freeze()
            self.frozen = True


def install(app, env=None):
    """Take over garbage collection for this program. Returns the scheduler, or None when
    BIOSOFT_GC_AUTO=1 asks for Python's automatic collector (nothing is changed then)."""
    global _scheduler
    if auto_requested(env):
        return None
    if _scheduler is not None:
        return _scheduler
    gc_pause.set_managed(True)
    gc.disable()
    _scheduler = GcScheduler(app)
    _scheduler.start()
    return _scheduler


def installed():
    return _scheduler


def uninstall() -> None:
    """Stop the timer and hand automatic collection back to Python (tests: an app's main()
    called inside the test run must not leave the collector off for the tests after it)."""
    global _scheduler
    if _scheduler is None:
        return
    try:
        _scheduler.stop()
    except RuntimeError:            # the timer's QObject already gone
        pass
    _scheduler = None
    gc_pause.set_managed(False)
    gc.enable()
