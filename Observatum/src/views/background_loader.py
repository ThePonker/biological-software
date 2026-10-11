"""Finish loading in the background after the main window has opened (Round 6, 11 Oct 2026).

Wil chose "window early, rest behind": the window opens once Home, Observation Data,
Contributed and Insect Collection are loaded (under the splash screen, startup_preload.py);
the Recording Scheme records, Stats/Reports, Mapping, Settings and the species-search index
then finish here, within a few seconds, while the window can be used. A small line in the
status bar says what is still loading and goes when everything is ready.

The window must keep responding meanwhile, so:
- reading records and other slow data work runs in worker threads (no widget touched
  there; every database read opens its own connection);
- building widgets runs on the GUI thread in short slices, one per turn of the event loop
  (QTimer.singleShot(0)), so clicks and repaints are handled between them.

Each step is a generator function. It does a short piece of GUI work and then yields:

    yield                     # next slice on the next turn of the event loop
    x = yield InThread(fn)    # fn() in a worker thread; resumes with its result (or raises)
    yield WaitFor(pred)       # resumes once pred() is true (checked every POLL_MS)

The steps run in queue order. A step waiting for a thread or a condition lets the next one
run meanwhile. prioritise(key) moves a step to the front (the tab Wil clicked); when_done(key,
fn) runs fn once the step has finished (navigation to a tab that is not ready yet waits for
it). stop() ends everything cleanly when the window closes: the steps' generators are closed,
its on_stop callbacks run (the Recording Scheme worker is cancelled and waited for) and every
worker thread is waited for.

The longest pause of the GUI thread while this runs (max_pause, seconds) is measured with a
5 ms heartbeat timer; run.bat --timing prints it with "everything ready".
"""

import gc
import threading
import time
import traceback
from typing import Callable, Dict, List, Optional

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import QLabel

POLL_MS = 15            # how often a step waiting for a thread or a condition is checked
MAX_JOBS = 1            # worker threads at once: they are Python work and share one GIL,
                        # so more at once only slows each, and the window, down
HEARTBEAT_MS = 5
SWITCH_INTERVAL_S = 0.001   # while loading: the GUI thread gets the GIL back sooner


class InThread:
    """yield InThread(fn): run fn() in a worker thread; the step resumes with its result."""

    def __init__(self, fn: Callable):
        self.fn = fn


class WaitFor:
    """yield WaitFor(pred): the step resumes once pred() is true (or fails after timeout_s).
    busy=True: what it waits for is a worker thread of its own (the Recording Scheme read),
    which counts against MAX_JOBS meanwhile."""

    def __init__(self, pred: Callable[[], bool], timeout_s: float = 180.0, what: str = "",
                 busy: bool = False):
        self.pred = pred
        self.timeout_s = timeout_s
        self.what = what or "waiting"
        self.busy = busy
        self.since = time.monotonic()


class Step:
    def __init__(self, key: str, label: str, run: Callable, on_stop: Optional[Callable] = None):
        self.key = key
        self.label = label            # plain words, for the status line
        self.run = run                # generator function: () -> generator
        self.on_stop = on_stop        # called by stop() (e.g. cancel a QThread worker)
        self.gen = None
        self.job: Optional[InThread] = None      # waiting to start (no free thread)
        self.thread: Optional[threading.Thread] = None
        self.box: Dict = {}
        self.wait: Optional[WaitFor] = None
        self.resume = ("value", None)
        self.done = False
        self.error: Optional[BaseException] = None
        self.result = None


