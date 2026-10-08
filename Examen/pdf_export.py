"""
Examen -- PDF assessment report (backlog E3)

Laid out from the assessment workbook via report_model, so every figure, status,
note and stamp is the workbook's own; word_export lays out the same sections as a
Word document. This module does layout only.

    from Examen.pdf_export import export_pdf, workbook_to_pdf
    export_pdf(result, detail, project, "Glory Park assessment.pdf", jurisdiction="England")
    workbook_to_pdf("Glory Park assessment.xlsx", "Glory Park assessment.pdf")

Sections: title and basis of assessment; 1 summary of figures; 2 key species (table,
then accounts with this survey's evidence); 3 habitats; 4 assemblages; 5 guilds;
Appendix A species list; Appendix B status definitions. Every page: title, page
number, run date and Codex version. Designations that do not count in the
jurisdiction are grey italic, as in the workbook. Requires reportlab.
"""
from __future__ import annotations

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, PageBreak,
                                    PageTemplate, Paragraph, Spacer, Table, TableStyle)
    HAS_REPORTLAB = True
except ImportError:  # pragma: no cover
    HAS_REPORTLAB = False

try:
    from Examen.report_model import ACCOUNTS_NOTE, KEY_TABLE, build_report, read_report
except ImportError:  # pragma: no cover
    from report_model import ACCOUNTS_NOTE, KEY_TABLE, build_report, read_report

MOSS = "#4A7C59"
INK = "#1F2937"
MUTED = "#6B7280"
LINE = "#D0D0D0"
NA_GREY = "#9CA3AF"
PALE = "#F4F6F3"

TABLE_WIDTHS = {   # relative column widths per section
    "Habitats": [1.3, 1.6, 0.6, 0.6, 0.6, 0.8],
    "Specific assemblage types": [1.9, 0.65, 0.65, 0.6, 0.75, 0.7, 0.85, 2.0],
    "Feeding guilds": [0.8, 2.0, 0.6],
}


def _esc(s) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _m(v) -> str:
    """Cell value -> Paragraph markup; designations not applying in grey italic."""
    if v is None:
        return ""
    if isinstance(v, list):
        return "".join(_esc(t) if ok else f'<font color="{NA_GREY}"><i>{_esc(t)}</i></font>'
                       for t, ok in v)
    return _esc(v)


def _styles():
    ss = getSampleStyleSheet()
    base = ParagraphStyle("base", parent=ss["Normal"], fontName="Helvetica", fontSize=8.5,
                          leading=10.5, textColor=colors.HexColor(INK))
    return {
        "base": base,
        "small": ParagraphStyle("small", parent=base, fontSize=7.2, leading=8.8),
        "note": ParagraphStyle("note", parent=base, fontSize=7.5, leading=9.5,
                               textColor=colors.HexColor(MUTED), fontName="Helvetica-Oblique"),
        "head": ParagraphStyle("head", parent=base, fontName="Helvetica-Bold", fontSize=7.5,
                               leading=9, textColor=colors.white),
        "title": ParagraphStyle("title", parent=base, fontName="Helvetica-Bold", fontSize=17,
                                leading=21, textColor=colors.HexColor("#2F4858"), spaceAfter=2),
        "subtitle": ParagraphStyle("subtitle", parent=base, fontSize=10.5, leading=13,
                                   textColor=colors.HexColor(MUTED), spaceAfter=10),
        "h1": ParagraphStyle("h1", parent=base, fontName="Helvetica-Bold", fontSize=12.5,
                             leading=15, textColor=colors.HexColor(MOSS), spaceBefore=10, spaceAfter=3),
        "h2": ParagraphStyle("h2", parent=base, fontName="Helvetica-Bold", fontSize=9.5,
                             leading=12, spaceBefore=6, spaceAfter=1),
        "account": ParagraphStyle("account", parent=base, fontSize=8.5, leading=11),
    }


def _widths(fracs, total):
    s = float(sum(fracs))
    return [total * f / s for f in fracs]


def _table(rows, heads, st, widths, italic_cols=(), small=False):
    body = st["small"] if small else st["base"]
    data = [[Paragraph(_esc(h), st["head"]) for h in heads]]
    for r in rows:
        cells = []
        for j in range(len(heads)):
            m = _m(r[j] if j < len(r) else None)
            cells.append(Paragraph(f"<i>{m}</i>" if j in italic_cols and m else m, body))
        data.append(cells)
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(MOSS)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor(LINE)),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(PALE)]),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return t


