"""
Examen - Species Appendix Export

Generates the standard invertebrate survey appendix as Excel (.xlsx).
Columns: Species Name, Common Name, Conservation Status, SQS, Tier,
Broad Biotope, Habitat, Family, Order. Sorted by taxonomic_sort_key.
Key species grouped at top. Summary row at bottom.

Requires openpyxl.
"""

import sqlite3
from pathlib import Path
from PySide6.QtWidgets import QFileDialog, QMessageBox
import paths

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

# Colours matching Naturalist theme
MOSS = "4A7C59"
ACCENT = "7C6C9F"
RED = "A63D40"
AMBER = "C2956E"
LIGHT_BG = "F0EEEA"
HEADER_BG = "5A4D78"
KEY_BG = "F0EDF5"


def _get_sort_keys(tvks: list[str]) -> dict[str, int]:
    """Look up taxonomic_sort_key for each TVK from UKSI."""
    if not tvks or not paths.UKSI_DB.exists():
        return {}
    conn = sqlite3.connect(str(paths.UKSI_DB))
    c = conn.cursor()
    result = {}
    for i in range(0, len(tvks), 500):
        batch = tvks[i:i+500]
        ph = ",".join("?" * len(batch))
        c.execute(f"SELECT tvk, sort_code FROM taxa WHERE tvk IN ({ph})", batch)
        for row in c.fetchall():
            result[row[0]] = row[1] or 999999
    conn.close()
    return result


def _get_taxonomy(tvks: list[str]) -> dict[str, dict]:
    """Look up common_name, family, order for each TVK."""
    if not tvks or not paths.UKSI_DB.exists():
        return {}
    conn = sqlite3.connect(str(paths.UKSI_DB))
    c = conn.cursor()
    result = {}
    for i in range(0, len(tvks), 500):
        batch = tvks[i:i+500]
        ph = ",".join("?" * len(batch))
        c.execute(f"""SELECT t.tvk, COALESCE(cn.common_name, '') as common,
                             COALESCE(t.family, '') as family, COALESCE(t."order", '') as "order"
                      FROM taxa t LEFT JOIN common_names cn ON t.tvk = cn.tvk AND cn.preferred = 1
                      WHERE t.tvk IN ({ph})""", batch)
        for row in c.fetchall():
            result[row[0]] = {"common": row[1], "family": row[2], "order": row[3]}
    conn.close()
    return result


