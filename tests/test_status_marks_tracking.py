"""Status marks remember the status they were made against (status_marked): a mark applies only
while the species' current status is that one; migration; the Status marks dialog; the tooltip."""
import sqlite3

import pytest
from _round_a_fixture import T_RARE, T_SCARCE, T_VU, add_committed, build

from Examen import examen_data as ed
from Examen import status_marks as sm
from Examen import workbook_export as we

JOB = ("Notts Park", "Acme", "2026")


@pytest.fixture()
def world(tmp_path, monkeypatch):
    build(tmp_path, monkeypatch)
    add_committed(tmp_path)
    return tmp_path


def _set_codex(world, tvk, value, track="rarity_modern"):
    c = sqlite3.connect(str(world / "codex.db"))
    c.execute("UPDATE status_summary SET status_value = ? WHERE tvk = ? AND status_track = ?",
              (value, tvk, track))
    c.commit()
    c.close()


def _summary(world, name):
    from openpyxl import load_workbook
    d = ed.load_project_detail(*JOB[:2], survey_year=JOB[2])
    path = str(world / name)
    we.export_workbook(d.analysis, d, None, path, jurisdiction=d.jurisdiction)
    ws = load_workbook(path)["Summary"]
    return {r[0]: r[1] for r in ws.iter_rows(min_row=3, values_only=True) if r[0]}


def _unused_key(world, tvk=T_RARE):
    d = ed.load_project_detail(*JOB[:2], survey_year=JOB[2])
    return next(k for k in d.analysis.key_species if k.tvk == tvk)


# ---- status_key ------------------------------------------------------------------

def test_status_key_normalises():
    from types import SimpleNamespace as NS
    assert sm.status_key(NS(rarity="rdb1", threat="", threat_legacy="")) == "RDB1"
    assert sm.status_key(NS(rarity="NS", threat="vu ", threat_legacy="")) == "NS; VU"
    assert sm.status_key(NS(rarity="VU", threat="VU", threat_legacy="")) == "VU"
    assert sm.status_key(["VU", "ns", ""]) == "NS; VU" and sm.status_key(()) == ""
    assert sm.status_key(None) == "" and sm.status_key(NS(rarity="", threat="")) == ""


def test_mark_state_is_the_one_decision():
    assert sm.mark_state("", "NS") == sm.UNRECORDED and sm.mark_applies("", "NS")
    assert sm.mark_state("NR", "NR") == sm.APPLIED
    assert sm.mark_state("NR", "NS") == sm.STALE and not sm.mark_applies("NR", "NS")
    assert sm.mark_state("NR", "") == sm.STALE
    assert sm.mark_state("NR", sm.NOT_GIVEN) == sm.APPLIED


# ---- applying only while the status stands ---------------------------------------

def test_mark_applies_then_stops_when_status_changes(world):
    sm.set_mark(T_RARE, "Rarus beetle", "old", sm.current_key(T_RARE))
    assert sm.list_marks()[0]["status_marked"] == "NR"
    assert sm.bracket_checker(*JOB)(T_RARE) and sm.is_bracketed(T_RARE, *JOB)
    base = _summary(world, "unrevised.xlsx")
    assert "Rare Key Species (revised)" in base
    _set_codex(world, T_RARE, "NS")                           # a new review: NR -> NS
    assert sm.current_key(T_RARE) == "NS" and not sm.is_bracketed(T_RARE, *JOB)
    after = _summary(world, "after.xlsx")
    assert not [k for k in after if "revised" in k]            # revised figures = unrevised
    assert after["Rare Key Species"] == 1 and after["Key Species (status only)"] == 3


