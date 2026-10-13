"""Cleaning report, 13 Oct 2026: double-click opens Record Detail (never iRecord); Edit / Delete
only on a live Observation row; the "Hidden here" tile; Show again stays on its tile.

Small purpose-made databases; offscreen; dialogs never block (exec is replaced).
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

OBS_COLS = ("id INTEGER PRIMARY KEY, irecord_id INTEGER, species_name TEXT, species_tvk TEXT, "
            "taxon_rank TEXT, date TEXT, date_type TEXT, grid_ref TEXT, site_name TEXT, "
            "recorder TEXT, latitude REAL, longitude REAL")
INS = "INSERT INTO {t} ({c}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)"


def _row(i, irec, grid="SP5820"):
    return (i, irec, "Clytus arietis", "T1", "Species", "2025-06-01", "D", grid, "A", "W", None, None)


def make_dbs(tmp_path, with_hidden_schema=True):
    """Observations 1 (live, coarse grid, iRecord 101), 2 (live, no iRecord ID, coarse grid),
    3 (hidden, iRecord 103), 4 (hidden and came back, iRecord 104); one scheme row (iRecord
    201, coarse grid) and one contributed row (coarse grid)."""
    main, uksi = tmp_path / "obs.db", tmp_path / "uksi.db"
    c = sqlite3.connect(main)
    c.execute(f"CREATE TABLE observations ({OBS_COLS})")
    c.executemany(INS.format(t="observations", c=OBS_COLS.replace(" INTEGER PRIMARY KEY", "")
                             .replace(" TEXT", "").replace(" REAL", "").replace(" INTEGER", "")),
                  [_row(1, 101, "SP58"), _row(2, None, "SP58"), _row(3, 103), _row(4, 104)])
    c.execute(f"CREATE TABLE recording_scheme ({OBS_COLS}, source TEXT)")
    c.execute("INSERT INTO recording_scheme VALUES (1,201,'Clytus arietis','T1','Species',"
              "'2025-06-01','D','SP58','A','W',NULL,NULL,'iRecord')")
    c.execute(f"CREATE TABLE contributed_observations ({OBS_COLS.replace('irecord_id INTEGER, ', '')}"
              f", contributor TEXT)")
    c.execute("INSERT INTO contributed_observations VALUES (1,'Clytus arietis','T1','Species',"
              "'2025-06-01','D','SP58','A','W',NULL,NULL,'Jon')")
    c.commit()
    if with_hidden_schema:
        import shared.hidden_records as hr
        hr.forget()
        hr.ensure_schema(c)
        hr.hide(c, 3, 103, "Clytus arietis")
        hr.hide(c, 4, 104, "Clytus arietis")
        hr.after_download(c, [104], "2026-10-12T09:30:00")
    c.close()
    u = sqlite3.connect(uksi)
    u.execute('CREATE TABLE taxa (tvk TEXT PRIMARY KEY, scientific_name TEXT, rank TEXT, '
              'parent_tvk TEXT, kingdom TEXT, "order" TEXT, family TEXT, genus TEXT)')
    u.execute("INSERT INTO taxa (tvk, scientific_name, rank) VALUES ('T1', 'Clytus arietis', 'Species')")
    u.execute("CREATE TABLE common_names (common_name TEXT, tvk TEXT, preferred INTEGER)")
    u.execute("CREATE TABLE synonyms (synonym TEXT, tvk TEXT)")
    u.execute("CREATE TABLE name_map (tvk TEXT PRIMARY KEY, recommended_tvk TEXT NOT NULL, name TEXT, "
              "recommended_name TEXT, name_status TEXT, deprecated TEXT, source TEXT)")
    u.execute("CREATE TABLE tvk_remap (old_tvk TEXT PRIMARY KEY, new_tvk TEXT, method TEXT, "
              "old_name TEXT, new_name TEXT)")
    u.commit()
    u.close()
    return str(main), str(uksi)


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


# ------------------------------------------------------------------ (a) the report

def test_hidden_tile_lists_every_hidden_row(tmp_path):
    from src.services.cleaning_report import OBSERVATION_ONLY, PROBLEMS, build_report
    main, uksi = make_dbs(tmp_path)
    assert "hidden" in OBSERVATION_ONLY and ("hidden", "Hidden here") in PROBLEMS
    rep = build_report(main, uksi, "observations")
    assert [r.record_id for r in rep.rows["hidden"]] == [3, 4]
    plain, back = rep.rows["hidden"]
    assert plain.detail.startswith("Removed here 20") and "came back" not in plain.detail
    assert "; came back from iRecord 2026-10-12 09:30" in back.detail
    assert [r.record_id for r in rep.rows["returned"]] == [4]            # unchanged subset
    assert "(still hidden)" in rep.rows["returned"][0].detail
    # hidden rows are not checked: totals cover the two live records only
    assert (rep.total_records, rep.hidden_records, rep.records_with_problem) == (2, 2, 2)
    assert [r.record_id for r in rep.rows["grid"]] == [1, 2]
    assert rep.counts["hidden"] == 2 and rep.counts["returned"] == 1


def test_no_hidden_at_column_gives_empty_tile(tmp_path):
    from src.services.cleaning_report import build_report
    main, uksi = make_dbs(tmp_path, with_hidden_schema=False)
    rep = build_report(main, uksi, "observations")
    assert rep.rows["hidden"] == [] and rep.rows["returned"] == []
    assert (rep.total_records, rep.hidden_records) == (4, 0)
    other = build_report(main, uksi, "recording_scheme")
    assert other.total_records == 1


def test_export_has_hidden_sheet(tmp_path):
    from src.services.cleaning_export import SHEET_NAMES, export_csv_folder
    from src.services.cleaning_report import PROBLEMS, build_report
    main, uksi = make_dbs(tmp_path)
    rep = build_report(main, uksi, "observations")
    assert all(k in SHEET_NAMES for k, _ in PROBLEMS)
    folder = export_csv_folder(rep, str(tmp_path / "csv"))
    assert "hidden_here.csv" in os.listdir(folder)


# ------------------------------------------------------------------ the screen

@pytest.fixture
def dash(qapp, tmp_path, monkeypatch):
    """Dashboard on the small database; every detail dialog is recorded, none blocks."""
    from src.views.dialogs import RecordDetailDialog, SchemeRecordDetailDialog
    from src.views.stats.cleaning_dashboard import CleaningDashboard
    main, uksi = make_dbs(tmp_path)
    d = CleaningDashboard(main_db=main, uksi_db=uksi)
    d.main_path = main
    d.opened, d.dialogs, d.wired = [], [], []
    d.open_url = lambda u: d.opened.append(u.toString())
    for cls in (RecordDetailDialog, SchemeRecordDetailDialog):
        monkeypatch.setattr(cls, "exec", lambda self: d.dialogs.append(self) or 0)
    import src.views.observations.observation_record_actions as ora
    monkeypatch.setattr(ora, "wire_observation_detail",
                        lambda dlg, src: d.wired.append(dlg) or True)
    d.refresh()
    yield d
    d.deleteLater()


def _double_click(d, key, record_id=None):
    from PySide6.QtCore import Qt
    d.show_problem(key)
    model = d.current_view().model()
    for r in range(model.rowCount()):
        idx = model.index(r, 0)
        if record_id is None or idx.data(Qt.ItemDataRole.UserRole).record_id == record_id:
            d._on_double_click(idx)
            return
    raise AssertionError("row not found")


def _edit_delete_visible(dlg):
    from PySide6.QtWidgets import QPushButton
    return [b.text() for b in dlg.findChildren(QPushButton)
            if b.text().strip() in ("Edit", "Delete") and b.isVisibleTo(dlg)]


def test_double_click_opens_detail_not_irecord(dash):
    _double_click(dash, "grid", 1)                       # record 1 has iRecord ID 101
    assert dash.opened == [] and len(dash.dialogs) == 1


def test_observation_row_wired_with_edit_delete(dash):
    _double_click(dash, "grid", 1)
    assert dash.wired == [dash.dialogs[0]]
    assert sorted(_edit_delete_visible(dash.dialogs[0])) == ["Delete", "Edit"]
    _double_click(dash, "grid", 2)                       # no iRecord ID: same dialog
    assert len(dash.wired) == 2


@pytest.mark.parametrize("key,rid", [("hidden", 3), ("hidden", 4), ("returned", 4)])
def test_hidden_and_returned_rows_view_only(dash, key, rid):
    _double_click(dash, key, rid)
    assert len(dash.dialogs) == 1 and dash.wired == []
    assert _edit_delete_visible(dash.dialogs[0]) == []


def test_scheme_and_contributed_rows_view_only(dash):
    for idx, table in ((1, "recording_scheme"), (2, "contributed_observations")):
        dash.cmb_source.setCurrentIndex(idx)
        assert dash.source() == table
        _double_click(dash, "grid")
        assert dash.dialogs and dash.wired == [] and dash.opened == []
        assert _edit_delete_visible(dash.dialogs[-1]) == []


class _FakeTab:
    """Stands in for the Observation tab: records_changed, and a reload counter."""
    def __init__(self):
        from PySide6.QtCore import QObject, Signal

        class _Sig(QObject):
            records_changed = Signal()
        self._q = _Sig()
        self.records_changed = self._q.records_changed
        self.loads = 0

    def _load_data(self):
        self.loads += 1


def test_looking_at_a_record_does_not_rebuild(dash, monkeypatch):
    import src.views.observations.observation_record_actions as ora
    monkeypatch.setattr(ora, "observation_tab_for", lambda w: _FakeTab())
    dash.show_problem("grid")
    before = dash.report()
    _double_click(dash, "grid", 1)
    assert dash.report() is before and dash.current_key() == "grid"


def test_a_change_in_the_dialog_rebuilds_on_the_same_tile(dash, monkeypatch):
    import src.views.observations.observation_record_actions as ora
    from src.views.dialogs import RecordDetailDialog
    tab = _FakeTab()
    monkeypatch.setattr(ora, "observation_tab_for", lambda w: tab)
    monkeypatch.setattr(RecordDetailDialog, "exec",
                        lambda self: dash.dialogs.append(self) or tab.records_changed.emit() or 0)
    dash.show_problem("grid")
    before = dash.report()
    _double_click(dash, "grid", 1)
    assert dash.report() is not before and dash.current_key() == "grid"


def test_failed_build_never_leaves_another_sources_rows_editable(dash, monkeypatch):
    """Review 13 Oct 2026: Contributed shown, switch to Observation, the build fails --
    the old rows must not open an observation with Edit / Delete."""
    import src.views.stats.cleaning_dashboard as cd
    dash.cmb_source.setCurrentIndex(2)                       # Contributed
    assert dash._models["grid"].rowCount() == 1
    dash.mark_stale()
    monkeypatch.setattr(cd, "build_report", lambda *a, **k: (_ for _ in ()).throw(OSError("x")))
    dash.cmb_source.setCurrentIndex(0)                       # Observation, build fails
    assert dash._shown_source is None
    assert all(m.rowCount() == 0 for m in dash._models.values())
    from src.services.cleaning_report import CleaningRow
    ghost = CleaningRow(record_id=1, species="", rank="", date="", grid_ref="", site="",
                        recorder="", irecord_id=None, problem="grid", detail="", dataset="")
    assert dash.detail_dialog(ghost) is None and dash.wired == []


def test_hidden_record_never_makes_a_live_one_a_synonym(tmp_path):
    """Review 13 Oct 2026: a hidden record under another name for the same TVK."""
    from src.services.cleaning_report import build_report
    main, uksi = make_dbs(tmp_path)
    c = sqlite3.connect(main)
    c.execute("UPDATE observations SET species_name = 'Clytus arietus' WHERE id = 3")
    c.commit()
    c.close()
    rep = build_report(main, uksi, "observations")
    assert rep.rows["synonym"] == [] and rep.records_with_problem == 2


# ------------------------------------------------------------------ (e) Show again

def test_show_again_on_hidden_tile_stays_there(dash, monkeypatch):
    import src.views.observations.observation_record_actions as ora
    tab = _FakeTab()
    monkeypatch.setattr(ora, "observation_tab_for", lambda w: tab)
    dash.show_problem("hidden")
    assert dash._tiles["hidden"].text().endswith("\n2")
    assert dash.btn_show_again.isVisibleTo(dash) and not dash.btn_show_again.isEnabled()
    view = dash.current_view()
    view.setCurrentIndex(view.model().index(0, 0))        # record 3, hidden and not returned
    assert dash.btn_show_again.isEnabled()
    dash.show_selected_again()
    assert dash.current_key() == "hidden"
    assert dash._tiles["hidden"].text().endswith("\n1")
    assert tab.loads == 1                                  # the Observation tab reloaded
    c = sqlite3.connect(dash.main_path)
    try:
        assert c.execute("SELECT hidden_at FROM observations WHERE id = 3").fetchone()[0] is None
        assert c.execute("SELECT hidden_at FROM observations WHERE id = 4").fetchone()[0] is not None
    finally:
        c.close()


def test_show_again_on_returned_tile_stays_there(dash):
    dash.show_problem("returned")
    assert dash.btn_show_again.isVisibleTo(dash)
    view = dash.current_view()
    view.setCurrentIndex(view.model().index(0, 0))
    dash.show_selected_again()
    assert dash.current_key() == "returned" and dash._tiles["returned"].text().endswith("\n0")
