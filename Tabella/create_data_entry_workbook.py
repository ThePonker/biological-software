"""
Tabella -- Create Data Entry Workbook (v2)

Creates a macro-enabled Excel workbook (.xlsm) with:
- Sheet 1: "Personal Observations" - personal iRecord data entry
- Sheet 2: "Commercial Observations" - commercial surveys with project/client/embargo
- Sheet 3: "Insect Collection" - specimen catalogue entry
- Sheet 4: "UKSI" - reference sheet with all species + Codex conservation data
- Sheet 5: "Instructions" - usage guide for all 3 templates

VBA macro auto-populates Conservation, Red List, Rarity, S41, Legal Protection,
BAP, TVK, Common Name, Class, Order, Family when you type a species name.

v2 changes (Codex Strategy doc, 16 April 2026):
  - Updated SQL to query the new 11-track scheme:
        threat_iucn_2001, threat_iucn_legacy, rarity_modern, rarity_legacy,
        priority, legal_protection
  - Workbook column structure UNCHANGED -- VBA macro continues to work
  - Section 41 column populated from `priority` entries naming England
  - BAP column populated from `priority` entries naming UK BAP
  - Legal Protection column populated from `legal_protection` (with detail
    where present)

Usage:
    python -m Tabella.create_data_entry_workbook
"""

import sqlite3
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
import paths
from pathlib import Path
from datetime import datetime

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.utils import get_column_letter
except ImportError:
    print("openpyxl required: pip install openpyxl")
    exit(1)


UKSI_PATH = paths.UKSI_DB
CODEX_PATH = paths.CODEX_DB

# Output to Tabella/output/ -- not data/
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

# Styles
MOSS = '4A7C59'
AMBER = '8B6914'
BLUE = '2E5984'
WARM_GREY = '8B8178'
LIGHT_BG = 'F0EEEA'
WHITE = 'FFFFFF'


# ============================================================
# Codex data loader -- updated for the 11-track scheme
# ============================================================
# Tracks queried (per Codex Strategy doc, section 3):
#   Threat (modern + legacy) -> red_list column
#   Rarity (modern + legacy) -> rarity column
#   priority                 -> s41 / bap columns (split by jurisdiction)
#   legal_protection         -> legal column (detail string preferred)
# ============================================================
def load_codex_data(codex_path):
    """Load Red List, Rarity, S41, BAP, Legal status from codex.db.

    Returns: {tvk: {'red_list', 'red_list_legacy', 'rarity', 'rarity_legacy',
                    's41', 'legal', 'bap'}}
    """
    if not codex_path.exists():
        print(f"  WARNING: codex.db not found at {codex_path} -- "
              f"conservation columns will be empty")
        return {}

    conn = sqlite3.connect(str(codex_path))
    data = {}

    cursor = conn.execute("""
        SELECT tvk, status_track, status_value, status_detail
        FROM status_summary
        WHERE status_track IN (
            'threat_iucn_2001',
            'threat_iucn_legacy',
            'rarity_modern',
            'rarity_legacy',
            'priority',
            'legal_protection'
        )
    """)

    for tvk, track, value, detail in cursor:
        if tvk not in data:
            data[tvk] = {
                'red_list': '',
                'red_list_legacy': '',
                'rarity': '',
                'rarity_legacy': '',
                's41': '',
                'legal': '',
                'bap': '',
            }

        if track == 'threat_iucn_2001':
            # Skip non-threat-relevant categories for the workbook column
            if value not in ('LC', 'NA', 'NE', 'WL'):
                data[tvk]['red_list'] = value
            elif not data[tvk]['red_list']:
                # Show LC etc. only if no other status takes priority
                data[tvk]['red_list'] = value

        elif track == 'threat_iucn_legacy':
            data[tvk]['red_list_legacy'] = value

        elif track == 'rarity_modern':
            data[tvk]['rarity'] = value

        elif track == 'rarity_legacy':
            data[tvk]['rarity_legacy'] = value

        elif track == 'priority':
            # priority track holds entries like "UK BAP", "NERC S.41 England",
            # "Env (Wales) Act S7", "Scottish Biodiversity List", "NI Priority Species"
            v = (value or '').strip()
            if v == "UK BAP":
                data[tvk]['bap'] = "UK"
            elif "NERC S.41" in v or "S.41" in v or v == "England":
                # Catch a few common variants
                data[tvk]['s41'] = "England"
            elif "Wales" in v:
                # If S41 not set, show Wales
                if not data[tvk]['s41']:
                    data[tvk]['s41'] = "Wales"
            elif "Scottish" in v or "Scotland" in v:
                if not data[tvk]['s41']:
                    data[tvk]['s41'] = "Scotland"
            elif "NI Priority" in v or "Northern Ireland" in v:
                if not data[tvk]['s41']:
                    data[tvk]['s41'] = "Northern Ireland"

        elif track == 'legal_protection':
            # Use detail (specific instrument) if present; else value
            label = detail or value or ''
            if not data[tvk]['legal']:
                data[tvk]['legal'] = label
            else:
                # Multiple legal instruments -- semicolon-join, capped to keep
                # the cell readable
                existing = data[tvk]['legal']
                if label not in existing:
                    if existing.count(';') < 2:
                        data[tvk]['legal'] = f"{existing}; {label}"

    conn.close()
    print(f"  Loaded Codex data for {len(data):,} species")
    return data