def test_stale_mark_not_bracketed_in_workbook_appendix_and_tab(world):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from Examen.species_tab import SpeciesTab, stale_note
    sm.set_mark(T_RARE, "Rarus beetle", "old", "RDB1")        # marked at RDB1; Codex now says NR
    d = ed.load_project_detail(*JOB[:2], survey_year=JOB[2])
    tab = SpeciesTab()
    tab.set_result(d.analysis, d, {})
    col = {tab.table.item(r, 0).text(): tab.table.item(r, 2) for r in range(tab.table.rowCount())}
    item = col["Rarus beetle"]
    assert not item.text().startswith("[")
    assert item.toolTip() == ("Status changed since you marked it (RDB1 → NR); "
                              "mark not applied") == stale_note(
        {"status_marked": "RDB1", "current": "NR"})
    # a live mark brackets and says so
    sm.set_mark(T_RARE, "Rarus beetle", "old", "NR")
    tab._apply_filters()
    col = {tab.table.item(r, 0).text(): tab.table.item(r, 2) for r in range(tab.table.rowCount())}
    assert col["Rarus beetle"].text() == "[Nationally Rare]"


def test_blank_status_marked_still_applies(world):
    sm.set_mark(T_RARE, "Rarus beetle", "old")                 # '' = not recorded
    assert sm.list_marks()[0]["status_marked"] == ""
    _set_codex(world, T_RARE, "NS")
    assert sm.is_bracketed(T_RARE, *JOB)
    assert "Rare Key Species (revised)" in _summary(world, "blank.xlsx")


def test_override_bracket_follows_the_same_rule(world):
    sm.set_override(*JOB, T_VU, "Vulnus bug", True, "VU")
    assert sm.list_overrides(*JOB)[0]["status_marked"] == "VU"
    assert sm.is_bracketed(T_VU, *JOB)
    sm.set_override(*JOB, T_SCARCE, "Scarcus beetle", True, "EN")   # Codex says NS: stale
    assert not sm.is_bracketed(T_SCARCE, *JOB)
    sm.set_override(*JOB, T_RARE, "Rarus beetle", True)         # '' applies
    assert sm.is_bracketed(T_RARE, *JOB)
    sm.clear_override(*JOB, T_SCARCE)
    sm.set_override(*JOB, T_SCARCE, "Scarcus beetle", False)    # bracket 0 stores no status
    assert {o["tvk"]: o["status_marked"] for o in sm.list_overrides(*JOB)}[T_SCARCE] == ""


def test_mark_again_resaves_against_the_current_status(world):
    sm.set_mark(T_RARE, "Rarus beetle", "why", "RDB1")
    sm.set_override(*JOB, T_RARE, "Rarus beetle", True, "RDB1")
    sm.set_override("Elsewhere", "", "2020", T_RARE, "Rarus beetle", True, "RDB1")   # other job
    sm.mark_again(T_RARE, "Rarus beetle")
    assert sm.list_marks()[0]["status_marked"] == "NR" and sm.list_marks()[0]["reason"] == "why"
    assert {o["status_marked"] for o in sm.list_overrides()} == {"NR"}
    assert sm.is_bracketed(T_RARE, *JOB)


# ---- old schema and migration ---------------------------------------------------

def test_reads_tolerate_a_missing_column_and_writes_refuse(tmp_path, monkeypatch):
    build(tmp_path, monkeypatch, old_marks_schema=True)
    c = sqlite3.connect(str(tmp_path / "examen.db"))
    c.execute("INSERT INTO status_downgrades (tvk, species_name) VALUES (?, 'x')", (T_RARE,))
    c.commit()
    c.close()
    assert sm.list_marks()[0]["status_marked"] == "" and not sm.columns_present()
    assert sm.is_bracketed(T_RARE, *JOB)
    with pytest.raises(sm.MissingTables):
        sm.set_mark(T_VU, "y", "", "VU")


