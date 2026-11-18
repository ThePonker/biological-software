"""Round A: "likely to be downgraded" status marks -- Examen.status_marks, the revised Key
Species figures, and the [square brackets] in the workbook, Word and PDF."""
import hashlib

import pytest
from _round_a_fixture import T_RARE, T_SCARCE, T_VU, add_committed, add_job, build

from Examen import examen_data as ed
from Examen import status_marks as sm
from Examen import workbook_export as we
from Examen.report_model import read_report

JOB = ("Notts Park", "Acme", "2026")


@pytest.fixture()
def world(tmp_path, monkeypatch):
    build(tmp_path, monkeypatch)
    add_committed(tmp_path)
    return tmp_path


def _summary_rows(path):
    from openpyxl import load_workbook
    ws = load_workbook(path)["Summary"]
    out = []
    for r in ws.iter_rows(min_row=3, values_only=True):
        if r[0] == "Basis of assessment":
            break
        if r[0]:
            out.append((r[0], r[1], r[2]))
    return out


def _export(world, name="a.xlsx", detail=None):
    detail = detail or ed.load_project_detail(*JOB[:2], survey_year=JOB[2])
    path = str(world / name)
    we.export_workbook(detail.analysis, detail, None, path, jurisdiction=detail.jurisdiction)
    return path, detail


# ---- resolution ----------------------------------------------------------------

def test_is_bracketed_global_override_and_scope(world):
    assert not sm.is_bracketed(T_RARE, *JOB)
    sm.set_mark(T_RARE, "Rarus beetle", "old status")
    assert sm.is_bracketed(T_RARE, *JOB) and sm.is_bracketed(T_RARE, "Other", "", "2020")
    assert not sm.is_bracketed(T_VU, *JOB) and not sm.is_bracketed("", *JOB)
    sm.set_override(*JOB, T_RARE, "Rarus beetle", False)             # unbracketed in this job
    assert not sm.is_bracketed(T_RARE, *JOB)
    assert sm.is_bracketed(T_RARE, "Notts Park", "Acme", "2025")     # another year: still marked
    assert sm.is_bracketed(T_RARE, "Other", "", "2026")
    sm.set_override(*JOB, T_VU, "Vulnus bug", True)                  # bracketed here only
    assert sm.is_bracketed(T_VU, *JOB) and not sm.is_bracketed(T_VU, "Other", "", "2026")
    fn = sm.bracket_checker(*JOB)
    assert (fn(T_RARE), fn(T_VU), fn(T_SCARCE)) == (False, True, False)
    sm.clear_override(*JOB, T_RARE)
    assert sm.is_bracketed(T_RARE, *JOB)
    sm.clear_mark(T_RARE)
    assert not sm.is_bracketed(T_RARE, *JOB)


def test_list_marks_and_overrides_and_reason(world):
    sm.set_mark(T_RARE, "Rarus beetle", "first")
    sm.set_mark(T_RARE, "Rarus beetle", "second")                    # replaces, one row
    sm.set_override(*JOB, T_VU, "Vulnus bug", True)
    assert sm.list_marks() == [{"tvk": T_RARE, "species_name": "Rarus beetle", "reason": "second"}]
    assert [(o["tvk"], o["bracket"]) for o in sm.list_overrides(*JOB)] == [(T_VU, 1)]
    assert sm.list_overrides("Elsewhere") == []
    assert sm.is_globally_marked(T_RARE) and not sm.is_globally_marked(T_VU)


# ---- missing tables ------------------------------------------------------------

def test_missing_tables_read_nothing_and_write_nothing(tmp_path, monkeypatch):
    build(tmp_path, monkeypatch, with_mark_tables=False)
    before = hashlib.sha256((tmp_path / "examen.db").read_bytes()).hexdigest()
    assert not sm.tables_present()
    assert sm.list_marks() == [] and sm.list_overrides() == []
    assert not sm.is_bracketed(T_RARE, *JOB)
    for call in (lambda: sm.set_mark(T_RARE, "x", "y"), lambda: sm.clear_mark(T_RARE),
                 lambda: sm.set_override(*JOB, T_RARE, "x", True),
                 lambda: sm.clear_override(*JOB, T_RARE)):
        with pytest.raises(sm.MissingTables, match=r"Run scripts\\add_report_tables.py first"):
            call()
    assert hashlib.sha256((tmp_path / "examen.db").read_bytes()).hexdigest() == before


def test_no_examen_db_at_all_creates_nothing(tmp_path, monkeypatch):
    import paths
    monkeypatch.setattr(paths, "EXAMEN_DB", tmp_path / "nope.db")
    assert sm.list_marks() == [] and not sm.is_bracketed(T_RARE, *JOB)
    with pytest.raises(sm.MissingTables):
        sm.set_mark(T_RARE, "x")
    assert not (tmp_path / "nope.db").exists()


# ---- revised figures -----------------------------------------------------------

