"""Round 8 (12 Oct 2026), Observatum.

O1 -- the pause of the window while the rest loads behind it (Wil's PC: 1,231 ms):
- run.bat --timing says where each pause over 100 ms happened (pause_watch.py), and costs
  nothing without --timing;
- no garbage collection while loading; what was loaded stays frozen afterwards;
- table headers that fit their contents are sized in a slice (settle_headers), not later from
  the event loop (where each cell waited for the GIL behind a loading thread);
- the outline file's points parsed in small pieces (json_pieces), same result as json.loads;
- Settings built a panel at a time; the map's label positions worked out in a thread.

O2 -- "Square opacity" on the Mapping tab: 0-100 %, default 100 % (as before), remembered,
applied to the map at once, the atlas page follows it, draw order unchanged.

Offscreen; no font-metric assumptions.
"""
import gc
import json
import os
import threading
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def settings_sandbox(qapp):
    from PySide6.QtCore import QCoreApplication, QSettings
    org = QCoreApplication.organizationName()
    QCoreApplication.setOrganizationName("ObservatumTests_obs_r8")
    QSettings().clear()
    yield
    QSettings().clear()
    QCoreApplication.setOrganizationName(org)


def _run(qapp, cond, timeout=10.0):
    end = time.monotonic() + timeout
    while not cond() and time.monotonic() < end:
        qapp.processEvents()
        time.sleep(0.002)
    assert cond(), "timed out"


class _Timing:
    def __init__(self, on):
        self.on = on
        self.marks = []

    def mark(self, label):
        self.marks.append(label)


# ── O1: where the pauses were ───────────────────────────────────────

def _hold_the_window():
    """A slice that keeps the GUI thread busy for 0.25 s (in Python, so it is sampled)."""
    end = time.perf_counter() + 0.25
    while time.perf_counter() < end:
        pass


def test_timing_lists_pauses_with_their_step_and_place(qapp):
    from src.views.background_loader import BackgroundLoader, Step

    def quick():
        yield

    def slow():
        yield
        _hold_the_window()
        yield

    timing = _Timing(True)
    bg = BackgroundLoader([Step("quick", "Quick", quick), Step("slow", "Slow", slow)],
                          timing=timing)
    bg.start()
    assert bg._watch is not None
    _run(qapp, lambda: not bg.running)
    assert not any(t.name == "observatum-pause-watch" for t in threading.enumerate())
    marks = timing.marks
    i = next(i for i, m in enumerate(marks) if m.startswith("everything ready"))
    report = marks[i + 1:]
    assert report[0].startswith("pauses over 100 ms: ")
    assert "garbage collections over 20 ms" in report[0]
    assert any("in slice slow" in line for line in report), report
    assert any("_hold_the_window" in line for line in report), report
    assert bg.pauses and max(p.seconds for p in bg.pauses) >= 0.2


def test_no_watchdog_without_timing(qapp):
    from src.views.background_loader import BackgroundLoader, Step

    def quick():
        yield

    for timing in (None, _Timing(False)):
        bg = BackgroundLoader([Step("a", "A", quick)], timing=timing)
        bg.start()
        assert bg._watch is None
        assert not any(t.name == "observatum-pause-watch" for t in threading.enumerate())
        _run(qapp, lambda: not bg.running)
        if timing is not None:
            assert not any(m.startswith("pauses over") for m in timing.marks)


def test_pause_report_places_gaps_and_collections():
    """Between slices / in a slice, and a garbage collection that ran in the pause."""
    from src.views.pause_watch import Pause, PauseWatch
    w = PauseWatch(clock_start=0.0)
    w.slice_done("scheme", 1.0, 1.05)
    w.slice_done("stats", 2.0, 2.02)
    w.collections.append((1.3, 1.6, 2, "observatum-mapping"))
    w.pauses = [Pause(1.2, 0.5), Pause(1.99, 0.2)]
    lines = w.report()
    assert lines[0].startswith("pauses over 100 ms: 2")
    assert "between slices (after scheme, before stats)" in lines[1]
    assert "garbage collection 300 ms (generation 2) in thread observatum-mapping" in lines[2]
    assert "in slice stats" in lines[3]
    assert PauseWatch().report()[0] == "pauses over 100 ms: none"