OLD_DDL = """
CREATE TABLE status_downgrades (tvk TEXT PRIMARY KEY, species_name TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '', created_at TEXT, updated_at TEXT);
CREATE TABLE status_downgrade_overrides (project_name TEXT NOT NULL,
    client TEXT NOT NULL DEFAULT '', survey_year TEXT NOT NULL DEFAULT '', tvk TEXT NOT NULL,
    species_name TEXT NOT NULL DEFAULT '', bracket INTEGER NOT NULL, updated_at TEXT,
    PRIMARY KEY(project_name, client, survey_year, tvk));
CREATE TABLE benchmark_choices (project_name TEXT NOT NULL, client TEXT NOT NULL DEFAULT '',
    survey_year TEXT NOT NULL DEFAULT '', included INTEGER NOT NULL, updated_at TEXT,
    PRIMARY KEY(project_name, client, survey_year));
INSERT INTO status_downgrades VALUES ('T1', 'Old mark', 'r', 'c', 'u');
"""


def test_migration_adds_columns_once(tmp_path, capsys):
    import sys
    sys.path.insert(0, str(sys.modules["paths"].__file__.rsplit("/", 1)[0] + "/scripts"))
    from scripts import add_report_tables as art
    ex, ob = tmp_path / "examen.db", tmp_path / "observatum.db"
    c = sqlite3.connect(str(ex))
    c.executescript(OLD_DDL)
    c.close()
    sqlite3.connect(str(ob)).close()
    args = ["--observatum-db", str(ob), "--examen-db", str(ex), "--backup-dir", str(tmp_path / "bk")]
    assert art.main(args) == 0
    out = capsys.readouterr().out
    assert "would add column status_marked to status_downgrades" in out
    assert "would add column status_marked to status_downgrade_overrides" in out and "DRY RUN" in out
    cols = lambda t: [r[1] for r in sqlite3.connect(str(ex)).execute(f"PRAGMA table_info({t})")]  # noqa: E731
    assert "status_marked" not in cols("status_downgrades")
    assert art.main(args + ["--apply"]) == 0
    assert "status_marked" in cols("status_downgrades")
    assert "status_marked" in cols("status_downgrade_overrides")
    assert list((tmp_path / "bk").glob("examen_pre_add_report_tables_*.db"))
    row = sqlite3.connect(str(ex)).execute("SELECT * FROM status_downgrades").fetchall()
    assert row == [("T1", "Old mark", "r", "c", "u", "")]            # old mark kept, '' recorded
    capsys.readouterr()
    before = len(list((tmp_path / "bk").iterdir()))
    assert art.main(args + ["--apply"]) == 0
    assert "Nothing to add" in capsys.readouterr().out
    assert len(list((tmp_path / "bk").iterdir())) == before          # second run changes nothing


# ---- the Status marks dialog ----------------------------------------------------

def test_dialog_lists_states(world):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from Examen.status_marks_dialog import StatusMarksDialog
    sm.set_mark(T_RARE, "Rarus beetle", "kept", "NR")           # applied
    sm.set_mark(T_SCARCE, "Scarcus beetle", "old", "RDB2")      # Codex says NS: stale
    sm.set_mark(T_VU, "Vulnus bug", "", "")                     # not recorded
    sm.set_override(*JOB, T_RARE, "Rarus beetle", False)
    dlg = StatusMarksDialog()
    by = {(r["species"], r["scope"]): r for r in dlg.rows}
    assert by[("Rarus beetle", "global")]["state_text"] == "applied"
    s = by[("Scarcus beetle", "global")]
    assert (s["marked"], s["current"], s["state_text"]) == (
        "RDB2", "NS", "status changed — not applied")
    assert by[("Vulnus bug", "global")]["state_text"] == "status not recorded"
    assert by[("Vulnus bug", "global")]["current"] == "VU"
    o = by[("Rarus beetle", "job")]
    assert o["job"] == "Notts Park / Acme / 2026" and o["state_text"] == "not bracketed in this job"
    assert dlg.table.rowCount() == 4 and dlg.table.item(0, 0).text()


