"""Round A: the report pack (Examen.report_pack) -- headings, tables, figures from the workbook,
brackets, weather, preview note, no consultant names. Purpose-made databases only."""
import sqlite3

import pytest
from _round_a_fixture import NAMES, T_RARE, T_SCARCE, T_VU, add_committed, add_job, build

pytest.importorskip("docx")
from docx import Document  # noqa: E402

import paths  # noqa: E402
from Examen import benchmark, report_pack  # noqa: E402
from Examen import status_marks as sm  # noqa: E402
from Examen import examen_data as ed  # noqa: E402
from Examen.report_model import build_report  # noqa: E402

JOB = ("Notts Park", "Acme", "2026")
WEATHER_DDL = ("CREATE TABLE visit_weather (id INTEGER PRIMARY KEY, project_name TEXT, "
               "client TEXT, date TEXT, temperature TEXT, wind TEXT, cloud TEXT, notes TEXT, "
               "updated_at TEXT)")


@pytest.fixture()
def world(tmp_path, monkeypatch):
    build(tmp_path, monkeypatch)
    add_committed(tmp_path)
    c = sqlite3.connect(str(tmp_path / "observatum.db"))
    c.execute("UPDATE assessment_records SET grid_ref='SK 123 456', method='pitfall', "
              "determiner='A. Smith', visit_number='1' WHERE date='2026-05-10'")
    c.execute("UPDATE assessment_records SET grid_ref='SK 124 457', method='sweep', "
              "visit_number='2' WHERE date='2026-06-11'")
    c.commit()
    c.close()
    monkeypatch.setattr(benchmark, "benchmark_rows", lambda mode, jurisdiction=None, current=None: [])
    return tmp_path


def _pack(world, name="p.docx", detail=None, project=None, **kw):
    detail = detail or ed.load_project_detail(*JOB[:2], survey_year=JOB[2])
    path = str(world / name)
    report_pack.export_report_pack(detail.analysis, detail, project, path,
                                   jurisdiction=detail.jurisdiction, **kw)
    return Document(path), detail


def _headings(doc):
    return [p.text for p in doc.paragraphs if p.style.name.startswith(("Heading 1", "Title"))]


def _text(doc):
    out = [p.text for p in doc.paragraphs]
    for t in doc.tables:
        out += [c.text for r in t.rows for c in r.cells]
    return "\n".join(out)


def _cap_tables(doc):
    return {p.text: t for p, t in zip([p for p in doc.paragraphs if p.text.startswith(
        ("Table ", "Appendix C Species list,"))], doc.tables)}


def test_headings_and_tables_in_order(world):
    doc, _ = _pack(world)
    assert _headings(doc) == ["Notts Park — 2026", "Survey visits",
                              "Species recorded by group", "Key Species", "Species accounts",
                              "Broad biotopes", "Specific assemblage types (SATs)",
                              "Appendix C Species list"]
    caps = [p.text for p in doc.paragraphs if p.text.startswith(("Table ", "Appendix C Species list,"))]
    assert caps[:3] == ["Table 4.1 Survey visits",
                        "Table 5.1 Species recorded by group (Key Species in brackets)",
                        "Table 5.2 Key Species"]
    assert caps[-1].startswith("Appendix C")
    assert "No broad biotope associations." in _text(doc)     # the fixture holds no biotope data
    assert len(doc.tables) == len(caps)


def test_key_counts_equal_workbook_summary(world):
    doc, detail = _pack(world)
    rep = build_report(detail.analysis, detail, None, jurisdiction=detail.jurisdiction)
    key_n = next(v for lab, v, _ in rep["figures"] if lab == "Key Species")
    t = doc.tables[1]                                  # Table 5.1
    last = [c.text for c in t.rows[-1].cells]
    assert last[0] == "All groups" and last[1].endswith(f"({key_n})")
    assert last[1].startswith(str(detail.analysis.total_species))
    assert len(doc.tables[2].rows) - 1 == key_n        # Table 5.2: one row per Key Species
    assert f"recorded {key_n} Key Species" in _text(doc)
    for name in (NAMES[T_RARE], NAMES[T_VU], NAMES[T_SCARCE]):
        assert name in _text(doc)


def test_species_account_blocks(world):
    doc, _ = _pack(world)
    text = _text(doc)
    assert text.count(report_pack.PLACEHOLDER) == 3
    assert "Records: 10 May 2026, SK 123 456, pitfall, n=1, det. A. Smith; " \
           "11 June 2026, SK 124 457, sweep, n=1" in text
    hl = [r for p in doc.paragraphs for r in p.runs if r.text == report_pack.PLACEHOLDER]
    assert hl and all(r.font.highlight_color is not None for r in hl)
    sci = [r for p in doc.paragraphs if p.style.name == "Heading 3" for r in p.runs if r.italic]
    assert {r.text for r in sci} >= {NAMES[T_RARE]}


def test_bracketed_status_appears_bracketed(world):
    sm.set_mark(T_RARE, NAMES[T_RARE], "old")
    doc, _ = _pack(world)
    row = next(r for r in doc.tables[2].rows if NAMES[T_RARE] in r.cells[0].text)
    status = row.cells[3].text
    assert "[" in status and "]" in status
    assert "left out" in _text(doc)                    # the sentence gives the revised figure


