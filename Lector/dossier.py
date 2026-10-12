"""Word dossier (+ Excel index) for one species or saved search, from lector.db.

    python -m Lector export --name "Lamia textor" --docx [--by-journal] [--pdf]

Needs python-docx (Word) and, for the Excel index, openpyxl:
    pip install python-docx openpyxl
Layout: summary table -> one entry per page (5-line excerpt, name in bold,
BHL link, authors and article title where BHL gives them, other scans of the
same text, your notes) -> Appendix A index/contents pages -> Appendix B pages
where the name is not in the OCR text. PDF: Lector.pdf.
"""
from datetime import date

from . import config
from .entries import Entry, build_entries, citation, prepare_row, source as _source  # noqa: F401
from .excerpts import copyright_flag, index_reason, name_pattern, split_marked

LINK_COLOUR = "34437A"
HEAD_COLOUR = "1E2226"
MUTED = "5B5F63"
FLAG_COLOUR = "8A5A00"


# --- python-docx helpers ----------------------------------------------------
def _docx():
    try:
        import docx                                   # noqa: F401
    except ImportError:
        raise SystemExit("✗ The Word export needs python-docx.\n"
                         "  Install it once with:  pip install python-docx openpyxl")
    from docx import Document
    from docx.enum.text import WD_BREAK
    from docx.opc.constants import RELATIONSHIP_TYPE as RT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor
    return Document, WD_BREAK, RT, OxmlElement, qn, Cm, Pt, RGBColor


Document, WD_BREAK, RT, OxmlElement, qn, Cm, Pt, RGBColor = (None,) * 8


def _link(par, text, url=None, anchor=None):
    """Append a hyperlink run: external url, or internal bookmark anchor."""
    h = OxmlElement("w:hyperlink")
    if url:
        h.set(qn("r:id"), par.part.relate_to(url, RT.HYPERLINK, is_external=True))
    else:
        h.set(qn("w:anchor"), anchor)
    r, rpr = OxmlElement("w:r"), OxmlElement("w:rPr")
    for tag, val in (("w:color", LINK_COLOUR), ("w:u", "single")):
        el = OxmlElement(tag)
        el.set(qn("w:val"), val)
        rpr.append(el)
    t = OxmlElement("w:t")
    t.text = text
    t.set(qn("xml:space"), "preserve")
    r.append(rpr)
    r.append(t)
    h.append(r)
    par._p.append(h)


def _bookmark(par, name, bid):
    start, end = OxmlElement("w:bookmarkStart"), OxmlElement("w:bookmarkEnd")
    start.set(qn("w:id"), str(bid))
    start.set(qn("w:name"), name)
    end.set(qn("w:id"), str(bid))
    par._p.insert(0, start)
    par._p.append(end)


def _run(par, text, bold=False, italic=False, size=None, colour=None):
    r = par.add_run(text)
    r.bold, r.italic = bold, italic
    if size:
        r.font.size = Pt(size)
    if colour:
        r.font.color.rgb = RGBColor.from_string(colour)
    return r


def _shade(cell, fill):
    pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    pr.append(shd)


def _table(doc, headers, widths):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.autofit = False                     # Word honours the widths below
    for col, w in zip(t.columns, widths):
        col.width = Cm(w)
    for cell, text, w in zip(t.rows[0].cells, headers, widths):
        cell.width = Cm(w)
        _shade(cell, "E6E1D5")
        _run(cell.paragraphs[0], text, bold=True, size=9)
    return t


def _row(table, widths):
    cells = table.add_row().cells
    for c, w in zip(cells, widths):
        c.width = Cm(w)
    return cells


def _page_footer(section, species):
    p = section.footer.paragraphs[0]
    _run(p, f"Lector · {species} · page ", size=8, colour=MUTED)
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    r = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.text = "1"
    r.append(t)
    fld.append(r)
    p._p.append(fld)


