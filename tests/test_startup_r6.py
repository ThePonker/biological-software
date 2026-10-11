"""Startup Round 6 (11 Oct 2026): "window early, rest behind" (Wil's choice).

The window opens once Home, Observation Data, Contributed and Insect Collection are loaded;
the Recording Scheme records, Stats/Reports, Mapping, Settings and the species search then
finish in the background (background_loader.py, background_steps.py,
main_window_background.py). Checked here:

- the loader: steps in order, data work in worker threads, GUI work in slices, one worker
  thread at a time, prioritise / when_done / finish_now, a failed step, stop();
- the window: "Still loading: ..." in the status bar, then gone; a tab clicked before it is
  ready shows "Finishing loading…" with a busy cursor, goes to the front of the queue and
  shows its contents once ready (no loading box);
- links from Stats into the Recording Scheme while its records still load wait for them;
- a Settings change before a tab is ready: no stale data;
- closing the window during the background phase: everything stopped and waited for.

Stand-in tabs (tests/test_loading_r5.py) except where the real Recording Scheme tab is named.
"""
import os
import threading
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from test_loading_r5 import finish_background, make_window  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, monkeypatch):
    yield from make_window(monkeypatch)


def _run(qapp, cond, timeout=10.0):
    end = time.monotonic() + timeout
    while not cond() and time.monotonic() < end:
        qapp.processEvents()
        time.sleep(0.002)
    assert cond(), "timed out"


# ── the loader ──────────────────────────────────────────────────────

def _loader(steps, **k):
    from src.views.background_loader import BackgroundLoader
    return BackgroundLoader(steps, **k)


def test_loader_runs_steps_threads_and_slices(qapp):
    from src.views.background_loader import InThread, Step
    seen = []

    def one():
        seen.append(("one", "gui", threading.current_thread() is threading.main_thread()))
        x = yield InThread(lambda: (threading.current_thread() is threading.main_thread(), 41))
        seen.append(("one", "thread on main?", x[0]))
        yield
        return x[1] + 1

    def two():
        seen.append(("two", "gui"))
        try:
            yield InThread(lambda: 1 / 0)
        except ZeroDivisionError:
            seen.append(("two", "error handed back"))
        return "ok"

    bg = _loader([Step("one", "One", one), Step("two", "Two", two)])
    done = []
    bg.when_done("two", lambda: done.append("two"))
    bg.start()
    _run(qapp, lambda: not bg.running)
    assert ("one", "gui", True) in seen and ("one", "thread on main?", False) in seen
    assert ("two", "error handed back") in seen
    assert bg.result("one") == 42 and bg.result("two") == "ok" and done == ["two"]
    assert bg.problems == [] and bg.error("one") is None
    assert {k for k, _dt in bg.slices} == {"one", "two"}
    assert bg.max_pause >= 0 and bg.slowest_slice[1] in ("one", "two")


def test_loader_one_worker_thread_at_a_time_and_waits(qapp):
    """A step waiting for its own worker (busy WaitFor, the Recording Scheme read) holds the
    one thread slot: the next step's thread work waits; its GUI slices do not."""
    from src.views.background_loader import InThread, Step, WaitFor
    release = threading.Event()
    order = []

    def scheme():
        yield WaitFor(release.is_set, busy=True)
        order.append("scheme ready")

    def stats():
        order.append("stats gui")                 # runs while the scheme still waits
        yield
        yield InThread(lambda: order.append("stats thread"))

    bg = _loader([Step("scheme", "Recording Scheme", scheme), Step("stats", "Stats", stats)])
    bg.start()
    _run(qapp, lambda: "stats gui" in order)
    for _ in range(30):
        qapp.processEvents()
        time.sleep(0.003)
    assert "stats thread" not in order            # the slot is the scheme's
    release.set()
    _run(qapp, lambda: not bg.running)
    assert order == ["stats gui", "scheme ready", "stats thread"]


