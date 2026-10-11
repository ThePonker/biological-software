"""Startup Round 5 (splash bar) and Round 6 (window early, rest behind), 11 Oct 2026.

Round 5 loaded everything under the splash screen (14.7 s on Wil's PC); Wil found that slower
than before Round 4 and chose "window early, rest behind" (Round 6):

- Under the splash (MainWindow.preload): Home, Observation Data, Contributed and Insect
  Collection only. The window then opens.
- After it (MainWindow.start_background): the Recording Scheme records, Stats/Reports,
  Mapping, Settings and the species search, in the background; afterwards every tab is
  loaded and opening it initialises nothing more, shows no loading box and no
  "Loading..." status (tests/test_startup_r6.py: clicking a tab that is not ready, links
  waiting for it, closing meanwhile, the loader itself).
- The splash bar follows the pre-window steps, weighted by their typical duration: its
  values never go backwards, glide after a busy moment, and reach 100 only when done.
- Closing the splash screen while loading stops startup cleanly (the Recording Scheme
  worker cancelled and waited for, no reading thread left running).
"""
import os
import sys
import threading
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import paths  # noqa: E402

from test_startup_r4 import _fakes  # noqa: E402  (the Round 4 stand-in tabs)

needs_data = pytest.mark.skipif(not os.path.exists(paths.OBSERVATUM_DB),
                                reason="no data/observatum.db")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


# ── stand-in tabs that also preload ────────────────────────────────

class _Worker:
    """The Recording Scheme worker as the startup code sees it (finished unless told)."""

    def __init__(self, done=True):
        self.results_ready = threading.Event()
        if done:
            self.results_ready.set()

    def isRunning(self):
        return not self.results_ready.is_set()


def _preload_fakes():
    f = _fakes()

    class Obs(f["Obs"]):
        def prepare(self):
            self.calls.append("prepare")

        def read_all_records(self):
            self.calls.append(("read", threading.current_thread() is threading.main_thread()))
            return ["r1", "r2"]

        def initialize(self, db_path=None, records=None):
            if getattr(self, "_obs_initialized", False):
                return
            self._obs_initialized = True
            self.calls.append(("init", records))
            self._all_observations = list(records or [])

        def _enable_sorting_on_first_view(self):
            self.calls.append("sorting")

    class Collection(f["Collection"]):
        def prepare(self, *a):
            self.calls.append("prepare")

        def query_filters(self, consume=False):
            return {"order": ""}

        def read_specimens(self, filters):
            self.calls.append(("read", filters))
            return ["s1"]

        def initialize(self, db=None, uksi=None, specimens=None):
            if getattr(self, "_ic_initialized", False):
                return
            self._ic_initialized = True
            self.calls.append(("init", specimens))

    class Scheme(f["Scheme"]):
        next_worker_done = True          # tests set False: the read "still running"

        def __init__(self, *a, **k):
            super().__init__()
            self._data_worker = None
            self._preload_records = None

        def start_preload(self, path):
            self.calls.append("preload")
            self._data_worker = _Worker(type(self).next_worker_done)

        def reload_preload(self):        # a setting changed before the tab was ready
            if self._initialized or self._data_worker is None:
                return
            self.calls.append("reload")
            self._data_worker = _Worker(type(self).next_worker_done)

        def initialize(self, *a, **k):
            if self._initialized:
                return
            self._initialized = True
            self.calls.append("init")

        def stop_loading(self, wait_ms=5000):
            self.calls.append("stop")

    f.update(Obs=Obs, Collection=Collection, Scheme=Scheme)
    return f


def _no_species_index():
    return
    yield                                # (never reached: makes this a generator)


@pytest.fixture
def window(qapp, monkeypatch):
    yield from make_window(monkeypatch)