def test_dialog_remove_uses_the_remove_functions(world):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from Examen.status_marks_dialog import StatusMarksDialog
    sm.set_mark(T_RARE, "Rarus beetle", "", "NR")
    sm.set_override(*JOB, T_VU, "Vulnus bug", True, "VU")
    dlg = StatusMarksDialog(current_keys=lambda tvks: {t: "VU" for t in tvks})
    dlg.table.selectRow(1)
    dlg.table.setCurrentCell(1, 0)
    dlg.remove_selected()
    assert not sm.list_overrides() and len(sm.list_marks()) == 1 and dlg.table.rowCount() == 1
    dlg.table.setCurrentCell(0, 0)
    dlg.remove_selected()
    assert not sm.list_marks() and dlg.table.rowCount() == 0


def test_dialog_survives_codex_failure(world):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from Examen.status_marks_dialog import build_rows
    sm.set_mark(T_RARE, "Rarus beetle", "", "NR")

    def boom(tvks):
        raise OSError("no codex")
    r = build_rows(boom)[0]
    assert r["current"] == "(unavailable)" and r["state"] is None
    assert r["state_text"].startswith("cannot check")
    sm.set_mark(T_VU, "Vulnus bug", "", "")                 # nothing recorded: still says so
    assert {x["species"]: x["state_text"] for x in build_rows(boom)}["Vulnus bug"] == (
        "status not recorded")


# ---- one source of truth: Codex by TVK, in every mode ----------------------------

def _pantheon_status(world, tvk, abbr):
    c = sqlite3.connect(str(world / "pantheon.db"))
    c.execute("INSERT INTO species VALUES (?, 'x', 'Fam')", (tvk,))
    c.execute("INSERT INTO sqs_scores VALUES (?, 8)", (tvk,))
    c.execute("INSERT INTO conservation_status VALUES (?, 'GB Status', ?)", (tvk, abbr))
    c.commit()
    c.close()


def _modes_summary(world, mode, name):
    from openpyxl import load_workbook
    d = ed.load_project_detail(*JOB[:2], mode, survey_year=JOB[2])
    path = str(world / name)
    we.export_workbook(d.analysis, d, None, path, jurisdiction=d.jurisdiction)
    wb = load_workbook(path)
    return {r[0]: r[1] for r in wb["Summary"].iter_rows(min_row=3, values_only=True) if r[0]}, d


def test_marks_hold_across_modes_and_go_stale_in_both(world):
    from shared.services.pantheon_analysis_service import AnalysisMode as M
    _pantheon_status(world, T_RARE, "Nb")                  # Pantheon says Nb; Codex says NR
    _pantheon_status(world, T_VU, "NS")
    _, dp = _modes_summary(world, M.PANTHEON_ONLY, "p0.xlsx")
    assert {k.tvk: k.rarity for k in dp.analysis.key_species}[T_RARE] == "Nb"
    sm.set_mark(T_RARE, "Rarus beetle", "x", sm.current_key(T_RARE))      # made in "Codex Full"
    assert sm.list_marks()[0]["status_marked"] == "NR"
    for mode in (M.CODEX_FULL, M.PANTHEON_ONLY):
        by, d = _modes_summary(world, mode, f"m_{mode.name}.xlsx")
        assert sm.is_bracketed(T_RARE, *JOB)
        assert any("revised" in k for k in by), mode
    _set_codex(world, T_RARE, "NS")                        # a Codex change: stale in both
    for mode in (M.CODEX_FULL, M.PANTHEON_ONLY):
        by, _ = _modes_summary(world, mode, f"s_{mode.name}.xlsx")
        assert not [k for k in by if "revised" in k], mode


def test_mark_made_in_pantheon_only_mode_uses_the_codex_key(world):
    # the key is by TVK from Codex whichever mode the screen is in, so it cannot differ
    from shared.services.pantheon_analysis_service import AnalysisMode as M
    _pantheon_status(world, T_RARE, "Nb")
    sm.set_mark(T_RARE, "Rarus beetle", "x", sm.current_key(T_RARE))
    by, _ = _modes_summary(world, M.CODEX_FULL, "c.xlsx")
    assert sm.list_marks()[0]["status_marked"] == "NR" and any("revised" in k for k in by)