def test_loader_prioritise_and_finish_now(qapp):
    from src.views.background_loader import InThread, Step
    order = []

    def step(name):
        def run():
            yield InThread(lambda: time.sleep(0.01))
            order.append(name)
        return run

    bg = _loader([Step(k, k, step(k)) for k in ("a", "b", "c", "d")])
    bg.prioritise("c")
    bg.start()
    bg.finish_now("d")                            # needed this moment: done, blocking
    assert bg.is_done("d") and order[0] == "d"
    _run(qapp, lambda: not bg.running)
    assert order == ["d", "c", "a", "b"]


def test_loader_failed_step_and_timeout(qapp):
    from src.views.background_loader import Step, WaitFor

    def broken():
        yield
        raise OSError("disk unavailable")

    def never():
        yield WaitFor(lambda: False, timeout_s=0.05, what="waiting for nothing")

    bg = _loader([Step("a", "A", broken), Step("b", "B", never)])
    bg.start()
    _run(qapp, lambda: not bg.running)
    assert isinstance(bg.error("a"), OSError) and isinstance(bg.error("b"), TimeoutError)
    assert len(bg.problems) == 2 and bg.is_done("a") and bg.is_done("b")


def test_loader_stop_closes_steps_and_waits_for_threads(qapp):
    from src.views.background_loader import InThread, Step
    release = threading.Event()
    threads, stopped, closed = [], [], []

    def slow():
        try:
            yield InThread(lambda: threads.append(threading.current_thread()) or release.wait(5))
            yield
        finally:
            closed.append("slow")

    bg = _loader([Step("slow", "Slow", slow, on_stop=lambda: (stopped.append(1), release.set())),
                  Step("later", "Later", lambda: iter(()))])
    bg.start()
    _run(qapp, lambda: threads)
    import gc
    assert gc.get_freeze_count() > 0                  # the loaded records left out meanwhile
    bg.stop()
    assert gc.get_freeze_count() == 0
    assert stopped == [1] and closed == ["slow"]
    assert not threads[0].is_alive()                  # waited for
    assert not bg.running and not bg.is_pending("later")
    for _ in range(10):
        qapp.processEvents()                          # nothing more runs
    assert not bg.is_done("later")


def test_loader_status_line_and_timing(qapp):
    from PySide6.QtWidgets import QMainWindow
    from src.views.background_loader import Step
    win = QMainWindow()
    win.show()
    marks = []
    timing = type("T", (), {"mark": lambda self, label: marks.append(label)})()

    def quick():
        yield

    bg = _loader([Step("scheme", "Recording Scheme", quick), Step("stats", "Stats/Reports", quick)],
                 timing=timing, status_bar=win.statusBar())
    assert bg.label.text() == "Still loading: Recording Scheme, Stats/Reports…"
    bg.start()
    _run(qapp, lambda: not bg.running)
    assert not bg.label.isVisible()
    import gc
    assert gc.get_freeze_count() == 0                 # the collector back to normal
    assert marks[:2] == ["loaded: scheme (background)", "loaded: stats (background)"]
    assert marks[-1].startswith("everything ready (longest GUI pause ")
    win.close()


# ── the lazy pages ──────────────────────────────────────────────────

def test_deferred_page_waits_and_both_ways_share_one_build(qapp):
    from PySide6.QtWidgets import QLabel
    from src.views.lazy_tab import PENDING_TEXT, LazyTabPage
    made = []

    def parts():
        made.append("start")
        yield
        made.append("middle")
        yield
        return QLabel("real")

    page = LazyTabPage(parts, "Thing")
    page.deferred = True
    page.show()
    assert not page.is_built and page._placeholder.text() == PENDING_TEXT
    steps = page.build_steps()
    next(steps)                                   # the background build has begun
    assert page.ensure_built().text() == "real"   # needed now: the same build, finished
    assert made == ["start", "middle"] and not page.deferred
    with pytest.raises(StopIteration):
        next(steps)                               # the background build sees it done
    page.close()


