"""Tier 2 review fixes, 10 Oct 2026 -- Observatum (OBS-04/05/10/13/16/17/19/20/21/24) and
Data Entry (DE3/DE6/DE9). Offscreen; small throwaway databases built from the real schema,
and the data copies opened read-only where a figure is checked against them."""
import csv
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import paths  # noqa: E402

HAVE_DATA = os.path.exists(str(paths.OBSERVATUM_DB))
needs_data = pytest.mark.skipif(not HAVE_DATA, reason="data/observatum.db not present")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _ro(path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def _schema_db(path, tables=("observations", "recording_scheme", "specimens")):
    """An empty database with the real tables' schema (from the data copy, read-only)."""
    src = _ro(paths.OBSERVATUM_DB)
    dst = sqlite3.connect(path)
    for t in tables:
        sql = src.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                          (t,)).fetchone()[0]
        dst.execute(sql)
    dst.commit()
    src.close()
    return dst


def _insert(conn, table, **row):
    cols = ", ".join(row)
    conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({', '.join('?' * len(row))})",
                 tuple(row.values()))
    conn.commit()


@pytest.fixture
def temp_db(tmp_path, monkeypatch, qapp):
    """A throwaway observatum.db as the app's database (singleton paths restored after)."""
    if not HAVE_DATA:
        pytest.skip("needs the real schema from data/observatum.db")
    path = tmp_path / "observatum.db"
    _schema_db(path).close()
    from src.models.database import get_database
    db = get_database()
    old = (db._main_db_path, db._uksi_db_path)
    db.set_main_path(str(path))
    db.set_uksi_path(str(paths.UKSI_DB))
    monkeypatch.setattr(paths, "OBSERVATUM_DB", path)
    from shared import backup_service as bs
    monkeypatch.setattr(bs, "BACKUP_ROOT", str(tmp_path / "backups"))
    yield db, path
    db._main_db_path, db._uksi_db_path = old


# ── OBS-05 gamification ─────────────────────────────────────────────────────

@needs_data
def test_gamification_vcs_and_medals_are_counted(qapp):
    from src.features.gamification.calculator import GamificationCalculator
    c = GamificationCalculator()
    conn = _ro(paths.OBSERVATUM_DB)
    want = {r[0] for r in conn.execute(
        "SELECT DISTINCT vc_number FROM observations WHERE vc_number BETWEEN 1 AND 112")}
    conn.close()
    assert set(c.get_observed_vcs()) == want and want          # was 0 (vice_county_number)
    badges = c.calculate_vice_county_badges()
    assert len(badges) == 112 and sum(b["earned"] for b in badges) == len(want)
    cov = c.get_vice_county_coverage()
    assert {k: v["total"] for k, v in cov["regions"].items()} == \
        {"england": 59, "wales": 12, "scotland": 41}
    assert len(c.get_family_achievements()["medals"]) > 0      # was 0 (taxon_rank)


# ── OBS-13 New Collections List ─────────────────────────────────────────────

@needs_data
def test_new_collections_list_has_every_species(qapp):
    from src.repositories import SpecimenRepository
    rows = SpecimenRepository(str(paths.OBSERVATUM_DB)).get_new_species_first_specimens(limit=None)
    conn = _ro(paths.OBSERVATUM_DB)
    n = conn.execute("SELECT COUNT(DISTINCT species_name) FROM specimens "
                     "WHERE species_name IS NOT NULL AND species_name != ''").fetchone()[0]
    conn.close()
    assert len(rows) == n > 1000 and "_first" not in rows[0]


