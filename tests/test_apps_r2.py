"""Round 2 (10 Oct evening): Settings (decision 11), Filter Wizard dataset / provider
(decision 4), Recording Scheme read-only (L15), Home Quick Stats cards (L16), Munia
multi-year split (decision 12 / MUN-4), Examen "1 sp." (L25), Curator genus-only rows
(L26), Atrium single instance (L28).

Offscreen; the real data copies (data/*.db) are read only, and those tests are skipped
when the copies are absent. Munia uses an in-memory database.
"""
import os
import sqlite3
import uuid
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import paths  # noqa: E402

HAVE_DATA = all(p.exists() for p in (paths.OBSERVATUM_DB, paths.UKSI_DB))
needs_data = pytest.mark.skipif(not HAVE_DATA, reason="real data copies not present")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def real_db(qapp):
    """The app's database pointed at the data copies (read by the code under test)."""
    from src.models.database import get_database
    db = get_database()
    old = (db._main_db_path, db._uksi_db_path)
    db.set_main_path(str(paths.OBSERVATUM_DB))
    db.set_uksi_path(str(paths.UKSI_DB))
    yield db
    db._main_db_path, db._uksi_db_path = old


def _ro():
    return sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)


# ── Decision 11: Settings ──────────────────────────────────────────────────────

def test_database_panel_has_no_change_buttons(qapp):
    from PySide6.QtWidgets import QPushButton
    from src.views.settings.database_panel import DatabaseSettingsPanel
    panel = DatabaseSettingsPanel()
    texts = {b.text() for b in panel.findChildren(QPushButton)}
    assert "Change" not in texts and "Update" not in texts
    assert {"Backup Database", "Restore from Backup", "Manage Species Aliases"} <= texts
    assert not hasattr(panel, "_change_main_db") and not hasattr(panel, "_update_uksi_db")
    assert not hasattr(DatabaseSettingsPanel, "database_changed")


def test_settings_tab_and_main_window_drop_database_changed(qapp):
    from src.views.main_window import MainWindow
    from src.views.settings.settings_tab import SettingsTab
    assert not hasattr(SettingsTab, "database_changed")
    assert not hasattr(MainWindow, "_on_database_changed")


def test_unread_settings_are_hidden_not_deleted(qapp):
    from src.views.settings.general_panel import GeneralSettingsPanel
    g = GeneralSettingsPanel()
    # hidden: saved but nothing reads them
    assert g.theme_group.isHidden() and g.auto_vc.isHidden() and g.record_books_group.isHidden()
    # still there (kept), and the ones that are read stay visible
    assert g.record_books_path is not None and g.theme_combo is not None
    for w in (g.default_recorder, g.date_format, g.cn_home,
              g.filters_observations, g.csv_backup_enabled, g.scheme_families_input):
        assert not w.isHidden()
    # the old single switch is superseded by Settings > Species counting (backlog A): hidden
    assert g.exclude_incomplete.isHidden()


# ── Decision 4: Filter Wizard dataset / provider ───────────────────────────────

def test_dataset_key_builds_sql_for_scheme_only():
    from src.services.filter_builder import KEY_TO_CARD, build_where, unsupported_keys
    assert KEY_TO_CARD["dataset"] == "status"
    sql, params = build_where("recording_scheme", {"dataset": ["NBN Atlas", "Cerambycidae Dataset"],
                                                   "verification_status": ["Accepted"]})
    assert "source = ? COLLATE NOCASE" in sql and " AND " in sql
    assert params[-2:] == ["NBN Atlas", "Cerambycidae Dataset"]
    assert build_where("observations", {"dataset": ["x"]}) == ("", [])
    assert unsupported_keys("observations", {"dataset": ["x"]}) == ["dataset"]


def test_dataset_counts_sorted_by_name():
    from src.services.filter_builder import dataset_counts
    assert dataset_counts([("b", 2), ("A", 5), (None, 3), ("  ", 1), ("a2", 1)]) == \
        [("A", 5), ("a2", 1), ("b", 2)]


@needs_data
def test_dataset_values_and_matches_on_real_data():
    from src.services.filter_builder import matching_ids, tab_values
    v = tab_values(paths.OBSERVATUM_DB, "recording_scheme", only=("datasets",))["datasets"]
    conn = _ro()
    try:
        expected = conn.execute("SELECT COUNT(DISTINCT source), COUNT(*) FROM recording_scheme "
                                "WHERE TRIM(COALESCE(source, '')) <> ''").fetchone()
        nbn = conn.execute("SELECT COUNT(*) FROM recording_scheme WHERE source = 'NBN Atlas'").fetchone()[0]
    finally:
        conn.close()
    assert len(v) == expected[0] and sum(n for _, n in v) == expected[1]
    assert [d for d, _ in v] == sorted((d for d, _ in v), key=lambda d: (d.casefold(), d))
    ids = matching_ids(paths.OBSERVATUM_DB, "recording_scheme", {"dataset": ["NBN Atlas"]})
    assert len(ids) == nbn