# ── the window ──────────────────────────────────────────────────────

def test_clicking_a_tab_that_is_not_ready_puts_it_first(window, qapp):
    from PySide6.QtWidgets import QApplication
    from src.views.lazy_tab import PENDING_TEXT
    w, f = window
    f["Scheme"].next_worker_done = False          # the scheme read "still running"
    try:
        w.preload()
        w.show()
        w.connect_tab_signal()
        bg = w.start_background()
        rs = w.recording_scheme_tab
        assert w._scheme_cover.text() == PENDING_TEXT
        assert "Recording Scheme" in bg.label.text()
        w.tabs.setCurrentWidget(w._settings_page)          # Wil clicks Settings at once
        assert bg._queue[0].key == "settings"
        assert QApplication.overrideCursor() is not None     # busy cursor
        assert w._settings_page._placeholder.text() == PENDING_TEXT
        assert w.statusbar.currentMessage() != "Loading..."
        _run(qapp, lambda: bg.is_done("settings"))
        assert w.settings_tab is not None and w._settings_page.page is w.settings_tab
        assert QApplication.overrideCursor() is None         # ready: cursor back
        assert bg.is_pending("scheme")                       # its read still running
        w.tabs.setCurrentWidget(rs)                          # Scheme: covered, busy
        assert QApplication.overrideCursor() is not None
        w.tabs.setCurrentWidget(w.observation_tab)           # away again: cursor back
        assert QApplication.overrideCursor() is None
        w.tabs.setCurrentWidget(rs)
        rs._data_worker.results_ready.set()                  # the read finishes
        _run(qapp, lambda: bg.is_done("scheme"))
        assert QApplication.overrideCursor() is None and w._scheme_cover is None
        assert "init" in rs.calls and w.tabs.indexOf(rs) in w._initialized_tabs
        _run(qapp, lambda: not bg.running)
        assert w._initialized_tabs == set(range(w.tabs.count()))
    finally:
        f["Scheme"].next_worker_done = True
        w._end_busy_cursor()


@pytest.mark.parametrize("link", ["taxon", "species", "vc", "record"])
def test_links_into_scheme_wait_for_its_records(window, qapp, link):
    """Stats > "View N scheme records" etc. at once after the window shows, while the
    Recording Scheme records still load: the tab opens at once ("Finishing loading…") and
    the records are filtered when they are in -- not before (they would be replaced)."""
    w, f = window
    f["Scheme"].next_worker_done = False
    try:
        w.preload()
        w.show()
        w.connect_tab_signal()
        bg = w.start_background()
        bg.prioritise("stats")
        _run(qapp, lambda: bg.is_done("stats"))
        rs = w.recording_scheme_tab
        rs._load_data = lambda filters=None: rs.calls.append(("load", filters))
        rs.show_record_by_id = lambda rid: rs.calls.append(("record", rid))
        st = w.stats_reports_tab
        emit = {"taxon": lambda: st.navigate_to_scheme_taxon.emit("Leiopus linnei/nebulosus"),
                "species": lambda: st.navigate_to_scheme.emit("Rhagium mordax"),
                "vc": lambda: st.navigate_to_scheme_vc.emit("Rhagium mordax", 23),
                "record": lambda: st.navigate_to_scheme_record.emit(17)}[link]
        emit()
        assert w.tabs.currentWidget() is rs                  # at once
        assert not [c for c in rs.calls if isinstance(c, tuple)]   # nothing filtered yet
        rs._data_worker.results_ready.set()
        _run(qapp, lambda: bg.is_done("scheme"))
        acted = [c for c in rs.calls if isinstance(c, tuple)]
        assert acted, rs.calls
        assert rs.calls.index("init") < rs.calls.index(acted[0])
        assert {"taxon": ("species", "Leiopus linnei/nebulosus"),
                "species": ("load", {"species": "Rhagium mordax", "species_exact": True}),
                "vc": ("load", {"species_exact": True, "species": "Rhagium mordax",
                                "vice_county": 23}),
                "record": ("record", 17)}[link] in acted
    finally:
        f["Scheme"].next_worker_done = True
        w._end_busy_cursor()