def make_window(monkeypatch):
    """A MainWindow with stand-in tabs (also used by tests/test_startup_r6.py)."""
    import src.views.main_window as mw
    import src.views.stats as stats_pkg
    import src.views.mapping as mapping_pkg
    import src.views.settings as settings_pkg
    import src.views.background_steps as bs
    import src.services.observation_stats_service as oss
    import DataEntry.embed as de_embed

    f = _preload_fakes()
    monkeypatch.setattr(mw, "HomeTab", f["Home"])
    monkeypatch.setattr(mw, "ObservationTab", f["Obs"])
    monkeypatch.setattr(mw, "ContributedTab", f["Contributed"])
    monkeypatch.setattr(mw, "RecordingSchemeTab", f["Scheme"])
    monkeypatch.setattr(mw, "InsectCollectionTab", f["Collection"])
    monkeypatch.setattr(stats_pkg, "StatsReportsTab", f["Stats"])
    monkeypatch.setattr(mapping_pkg, "MappingTab", f["Mapping"])
    monkeypatch.setattr(settings_pkg, "SettingsTab", f["Settings"])
    monkeypatch.setattr(oss, "get_observation_stats", lambda: {})

    def no_de(**k):
        raise RuntimeError("not in this test")
    monkeypatch.setattr(de_embed, "make_data_entry_tab", no_de)
    monkeypatch.setattr(mw.MainWindow, "_initialize_services", lambda self: None)
    monkeypatch.setattr(mw, "get_database", lambda: None)
    import src.views.main_window_background as mwb
    monkeypatch.setattr(mwb, "get_database", lambda: None)
    # the real map outlines and species index are not needed with stand-in tabs
    monkeypatch.setattr(bs, "_read_map_data", lambda: {})
    monkeypatch.setattr(bs, "species_search_step", _no_species_index)

    w = mw.MainWindow()
    yield w, f
    w.stop_background()
    w.deleteLater()


def finish_background(w, qapp, timeout=10.0):
    """Start the background phase (if not started) and let it run to the end."""
    bg = w.start_background()
    end = time.monotonic() + timeout
    while bg.running and time.monotonic() < end:
        qapp.processEvents()
        time.sleep(0.002)
    assert not bg.running, f"still loading: {bg.pending_labels()}"
    return bg


# ── before the window: the first four tabs only ─────────────────────

def test_preload_loads_the_first_tabs_only(window):
    w, f = window
    result = w.preload()
    assert not result.cancelled and result.problems == []
    assert result.done == ["home", "observations", "contributed", "collection"]
    obs, ic, rs = w.observation_tab, w.insect_collection_tab, w.recording_scheme_tab
    # records read in a background thread, then shown without a second read
    loading = [c for c in obs.calls if c != "theme"]
    assert loading[:3] == ["prepare", ("read", False), ("init", ["r1", "r2"])]
    assert ("read", {"order": ""}) in ic.calls and ("init", ["s1"]) in ic.calls
    assert "init" in w.home_tab.calls and "init" in w.contributed_tab.calls
    # the rest waits for the background phase, after the window has opened
    assert "preload" not in rs.calls and "init" not in rs.calls
    assert w.stats_reports_tab is None and w.mapping_tab is None and w.settings_tab is None
    ready = {w.tabs.indexOf(t) for t in (w.home_tab, obs, w.contributed_tab, ic)}
    assert w._initialized_tabs == ready


def test_background_then_loads_every_other_tab(window, qapp):
    w, f = window
    w.preload()
    w.connect_tab_signal()
    finish_background(w, qapp)
    rs = w.recording_scheme_tab
    assert [c for c in rs.calls if c != "theme"] == ["preload", "init"]
    assert w.stats_reports_tab is not None and "init" in w.stats_reports_tab.calls
    assert w.mapping_tab is not None and w.settings_tab is not None
    assert w._initialized_tabs == set(range(w.tabs.count()))
    assert not w._bg.label.isVisible()                    # "Still loading" gone