def test_codex_unreadable_applies_as_marked_with_a_note(world, monkeypatch):
    from openpyxl import load_workbook
    sm.set_mark(T_RARE, "Rarus beetle", "x", "RDB1")       # would be stale with a readable Codex
    sm.set_mark(T_VU, "Vulnus bug", "x", "")
    monkeypatch.setattr(sm, "codex_status_keys", lambda t: (_ for _ in ()).throw(OSError("no")))
    chk = sm.bracket_checker(*JOB)
    assert chk.unchecked and chk(T_RARE) and chk(T_VU)
    d = ed.load_project_detail(*JOB[:2], survey_year=JOB[2])
    path = str(world / "u.xlsx")
    we.export_workbook(d.analysis, d, None, path, jurisdiction=d.jurisdiction)
    text = [str(c.value) for row in load_workbook(path)["Summary"].iter_rows() for c in row if c.value]
    assert we.UNCHECKED_NOTE in text
    from Examen.report_model import read_report
    from Examen.report_pack_tables import key_sentence
    assert key_sentence(read_report(path)).endswith(we.UNCHECKED_NOTE)


def test_no_note_when_codex_is_readable(world):
    from openpyxl import load_workbook
    sm.set_mark(T_RARE, "Rarus beetle", "x", "NR")
    d = ed.load_project_detail(*JOB[:2], survey_year=JOB[2])
    path = str(world / "n.xlsx")
    we.export_workbook(d.analysis, d, None, path, jurisdiction=d.jurisdiction)
    text = [str(c.value) for row in load_workbook(path)["Summary"].iter_rows() for c in row if c.value]
    assert we.UNCHECKED_NOTE not in text


def test_never_bracket_threat_categories_only():
    """LC / NA / NE / WL (threat categories that are not a status) are never bracketed; the
    rarity Notable A "Na" and DD (a Rare Key code) are."""
    from types import SimpleNamespace as NS
    e = NS(rarity="NR", threat="LC", threat_legacy="")
    assert sm.status_key(e) == "NR" and sm.status_key(["LC", "NE", "NA", "WL"]) == ""
    assert we.status_codes(e) == ("NR",)
    na = NS(rarity="Na", threat="NA", threat_legacy="")
    assert we.status_codes(na) == ("Na",) and sm.status_key(na) == "NA"
    assert sm.status_key(NS(rarity="", threat="DD", threat_legacy="")) == "DD"
    parts = [("LC", True), ("NR", True), ("DD", True), ("NA", True), ("Na", True)]
    assert we.bracket_parts(parts, True, codes=("LC", "NR", "DD", "NA", "Na")) == [
        ("LC", True), ("[NR]", True), ("[DD]", True), ("NA", True), ("[Na]", True)]
    assert we.bracket_parts(parts, True) == [("LC", True), ("[NR]", True), ("[DD]", True),
                                             ("NA", True), ("[Na]", True)]
    assert we.string_codes("Na, NA, S41") == ("Na",)
    assert sm.status_key(we.string_codes("LC, NR, S41")) == sm.status_key(e) == "NR"


def test_menu_offers_no_mark_without_a_codex_code(world, monkeypatch):
    """A species whose Codex status has no rarity or threat code (e.g. LC only) cannot be marked:
    the menu shows a disabled line instead, so no mark is saved with an empty status."""
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QMenu
    QApplication.instance() or QApplication([])
    from Examen import status_marks_ui
    seen = []

    class Menu(QMenu):
        def exec(self, *a):
            seen.extend((act.text(), act.isEnabled()) for act in self.actions())
    monkeypatch.setattr(status_marks_ui, "QMenu", Menu)
    monkeypatch.setattr(sm, "current_key", lambda tvk: "")
    status_marks_ui.show_menu(None, None, "TVK1", "Speciesus nocodus", ("P", "C", "2026"), lambda: None)
    assert (status_marks_ui.NO_CODE, False) in seen
    assert not any(t.startswith("Mark status") for t, _ in seen)