def test_first_specimen_is_earliest_dated_and_undated_species_kept(temp_db):
    db, path = temp_db
    conn = sqlite3.connect(path)
    _insert(conn, "specimens", id=1, species_name="Rhagium mordax", date_collected="2021-06-01")
    _insert(conn, "specimens", id=2, species_name="Rhagium mordax", date_collected="")
    _insert(conn, "specimens", id=3, species_name="Rhagium mordax", date_collected="2019-05-01")
    _insert(conn, "specimens", id=4, species_name="Leptura aurulenta", date_collected="")
    conn.close()
    from src.repositories import SpecimenRepository
    rows = {r["species_name"]: r["id"] for r in
            SpecimenRepository(str(path)).get_new_species_first_specimens(limit=None)}
    assert rows == {"Rhagium mordax": 3, "Leptura aurulenta": 4}


# ── OBS-21 County Firsts ────────────────────────────────────────────────────

def test_county_firsts_ignore_undated_records(temp_db):
    db, path = temp_db
    conn = sqlite3.connect(path)
    for i, (tvk, name, date) in enumerate([
            ("T1", "Rhagium mordax", ""), ("T1", "Rhagium mordax", "2020-05-01"),
            ("T1", "Rhagium mordax", "2022-06-01"), ("T2", "Leptura aurulenta", "")], 1):
        _insert(conn, "recording_scheme", id=i, species_tvk=tvk, species_name=name, date=date,
                vc_number=23, family="Cerambycidae")
    conn.close()
    from src.services.recording_scheme_stats_service import get_recording_scheme_stats
    s = get_recording_scheme_stats()
    s.initialize(db)
    s.invalidate()
    try:
        firsts = {f["species"]: f["date"] for f in s.get("county_firsts")}
        vc = s.get_vc_details(23) if hasattr(s, "get_vc_details") else None
    finally:
        s.invalidate()
    assert firsts == {"Rhagium mordax": "2020-05-01"}           # '' was the "first" before
    if vc and vc.get("species_list"):
        first = {r["species_name"]: r["first_date"] for r in vc["species_list"]}
        assert first["Rhagium mordax"] == "2020-05-01" and first["Leptura aurulenta"] == ""


# ── OBS-24 New Species List by record type ──────────────────────────────────

def test_new_species_list_follows_personal_commercial(temp_db):
    db, path = temp_db
    conn = sqlite3.connect(path)
    _insert(conn, "observations", id=1, species_tvk="A", species_name="Abax parallelus",
            date="2020-06-01", record_type="Personal")
    _insert(conn, "observations", id=2, species_tvk="A", species_name="Abax parallelus",
            date="2019-06-01", record_type="Commercial")
    _insert(conn, "observations", id=3, species_tvk="B", species_name="Bembidion lampros",
            date="2021-06-01", record_type="Commercial")
    conn.close()
    from src.repositories.observation_repository import ObservationRepository
    r = ObservationRepository(db)

    def got(rt):
        return {x["species_tvk"]: x["date"] for x in r.get_new_species_first_records(100, rt)}
    assert got("Personal") == {"A": "2020-06-01"}
    assert got("Commercial") == {"A": "2019-06-01", "B": "2021-06-01"}
    assert got(None) == {"A": "2019-06-01", "B": "2021-06-01"}


# ── OBS-19 Year-by-Year exports ─────────────────────────────────────────────