# --- document ---------------------------------------------------------------
def _setup(doc, species):
    normal = doc.styles["Normal"]
    normal.font.name = "Cambria"
    normal.font.size = Pt(10.5)
    for name in ("Title", "Heading 1", "Heading 2"):
        st = doc.styles[name]
        st.font.name = "Cambria"
        st.font.color.rgb = RGBColor.from_string(HEAD_COLOUR)
    doc.styles["Heading 2"].font.size = Pt(11.5)
    sec = doc.sections[0]
    sec.page_height, sec.page_width = Cm(29.7), Cm(21.0)
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, side, Cm(2.0))
    _page_footer(sec, species)


def _front(doc, species, rows, main, index, no_match, by_journal, about=None):
    title = doc.add_paragraph(style="Title")
    _run(title, species, italic=True)
    p = doc.add_paragraph()
    _run(p, "Literature found in the Biodiversity Heritage Library", size=13, colour=MUTED)
    tvk = next((r["tvk"] for r in rows if r["tvk"]), None)
    names = sorted({n for r in rows for n in (r["matched_names"] or "").split(",") if n})
    about = list(about or [])
    merged = sum(len(e.copies) for e in main)
    facts = [("TVK", tvk or "not linked to UKSI"),
             ("Names searched", ", ".join(names)),
             ("Generated", date.today().strftime("%d %B %Y")),
             ("Pages", f"{len(rows)} harvested: {len(main)} entries"
                       f" ({merged} duplicate scans merged), {len(index)} index or"
                       f" contents pages, {len(no_match)} without the name in the text"),
             ("Order", "by journal, then year" if by_journal else "by year")] + about
    for label, value in facts:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(0)
        _run(p, f"{label}: ", bold=True, size=9.5)
        _run(p, value, size=9.5)
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    _run(p, "Excerpts are uncorrected OCR text. Check names, dates and localities "
            "against the page image (follow the BHL link) before citing or "
            "entering a record.", italic=True, size=9.5, colour=MUTED)


def _summary(doc, main):
    doc.add_heading("Summary", level=1)
    widths = (1.2, 1.4, 10.6, 2.0, 1.8)
    t = _table(doc, ("No.", "Year", "Source", "Type", "BHL"), widths)
    for e in main:
        r = e.row
        c = _row(t, widths)
        _link(c[0].paragraphs[0], str(e.number), anchor=f"entry{e.number}")
        _run(c[1].paragraphs[0], str(r["year"] or "?"), size=9)
        _run(c[2].paragraphs[0], _source(r), size=9)
        if e.copies:
            _run(c[2].paragraphs[0], f"  (+{len(e.copies)} other scan"
                 f"{'s' if len(e.copies) > 1 else ''})", size=8, colour=MUTED)
        _run(c[3].paragraphs[0], r["page_type"] or "", size=9)
        _link(c[4].paragraphs[0], "page", url=r["page_url"])


def _entry(doc, e, include_notes=True):
    r = e.row
    h = doc.add_heading(level=2)
    _run(h, f"{e.number}.  {r['year'] or '?'} · {_source(r)}")
    _bookmark(h, f"entry{e.number}", 1000 + e.number)
    pattern = name_pattern(r["names"])
    for i, lines in enumerate(e.excerpts):
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.8)
        p.paragraph_format.space_after = Pt(4)
        if i:
            _run(p, "…", colour=MUTED)
            p.runs[-1].add_break(WD_BREAK.LINE)
        # match across line ends too, so 'Lamia' / 'textor' split over two
        # lines is still set in bold
        for text, is_name in split_marked("\n".join(lines), pattern):
            for k, piece in enumerate(text.split("\n")):
                if k:
                    (p.runs[-1] if p.runs else _run(p, "")).add_break(WD_BREAK.LINE)
                if piece:
                    _run(p, piece, bold=is_name, size=10)
    p = doc.add_paragraph()
    _link(p, "View page on BHL", url=r["page_url"])
    _run(p, f"   page {r['page_id']} · matched as {r['matched_names']}"
            f" · {r['text_source'] or 'text'}", size=8.5, colour=MUTED)
    for c in e.copies:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.8)
        _run(p, "Same text also at: ", size=8.5, colour=MUTED)
        _link(p, f"{citation(c)}", url=c["page_url"])
    flag = copyright_flag(r)
    if flag:
        p = doc.add_paragraph()
        _run(p, flag, italic=True, size=8.5, colour=FLAG_COLOUR)
    if include_notes and (r["notes"] or r["review_tag"]):
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.8)
        _run(p, "Your note: ", bold=True, size=9)
        tag = f"[{r['review_tag']}] " if r["review_tag"] else ""
        _run(p, tag + (r["notes"] or ""), size=9)