def _story(rep, st, width):
    out = [Paragraph(_esc(rep["title"]), st["title"]), Paragraph(_esc(rep["subtitle"]), st["subtitle"])]
    bt = Table([[Paragraph(f"<b>{_esc(k)}</b>", st["small"]), Paragraph(_m(v), st["small"])]
                for k, v in rep["basis"]], colWidths=_widths([1.1, 2.4], width))
    bt.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor(LINE)),
                            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(PALE)),
                            ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5)]))
    out += [Paragraph("Basis of assessment", st["h2"]), bt, Spacer(1, 6),
            Paragraph("1  Summary of figures", st["h1"]),
            _table(rep["figures"], ["Measure", "Value", "Basis / note"], st, _widths([1.5, 0.55, 3.2], width))]
    if rep["attribution"]:
        out += [Spacer(1, 4)] + [Paragraph(_esc(a), st["note"]) for a in rep["attribution"]]

    key = rep.get("key")
    out.append(Paragraph("2  Key species", st["h1"]))
    if key and key["subtitle"]:
        out.append(Paragraph(_esc(key["subtitle"]), st["note"]))
    if not key or not key["rows"]:
        out.append(Paragraph("No key species recorded.", st["base"]))
    else:
        out += [Spacer(1, 3), _table(key["rows"], KEY_TABLE, st,
                                     _widths([0.75, 0.8, 0.9, 1.25, 0.95, 1.0, 0.45, 0.95, 1.05], width),
                                     italic_cols={KEY_TABLE.index("Species")}, small=True)]
        for i, a in enumerate(key["accounts"]):
            block = [Paragraph("Species accounts", st["h2"])] if i == 0 else []
            block.append(Paragraph(f"<b><i>{_esc(a['species'])}</i></b>"
                                   + (f" ({_esc(a['common'])})" if a["common"] else "")
                                   + f" — {_m(a['status'])}", st["base"]))
            if a["account"]:
                block.append(Paragraph(_esc(a["account"]), st["account"]))
            bits = ([f"Account: {_esc(a['source'])}"] if a["source"] else []) + \
                   ([f"This survey: {_esc(a['evidence'])}"] if a["evidence"] else [])
            if bits:
                block.append(Paragraph("   ".join(bits), st["note"]))
            block.append(Spacer(1, 5))
            out.append(KeepTogether(block))
        out.append(Paragraph(ACCOUNTS_NOTE, st["note"]))

    for n, (label, t) in enumerate(rep["tables"], start=3):
        out.append(Paragraph(f"{n}  {_esc(label)}", st["h1"]))
        if t["subtitle"]:
            out.append(Paragraph(_esc(t["subtitle"]), st["note"]))
        if t["heads"]:
            fr = TABLE_WIDTHS.get(label, [1] * len(t["heads"]))[:len(t["heads"])]
            out += [Spacer(1, 3), _table(t["rows"], t["heads"], st, _widths(fr, width), small=True)]
        out += [Paragraph(_esc(x), st["note"]) for x in t["notes"]]

    ap = rep.get("appendix")
    if ap:
        out += [PageBreak(), Paragraph("Appendix A  Species list", st["h1"])]
        if ap["subtitle"]:
            out.append(Paragraph(_esc(ap["subtitle"]), st["note"]))
        heads = ap["heads"]
        fr = [0.85, 1.0, 1.55, 1.0, 0.9, 0.4, 0.95, 1.05, 0.6][:len(heads)]
        out += [Spacer(1, 3), _table(ap["rows"], heads, st, _widths(fr, width),
                                     italic_cols={heads.index("Species")} if "Species" in heads else (),
                                     small=True)]
        if ap["footer"]:
            ft = Table([[Paragraph(f"<b>{_esc(k)}</b>", st["small"]), Paragraph(_m(v), st["small"])]
                        for k, v in ap["footer"]], colWidths=_widths([2, 1], width * 0.45), hAlign="LEFT")
            ft.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor(LINE))]))
            out += [Spacer(1, 4), ft]

    if rep["definitions"]:
        out += [PageBreak(), Paragraph("Appendix B  Status definitions", st["h1"])]
        data, extra = [], []
        for i, d in enumerate(rep["definitions"]):
            if d[0] == "section":
                data.append([Paragraph(f"<b>{_esc(d[1])}</b>", st["base"]), ""])
                extra += [("SPAN", (0, i), (1, i)), ("TOPPADDING", (0, i), (1, i), 6)]
            else:
                data.append([Paragraph(_m(d[1]), st["small"]), Paragraph(_m(d[2]), st["small"])])
        t = Table(data, colWidths=_widths([1.3, 3.7], width))
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 2)] + extra))
        out.append(t)
    return out


def report_to_pdf(rep, pdf_path):
    """Lay out report sections (report_model) as a PDF."""
    if not HAS_REPORTLAB:
        raise ImportError("reportlab is required for the PDF report: py -3.14 -m pip install reportlab")
    st = _styles()
    page_w, page_h = A4
    margin = 16 * mm
    width = page_w - 2 * margin
    title = rep["title"]
    footer = f"Examen — run {rep['run']}" + (f" — Codex {rep['codex']}" if rep["codex"] else "")

    doc = BaseDocTemplate(pdf_path, pagesize=A4, leftMargin=margin, rightMargin=margin,
                          topMargin=18 * mm, bottomMargin=16 * mm, title=title,
                          author="Flauna Ecology", subject="Invertebrate assemblage assessment")

    def decorate(canvas, d):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor(MUTED))
        canvas.drawString(margin, page_h - 11 * mm, title)
        canvas.setStrokeColor(colors.HexColor(LINE))
        canvas.setLineWidth(0.4)
        canvas.line(margin, page_h - 12.5 * mm, page_w - margin, page_h - 12.5 * mm)
        canvas.drawString(margin, 9 * mm, footer)
        canvas.drawRightString(page_w - margin, 9 * mm, f"Page {d.page}")
        canvas.restoreState()

    doc.addPageTemplates([PageTemplate(id="page", onPage=decorate,
                                       frames=[Frame(margin, 16 * mm, width, page_h - 34 * mm, id="body")])])
    doc.build(_story(rep, st, width))
    return pdf_path


def workbook_to_pdf(xlsx_path, pdf_path):
    return report_to_pdf(read_report(xlsx_path), pdf_path)


def export_pdf(result, detail, project, path, jurisdiction="England",
               sqs_basis="Pantheon published", pooled_years=False):
    return report_to_pdf(build_report(result, detail, project, jurisdiction=jurisdiction,
                                      sqs_basis=sqs_basis, pooled_years=pooled_years), path)