def test_year_exports_write_table_and_that_years_records(temp_db, tmp_path, monkeypatch):
    db, path = temp_db
    conn = sqlite3.connect(path)
    _insert(conn, "observations", id=1, species_tvk="A", species_name="Abax parallelus",
            date="2024-06-01", record_type="Personal", site_name="Wytham")
    _insert(conn, "observations", id=2, species_tvk="B", species_name="Bembidion lampros",
            date="2024-07-01", record_type="Commercial")
    _insert(conn, "observations", id=3, species_tvk="A", species_name="Abax parallelus",
            date="2023-06-01", record_type="Personal")
    conn.close()
    from PySide6.QtWidgets import QFileDialog, QMessageBox
    from src.views.stats import year_export as ye
    from src.views.stats.stat_widgets import YearByYearTable
    table = YearByYearTable()
    table.set_data({2024: {"species": 1, "records": 1, "newSpecies": 0},
                    2023: {"species": 1, "records": 1, "newSpecies": 1}})
    ye.wire_year_exports(table, "Personal", "Personal", None)
    out = {"p": ""}
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (out["p"], "")))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    out["p"] = str(tmp_path / "all.csv")
    table.export_all_clicked.emit()
    with open(out["p"], encoding="utf-8-sig") as f:
        assert list(csv.reader(f)) == [["Year", "Species", "Records", "New"],
                                       ["2024", "1", "1", "0"], ["2023", "1", "1", "1"]]
    out["p"] = str(tmp_path / "y2024.csv")
    table.export_year_clicked.emit("2024")
    with open(out["p"], encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert [(r["Species"], r["Site"], r["Record Type"]) for r in rows] == \
        [("Abax parallelus", "Wytham", "Personal")]              # not the commercial one


# ── OBS-17 profile button ───────────────────────────────────────────────────

def test_specimen_dialog_profile_button_opens_account(qapp, monkeypatch):
    import src.views.home.species_profile_dialog as spd
    opened = []
    monkeypatch.setattr(spd.SpeciesProfileDialog, "exec",
                        lambda self: opened.append((self._species_name, self._tvk)) or 0)
    from src.views.dialogs.add_specimen_dialog import AddSpecimenDialog
    d = AddSpecimenDialog(None, None, None, existing_specimen={
        "id": 1, "species_name": "Rhagium mordax", "species_tvk": "NBNSYS0000010506"})
    d.profile_link.click()
    assert opened == [("Rhagium mordax", "NBNSYS0000010506")]


# ── OBS-04 Edit / Delete that did nothing ───────────────────────────────────

def _scheme_row(path):
    conn = sqlite3.connect(path)
    _insert(conn, "recording_scheme", id=7, species_name="Rhagium mordax", species_tvk="T1",
            date="2020-05-01", grid_ref="SP5822", vc_number=23, vice_county="Oxfordshire",
            comment="keep me", site_name="Bicester")
    conn.close()


def _scheme_ids(path):
    conn = _ro(path)
    try:
        return [r[0] for r in conn.execute("SELECT id FROM recording_scheme")]
    finally:
        conn.close()


def test_scheme_detail_delete_backs_up_then_deletes(temp_db, tmp_path, monkeypatch):
    db, path = temp_db
    _scheme_row(path)
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    from src.views.dialogs import SchemeRecordDetailDialog
    from src.views.scheme.recording_scheme_tab import RecordingSchemeTab
    tab = RecordingSchemeTab()
    changed = []
    tab.records_changed.connect(lambda: changed.append(1))
    monkeypatch.setattr(tab, "refresh", lambda: None)
    dlg = SchemeRecordDetailDialog({"id": 7, "species": "Rhagium mordax",
                                    "species_name": "Rhagium mordax"}, parent=tab)
    tab._wire_edit_delete(dlg)
    dlg._on_delete()                                      # confirms, then emits
    assert _scheme_ids(path) == [] and changed == [1]
    kept = os.listdir(tmp_path / "backups" / "kept")
    assert len(kept) == 1 and "pre-delete" in kept[0]


def test_scheme_delete_refused_when_backup_fails(temp_db, monkeypatch):
    db, path = temp_db
    _scheme_row(path)
    import shared.backup_service as bs
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(bs, "backup_main_only", lambda label="": False)
    said = []
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: said.append(a[2])))
    from src.views.scheme.scheme_record_actions import delete_scheme_record
    assert delete_scheme_record(None, {"id": 7}, db) is False
    assert _scheme_ids(path) == [7] and "nothing has been deleted" in said[0]