def _appendix(doc, heading, intro, entries, reason):
    doc.add_heading(heading, level=1).paragraph_format.page_break_before = True
    _run(doc.add_paragraph(), intro, italic=True, size=9.5, colour=MUTED)
    if not entries:
        _run(doc.add_paragraph(), "None.", size=9.5)
        return
    widths = (1.4, 11.2, 2.6, 1.8)
    t = _table(doc, ("Year", "Source", "Note", "BHL"), widths)
    for e in entries:
        c = _row(t, widths)
        _run(c[0].paragraphs[0], str(e.row["year"] or "?"), size=9)
        _run(c[1].paragraphs[0], _source(e.row), size=9)
        _run(c[2].paragraphs[0], reason(e.row), size=9)
        _link(c[3].paragraphs[0], "page", url=e.row["page_url"])


def write_docx(species, rows, path, by_journal=False, include_appendices=True,
               include_notes=True, extra_names=(), about=None, merge_duplicates=True,
               keep=None):
    """Write the Word dossier. Returns (main, index, no_match) entry lists."""
    global Document, WD_BREAK, RT, OxmlElement, qn, Cm, Pt, RGBColor
    Document, WD_BREAK, RT, OxmlElement, qn, Cm, Pt, RGBColor = _docx()
    main, index, no_match = build_entries(rows, by_journal, extra_names, merge_duplicates, keep)
    rows = [e.row for e in main + index + no_match] + [c for e in main for c in e.copies]
    doc = Document()
    _setup(doc, species)
    _front(doc, species, rows, main, index, no_match, by_journal, about)
    _summary(doc, main)
    doc.add_heading("Entries", level=1).paragraph_format.page_break_before = True
    for e in main:
        _entry(doc, e, include_notes)
    if not include_appendices:
        doc.save(str(path))
        return main, index, no_match
    _appendix(doc, "Appendix A · Index and contents pages",
              "Pages where the name appears in an index, contents list or list of "
              "illustrations. Follow the page numbers to find the text itself.",
              index, lambda r: index_reason(r))
    _appendix(doc, "Appendix B · Name not found in the page text",
              "BHL's name index lists these pages, but the name is not in the OCR "
              "text: often a plate, a caption or an OCR misreading. Check the image.",
              no_match, lambda r: "no text fetched" if r["fetched_at"] is None
              else "not in OCR text")
    doc.save(str(path))
    return main, index, no_match


NO_AUTHORS_NOTE = "Authors and article titles: none given by BHL for these pages"
OPTIONAL_COLUMNS = {"Authors": "authors", "Article title": "article_title"}
XLSX_WIDTHS = {"Entry": 7, "Year": 7, "Title": 48, "Volume": 10, "Page": 12, "Page type": 14,
               "Section": 12, "Same text as entry": 10, "Matched names": 24, "Rights check": 10,
               "BHL link": 44, "Page ID": 11, "Excerpt": 80, "Authors": 24,
               "Article title": 40, "Review": 14, "Notes": 40, "Citation": 60}


def present_columns(rows, columns=OPTIONAL_COLUMNS):
    """{header: True/False}: does any row give this optional column a value? BHL gives
    authors and article titles only for article 'parts' (few, mostly modern papers),
    so on most searches every row is empty and the column is left out."""
    return {h: any(str(r.get(k) or "").strip() for r in rows) for h, k in columns.items()}