# ── O1: garbage collection ──────────────────────────────────────────

def test_no_collection_while_loading_then_loaded_objects_stay_frozen(qapp):
    from src.views.background_loader import BackgroundLoader, InThread, Step
    seen = {}

    def step():
        seen["during"] = gc.isenabled()
        yield InThread(lambda: [[i] for i in range(50000)])   # objects made in a thread
        seen["after_thread"] = gc.isenabled()

    gc.enable()
    bg = BackgroundLoader([Step("a", "A", step)])
    bg.start()
    _run(qapp, lambda: not bg.running)
    assert seen == {"during": False, "after_thread": False}
    assert gc.isenabled()
    assert gc.get_freeze_count() > 0          # the loaded objects out of later passes


def test_stop_hands_everything_back_to_the_collector(qapp):
    from src.views.background_loader import BackgroundLoader, InThread, Step
    release = threading.Event()

    def step():
        yield InThread(lambda: release.wait(5))

    bg = BackgroundLoader([Step("a", "A", step, on_stop=release.set)])
    bg.start()
    _run(qapp, lambda: bg._steps["a"].thread is not None)
    assert not gc.isenabled()
    bg.stop()
    assert gc.isenabled() and gc.get_freeze_count() == 0


def test_switch_interval_under_a_millisecond():
    """On Windows Python waits whole milliseconds for the GIL: under 1 ms waits 0 ms there."""
    from src.views.background_loader import SWITCH_INTERVAL_S
    assert SWITCH_INTERVAL_S < 0.001


# ── O1: table headers sized in the slice ────────────────────────────

def _table(rows=300):
    from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

    class Table(QTableWidget):            # a Python subclass, as the dashboards' tables are
        pass
    t = Table(rows, 3)
    h = t.horizontalHeader()
    h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    h.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
    h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
    for r in range(rows):
        for c in range(3):
            t.setItem(r, c, QTableWidgetItem(f"row {r} column {c}" + "x" * (r % 7)))
    return t


def test_settle_headers_sizes_like_the_event_loop_would(qapp):
    from PySide6.QtWidgets import QHeaderView, QTableWidget, QWidget, QVBoxLayout
    from src.views.background_steps import settle_headers
    page = QWidget()
    lay = QVBoxLayout(page)
    a = _table()
    lay.addWidget(a)
    plain = QTableWidget(5, 2)                # no column fits its contents: left alone
    plain.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    lay.addWidget(plain)
    assert settle_headers(page) == 1
    settled = [a.horizontalHeader().sectionSize(i) for i in range(3)]
    b = _table()                              # the same table, sized by Qt's own timer
    for _ in range(20):
        qapp.processEvents()
        time.sleep(0.005)
    assert [b.horizontalHeader().sectionSize(i) for i in range(3)] == settled
    assert settle_headers(None) == 0


def test_steps_settle_their_pages():
    import inspect
    from src.views import background_steps as bs
    for fn in (bs.scheme_step, bs.stats_step, bs.mapping_step, bs.settings_step):
        assert "settle_headers(" in inspect.getsource(fn), fn.__name__


# ── O1: the outline file parsed in small pieces ─────────────────────

def test_points_in_chunks_same_as_json(monkeypatch):
    from src.views import json_pieces as jp
    monkeypatch.setattr(jp, "CHUNK", 64)       # many chunks, even in small texts
    ring = [[51.5 + i / 1000, -1.25 - i / 3000] for i in range(400)]
    doc = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"VCNUMBER": 23, "VCNAME": "Oxon [x]]"},
         "geometry": {"type": "Polygon", "coordinates": [ring, ring[:5]]}},
        {"type": "Feature", "properties": {},
         "geometry": {"type": "MultiPolygon", "coordinates": [[ring[:50]], [ring[100:300]]]}},
        {"x": [[1, 2, 3], [4, 5e-3, -6]], "y": [[1, [2]], [3]], "z": [[], [1]],
         "w": [["a", "b]]"], [1]], "v": [[1, 2]], "u": [[True, None], [1, 2]]},
    ]}
    for text in (json.dumps(doc), json.dumps(doc, indent=1), json.dumps(doc, indent="\t")):
        assert jp.loads_in_pieces(text) == json.loads(text)
    for bad in ('{"a": [[1, 2], [3, 4]', '{"a": [[1, 2],, [3]]}', '{"a": [[1, 2] [3]]}'):
        with pytest.raises(ValueError):
            jp.loads_in_pieces(bad)


