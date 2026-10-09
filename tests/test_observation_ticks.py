"""Observation Data / Recording Scheme: ticks follow records through a sort (OBS-01),
Delete Selected names and deletes the ticked records, the iRecord export leaves out
records that came from iRecord (OBS-12), and an edited grid ref re-derives VC and
lat/long (OBS-03). Driven offscreen on small throwaway databases.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import paths  # noqa: E402

RECORDS = [
    {"id": 11, "species_name": "Pterostichus madidus", "date": "2024-05-01",
     "site_name": "Bicester", "grid_ref": "SP5822"},
    {"id": 12, "species_name": "Harpalus affinis", "date": "2024-06-02",
     "site_name": "Banbury", "grid_ref": "SP4540"},
    {"id": 13, "species_name": "Abax parallelepipedus", "date": "2024-07-03",
     "site_name": "Wytham", "grid_ref": "SP4608"},
    {"id": 14, "species_name": "Abax parallelus", "date": "2024-08-04",
     "site_name": "Otmoor", "grid_ref": "SP5614"},
]


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _tick(model, row):
    from PySide6.QtCore import Qt
    model.setData(model.index(row, 0), Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)


def _sort_by(tab, model, key, desc=False):
    from PySide6.QtCore import Qt
    col = [c[0] for c in model.COLUMNS].index(key)
    tab.sort_proxy.sort(col, Qt.SortOrder.DescendingOrder if desc else Qt.SortOrder.AscendingOrder)


@pytest.fixture
def obs_tab(qapp):
    from src.views.observations.observation_tab import ObservationTab
    tab = ObservationTab()
    tab.table_model.set_observations([dict(r) for r in RECORDS])
    tab._connect_proxy_after_load()
    return tab


def test_observation_ticks_follow_records_through_sort(obs_tab):
    m = obs_tab.table_model
    _tick(m, 0)                                   # P. madidus
    _tick(m, 1)                                   # H. affinis
    assert sorted(m.get_checked_ids()) == [11, 12]
    _sort_by(obs_tab, m, "species_name")          # Abax ... first
    assert [r["id"] for r in m._observations][:2] == [13, 14]
    assert sorted(m.get_checked_ids()) == [11, 12]              # not the two Abax
    assert {o["species_name"] for o in m.get_checked_observations()} == \
        {"Pterostichus madidus", "Harpalus affinis"}
    # the tick drawn on screen follows too
    from PySide6.QtCore import Qt
    shown = [m.data(m.index(r, 0), Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked
             for r in range(m.rowCount())]
    assert [m._observations[i]["id"] for i, s in enumerate(shown) if s] == \
        [r["id"] for r in m._observations if r["id"] in (11, 12)]
    assert m.checked_count() == 2
    m.set_all_checked(True)
    assert m.checked_count() == 4
    m.set_all_checked(False)
    assert m.get_checked_ids() == []


class _FakeDB:
    def __init__(self, path):
        self.path = path

    def execute_main_write(self, sql, params=()):
        conn = sqlite3.connect(self.path)
        conn.execute(sql, params)
        conn.commit()
        conn.close()


def _make_obs_db(path):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, species_name TEXT, "
                 "date TEXT, site_name TEXT, grid_ref TEXT, record_type TEXT)")
    conn.executemany("INSERT INTO observations (id, species_name, date, site_name, grid_ref) "
                     "VALUES (:id, :species_name, :date, :site_name, :grid_ref)", RECORDS)
    conn.commit()
    conn.close()


def _ids(path):
    conn = sqlite3.connect(path)
    try:
        return sorted(r[0] for r in conn.execute("SELECT id FROM observations"))
    finally:
        conn.close()


def test_delete_selected_deletes_ticked_records_after_sort(obs_tab, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    import src.models.database as dbmod
    from shared import backup_service as bs

    db_path = str(tmp_path / "observatum.db")
    _make_obs_db(db_path)
    monkeypatch.setattr(paths, "OBSERVATUM_DB", tmp_path / "observatum.db")
    monkeypatch.setattr(bs, "BACKUP_ROOT", str(tmp_path / "backups"))
    monkeypatch.setattr(dbmod, "get_database", lambda: _FakeDB(db_path))
    monkeypatch.setattr(obs_tab, "_load_data", lambda *a, **k: None)
    shown = {}

    def fake_warning(parent, title, text, *a, **k):
        shown["text"] = text
        return QMessageBox.StandardButton.Yes
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(fake_warning))

    m = obs_tab.table_model
    _tick(m, 0)
    _tick(m, 1)
    _sort_by(obs_tab, m, "species_name")
    obs_tab._on_delete_selected()

    assert _ids(db_path) == [13, 14]                       # the two Abax survive
    assert "Pterostichus madidus" in shown["text"] and "Harpalus affinis" in shown["text"]
    assert "Abax" not in shown["text"]
    assert "Bicester" in shown["text"]                     # site is named
    kept = os.listdir(tmp_path / "backups" / "kept")
    assert len(kept) == 1 and "pre-delete" in kept[0]      # backed up first


def test_delete_refused_when_backup_fails(obs_tab, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    import src.models.database as dbmod
    import shared.backup_service as bs

    db_path = str(tmp_path / "observatum.db")
    _make_obs_db(db_path)
    monkeypatch.setattr(dbmod, "get_database", lambda: _FakeDB(db_path))
    monkeypatch.setattr(bs, "backup_main_only", lambda label="": False)
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: None))
    _tick(obs_tab.table_model, 0)
    obs_tab._on_delete_selected()
    assert _ids(db_path) == [11, 12, 13, 14]


def test_describe_records_lists_first_15_then_more():
    from src.views.observations.checked_records import describe_records
    recs = [{"species_name": f"Sp {i}", "date": "", "site_name": f"Site {i}"} for i in range(20)]
    text = describe_records(recs)
    lines = text.splitlines()
    assert len(lines) == 16
    assert "Sp 0" in lines[0] and "Site 0" in lines[0] and "no date" in lines[0]
    assert lines[-1].endswith("and 5 more")


def test_mark_commercial_and_export_use_ticked_records(obs_tab, monkeypatch):
    m = obs_tab.table_model
    _tick(m, 2)                                    # Abax parallelepipedus (id 13)
    _sort_by(obs_tab, m, "date", desc=True)
    got = {}
    monkeypatch.setattr(obs_tab, "_export_observations",
                        lambda obs, title: got.setdefault("ids", [o["id"] for o in obs]))
    obs_tab._on_export_selected()
    assert got["ids"] == [13]

    import src.views.dialogs.mark_commercial_dialog as mcd
    captured = {}

    class FakeDialog:
        def __init__(self, n, parent=None):
            captured["n"] = n

        def exec(self):
            return 0                               # cancelled: nothing written
    monkeypatch.setattr(mcd, "MarkCommercialDialog", FakeDialog)
    obs_tab._mark_as_commercial()
    assert captured["n"] == 1


def test_irecord_export_leaves_out_irecord_sourced_records():
    from src.views.observations.observation_export_mixin import ObservationExportMixin
    recs = [
        {"id": 1, "irecord_id": 34898641, "source": "iRecord | iRecord Import"},
        {"id": 2, "irecord_id": None, "source": "iRecord | iRecord App"},
        {"id": 3, "irecord_id": "", "source": None},
        {"id": 4, "irecord_id": None, "source": "", "never_upload_to_irecord": 1},
        {"id": 5, "irecord_id": None, "source": "", "embargo_status": "Active",
         "embargo_until": "2999-01-01"},
        {"id": 6, "irecord_id": 777, "source": None},
    ]
    keep, counts = ObservationExportMixin._irecord_export_filter(recs)
    assert [r["id"] for r in keep] == [3]
    assert counts == {"from_irecord": 3, "never_upload": 1, "embargo": 1}


# ── Recording Scheme ────────────────────────────────────────────────────────

def test_scheme_ticks_follow_records_through_sort(qapp):
    from src.views.scheme.scheme_record_model import SchemeRecordModel
    from src.views.scheme.recording_scheme_tab import FastSortProxy
    from PySide6.QtCore import Qt
    m = SchemeRecordModel()
    m.set_records([dict(r) for r in RECORDS])
    proxy = FastSortProxy()
    proxy.setSourceModel(m)
    _tick(m, 0)
    _tick(m, 1)
    col = [c[0] for c in m.COLUMNS].index("species_name")
    proxy.sort(col, Qt.SortOrder.AscendingOrder)
    assert sorted(m.get_checked_ids()) == [11, 12]
    assert {r["species_name"] for r in m.get_checked_records()} == \
        {"Pterostichus madidus", "Harpalus affinis"}
    m.removeRows(0, 1)                              # an Abax goes; ticks unaffected
    assert sorted(m.get_checked_ids()) == [11, 12]


def test_scheme_export_selected_uses_ticked_ids(qapp, monkeypatch):
    from src.views.scheme.recording_scheme_tab import RecordingSchemeTab
    from PySide6.QtCore import Qt
    tab = RecordingSchemeTab()
    tab.table_model.set_records([dict(r) for r in RECORDS])
    tab._connect_proxy_after_load()
    _tick(tab.table_model, 0)
    col = [c[0] for c in tab.table_model.COLUMNS].index("species_name")
    tab.sort_proxy.sort(col, Qt.SortOrder.AscendingOrder)
    seen = {}

    class DB:
        def execute_main(self, sql, params=()):
            seen["params"] = params
            return []
    import src.views.scheme.recording_scheme_tab as rst
    monkeypatch.setattr(rst, "get_database", lambda: DB())
    monkeypatch.setattr(tab, "_export_rs_records", lambda rows, title: None)
    tab._on_export_selected()
    assert seen.get("params") == (11,)


def test_deselect_all_clears_single_ticks_in_one_click(obs_tab):
    """Ticking single records turns the button to 'Deselect All' (Wil, 9 Oct)."""
    m, btn = obs_tab.table_model, obs_tab.toolbar.select_all_btn
    _tick(m, 1)
    _tick(m, 2)
    assert btn.text() == "Deselect All"
    btn.click()
    assert m.get_checked_ids() == [] and btn.text() == "Select All"