def test_links_into_observations_work_at_once_after_the_window_shows(window, qapp):
    w, f = window
    w.preload()
    w.connect_tab_signal()
    bg = w.start_background()
    bg.prioritise("stats")
    _run(qapp, lambda: bg.is_done("stats"))
    w.stats_reports_tab.navigate_to_observations.emit("Rutpela maculata")
    assert ("species", "Rutpela maculata") in w.observation_tab.calls
    w.stats_reports_tab.navigate_to_collection.emit("")
    assert w.tabs.currentWidget() is w.insect_collection_tab
    finish_background(w, qapp)


def test_settings_change_before_scheme_ready_waits_for_the_new_read(window, qapp):
    """The records read under the old setting are not shown: the read started again by the
    change (reload_preload) is the one waited for."""
    w, f = window
    f["Scheme"].next_worker_done = False
    try:
        w.preload()
        bg = w.start_background()
        rs = w.recording_scheme_tab
        old = rs._data_worker
        _run(qapp, lambda: rs._data_worker is not None)
        w._on_settings_changed()
        assert "reload" in rs.calls and rs._data_worker is not old
        old.results_ready.set()                              # the old read ends: not used
        for _ in range(30):
            qapp.processEvents()
            time.sleep(0.003)
        assert bg.is_pending("scheme") and "init" not in rs.calls
        rs._data_worker.results_ready.set()
        _run(qapp, lambda: bg.is_done("scheme"))
        assert "init" in rs.calls
    finally:
        f["Scheme"].next_worker_done = True


def test_settings_change_while_stats_figures_are_read(window, qapp, monkeypatch):
    """Figures read ahead for Stats while a setting changes are thrown away (re-read)."""
    import src.services.observation_stats_service as oss
    w, f = window
    reading, release = threading.Event(), threading.Event()

    def slow_figures():
        reading.set()
        release.wait(5)
        return {}
    invalidated = []
    monkeypatch.setattr(oss, "get_observation_stats", slow_figures)
    monkeypatch.setattr(oss.get_observation_stats_service(), "invalidate",
                        lambda: invalidated.append(1))
    w.preload()
    bg = w.start_background()
    bg.prioritise("stats")
    _run(qapp, lambda: reading.is_set())
    before = len(invalidated)
    w._on_counting_changed("observations")            # a species-counting switch
    release.set()
    _run(qapp, lambda: bg.is_done("stats"))
    # once by the change, once more after the read that began before it (stale)
    assert len(invalidated) >= before + 2
    finish_background(w, qapp)


def test_closing_the_window_during_the_background_phase(window, qapp, monkeypatch, tmp_path):
    """Close at once after the window shows: the background stops, its threads are waited
    for, nothing runs afterwards (closeEvent; backups pointed at a temp folder)."""
    import paths
    import shared.backup_service as backup
    from src.views.background_loader import InThread, Step
    monkeypatch.setattr(backup, "backup_working", lambda *a, **k: None)
    monkeypatch.setattr(paths, "OBSERVATUM_DB", tmp_path / "o.db")
    monkeypatch.setattr(paths, "UKSI_DB", tmp_path / "u.db")
    w, f = window
    f["Scheme"].next_worker_done = False
    release = threading.Event()
    threads, later = [], []

    def slow():
        yield InThread(lambda: threads.append(threading.current_thread()) or release.wait(5))
        later.append("ran after close")

    try:
        w.preload()
        w.show()
        from src.views.background_steps import background_steps
        steps = background_steps(w)
        steps.insert(0, Step("slow", "Slow", slow, on_stop=release.set))
        bg = w.start_background(steps=steps)
        _run(qapp, lambda: threads)
        w.close()
        assert "stop" in w.recording_scheme_tab.calls      # the scheme worker stopped
        assert not threads[0].is_alive() and not bg.running
        for _ in range(20):
            qapp.processEvents()
        assert later == []
    finally:
        f["Scheme"].next_worker_done = True


