"""
Curator - Taxonomic Label PDF Export
Black and white friendly, cascading sizes, cut lines. Uses fpdf2.
"""
try:
    from fpdf import FPDF
except ImportError:
    FPDF = None


def export_taxonomic_labels_pdf(path, labels, full_width=True,
                                 show_common=True,
                                 show_my_specimens=False,
                                 show_my_species=False,
                                 show_fauna=False,
                                 font_family="Helvetica", font_size=11):
    """Write the labels PDF. Raises RuntimeError / OSError on failure (CUR-3:
    the caller shows it); returns the font family actually used."""
    if FPDF is None:
        raise RuntimeError("The PDF export needs fpdf2. In a terminal:  py -3.14 -m pip install fpdf2")

    pdf = FPDF(orientation="P", unit="mm", format="A4")

    # Register custom fonts if needed
    try:
        from .planner_fonts import register_pdf_fonts
        f = register_pdf_fonts(pdf, font_family)
    except ImportError:
        # Fallback to built-in mapping
        fm = {"Helvetica":"Helvetica","Arial":"Helvetica",
              "Times":"Times","Courier":"Courier"}
        f = fm.get(font_family, "Helvetica")

    if full_width:
        _full(pdf, path, labels, show_common, show_my_specimens, show_my_species, show_fauna, f, font_size)
    else:
        _pinned(pdf, path, labels, show_common, show_my_specimens, show_my_species, show_fauna, f, font_size)
    return f


def _rh(rank, sz):
    """Row height scales with font size."""
    return max(5, {"Order":sz+6,"Suborder":sz+6,"Superfamily":sz+4,
            "Family":sz+2,"Subfamily":sz+2,
            "Genus":sz,"Species":sz}.get(rank, sz))


def _rsz(rank, sz):
    """Font size per rank - four tiers."""
    return max(6, sz + {"Order":6,"Suborder":6,"Superfamily":4,
            "Family":2,"Subfamily":2,
            "Genus":0,"Species":0}.get(rank, 0))


def _cut(pdf, pw):
    """Draw a dashed cut line."""
    pdf.set_draw_color(180, 180, 180)
    pdf.set_line_width(0.15)
    pdf.dashed_line(15, pdf.get_y(), 15 + pw, pdf.get_y(),
                    dash_length=1.5, space_length=1.5)


