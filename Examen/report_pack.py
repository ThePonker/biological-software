"""
Examen -- the report pack: results tables and species accounts, in the report template's style.

A Word document of the results sections, ready to paste into the author's report template:
survey visits (with weather), species by group, Key Species with a short account block each,
biotopes, assemblage types, the species list (Appendix C) and the benchmark sentence. Every figure
is read from the assessment workbook through report_model.build_report; nothing is recounted.

    from Examen.report_pack import export_report_pack
    export_report_pack(result, detail, project, "Site report pack.docx", jurisdiction="England")

Requires python-docx. No consultant or index author is named anywhere in the document.
"""
from __future__ import annotations

try:
    from docx import Document
    from docx.enum.section import WD_ORIENT
    from docx.enum.text import WD_BREAK, WD_COLOR_INDEX
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor
    HAS_DOCX = True
except ImportError:  # pragma: no cover
    HAS_DOCX = False

from Examen import benchmark
from Examen import report_pack_tables as T
from Examen.report_model import KEY_TABLE, build_report, plain
from Examen.word_export import _repeat_header, _runs, _shade
from shared import visit_weather

# Document colours of the report template (not UI colours, so theme() does not apply)
LEAD, SOFT, ACCENT = "362554", "554475", "2F7A5A"
TINT, RULE, INK, GREY = "F1EFF6", "D1CCDE", "1D1829", "5D5868"
HEAD_FONT, BODY_FONT = "Georgia", "Calibri"
BODY_PT, CELL_PT, CAPTION_PT = 10.5, 9, 8.5
MARGIN_CM = 2.5
TEXT_CM = 16.0           # A4 width less two margins
PLACEHOLDER = "[write account]"


def _rgb(hex_):
    return RGBColor.from_string(hex_)


def _set_font(style, name, size=None, colour=None, bold=None):
    style.font.name = name
    rpr = style.element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.append(fonts)
    for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        if fonts.get(qn(attr)) is not None:
            del fonts.attrib[qn(attr)]
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        fonts.set(qn(attr), name)
    if size:
        style.font.size = Pt(size)
    if colour:
        style.font.color.rgb = _rgb(colour)
    if bold is not None:
        style.font.bold = bold


def _new_document():
    doc = Document()
    _set_font(doc.styles["Normal"], BODY_FONT, BODY_PT, INK)
    for name, size, col in (("Title", 22, LEAD), ("Heading 1", 16, LEAD),
                            ("Heading 2", 13, LEAD), ("Heading 3", 11, SOFT)):
        _set_font(doc.styles[name], HEAD_FONT, size, col, bold=name != "Title")
    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.PORTRAIT
    sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, side, Cm(MARGIN_CM))
    return doc


def _note(doc, text):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.italic = True
    r.font.size = Pt(CAPTION_PT)
    r.font.color.rgb = _rgb(GREY)
    return p


def _caption(doc, text):
    p = _note(doc, text)
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.space_after = Pt(3)
    return p


def _bottom_rule(cell):
    tcPr = cell._tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    el = OxmlElement("w:bottom")
    for k, v in (("val", "single"), ("sz", "4"), ("space", "0"), ("color", RULE)):
        el.set(qn(f"w:{k}"), v)
    borders.append(el)
    tcPr.append(borders)


def _table(doc, heads, rows, widths_cm, italic_cols=(), bold_last=False):
    """House-style table: lead header (white bold, repeats), tint on alternate rows, rule-coloured
    bottom borders, no vertical lines."""
    t = doc.add_table(rows=1, cols=len(heads))
    hdr = t.rows[0]
    _repeat_header(hdr)
    for j, h in enumerate(heads):
        c = hdr.cells[j]
        _runs(c.paragraphs[0], h, bold=True, size=CELL_PT)
        c.paragraphs[0].runs[0].font.color.rgb = _rgb("FFFFFF")
        _shade(c, LEAD)
        c.paragraphs[0].paragraph_format.space_after = Pt(2)
    for n, r in enumerate(rows):
        row = t.add_row()
        trPr = row._tr.get_or_add_trPr()
        trPr.append(OxmlElement("w:cantSplit"))
        last = bold_last and n == len(rows) - 1
        for j in range(len(heads)):
            c = row.cells[j]
            _runs(c.paragraphs[0], r[j] if j < len(r) else "", italic=j in italic_cols,
                  bold=last, size=CELL_PT)
            c.paragraphs[0].paragraph_format.space_after = Pt(2)
            if n % 2:
                _shade(c, TINT)
            _bottom_rule(c)
    t.autofit = False
    widths = [Cm(w) for w in widths_cm]
    for col, w in zip(t._tbl.tblGrid.findall(qn("w:gridCol")), widths):
        col.set(qn("w:w"), str(int(w.twips)))
    for row in t.rows:
        for j, w in enumerate(widths):
            row.cells[j].width = w
    doc.add_paragraph()
    return t


def _fit(widths):
    """Scale column widths to the text width."""
    k = TEXT_CM / sum(widths)
    return [w * k for w in widths]


def _heading(doc, text, level=1):
    return doc.add_heading(text, level=level)


def _tables_section(doc, title, caption, heads, rows, widths, none_text, **kw):
    _heading(doc, title)
    if not rows:
        doc.add_paragraph(none_text)
        return
    _caption(doc, caption)
    _table(doc, heads, rows, _fit(widths), **kw)