def test_revised_key_figures(world):
    d = ed.load_project_detail(*JOB[:2], survey_year=JOB[2])
    keys = d.analysis.key_species
    assert sm.revised_key_figures(keys, lambda t: False) == (3, 2)
    assert sm.revised_key_figures(keys, lambda t: t == T_RARE) == (2, 1)
    assert sm.revised_key_figures(keys, lambda t: t in (T_RARE, T_VU, T_SCARCE)) == (0, 0)


def test_summary_rows_added_only_when_a_key_species_is_bracketed(world):
    plain, _ = _export(world, "plain.xlsx")
    base = _summary_rows(plain)
    new = {"Key Species (status only, revised)", "% Key Species (status only, revised)",
           "Rare Key Species (revised)"}
    assert not new & {r[0] for r in base}                       # no brackets: as before Round A
    sm.set_mark(T_RARE, "Rarus beetle", "old")
    marked, _ = _export(world, "marked.xlsx")
    rows = _summary_rows(marked)
    assert new <= {r[0] for r in rows}
    assert {"Species recorded", "Key Species", "% Key Species", "Key Species (status only)",
            "% Key Species (status only)", "Rare Key Species", "% Rare Key Species",
            "Codex tiers \u2014 Rare", "Species Quality Index (SQI)"} <= {r[0] for r in rows}
    assert [r for r in rows if r[0] not in new] == base          # nothing else moved
    by = {r[0]: r for r in rows}
    assert by["Key Species"][1] == 3 and by["Key Species (status only)"][1] == 3
    assert by["Key Species (status only, revised)"][1] == 2
    assert by["% Key Species (status only, revised)"][1] == "40.0%"      # 2 / 5 species
    assert by["Rare Key Species"][1] == 2 and by["Rare Key Species (revised)"][1] == 1
    assert "square brackets" in by["Rare Key Species (revised)"][2]
    labels = [r[0] for r in rows]
    i = labels.index("% Key Species (status only)")
    assert labels[i + 1:i + 3] == ["Key Species (status only, revised)",
                                   "% Key Species (status only, revised)"]
    j = labels.index("% Rare Key Species")
    assert labels[j + 1] == "Rare Key Species (revised)"


def test_no_revised_rows_without_brackets_in_report_model_and_pack(world):
    path, d = _export(world)
    rep = read_report(path)
    labels = [f[0] for f in rep["figures"] if f[0]]
    assert not [x for x in labels if "revised" in x]
    from Examen import report_pack_tables as T
    assert "left out" not in T.key_sentence(rep)
    sm.set_mark(T_RARE, "Rarus beetle", "old")
    rep = read_report(_export(world, "m.xlsx")[0])
    assert "left out" in T.key_sentence(rep)


def test_override_unbracketing_a_marked_species_adds_no_revised_rows(world):
    sm.set_mark(T_RARE, "Rarus beetle", "old")
    sm.set_override(*JOB, T_RARE, "Rarus beetle", False)
    path, _ = _export(world)
    assert not [r for r in _summary_rows(path) if "revised" in r[0]]
    sm.set_override(*JOB, T_VU, "Vulnus bug", True)               # another species bracketed here
    by = {r[0]: r for r in _summary_rows(_export(world, "b.xlsx")[0])}
    assert by["Rare Key Species (revised)"][1] == 1


def test_remove_mark_leaves_the_species_unbracketed_here(world):
    sm.set_mark(T_RARE, "Rarus beetle", "old")
    sm.set_override(*JOB, T_RARE, "Rarus beetle", True)
    assert sm.is_bracketed(T_RARE, *JOB)
    sm.remove_mark(*JOB, T_RARE)
    assert not sm.is_bracketed(T_RARE, *JOB)
    assert not sm.list_marks() and not sm.list_overrides(*JOB)


def test_marks_refused_on_an_away_machine(world, monkeypatch):
    import shared.away_mode as am
    monkeypatch.setattr(am, "away_active", lambda: True)
    with pytest.raises(sm.MarkError):
        sm.set_mark(T_RARE, "Rarus beetle", "x")
    with pytest.raises(sm.MarkError):
        sm.set_override(*JOB, T_RARE, "Rarus beetle", True)
    assert not sm.list_marks() and not sm.list_overrides()


def test_brackets_only_on_rarity_and_threat_codes():
    parts = [("NR", True), ("S41", True), ("Wales S7", True), ("Legal: WCA Sch5", True),
             ("status held at sensu lato", True)]
    assert we.bracket_parts(parts, True) == [("[NR]", True), ("S41", True), ("Wales S7", True),
                                             ("Legal: WCA Sch5", True),
                                             ("status held at sensu lato", True)]
    assert we.bracket_parts(parts, True, codes=("NR",))[0] == ("[NR]", True)
    assert we.bracket_parts(parts, True, codes=())[0] == ("NR", True)     # not this entry's code
    assert we.bracket_parts(parts, False) == parts