def test_real_scheme_worker_stopped_when_closed_during_background(qapp):
    """The real Recording Scheme tab, its read still running when the window closes: the
    worker is cancelled and waited for (a QThread destroyed while running aborts)."""
    from PySide6.QtCore import QThread
    import src.views.scheme.recording_scheme_tab as rst
    from src.views.background_steps import background_steps

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
    tab.filter_bar.read_choices = lambda db: {}
    worker = Slow()
    tab._data_worker = worker
    worker.start()
    fake = type("W", (), {"recording_scheme_tab": tab, "_main_db_path": None,
                          "_uksi_db_path": None})()
    scheme = [s for s in background_steps(fake) if s.key == "scheme"]
    bg = _loader(scheme)
    bg.start()
    _run(qapp, lambda: scheme[0].wait is not None)        # waiting for the read
    bg.stop()
    assert not worker.isRunning()


def test_splash_steps_are_the_pre_window_steps_only():
    from src.views.background_steps import LABELS
    from src.views.splash_progress import STEPS
    keys = [k for k, _l, _s in STEPS]
    assert keys == ["imports", "window", "services", "home", "observations", "contributed",
                    "collection"]
    assert not set(keys) & set(LABELS)


# ── data read ahead in threads: the same as read on the GUI thread ──

def test_json_in_pieces_same_as_json():
    import json
    import paths
    from shared.maps import vc_map
    from src.views.json_pieces import loads_in_pieces, pieces_for
    for text in ('{}', '[1, 2]', ' 3 ', '{"a": [], "b": {"c": [1]}, "d": [1, {"e": 2}] }',
                 '{"a": 1} x', '{"a": [1,, 2]}', '{"type": "FeatureCollection", "features": '
                 '[{"type": "Feature", "properties": {"VCNUMBER": 23}}, {"x": [1.5, -2e3]}]}',
                 '{"a": 1, "a": 2}'):
        try:
            want = json.loads(text)
        except ValueError as e:
            want = type(e)
        try:
            got = loads_in_pieces(text)
        except ValueError as e:
            got = type(e)
        assert got == want, text
    if paths.VC_GEOJSON.exists():
        text = paths.VC_GEOJSON.read_text(encoding="utf-8")
        assert loads_in_pieces(text) == json.loads(text)
    with pieces_for(vc_map):
        assert vc_map.json is not json
    assert vc_map.json is json                       # put back


def test_scheme_filter_lists_read_in_a_thread_match(qapp):
    """The Recording Scheme filter bar filled from lists read in a worker thread
    (read_choices) is the same as filled on the GUI thread (initialize_with_database)."""
    import paths
    if not os.path.exists(paths.OBSERVATUM_DB):
        pytest.skip("no data/observatum.db")
    from src.models.database import get_database
    from src.views.scheme.scheme_filter_bar import SchemeFilterBar
    db = get_database()
    db.set_main_path(str(paths.OBSERVATUM_DB))
    a, b = SchemeFilterBar(), SchemeFilterBar()
    a.initialize_with_database(db)
    box = {}
    t = threading.Thread(target=lambda: box.setdefault("c", SchemeFilterBar.read_choices(db)))
    t.start()
    t.join()
    b.initialize_with_database(db, choices=box["c"])

    def state(bar):
        combos = [[(c.itemText(i), c.itemData(i)) for i in range(c.count())]
                  for c in (bar.vc_combo, bar.subfamily_combo, bar.status_combo)]
        return (combos, bar._species_completer_model.stringList(),
                bar._location_completer_model.stringList())
    assert state(a) == state(b)
    assert len(state(b)[1]) > 10 and len(state(b)[0][0]) > 2