def _account(doc, acc, records):
    h = doc.add_heading("", level=3)
    _runs(h, acc["species"], italic=True)
    if acc["common"]:
        _runs(h, f"  {acc['common']}")
    p = doc.add_paragraph()
    _runs(p, "Status: ", bold=True)
    _runs(p, acc["status"] if acc["status"] not in (None, "") else "none held")
    p = doc.add_paragraph()
    _runs(p, "Records: ", bold=True)
    _runs(p, "; ".join(records) if records else "none held")
    own = acc["account"] if acc["account"] and not acc["source"] else ""
    if own:          # the author's account (the workbook's "Your account"), paragraph by paragraph
        for para in (t.strip() for t in own.splitlines()):
            if para:
                doc.add_paragraph(para)
        return
    p = doc.add_paragraph()
    p.add_run(PLACEHOLDER).font.highlight_color = WD_COLOR_INDEX.YELLOW


def _key_tvks(result):
    out = {}
    for k in result.key_species:
        out[k.species_name] = k.tvk
        if getattr(k, "recorded_note", ""):
            out[f"{k.species_name} ({k.recorded_note})"] = k.tvk
    return out


def _benchmark_line(rep, mode, current=None):
    try:
        rows = benchmark.benchmark_rows(mode, current=current)
    except Exception:  # noqa: BLE001 -- a benchmark that cannot be built never stops the pack
        return ""
    return T.benchmark_sentence(benchmark.benchmark_summary(rows),
                                T.figure(rep, "% Key Species (status only)"))


def _mode_of(detail):
    from Examen.examen_data import AnalysisMode
    try:
        return AnalysisMode(getattr(detail.site, "mode", ""))
    except ValueError:
        return AnalysisMode.CODEX_FULL


def export_report_pack(result, detail, project, path, jurisdiction="England",
                       pooled_years=None):
    """Write the report pack to `path`. Returns the path."""
    if not HAS_DOCX:
        raise ImportError("python-docx is required for the report pack: "
                          "py -3.14 -m pip install python-docx")
    pooled = bool(pooled_years)
    rep = build_report(result, detail, project, jurisdiction=jurisdiction, pooled_years=pooled)
    scope = T.survey_scope(detail, project, pooled)
    basis = {k: v for k, v in rep["basis"]}
    doc = _new_document()
    site = getattr(detail, "site", None)
    year = scope[2]
    doc.add_heading(f"{scope[0]}{f' — {year}' if year else ''}", level=0)
    _note(doc, "Results tables and species accounts")
    if basis.get("Preview"):
        _note(doc, plain(basis["Preview"]))
    if pooled:
        _note(doc, f"Survey scope: {plain(basis.get('Survey scope', 'all years pooled'))}.")

    weather = (visit_weather.weather_for(scope[0], scope[1])
               if visit_weather.table_ready() else {})
    _tables_section(doc, "Survey visits", "Table 4.1 Survey visits",
                    ["Date", "Visit", "Temperature", "Wind", "Cloud"], T.visit_table(scope, weather),
                    [4, 1.8, 3.4, 3.4, 3.4], "No survey dates are held.")
    _tables_section(doc, "Species recorded by group",
                    "Table 5.1 Species recorded by group (Key Species in brackets)",
                    ["Group", "Species (Key Species)"], T.group_table(rep), [10, 6],
                    "No species recorded.", bold_last=True)

    key = rep.get("key") or {"rows": [], "accounts": []}
    _heading(doc, "Key Species")
    if key["rows"]:
        _caption(doc, "Table 5.2 Key Species")
        i = {c: KEY_TABLE.index(c) for c in KEY_TABLE}
        rows = [[r[i["Species"]], r[i["Common name"]],
                 " / ".join(x for x in (plain(r[i["Order"]]), plain(r[i["Family"]])) if x),
                 r[i["Conservation status"]], r[i["SQS"]]] for r in key["rows"]]
        _table(doc, ["Species", "Common name", "Order / family", "Conservation status", "SQS"],
               rows, _fit([4.1, 3.0, 3.1, 3.6, 2.2]), italic_cols={0})
    doc.add_paragraph(T.key_sentence(rep))

    _heading(doc, "Species accounts")
    if not key["accounts"]:
        doc.add_paragraph("No Key Species recorded.")
    tvk_of = _key_tvks(result)
    recs = T.records_by_tvk({tvk_of.get(a["species"]) for a in key["accounts"]}, scope)
    for acc in key["accounts"]:
        _account(doc, acc, recs.get(tvk_of.get(acc["species"]), []))

    _tables_section(doc, "Broad biotopes", "Table 5.3 Broad biotopes",
                    ["Broad biotope", "Species", "Scoring species", "SQI", "% national pool"],
                    T.biotope_rows(rep), [5, 2.5, 3, 2.5, 3], "No broad biotope associations.")
    heads, sats = T.sat_rows(rep)
    _tables_section(doc, "Specific assemblage types (SATs)",
                    "Table 5.4 Specific assemblage types (SATs)", heads, sats,
                    [4.2, 1.3, 1.4, 1.4, 1.7, 1.6, 1.8, 3.0], "No assemblage types recorded.")

    ap = rep.get("appendix")
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    _heading(doc, "Appendix C Species list")
    if ap and ap["rows"]:
        _caption(doc, "Appendix C Species list, in taxonomic order")
        h = ap["heads"]
        cols = [h.index(c) for c in ("Species", "Common name", "Order", "Family",
                                     "Conservation status")]
        _table(doc, ["Species", "Common name", "Order", "Family", "Conservation status"],
               [[r[c] if c < len(r) else "" for c in cols] for r in ap["rows"]],
               _fit([4.6, 3.4, 2.4, 2.6, 3.0]), italic_cols={0})

    line = _benchmark_line(rep, _mode_of(detail), scope[:3])
    if line:
        _heading(doc, "Benchmark")
        doc.add_paragraph(line)
    doc.core_properties.title = f"{scope[0]} report pack"
    doc.save(path)
    return path