def test_real_outline_file_in_pieces_same_and_short():
    import paths
    from src.views import json_pieces as jp
    if not paths.VC_GEOJSON.exists():
        pytest.skip("no outline file")
    text = paths.VC_GEOJSON.read_text(encoding="utf-8")
    assert jp.loads_in_pieces(text) == json.loads(text)
    # no single parse holds the GIL long: each piece is at most a feature's small parts or
    # a chunk of points
    longest = [0.0]
    real = json.loads

    class Timed:
        def __getattr__(self, name):
            return getattr(json, name)

        def loads(self, s, **k):
            t0 = time.perf_counter()
            try:
                return real(s, **k)
            finally:
                longest[0] = max(longest[0], time.perf_counter() - t0)
    saved, was_on = jp.json, gc.isenabled()
    jp.json = Timed()
    gc.disable()                 # as while loading (a collection is not the parse)
    try:
        jp.loads_in_pieces(text)
    finally:
        jp.json = saved
        if was_on:
            gc.enable()
    assert longest[0] < 0.02


# ── O1: Settings a panel at a time; labels worked out ahead ─────────

def test_settings_tab_built_in_parts_matches_built_at_once(qapp):
    from src.views.settings.settings_tab import SettingsTab
    whole = SettingsTab()
    parts = SettingsTab(build=False)
    assert not hasattr(parts, "panel_stack")
    n = sum(1 for _ in parts.build_parts())
    assert n >= 5
    assert parts.panel_stack.count() == whole.panel_stack.count() == 5
    for name in ("general_panel", "database_panel", "export_panel", "sync_panel",
                 "counting_panel"):
        assert type(getattr(parts, name)) is type(getattr(whole, name))
    got = []
    parts.settings_changed.connect(lambda: got.append(1))
    parts.general_panel.settings_changed.emit()
    assert got == [1]                                  # signals connected at the end