def test_opening_tabs_after_startup_loads_nothing_more(window, qapp):
    w, f = window
    w.preload()
    w.connect_tab_signal()
    finish_background(w, qapp)
    before = {name: list(getattr(w, name).calls) for name in
              ("observation_tab", "insect_collection_tab", "recording_scheme_tab",
               "contributed_tab", "mapping_tab", "settings_tab")}
    for i in range(w.tabs.count()):
        w.tabs.setCurrentIndex(i)
        qapp.processEvents()
        assert w.statusbar.currentMessage() != "Loading..."
    for name, calls in before.items():
        assert getattr(w, name).calls == calls, name          # not initialised again
    # Stats/Reports is refreshed on a visit, as before (its figures may have changed)
    assert "refresh" in w.stats_reports_tab.calls
    assert f["Stats"].built == 1 and f["Mapping"].built == 1


def test_stats_navigation_works_at_once(window, qapp):
    w, f = window
    w.preload()
    w.connect_tab_signal()
    finish_background(w, qapp)
    w.tabs.setCurrentWidget(w._stats_page)
    obs = w.observation_tab
    n_init = sum(1 for c in obs.calls if isinstance(c, tuple) and c[0] == "init")
    w.stats_reports_tab.navigate_to_observations.emit("Rutpela maculata")
    assert w.tabs.currentWidget() is obs and ("species", "Rutpela maculata") in obs.calls
    assert sum(1 for c in obs.calls if isinstance(c, tuple) and c[0] == "init") == n_init
    rs = w.recording_scheme_tab
    w.stats_reports_tab.navigate_to_scheme_taxon.emit("Leiopus linnei/nebulosus")
    assert w.tabs.currentWidget() is rs and ("species", "Leiopus linnei/nebulosus") in rs.calls
    w.stats_reports_tab.navigate_to_collection.emit("")
    assert w.tabs.currentWidget() is w.insect_collection_tab


def test_settings_change_after_startup_refreshes_loaded_tabs(window, qapp):
    """No stale data: with every tab loaded, a Settings change refreshes them."""
    w, f = window
    w.preload()
    finish_background(w, qapp)
    w._on_settings_changed()
    assert "filters" in w.observation_tab.calls
    assert "refresh" in w.recording_scheme_tab.calls
    assert "refresh" in w.stats_reports_tab.calls


def test_failed_step_is_reported_and_tab_loads_on_opening(window, qapp):
    w, f = window

    def broken(self):
        raise OSError("disk unavailable")
    f["Obs"].read_all_records = broken
    result = w.preload()
    from src.views.startup_preload import problems_message
    assert any("Observation Data" in p and "disk unavailable" in p for p in result.problems)
    assert "loaded again when their tab is opened" in problems_message(result)
    i = w.tabs.indexOf(w.observation_tab)
    assert i not in w._initialized_tabs
    assert "init" in w.insect_collection_tab.calls[-1]   # the other steps still ran
    w.connect_tab_signal()
    w.tabs.setCurrentIndex(i)                     # the Round 4 path: loads on opening
    assert any(isinstance(c, tuple) and c[0] == "init" for c in w.observation_tab.calls)


def test_failed_background_step_falls_back_to_loading_on_opening(window, qapp):
    w, f = window
    real_init = f["Mapping"].__init__

    def broken(self, *a, **k):
        raise OSError("outline file unreadable")
    f["Mapping"].__init__ = broken
    w.preload()
    w.connect_tab_signal()
    try:
        bg = finish_background(w, qapp)
    finally:
        f["Mapping"].__init__ = real_init
    assert isinstance(bg.error("mapping"), OSError)
    assert "Mapping could not be loaded" in w.statusbar.currentMessage()
    assert w.settings_tab is not None                  # the other steps still ran
    i = w.tabs.indexOf(w._mapping_page)
    assert i not in w._initialized_tabs and not w._mapping_page.deferred
    w.tabs.setCurrentIndex(i)                          # built on opening (Round 4)
    assert w.mapping_tab is not None and w._mapping_page.page is w.mapping_tab


# ── closing the splash screen while loading ─────────────────────────