class BackgroundLoader(QObject):
    """Runs the background steps; see the module's notes."""

    step_finished = Signal(str)           # key (also when the step failed: see error())
    finished = Signal()

    def __init__(self, steps: List[Step], timing=None, status_bar=None, parent=None):
        super().__init__(parent)
        self._steps = {s.key: s for s in steps}
        self._queue: List[Step] = list(steps)
        self._timing = timing
        self._callbacks: Dict[str, List[Callable]] = {}
        self._scheduled = False
        self._in_slice = False
        self._stopped = False
        self._started = False
        self.problems: List[str] = []
        self.max_pause = 0.0              # the longest gap between heartbeats, seconds
        self.slowest_slice = (0.0, "")    # (seconds, step key): the longest single slice
        self.slices: List[tuple] = []     # (step key, seconds) of every slice, for checks
        self._switch = None               # sys.getswitchinterval() before start()
        self._last_beat = None
        self._beat = QTimer(self)
        self._beat.setTimerType(Qt.TimerType.PreciseTimer)
        self._beat.setInterval(HEARTBEAT_MS)
        self._beat.timeout.connect(self._on_beat)
        self.label = None
        if status_bar is not None:
            self.label = QLabel()
            self.label.setObjectName("backgroundLoading")
            status_bar.addPermanentWidget(self.label)
            self.apply_theme()
            self._update_label()

    # ------------------------------------------------------------------ public
    def start(self):
        self._started = True
        import sys
        self._switch = sys.getswitchinterval()
        sys.setswitchinterval(min(self._switch, SWITCH_INTERVAL_S))
        # The records already loaded (hundreds of thousands of objects) are left out of the
        # garbage collector's full passes while this runs: each pass over them paused every
        # thread, the window too, for 0.1-0.2 s. Undone when it ends (_restore_switch);
        # nothing is kept that would otherwise be freed (reference counting still frees).
        gc.freeze()
        self._frozen = True
        self._last_beat = time.perf_counter()
        self._beat.start()
        self._schedule(0)

    @property
    def running(self) -> bool:
        return self._started and not self._stopped and bool(self._queue)

    def is_done(self, key: str) -> bool:
        step = self._steps.get(key)
        return step is None or step.done

    def is_pending(self, key: str) -> bool:
        """The step `key` exists and has not finished (and the loader was not stopped)."""
        step = self._steps.get(key)
        return step is not None and not step.done and not self._stopped

    def error(self, key: str) -> Optional[BaseException]:
        step = self._steps.get(key)
        return None if step is None else step.error

    def result(self, key: str):
        step = self._steps.get(key)
        return None if step is None else step.result

    def pending_labels(self) -> List[str]:
        return [s.label for s in self._queue]

    def prioritise(self, key: str):
        """Step `key` next (Wil clicked its tab, or a link needs it)."""
        step = self._steps.get(key)
        if step is None or step.done or step not in self._queue:
            return
        self._queue.remove(step)
        self._queue.insert(0, step)
        self._schedule(0)

    def when_done(self, key: str, fn: Callable):
        """fn() once step `key` has finished (at once if it has, or if there is no such step)."""
        if not self.is_pending(key):
            fn()
            return
        self._callbacks.setdefault(key, []).append(fn)
        self.prioritise(key)

    def stop(self):
        """Stop cleanly (the window is closing): no more slices, each unfinished step's
        on_stop, every worker thread waited for."""
        if self._stopped:
            return
        self._stopped = True
        self._beat.stop()
        self._restore_switch()
        for step in list(self._queue):
            if step.on_stop is not None:
                try:
                    step.on_stop()
                except Exception as e:
                    print(f"[startup] could not stop {step.label}: {e}")
            if step.gen is not None:
                try:
                    step.gen.close()
                except Exception:
                    pass
        for step in list(self._queue):
            if step.thread is not None:
                step.thread.join(30)
        self._callbacks.clear()
        if self.label is not None:
            self.label.hide()

    def apply_theme(self):
        if self.label is None:
            return
        try:
            from ..themes import theme
            t = theme()
            self.label.setStyleSheet(
                f"color: {t.get('text_secondary')}; font-size: 11px; padding: 0 8px;")
        except Exception:
            pass

    # ------------------------------------------------------------------ running
    def _schedule(self, ms: int):
        if self._stopped or self._scheduled or not self._queue:
            return
        self._scheduled = True
        QTimer.singleShot(ms, self._tick)

    def _tick(self):
        self._scheduled = False
        if self._stopped or not self._queue:
            return
        if self._in_slice:                      # a slice ran the event loop: not again inside
            self._schedule(POLL_MS)
            return
        self._collect_threads()
        for step in list(self._queue):
            if step.thread is not None:
                continue
            if step.job is not None:            # waiting for a free thread
                if self._may_start_thread(step):
                    self._start_thread(step)
                continue
            if step.wait is not None:
                if not self._wait_over(step):
                    continue
            self._advance(step)
            self._schedule(0)
            return
        self._schedule(POLL_MS)                 # every step waits: look again shortly

    def _wait_over(self, step: Step) -> bool:
        w = step.wait
        try:
            ok = bool(w.pred())
        except Exception as e:
            step.wait, step.resume = None, ("error", e)
            return True
        if ok:
            step.wait, step.resume = None, ("value", None)
            return True
        if time.monotonic() - w.since > w.timeout_s:
            step.wait = None
            step.resume = ("error", TimeoutError(f"still {w.what} after {w.timeout_s:.0f} s"))
            return True
        return False

    def _running_threads(self) -> int:
        return sum(1 for s in self._queue
                   if s.thread is not None or (s.wait is not None and s.wait.busy))

    def _may_start_thread(self, step: Step) -> bool:
        """One worker thread at a time -- but the step at the front of the queue (one Wil
        asked for by clicking its tab) need not wait for a busy WaitFor's own worker."""
        if self._running_threads() < MAX_JOBS:
            return True
        return (bool(self._queue) and step is self._queue[0]
                and not any(s.thread is not None for s in self._queue))

    def _restore_switch(self):
        if getattr(self, "_frozen", False):
            self._frozen = False
            gc.unfreeze()
        if self._switch is not None:
            import sys
            sys.setswitchinterval(self._switch)
            self._switch = None

    def _start_thread(self, step: Step):
        job, step.job = step.job, None
        box = step.box = {}

        def work():
            try:
                box["value"] = job.fn()
            except BaseException as e:            # handed back to the GUI thread
                box["error"] = e
        step.thread = threading.Thread(target=work, name=f"observatum-{step.key}", daemon=True)
        step.thread.start()

    def _collect_threads(self):
        for step in self._queue:
            if step.thread is not None and not step.thread.is_alive():
                step.thread = None
                if "error" in step.box:
                    step.resume = ("error", step.box["error"])
                else:
                    step.resume = ("value", step.box.get("value"))
                step.box = {}

    def _advance(self, step: Step):
        """One slice of `step`: run its generator to its next yield."""
        self._in_slice = True
        t0 = time.perf_counter()
        try:
            if step.gen is None:
                step.gen = step.run()
            kind, value = step.resume
            step.resume = ("value", None)
            item = step.gen.throw(value) if kind == "error" else step.gen.send(value)
        except StopIteration as stop:
            self._finish(step, None, stop.value)
        except Exception as e:
            traceback.print_exc()
            self._finish(step, e, None)
        else:
            if isinstance(item, InThread):
                step.job = item
                if self._may_start_thread(step):
                    self._start_thread(step)
            elif isinstance(item, WaitFor):
                item.since = time.monotonic()
                step.wait = item
        finally:
            self._in_slice = False
            dt = time.perf_counter() - t0
            self.slices.append((step.key, dt))
            if dt > self.slowest_slice[0]:
                self.slowest_slice = (dt, step.key)

    def _finish(self, step: Step, error: Optional[BaseException], result):
        step.done, step.error, step.result, step.gen = True, error, result, None
        if step in self._queue:
            self._queue.remove(step)
        if error is not None:
            self.problems.append(f"{step.label}: {error}")
        self._mark(f"loaded: {step.key} (background)" if error is None
                   else f"failed: {step.key} (background): {error}")
        self._update_label()
        # the window first (a failed tab takes the first-opening path), then whatever
        # was waiting for this step (a link into the tab)
        self.step_finished.emit(step.key)
        for fn in self._callbacks.pop(step.key, []):
            try:
                fn()
            except Exception:
                traceback.print_exc()
        if not self._queue and not self._stopped:
            self._beat.stop()
            self._restore_switch()
            self._on_beat()
            self._mark(f"everything ready (longest GUI pause {self.max_pause * 1000:.0f} ms; "
                       f"longest slice {self.slowest_slice[0] * 1000:.0f} ms, "
                       f"{self.slowest_slice[1]})")
            self.finished.emit()

    def _update_label(self):
        if self.label is None:
            return
        names = self.pending_labels()
        if names:
            self.label.setText("Still loading: " + ", ".join(names) + "…")
            self.label.show()
        else:
            self.label.hide()

    def _on_beat(self):
        now = time.perf_counter()
        if self._last_beat is not None:
            self.max_pause = max(self.max_pause, now - self._last_beat - HEARTBEAT_MS / 1000)
        self._last_beat = now

    def _mark(self, label: str):
        if self._timing is not None:
            self._timing.mark(label)

    # ------------------------------------------------------------------ at once
    def finish_now(self, key: str):
        """Run step `key` to its end now, blocking (something needs it this moment)."""
        step = self._steps.get(key)
        if step is None or step.done or self._stopped:
            return
        while not step.done:
            if step.job is not None:
                self._start_thread(step)
            if step.thread is not None:
                step.thread.join()
                self._collect_threads()
            if step.wait is not None:
                while not self._wait_over(step):
                    time.sleep(POLL_MS / 1000)
            self._advance(step)
