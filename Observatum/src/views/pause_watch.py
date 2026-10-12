"""Where the window paused during the background loading (run.bat --timing only; Round 8).

The background loader's 5 ms heartbeat measures the longest pause of the GUI thread; this
says WHERE each pause over 100 ms happened, so a pause on Wil's PC can be found without
guessing:

- a watchdog thread looks every 20 ms; while the GUI thread has missed its heartbeat for
  more than 50 ms it samples the GUI thread's Python stack (sys._current_frames) and the
  innermost frame of every other loading thread;
- each pause is kept with the slice running during it (or the slices just before and after
  it, when it fell between slices) and the most-sampled places;
- every garbage collection over 20 ms is timed (gc.callbacks), with the thread it ran in;
- report() gives the "pauses over 100 ms" lines printed at the end of --timing.

run.bat --timing --timing-events also notes the last Qt event the GUI thread started
handling, for a pause inside Qt itself. Off by default: every event then passes through
Python, which needs Python's lock (GIL) and so slows the window a little while it loads.

Only created when --timing is on: costs nothing otherwise.

Reading it: a GUI-thread sample "main (Observatum/src/main.py ...)" means the GUI thread was
inside Qt itself (layout, painting, sizing table columns) rather than in Observatum's Python.
With a loading thread sampled "meanwhile", that is usually Qt calling back into Python item
by item (every widget made in PySide is a Python object) and each call waiting its turn for
Python's lock (GIL): the 1.2 s pause on Wil's PC, 12 Oct 2026, was a table header sizing its
columns to their contents that way (now done in a slice: background_steps.settle_headers).
"""

import gc
import os
import sys
import threading
import time
from collections import Counter
from typing import List, Optional

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

PAUSE_S = 0.100          # pauses longer than this are kept
SAMPLE_AFTER_S = 0.050   # the GUI thread is sampled once it has missed its beat this long
WATCH_EVERY_S = 0.020
STACK_DEPTH = 4          # GUI-thread frames kept per sample (innermost first)
EVENTS_FLAG = "--timing-events"   # also note the last Qt event (slows the window a little)

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))       # the suite root, cut from file names


def _where(frame) -> str:
    path = frame.f_code.co_filename
    if path.startswith(_ROOT + os.sep):
        path = path[len(_ROOT) + 1:]
    else:
        path = os.path.basename(path)
    return f"{frame.f_code.co_name} ({path.replace(os.sep, '/')}:{frame.f_lineno})"


def _stack(frame, depth: int = STACK_DEPTH) -> str:
    parts = []
    while frame is not None and frame.f_code.co_filename == __file__:
        frame = frame.f_back          # the event filter below: not what was paused
    while frame is not None and len(parts) < depth:
        parts.append(_where(frame))
        frame = frame.f_back
    return " <- ".join(parts) if parts else "?"


class _LastEvent(QObject):
    """Notes the last Qt event the GUI thread started handling (what it was doing when the
    sample finds it inside Qt itself)."""

    def __init__(self):
        super().__init__()
        self.last = None              # (event type, receiver class, perf_counter)

    def eventFilter(self, obj, event):
        self.last = (event.type(), type(obj).__name__, time.perf_counter())
        return False


def _event_name(last) -> str:
    if last is None:
        return ""
    etype, cls, t = last
    name = getattr(etype, "name", str(etype))
    return f"last Qt event {name} to {cls}, {(time.perf_counter() - t) * 1000:.0f} ms before"


class Pause:
    def __init__(self, start: float, seconds: float):
        self.start = start
        self.seconds = seconds
        self.gui = Counter()          # GUI-thread stacks sampled
        self.workers = Counter()      # "thread: innermost frame" sampled meanwhile
        self.gc = []                  # (seconds, generation, thread) of collections in it
        self.during = ""              # slice(s) running in the pause
        self.before = ""              # the slice that ended last before it
        self.after = ""               # the slice that started first after it