def _full(pdf, path, labels, show_common, show_my_specimens, show_my_species, show_fauna, f, sz):
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font(f, "B", sz + 1)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 8, "Taxonomic Collection Labels", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pw = 180
    for i, entry in enumerate(labels):
        if len(entry) == 6:
            name, rank, cn, specimens, my_species, gb_species = entry
        elif len(entry) == 5:
            name, rank, cn, specimens, gb_species = entry
            my_species = 0
        else:
            name, rank, cn, specimens = entry
            my_species, gb_species = 0, 0
        h = _rh(rank, sz)
        rsz = _rsz(rank, sz)
        if pdf.get_y() + h > 280:
            pdf.add_page()
        # Cut line between every label
        if i > 0:
            _cut(pdf, pw)
        y = pdf.get_y()
        if rank == "Order":
            # B&W: thick top border + bold text, no filled background
            pdf.set_draw_color(0, 0, 0)
            pdf.set_line_width(0.8)
            pdf.line(15, y, 15 + pw, y)
            pdf.set_font(f, "B", rsz)
            pdf.set_text_color(0, 0, 0)
            pdf.set_xy(15, y + 0.5)
            pdf.cell(pw, h - 0.5, f"  {name.upper()}", align="L")
            pdf.set_draw_color(0, 0, 0)
            pdf.set_line_width(0.3)
            pdf.line(15, y + h, 15 + pw, y + h)
        elif rank == "Suborder":
            pdf.set_font(f, "B", rsz)
            pdf.set_text_color(0, 0, 0)
            pdf.set_xy(15, y)
            pdf.cell(pw, h, f"  {name.upper()}", align="L")
        elif rank == "Superfamily":
            pdf.set_font(f, "B", rsz)
            pdf.set_text_color(0, 0, 0)
            pdf.set_xy(15, y)
            pdf.cell(pw, h, f"  {name}", align="L")
        elif rank == "Family":
            pdf.set_font(f, "B", rsz)
            pdf.set_text_color(0, 0, 0)
            pdf.set_xy(15, y)
            pdf.cell(0, h, f"  {name}", align="L")
            rp = []
            if show_common and cn:
                rp.append(cn)
            parts = []
            if show_my_specimens and specimens > 0:
                parts.append(f"{specimens} specimens")
            if show_my_species and my_species > 0:
                parts.append(f"{my_species} species")
            if show_fauna and gb_species > 0:
                parts.append(f"{gb_species} GB")
            if parts:
                rp.append(" / ".join(parts))
            if rp:
                pdf.set_font(f, "", rsz - 3)
                pdf.set_text_color(120, 120, 120)
                pdf.set_xy(15, y)
                pdf.cell(pw - 4, h, " \u00b7 ".join(rp), align="R")
                pdf.set_text_color(0, 0, 0)
        elif rank == "Subfamily":
            pdf.set_font(f, "B", rsz)
            pdf.set_text_color(0, 0, 0)
            pdf.set_xy(15, y)
            pdf.cell(pw, h, f"  {name}", align="L")
        elif rank == "Genus":
            pdf.set_font(f, "I", rsz)
            pdf.set_text_color(0, 0, 0)
            pdf.set_xy(15, y)
            pdf.cell(pw, h, f"  {name}")
            parts = []
            if show_my_specimens and specimens > 0:
                parts.append(f"{specimens} specimens")
            if show_my_species and my_species > 0:
                parts.append(f"{my_species} species")
            if show_fauna and gb_species > 0:
                parts.append(f"{gb_species} GB")
            if parts:
                pdf.set_font(f, "", rsz - 2)
                pdf.set_text_color(120, 120, 120)
                pdf.set_xy(15, y)
                pdf.cell(pw - 4, h, " / ".join(parts), align="R")
            pdf.set_text_color(0, 0, 0)
        elif rank == "Species":
            pdf.set_font(f, "I", rsz)
            pdf.set_text_color(0, 0, 0)
            pdf.set_xy(15, y)
            pdf.cell(0, h, f"  {name}")
            rp = []
            if show_common and cn:
                rp.append(cn)
            if show_my_specimens and specimens > 0:
                rp.append(f"{specimens} specimen{'s' if specimens != 1 else ''}")
            if rp:
                pdf.set_font(f, "", rsz - 2)
                pdf.set_text_color(120, 120, 120)
                pdf.set_xy(15, y)
                pdf.cell(pw - 4, h, " \u00b7 ".join(rp), align="R")
            pdf.set_text_color(0, 0, 0)
        pdf.set_y(y + h)
    _cut(pdf, pw)
    pdf.output(path)
    print(f"Exported labels: {path}")


