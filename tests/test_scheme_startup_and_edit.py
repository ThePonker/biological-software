"""Startup cannot hang on the Recording Scheme load (OBS-02 / SRCH20b); the scheme
CSV export writes the values (it wrote blanks from sqlite3.Row); an edited grid ref
re-derives vice-county and lat/long (OBS-03)."""
import csv
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import paths  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_worker_error_still_sets_ready(tmp_path):
    from src.views.scheme.scheme_data_worker import SchemeDataWorker
    w = SchemeDataWorker(str(tmp_path / "no_such_dir" / "x.db"))
    w.run()                                   # synchronously: raises inside, must not hang
    assert w.results_ready.is_set()
    assert w.results is None
    assert w.error_message


def test_worker_success_sets_results(tmp_path):
    import sqlite3
    from src.views.scheme.scheme_data_worker import SchemeDataWorker
    db = tmp_path / "o.db"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE recording_scheme (id INTEGER, species_name TEXT, date TEXT, family TEXT)")
    c.execute("INSERT INTO recording_scheme VALUES (1, 'Rhagium mordax', '2024-05-01', 'Cerambycidae')")
    c.commit()
    c.close()
    w = SchemeDataWorker(str(db))
    w.run()
    assert w.results_ready.is_set() and w.error_message is None
    records, n_species = w.results
    assert n_species == 1 and records[0]["species_name"] == "Rhagium mordax"


def test_tab_takes_finished_worker_results_directly(qapp, tmp_path, monkeypatch):
    """initialize() after the worker finished but before the poll timer collected:
    used to read the undefined self._worker_results and stop startup."""
    import sqlite3
    from src.views.scheme.recording_scheme_tab import RecordingSchemeTab
    from src.views.scheme.scheme_data_worker import SchemeDataWorker
    import src.views.scheme.recording_scheme_tab as rst

    db = tmp_path / "o.db"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE recording_scheme (id INTEGER, species_name TEXT, date TEXT, family TEXT)")
    c.execute("INSERT INTO recording_scheme VALUES (1, 'Rhagium mordax', '2024-05-01', 'Cerambycidae')")
    c.commit()
    c.close()

    tab = RecordingSchemeTab()
    assert tab._worker_results is None                      # defined from the start
    w = SchemeDataWorker(str(db))
    w.run()
    tab._data_worker = w
    monkeypatch.setattr(rst, "get_database", lambda: None)
    monkeypatch.setattr(tab.filter_bar, "initialize_with_database", lambda db: None)
    monkeypatch.setattr(tab, "_load_wizard_tab_data", lambda: None)
    tab.initialize(str(db))
    assert tab.table_model.rowCount() == 1


def test_tab_initialize_after_worker_error_does_not_raise(qapp, tmp_path, monkeypatch):
    from src.views.scheme.recording_scheme_tab import RecordingSchemeTab
    from src.views.scheme.scheme_data_worker import SchemeDataWorker
    import src.views.scheme.recording_scheme_tab as rst

    tab = RecordingSchemeTab()
    w = SchemeDataWorker(str(tmp_path / "missing" / "x.db"))
    w.run()
    tab._data_worker = w
    monkeypatch.setattr(rst, "get_database", lambda: None)
    monkeypatch.setattr(tab.filter_bar, "initialize_with_database", lambda db: None)
    tab.initialize()
    assert tab.worker_error()
    assert tab.table_model.rowCount() == 0


def test_scheme_export_writes_values(qapp, tmp_path, monkeypatch):
    import sqlite3
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    from src.views.scheme.recording_scheme_tab import RecordingSchemeTab

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE recording_scheme (id INTEGER, species_name TEXT, grid_ref TEXT)")
    conn.execute("INSERT INTO recording_scheme VALUES (1, 'Rhagium mordax', 'SP5822')")
    rows = conn.execute("SELECT * FROM recording_scheme").fetchall()   # sqlite3.Row, as execute_main gives
    out = tmp_path / "rs.csv"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(out), "")))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    RecordingSchemeTab()._export_rs_records(rows, "t")
    with open(out, encoding="utf-8-sig") as f:
        r = list(csv.DictReader(f))
    assert r[0]["Species"] == "Rhagium mordax" and r[0]["Grid Ref"] == "SP5822"


# ── OBS-03: edited grid ref ────────────────────────────────────────────────

class _FakeVC:
    def __init__(self, result):
        self.result = result

    def assess(self, ref):
        return self.result


def test_derive_location_unchanged_ref_changes_nothing():
    from src.views.observations.observation_detail_mixin import ObservationDetailMixin as M
    assert M._derive_location_fields("SO 539 092", "so539092", _FakeVC(None)) == ({}, "")


def test_derive_location_new_ref_sets_vc_latlon_and_note():
    from src.views.observations.observation_detail_mixin import ObservationDetailMixin as M
    vc = _FakeVC({"vc_number": 16, "vc_name": "West Kent", "boundary": True,
                  "vcs": [(16, 60), (17, 40)], "note": "On the VC16/VC17 boundary: ..."})
    out, note = M._derive_location_fields("TQ5070", "SO539092", vc)
    assert out["vc_number"] == 16 and out["vice_county"] == "West Kent"
    assert 51.3 < out["latitude"] < 51.5 and 0.1 < out["longitude"] < 0.3
    assert out["geodetic_datum"] == "WGS84"
    assert note.startswith("On the VC16/VC17 boundary")


def test_derive_location_no_vc_clears_old_values():
    from src.views.observations.observation_detail_mixin import ObservationDetailMixin as M
    out, note = M._derive_location_fields("TQ5070", "SO539092", _FakeVC(None))
    assert out["vc_number"] is None and out["vice_county"] is None


@pytest.mark.skipif(not os.path.exists(str(getattr(paths, "VC_LOOKUP_DB", ""))),
                    reason="vc_lookup.db not present")
def test_derive_location_real_lookup_moves_off_vc34():
    """The review's case: SO539092 (VC34 West Gloucestershire) edited to TQ5070."""
    from src.services.vc_lookup_service import VCLookupService
    from src.views.observations.observation_detail_mixin import ObservationDetailMixin as M
    out, _ = M._derive_location_fields("TQ5070", "SO539092", VCLookupService())
    assert out["vc_number"] not in (None, 34)