def test_weather_filled_and_blank(world):
    doc, _ = _pack(world)                              # no visit_weather table at all
    rows = [[c.text for c in r.cells] for r in doc.tables[0].rows[1:]]
    assert [r[0] for r in rows] == ["10 May 2026", "11 June 2026"]
    assert [r[1] for r in rows] == ["1", "2"] and all(r[2:] == ["", "", ""] for r in rows)
    c = sqlite3.connect(str(paths.OBSERVATUM_DB))
    c.execute(WEATHER_DDL)
    c.execute("INSERT INTO visit_weather (project_name, client, date, temperature, wind, cloud) "
              "VALUES ('Notts Park','Acme','2026-05-10','18 C','Beaufort 2','3 oktas')")
    c.commit()
    c.close()
    doc, _ = _pack(world, "w.docx")
    rows = [[c.text for c in r.cells] for r in doc.tables[0].rows[1:]]
    assert rows[0][2:] == ["18 C", "Beaufort 2", "3 oktas"] and rows[1][2:] == ["", "", ""]


def test_preview_note_and_visits_from_staged_rows(world):
    jid = add_job(world, name="Notts job", project="Preview Park", client="Acme")
    c = sqlite3.connect(str(paths.OBSERVATUM_DB))
    c.execute("UPDATE entry_staging SET grid_ref='SK 9 9', method='net', determiner='B. Jones'"
              " WHERE job_id=?", (jid,))
    c.commit()
    c.close()
    detail = ed.load_entry_job_detail(jid)
    doc, _ = _pack(world, "pv.docx", detail=detail)
    note = [p for p in doc.paragraphs if p.text.startswith("Preview of the uncommitted")]
    assert note and "'Notts job'" in note[0].text and note[0].runs[0].italic
    assert [r.cells[0].text for r in doc.tables[0].rows[1:]] == ["10 May 2026", "11 June 2026"]
    assert "net, n=1, det. B. Jones" in _text(doc)
    plain_doc, _ = _pack(world, "np.docx")
    assert "Preview of the uncommitted" not in _text(plain_doc)


def test_pooled_line(world):
    doc, _ = _pack(world, "po.docx", pooled_years=True)
    assert "Survey scope: all years pooled." in _text(doc)


def test_benchmark_sentence_only_with_surveys(world, monkeypatch):
    doc, _ = _pack(world)
    assert "comparable surveys" not in _text(doc)
    rows = [{"included": True, "pct": p} for p in (2.0, 4.0, 6.0, 8.0)]
    monkeypatch.setattr(benchmark, "benchmark_rows", lambda mode, jurisdiction=None, current=None: rows)
    doc, _ = _pack(world, "b.docx")
    assert ("Across the 4 comparable surveys, the proportion of status-only Key Species ranged "
            "from 2.0% to 8.0% (median 5.0%, interquartile range 3.5–6.5%); this site's "
            "figure is ") in _text(doc)


def test_no_consultant_names(world, monkeypatch):
    rows = [{"included": True, "pct": 5.0}]
    monkeypatch.setattr(benchmark, "benchmark_rows", lambda mode, jurisdiction=None, current=None: rows)
    doc, _ = _pack(world)
    text = _text(doc)
    for name in ("Telfer", "Kirby", "Wilson", "Jukes", "Webb"):
        assert name not in text


def test_a4_and_house_style(world):
    doc, _ = _pack(world)
    s = doc.sections[0]
    assert round(s.page_width.cm, 1) == 21.0 and round(s.left_margin.cm, 1) == 2.5
    assert doc.styles["Heading 1"].font.name == "Georgia"
    assert str(doc.styles["Normal"].font.color.rgb) == report_pack.INK
    head = doc.tables[0].rows[0]
    assert 'w:val="clear"' in head.cells[0]._tc.xml and report_pack.LEAD in head.cells[0]._tc.xml


def test_pack_benchmark_excludes_the_survey_being_reported(world, monkeypatch):
    seen = []
    monkeypatch.setattr(benchmark, "benchmark_rows",
                        lambda mode, jurisdiction=None, current=None: seen.append(current) or [])
    _pack(world)
    assert seen == [("Notts Park", "Acme", "2026")]
    jid = add_job(world, name="Notts")
    seen.clear()
    _pack(world, "pv.docx", detail=ed.load_entry_job_detail(jid))
    assert seen == [("Notts Park", "Acme", "2026")]


def test_own_account_replaces_placeholder(world, monkeypatch):
    """The author's account (the workbook's "Your account") goes in place of the placeholder;
    a quoted review account does not -- that species keeps the placeholder."""
    from Examen import workbook_export as we
    real = we._profiles

    def profiles(tvks):
        out = real(tvks)
        out[T_RARE] = ("First paragraph of my account.\nSecond paragraph.", "Your account")
        out[T_SCARCE] = ("[Quoted from A Review 2020] Review text.", "Quoted - A Review 2020")
        return out
    monkeypatch.setattr(we, "_profiles", profiles)
    doc, _ = _pack(world)
    paras = [p.text for p in doc.paragraphs]
    assert "First paragraph of my account." in paras and "Second paragraph." in paras
    assert "Review text." not in _text(doc)
    assert _text(doc).count(report_pack.PLACEHOLDER) == 2
