"""The steps finished in the background after the main window opens (Round 6).

Order (Wil): Recording Scheme records, Stats/Reports, Mapping (map outlines, the tab, its
coast and border lines and its first drawing at the window's size), Settings, the species
search index. Each is a generator for background_loader.BackgroundLoader: data work in
worker threads (InThread), widget building in short slices on the GUI thread (bare yield).

A step returns True when its tab is ready; MainWindow.mark_tab_ready is called by the step.
A step that fails (or returns False) leaves its tab to load on first opening, as in Round 4.
"""

import importlib
from contextlib import contextmanager
from typing import List

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QApplication, QWidget

from .background_loader import InThread, Step, WaitFor

SCHEME_WAIT_MAX_S = 180          # the Recording Scheme read normally takes seconds

# the tab page each step makes ready (MainWindow attribute names)
STEP_PAGES = {
    "scheme": "recording_scheme_tab",
    "stats": "_stats_page",
    "mapping": "_mapping_page",
    "settings": "_settings_page",
}

LABELS = {
    "scheme": "Recording Scheme",
    "stats": "Stats/Reports",
    "mapping": "Mapping",
    "settings": "Settings",
    "species_search": "species search",
}


def settle_headers(page) -> int:
    """Size the table columns set to fit their contents now, on this turn (Round 8).

    A table header set to "resize to contents" sizes its columns a moment after its rows
    are filled, from the event loop. Each cell it measures calls back into Python (every
    widget made in PySide is a Python object), and from the event loop every such call has
    to wait its turn for Python's lock (GIL) while a loading thread is running Python: on
    Wil's PC the Personal Stats species table (500 rows) froze the window for 1.2 s that
    way. Done here, from Python, the same sizing holds the lock throughout: 5-20 ms.
    Returns how many headers were sized."""
    if page is None:
        return 0
    from PySide6.QtWidgets import QHeaderView
    fit = QHeaderView.ResizeMode.ResizeToContents
    n = 0
    for h in page.findChildren(QHeaderView):
        if h.model() is None or not h.count():
            continue
        if any(h.sectionResizeMode(i) == fit for i in range(h.count())):
            h.resizeSections()
            n += 1
    return n


def background_steps(w) -> List[Step]:
    """The steps for MainWindow `w`, in Wil's order."""
    return [
        Step("scheme", LABELS["scheme"], lambda: scheme_step(w),
             on_stop=lambda: w.recording_scheme_tab.stop_loading()),
        Step("stats", LABELS["stats"], lambda: stats_step(w)),
        Step("mapping", LABELS["mapping"], lambda: mapping_step(w)),
        Step("settings", LABELS["settings"], lambda: settings_step(w)),
        Step("species_search", LABELS["species_search"], species_search_step),
    ]


# ── Recording Scheme ────────────────────────────────────────────────

def start_scheme_read(w):
    """The Recording Scheme records start loading in their own worker thread (at once when
    the window opens; the step below then only waits for whatever is left)."""
    rs = w.recording_scheme_tab
    if getattr(rs, "_initialized", False) or getattr(rs, "_data_worker", None) is not None:
        return
    rs.start_preload(w._main_db_path)


def _scheme_records_ready(rs) -> bool:
    # the worker is looked up afresh each time: a Settings change before the tab was
    # ready starts a new read (reload_preload), and that is the one to wait for
    if getattr(rs, "_preload_records", None) is not None:
        return True
    worker = getattr(rs, "_data_worker", None)
    return worker is None or worker.results_ready.is_set()


def scheme_step(w):
    rs = w.recording_scheme_tab
    start_scheme_read(w)
    choices = None
    read = getattr(getattr(rs, "filter_bar", None), "read_choices", None)
    if read is not None:
        from ..models.database import get_database
        db = get_database()
        choices = yield InThread(lambda: read(db))      # the filter bar's lists
    yield WaitFor(lambda: _scheme_records_ready(rs), SCHEME_WAIT_MAX_S,
                  "loading the Recording Scheme records", busy=True)
    if choices is None:
        rs.initialize(w._main_db_path, w._uksi_db_path)
    else:
        rs.initialize(w._main_db_path, w._uksi_db_path, choices=choices)
    err = rs.worker_error() if hasattr(rs, "worker_error") else None
    if err:
        # not marked ready: the tab's first opening reports it (MainWindow._on_tab_changed)
        print(f"[startup] Recording Scheme records could not be loaded: {err}")
        return False
    yield
    settle_headers(rs)
    w.mark_tab_ready(rs)
    return True


# ── Stats/Reports ───────────────────────────────────────────────────

def _import(name: str):
    """Import a module of this package (in a worker thread: importing is Python work)."""
    return importlib.import_module(name, __package__)


def stats_step(w):
    yield InThread(lambda: _import(".stats"))
    tab = yield from w._stats_page.build_steps()
    # the Personal dashboard's figures (about a second of queries) in a thread; the service
    # keeps them, so initialize() below finds them ready
    from ..services.observation_stats_service import (get_observation_stats,
                                                      get_observation_stats_service)
    generation = w.settings_generation
    try:
        yield InThread(get_observation_stats)
    except Exception as e:
        print(f"[startup] observation figures not read ahead: {e}")
    if w.settings_generation != generation:
        # a setting changed while they were read: they may be the old ones
        get_observation_stats_service().invalidate()
    tab.initialize(w._main_db_path, w._uksi_db_path)
    yield
    settle_headers(tab)
    w.mark_tab_ready(w._stats_page)
    return True