def export_appendix(parent_widget, site_name: str, result, detail=None):
    """Export species appendix to Excel.

    Args:
        parent_widget: Qt parent for file dialog
        site_name: Site name for filename default
        result: AnalysisResult from PantheonAnalysisService
        detail: Optional SiteDetail with full species list
    """
    if not HAS_OPENPYXL:
        QMessageBox.warning(parent_widget, "Examen",
                            "openpyxl required for Excel export.\npip install openpyxl")
        return

    safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in site_name)
    path, _ = QFileDialog.getSaveFileName(
        parent_widget, "Export Species Appendix",
        f"{safe_name}_species_appendix.xlsx", "Excel (*.xlsx)")
    if not path:
        return

    # Gather all species TVKs
    key_tvks = {k.tvk for k in result.key_species}
    all_tvks = list(key_tvks)
    non_key_species = []
    if detail:
        for sp in detail.species_list:
            if sp.tvk and sp.tvk not in key_tvks:
                all_tvks.append(sp.tvk)
                non_key_species.append(sp)

    sort_keys = _get_sort_keys(all_tvks)
    taxonomy = _get_taxonomy(all_tvks)

    # Sort key species by taxonomic order
    key_sorted = sorted(result.key_species, key=lambda k: sort_keys.get(k.tvk, 999999))
    # Sort non-key by taxonomic order
    non_key_sorted = sorted(non_key_species, key=lambda s: sort_keys.get(s.tvk, 999999))

    # Build workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Species Appendix"

    # Styles
    hdr_font = Font(name="Arial", bold=True, size=10, color="FFFFFF")
    hdr_fill = PatternFill(start_color=HEADER_BG, end_color=HEADER_BG, fill_type="solid")
    hdr_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    key_fill = PatternFill(start_color=KEY_BG, end_color=KEY_BG, fill_type="solid")
    body_font = Font(name="Arial", size=10)
    bold_font = Font(name="Arial", size=10, bold=True)
    border = Border(
        left=Side(style="thin", color="D4D0C8"), right=Side(style="thin", color="D4D0C8"),
        top=Side(style="thin", color="D4D0C8"), bottom=Side(style="thin", color="D4D0C8"))
    center = Alignment(horizontal="center")

    # Title row
    ws.merge_cells("A1:I1")
    title_cell = ws["A1"]
    title_cell.value = f"Species Appendix -- {site_name}"
    title_cell.font = Font(name="Georgia", bold=True, size=14, color=ACCENT)

    # Headers (row 3)
    headers = ["Species Name", "Common Name", "Conservation Status", "SQS", "Tier",
               "Broad Biotope", "Habitat", "Family", "Order"]
    widths = [32, 24, 20, 8, 10, 18, 18, 18, 16]
    for col, (h, w) in enumerate(zip(headers, widths), 1):
        cell = ws.cell(row=3, column=col, value=h)
        cell.font = hdr_font
        cell.fill = hdr_fill
        cell.alignment = hdr_align
        cell.border = border
        ws.column_dimensions[chr(64 + col)].width = w

    # Key species section
    row = 4
    if key_sorted:
        for k in key_sorted:
            tax = taxonomy.get(k.tvk, {})
            values = [k.species_name, tax.get("common", ""), k.status_display or k.short_status,
                      k.sqs if k.sqs else "", k.tier, k.broad_biotope, k.habitat,
                      k.family or tax.get("family", ""), tax.get("order", "")]
            for col, val in enumerate(values, 1):
                cell = ws.cell(row=row, column=col, value=val)
                cell.font = bold_font if col == 1 else body_font
                cell.fill = key_fill
                cell.border = border
                if col in (4, 5):
                    cell.alignment = center
            row += 1

    # Separator row
    if key_sorted and non_key_sorted:
        for col in range(1, 10):
            cell = ws.cell(row=row, column=col)
            cell.border = border
        row += 1

    # Non-key species
    for sp in non_key_sorted:
        tax = taxonomy.get(sp.tvk, {})
        values = [sp.name, tax.get("common", ""), sp.status or "", sp.sqs if sp.sqs else "",
                  "", sp.broad_biotope or "", sp.habitat or "",
                  tax.get("family", ""), tax.get("order", "")]
        for col, val in enumerate(values, 1):
            cell = ws.cell(row=row, column=col, value=val)
            cell.font = body_font
            cell.border = border
            if col in (4, 5):
                cell.alignment = center
        row += 1

    # Summary row
    row += 1
    summary_font = Font(name="Arial", size=10, bold=True, color=ACCENT)
    ws.cell(row=row, column=1, value="TOTALS").font = summary_font
    total_species = len(key_sorted) + len(non_key_sorted)
    ws.cell(row=row, column=2, value=f"{total_species} species").font = summary_font
    ws.cell(row=row, column=5, value=f"{len(key_sorted)} key").font = summary_font
    sqi = result.overall_sqi
    if sqi and sqi.sqi:
        ws.cell(row=row, column=4, value=f"SQI: {int(sqi.sqi)}").font = summary_font
    ws.cell(row=row, column=6, value=f"R:{result.rare_count} S:{result.scarce_count} P:{result.priority_count}").font = summary_font

    ws.freeze_panes = "A4"

    try:
        wb.save(path)
        QMessageBox.information(parent_widget, "Examen",
                                f"Species appendix exported.\n{total_species} species, "
                                f"{len(key_sorted)} key.\n{path}")
    except Exception as e:
        QMessageBox.warning(parent_widget, "Examen", f"Export failed:\n{e}")
