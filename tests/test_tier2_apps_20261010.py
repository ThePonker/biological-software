"""Tier 2 review findings, 10 Oct 2026: Examen (EXA11, 15, 17, 19), Codex Manager
(CDX-3), Curator (CUR-1, 2, 3), Munia (MUN-3, 4), Atrium (ATR-1, 2) and backups (INF4).

Small hand-built inputs and temporary databases; the few tests that read the real
data copies (data/*.db) do so read-only and are skipped when they are absent.
"""
import os
import sqlite3
import sys
from types import SimpleNamespace as S

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import paths  # noqa: E402

HAVE_DATA = all(p.exists() for p in (paths.OBSERVATUM_DB, paths.CODEX_DB,
                                     paths.PANTHEON_DB, paths.UKSI_DB))
needs_data = pytest.mark.skipif(not HAVE_DATA, reason="real data copies not present")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def boxes(monkeypatch):
    """QMessageBox / QFileDialog replaced by recorders."""
    from PySide6.QtWidgets import QMessageBox
    shown = []
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda *a, **k: shown.append(("warning",) + a[1:3])))
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: shown.append(("information",) + a[1:3])))
    return shown


def _sqi(label, n, sqi, species=None):
    return S(label=label, species_with_sqs=n, sqi=sqi, reliable=n >= 15,
             species_total=species or n)


# ============================================================ Examen ==========

def test_exa11_biotope_filter_lists_single_biotopes_and_finds_the_third(qapp):
    from Examen.species_tab import SpeciesTab, biotope_options
    result = S(key_species=[], biotopes_by_tvk={
        "T1": ["open habitats", "tree-associated", "wetland"],   # display shows two
        "T2": ["coastal", "wetland"],
        "T3": ["open habitats"]})
    detail = S(species_list=[
        S(name="Three biotopes", tvk="T1", status="", sqs=1, tier="",
          broad_biotope="open habitats, tree-associated", habitat=""),
        S(name="Coast", tvk="T2", status="", sqs=1, tier="",
          broad_biotope="coastal, wetland", habitat=""),
        S(name="Open", tvk="T3", status="", sqs=1, tier="",
          broad_biotope="open habitats", habitat="")])
    tab = SpeciesTab()
    tab.set_result(result, detail)
    options = [tab.biotope_filter.itemText(i) for i in range(tab.biotope_filter.count())]
    assert options == ["All", "coastal", "open habitats", "tree-associated", "wetland"]
    assert biotope_options(tab._all_species) == options[1:]
    tab.biotope_filter.setCurrentIndex(options.index("wetland"))
    shown = {tab.table.item(r, 0).text() for r in range(tab.table.rowCount())}
    assert shown == {"Three biotopes", "Coast"}
    tab.biotope_filter.setCurrentIndex(options.index("coastal"))
    assert tab.table.rowCount() == 1


def test_exa15_assemblage_and_habitat_tabs_show_the_workbook_cell(qapp):
    from PySide6.QtGui import QColor
    from Examen.assemblage_tab import AssemblageTab, AMBER
    from Examen.habitat_tab import HabitatTab
    from Examen.workbook_export import _sqi_cell, PTT_NEAR
    assert PTT_NEAR == 80
    result = S(sat_sqi=[_sqi("weak", 3, 200), _sqi("strong", 20, 160)],
               sat_counts={"weak": 3, "strong": 20}, stenotopic_count=23)
    tab = AssemblageTab()
    tab.set_result(result)
    cells = {tab.table.item(r, 0).text(): tab.table.item(r, 3).text()
             for r in range(tab.table.rowCount())}
    assert cells == {"weak": "(3 spp)", "strong": "160"}     # 200 withheld, as exported
    for s in result.sat_sqi:
        assert cells[s.label] == str(_sqi_cell(s))
        assert HabitatTab._sqi_text(s) == str(_sqi_cell(s))
    assert HabitatTab._sqi_text(_sqi("one", 1, 400)) == "(1 sp)"
    assert HabitatTab._sqi_text(None) == "-"

    # The amber band: 80% of the threshold, as the workbook (was 75% on the tab)
    import Examen.assemblage_tab as at
    sat = "rich flower resource"
    old = at._thresholds_cache
    at._thresholds_cache = {sat: {"threshold": 100}}
    try:
        for n, amber in ((78, False), (82, True)):
            t = AssemblageTab()
            t.set_result(S(sat_sqi=[], sat_counts={sat: n}))
            colour = t.table.item(0, 6).foreground().color()
            assert (colour == QColor(AMBER)) is amber, n
    finally:
        at._thresholds_cache = old