@needs_data
def test_status_dialog_dataset_picker_round_trip(qapp):
    from PySide6.QtCore import Qt
    from src.views.components.filter_wizard.filter_wizard import FilterWizard
    from src.views.components.filter_wizard.status_filter_dialog import StatusFilterDialog
    w = FilterWizard(tab_name="recording_scheme")
    w.set_db_path(paths.OBSERVATUM_DB)
    w._ensure_tab_values()
    assert w._dataset_list and "dataset" in w.card_grid.get_card("status").desc_label.text()
    d = StatusFilterDialog(current_values={"dataset": ["nbn atlas"]}, status_list=w._status_list,
                           type_list=w._record_type_list, dataset_list=w._dataset_list)
    assert d.dataset_picker.selected() == ["NBN Atlas"]           # case ignored on load
    d.dataset_picker.search.setText("longhorn trial")
    shown = [d.dataset_picker.list.item(i) for i in range(d.dataset_picker.list.count())
             if not d.dataset_picker.list.item(i).isHidden()]
    names = [i.data(Qt.ItemDataRole.UserRole) for i in shown]
    assert "NBN Atlas" in names                                    # ticked rows stay visible
    assert all("longhorn trial" in n.casefold() for n in names if n != "NBN Atlas")
    assert all(i.text().endswith(")") for i in shown)              # "<dataset> (n)"
    d._clear_all()
    assert d.get_values() == {}
    # the observations wizard offers no dataset section
    o = FilterWizard(tab_name="observations")
    o.set_db_path(paths.OBSERVATUM_DB)
    o._ensure_tab_values()
    assert o._dataset_list == []
    assert StatusFilterDialog(status_list=["Accepted"], type_list=[], dataset_list=[]).dataset_picker is None


# ── L15: Recording Scheme read-only ─────────────────────────────────────────────

def test_scheme_detail_dialog_is_view_only(qapp):
    from PySide6.QtWidgets import QPushButton
    from src.views.dialogs import SchemeRecordDetailDialog
    dlg = SchemeRecordDetailDialog({"id": 7, "species": "Rhagium mordax",
                                    "species_name": "Rhagium mordax"})
    texts = {b.text() for b in dlg.findChildren(QPushButton)}
    assert "Edit" not in texts and "Delete" not in texts and "Close" in texts
    assert not hasattr(dlg, "edit_requested") and not hasattr(dlg, "delete_requested")


def test_scheme_record_actions_retired():
    import importlib.util
    assert importlib.util.find_spec("src.views.scheme.scheme_record_actions") is None
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assert os.path.exists(os.path.join(root, "_archive", "scheme_record_actions_20261010",
                                       "scheme_record_actions.py"))


# ── L16: Home Quick Stats cards ─────────────────────────────────────────────────

def test_home_left_column_order(qapp):
    from src.features.gamification import GamificationLauncher
    from src.views.home.home_tab import HomeTab
    from src.views.home.observation_stats_card import ObservationStatsCard
    from src.views.home.quick_stats import QuickStatsPanel
    h = HomeTab()
    lay = h.personal_stats.parentWidget().layout()   # the left column (in a scroll area since R4)
    widgets = [lay.itemAt(i).widget() for i in range(lay.count()) if lay.itemAt(i).widget()]
    assert [type(w) for w in widgets] == [ObservationStatsCard, ObservationStatsCard,
                                         QuickStatsPanel, GamificationLauncher]
    assert [w.record_type for w in widgets[:2]] == ["Personal", "Commercial"]


@needs_data
def test_home_cards_split_by_record_type(real_db):
    from src.repositories import ObservationRepository
    from src.views.home.home_tab import HomeTab
    repo = ObservationRepository()
    allq = repo.get_quick_stats()
    per, com = repo.get_quick_stats("Personal"), repo.get_quick_stats("Commercial")
    for k in ("total_records", "this_year_records", "last_month_records"):
        assert per[k] + com[k] == allq[k], k
    conn = _ro()
    try:
        # Home follows the species-counting switches (OBS-18): Personal rows less the excluded
        import shared.species_counting as sc
        n_per = conn.execute("SELECT COUNT(*) FROM observations WHERE record_type='Personal'"
                             + sc.not_excluded_sql(paths.OBSERVATUM_DB, "observations")).fetchone()[0]
    finally:
        conn.close()
    assert per["total_records"] == n_per
    assert per["total_species"] == repo.count_unique_species(record_type="Personal")
    h = HomeTab()
    h.initialize()
    assert h.personal_stats.value("total_records") == f"{per['total_records']:,}"
    assert h.commercial_stats.value("total_species") == f"{com['total_species']:,}"
    assert h.commercial_stats.value("last_month_records") == f"{com['last_month_records']:,}"