def test_closing_splash_during_preload_stops_cleanly(window, qapp):
    from PySide6.QtCore import QTimer
    from src.views.splash_progress import ProgressPlan
    from src.views.splash_screen import ObservatumSplashScreen
    w, f = window
    splash = ObservatumSplashScreen()
    splash.show()
    splash.start_plan(ProgressPlan())
    w._splash = splash
    release = threading.Event()
    reading = []

    def slow_read(self):
        reading.append(threading.current_thread())
        release.wait(10)
        return []
    f["Obs"].read_all_records = slow_read
    QTimer.singleShot(100, splash.close)               # Wil closes the splash
    QTimer.singleShot(300, release.set)
    result = w.preload()
    assert result.cancelled
    assert "stop" in w.recording_scheme_tab.calls      # any scheme worker stopped first
    assert reading and not reading[0].is_alive()       # no reading thread left running
    assert "init" not in w.insect_collection_tab.calls  # nothing after the close ran
    assert w._bg is None                               # the background phase never began
    splash.deleteLater()


def test_real_scheme_worker_stopped_when_startup_is_cancelled(qapp):
    """With the real Recording Scheme tab: a load running when startup stops is cancelled
    and waited for (a QThread destroyed while running aborts the process)."""
    from PySide6.QtCore import QThread
    import src.views.scheme.recording_scheme_tab as rst
    from src.views.startup_preload import StartupPreloader

    class Slow(QThread):
        def __init__(self):
            super().__init__()
            self.stop = threading.Event()
            self.results_ready = threading.Event()

        def cancel(self):
            self.stop.set()

        def run(self):
            self.stop.wait(30)

    tab = rst.RecordingSchemeTab()
    worker = Slow()
    tab._data_worker = worker
    worker.start()
    fake_window = type("W", (), {"recording_scheme_tab": tab})()
    StartupPreloader(fake_window).stop()
    assert not worker.isRunning()


# ── the splash bar ──────────────────────────────────────────────────

class _Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def _run_plan(steps, actual, dt=0.016):
    """Simulate a startup: each step takes actual[key] seconds; tick every dt."""
    from src.views.splash_progress import ProgressPlan
    clock = _Clock()
    plan = ProgressPlan(steps, clock=clock)
    values = []
    for key, _label, _s in steps:
        plan.begin(key)
        end = clock.t + actual[key]
        while clock.t < end:
            clock.t += dt
            values.append((clock.t, plan.tick()))
    return plan, values


def test_bar_is_monotonic_even_and_100_only_when_done():
    steps = [("a", "A", 1.0), ("b", "B", 3.0), ("c", "C", 1.0)]
    plan, values = _run_plan(steps, {"a": 1.0, "b": 3.0, "c": 1.0})
    vals = [v for _t, v in values]
    assert all(b >= a for a, b in zip(vals, vals[1:]))
    assert max(vals) < 100
    # even in time: about a fifth of the way after a fifth of the time, half at half
    at = {round(t, 1): v for t, v in values}
    assert 12 < at[1.0] < 24 and 40 < at[2.5] < 58
    # no jumps: never more than a couple of per cent between two ticks
    assert max(b - a for a, b in zip(vals, vals[1:])) < 2.5
    plan.finish()
    assert plan.tick() == 100.0
    assert set(plan.measured) == {"a", "b", "c"}