@needs_data
def test_exa15_every_sat_cell_matches_the_export_for_a_real_survey(qapp):
    from shared.repositories.codex_repository import AnalysisMode
    from Examen import examen_data as ed
    from Examen.assemblage_tab import AssemblageTab
    from Examen.workbook_export import _sqi_cell
    p = ed.load_all_projects(AnalysisMode.CODEX_FULL)[0]
    d = ed.load_project_detail(p.project_name, p.client, AnalysisMode.CODEX_FULL,
                               survey_year=p.survey_year or None)
    tab = AssemblageTab()
    tab.set_result(d.analysis)
    by = {s.label: s for s in d.analysis.sat_sqi}
    assert tab.table.rowCount() == len(d.analysis.sat_counts)
    for r in range(tab.table.rowCount()):
        name = tab.table.item(r, 0).text()
        if name in by:
            assert tab.table.item(r, 3).text() == str(_sqi_cell(by[name]))


@needs_data
def test_exa17_failed_load_or_analysis_disables_exports(qapp, monkeypatch):
    from Examen import examen_data as ed
    from Examen import site_analysis_view as sav
    view = sav.SiteAnalysisView(ed.analysis_service())
    view._on_project_clicked(0, 0)
    assert view.workbook_btn.isEnabled() and view._current_result is not None

    def boom(*a, **k):
        raise RuntimeError("pantheon.db is locked")
    monkeypatch.setattr(sav, "load_project_detail", boom)
    view._on_project_clicked(1, 0)
    assert view._current_result is None and view._current_detail is None
    assert not any(b.isEnabled() for b in (view.appendix_btn, view.workbook_btn,
                                           view.pdf_btn, view.word_btn))
    assert "pantheon.db is locked" in view.detail_header.text()

    # An analysis that fails inside the detail (Codex unreadable)
    monkeypatch.undo()
    view._on_project_clicked(0, 0)
    assert view.pdf_btn.isEnabled()
    from shared.services import pantheon_analysis_service as pas
    monkeypatch.setattr(pas.PantheonAnalysisService, "analyse",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("codex.db unreadable")))
    view._on_project_clicked(1, 0)
    assert view._current_result is None and not view.pdf_btn.isEnabled()
    assert "codex.db unreadable" in view.detail_header.text()
    # ... and the project table says so (EXA19)
    view._load_projects()
    assert "could not be read" in view.summary_label.text()


def test_exa19_analysis_failures_are_recorded(monkeypatch):
    from Examen import examen_data as ed
    ed.take_read_errors()
    monkeypatch.setattr(ed, "analysis_service",
                        lambda: (_ for _ in ()).throw(sqlite3.OperationalError("no such table")))
    assert ed._analyse(["T"], None, "England") is None
    assert ed.take_read_errors() == ["OperationalError: no such table"]
    assert ed.take_read_errors() == []


def test_exa19_csv_export_error_is_shown(qapp, monkeypatch, boxes, tmp_path):
    from PySide6.QtWidgets import QFileDialog
    from Examen import site_analysis_view as sav
    proj = S(project_name="P", survey_year="2026", client="C", site_count=1, visit_count=2,
             species_count=3, key_species_count=1, key_species_pct=33.3, sqi=120,
             sqi_reliable=False, rare_count=0, scarce_count=1, priority_count=0,
             first_date="2026-05-01", last_date="2026-06-01")
    view = S(_projects=[proj])
    bad = str(tmp_path / "missing" / "x.csv")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (bad, "")))
    sav.SiteAnalysisView._export_csv(view)
    assert boxes[-1][:2] == ("warning", "Export failed")
    good = str(tmp_path / "x.csv")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (good, "")))
    sav.SiteAnalysisView._export_csv(view)
    assert boxes[-1][0] == "information" and os.path.getsize(good) > 0