def test_scheme_edit_writes_and_rederives_vc(temp_db, monkeypatch):
    db, path = temp_db
    _scheme_row(path)
    import src.views.scheme.scheme_record_actions as sra
    from src.views.dialogs.edit_observation_dialog import EditObservationDialog

    class _VC:
        def assess(self, ref):
            return {"vc_number": 16, "vc_name": "West Kent", "note": ""}
    monkeypatch.setattr(sra, "_vc_service", lambda: _VC())
    seen = {}

    def fake_exec(self):
        seen["record"] = self._observation
        seen["require"] = self._require_date_and_grid
        self.gridref_edit.setText("TQ5070")
        self.site_edit.setText("Darenth")
        return True
    monkeypatch.setattr(EditObservationDialog, "exec", fake_exec)
    assert sra.edit_scheme_record(None, {"id": 7, "species_name": "Rhagium mordax"}, db)
    assert seen["require"] is False and seen["record"]["comment"] == "keep me"   # full row read
    conn = _ro(path)
    row = conn.execute("SELECT grid_ref, vc_number, vice_county, site_name, comment, latitude "
                       "FROM recording_scheme WHERE id=7").fetchone()
    conn.close()
    assert row[:5] == ("TQ5070", 16, "West Kent", "Darenth", "keep me") and 51 < row[5] < 52


def test_specimen_detail_delete_backs_up(qapp, tmp_path, monkeypatch):
    import shared.backup_service as bs
    from src.views.collection.insect_collection_tab import InsectCollectionTab
    calls = []
    monkeypatch.setattr(bs, "backup_main_only", lambda label="": calls.append(label) or True)
    tab = InsectCollectionTab()

    class _Repo:
        deleted = []

        def delete(self, i):
            self.deleted.append(i)
    tab._specimen_repo = _Repo()
    monkeypatch.setattr(tab, "_load_data", lambda *a, **k: None)
    tab._on_detail_delete_requested({"id": 5, "species_name": "Rhagium mordax"})
    assert calls == ["pre-delete"] and _Repo.deleted == [5]
    monkeypatch.setattr(bs, "backup_main_only", lambda label="": False)
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: None))
    tab._on_detail_delete_requested({"id": 6})
    assert _Repo.deleted == [5]                                # refused without a backup


# ── OBS-10 stale figures ────────────────────────────────────────────────────

def test_mark_stale_clears_dashboard_guards(qapp):
    from src.views.stats.stats_reports_tab import StatsReportsTab
    st = StatsReportsTab()
    for d in (st.personal_dashboard, st.commercial_stats_dashboard, st.all_stats_dashboard):
        d._dashboard_refreshed = True
    st.mark_stale()
    assert not any(d._dashboard_refreshed for d in
                   (st.personal_dashboard, st.commercial_stats_dashboard, st.all_stats_dashboard))


def test_data_change_refreshes_home_and_stats(qapp):
    from types import SimpleNamespace
    from src.views.main_window import MainWindow
    hits = []
    fake = SimpleNamespace(stats_reports_tab=SimpleNamespace(mark_stale=lambda: hits.append("stats")),
                           home_tab=SimpleNamespace(refresh_data=lambda: hits.append("home")))
    MainWindow._mark_data_changed(fake)
    assert fake._data_changed and hits == ["stats", "home"]


def test_tabs_announce_record_changes(qapp):
    from src.views.observations.observation_tab import ObservationTab
    from src.views.scheme.recording_scheme_tab import RecordingSchemeTab
    from src.views.stats.scheme_dashboard import SchemeDashboard
    assert hasattr(ObservationTab, "records_changed")
    assert hasattr(RecordingSchemeTab, "records_changed")
    assert hasattr(SchemeDashboard, "scheme_records_changed")


# ── OBS-16 Quick Entry ──────────────────────────────────────────────────────

