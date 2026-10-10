"""
Collection Planner — PDF Export

Generates printable PDFs:
- Full layout diagrams (one page per box with family sections)
- Label strips (family names for cutting and placing in boxes)

Uses fpdf2 for PDF generation.
Install: pip install fpdf2
"""


try:
    from fpdf import FPDF
except ImportError:
    FPDF = None
    print("WARNING: fpdf2 not installed. Run: pip install fpdf2")

from .planner_data import (
    ProfileManager, calculate_family_rows,
)


def _core_text(text):
    """Text the built-in Helvetica can print: box labels carry an em dash, which
    made the layout export fail (found with CUR-3, 10 Oct 2026)."""
    text = str(text).replace("\u2014", "-").replace("\u2013", "-")
    return text.encode("latin-1", "replace").decode("latin-1")


if FPDF is not None:
    class _LayoutPDF(FPDF):
        def normalize_text(self, text):
            return super().normalize_text(_core_text(text))
else:  # pragma: no cover
    _LayoutPDF = None


# Colours matching the preview (RGB tuples)
FAMILY_COLOURS_RGB = [
    (194, 149, 110),  # Terracotta
    (122, 158, 126),  # Sage green
    (110, 136, 152),  # Dusty blue
    (139, 129, 120),  # Warm grey
    (184, 134, 11),   # Gold
    (166, 61, 64),    # Muted red
    (95, 133, 117),   # Dark sage
    (154, 117, 85),   # Dark terracotta
    (74, 124, 89),    # Moss green
    (107, 91, 115),   # Muted purple
]


def export_layout_pdf(path: str, boxes: list, profile_mgr: ProfileManager,
                      box_key: str, growth_pct: float):
    """
    Export a PDF with allocation summary and one page per box.
    """
    if FPDF is None:
        raise RuntimeError("The PDF export needs fpdf2. In a terminal:  py -3.14 -m pip install fpdf2")

    box_size = profile_mgr.get_box(box_key)
    if not box_size:
        raise RuntimeError(f"No box size '{box_key}' (see mounting_profiles.json).")

    pdf = _LayoutPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)

    # =========================================================================
    # Page 1: Summary
    # =========================================================================
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Collection Layout Plan", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Box: {box_size.label} ({box_size.width_mm} x {box_size.height_mm}mm)",
             new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Growth factor: {growth_pct}%",
             new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Total boxes: {len(boxes)}",
             new_x="LMARGIN", new_y="NEXT")

    pdf.ln(6)

    # Summary table
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(15, 7, "Box", border=1)
    pdf.cell(80, 7, "Families", border=1)
    pdf.cell(25, 7, "Specimens", border=1)
    pdf.cell(25, 7, "Capacity", border=1)
    pdf.ln()

    pdf.set_font("Helvetica", "", 9)
    for box in boxes:
        specimen_total = sum(f.specimen_count for f in box.families)
        families_text = ""
        if box.families:
            first = box.families[0].family
            last = box.families[-1].family
            families_text = first if first == last else f"{first} - {last}"

        pdf.cell(15, 6, str(box.box_number), border=1)
        pdf.cell(80, 6, families_text[:45], border=1)
        pdf.cell(25, 6, str(specimen_total), border=1, align="R")
        pdf.cell(25, 6, f"{box.capacity_pct}%", border=1, align="R")
        pdf.ln()

    # =========================================================================
    # One page per box: layout diagram
    # =========================================================================
    for box in boxes:
        pdf.add_page()

        # Title
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 8, box.label, new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("Helvetica", "", 9)
        specimen_total = sum(f.specimen_count for f in box.families)
        pdf.cell(0, 5,
                 f"{box_size.label}  |  {specimen_total} specimens  |  "
                 f"{box.capacity_pct}% capacity  |  Growth: {growth_pct}%",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

        # Draw box outline (scaled to fit page)
        page_w = 190  # A4 width minus margins
        scale = min(page_w / box_size.width_mm, 1.0)
        draw_w = box_size.width_mm * scale
        draw_h = box_size.height_mm * scale

        start_x = pdf.get_x()
        start_y = pdf.get_y()

        # Box outline
        pdf.set_draw_color(150, 150, 150)
        pdf.set_line_width(0.5)
        pdf.rect(start_x, start_y, draw_w, draw_h)

        # Family sections with superfamily headers
        y_pos = start_y
        separator = 1.5 * scale
        sf_separator = 4 * scale
        sf_header_h = 5 * scale
        prev_sf = ""

        for i, family in enumerate(box.families):
            # Superfamily header
            is_sf_boundary = (family.superfamily != prev_sf
                              and family.superfamily != "" and prev_sf != "")
            if is_sf_boundary or (i == 0 and family.superfamily):
                if i > 0:
                    y_pos += sf_separator
                if y_pos + sf_header_h < start_y + draw_h:
                    pdf.set_font("Helvetica", "BI", 6)
                    pdf.set_text_color(154, 117, 85)
                    pdf.set_xy(start_x + 2, y_pos)
                    pdf.cell(draw_w - 4, sf_header_h, family.superfamily)
                    pdf.set_draw_color(194, 149, 110)
                    pdf.set_line_width(0.2)
                    pdf.line(start_x + 1, y_pos + sf_header_h,
                             start_x + draw_w - 1, y_pos + sf_header_h)
                    y_pos += sf_header_h
            elif i > 0:
                y_pos += separator
            prev_sf = family.superfamily

            info = calculate_family_rows(
                family, profile_mgr, box_size, growth_pct
            )
            section_h = info["height_mm"] * scale

            if y_pos + section_h > start_y + draw_h:
                section_h = (start_y + draw_h) - y_pos
                if section_h <= 0:
                    break

            # Coloured fill
            r, g, b = FAMILY_COLOURS_RGB[i % len(FAMILY_COLOURS_RGB)]
            pdf.set_fill_color(r, g, b)
            pdf.set_draw_color(max(r - 30, 0), max(g - 30, 0), max(b - 30, 0))
            pdf.rect(start_x, y_pos, draw_w, section_h, style="DF")

            # Family label inside the section
            if section_h > 4:
                pdf.set_font("Helvetica", "B", 7)
                pdf.set_text_color(255, 255, 255)
                pdf.set_xy(start_x + 2, y_pos + 1)
                pdf.cell(draw_w - 4, 4, family.family)

                if section_h > 8:
                    pdf.set_font("Helvetica", "", 6)
                    pdf.set_xy(start_x + 2, y_pos + 5)
                    pdf.cell(
                        draw_w - 4, 3,
                        f"{family.specimen_count} specimens, "
                        f"{info['specimens_per_row']}/row, "
                        f"{info['base_rows']}+{info['growth_rows']} rows"
                    )

            pdf.set_text_color(0, 0, 0)
            y_pos += section_h + separator

        # Species list below the diagram
        list_y = start_y + draw_h + 8
        pdf.set_xy(start_x, list_y)

        if pdf.get_y() < 260:  # Only if room on page
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 5, "Species in this box:", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 8)

            for family in box.families:
                for sp_name, sp_count in family.species[:20]:
                    if pdf.get_y() > 275:
                        break
                    pdf.cell(0, 4, f"  {sp_name} ({sp_count})",
                             new_x="LMARGIN", new_y="NEXT")
                if len(family.species) > 20:
                    pdf.cell(0, 4, f"  ... and {len(family.species) - 20} more",
                             new_x="LMARGIN", new_y="NEXT")

    pdf.output(path)
    print(f"Exported layout PDF: {path}")