# ── Decision 12 / MUN-4: Munia multi-year projects ────────────────────────────────

@pytest.fixture
def munia():
    from Munia import munia_data as db
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.ensure_schema(conn)
    yield db, conn
    conn.close()


def test_munia_split_by_days_and_evenly(munia):
    db, conn = munia
    a = db.add_project(conn, {"start_year": 2025, "end_year": 2027, "project_name": "A",
                              "status": "accepted", "quote_value": 10000})
    db.add_project(conn, {"start_year": 2025, "end_year": 2027, "project_name": "B",
                          "status": "accepted", "quote_value": 9000})
    db.add_project(conn, {"start_year": 2026, "end_year": 2026, "project_name": "S",
                          "status": "accepted", "quote_value": 1000})
    db.set_project_field_months(conn, a, 2025, [{"month": 5, "field_days": 4}])
    db.set_project_annual_days(conn, a, 2026, {"micro_days": 4, "report_days": 2})
    got, confirmed = {}, {}
    for y in (2025, 2026, 2027):
        ps = db.apportion_projects(conn, db.get_projects_for_year(conn, y), y)
        got[y] = {p["project_name"]: (round(p["year_value"], 2), p["value_split"]) for p in ps}
        confirmed[y] = db.summarise_pipeline(ps)["confirmed"]
        assert all(p["quote_value"] in (10000, 9000, 1000) for p in ps)   # whole quote kept
    assert got[2025] == {"A": (4000.0, "days"), "B": (3000.0, "even")}
    assert got[2026] == {"A": (6000.0, "days"), "B": (3000.0, "even"), "S": (1000.0, "single")}
    assert got[2027] == {"A": (0.0, "days"), "B": (3000.0, "even")}
    assert sum(confirmed.values()) == 20000                      # each quote counted once
    s = db.summarise_pipeline(db.apportion_projects(conn, db.get_projects_for_year(conn, 2026), 2026))
    assert (s["multi_year_count"], s["multi_year_confirmed"], s["multi_year_even"]) == (2, 9000, 1)
    assert db.get_project_field_total(conn, a, 2025) == 4 and db.get_project_field_total(conn, a, 2026) == 0
    assert db.get_project_micro_total(conn, a) == 4


def test_munia_days_outside_span_ignored():
    from Munia.munia_data import year_share
    p = {"start_year": 2025, "end_year": 2026}
    assert year_share(p, 2025, {2024: 5, 2025: 1, 2026: 3}) == (0.25, "days")
    assert year_share(p, 2027, {2025: 1}) == (0.0, "days")
    assert year_share({"start_year": 2026, "end_year": 2026}, 2026, {}) == (1.0, "single")


def test_munia_projects_panel_shows_year_share(qapp, munia):
    db, conn = munia
    a = db.add_project(conn, {"start_year": 2025, "end_year": 2026, "project_name": "A",
                              "status": "accepted", "quote_value": 8000})
    db.set_project_field_months(conn, a, 2025, [{"month": 5, "field_days": 1}])
    db.set_project_field_months(conn, a, 2026, [{"month": 5, "field_days": 3}])
    from Munia.projects_panel import ProjectsPanel
    panel = ProjectsPanel(conn)
    panel.load(db.apportion_projects(conn, db.get_projects_for_year(conn, 2026), 2026), 2026)
    assert panel.table.item(0, 4).text() == "£6,000 of £8,000"
    assert panel.table.item(0, 5).text() == "3"                 # this year's field days