def test_exa19_species_database_says_when_codex_cannot_be_read(qapp):
    from Examen.species_database_view import SpeciesDatabaseView

    class Broken:
        def get_status_summary(self, tvk):
            raise sqlite3.DatabaseError("file is not a database")

        def get_species_profile(self, tvk):
            raise FileNotFoundError("pantheon.db")
    v = SpeciesDatabaseView(Broken(), Broken())
    from PySide6.QtWidgets import QListWidgetItem
    from PySide6.QtCore import Qt
    item = QListWidgetItem("x")
    item.setData(Qt.ItemDataRole.UserRole, ("Name", "TVK1", "", "Fam", "Species"))
    v._on_species_selected(item, None)
    text = v.read_error_label.text()
    assert not v.read_error_label.isHidden()
    assert "Codex could not be read" in text and "Pantheon could not be read" in text


@needs_data
def test_exa7_cryptocephalus_sexpunctatus_has_score_and_ecology(qapp):
    from shared.repositories.codex_repository import CodexRepository
    from shared.repositories.pantheon_repository import PantheonRepository
    from Examen.species_database_view import SpeciesDatabaseView
    v = SpeciesDatabaseView(CodexRepository(), PantheonRepository())
    from PySide6.QtWidgets import QListWidgetItem
    from PySide6.QtCore import Qt
    item = QListWidgetItem("x")
    item.setData(Qt.ItemDataRole.UserRole, ("Cryptocephalus sexpunctatus", "NBNSYS0000011140",
                                            "", "Chrysomelidae", "Species"))
    v._on_species_selected(item, None)
    assert "16" in v.sqs_label.text()
    assert not v.ecology_group.isHidden()


# ============================================================ Codex ===========

@needs_data
def test_cdx3_codex_manager_has_no_import_or_unresolved_tab(qapp):
    import importlib.util
    from Codex.codex_manager import CodexManager, IMPORT_NOTE
    m = CodexManager()
    assert [m.tabs.tabText(i) for i in range(m.tabs.count())] == ["Reviews", "Species Search"]
    assert "import_status_review.py" in IMPORT_NOTE
    assert importlib.util.find_spec("Codex.import_tab") is None
    assert importlib.util.find_spec("Codex.unresolved_tab") is None
    m.close()


# ============================================================ Curator =========

def _profile(height=300, width=440):
    from Curator import planner_data as pd
    pm = pd.ProfileManager.__new__(pd.ProfileManager)
    pm._data, pm.problem = {}, ""
    pm._sizes = {"standard": pd.SpecimenSize("standard", "Standard", 25, 20)}
    pm._boxes = {"drawer": pd.BoxSize("drawer", "Drawer", width, height)}
    pm._family_profiles = {}
    return pm


def test_cur1_oversized_family_split_wherever_it_falls():
    from Curator import planner_data as pd
    fam = lambda name, n: pd.FamilyData(name, n, 1, [], 0)  # noqa: E731
    families = [fam("Small", 40), fam("Huge", 500), fam("After", 10)]
    boxes = pd.allocate_to_boxes(families, _profile(), "drawer", growth_pct=0)
    # 17 per row, 20 mm rows, 300 mm box = 15 rows; Huge needs 30 rows
    assert max(b.capacity_pct for b in boxes) <= 100
    assert sum(f.specimen_count for b in boxes for f in b.families) == 550
    names = [[f.family for f in b.families] for b in boxes]
    assert names[0][0] == "Small" and names[0][-1] == "Huge (part 1)"   # fills box 1
    assert [f.part for b in boxes for f in b.families if f.family.startswith("Huge")] == [1, 2, 3]
    # still split when it starts a box
    boxes = pd.allocate_to_boxes([fam("Huge", 500)], _profile(), "drawer", growth_pct=0)
    assert max(b.capacity_pct for b in boxes) <= 100
    assert sum(f.specimen_count for b in boxes for f in b.families) == 500