# ── Mapping ─────────────────────────────────────────────────────────

def _read_map_data():
    """The vice-county outlines and the coast (cached by shared/maps), read and projected,
    and the Mapping filter panel's lists (recorders, sites, projects, vice-counties)."""
    import paths
    _import(".mapping")
    from shared.maps import grid_map, vc_map
    from ..services.map_selection import distinct_values, vc_choices
    geojson = str(paths.VC_GEOJSON) if paths.VC_GEOJSON.exists() else None
    land = {}
    loader = getattr(grid_map, "_load_gb_outline", None)
    if loader is not None:
        land = loader(str(paths.MAPS_DIR))[0]
    if geojson:
        from .json_pieces import pieces_for
        with pieces_for(vc_map):        # the window keeps responding while it is parsed
            vc_map.load_vc_polygons(geojson)
            vc_map.vc_names(geojson)
            if not land:
                vc_map.load_vc_polygons(geojson, tol=100.0)
    lists = {}
    for kind in ("recorder", "site", "project"):
        try:
            lists[kind] = distinct_values(kind)
        except Exception as e:          # the panel reads it itself
            print(f"[startup] map {kind} list not read ahead: {e}")
    try:
        lists["vc"] = vc_choices()
    except Exception as e:
        print(f"[startup] map vice-county list not read ahead: {e}")
    return lists


@contextmanager
def prefetched_map_lists(lists):
    """While the Mapping tab is built: its filter panel takes the lists read in the thread
    instead of querying the database on the GUI thread (a quarter of a second)."""
    from .mapping import filter_panel as fp
    real_values, real_vcs = fp.distinct_values, fp.vc_choices

    def values(kind, db_path=None):
        if db_path is None and kind in lists:
            return list(lists[kind])
        return real_values(kind, db_path)

    def vcs(*a, **k):
        if not a and not k and "vc" in lists:
            return list(lists["vc"])
        return real_vcs(*a, **k)
    fp.distinct_values, fp.vc_choices = values, vcs
    try:
        yield
    finally:
        fp.distinct_values, fp.vc_choices = real_values, real_vcs


def _size_hidden_page(page: QWidget, like: QWidget):
    """Lay out a hidden tab page at the size of the page on screen (Qt keeps a hidden
    widget's resize pending until it is shown, so its map would be laid out small)."""
    page.setGeometry(like.geometry())
    for _round in range(4):
        for x in (page, *page.findChildren(QWidget)):
            if x.testAttribute(Qt.WidgetAttribute.WA_PendingResizeEvent):
                x.setAttribute(Qt.WidgetAttribute.WA_PendingResizeEvent, False)
                QApplication.sendEvent(x, QResizeEvent(x.size(), QSize()))
            lay = x.layout()
            if lay is not None:
                lay.activate()


def mapping_step(w):
    try:
        w._map_lists = yield InThread(_read_map_data)
    except Exception as e:              # the Mapping tab reads them itself when it is built
        print(f"[startup] map outlines not read ahead: {e}")
        w._map_lists = {}
    tab = yield from w._mapping_page.build_steps()
    w._map_lists = None
    yield
    settle_headers(tab)
    w.mark_tab_ready(w._mapping_page)
    mw = getattr(tab, "map_widget", None)
    if mw is None or not hasattr(mw, "_chains"):
        return True
    yield
    # the coast and VC border lines (split once per outline file, ~1 s): worked out now
    # rather than on the Mapping tab's first paint (data only). If this fails the first
    # paint works them out as before: nothing to report.
    try:
        yield InThread(lambda: [mw._chains(name) for name in ("coast", "vc_inland")])
    except Exception as e:
        print(f"[startup] coast lines not prepared: {e}")
        return True
    # the outlines projected for the window's size and the VC label positions worked out,
    # in a thread, so the first opening of Mapping is only its paint. (Round 8: no longer an
    # off-screen paint here as well -- it held the window 0.15-0.25 s, and the map has no
    # picture cache, so its first opening painted again anyway.)
    page, shown = w._mapping_page, w.tabs.currentWidget()
    if shown is None or shown is page or not w.isVisible():
        return True
    _size_hidden_page(page, shown)
    if mw.width() < 50 or mw.height() < 50:
        return True
    fit = mw.fit()
    try:
        yield InThread(lambda: (mw._polygons(fit),
                                [mw._lines(name, fit) for name in ("coast", "vc_inland")],
                                _label_points_ahead(mw)))
    except Exception as e:
        print(f"[startup] map not projected ahead: {e}")
    return True


def _label_points_ahead(mw):
    """The VC label positions (GridMap works them out on its first paint otherwise; data
    only, ~50 ms of Python)."""
    if getattr(mw, "_label_pts", True) is None and getattr(mw, "_vc_rings", None):
        from shared.maps.vc_labels import label_points
        mw._label_pts = label_points(mw._vc_rings)


# ── Settings, species search ────────────────────────────────────────

def settings_step(w):
    yield InThread(lambda: _import(".settings"))
    tab = yield from w._settings_page.build_steps()
    yield
    settle_headers(tab)
    w.mark_tab_ready(w._settings_page)
    return True


def species_search_step():
    """The shared species-search index (used by every species box)."""
    from shared.species_search import get_index
    try:
        yield InThread(lambda: get_index(None))
    except Exception as e:              # a missing uksi.db must not stop startup
        print(f"[species_search] index not built: {e}")
    return True
