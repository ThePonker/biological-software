"""25 Nov 2026: the Insect Collection reloads on its next visit after specimens may have changed
elsewhere (Make specimens or a delete on Observation Data, an import, a visit to Data Entry)."""
from types import SimpleNamespace


def _window():
    from src.views.main_window import MainWindow
    coll, de, obs = SimpleNamespace(n=0), object(), object()
    coll.refresh = lambda: setattr(coll, "n", coll.n + 1)
    pages = {0: obs, 1: coll, 2: de}
    mw = SimpleNamespace(
        _ready=True, _tab_pending_in_background=lambda i: False,
        tabs=SimpleNamespace(widget=lambda i: pages[i]),
        stats_reports_tab=None, observation_tab=obs, insect_collection_tab=coll,
        recording_scheme_tab=None, data_entry_tab=de, _initialized_tabs={0, 1, 2},
        statusbar=SimpleNamespace(showMessage=lambda *a: None))
    mw._mark_collection_stale = lambda *a: MainWindow._mark_collection_stale(mw, *a)
    return MainWindow, mw, coll


def test_collection_reloads_once_after_a_change():
    MainWindow, mw, coll = _window()
    MainWindow._on_tab_changed(mw, 1)
    assert coll.n == 0                         # nothing changed: no reload
    mw._mark_collection_stale()                # e.g. Make specimens on Observation Data
    MainWindow._on_tab_changed(mw, 1)
    MainWindow._on_tab_changed(mw, 1)
    assert coll.n == 1                         # once, not on every visit
    MainWindow._on_tab_changed(mw, 2)          # a visit to Data Entry (make / commit there)
    MainWindow._on_tab_changed(mw, 0)
    MainWindow._on_tab_changed(mw, 1)
    assert coll.n == 2