@needs_data
def test_munia_real_figures_unchanged():
    """No project in the data copy spans two years: confirmed stays £65,540.50."""
    from Munia import munia_data as db
    conn = sqlite3.connect(f"file:{paths.DATA_DIR / 'munia.db'}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        ps = db.get_projects_for_year(conn, 2026)
        assert db.summarise_pipeline(db.apportion_projects(conn, ps, 2026))["confirmed"] == \
            db.summarise_pipeline(ps)["confirmed"]
    finally:
        conn.close()


# ── L25: Examen "1 sp." ─────────────────────────────────────────────────────────

def test_examen_sp_pluralisation():
    from Examen.workbook_export import spp
    assert (spp(1), spp(0), spp(2), spp(19)) == ("sp.", "spp.", "spp.", "spp.")


def test_examen_compartment_sqi_cell_one_species():
    from types import SimpleNamespace as S
    from Examen.compartments import CompRow as CompartmentRow
    import dataclasses
    fields = {f.name: None for f in dataclasses.fields(CompartmentRow)}
    for n, want in ((1, "(1 sp)"), (3, "(3 spp)")):
        row = CompartmentRow(**{**fields, "sqi": S(species_with_sqs=n, reliable=False, sqi=0)})
        assert row.sqi_cells() == (n, want)


# ── L26: Curator genus-only rows ─────────────────────────────────────────────────

def test_curator_genus_only_row_adds_up():
    from Curator.planner_tree_data import TaxonNode, _add_genera_to_node, \
        _aggregate_specimen_counts, _set_species_counts
    fam = TaxonNode("Cerambycidae", "Family")
    _add_genera_to_node(fam, [("Leiopus", 10)], {"Leiopus": [("Leiopus nebulosus", 11)]}, {},
                        {"Leiopus nebulosus": 2}, {"Leiopus"}, {"Leiopus nebulosus"}, True,
                        gen_counts={"Leiopus": 1})
    _aggregate_specimen_counts(fam)
    _set_species_counts(fam)
    gen = fam.children[0]
    assert [(c.name, c.specimen_count, c.genus_only) for c in gen.children] == \
        [("Leiopus nebulosus", 2, False), ("Leiopus sp.", 1, True)]
    assert gen.specimen_count == 3 == sum(c.specimen_count for c in gen.children)
    assert (fam.specimen_count, fam.species_count, fam.my_species_count) == (3, 1, 1)


def test_curator_genus_with_only_genus_level_specimens_is_kept():
    from Curator.planner_tree_data import TaxonNode, _add_genera_to_node, _aggregate_specimen_counts
    fam = TaxonNode("F", "Family")
    _add_genera_to_node(fam, [("G", 1)], {"G": [("G a", 2)]}, {}, {}, {"G"}, set(), True,
                        gen_counts={"G": 4})
    _aggregate_specimen_counts(fam)
    assert [(c.name, c.specimen_count) for c in fam.children[0].children] == [("G sp.", 4)]
    assert fam.specimen_count == 4 and fam.my_species_count == 0


@needs_data
def test_curator_every_genus_adds_up_on_real_data():
    from Curator.planner_tree_data import load_taxonomic_tree
    root = load_taxonomic_tree("Coleoptera")
    bad, rows = [], []

    def walk(n):
        if n.rank == "Genus":
            if sum(c.specimen_count for c in n.children) != n.specimen_count:
                bad.append(n.name)
            rows.extend(c.name for c in n.children if c.genus_only)
        for c in n.children:
            walk(c)
    walk(root)
    assert bad == [] and "Leiopus sp." in rows


# ── L28: Atrium single instance ─────────────────────────────────────────────────

def test_atrium_second_copy_signals_first(qapp):
    """The second copy runs as its own program (as on the PC): it must reach the open copy,
    get its "ok", and report that a copy is open."""
    import subprocess
    import sys
    from PySide6.QtCore import QCoreApplication, QElapsedTimer
    from Atrium.single_instance import SingleInstance
    name = f"BiologicalSoftware.AtriumTest.{uuid.uuid4().hex[:8]}"
    first = SingleInstance(name)
    shown = []
    assert first.signal_running_copy(timeout_ms=100) is False     # nobody there yet
    assert first.listen(lambda: shown.append(1))
    root = str(Path(__file__).resolve().parents[1])
    code = ("import sys; sys.path.insert(0, r'%s'); "
            "from PySide6.QtCore import QCoreApplication; app = QCoreApplication([]); "
            "from Atrium.single_instance import SingleInstance; "
            "print('RESULT', SingleInstance(%r).signal_running_copy())" % (root, name))
    proc = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    try:
        t = QElapsedTimer()
        t.start()
        while proc.poll() is None and t.elapsed() < 15000:
            QCoreApplication.processEvents()       # the open copy answers while it waits
        out = proc.communicate(timeout=5)[0]
        assert "RESULT True" in out, out
        assert shown == [1]
    finally:
        if proc.poll() is None:
            proc.kill()
        first.close()


def test_atrium_bring_to_front_shows_panel(qapp, monkeypatch):
    from Atrium import atrium_ui
    calls = []
    fake = atrium_ui.AtriumApp.__new__(atrium_ui.AtriumApp)
    fake._show_panel = lambda: calls.append("show")
    fake._panel = type("P", (), {"raise_": lambda s: calls.append("raise"),
                                 "activateWindow": lambda s: calls.append("activate")})()
    atrium_ui.AtriumApp.bring_to_front(fake)
    assert calls == ["show", "raise", "activate"]


def test_atrium_channel_name_is_per_user():
    from Atrium.single_instance import channel_name
    n = channel_name()
    assert n.startswith("BiologicalSoftware.Atrium.") and " " not in n
