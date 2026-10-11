"""Review of Round 4 (11 Oct 2026).

1. shared/maps/project_many: the vice-county outlines projected on arrays give the same
   eastings/northings as shared/osgb.wgs84_to_osgb_en point by point (the Mapping tab's
   first opening spent most of its time projecting one point at a time).
2. Recording Scheme records read in the background are read again when Settings (scheme
   families, species counting) change before the tab is first opened.
3. Backups reached by a test stay in the test folder (tests/conftest.py).
4. Closing the window stops the background Recording Scheme load first (a running QThread
   aborted the process on exit).
"""
import json
import random

import pytest

from shared.osgb import wgs84_to_osgb_en


def _points(n=500, seed=4):
    rnd = random.Random(seed)
    # GB and a little beyond (Scilly to Shetland, Channel Islands longitudes)
    return [(rnd.uniform(49.0, 61.0), rnd.uniform(-8.7, 2.0)) for _ in range(n)]


def test_project_many_matches_one_point_function():
    from shared.maps.project_many import project_many
    pts = _points()
    got = project_many(pts)
    assert len(got) == len(pts)
    for (lat, lon), (e, n) in zip(pts, got):
        e1, n1 = wgs84_to_osgb_en(lat, lon)
        assert abs(e - e1) < 1e-6 and abs(n - n1) < 1e-6
    assert project_many([]) == []
    assert project_many(pts[:3]) == [wgs84_to_osgb_en(a, b) for a, b in pts[:3]]


def test_project_many_without_numpy(monkeypatch):
    import shared.maps.project_many as pm
    monkeypatch.setattr(pm, "_np", None)
    pts = _points(40)
    assert pm.project_many(pts) == [wgs84_to_osgb_en(a, b) for a, b in pts]


@pytest.mark.parametrize("tol", [300.0, 100.0, 0])
def test_load_vc_polygons_same_as_point_by_point(tmp_path, monkeypatch, tol):
    """The outlines load_vc_polygons returns are the ones the one-point projection gives."""
    import shared.maps.project_many as pm
    import shared.maps.vc_map as vm
    rnd = random.Random(7)

    def ring(lat0, lon0, k=60, r=0.3):
        import math
        pts = [[lat0 + r * math.sin(2 * math.pi * i / k) * (1 + 0.1 * rnd.random()),
                lon0 + 2 * r * math.cos(2 * math.pi * i / k)] for i in range(k)]
        return pts + [pts[0]]

    gj = {"type": "FeatureCollection", "features": [
        {"properties": {"VCNUMBER": 23, "VCNAME": "Oxfordshire"},
         "geometry": {"type": "Polygon", "coordinates": [ring(51.8, -1.3)]}},
        {"properties": {"VCNUMBER": 1, "VCNAME": "West Cornwall"},
         "geometry": {"type": "MultiPolygon", "coordinates": [
             [ring(50.2, -5.3)], [ring(49.93, -6.3, k=6, r=0.002)], [[[49.9, -6.4]]]]}},
    ]}
    path = tmp_path / "vc.geojson"
    path.write_text(json.dumps(gj), encoding="utf-8")
    monkeypatch.setattr(vm, "_CACHE", {})        # the process's own cache left alone
    monkeypatch.setattr(vm, "_NAMES", {})
    fast = vm.load_vc_polygons(str(path), tol=tol)
    monkeypatch.setattr(vm, "_CACHE", {})
    monkeypatch.setattr(pm, "_np", None)
    slow = vm.load_vc_polygons(str(path), tol=tol)
    assert fast[0].keys() == slow[0].keys() == {1, 23}
    for vc in fast[0]:
        assert [len(r) for r in fast[0][vc]] == [len(r) for r in slow[0][vc]]
        for rf, rs in zip(fast[0][vc], slow[0][vc]):
            for (e1, n1), (e2, n2) in zip(rf, rs):
                assert abs(e1 - e2) < 1e-6 and abs(n1 - n2) < 1e-6
    assert all(abs(a - b) < 1e-6 for a, b in zip(fast[1], slow[1]))


# ------------------------------------------------- 2. settings changed before first opening

@pytest.fixture(scope="module")
def qapp():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_scheme_preload_reread_when_settings_change_before_first_opening(qapp, monkeypatch):
    """Records read in the background, then Settings > scheme families (or a counting
    switch) changed, then the tab opened: it showed the old load (on the copy, 110,510
    records with the families set to Carabidae). The background load is now read again."""
    import src.views.scheme.recording_scheme_tab as rst
    tab = rst.RecordingSchemeTab()
    loads = []
    monkeypatch.setattr(tab, "_load_data", lambda filters=None: loads.append(filters))
    tab.reload_preload()                          # no background load started: nothing
    assert loads == []
    tab._preload_started = True
    tab._preload_records = (["stale"], 1, {}, 1)
    tab.reload_preload()
    assert loads == [None] and tab._preload_records is None
    tab._initialized = True                       # once opened, the caller refreshes it
    tab.reload_preload()
    assert loads == [None]


def test_main_window_rereads_unopened_scheme_tab(monkeypatch):
    import src.views.main_window as mw
    calls = []

    class RS:
        _initialized = False

        def refresh(self):
            calls.append("refresh")

        def reload_preload(self):
            calls.append("reload")

    fake = type("W", (), {"recording_scheme_tab": RS()})()
    mw.MainWindow._refresh_scheme_tab_if_loaded(fake)
    fake.recording_scheme_tab._initialized = True
    mw.MainWindow._refresh_scheme_tab_if_loaded(fake)
    assert calls == ["reload", "refresh"]


def test_backups_go_to_the_test_folder(_backups_never_leave_the_test_folder):
    """tests/conftest.py: nothing a test reaches writes C:\\BiologicalSoftware_Backups."""
    import DataEntry.csv_backup as cb
    import shared.backup_service as bs
    folder = _backups_never_leave_the_test_folder
    assert cb.BACKUP_DIR == folder and bs.BACKUP_ROOT == folder
    assert "BiologicalSoftware_Backups" not in folder
    path = cb._write_rows("probe.csv", ["a"], [[1]])
    assert path and path.startswith(folder)


def test_scheme_load_stopped_before_the_window_closes(qapp):
    """Closing Observatum while the Recording Scheme records still loaded in the background
    aborted the process ('QThread: Destroyed while thread is still running'). stop_loading()
    cancels the load and waits for its thread; closeEvent calls it first."""
    import threading
    import inspect
    from PySide6.QtCore import QThread
    import src.views.main_window as mw
    import src.views.scheme.recording_scheme_tab as rst

    class Slow(QThread):
        def __init__(self):
            super().__init__()
            self.stop = threading.Event()
            self.cancelled = False

        def cancel(self):
            self.cancelled = True
            self.stop.set()

        def run(self):
            self.stop.wait(30)

    tab = rst.RecordingSchemeTab()
    w1, w2 = Slow(), Slow()
    tab._data_worker, tab._old_workers = w1, [w2]
    w1.start()
    w2.start()
    assert w1.isRunning() and w2.isRunning()
    tab.stop_loading()
    assert w1.cancelled and w2.cancelled
    assert not w1.isRunning() and not w2.isRunning()
    tab.stop_loading()                            # nothing running: harmless
    src = inspect.getsource(mw.MainWindow.closeEvent)
    assert src.index("stop_loading") < src.index("wal_checkpoint")