def write_xlsx(path, main, index, no_match, about=()):
    """Companion index for sorting and checking. Returns None if no openpyxl.
    Authors / Article title appear only when some row has one (see present_columns);
    the About sheet says so when they are left out."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
    except ImportError:
        return None
    section_names = {"main": "Entries", "index": "Appendix A", "no_match": "Appendix B"}
    records = []

    def add(r, entry_no, section, same_as, excerpts):
        r = prepare_row(r)
        records.append({
            "Entry": entry_no, "Year": r["year"], "Title": r["title"], "Volume": r["volume"],
            "Page": r["page_label"], "Page type": r["page_type"],
            "Section": section_names[section], "Same text as entry": same_as,
            "Matched names": r["matched_names"],
            "Rights check": "check" if copyright_flag(r) else "", "BHL link": r["page_url"],
            "Page ID": r["page_id"],
            "Excerpt": " / ".join(" ".join(x) for x in excerpts)[:2000],
            "Authors": r["authors"], "Article title": r["article_title"],
            "Review": r["review_status"] or r["statuses"], "Notes": r["notes"],
            "Citation": citation(r)})

    for e in main:
        add(e.row, e.number, "main", None, e.excerpts)
        for c in e.copies:
            add(c, None, "main", e.number, e.excerpts)
    for e in index + no_match:
        add(e.row, None, e.section, None, e.excerpts)
    present = present_columns(records, {h: h for h in OPTIONAL_COLUMNS})
    head = [h for h in XLSX_WIDTHS if present.get(h, True)]
    wb = Workbook()
    ws = wb.active
    ws.title = "Index"
    ws.append(head)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="4A7C59")
    link_col = head.index("BHL link") + 1
    for rec in records:
        ws.append([rec[h] for h in head])
        link = ws.cell(row=ws.max_row, column=link_col)
        link.hyperlink = rec["BHL link"]
        link.font = Font(color=LINK_COLOUR, underline="single")
    from openpyxl.utils import get_column_letter
    for i, h in enumerate(head, 1):
        ws.column_dimensions[get_column_letter(i)].width = XLSX_WIDTHS[h]
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    notes = wb.create_sheet("About")
    notes.column_dimensions["A"].width = 22
    notes.column_dimensions["B"].width = 90
    for label, value in list(about) + [("Rows", f"{len(records)} pages")]:
        notes.append([label, value])
    if not all(present.values()):
        notes.append(["Note", NO_AUTHORS_NOTE if not any(present.values()) else
                      " and ".join(h for h, on in present.items() if not on)
                      + ": none given by BHL for these pages"])
    notes.append(["Note", "Excerpts are uncorrected OCR text: check them against the page "
                          "image before citing."])
    for row in notes.iter_rows(min_col=1, max_col=1):
        row[0].font = Font(bold=True)
    wb.save(str(path))
    return path


def write_dossier(title, rows, out_dir, stem, by_journal=False, include_appendices=True,
                  include_notes=True, xlsx=True, extra_names=(), about=None, keep=None):
    """Word dossier (+ Excel index) for any set of page rows.
    Returns (docx_path, xlsx_path or None, (entries, merged, index, no_match))."""
    out_dir.mkdir(parents=True, exist_ok=True)
    docx_path = out_dir / f"{stem}_dossier.docx"
    main, index, no_match = write_docx(title, rows, docx_path, by_journal, include_appendices,
                                       include_notes, extra_names, about, keep=keep)
    xlsx_path = write_xlsx(out_dir / f"{stem}_dossier_index.xlsx", main, index, no_match,
                           about=[("Search", title)] + list(about or [])) if xlsx else None
    counts = (len(main), sum(len(e.copies) for e in main), len(index), len(no_match))
    return docx_path, xlsx_path, counts


def export_dossier(store, species, out_dir=config.EXPORT_DIR, by_journal=False):
    from .review import combined_status
    rows = store.dossier_rows(species)
    if not rows:
        return None, None, None
    from .export import console_stem                 # <Species>_all_pages_dossier.docx
    return write_dossier(species, rows, out_dir, console_stem(species), by_journal,
                         extra_names=[species],
                         keep=lambda r: combined_status(r["statuses"]) != "not_relevant")