def _pinned(pdf, path, labels, show_common, show_my_specimens, show_my_species, show_fauna, f, sz):
    """Small pinned labels — stacked across the full page width."""
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()

    # Layout: fill page width with as many columns as fit
    mx, my = 10, 10  # page margins
    page_w = 210 - 2 * mx  # usable width
    gx, gy = 2, 2  # gaps between cards
    cw = 36  # card width — fits 5 across comfortably
    ch = 16  # card height
    cols = int((page_w + gx) / (cw + gx))  # calculate columns dynamically

    col, x, y = 0, mx, my

    pdf.set_font(f, "B", sz)
    pdf.cell(0, 6, "Pinned Collection Labels", new_x="LMARGIN", new_y="NEXT")
    y = pdf.get_y() + 3

    for entry in labels:
        if len(entry) == 6:
            name, rank, cn, specimens, my_species, gb_species = entry
        elif len(entry) == 5:
            name, rank, cn, specimens, gb_species = entry
            my_species = 0
        else:
            name, rank, cn, specimens = entry
            my_species, gb_species = 0, 0
        # Full-width header rows for Order/Suborder/Superfamily/Subfamily
        if rank in ("Order", "Suborder", "Superfamily", "Subfamily"):
            # Start new row if mid-row
            if col > 0:
                y += ch + gy
                col, x = 0, mx

            if y + 7 > 290:
                pdf.add_page()
                y, col, x = my, 0, mx

            if rank == "Order":
                # B&W: bold text with top/bottom lines
                pdf.set_draw_color(0, 0, 0)
                pdf.set_line_width(0.6)
                pdf.line(mx, y, mx + page_w, y)
                pdf.set_font(f, "B", sz - 2)
                pdf.set_text_color(0, 0, 0)
                pdf.set_xy(mx, y + 0.5)
                pdf.cell(page_w, 6, f"  {name.upper()}", align="L")
                pdf.set_line_width(0.3)
                pdf.line(mx, y + 7, mx + page_w, y + 7)
            elif rank == "Suborder":
                pdf.set_font(f, "B", sz - 3)
                pdf.set_text_color(50, 50, 50)
                pdf.set_xy(mx, y)
                pdf.cell(page_w, 6, f"  {name}")
                pdf.set_text_color(0, 0, 0)
            elif rank == "Superfamily":
                pdf.set_font(f, "B", sz - 3)
                pdf.set_text_color(80, 80, 80)
                pdf.set_xy(mx, y)
                pdf.cell(page_w, 6, f"  {name}")
                pdf.set_text_color(0, 0, 0)
            else:  # Subfamily
                pdf.set_font(f, "I", sz - 3)
                pdf.set_text_color(100, 100, 100)
                pdf.set_xy(mx + 5, y)
                pdf.cell(page_w - 5, 6, f"  {name}")
                pdf.set_text_color(0, 0, 0)
            y += 8
            continue

        # Regular card labels for Family/Genus/Species
        if y + ch > 290:
            pdf.add_page()
            y, col, x = my, 0, mx

        # Draw card border
        pdf.set_draw_color(180, 180, 180)
        pdf.set_line_width(0.3)
        pdf.rect(x, y, cw, ch)

        rsz = _rsz(rank, sz)

        if rank == "Family":
            pdf.set_font(f, "B", min(rsz - 3, 8))
            pdf.set_text_color(0, 0, 0)
            pdf.set_xy(x + 1.5, y + 1)
            pdf.cell(cw - 3, 5, name)
        elif rank == "Genus":
            pdf.set_font(f, "I", min(rsz - 3, 8))
            pdf.set_text_color(0, 0, 0)
            pdf.set_xy(x + 1.5, y + 1)
            pdf.cell(cw - 3, 5, name)
        else:  # Species
            pdf.set_font(f, "I", min(rsz - 4, 7))
            pdf.set_text_color(0, 0, 0)
            pdf.set_xy(x + 1.5, y + 1)
            # Truncate long species names
            display = name if len(name) <= 20 else name[:18] + ".."
            pdf.cell(cw - 3, 5, display)

        # Detail line (common name / count)
        lp = []
        if show_common and cn:
            lp.append(cn[:18])
        if rank == "Species":
            if show_my_specimens and specimens > 0:
                lp.append(f"{specimens} sp.")
        else:
            parts = []
            if show_my_specimens and specimens > 0:
                parts.append(f"{specimens}sp")
            if show_my_species and my_species > 0:
                parts.append(f"{my_species}spp")
            if show_fauna and gb_species > 0:
                parts.append(f"{gb_species}GB")
            if parts:
                lp.append("/".join(parts))
        if lp:
            pdf.set_font(f, "", max(5, sz - 5))
            pdf.set_text_color(130, 130, 130)
            pdf.set_xy(x + 1.5, y + 7)
            pdf.cell(cw - 3, 5, " \u00b7 ".join(lp))
            pdf.set_text_color(0, 0, 0)

        col += 1
        if col >= cols:
            col, x = 0, mx
            y += ch + gy
        else:
            x += cw + gx

    pdf.output(path)
    print(f"Exported pinned labels: {path}")
