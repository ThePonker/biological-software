"""Mapping tab, Round 16 (10 Nov 2026), B2: Generate makes the map in a worker thread
(Observatum/src/views/mapping/map_job.py). The mixin is tested on a small stand-in for the tab (a
widget with the two members it uses), with the fetch replaced by one that waits for the test: no
database, no data copies.
"""
import os
import sys
import threading
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Observatum"))

from src.views.mapping import map_job  # noqa: E402
from src.views.mapping.map_job import MapJobMixin, MapRequest  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


class _Map:
    def __init__(self):
        self.messages = []

    def set_message(self, text):
        self.messages.append(text)


class _Panel:
    def __init__(self):
        from PySide6.QtWidgets import QPushButton
        self.generate_btn = QPushButton("Generate Map")
        self.reversed = False

    def dates_reversed(self):
        return self.reversed


def _host(qapp):
    from PySide6.QtWidgets import QWidget

    class Host(MapJobMixin, QWidget):
        def __init__(self):
            super().__init__()
            self.filter_panel, self.map_widget = _Panel(), _Map()
            self.applied, self.requested = [], []
            self._init_job()

        def _generate_map(self):            # the tab's: here it just asks for what is "now" wanted
            self.requested.append(self.now)
            self._job_request(self.now)

        def _apply_map(self, req, data):
            self.applied.append((req, data, threading.get_ident()))
    return Host()


def _req(tag="a", **kw):
    base = dict(selection=[{"label": tag}], sources=["personal"], filters=None, size=10000,
                tetrads=False, bands=("x",))
    base.update(kw)
    return MapRequest(**base)


class _Fetch:
    """Replaces make_map_data: records the thread, waits until released."""

    def __init__(self):
        self.gate = threading.Event()
        self.threads, self.reqs = [], []

    def __call__(self, req):
        self.threads.append(threading.get_ident())
        self.reqs.append(req)
        assert self.gate.wait(10)
        return map_job.MapData(result=f"result of {req.selection[0]['label']}", tetrads_held=0,
                               squares={}, coarse=0, unparsed=0, timing=(0.0, 0.0))


@pytest.fixture()
def fetch(monkeypatch):
    f = _Fetch()
    monkeypatch.setattr(map_job, "make_map_data", f)
    return f


def _wait(host, seconds=10.0):
    assert host.wait_for_map(seconds)


# ---------------------------------------------------------------- while it runs

def test_the_map_is_made_in_a_worker_thread_and_applied_on_the_gui_thread(qapp, fetch):
    h = _host(qapp)
    h.now = _req()
    h._generate_map()
    assert h.map_running() and h.map_widget.messages == ["Making map…"]
    assert not h.filter_panel.generate_btn.isEnabled()
    assert h.applied == []                                   # nothing yet: the GUI thread was not held
    fetch.gate.set()
    _wait(h)
    (req, data, applied_on), = h.applied
    assert data.result == "result of a" and req == h.now
    assert fetch.threads == [fetch.threads[0]] and fetch.threads[0] != threading.get_ident()
    assert applied_on == threading.get_ident()
    assert h.filter_panel.generate_btn.isEnabled() and not h.map_running()


def test_the_gui_thread_is_free_while_the_worker_waits(qapp, fetch):
    h = _host(qapp)
    h.now = _req()
    t0 = time.perf_counter()
    h._generate_map()
    assert time.perf_counter() - t0 < 0.5                    # returns at once, the fetch is still blocked
    qapp.processEvents()
    assert h.map_running()
    fetch.gate.set()
    _wait(h)


def test_a_second_press_with_the_same_inputs_is_ignored(qapp, fetch):
    h = _host(qapp)
    h.now = _req()
    h._generate_map()
    h._generate_map()
    h._generate_map()
    fetch.gate.set()
    _wait(h)
    assert len(fetch.reqs) == 1 and len(h.applied) == 1


def test_a_changed_selection_throws_the_stale_map_away_and_makes_the_new_one(qapp, fetch):
    h = _host(qapp)
    h.now = _req("old")
    h._generate_map()
    h.now = _req("new")                                      # a taxon added while it ran
    h._generate_map()
    assert len(fetch.reqs) == 1                              # still the one in flight
    fetch.gate.set()
    _wait(h)
    assert [d.result for _r, d, _t in h.applied] == ["result of new"]      # the old one never shown
    assert [r.selection[0]["label"] for r in fetch.reqs] == ["old", "new"]
    assert h.filter_panel.generate_btn.isEnabled()


@pytest.mark.parametrize("change", [dict(sources=["scheme"]), dict(size=1000), dict(tetrads=True),
                                    dict(bands=("y",)), dict(filters="other")])