def load_uksi_species(db_path, codex_data):
    """Load species data from UKSI with disambiguated display names + Codex."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    cursor = conn.execute("""
        SELECT t.scientific_name, t.tvk, t.rank,
               COALESCE((SELECT cn2.common_name FROM common_names cn2
                     WHERE cn2.tvk = t.tvk AND cn2.preferred = 1 LIMIT 1), '')
                       as common_name,
               COALESCE(t.family, '') as family,
               COALESCE(t."order", '') as "order",
               COALESCE(t.class, '') as class_name,
               COALESCE(t.red_list_status, '') as red_list_status,
               COALESCE(t.legal_protection, '') as legal_protection,
               COALESCE(t.bap_status, '') as bap_status,
               COALESCE(t.rarity_status, '') as rarity_status,
               COALESCE(t.nnss_status, '') as nnss_status,
               COALESCE(t.international_status, '') as international_status,
               COALESCE(t.sort_code, 0) as sort_code
        FROM taxa t
        WHERE t.rank IN ('Species', 'Subspecies', 'Species aggregate',
                         'Species sensu lato', 'Species sensu stricto',
                         'Variety', 'Form', 'Species Hybrid')
        ORDER BY t.scientific_name, t.rank
    """)

    raw_entries = []
    for row in cursor:
        # Combined UKSI conservation string (legacy / for Conservation column)
        statuses = []
        for field in ['red_list_status', 'legal_protection', 'bap_status',
                      'rarity_status', 'nnss_status', 'international_status']:
            val = row[field]
            if val:
                statuses.append(val)
        conservation = '; '.join(statuses)

        # Codex-authoritative columns, with UKSI fallback for species
        # Codex doesn't cover (e.g. older non-invertebrate entries)
        tvk = row['tvk']
        codex = codex_data.get(tvk, {})

        # Modern preferred, legacy fallback
        red_list = codex.get('red_list', '') or codex.get('red_list_legacy', '')
        rarity = codex.get('rarity', '') or codex.get('rarity_legacy', '')
        s41 = codex.get('s41', '')
        legal = codex.get('legal', '')
        bap = codex.get('bap', '')

        # UKSI fallback for species not in Codex at all
        if not codex:
            if not red_list:
                red_list = row['red_list_status'] or ''
            if not rarity:
                rarity = row['rarity_status'] or ''
            if not legal:
                legal = row['legal_protection'] or ''
            if not bap:
                bap = row['bap_status'] or ''

        raw_entries.append({
            'scientific_name': row['scientific_name'],
            'tvk': tvk,
            'rank': row['rank'],
            'common_name': row['common_name'],
            'family': row['family'],
            'order': row['order'],
            'class_name': row['class_name'],
            'conservation': conservation,
            'red_list': red_list,
            'rarity': rarity,
            's41': s41,
            'legal': legal,
            'bap': bap,
            'sort_code': row['sort_code'],
        })

    conn.close()

    # Disambiguate display names
    name_ranks = {}
    for entry in raw_entries:
        name = entry['scientific_name']
        if name not in name_ranks:
            name_ranks[name] = []
        name_ranks[name].append(entry['rank'])

    species = []
    seen_display = set()

    for entry in raw_entries:
        name = entry['scientific_name']
        rank = entry['rank']

        if rank in ('Species sensu lato', 'Species aggregate'):
            display = f"{name} agg."
        elif rank == 'Species sensu stricto':
            display = f"{name} s.s."
        else:
            display = name

        if display in seen_display:
            continue
        seen_display.add(display)

        species.append({**entry, 'display_name': display})

    # Add s.l. aliases for s.s. and aggregate
    extra = []
    for entry in species:
        if entry['display_name'].endswith(' agg.'):
            sl_name = entry['display_name'].replace(' agg.', ' s.l.')
            if sl_name not in seen_display:
                seen_display.add(sl_name)
                extra.append({**entry, 'display_name': sl_name})
    species.extend(extra)

    species.sort(key=lambda x: x['display_name'].lower())
    return species


def make_header_font(color=MOSS):
    return Font(name='Arial', bold=True, size=10, color=WHITE)

def make_header_fill(color=MOSS):
    return PatternFill(start_color=color, end_color=color, fill_type='solid')

def make_border():
    side = Side(style='thin', color='D4D0C8')
    return Border(left=side, right=side, top=side, bottom=side)

def make_auto_fill():
    return PatternFill(start_color=LIGHT_BG, end_color=LIGHT_BG, fill_type='solid')


def create_template_sheet(wb, sheet_name, columns, accent_color, num_rows=1000):
    """Create a formatted template sheet with info panel, headers, and validations."""
    ws = wb.create_sheet(sheet_name)

    h_font = make_header_font()
    h_fill = make_header_fill(accent_color)
    h_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
    border = make_border()
    auto_fill = make_auto_fill()
    auto_font = Font(name='Arial', size=10, color='888888')
    edit_font = Font(name='Arial', size=10)

    # Info panel rows 1-3
    panel_bg = PatternFill(start_color='F7F5F1', end_color='F7F5F1', fill_type='solid')
    panel_fonts = [
        Font(name='Georgia', bold=True, size=13, color=accent_color),
        Font(name='Arial', size=10, color=WARM_GREY),
        Font(name='Arial', italic=True, size=10, color='555555'),
    ]
    panel_defaults = ["Select a species row to see details here", "", ""]

    entry_count = sum(1 for _, _, auto, _ in columns if not auto)
    fill_cols = max(entry_count, 8)
    for r in range(1, 4):
        for ci in range(1, fill_cols + 1):
            cell = ws.cell(row=r, column=ci)
            cell.fill = panel_bg
            if r == 3:
                cell.border = Border(bottom=Side(style='medium', color=accent_color))
        cell_a = ws.cell(row=r, column=1)
        cell_a.value = panel_defaults[r - 1]
        cell_a.font = panel_fonts[r - 1]
        cell_a.alignment = Alignment(vertical='center')
    ws.row_dimensions[1].height = 26
    ws.row_dimensions[2].height = 20
    ws.row_dimensions[3].height = 20

    # Headers row 4
    HDR = 4
    DATA = 5
    for col_idx, (name, width, is_auto, dv_formula) in enumerate(columns, 1):
        cell = ws.cell(row=HDR, column=col_idx, value=name)
        cell.font = h_font
        cell.fill = h_fill
        cell.alignment = h_align
        cell.border = border
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    # Data rows from row 5
    for row in range(DATA, DATA + num_rows):
        for col_idx, (name, width, is_auto, dv_formula) in enumerate(columns, 1):
            cell = ws.cell(row=row, column=col_idx)
            cell.border = border
            if is_auto:
                cell.fill = auto_fill
                cell.font = auto_font
            else:
                cell.font = edit_font

    # Data validations
    for col_idx, (name, width, is_auto, dv_formula) in enumerate(columns, 1):
        if dv_formula:
            col_letter = get_column_letter(col_idx)
            dv = DataValidation(type="list", formula1=dv_formula, allow_blank=True)
            ws.add_data_validation(dv)
            dv.add(f'{col_letter}{DATA}:{col_letter}{DATA + num_rows - 1}')

    ws.freeze_panes = f'A{DATA}'
    ws.sheet_properties.tabColor = accent_color
    return ws


def create_workbook(species_data, output_path):
    """Create the multi-template Excel workbook."""
    wb = Workbook()

    # =========================================================
    # UKSI Reference Sheet
    # =========================================================
    ws_uksi = wb.active
    ws_uksi.title = "UKSI"

    # Column structure UNCHANGED -- the VBA macro depends on these names
    uksi_headers = ['Display Name', 'TVK', 'Common Name', 'Class',
                     'Family', 'Order', 'Conservation', 'Red List', 'Rarity',
                     'S41', 'Legal Protection', 'BAP', 'Sort Code', 'Rank']
    uksi_header_font = Font(name='Arial', bold=True, size=9)
    uksi_data_font = Font(name='Arial', size=9)

    for col_idx, header in enumerate(uksi_headers, 1):
        cell = ws_uksi.cell(row=1, column=col_idx, value=header)
        cell.font = uksi_header_font

    for row_idx, sp in enumerate(species_data, 2):
        ws_uksi.cell(row=row_idx, column=1, value=sp['display_name']).font = uksi_data_font
        ws_uksi.cell(row=row_idx, column=2, value=sp['tvk']).font = uksi_data_font
        ws_uksi.cell(row=row_idx, column=3, value=sp['common_name']).font = uksi_data_font
        ws_uksi.cell(row=row_idx, column=4, value=sp['class_name']).font = uksi_data_font
        ws_uksi.cell(row=row_idx, column=5, value=sp['family']).font = uksi_data_font
        ws_uksi.cell(row=row_idx, column=6, value=sp['order']).font = uksi_data_font
        ws_uksi.cell(row=row_idx, column=7, value=sp['conservation']).font = uksi_data_font
        ws_uksi.cell(row=row_idx, column=8, value=sp.get('red_list', '')).font = uksi_data_font
        ws_uksi.cell(row=row_idx, column=9, value=sp.get('rarity', '')).font = uksi_data_font
        ws_uksi.cell(row=row_idx, column=10, value=sp.get('s41', '')).font = uksi_data_font
        ws_uksi.cell(row=row_idx, column=11, value=sp.get('legal', '')).font = uksi_data_font
        ws_uksi.cell(row=row_idx, column=12, value=sp.get('bap', '')).font = uksi_data_font
        ws_uksi.cell(row=row_idx, column=13, value=sp['sort_code']).font = uksi_data_font
        ws_uksi.cell(row=row_idx, column=14, value=sp['rank']).font = uksi_data_font

        if row_idx % 10000 == 0:
            print(f"  Writing UKSI row {row_idx:,}...")

    uksi_widths = [35, 20, 25, 14, 20, 18, 30, 12, 10, 12, 18, 10, 10, 20]
    for col_idx, width in enumerate(uksi_widths, 1):
        ws_uksi.column_dimensions[get_column_letter(col_idx)].width = width

    ws_uksi.freeze_panes = 'A2'

    # =========================================================
    # Drop-down formulas
    # =========================================================
    DV_METHOD = ('"Field observation,Hand search,Sweep netting,Beating,'
                 'Grubbing,Pitfall trap,Light trap,Light (MV),Light (LED),'
                 'Light (actinic),Malaise trap,Flight interception trap,'
                 'Water trap,Pan trap,Netting,Dredging,Litter sieving,'
                 'Bark sieving,Reared/bred,Dissection,Collected,Other"')
    DV_STAGE = '"Adult,Larva,Pupa,Egg,Nymph,Teneral,Not recorded"'
    DV_SEX = '"Female,Male,Mixed,Not recorded"'
    DV_CERT = '"Certain,Likely,Uncertain"'
    DV_DTYPE = '"Personal,Commercial"'
    DV_PREP = ('"Pinned,Carded,Pointed,Slide mounted,Spirit (ethanol),'
               'Spirit (IPA),Dry papered,Plastazote strip,Not prepared"')
    DV_COND = '"Excellent,Good,Fair,Poor,Damaged,Partial"'

    # =========================================================
    # Sheet 1: Personal Observations
    # =========================================================
    personal_cols = [
        ('Species', 30, False, None),
        ('Date', 12, False, None),
        ('Grid Ref', 14, False, None),
        ('Site Name', 25, False, None),
        ('VC', 8, False, None),
        ('Recorder', 18, False, None),
        ('Determiner', 18, False, None),
        ('Method', 18, False, DV_METHOD),
        ('Stage', 10, False, DV_STAGE),
        ('Sex', 10, False, DV_SEX),
        ('Qty', 6, False, None),
        ('Certainty', 12, False, DV_CERT),
        ('Comment', 30, False, None),
        ('Conservation', 25, True, None),
        ('Red List', 10, True, None),
        ('Rarity', 10, True, None),
        ('S41', 10, True, None),
        ('Legal Protection', 18, True, None),
        ('BAP', 10, True, None),
        ('TVK', 18, True, None),
        ('Common Name', 22, True, None),
        ('Class', 14, True, None),
        ('Order', 15, True, None),
        ('Family', 18, True, None),
        ('Sort Code', 10, True, None),
        ('Personal', 12, True, None),
        ('Commercial', 12, True, None),
        ('Specimens', 12, True, None),
    ]
    create_template_sheet(wb, "Personal Observations", personal_cols, MOSS)

    # =========================================================
    # Sheet 2: Commercial Observations
    # =========================================================
    commercial_cols = [
        ('Species', 30, False, None),
        ('Date', 12, False, None),
        ('Grid Ref', 14, False, None),
        ('Site Name', 25, False, None),
        ('VC', 8, False, None),
        ('Recorder', 18, False, None),
        ('Determiner', 18, False, None),
        ('Method', 18, False, DV_METHOD),
        ('Stage', 10, False, DV_STAGE),
        ('Sex', 10, False, DV_SEX),
        ('Qty', 6, False, None),
        ('Certainty', 12, False, DV_CERT),
        ('Comment', 30, False, None),
        ('Project Name', 20, False, None),
        ('Client', 18, False, None),
        ('Embargo Until', 14, False, None),
        ('Conservation', 25, True, None),
        ('Red List', 10, True, None),
        ('Rarity', 10, True, None),
        ('S41', 10, True, None),
        ('Legal Protection', 18, True, None),
        ('BAP', 10, True, None),
        ('TVK', 18, True, None),
        ('Common Name', 22, True, None),
        ('Class', 14, True, None),
        ('Order', 15, True, None),
        ('Family', 18, True, None),
        ('Sort Code', 10, True, None),
        ('Personal', 12, True, None),
        ('Commercial', 12, True, None),
        ('Specimens', 12, True, None),
    ]
    create_template_sheet(wb, "Commercial Observations", commercial_cols, AMBER)

    # =========================================================
    # Sheet 3: Insect Collection
    # =========================================================
    collection_cols = [
        ('Species', 30, False, None),
        ('Date Collected', 14, False, None),
        ('Grid Ref', 14, False, None),
        ('Site Name', 25, False, None),
        ('Collector', 18, False, None),
        ('Determiner', 18, False, None),
        ('Sex', 10, False, DV_SEX),
        ('Specimen Code', 14, False, None),
        ('Preparation Type', 16, False, DV_PREP),
        ('Storage Location', 16, False, None),
        ('Drawer/Unit', 12, False, None),
        ('Condition', 12, False, DV_COND),
        ('Label Data', 25, False, None),
        ('Notes', 25, False, None),
        ('Conservation', 25, True, None),
        ('Red List', 10, True, None),
        ('Rarity', 10, True, None),
        ('S41', 10, True, None),
        ('Legal Protection', 18, True, None),
        ('BAP', 10, True, None),
        ('TVK', 18, True, None),
        ('Common Name', 22, True, None),
        ('Order', 15, True, None),
        ('Family', 18, True, None),
        ('Sort Code', 10, True, None),
        ('Personal', 12, True, None),
        ('Commercial', 12, True, None),
        ('Specimens', 12, True, None),
    ]
    create_template_sheet(wb, "Insect Collection", collection_cols, BLUE)

    # =========================================================
    # Records Sheet (hidden, pre-populated + refreshable via VBA)
    # =========================================================
    ws_rec = wb.create_sheet("Records")
    rec_headers = ['TVK', 'PersonalCount', 'PersonalLastDate',
                   'CommercialCount', 'CommercialProjects', 'SpecimenCount',
                   'PendingPersonal', 'PendingCommercial']
    rec_hdr_font = Font(name='Arial', bold=True, size=9)
    rec_data_font = Font(name='Arial', size=9)
    for ci, h in enumerate(rec_headers, 1):
        ws_rec.cell(row=1, column=ci, value=h).font = rec_hdr_font

    obs_path = paths.OBSERVATUM_DB
    if obs_path.exists():
        try:
            obs_conn = sqlite3.connect(str(obs_path))
            obs_conn.row_factory = sqlite3.Row
            personal, commercial, specimens = {}, {}, {}
            for row in obs_conn.execute(
                    "SELECT species_tvk, COUNT(*) as cnt, MAX(date) as last_date "
                    "FROM observations WHERE record_type='Personal' "
                    "AND species_tvk IS NOT NULL AND species_tvk!='' GROUP BY species_tvk"):
                personal[row["species_tvk"]] = (row["cnt"], (row["last_date"] or "")[:10])
            for row in obs_conn.execute(
                    "SELECT species_tvk, COUNT(*) as cnt, "
                    "GROUP_CONCAT(DISTINCT project_name) as projects "
                    "FROM observations WHERE record_type='Commercial' "
                    "AND species_tvk IS NOT NULL AND species_tvk!='' GROUP BY species_tvk"):
                proj = row["projects"] or ""
                pl = [p.strip() for p in proj.split(",") if p.strip()]
                commercial[row["species_tvk"]] = (
                    row["cnt"],
                    ", ".join(pl[:3]) + ("..." if len(pl) > 3 else "")
                )
            for row in obs_conn.execute(
                    "SELECT species_tvk, COUNT(*) as cnt FROM specimens "
                    "WHERE species_tvk IS NOT NULL AND species_tvk!='' GROUP BY species_tvk"):
                specimens[row["species_tvk"]] = row["cnt"]
            obs_conn.close()
            all_tvks = sorted(set(personal) | set(commercial) | set(specimens))
            for ri, tvk in enumerate(all_tvks, 2):
                p = personal.get(tvk, (0, ""))
                c = commercial.get(tvk, (0, ""))
                s = specimens.get(tvk, 0)
                ws_rec.cell(row=ri, column=1, value=tvk).font = rec_data_font
                ws_rec.cell(row=ri, column=2, value=p[0]).font = rec_data_font
                ws_rec.cell(row=ri, column=3, value=p[1]).font = rec_data_font
                ws_rec.cell(row=ri, column=4, value=c[0]).font = rec_data_font
                ws_rec.cell(row=ri, column=5, value=c[1]).font = rec_data_font
                ws_rec.cell(row=ri, column=6, value=s).font = rec_data_font
                ws_rec.cell(row=ri, column=7, value=0).font = rec_data_font
                ws_rec.cell(row=ri, column=8, value=0).font = rec_data_font
            print(f"  Pre-populated Records: {len(all_tvks):,} species from observatum.db")
        except Exception as e:
            print(f"  Records pre-population skipped: {e}")
    ws_rec.sheet_state = 'hidden'

    # =========================================================
    # Sheet 5: Instructions
    # =========================================================
    ws_help = wb.create_sheet("Instructions")
    instructions = [
        "Tabella - Field Entry Workbook",
        "",
        "OVERVIEW:",
        "  This workbook contains 3 data entry templates:",
        "  1. Personal Observations - for personal iRecord data",
        "  2. Commercial Observations - for commercial surveys with project/client/embargo",
        "  3. Insect Collection - for physical specimen cataloguing",
        "",
        "HOW TO USE:",
        "  1. Copy this master .xlsm file for each project or year",
        "  2. Choose the appropriate tab for your data type",
        "  3. Type species names in the Species column (Column A)",
        "  4. Conservation status, Red List, Rarity, S41 auto-populate next to the species",
        "  5. TVK, Common Name, Class, Order, Family auto-populate at end of row",
        "  6. If TVK shows '?' the species was not found in UKSI",
        "  7. Fill in remaining fields (Date, Grid Ref, Site Name, etc.)",
        "  8. Save and import into Observatum via the appropriate wizard",
        "",
        "FUZZY SEARCH:",
        "  Type partial names like 'Rut mac' for Rutpela maculata",
        "  The popup shows taxonomy info to help you pick the right species",
        "  Single matches auto-select without a popup",
        "",
        "SPECIES NAMES:",
        "  For aggregates: 'Bombus lucorum agg.' or 'Bombus lucorum s.l.'",
        "  For sensu stricto: 'Araniella cucurbitina s.s.'",
        "  Search the UKSI sheet with Ctrl+F to find correct names",
        "",
        "CONSERVATION COLUMNS (drawn from Codex, all British taxa):",
        "  Conservation: Combined status string from UKSI taxa fields",
        "  Red List: Modern GB Red List (CR, EN, VU, NT, DD, LC) or legacy (RDB1-3)",
        "  Rarity: Modern GB Rarity (NR, NS) or legacy (Na, Nb, Notable)",
        "  S41: Country priority listing (England, Wales, Scotland, NI)",
        "       - drawn from NERC S.41, Welsh S7, Scottish Biodiversity List, NI Priority",
        "  Legal Protection: WCA, Habitats Regs, Habitats Directive, Bern, CITES, etc.",
        "  BAP: 'UK' if listed on the UK Biodiversity Action Plan",
        "  Source: JNCC Conservation Designations (Dec 2023) consolidated via Codex",
        "          plus any imported species status reviews",
        "",
        "PERSONAL OBSERVATIONS (green tab):",
        "  Standard observation fields matching iRecord format",
        "  After entry: upload CSV to iRecord, then sync into Observatum",
        "  Or import directly into Observatum via Import Wizard",
        "",
        "COMMERCIAL OBSERVATIONS (amber tab):",
        "  Same as Personal plus Project Name, Client, and Embargo Until columns",
        "  The import wizard reads these from the CSV automatically",
        "  After entry: import directly into Observatum via Import Wizard",
        "",
        "INSECT COLLECTION (blue tab):",
        "  Specimen-specific fields: prep type, storage, drawer, condition, etc.",
        "  After entry: import into Observatum via Specimen Import Wizard",
        "",
        "This workbook is self-contained and works anywhere on your system.",
        "The UKSI sheet contains the full species reference (~140,000 entries).",
    ]

    title_font = Font(name='Arial', bold=True, size=14, color=MOSS)
    heading_font = Font(name='Arial', bold=True, size=11)
    body_font = Font(name='Arial', size=10)

    for row_idx, text in enumerate(instructions, 1):
        cell = ws_help.cell(row=row_idx, column=1, value=text)
        if row_idx == 1:
            cell.font = title_font
        elif text.rstrip().endswith(':'):
            cell.font = heading_font
        else:
            cell.font = body_font

    ws_help.column_dimensions['A'].width = 85

    # Hidden rows for VBA RefreshRecords
    ws_help.cell(row=100, column=1, value=sys.executable)
    script_path = str(Path(__file__).resolve().parent / "refresh_records.py")
    ws_help.cell(row=101, column=1, value=script_path)
    csv_cache_path = str(OUTPUT_DIR / ".records_cache.csv")
    ws_help.cell(row=102, column=1, value=csv_cache_path)

    # Reorder sheets
    desired_order = ["Personal Observations", "Commercial Observations",
                     "Insect Collection", "UKSI", "Records", "Instructions"]
    for i, name in enumerate(desired_order):
        idx = wb.sheetnames.index(name)
        wb.move_sheet(name, offset=i - idx)

    wb.save(str(output_path))
    print(f"\n  Workbook saved: {output_path}")
    print(f"    Personal Observations: 1000 rows (green tab)")
    print(f"    Commercial Observations: 1000 rows (amber tab)")
    print(f"    Insect Collection: 1000 rows (blue tab)")
    print(f"    UKSI: {len(species_data):,} species entries")
    print(f"    Instructions: usage guide")


# =================================================================
# VBA INJECTION
# =================================================================
def inject_vba(xlsx_path: Path):
    """Open .xlsx in Excel, inject VBA macro, save as .xlsm."""
    try:
        import win32com.client
    except ImportError:
        print("\n  pywin32 not installed -- saving as .xlsx without macro.")
        print("  To enable macro: pip install pywin32")
        return None

    from Tabella.vba_source import MODULE_CODE, THISWORKBOOK_CODE
    import shutil

    xlsm_path = xlsx_path.with_suffix(".xlsm")
    tmp_path = xlsx_path.with_suffix(".tmp.xlsx")
    shutil.copy2(str(xlsx_path), str(tmp_path))

    print(f"\n  Injecting VBA macro...")

    xl = win32com.client.Dispatch("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False

    try:
        wb = xl.Workbooks.Open(str(tmp_path.resolve()))
        vb_proj = wb.VBProject

        mod = vb_proj.VBComponents.Add(1)
        mod.Name = "DataEntry"
        mod.CodeModule.AddFromString(MODULE_CODE)

        tw = vb_proj.VBComponents("ThisWorkbook")
        tw.CodeModule.AddFromString(THISWORKBOOK_CODE)

        wb.SaveAs(str(xlsm_path.resolve()), FileFormat=52)
        wb.Close(SaveChanges=False)
        xl.Quit()

        try:
            tmp_path.unlink()
        except OSError:
            pass
        try:
            xlsx_path.unlink()
        except OSError:
            pass

        print(f"  Macro-enabled workbook: {xlsm_path.name}")
        return xlsm_path

    except Exception as e:
        print(f"\n  VBA injection failed: {e}")
        if "Programmatic access" in str(e):
            print("\n  Fix: Excel > File > Options > Trust Centre > Trust Centre Settings")
            print("       > Macro Settings > tick 'Trust access to the VBA project object model'")
        print(f"\n  Plain workbook still available: {xlsx_path.name}")

        try:
            wb.Close(SaveChanges=False)
        except Exception:
            pass
        try:
            xl.Quit()
        except Exception:
            pass
        try:
            tmp_path.unlink()
        except OSError:
            pass
        return None


# =================================================================
# MAIN
# =================================================================
def main():
    if not UKSI_PATH.exists():
        print(f"UKSI database not found: {UKSI_PATH}")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d')
    xlsx_path = OUTPUT_DIR / f"Tabella_Field_Entry_{timestamp}.xlsx"

    print("Tabella -- Creating Field Entry Workbook")
    print(f"  UKSI database: {UKSI_PATH}")
    print(f"  Codex database: {CODEX_PATH}")
    print(f"  Output folder: {OUTPUT_DIR}")

    print("\nLoading Codex conservation data...")
    codex_data = load_codex_data(CODEX_PATH)

    print("\nLoading UKSI species data...")
    species = load_uksi_species(UKSI_PATH, codex_data)
    print(f"  Loaded {len(species):,} species entries (including agg./s.l./s.s. variants)")

    print("\nBuilding workbook...")
    create_workbook(species, xlsx_path)

    result = inject_vba(xlsx_path)

    if result:
        print(f"\nDone! Output: {result}")
    else:
        print(f"\nDone! Output: {xlsx_path} (no macro -- install pywin32 to enable)")


if __name__ == "__main__":
    main()