def test_mark_menu_only_for_a_species_with_a_code(world, monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from Examen import status_marks_ui
    from Examen.species_tab import SpeciesTab
    d = ed.load_project_detail(*JOB[:2], survey_year=JOB[2])
    tab = SpeciesTab()
    tab.set_result(d.analysis, d, {})
    asked = []
    monkeypatch.setattr(status_marks_ui, "show_menu", lambda *a, **k: asked.append(a[2]))
    # offer for a coded key species, not for a key species without a code or a non-key one
    tab._all_species[0]["codes"] = ()
    tab._apply_filters()
    rows = {tab.table.item(r, 0).text(): r for r in range(tab.table.rowCount())}
    for name, sp in ((s["name"], s) for s in tab._all_species):
        tab._on_context_menu(tab.table.visualItemRect(tab.table.item(rows[name], 0)).center())
    coded = {s["tvk"] for s in tab._all_species if s["key"] and s["codes"]}
    assert set(asked) == coded and coded and len(coded) < len(
        [s for s in tab._all_species if s["key"]])


# ---- brackets in the exports ---------------------------------------------------

def _key_status(path):
    from openpyxl import load_workbook
    ws = load_workbook(path, rich_text=True)["Key species"]
    head = next(r for r in ws.iter_rows(values_only=True) if r and "Conservation status" in r)
    c, sp = head.index("Conservation status"), head.index("Species")
    return {r[sp]: "".join(getattr(x, "text", x) for x in r[c]) if not isinstance(r[c], str)
            else r[c] for r in ws.iter_rows(values_only=True) if r and r[0] and str(r[0]).endswith("Key")}


def test_brackets_in_the_workbook_word_and_pdf(world):
    sm.set_mark(T_RARE, "Rarus beetle", "old")
    path, d = _export(world)
    status = _key_status(path)
    assert status["Rarus beetle"] == "[NR]"
    assert status["Scarcus beetle"] == "NS" and status["Vulnus bug"] == "VU"
    rep = read_report(path)
    labels = [f[0] for f in rep["figures"] if f[0]]
    assert "Rare Key Species (revised)" in labels
    assert "% Key Species (status only, revised)" in labels
    assert "[S41]" not in str(rep)
    key_rows = {r[3]: r[5] for r in rep["key"]["rows"]}
    assert "[NR]" in "".join(t for t, _ in key_rows["Rarus beetle"]) if isinstance(
        key_rows["Rarus beetle"], list) else "[NR]" in key_rows["Rarus beetle"]
    app = next(r for r in rep["appendix"]["rows"] if "Rarus beetle" in str(r[2]))
    assert "[NR]" in "".join(t for t, _ in app[4]) if isinstance(app[4], list) else "[NR]" in app[4]
    other = next(r for r in rep["appendix"]["rows"] if "Scarcus beetle" in str(r[2]))
    assert "[" not in str(other[4])

    from Examen.word_export import HAS_DOCX, export_word
    if HAS_DOCX:
        out = str(world / "r.docx")
        export_word(d.analysis, d, None, out, jurisdiction=d.jurisdiction)
        import docx
        text = "\n".join(c.text for t in docx.Document(out).tables for r in t.rows for c in r.cells)
        assert "[NR]" in text and "Rare Key Species (revised)" in text
    from Examen.pdf_export import HAS_REPORTLAB, export_pdf
    if HAS_REPORTLAB:
        out = str(world / "r.pdf")
        export_pdf(d.analysis, d, None, out, jurisdiction=d.jurisdiction)
        assert (world / "r.pdf").stat().st_size > 1000


def test_preview_export_is_stamped_and_reads_the_job_not_the_committed_records(world):
    # A committed project of the same name with a different record count must not leak in.
    jid = add_job(world, project="Notts Park", client="Acme")
    d = ed.load_entry_job_detail(jid)
    path, _ = _export(world, "prev.xlsx", detail=d)
    from openpyxl import load_workbook
    ws = load_workbook(path)["Summary"]
    text = [str(c.value) for row in ws.iter_rows() for c in row if c.value]
    assert ("Preview of the uncommitted Data Entry job 'Notts': figures may change when the job "
            "is committed.") in text
    committed, _ = _export(world, "comm.xlsx")
    pv = {r[0]: r[1] for r in _summary_rows(path)}
    cm = {r[0]: r[1] for r in _summary_rows(committed)}
    assert pv == cm                                                   # same rules, same figures
    ws = load_workbook(path)["Key species"]
    occ = [r[-1] for r in ws.iter_rows(values_only=True) if r and r[0] and str(r[0]).endswith("Key")]
    assert all("Recorded" in (o or "") or "individual" in (o or "") for o in occ) and occ


def test_species_tab_shows_brackets(world):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from Examen.species_tab import SpeciesTab
    sm.set_mark(T_RARE, "Rarus beetle", "old")
    d = ed.load_project_detail(*JOB[:2], survey_year=JOB[2])
    tab = SpeciesTab()
    tab.set_result(d.analysis, d, {})
    shown = {tab.table.item(r, 0).text(): tab.table.item(r, 2).text()
             for r in range(tab.table.rowCount())}
    assert shown["Rarus beetle"].startswith("[") and shown["Rarus beetle"].endswith("]")
    assert not shown["Scarcus beetle"].startswith("[")