def test_any_input_that_changes_makes_it_stale(qapp, fetch, change):
    h = _host(qapp)
    h.now = _req()
    h._generate_map()
    h.now = _req(**change)
    h._generate_map()
    fetch.gate.set()
    _wait(h)
    assert len(fetch.reqs) == 2 and len(h.applied) == 1 and h.applied[0][0] == h.now


def test_clearing_the_map_discards_the_result_and_makes_nothing_else(qapp, fetch):
    h = _host(qapp)
    h.now = _req()
    h._generate_map()
    h._job_discard()                                         # the tab's _clear_map does this
    fetch.gate.set()
    _wait(h)
    assert h.applied == [] and len(fetch.reqs) == 1 and h.requested == [h.now]
    assert h.filter_panel.generate_btn.isEnabled()
    h.now = _req("later")                                    # and Generate works again afterwards
    h._generate_map()
    _wait(h)
    assert len(h.applied) == 1


def test_a_change_then_a_clear_makes_nothing(qapp, fetch):
    h = _host(qapp)
    h.now = _req("one")
    h._generate_map()
    h.now = _req("two")
    h._generate_map()                                        # asks for a remake ...
    h._job_discard()                                         # ... then the map is cleared: no remake
    fetch.gate.set()
    _wait(h)
    assert h.applied == [] and len(fetch.reqs) == 1


def test_a_failed_fetch_says_so_and_frees_the_button(qapp, monkeypatch, capsys):
    def boom(req):
        raise RuntimeError("database is locked")
    monkeypatch.setattr(map_job, "make_map_data", boom)
    h = _host(qapp)
    h.now = _req()
    h._generate_map()
    _wait(h)
    assert h.applied == [] and h.map_widget.messages[-1] == "Map not made. database is locked"
    assert h.filter_panel.generate_btn.isEnabled()


def test_the_button_stays_off_when_the_dates_are_reversed(qapp, fetch):
    h = _host(qapp)
    h.now = _req()
    h._generate_map()
    h.filter_panel.reversed = True
    fetch.gate.set()
    _wait(h)
    assert not h.filter_panel.generate_btn.isEnabled()


def test_the_cyclic_collector_is_off_while_the_worker_runs(qapp, fetch):
    import gc
    h = _host(qapp)
    h.now = _req()
    was = gc.isenabled()
    h._generate_map()
    assert not gc.isenabled()
    fetch.gate.set()
    _wait(h)
    assert gc.isenabled() == was


# ---------------------------------------------------------------- the worker's own work

def test_fetch_and_the_squares_run_in_the_worker_with_its_own_connection(monkeypatch):
    """make_map_data in a thread, with the real fetch on a tiny in-memory table: the connection is
    opened by fetch itself in that thread (sqlite3 refuses one made in another), the squares come
    from the fetched record."""
    import sqlite3
    from src.services import map_selection
    from src.services import map_square_service as svc
    opened = []

    class Ctx:
        known_groups = {}

        def species_key(self, tvk, name):
            return tvk

    def connect(path, **kw):
        conn = sqlite3.connect(":memory:")                  # made in the calling thread
        conn.execute("CREATE TABLE observations (id, species_name, species_tvk, common_name, grid_ref,"
                     " date, site_name, recorder, quantity, vc_number, record_type, taxon_group,"
                     " order_name, family, date_type)")
        conn.execute("INSERT INTO observations VALUES (1, 'Rutpela maculata', 'T1', '', 'SP5106',"
                     " '2020-06-01', 'Wood', 'Me', 1, 23, 'Personal', 'Beetles', 'Coleoptera', 'F', 'D')")
        opened.append(threading.get_ident())
        return conn
    monkeypatch.setattr(map_selection, "connect_ro", connect)
    monkeypatch.setattr(map_selection, "get_context", lambda *a, **k: Ctx())
    monkeypatch.setattr(map_selection, "counting_exclusions", lambda db: {})
    monkeypatch.setattr(map_selection, "build_query",
                        lambda table, *a, **k: ("1", []) if table == "observations" and not k.get("part")
                        else ("0", []))
    req = _req(selection=[], size=10000, bands=svc.BAND_PRESETS["default"])
    out = {}
    t = threading.Thread(target=lambda: out.update(d=map_job.make_map_data(req)))
    t.start()
    t.join(10)
    d = out["d"]
    assert opened == [t.ident] and t.ident != threading.get_ident()
    assert [r["grid_ref"] for r in d.result.records] == ["SP5106"]
    assert set(d.squares) == {"SP50"} and d.tetrads_held == 0 and len(d.timing) == 2
