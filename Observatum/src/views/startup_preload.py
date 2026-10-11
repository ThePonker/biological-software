"""Load the first tabs under the splash screen, before the main window is shown.

Round 5 (11 Oct 2026) loaded everything here (about 14.7 s on Wil's PC); Wil found that
slower than before. Round 6 ("window early, rest behind", Wil's choice): only Home,
Observation Data, Contributed and Insect Collection are loaded here, so the window opens at
about 7-8 s; the Recording Scheme records, Stats/Reports, Mapping, Settings and the species
search then finish in the background (MainWindow.start_background, background_loader.py).

The splash keeps moving meanwhile: record reads run in background threads (they touch no
widget; every database query opens its own connection) while this thread pumps events, so
the splash's timer animates the bar (splash_progress.ProgressPlan). Work that must be on the
GUI thread (building widgets, filling tables) runs between pumps.

A step that fails is reported after the window opens and its tab falls back to loading on
first opening, as in Round 4. Closing the splash screen stops startup cleanly: any reading
thread is waited for (and a Recording Scheme load, should one be running, is cancelled and
waited for: a QThread destroyed while running aborts the process).

    result = StartupPreloader(window, splash, timing).run()
    if result.cancelled: ...           # do not show the window
"""

import threading
import traceback
from typing import Callable, List, Optional

from PySide6.QtWidgets import QApplication

_WAIT_S = 0.015          # pump interval while a thread works (the splash timer is 16 ms)


class Cancelled(Exception):
    """The splash screen was closed: stop loading."""


class PreloadResult:
    def __init__(self):
        self.cancelled = False
        self.problems: List[str] = []       # plain words, shown after the window opens
        self.done: List[str] = []           # the steps that finished


class StartupPreloader:
    """Runs the startup steps (see splash_progress.STEPS) for a built MainWindow."""

    def __init__(self, window, splash=None, timing=None):
        self.w = window
        self.splash = splash
        self.timing = timing
        self.result = PreloadResult()
        self._threads: List[threading.Thread] = []

    # ------------------------------------------------------------------ running
    def steps(self):
        """(key, function) in the order they run; keys match splash_progress.STEPS."""
        return [
            ("home", self._home),
            ("observations", self._observations),
            ("contributed", self._contributed),
            ("collection", self._collection),
        ]

    def run(self) -> PreloadResult:
        try:
            for key, fn in self.steps():
                self._check_cancel()
                if self.splash is not None:
                    self.splash.begin_step(key)
                try:
                    fn()
                    self.result.done.append(key)
                except Cancelled:
                    raise
                except Exception as e:
                    traceback.print_exc()
                    self.result.problems.append(f"{_PLAIN.get(key, key)}: {e}")
                self._mark(f"loaded: {key}")
            self._check_cancel()
        except Cancelled:
            self.result.cancelled = True
            self.stop()
        return self.result

    def stop(self):
        """Stop the Recording Scheme worker and wait for any reading thread (closing the
        splash screen while loading)."""
        try:
            self.w.recording_scheme_tab.stop_loading()
        except Exception as e:
            print(f"[startup] could not stop the Recording Scheme load: {e}")
        for t in self._threads:
            t.join(30)

    # ------------------------------------------------------------------ helpers
    def _cancelled(self) -> bool:
        return bool(getattr(self.splash, "cancel_requested", False))

    def _check_cancel(self):
        if self._cancelled():
            raise Cancelled()

    def _pump(self):
        if self.splash is not None:
            self.splash.pump()
        else:
            QApplication.processEvents()

    def _mark(self, label: str):
        if self.timing is not None:
            self.timing.mark(label)

    def in_thread(self, fn: Callable):
        """fn() in a background thread while the splash keeps animating; its result (or
        its exception, raised here). A closed splash stops the wait (Cancelled) once the
        thread has ended."""
        box = {}

        def work():
            try:
                box["value"] = fn()
            except BaseException as e:            # handed to the GUI thread
                box["error"] = e

        t = threading.Thread(target=work, name="observatum-startup", daemon=True)
        self._threads.append(t)
        t.start()
        while t.is_alive():
            self._pump()
            t.join(_WAIT_S)
        self._threads.remove(t)
        self._check_cancel()
        if "error" in box:
            raise box["error"]
        return box.get("value")

    def _paths(self):
        return self.w._main_db_path, self.w._uksi_db_path

    # ------------------------------------------------------------------ the steps
    def _home(self):
        self.w.home_tab.initialize()
        self.w.mark_tab_ready(self.w.home_tab)
        de = getattr(self.w, "data_entry_tab", None)
        if de is not None:                      # builds itself; nothing to load on opening
            self.w.mark_tab_ready(de)

    def _observations(self):
        obs = self.w.observation_tab
        obs.prepare()
        self._pump()
        records = self.in_thread(obs.read_all_records)
        obs.initialize(records=records)
        if hasattr(obs, "_enable_sorting_on_first_view"):
            obs._enable_sorting_on_first_view()
        self.w.mark_tab_ready(obs)

    def _contributed(self):
        self.w.contributed_tab.initialize()
        self.w.mark_tab_ready(self.w.contributed_tab)

    def _collection(self):
        ic = self.w.insect_collection_tab
        db, uksi = self._paths()
        ic.prepare(db, uksi)
        self._pump()
        filters = ic.query_filters()
        specimens = self.in_thread(lambda: ic.read_specimens(filters))
        ic.initialize(db, uksi, specimens=specimens)
        if hasattr(ic, "_enable_sorting_on_first_view"):
            ic._enable_sorting_on_first_view()
        self.w.mark_tab_ready(ic)


_PLAIN = {
    "home": "Home page",
    "observations": "Observation Data records",
    "contributed": "Contributed records",
    "collection": "Insect Collection specimens",
}


def problems_message(result: Optional[PreloadResult]) -> str:
    """What to tell Wil when part of startup failed ('' when nothing did)."""
    if result is None or not result.problems:
        return ""
    return ("Some parts of Observatum could not be loaded at startup. They will be loaded "
            "again when their tab is opened.\n\n" + "\n".join(result.problems))