def test_quick_entry_commercial_needs_project_and_certainty_has_its_column(temp_db, monkeypatch):
    db, path = temp_db
    conn = sqlite3.connect(path)
    _insert(conn, "observations", id=1, species_tvk="X", species_name="Abax parallelus",
            date="2024-06-01", record_type="Commercial", project_name="Hook Farm", client="BAM",
            embargo_status="Active", embargo_until="2030-01-01")
    conn.close()
    from PySide6.QtWidgets import QMessageBox
    errs = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: errs.append(a[2])))
    import src.views.home.quick_entry as qe
    monkeypatch.setattr(qe, "get_vc_service", lambda: type("V", (), {
        "get_vice_county": lambda self, g: {"name": "Oxfordshire", "number": 23}})())
    f = qe.QuickEntryForm()
    f.set_species({"scientific_name": "Rhagium mordax", "tvk": "NBNSYS0000010506",
                   "common_name": "", "order": "Coleoptera", "family": "Cerambycidae"})
    f.grid_ref_edit.setText("SP4537")
    f.location_edit.setText("Hook Farm")
    f.recorder_edit.setText("Heeney, W.J.")
    f.determiner_edit.setText("Heeney, W.J.")
    f.certainty_combo.setCurrentText("Likely")
    f.comment_edit.setText("under bark")
    f.record_type_combo.setCurrentText("Commercial")
    assert f.project_combo.isEnabled() and f.project_combo.count() == 2
    f._on_save_clicked()
    assert errs and "needs its project" in errs[0]
    f.project_combo.setCurrentIndex(1)
    f._on_save_clicked()
    conn = _ro(path)
    row = conn.execute("SELECT record_type, project_name, client, embargo_status, embargo_until, "
                       "recorder_certainty, comment FROM observations WHERE id != 1").fetchone()
    conn.close()
    assert row == ("Commercial", "Hook Farm", "BAM", "Active", "2030-01-01", "Likely", "under bark")
    f.record_type_combo.setCurrentText("Personal")
    assert not f.project_combo.isEnabled()


# ── OBS-20 theme handler ────────────────────────────────────────────────────

def test_theme_handler_no_longer_calls_a_missing_method(qapp):
    from src.themes import theme
    assert theme().set_theme("Naturalist") is False
    from src.views.settings.general_panel import GeneralSettingsPanel
    p = GeneralSettingsPanel()
    p._loading = False
    p._on_theme_changed("Naturalist")                      # AttributeError before


# ── Data Entry ──────────────────────────────────────────────────────────────

@pytest.fixture
def staging(tmp_path, qapp):
    from DataEntry import staging_repo as repo
    conn = sqlite3.connect(tmp_path / "s.db")
    conn.row_factory = sqlite3.Row
    repo.ensure_schema(conn)
    pid = repo.ensure_personal_job(conn)
    return conn, pid


def test_de3_sort_then_repeat_or_insert_keeps_entry_order(staging):
    from DataEntry import staging_repo as repo
    from DataEntry.entry_grid import COLIDX, StagingTableModel
    conn, pid = staging
    for n in ("Cychrus caraboides", "Abax parallelepipedus", "Bembidion lampros"):
        repo.insert_row(conn, pid, {"species_name": n})
    m = StagingTableModel(conn, pid, None)
    m.sort_rows(COLIDX["species_name"])
    assert [r["species_name"] for r in m._rows][:3] == \
        ["Abax parallelepipedus", "Bembidion lampros", "Cychrus caraboides"]
    m.repeat_row(0)                         # Abax again, just after Abax
    m.insert_rows(3, 1)                     # below Bembidion in the sorted view
    m.restore_entry_order()
    assert [r["species_name"] for r in m._rows] == [
        "Cychrus caraboides", "Abax parallelepipedus", "Abax parallelepipedus",
        "Bembidion lampros", None]          # before: Abax, Abax, Bembidion, blank, Cychrus


def test_de3_unsorted_insert_is_unchanged(staging):
    from DataEntry import staging_repo as repo
    from DataEntry.entry_grid import StagingTableModel
    conn, pid = staging
    for n in ("A a", "B b", "C c"):
        repo.insert_row(conn, pid, {"species_name": n})
    m = StagingTableModel(conn, pid, None)
    m.insert_rows(1, 1)
    m.insert_rows(0, 1)
    m.restore_entry_order()
    assert [r["species_name"] for r in m._rows] == [None, "A a", None, "B b", "C c"]