def test_label_points_worked_out_ahead(qapp):
    from src.views.background_steps import _label_points_ahead
    from shared.maps.vc_labels import label_points

    class Map:
        _label_pts = None
        _vc_rings = {23: [[(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]]}
    m = Map()
    _label_points_ahead(m)
    assert m._label_pts == label_points(Map._vc_rings)
    kept = m._label_pts
    _label_points_ahead(m)                             # already there: left alone
    assert m._label_pts is kept


def test_mapping_step_no_longer_paints_off_screen():
    import inspect
    from src.views import background_steps as bs
    assert ".grab()" not in inspect.getsource(bs.mapping_step)


# ── O2: square opacity ──────────────────────────────────────────────

def test_opacity_slider_default_remembered_and_beside_the_switches(settings_sandbox):
    from PySide6.QtCore import QSettings
    from src.views.mapping.display_bar import OPACITY_SETTING, MapDisplayBar
    bar = MapDisplayBar()
    assert bar.square_opacity() == 100                    # as before until it is moved
    assert bar.opacity_label.text() == "Square opacity"
    assert bar.opacity_value.text() == "100%"
    s = bar.opacity_slider
    assert (s.minimum(), s.maximum()) == (0, 100)
    lay = bar.layout()
    assert lay.indexOf(bar.opacity_label) == lay.indexOf(bar.districts_check) + 1
    assert lay.indexOf(bar.opacity_slider) == lay.indexOf(bar.opacity_label) + 1
    got = []
    bar.square_opacity_changed.connect(got.append)
    s.setValue(40)
    assert got == [40] and bar.opacity_value.text() == "40%"
    QSettings().sync()
    assert QSettings().value(OPACITY_SETTING, 100, type=int) == 40
    assert MapDisplayBar().square_opacity() == 40         # remembered
    QSettings().setValue(OPACITY_SETTING, "rubbish")
    assert MapDisplayBar().square_opacity() == 100


def test_slider_does_not_hold_a_laptop_window_wide(settings_sandbox):
    """The bar may give up width on a narrow window (the slider down to 56 px, the two lists
    to 110 px) instead of growing the Mapping page's minimum by the whole slider."""
    from src.views.mapping.display_bar import MapDisplayBar
    bar = MapDisplayBar()
    s = bar.opacity_slider
    assert s.minimumWidth() == 56 and s.maximumWidth() >= s.sizeHint().width()
    for combo in (bar.style_combo, bar.period_combo):
        assert 0 < combo.minimumWidth() <= 110
        assert combo.minimumWidth() <= combo.sizeHint().width()


def _square_map(qapp):
    from shared.maps import grid_squares as gs
    from shared.maps.grid_map import GridMap
    m = GridMap()
    m.resize(400, 500)
    m.set_vc_labels(False)
    e, n = 450000.0, 200000.0
    lab = gs.square_for_point(e, n, gs.HECTAD)
    b = gs.square_bounds(lab)
    centre = ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
    return m, lab, centre


def _pixel(m, centre):
    img = m.grab().toImage()
    x, y = m.fit().to_px(*centre)
    c = img.pixelColor(round(x), round(y))
    return c.red(), c.green(), c.blue()


def test_opacity_applies_to_the_squares_at_once(qapp):
    from shared.maps import grid_squares as gs
    m, lab, centre = _square_map(qapp)
    under = _pixel(m, centre)                               # no square: what lies under it
    m.set_squares({lab: {"count": 1, "fill": "#ff0000"}}, gs.HECTAD)
    assert m.square_opacity() == 100
    assert _pixel(m, centre) == (255, 0, 0)                 # 100 %: solid, as before R8
    m.set_square_opacity(0)
    assert _pixel(m, centre) == under                       # 0 %: only what is under it
    m.set_square_opacity(50)
    half = _pixel(m, centre)
    for got, a, b in zip(half, (255, 0, 0), under):
        assert min(a, b) - 2 <= got <= max(a, b) + 2
    assert half != (255, 0, 0) and half != under
    m.set_square_opacity(250)
    assert m.square_opacity() == 100                       # kept within 0-100


def test_selected_outline_stays_solid_and_order_kept(qapp, monkeypatch):
    """The clicked square's outline is drawn at full strength whatever the opacity; the
    painter's opacity is back to normal for the outline and the labels."""
    from shared.maps import grid_squares as gs
    m, lab, centre = _square_map(qapp)
    m.set_squares({lab: {"count": 1, "fill": "#ff0000"}}, gs.HECTAD)
    m.set_selected(lab)
    m.set_square_opacity(20)
    import shared.maps.grid_map as gm
    seen = []
    real = gm.QPainter.drawRect

    def spy(p, *a):
        seen.append(round(p.opacity(), 2))
        return real(p, *a)
    monkeypatch.setattr(gm.QPainter, "drawRect", spy)
    m.grab()
    assert seen[0] == 0.2 and seen[-1] == 1.0               # the square, then its outline


def test_mapping_tab_wires_the_slider_and_the_atlas_page_follows(qapp, settings_sandbox):
    from PySide6.QtCore import QSettings
    from src.views.mapping.display_bar import OPACITY_SETTING, MapDisplayBar
    from shared.maps.grid_map import GridMap
    QSettings().setValue(OPACITY_SETTING, 30)
    bar = MapDisplayBar()
    m = GridMap()
    bar.attach_map(m)
    assert m.square_opacity() == 30                         # the saved setting, at once
    bar.opacity_slider.setValue(75)
    assert m.square_opacity() == 75
    # the atlas page is drawn by the same map (GridMap.draw -> _draw_squares)
    import inspect
    from shared.maps import atlas_sheet
    assert "self.draw(" in inspect.getsource(atlas_sheet)