def export_labels_pdf(path: str, families: list):
    """
    Export a PDF with family name label strips for cutting.
    """
    if FPDF is None:
        raise RuntimeError("The PDF export needs fpdf2. In a terminal:  py -3.14 -m pip install fpdf2")

    pdf = _LayoutPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Collection Labels", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Label strips: full width, with cut lines
    label_height = 12
    label_width = 180

    pdf.set_font("Helvetica", "B", 11)
    prev_sf = ""

    for family in families:
        if pdf.get_y() + label_height > 280:
            pdf.add_page()

        # Superfamily header
        if family.superfamily and family.superfamily != prev_sf:
            if prev_sf:
                pdf.ln(3)
            if pdf.get_y() + 8 + label_height > 280:
                pdf.add_page()
            pdf.set_font("Helvetica", "BI", 9)
            pdf.set_text_color(154, 117, 85)
            pdf.cell(label_width, 7, f"  {family.superfamily}", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)
            prev_sf = family.superfamily

        y = pdf.get_y()

        # Cut line (dashed)
        pdf.set_draw_color(200, 200, 200)
        pdf.set_line_width(0.2)
        pdf.dashed_line(15, y, 15 + label_width, y, dash_length=2, space_length=2)

        # Family name
        pdf.set_xy(15, y + 1)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(label_width, label_height - 2,
                 f"  {family.family.upper()}", align="L")

        # Specimen count (right-aligned)
        pdf.set_xy(15, y + 1)
        pdf.set_font("Helvetica", "", 8)
        pdf.cell(label_width - 4, label_height - 2,
                 f"{family.specimen_count} specimens",
                 align="R")

        pdf.set_y(y + label_height)

    # Final cut line
    pdf.set_draw_color(200, 200, 200)
    pdf.dashed_line(15, pdf.get_y(), 15 + label_width, pdf.get_y(),
                    dash_length=2, space_length=2)

    pdf.output(path)
    print(f"Exported labels PDF: {path}")