@pytest.mark.parametrize("typed, stored, flagged", [
    ("c.20", "c.20", True), ("0", 0, True), ("2x", "2x", True), ("1.5", 1.5, True),
    ("3", 3, False), ("3.0", 3, False), ("", None, False)])
def test_de9_mistyped_number_is_kept_and_flagged(staging, typed, stored, flagged):
    from PySide6.QtCore import Qt
    from DataEntry import staging_repo as repo
    from DataEntry.entry_grid import COLIDX, StagingTableModel
    conn, pid = staging
    repo.insert_row(conn, pid, {"species_name": "Abax parallelus", "date": "2026-06-01"})
    m = StagingTableModel(conn, pid, None)
    i = m.index(0, COLIDX["quantity"])
    m.setData(i, typed, Qt.ItemDataRole.EditRole)
    assert conn.execute("SELECT quantity FROM entry_staging").fetchone()[0] == stored
    assert (m.data(i, Qt.ItemDataRole.BackgroundRole) is not None) is flagged


def test_de9_unreadable_number_stays_in_staging(staging):
    from DataEntry import irecord_export as ie
    from DataEntry import staging_repo as repo
    from DataEntry.commit_service import _eligibility, build_kwargs_from_row, precommit_issues, read_qty
    conn, pid = staging
    repo.insert_row(conn, pid, {"species_name": "Abax parallelus", "date": "2026-06-01",
                                "quantity": "c.20"})
    repo.insert_row(conn, pid, {"species_name": "Abax parallelus", "date": "2026-06-02",
                                "quantity": 4})
    rows = repo.fetch_rows(conn, pid)
    assert [_eligibility(r) for r in rows] == ["bad_qty", None]
    assert precommit_issues(rows)["unreadable No."] == [1]
    assert ie.blocking_rows(rows) == [1]
    assert build_kwargs_from_row(rows[1], {"mode": "Personal"})["quantity"] == 4
    assert read_qty(None) == 1 and read_qty(" 7 ") == 7 and read_qty("-2") is None


@pytest.mark.skipif(not os.path.exists(str(paths.CODEX_DB)), reason="codex.db not present")
def test_de6_conservation_chips_follow_the_records_country(qapp):
    from DataEntry.info_panel import InfoService
    s = InfoService(sqlite3.connect(":memory:"), str(paths.CODEX_DB))
    skylark = "NHMSYS0000530139"        # NI Priority, S.41 England and SBL; NI row comes first
    labels = lambda vc: [lab for lab, k in s.conservation_chips(skylark, vc) if k == "priority"]  # noqa: E731
    if not labels(23):
        pytest.skip("skylark statuses not in this codex.db")
    assert labels(23) == ["Priority (NERC S.41 England)"]          # Oxfordshire
    assert labels(90) == ["Priority (Scottish Biodiversity List)"]
    assert labels(None) == ["Priority (NERC S.41 England)"]        # no VC: Examen's default
    assert not any("NI" in x for vc in (23, 49, 90) for x in labels(vc))
    assert s.jurisdiction_for_vc(35) == "Wales" and s.jurisdiction_for_vc("x") == "England"


# ── Tier 4 ──────────────────────────────────────────────────────────────────

def test_obs27_counts_are_singular_for_one(qapp):
    from src.utils.text import counted
    assert counted(1, "record") == "1 record" and counted(24962, "record") == "24,962 records"
    assert counted(1, "species", "species") == "1 species"


def test_de12_standalone_never_falls_back_to_the_live_db(monkeypatch):
    import DataEntry.__main__ as m
    from DataEntry import bootstrap
    monkeypatch.setattr(bootstrap, "newest_dev_db", lambda d: None)
    assert m._resolve_main_db(None)[0] is None and m.main([]) == 2
    assert m._resolve_main_db("x.db")[0] == "x.db"