def _uksi(path):
    c = sqlite3.connect(path)
    c.execute('CREATE TABLE taxa (tvk TEXT, scientific_name TEXT, rank TEXT, genus TEXT, '
              'family TEXT, "order" TEXT, sort_code INTEGER)')
    c.executemany("INSERT INTO taxa VALUES (?,?,?,?,?,?,?)", [
        ("T_MAL", "Malthodes marginatus", "Species", "Malthodes", "Cantharidae", "Coleoptera", 2),
        ("T_LEI", "Leiopus", "Genus", "Leiopus", "Cerambycidae", "Coleoptera", 3),
        ("T_LAS", "Lasioglossum minutissimum", "Species", "Lasioglossum", "Halictidae",
         "Coleoptera", 4),
        ("T_OLD", "Newname species", "Species", "Newname", "Cantharidae", "Coleoptera", 5),
    ])
    c.commit()
    c.close()


def test_cur2_specimens_placed_by_tvk(tmp_path, monkeypatch):
    from Curator import planner_tree_data as td
    obs, uksi = str(tmp_path / "observatum.db"), str(tmp_path / "uksi.db")
    _uksi(uksi)
    c = sqlite3.connect(obs)
    c.execute("CREATE TABLE specimens (species_name TEXT, species_tvk TEXT, family TEXT, "
              "order_name TEXT)")
    c.executemany("INSERT INTO specimens VALUES (?,?,?,?)", [
        ("Malthodes Marginatus", "T_MAL", "Cantharidae", "Coleoptera"),      # wrong case
        ("lasioglossum minutissimum", "T_LAS", "Halictidae", "Coleoptera"),
        ("lasioglossum minutissimum", "T_LAS", "Halictidae", "Coleoptera"),
        ("Leiopus", "T_LEI", "Cerambycidae", "Coleoptera"),                  # genus only
        ("Oldname species", "T_OLD", "Cantharidae", "Coleoptera"),           # renamed
        ("malthodes marginatus", None, "Cantharidae", "Coleoptera"),         # no TVK
    ])
    c.commit()
    c.close()
    from pathlib import Path
    monkeypatch.setattr(td, "DB_PATH", Path(obs))
    monkeypatch.setattr(td, "UKSI_PATH", Path(uksi))
    fams, gens, sps, fam_n, sp_n, gen_n = td._load_specimen_data("Coleoptera")
    assert sp_n == {"Malthodes marginatus": 2, "Lasioglossum minutissimum": 2,
                    "Newname species": 1}
    assert gen_n == {"Leiopus": 1}
    assert sum(sp_n.values()) + sum(gen_n.values()) == 6
    assert {"Malthodes", "Lasioglossum", "Leiopus", "Newname"} <= gens
    assert fam_n == {"Cantharidae": 3, "Halictidae": 2, "Cerambycidae": 1}


def test_cur2_counts_reach_every_rank():
    from Curator.planner_tree_data import TaxonNode, _aggregate_specimen_counts, _set_species_counts
    sp = TaxonNode("A b", "Species", specimen_count=3)
    gen = TaxonNode("A", "Genus", children=[sp], own_specimen_count=2)
    fam = TaxonNode("F", "Family", children=[gen])
    sf = TaxonNode("SF", "Superfamily", children=[fam])
    root = TaxonNode("O", "Order", children=[sf])
    _aggregate_specimen_counts(root)
    _set_species_counts(root)
    assert (root.specimen_count, sf.specimen_count, gen.specimen_count) == (5, 5, 5)
    assert (root.species_count, root.my_species_count) == (1, 1)


@needs_data
def test_cur2_real_tree_holds_every_specimen():
    from Curator.planner_data import load_orders
    from Curator.planner_tree_data import load_taxonomic_tree
    for order, n in load_orders():
        assert load_taxonomic_tree(order, my_specimens_only=True).specimen_count == n, order