class PauseWatch:
    """Started and stopped by BackgroundLoader when --timing is on."""

    def __init__(self, clock_start: float = 0.0):
        self._clock_start = clock_start   # report times as seconds since startup
        self._main_id = threading.main_thread().ident
        self._last_beat = time.perf_counter()
        self._samples = Counter()
        self._workers = Counter()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._events: Optional[_LastEvent] = None
        self.pauses: List[Pause] = []
        self.slices: List[tuple] = []     # (key, t0, t1)
        self.collections: List[tuple] = []   # (t0, t1, generation, thread name), > 20 ms
        self._gc_start = {}               # thread id -> perf_counter at the collection start

    def start(self):
        app = QApplication.instance()
        if app is not None and EVENTS_FLAG in sys.argv:
            self._events = _LastEvent()
            app.installEventFilter(self._events)
        gc.callbacks.append(self._on_gc)
        self._last_beat = time.perf_counter()
        self._thread = threading.Thread(target=self._watch, name="observatum-pause-watch",
                                        daemon=True)
        self._thread.start()

    def stop(self):
        app = QApplication.instance()
        if self._events is not None and app is not None:
            app.removeEventFilter(self._events)
        if self._on_gc in gc.callbacks:
            gc.callbacks.remove(self._on_gc)
        self._stop.set()
        if self._thread is not None:
            self._thread.join(2)

    # ---------------------------------------------------------------- GUI thread
    def beat(self, now: float, gap: float):
        """The heartbeat came `gap` seconds late (called by the loader's heartbeat)."""
        with self._lock:
            samples, workers = self._samples, self._workers
            self._samples, self._workers = Counter(), Counter()
            self._last_beat = now
        if gap > PAUSE_S:
            p = Pause(now - gap, gap)
            p.gui, p.workers = samples, workers
            self.pauses.append(p)

    def slice_done(self, key: str, t0: float, t1: float):
        self.slices.append((key, t0, t1))

    def _on_gc(self, phase, info):
        """gc.callbacks: a garbage collection holds Python's lock (GIL) throughout, so it
        pauses every thread, the window too, whichever thread it runs in."""
        me = threading.get_ident()
        if phase == "start":
            self._gc_start[me] = time.perf_counter()
            return
        t0 = self._gc_start.pop(me, None)
        if t0 is None:
            return
        t1 = time.perf_counter()
        if t1 - t0 > 0.020:
            self.collections.append((t0, t1, info.get("generation"),
                                     threading.current_thread().name))

    # ---------------------------------------------------------------- watchdog
    def _watch(self):
        while not self._stop.wait(WATCH_EVERY_S):
            with self._lock:
                late = time.perf_counter() - self._last_beat
            if late < SAMPLE_AFTER_S:
                continue
            frames = sys._current_frames()
            main = frames.get(self._main_id)
            gui = _stack(main) if main is not None else "?"
            events = self._events
            if events is not None and main is not None and main.f_code.co_name == "main":
                gui += " | " + _event_name(events.last)            # inside app.exec
            names = {t.ident: t.name for t in threading.enumerate()}
            workers = [f"{names.get(ident, ident)}: {_where(f)}"
                       for ident, f in frames.items()
                       if ident not in (self._main_id, threading.get_ident())]
            with self._lock:
                self._samples[gui] += 1
                for w in workers:
                    self._workers[w] += 1
            del frames, main

    # ---------------------------------------------------------------- report
    def _place(self, p: Pause):
        a, b = p.start, p.start + p.seconds
        during = [k for k, t0, t1 in self.slices if t0 < b and t1 > a]
        before = [k for k, t0, t1 in self.slices if t1 <= a]
        after = [k for k, t0, t1 in self.slices if t0 >= b]
        p.during = ", ".join(dict.fromkeys(during))
        p.before = before[-1] if before else "(none: start)"
        p.after = after[0] if after else "(none: end)"
        p.gc = [(t1 - t0, gen, name) for t0, t1, gen, name in self.collections
                if t0 < b and t1 > a]

    def report(self, limit: int = 8) -> List[str]:
        """Lines for --timing: the pauses over 100 ms, longest first."""
        gc_total = sum(t1 - t0 for t0, t1, _g, _n in self.collections)
        gc_line = (f"garbage collections over 20 ms: {len(self.collections)}, "
                   f"{gc_total * 1000:.0f} ms in all")
        if not self.pauses:
            return ["pauses over 100 ms: none", gc_line]
        lines = [f"pauses over 100 ms: {len(self.pauses)} (longest first); {gc_line}"]
        for p in sorted(self.pauses, key=lambda x: -x.seconds)[:limit]:
            self._place(p)
            where = (f"in slice {p.during}" if p.during
                     else f"between slices (after {p.before}, before {p.after})")
            lines.append(f"  {p.seconds * 1000:5.0f} ms at {p.start - self._clock_start:6.2f} s, "
                         f"{where}")
            for secs, gen, name in p.gc:
                lines.append(f"      garbage collection {secs * 1000:.0f} ms (generation {gen}) "
                             f"in thread {name}")
            for stack, n in p.gui.most_common(2):
                lines.append(f"      GUI thread ({n}x): {stack}")
            for w, n in p.workers.most_common(2):
                lines.append(f"      meanwhile ({n}x) {w}")
        return lines