def test_bar_creeps_when_a_step_runs_long_and_glides_after_a_pause():
    steps = [("a", "A", 1.0), ("b", "B", 1.0)]
    # step a takes four times as long as expected: the bar stays below b's start
    plan, values = _run_plan(steps[:1], {"a": 4.0})
    assert values[-1][1] < plan.span["a"][1]
    assert values[-1][1] > values[len(values) // 2][1]           # still creeping
    # a busy GUI moment (no ticks for 0.8 s), then the bar glides rather than jumps
    from src.views.splash_progress import ProgressPlan
    clock = _Clock()
    plan = ProgressPlan(steps, clock=clock)
    plan.begin("a")
    plan.tick()
    clock.t = 0.8
    first = plan.tick()
    assert first < plan.target() * 0.5
    for _ in range(60):
        clock.t += 0.016
        plan.tick()
    assert plan.tick() > plan.target() - 3


def test_bar_uses_this_computers_durations():
    from src.views.splash_progress import ProgressPlan, STEPS
    # "scheme": kept by a Round 5 startup, no longer a splash step (ignored)
    plan = ProgressPlan(seconds={"contributed": 6.0, "nonsense": 5, "home": -1,
                                 "scheme": 3.0})
    default = ProgressPlan()
    width = lambda p, k: p.span[k][1] - p.span[k][0]   # noqa: E731
    assert width(plan, "contributed") > 3 * width(default, "contributed")
    assert width(plan, "home") < width(default, "home")       # bad value ignored, others shrink
    assert plan.keys == [k for k, _l, _s in STEPS]
    assert "scheme" not in plan.keys and "stats" not in plan.keys   # after the window (R6)


def test_step_keys_match_the_preloader():
    from src.views.splash_progress import STEPS
    from src.views.startup_preload import StartupPreloader
    keys = [k for k, _l, _s in STEPS]
    run = [k for k, _fn in StartupPreloader(None).steps()]
    assert keys == ["imports", "window", "services"] + run


def test_splash_follows_plan_and_fills_only_at_finish(qapp):
    from src.views.splash_progress import ProgressPlan
    from src.views.splash_screen import ObservatumSplashScreen
    splash = ObservatumSplashScreen()
    splash.show()
    splash.start_plan(ProgressPlan())
    seen = []
    for key in ("imports", "window", "home", "observations"):
        splash.begin_step(key)
        end = time.perf_counter() + 0.12
        while time.perf_counter() < end:
            qapp.processEvents()
            seen.append(splash.progress_value())
    assert "observation records" in splash._status.text()
    assert all(b >= a for a, b in zip(seen, seen[1:])) and 0 < seen[-1] < 100
    splash.set_progress(5, "older call")                   # never pulls the bar back
    assert splash.progress_value() >= seen[-1]
    splash.finish_progress()
    assert splash.progress_value() == 100.0 and splash._progress.value() == 1000
    assert not splash.cancel_requested
    splash.close()                                          # closed when done: no cancel
    assert not splash.cancel_requested


# ── the real tabs, on the data copy ─────────────────────────────────

_REAL_STARTUP = r"""
import json, sqlite3, sys, time
import paths
from PySide6.QtWidgets import QApplication, QDialog
app = QApplication([])
import src.views.observations.observation_tab as ot
boxes = []
real_dialog = ot.LoadingDialog
def counting_dialog(*a, **k):
    boxes.append(1)
    return real_dialog(*a, **k)
ot.LoadingDialog = counting_dialog
from src.startup_timing import timer
from src.views.main_window import MainWindow
from src.views.splash_progress import ProgressPlan
from src.views.splash_screen import ObservatumSplashScreen
timing = timer()
splash = ObservatumSplashScreen()
splash.show()
plan = ProgressPlan()
splash.start_plan(plan)
seen = []
splash._anim.timeout.connect(lambda: seen.append(splash.progress_value()))
w = MainWindow(main_db_path=str(paths.OBSERVATUM_DB), uksi_db_path=str(paths.UKSI_DB), splash=splash)
result = w.preload(timing)
before_finish = splash.progress_value()
splash.finish_progress()
splash.close()
w.resize(1400, 900)
w.show()
w.connect_tab_signal()
timing.mark("window shown")
at_show = dict(stats=w.stats_reports_tab is None, scheme=not w.recording_scheme_tab._initialized,
               ready=sorted(w._initialized_tabs))
bg = w.start_background(timing)
label = bg.label.text()
end = time.monotonic() + 240
while bg.running and time.monotonic() < end:
    app.processEvents()
    time.sleep(0.002)
status, dialogs = [], []
for i in range(w.tabs.count()):
    w.tabs.setCurrentIndex(i)
    app.processEvents()
    status.append(w.statusbar.currentMessage())
    dialogs += [d.windowTitle() for d in app.topLevelWidgets() if isinstance(d, QDialog) and d.isVisible()]
con = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
marks = [m for m, _t in timing.marks]
out = dict(
    cancelled=result.cancelled, problems=result.problems, bg_problems=bg.problems,
    running=bg.running, boxes=len(boxes), status=status, label=label,
    label_after=bg.label.isVisible(), dialogs=dialogs, before_finish=before_finish,
    seen=seen, ticks=len(seen), at_show=at_show, marks=marks,
    max_pause=bg.max_pause, slowest=bg.slowest_slice,
    obs=w.observation_tab.table_model.rowCount(),
    n_obs=con.execute("SELECT COUNT(*) FROM observations").fetchone()[0],
    ic=w.insect_collection_tab.table_model.rowCount(),
    n_spec=con.execute("SELECT COUNT(*) FROM specimens").fetchone()[0],
    rs=w.recording_scheme_tab.table_model.rowCount(),
    built=[w.stats_reports_tab is not None, w.mapping_tab is not None, w.settings_tab is not None],
    ready=sorted(w._initialized_tabs), count=w.tabs.count(), measured=sorted(plan.measured))
w.stop_background()
print("RESULT " + json.dumps(out), flush=True)
"""


@needs_data
def test_real_startup_loads_every_tab_without_loading_boxes():
    """The real tabs on the data copy, in a fresh interpreter (as at startup; it also keeps
    the whole loaded window's memory out of the test session): the first four tabs before
    the window, the rest in the background after it, then every tab loaded, no box."""
    import json
    import subprocess
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([root, os.path.join(root, "Observatum")]),
               QT_QPA_PLATFORM="offscreen", PYTHONIOENCODING="utf-8")
    out = subprocess.run([sys.executable, "-c", _REAL_STARTUP], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", env=env, cwd=root, timeout=300)
    lines = [ln for ln in out.stdout.splitlines() if ln.startswith("RESULT ")]
    if not lines and sys.platform == "win32" and "Cannot find font directory" in out.stderr:
        # Qt's offscreen platform on Windows has no fonts: the window crashes there
        # (exit 3221225477, an access violation) before anything this test checks
        pytest.skip("offscreen Qt on Windows has no fonts (\"Cannot find font directory\"); "
                    f"the real-startup check runs on Linux (exit {out.returncode})")
    assert out.returncode == 0 and lines, out.stderr[-3000:]
    r = json.loads(lines[-1][len("RESULT "):])
    assert not r["cancelled"] and r["problems"] == [] and r["bg_problems"] == []
    # when the window opened: Stats and the Recording Scheme still to come
    assert r["at_show"]["stats"] and r["at_show"]["scheme"]
    assert len(r["at_show"]["ready"]) < r["count"]
    assert r["label"].startswith("Still loading: Recording Scheme")
    assert not r["running"] and not r["label_after"]
    assert r["boxes"] == 0 and r["dialogs"] == []                 # no loading box
    assert "Loading..." not in r["status"]
    assert r["obs"] == r["n_obs"] and r["ic"] == r["n_spec"] and r["rs"] > 0
    assert r["built"] == [True, True, True]
    assert r["ready"] == list(range(r["count"]))                 # every tab loaded
    marks = r["marks"]
    shown = marks.index("window shown")
    for key in ("scheme", "stats", "mapping", "settings", "species_search"):
        assert marks.index(f"loaded: {key} (background)") > shown, key
    assert marks[-1].startswith("everything ready (longest GUI pause")
    # the window kept responding: no slice of GUI work near a freeze (the target is
    # < 150 ms on Wil's PC; this machine and a busy test run vary, so a wide margin)
    assert r["slowest"][0] < 0.6, r["slowest"]
    print(f"longest GUI pause {r['max_pause'] * 1000:.0f} ms, longest slice "
          f"{r['slowest'][0] * 1000:.0f} ms ({r['slowest'][1]})")
    seen = r["seen"]
    assert r["ticks"] > 20                                       # the bar kept moving
    assert all(b >= a for a, b in zip(seen, seen[1:])) and max(seen) < 100
    assert r["before_finish"] < 100
    # (the bar's steps: "imports" and "window" are begun by main.py, not here)
    assert set(r["measured"]) == {"services", "home", "observations", "contributed",
                                  "collection"}