def test_cur3_missing_profiles_are_reported(monkeypatch, tmp_path):
    from Curator import planner_data as pd
    monkeypatch.setattr(pd, "PROFILES_PATH", tmp_path / "mounting_profiles.json")
    pm = pd.ProfileManager()
    assert "mounting_profiles.json is missing" in pm.problem
    assert pm.problem in pd.config_problems()
    (tmp_path / "mounting_profiles.json").write_text("{not json", encoding="utf-8")
    assert "could not be read" in pd.ProfileManager().problem


def test_cur3_pdf_exports_raise_instead_of_printing(monkeypatch):
    from Curator import planner_label_export as le, planner_export as pe
    monkeypatch.setattr(le, "FPDF", None)
    with pytest.raises(RuntimeError, match="fpdf2"):
        le.export_taxonomic_labels_pdf("x.pdf", [])
    monkeypatch.setattr(pe, "FPDF", None)
    with pytest.raises(RuntimeError, match="fpdf2"):
        pe.export_layout_pdf("x.pdf", [], _profile(), "drawer", 0)


def test_cur3_layout_pdf_text_is_core_font_safe():
    from Curator.planner_export import _core_text
    assert _core_text("Box 1: Carabidae — Silphidae") == "Box 1: Carabidae - Silphidae"
    _core_text("Aë 中").encode("latin-1")     # never raises


# ============================================================ Munia ===========

@pytest.fixture
def munia():
    from Munia import munia_data as db
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    db.ensure_schema(c)
    return c


def test_mun3_duplicate_name_is_refused_with_a_reason(munia):
    from Munia import munia_data as db
    a = db.add_project(munia, {"start_year": 2026, "end_year": 2026, "project_name": "Alsager"})
    with pytest.raises(db.DuplicateProjectName, match="Alsager"):
        db.add_project(munia, {"start_year": 2026, "end_year": 2026, "project_name": "Alsager"})
    db.add_project(munia, {"start_year": 2027, "end_year": 2027, "project_name": "Alsager"})
    b = db.add_project(munia, {"start_year": 2026, "end_year": 2026, "project_name": "Bristol"})
    with pytest.raises(db.DuplicateProjectName):
        db.update_project(munia, b, {"project_name": "Alsager"})
    db.update_project(munia, a, {"project_name": "Alsager", "quote_value": 5})   # itself: fine


def test_mun3_form_shows_the_message(qapp, munia, boxes):
    from Munia.project_form import ProjectForm
    f = ProjectForm(munia)
    f.set_year(2026)
    f.clear()
    f.name_edit.setText("Alsager")
    f._on_save()
    f.clear()
    f.name_edit.setText("Alsager")
    f._on_save()
    assert boxes and boxes[-1][1] == "Project not saved" and "Alsager" in boxes[-1][2]
    assert munia.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 1
    assert f.name_edit.text() == "Alsager"            # the form keeps what was typed
    f.clear()
    f._on_save()
    assert "name" in boxes[-1][2]


def test_mun4_summary_reports_multi_year_projects():
    from Munia.munia_data import summarise_pipeline
    s = summarise_pipeline([
        {"status": "accepted", "quote_value": 9000, "start_year": 2025, "end_year": 2027},
        {"status": "accepted", "quote_value": 1000, "start_year": 2026, "end_year": 2026},
        {"status": "quoted", "quote_value": 500, "start_year": 2026, "end_year": 2027}])
    assert s["confirmed"] == 10000                     # unchanged: counted in full
    assert (s["multi_year_count"], s["multi_year_confirmed"]) == (2, 9000)


# ============================================================ Atrium ==========

class _FakeProc:
    started = []

    def __init__(self, cmd, **kwargs):
        _FakeProc.started.append((cmd, kwargs))
        self.code = None

    def poll(self):
        return self.code


def test_atr1_tiles_and_one_copy_each(qapp, monkeypatch):
    from Atrium import process_manager as pm
    from Atrium.atrium_ui import AtriumPanel
    names = [b._app.name for b in AtriumPanel()._buttons]
    assert names == ["Observatum", "Examen", "Curator", "Munia", "Lector"]   # no Data Entry (review 4)

    monkeypatch.setattr(pm.subprocess, "Popen", _FakeProc)
    monkeypatch.setattr(pm, "_visible_windows", lambda: [])
    _FakeProc.started.clear()
    ex = next(a for a in pm.APPS if a.name == "Examen")
    monkeypatch.setattr(ex, "process", None)
    assert pm.launch_app(ex)[0] == pm.LAUNCHED
    assert pm.launch_app(ex)[0] == pm.ALREADY_RUNNING          # no second copy
    assert len(_FakeProc.started) == 1
    ex.process.code = 0                                          # it was closed
    focused = []
    monkeypatch.setattr(pm, "bring_to_front", lambda h: focused.append(h) or True)
    monkeypatch.setattr(pm, "_visible_windows", lambda: [
        (7, "Examen — Species Assessment Tool", "Qt6110QWindowIcon"),
        (8, "Lector", "CabinetWClass")])                         # an Explorer folder
    assert pm.launch_app(ex)[0] == pm.FOCUSED and focused == [7]  # opened elsewhere
    assert len(_FakeProc.started) == 1

    lector = next(a for a in pm.APPS if a.name == "Lector")
    monkeypatch.setattr(lector, "process", None)
    assert pm.launch_app(lector)[0] == pm.LAUNCHED              # the folder is not Lector
    cmd = _FakeProc.started[-1][0]
    assert cmd[1:5] == ["-m", "Atrium.console_launch", "Lector", pm.LECTOR_TITLE]
    if sys.platform == "win32":
        assert _FakeProc.started[-1][1]["creationflags"] == pm.subprocess.CREATE_NEW_CONSOLE


def test_atr1_console_launch_runs_the_module_and_waits(tmp_path, monkeypatch, capsys):
    (tmp_path / "fake_tool.py").write_text(
        "import sys\nprint('ran', sys.argv[1:])\nraise SystemExit(3)\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr("builtins.input", lambda *a: "")
    from Atrium.console_launch import main
    assert main(["x", "fake_tool", "Title", "status"]) == 3
    assert "ran ['status']" in capsys.readouterr().out


def test_atr2_no_tabella_code_left():
    import inspect
    from Atrium import process_manager as pm, atrium_ui
    for mod in (pm, atrium_ui):
        src = inspect.getsource(mod)
        assert "unlink" not in src and "_run_generator" not in src and ".xlsm\"" not in src
    assert not hasattr(pm, "_open_tabella_workbook")


# ============================================================ INF4 ============

def test_inf4_lector_and_vc_splits_registered_and_backed_up(tmp_path, monkeypatch):
    from shared import backup_service as bs
    assert paths.LECTOR_DB.name == "lector.db" and paths.VC_SPLITS_DB.name == "vc_splits.db"
    assert "LECTOR_DB" in bs.WORKING_DBS and "VC_SPLITS_DB" in bs.REFERENCE_DBS
    root = tmp_path / "backups"
    monkeypatch.setattr(bs, "BACKUP_ROOT", str(root))
    for name in bs.WORKING_DBS + bs.REFERENCE_DBS:
        monkeypatch.setattr(paths, name, tmp_path / "absent" / f"{name}.db")
    for name, fn in (("LECTOR_DB", "lector.db"), ("VC_SPLITS_DB", "vc_splits.db")):
        p = tmp_path / fn
        c = sqlite3.connect(str(p))
        c.execute("CREATE TABLE t (v)")
        c.commit()
        c.close()
        monkeypatch.setattr(paths, name, p)
    assert bs.backup_working("test")
    assert (root / "current" / "lector.db").exists()
    assert not (root / "current" / "vc_splits.db").exists()
    assert bs.backup_reference()
    assert (root / "reference" / "vc_splits.db").exists()
