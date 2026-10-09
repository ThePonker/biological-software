"""
Examen — Excel workbook export (E2)

Produces the multi-sheet workbook that backs a written assessment. Structure and
conventions follow published practice surveyed across eleven reports; see
docs/38_Report_Survey.md.

    from Examen.workbook_export import export_workbook
    path = export_workbook(result, detail, project, path)

Sheets
------
    Summary              metrics, with the stamp that makes them defensible
    Key species          Rare Key first, then Scarce (Telfer), with accounts
    Species appendix     full list, taxonomic order, computed footer
    Habitats             biotope -> habitat, SQI, % national pool
    Assemblages          SATs with Favourable Condition threshold and PtT
    Guilds               larval and adult composition
    Status definitions   the three-version annex, generated

Why the figures are presented the way they are
----------------------------------------------
* Every figure carries its evidence. "Favourable - 19 spp., threshold 11", not
  "Favourable". "SQI 145 from 234 scoring species", not "SQI 145".
* Withhold what cannot be supported. Pantheon does not trust an SQI below 15
  scoring species; below that the count is shown and the index is not.
* Report the percentages, not a verdict. Two threshold conventions are in
  circulation (Telfer 2023: ~10% Key and >1% Rare Key; Kirby-Lambert: 5-10%
  high, >10% exceptional). The author cites whichever they use.
* Exclusions are stated, not silent. Species Pantheon cannot analyse, and
  species without a TVK, are counted and shown.

Key Species vs Codex tiers
--------------------------
Two vocabularies, deliberately kept apart:

* Codex `_classify` gives Rare / Scarce / Priority. That is Codex's internal
  classification and drives Examen's on-screen tiers.
* Telfer's Key Species / Rare Key Species is the published evaluation framework
  the profession cites, and it splits RDB differently: ALL Red Data Book
  categories are Rare Key, where Codex puts RDB3 and RDBK in Scarce.

The workbook computes Key / Rare Key here, in the report layer, following
Telfer exactly, and leaves Codex's tiers untouched.

    Key Species      = RDB (v1); CR/EN/VU/NT/DD (v2); NR/NS (v3); plus SPI
    Rare Key Species = RDB (v1); CR/EN/VU/DD (v2); NR (v3)

Species accounts
----------------
Accounts come from observatum.db.species_profiles. The stored profile is the
reusable part; the site-specific closing sentence ("a single adult was taken
from FIT 3 in July") is WRITTEN, not generated -- a manufactured sentence reads
uniformly across a whole table in a way a real account does not.

The occurrence column therefore carries a placeholder followed by the evidence
needed to write it: count, places, months. Where no profile exists the account
cell is left blank, which also shows which accounts are worth writing next.
"""

import json
import os
import sqlite3
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths  # noqa: E402

try:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
except ImportError:  # pragma: no cover
    raise ImportError("openpyxl is required for workbook export")

try:
    from openpyxl.cell.rich_text import CellRichText, TextBlock
    from openpyxl.cell.text import InlineFont
    _RICH = True
except ImportError:  # openpyxl < 3.1: greyed parts fall back to an (n/a) suffix
    _RICH = False

# Which designations count where is decided in ONE place -- CodexRepository,
# the same functions _classify uses. The workbook calls them rather than keeping
# its own list, so the report can never disagree with the key-species count.
try:
    from shared.repositories.codex_repository import (
        _priority_applies, _legal_applies, StatusEntry)
except ImportError:  # pragma: no cover -- degrade to "everything applies"
    _priority_applies = None
    _legal_applies = None
    StatusEntry = None

# Dates dd/mm/yyyy and mode labels: the same formatter the Examen screen uses.
from shared.display_format import dmy, mode_label  # noqa: E402


# ============================================================
# Presentation
# ============================================================

HEAD_FILL = PatternFill("solid", fgColor="4A7C59")      # Moss green
HEAD_FONT = Font(bold=True, color="FFFFFF", size=10)
TITLE_FONT = Font(bold=True, size=13, color="2F4858")
NOTE_FONT = Font(italic=True, size=9, color="6B6B6B")
BOLD = Font(bold=True, size=10)

GOOD_FILL = PatternFill("solid", fgColor="D6E9D6")      # meets threshold
NEAR_FILL = PatternFill("solid", fgColor="F6E6C8")      # >= 80% of threshold
THIN = Side(style="thin", color="D0D0D0")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

# Pantheon does not trust an SQI computed from fewer than this many scoring
# species. Telfer calls an assemblage above it "well represented".
SQI_MIN_SPECIES = 15

# The occurrence sentence is written by the author, not generated. This marker
# opens the cell, followed by the evidence needed to write it.
OCCURRENCE_PLACEHOLDER = "[write occurrence]"


_TAX_CACHE = {}


def _taxon(k):
    """Order/family/common for a key-species entry, from examen_data.load_taxonomy."""
    tvk = getattr(k, "tvk", "") or ""
    if tvk and tvk not in _TAX_CACHE:
        try:
            from Examen.examen_data import load_taxonomy
        except ImportError:
            from examen_data import load_taxonomy
        _TAX_CACHE.update(load_taxonomy([tvk]))
    return _TAX_CACHE.get(tvk, {})


def _in_taxonomic_order(items, tvk=lambda x: x.tvk, name=lambda x: x.name):
    """examen_data.in_taxonomic_order -- one sort rule for the screen and every export."""
    try:
        from Examen.examen_data import in_taxonomic_order
    except ImportError:
        from examen_data import in_taxonomic_order
    return in_taxonomic_order(items, tvk, name)


def _sqi_value(s):
    """SQI number from an SQIResult, tolerating field-name differences."""
    if s is None:
        return None
    for name in ("sqi", "value", "index"):
        v = getattr(s, name, None)
        if isinstance(v, (int, float)):
            return v
    return None


def _sqi_n(s):
    """Scoring-species count from an SQIResult."""
    if s is None:
        return 0
    for name in ("species_with_sqs", "scoring_species", "n_scoring", "count"):
        v = getattr(s, name, None)
        if isinstance(v, int):
            return v
    return 0


def _sqi_label(s):
    for name in ("label", "name", "title"):
        v = getattr(s, name, None)
        if isinstance(v, str):
            return v
    return ""


def _sqi_cell(s):
    """SQI for display: the number, or the evidence when it cannot be trusted."""
    n = _sqi_n(s)
    v = _sqi_value(s)
    if not n or v is None:
        return "-"
    if n < SQI_MIN_SPECIES:
        return f"({n} sp)" if n == 1 else f"({n} spp)"
    return int(round(v))


# ============================================================
# Telfer's Key Species framework
# ============================================================

_RARE_V1 = {"RDB1", "RDB 1", "RDB2", "RDB 2", "RDB3", "RDB 3",
            "RDBK", "RDB K", "RDBI", "RDB I"}
_RARE_V2 = {"CR", "EN", "VU", "DD", "RE", "EX", "EW"}
_SCARCE_V2 = {"NT"}
_RARE_V3 = {"NR"}
_SCARCE_V3 = {"NS"}
_SCARCE_V1 = {"NA", "NB", "NOTABLE", "N", "SCARCE"}


def _norm(v):
    return (v or "").strip().upper()


def telfer_tier(entry):
    """'rare' | 'scarce' | '' for a KeySpeciesEntry, per Telfer (2023).

    Rare Key Species: Red Data Book (v1); Threatened and Data Deficient (v2);
    Nationally Rare (v3).
    Scarce Key Species: Near Threatened (v2); Nationally Scarce / Notable (v3
    and v1). Priority Species are Key but not Rare Key.
    """
    r = _norm(getattr(entry, "rarity", ""))
    t = _norm(getattr(entry, "threat", ""))
    tl = _norm(getattr(entry, "threat_legacy", ""))

    # NA -- not an established native -- is never Key, whatever its rarity.
    # Mirrors CodexRepository._classify; see patch_na_not_key.py.
    if t == "NA":
        return ""
    if r in _RARE_V3 or t in _RARE_V2 or tl in _RARE_V1:
        return "rare"
    if r in _SCARCE_V3 or r in _SCARCE_V1 or t in _SCARCE_V2 or tl in _SCARCE_V1:
        return "scarce"
    if getattr(entry, "priority", None) or getattr(entry, "legal", None):
        return "scarce"          # SPI and protected species are Key, not Rare Key
    return "scarce" if getattr(entry, "tier", "") else ""


def status_string(entry):
    """Comma-separated status, both axes, as published reports write it."""
    parts = []
    for v in (getattr(entry, "threat", ""), getattr(entry, "threat_legacy", ""),
              getattr(entry, "rarity", "")):
        if v and v not in parts:
            parts.append(v)
    for j in getattr(entry, "priority", None) or []:
        parts.append(_short_jurisdiction(j))
    if getattr(entry, "legal", None):
        parts.append(f"Legal ({len(entry.legal)})")
    return ", ".join(parts)


def _short_jurisdiction(value):
    v = (value or "").lower()
    if "s.41" in v or "s41" in v or "section 41" in v:
        return "S41"
    if "wales" in v or "s7" in v:
        return "Wales S7"
    if "scottish" in v:
        return "SBL"
    if "northern ireland" in v or v.startswith("ni "):
        return "NI Priority"
    if "bap" in v:
        return "UK BAP"
    return value or ""


# ---- jurisdiction-aware status cells --------------------------------------

NA_GREY = "9CA3AF"

# Appendix labels (CodexRepository._priority_label output) back to a substring
# _priority_applies recognises. "SBL" in particular carries no "scottish".
_LABEL_KEYS = (("S41 (research", "research"), ("UK BAP (research", "research"), ("S41", "s41"), ("Wales S7", "wales"), ("SBL", "scottish"),
               ("NI Priority", "ni priority"), ("UK BAP", "bap"))


def _priority_ok(value, jurisdiction):
    if _priority_applies is None:
        return True
    return _priority_applies(value, jurisdiction)


def _legal_ok(text, jurisdiction):
    if _legal_applies is None or StatusEntry is None:
        return True
    return _legal_applies(StatusEntry(value=text, detail=text), jurisdiction)


def _label_ok(token, jurisdiction):
    if token.startswith("Legal:"):
        return _legal_ok(token[len("Legal:"):].strip(), jurisdiction)
    for prefix, key in _LABEL_KEYS:
        if token.startswith(prefix):
            return _priority_ok(key, jurisdiction)
    return True      # threat / rarity codes and anything unrecognised: GB-wide


def status_parts(entry, jurisdiction):
    """[(text, applies), ...] for a KeySpeciesEntry."""
    parts = []
    for v in (getattr(entry, "threat", ""), getattr(entry, "threat_legacy", ""),
              getattr(entry, "rarity", "")):
        if v and (v, True) not in parts:
            parts.append((v, True))
    for j in getattr(entry, "priority", None) or []:
        parts.append((_short_jurisdiction(j), _priority_ok(j, jurisdiction)))
    legal = getattr(entry, "legal", None) or []
    ok = sum(1 for x in legal if _legal_ok(x, jurisdiction))
    if ok:
        parts.append((f"Legal ({ok})", True))
    if len(legal) - ok:
        parts.append((f"Legal, other jurisdiction ({len(legal) - ok})", False))
    return parts


def _parts_from_string(s, jurisdiction):
    """Same, for a non-key species' Codex display string."""
    return [(t, _label_ok(t, jurisdiction))
            for t in (x.strip() for x in (s or "").split(",")) if t]


def status_cell(parts, jurisdiction):
    """Cell value: plain text, with other jurisdictions' designations in grey."""
    if not parts:
        return ""
    if all(a for _, a in parts):
        return ", ".join(t for t, _ in parts)
    if _RICH:
        blocks = []
        for i, (t, a) in enumerate(parts):
            if i:
                blocks.append(", ")
            blocks.append(t if a else TextBlock(InlineFont(color=NA_GREY, i=True), t))
        return CellRichText(*blocks)
    return ", ".join(t if a else f"{t} (n/a {jurisdiction})" for t, a in parts)


# ============================================================
# Supporting data
# ============================================================

def _reference_counts():
    """National species totals per biotope / habitat / SAT, for '% national pool'."""
    out = {"biotope": {}, "habitat": {}, "sat": {}}
    try:
        p = sqlite3.connect(f"file:{paths.PANTHEON_DB}?mode=ro", uri=True)
        for k, (tbl, col) in {"biotope": ("broad_biotope", "biotope"),
                              "habitat": ("habitats", "habitat"),
                              "sat": ("specific_assemblage_types", "sat_name")}.items():
            try:
                for v, n in p.execute(
                        f"SELECT {col}, COUNT(DISTINCT tvk) FROM {tbl} GROUP BY 1"):
                    if v:
                        out[k][v] = n
            except sqlite3.Error:
                pass
        p.close()
    except sqlite3.Error:
        pass
    return out


def _sat_thresholds():
    """Favourable Condition thresholds, from Examen's own verified copy."""
    here = os.path.dirname(os.path.abspath(__file__))
    for candidate in (os.path.join(here, "sat_thresholds.json"),
                      os.path.join(_ROOT_DIR(), "Examen", "sat_thresholds.json")):
        try:
            with open(candidate, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {k: (v.get("threshold") if isinstance(v, dict) else v)
                    for k, v in data.items()}
        except (OSError, ValueError):
            continue
    return {}


def _ROOT_DIR():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _profiles(tvks):
    """{tvk: (account_text, source_label)} -- your account, else an open-licence
    review account quoted and cited, else a pointer to the review. Read through
    shared/species_accounts.py, the reader the panel and editor use."""
    out = {}
    if not tvks:
        return out
    try:
        from shared.species_accounts import get_species_accounts
    except Exception:
        return out
    for tvk in tvks:
        try:
            acc = get_species_accounts(tvk)
        except Exception:
            continue
        if acc.own:
            out[tvk] = (acc.own, "Your account")
            continue
        r = acc.current_review
        if not (r and r.text):
            continue
        year = (r.date_published or "")[:4]
        cite = r.author or r.cite
        if year and year not in cite:
            cite = f"{cite} {year}"
        lic = (r.licence or "").lower()
        if any(k in lic for k in ("open government licence", "creative commons", "cc by", "ogl")):
            out[tvk] = (f"[Quoted from {cite}] {r.text}", f"Quoted - {cite}")
        else:
            out[tvk] = (f"See {cite}.", f"Not quoted (licence) - see {cite}")
    return out


def _survey_where(project_name, client="", survey_year=None):
    """WHERE clause and params for one survey's records in assessment_records."""
    where = "record_type='Commercial' AND project_name=?"
    params = [project_name]
    if client:
        where += " AND client=?"
        params.append(client)
    if survey_year:
        where += " AND substr(date,1,4)=?"
        params.append(str(survey_year))
    return where, params


def _contributions(project_name, client="", survey_year=None):
    """[(contributor, records)] for the survey's contributed records (backlog E21)."""
    if not project_name:
        return []
    where, params = _survey_where(project_name, client, survey_year)
    try:
        c = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
        rows = c.execute(
            f"""SELECT contributor, COUNT(1) FROM assessment_records
                WHERE {where} AND origin='contributed'
                GROUP BY contributor ORDER BY 2 DESC, 1""", params).fetchall()
        c.close()
    except sqlite3.Error:
        return []
    return [(who or "unnamed contributor", n) for who, n in rows]


def _contribution_line(contributions):
    """'162 records contributed by Moore, J.' -- or '' when there are none."""
    if not contributions:
        return ""
    total = sum(n for _, n in contributions)
    names = ", ".join(f"{who} ({n:,})" if len(contributions) > 1 else who
                      for who, n in contributions)
    return (f"{total:,} record{'s' if total != 1 else ''} contributed by {names}; "
            "included in every figure")


def _occurrences(tvks, project_name, client="", survey_year=None):
    """{tvk: 'Recorded from <sites> in <months>.'} generated from the records.

    The reusable profile is stored; the site-specific sentence is generated,
    because it differs per assessment. Published accounts always close with one.
    A species with contributed records names the contributor (backlog E21).
    """
    if not tvks:
        return {}
    out = {}
    where, params = _survey_where(project_name, client, survey_year)
    try:
        c = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
        rows = c.execute(
            f"""SELECT species_tvk, site_name, sub_location, date, quantity,
                       CASE WHEN origin='contributed' THEN COALESCE(contributor, '?') END
                FROM assessment_records WHERE {where} AND species_tvk IS NOT NULL""",
            params).fetchall()
        c.close()
    except sqlite3.Error:
        return {}

    MONTHS = ["January", "February", "March", "April", "May", "June", "July",
              "August", "September", "October", "November", "December"]
    grouped = {}
    for tvk, site, sub, dt, qty, contributor in rows:
        if tvk not in tvks:
            continue
        g = grouped.setdefault(tvk, {"places": set(), "months": set(), "n": 0,
                                     "by": set()})
        if contributor:
            g["by"].add(contributor)
        place = (sub or site or "").strip()
        if place:
            g["places"].add(place)
        try:
            g["months"].add(int(str(dt)[5:7]))
        except (ValueError, TypeError):
            pass
        try:
            g["n"] += int(qty or 1)
        except (TypeError, ValueError):
            g["n"] += 1

    for tvk, g in grouped.items():
        months = [MONTHS[m - 1] for m in sorted(g["months"]) if 1 <= m <= 12]
        places = sorted(g["places"])
        bits = [OCCURRENCE_PLACEHOLDER]
        bits.append("1 individual" if g["n"] == 1 else f"{g['n']} individuals")
        if places:
            bits.append(", ".join(places[:4])
                        + (" and elsewhere" if len(places) > 4 else ""))
        if months:
            bits.append(", ".join(months))
        if g["by"]:
            bits.append("contributed by " + ", ".join(sorted(g["by"])))
        out[tvk] = "  \u00b7  ".join(bits)
    return out


def _codex_provenance():
    """What the figures were computed against.

    Reproducibility needs more than a version number: the same Codex build,
    from the same JNCC spreadsheet and the same Pantheon release, gives the
    same figures. All three are recorded in codex.db.

    Returns [(label, value), ...] for the basis block.
    """
    meta, notes = {}, ""
    try:
        c = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)
        try:
            meta = {k: v for k, v in c.execute("SELECT key, value FROM metadata")}
        except sqlite3.Error:
            pass
        try:
            r = c.execute("SELECT notes FROM build_log ORDER BY id DESC "
                          "LIMIT 1").fetchone()
            notes = (r[0] or "") if r else ""
        except sqlite3.Error:
            pass
        c.close()
    except sqlite3.Error:
        pass

    version = meta.get("version") or meta.get("schema_version") or "unknown"
    built = (meta.get("build_date") or "")[:19].replace("T", " ")
    jncc = meta.get("jncc_date", "")

    pantheon = ""
    for token in notes.replace(",", " ").split():
        if token.lower().startswith("v3.") or token.lower().startswith("3."):
            pantheon = token.lstrip("vV")
            break

    out = [("Codex version", f"{version}" + (f", built {built}" if built else ""))]
    if jncc:
        out.append(("JNCC designations", jncc))
    if pantheon:
        out.append(("Pantheon version", pantheon))
    elif notes:
        out.append(("Source data", notes))
    return out


# ============================================================
# Sheet helpers
# ============================================================

def _header(ws, row, headings, widths=None):
    for i, h in enumerate(headings, start=1):
        cell = ws.cell(row=row, column=i, value=h)
        cell.fill, cell.font = HEAD_FILL, HEAD_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center",
                                   wrap_text=True)
        cell.border = BOX
    if widths:
        for i, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = ws.cell(row=row + 1, column=1)
    return row + 1


def _title(ws, text, sub=None):
    ws["A1"] = text
    ws["A1"].font = TITLE_FONT
    if sub:
        ws["A2"] = sub
        ws["A2"].font = NOTE_FONT
        return 4
    return 3


# ============================================================
# Sheets
# ============================================================

def _sqi_arith(s):
    """The SQI's own arithmetic, so a reader can check it from the sheet."""
    if s is None:
        return ""
    n = getattr(s, "species_analysed", 0) or s.species_with_sqs
    unscored = n - s.species_with_sqs
    tail = (f"; {unscored} Pantheon species without a score count as 0"
            if unscored > 0 else "")
    return (f"{s.sqs_sum} \u00f7 {n} species analysed \u00d7 100 "
            f"({s.species_with_sqs} scoring{tail})")


def _sheet_summary(wb, result, detail, project, stamp):
    ws = wb.create_sheet("Summary")
    r = _title(ws, stamp["title"],
               "Invertebrate assemblage assessment — figures and their basis")

    ws.column_dimensions["A"].width = 38
    ws.column_dimensions["B"].width = 22
    ws.column_dimensions["C"].width = 60

    keys = list(result.key_species)
    rare = [k for k in keys if telfer_tier(k) == "rare"]
    total = result.total_species or 1

    rows = [
        ("Species recorded", result.total_species, ""),
        ("Analysed by Pantheon", result.species_in_pantheon,
         "Species Pantheon holds ecology for; the remainder cannot be analysed."),
        ("Scoring species (SQS)", result.species_with_sqs,
         "Species carrying a Species Quality Score."),
        (None, None, None),
        ("Key Species", len(keys),
         "Rare, scarce, threatened or near threatened conservation status, "
         "plus Species of Principal Importance. Telfer (2023)."),
        ("% Key Species", f"{round(len(keys) / total * 100, 1)}%",
         "Telfer: close to 10% suggests potential national significance. "
         "Kirby-Lambert: 5-10% high quality, >10% exceptional."),
        ("Rare Key Species", len(rare),
         "Red Data Book, IUCN Threatened, Data Deficient, or Nationally Rare."),
        ("% Rare Key Species", f"{round(len(rare) / total * 100, 1)}%",
         "Telfer: more than 1% suggests potential national significance."),
        (None, None, None),
        ("Codex tiers — Rare", result.rare_count,
         "Codex's own classification; not the same split as Telfer's Rare Key."),
        ("Codex tiers — Scarce", result.scarce_count, ""),
        ("Codex tiers — Priority", result.priority_count, ""),
        (None, None, None),
        ("Species Quality Index (SQI)", _sqi_cell(result.overall_sqi),
         f"{_sqi_arith(result.overall_sqi)}. "
         f"Pantheon does not trust an SQI below {SQI_MIN_SPECIES}."),
        ("Stenotopic species (in SATs)", sum(result.sat_counts.values())
         if result.sat_counts else 0,
         "Species restricted to specific assemblage types."),
    ]

    # Both SQS bases, when any score was derived (patch_sqs_basis.py).
    _der = getattr(result, "derived_sqs_tvks", set()) or set()
    _pub = getattr(result, "overall_sqi_published", None)
    if _der and _pub is not None:
        _nm = {s.tvk: s.name for s in (getattr(detail, "species_list", None) or []) if s.tvk}
        _names = ", ".join(sorted(_nm.get(t, t) for t in _der))
        _i = next(n for n, row in enumerate(rows) if row[0] == "Species Quality Index (SQI)")
        rows[_i] = ("Species Quality Index (SQI)", _sqi_cell(result.overall_sqi),
                    f"{_sqi_arith(result.overall_sqi)}, including "
                    f"{len(_der)} scored from current status by Pantheon's published "
                    f"rule because Pantheon holds no score ({_names}).")
        rows.insert(_i + 1, ("SQI on Pantheon scores only", _sqi_cell(_pub),
                    f"{_sqi_arith(_pub)}, on Pantheon's published scores only. "
                    "Comparable with the Pantheon website and the literature."))

    for label, value, note in rows:
        if label is None:
            r += 1
            continue
        ws.cell(row=r, column=1, value=label).font = BOLD
        v = ws.cell(row=r, column=2, value=value)
        v.alignment = Alignment(horizontal="center")
        n = ws.cell(row=r, column=3, value=note)
        n.font = NOTE_FONT
        n.alignment = Alignment(wrap_text=True, vertical="top")
        r += 1

    # ---- the stamp: what makes these figures defensible later ----
    r += 2
    ws.cell(row=r, column=1, value="Basis of assessment").font = TITLE_FONT
    r += 1
    for label, value in stamp["basis"]:
        if label == "SQS basis" and _der:
            value = f"Pantheon published, plus {len(_der)} derived (both SQIs above)"
        ws.cell(row=r, column=1, value=label).font = BOLD
        ws.cell(row=r, column=2, value=value)
        r += 1

    r += 1
    for line in stamp["attribution"]:
        c = ws.cell(row=r, column=1, value=line)
        c.font = NOTE_FONT
        r += 1
    return ws


def _sheet_key_species(wb, result, project, stamp):
    ws = wb.create_sheet("Key species")
    r = _title(ws, "Key Species",
               "Rare Key Species first, then Scarce Key Species; "
               "taxonomic order within each. Telfer (2023).")

    r = _header(ws, r,
                ["Tier", "Order", "Family", "Species", "Common name",
                 "Conservation status", "SQS", "Broad biotope", "Habitat",
                 "Species account", "Account source",
                 "Occurrence — to write (evidence follows)"],
                [12, 16, 20, 26, 20, 26, 6, 22, 24, 70, 26, 44])

    keys = list(result.key_species)
    tvks = {k.tvk for k in keys if k.tvk}
    profiles = _profiles(tvks)
    occurrences = _occurrences(tvks, stamp["project_name"], stamp["client"],
                               stamp["survey_year"])

    # Taxonomic order within each tier, as the subtitle says (backlog E19).
    _tax = lambda ks: _in_taxonomic_order(ks, name=lambda k: k.species_name)  # noqa: E731
    ordered = (_tax(k for k in keys if telfer_tier(k) == "rare")
               + _tax(k for k in keys if telfer_tier(k) != "rare"))

    for k in ordered:
        tier = "Rare Key" if telfer_tier(k) == "rare" else "Scarce Key"
        prof, prof_source = profiles.get(k.tvk, ("", ""))
        ws.append([tier,
                   getattr(k, "order_name", "") or _taxon(k).get("order", ""),
                   k.family or _taxon(k).get("family", ""),
                   k.species_name,
                   getattr(k, "common_name", "") or _taxon(k).get("common", ""),
                   status_cell(status_parts(k, stamp["jurisdiction"]),
                               stamp["jurisdiction"]),
                   k.sqs or "",
                   k.broad_biotope or "",
                   k.habitat or "",
                   prof,
                   prof_source,
                   occurrences.get(k.tvk, "")])
        for col in (10, 12):
            ws.cell(row=ws.max_row, column=col).alignment = Alignment(
                wrap_text=True, vertical="top")
        if tier == "Rare Key":
            ws.cell(row=ws.max_row, column=1).font = BOLD

    r = ws.max_row + 2
    ws.cell(row=r, column=1,
            value="Species account: yours where written; otherwise the current published "
                  "review account, quoted and cited where its licence is open, or a "
                  "pointer to the review where it is not (see Account source). "
                  "The occurrence sentence is written by the author; the "
                  "column gives the evidence from this survey — count, places "
                  "and months — after the marker. Blank account cells have no "
                  "account yet.").font = NOTE_FONT
    return ws


def _sheet_appendix(wb, detail, result, stamp):
    ws = wb.create_sheet("Species appendix")
    r = _title(ws, "Species appendix",
               "All species recorded, in taxonomic order. Key species carry a "
               "conservation status.")

    r = _header(ws, r,
                ["Order", "Family", "Species", "Common name",
                 "Conservation status", "SQS", "Broad biotope", "Habitat",
                 "Records"],
                [16, 20, 28, 22, 24, 6, 22, 26, 9])

    key_by_tvk = {k.tvk: k for k in result.key_species if k.tvk}
    # Taxonomic order; species without a TVK last, so the exclusion shows (E19).
    species = _in_taxonomic_order(getattr(detail, "species_list", []) or [])
    no_tvk = 0
    scoring = 0
    sqs_total = 0

    for sp in species:
        if not sp.tvk:
            no_tvk += 1
        k = key_by_tvk.get(sp.tvk)
        juris = stamp["jurisdiction"]
        status = status_cell(status_parts(k, juris) if k
                             else _parts_from_string(getattr(sp, "status_full", "") or sp.status, juris), juris)
        if sp.sqs:
            scoring += 1
            sqs_total += sp.sqs
        ws.append([getattr(sp, "order_name", "") or "",
                   getattr(sp, "family", "") or "",
                   sp.name,
                   getattr(sp, "common_name", "") or "",
                   status,
                   sp.sqs or "",
                   sp.broad_biotope or "",
                   sp.habitat or "",
                   sp.count or ""])

    # ---- computed footer, as Wilson's appendices do ----
    # The SQI is the Summary's own figure: Pantheon divides by every species it
    # analysed, scored or not (Glory Park 144 / 123 = 117, the issued report). The
    # footer used to divide by scoring species only (144 / 120 = 120) -- two SQIs
    # in one workbook (found 8 Oct 2026).
    r = ws.max_row + 2
    osqi = getattr(result, "overall_sqi", None)
    analysed = (getattr(osqi, "species_analysed", 0) or getattr(result, "species_in_pantheon", 0)
                or scoring)
    for label, value in [
            ("Species recorded", len(species)),
            ("Without a TVK (not analysed)", no_tvk),
            ("Analysed by Pantheon", analysed),
            ("Scoring taxa", scoring),
            ("Species Quality Score (SQS)", getattr(osqi, "sqs_sum", None) or sqs_total),
            ("Species Quality Index (SQI)", _sqi_cell(osqi) if osqi is not None else "-")]:
        ws.cell(row=r, column=2, value=label).font = BOLD
        ws.cell(row=r, column=3, value=value).font = BOLD
        r += 1
    return ws


def _sheet_habitats(wb, result, refs):
    ws = wb.create_sheet("Habitats")
    r = _title(ws, "Habitats",
               "Biotope and habitat associations. % national pool is the share "
               "of the national fauna coded for that biotope or habitat which "
               "this sample holds.")

    r = _header(ws, r,
                ["Broad biotope", "Habitat", "Species", "Scoring", "SQI",
                 "% national pool"],
                [24, 30, 10, 10, 14, 16])

    bio_sqi = {_sqi_label(s): s for s in result.biotope_sqi}
    pair_counts = getattr(result, "biotope_habitat_counts", {}) or {}
    pair_sqi = getattr(result, "biotope_habitat_sqi", {}) or {}

    for bio in sorted(result.biotope_counts, key=lambda b: -result.biotope_counts[b]):
        n = result.biotope_counts[bio]
        tot = refs["biotope"].get(bio, 0)
        s = bio_sqi.get(bio)
        ws.append([bio, "", n, _sqi_n(s), _sqi_cell(s),
                   f"{round(n / tot * 100, 1)}%" if tot else "-"])
        ws.cell(row=ws.max_row, column=1).font = BOLD

        habs = pair_counts.get(bio, {})
        for hab in sorted(habs, key=lambda h: -habs[h]):
            hn = habs[hab]
            htot = refs["habitat"].get(hab, 0)
            hs = pair_sqi.get(bio, {}).get(hab)
            ws.append(["", hab, hn, _sqi_n(hs), _sqi_cell(hs),
                       f"{round(hn / htot * 100, 1)}%" if htot else "-"])

    r = ws.max_row + 2
    ws.cell(row=r, column=1,
            value="A species occupying two habitats is counted under both, so "
                  "habitat counts do not sum to the biotope total. SQI is "
                  f"withheld below {SQI_MIN_SPECIES} scoring species and the "
                  "count shown instead.").font = NOTE_FONT
    return ws


def _sheet_assemblages(wb, result, refs, thresholds):
    ws = wb.create_sheet("Assemblages")
    r = _title(ws, "Specific Assemblage Types (SATs)",
               "SATs are assemblages of stenotopic species — those restricted "
               "to particular resources. The Favourable Condition threshold is "
               "the species count expected of a site in favourable condition.")

    r = _header(ws, r,
                ["Specific Assemblage Type", "Species", "Scoring", "SQI",
                 "% national pool", "FC threshold", "Proportion to threshold",
                 "Reported condition"],
                [34, 10, 10, 12, 15, 14, 20, 34])

    sat_sqi = {_sqi_label(s): s for s in result.sat_sqi}
    counts = result.sat_counts or {}

    for sat in sorted(counts, key=lambda s: -counts[s]):
        n = counts[sat]
        s = sat_sqi.get(sat)
        tot = refs["sat"].get(sat, 0)
        fct = thresholds.get(sat)
        ptt = round(n / fct * 100) if fct else None
        if fct:
            cond = ("Favourable" if n >= fct else "Unfavourable") + \
                   f" — {n} spp., threshold {fct}"
        else:
            cond = f"{n} spp., no threshold published"
        ws.append([sat, n, _sqi_n(s), _sqi_cell(s),
                   f"{round(n / tot * 100, 1)}%" if tot else "-",
                   fct or "-", f"{ptt}%" if ptt is not None else "-", cond])
        if ptt is not None:
            row = ws.max_row
            if ptt >= 100:
                for col in range(1, 9):
                    ws.cell(row=row, column=col).fill = GOOD_FILL
            elif ptt >= 80:
                for col in range(1, 9):
                    ws.cell(row=row, column=col).fill = NEAR_FILL

    r = ws.max_row + 2
    ws.cell(row=r, column=1,
            value="Cross-cutting SATs (rich flower resource, scrub edge, "
                  "scrub-heath and moorland) occur in many situations and have "
                  "poor discriminatory value; exceeding the threshold is not on "
                  "its own sufficient to conclude national significance "
                  "(Webb et al., 2018).").font = NOTE_FONT
    return ws


def _sheet_saproxylic(wb, detail):
    """Saproxylic SQI and IEC (backlog E7). Only written when listed species occur."""
    try:
        from Examen.saproxylic import assess, band_text
    except ImportError:  # pragma: no cover
        from saproxylic import assess, band_text
    sap = assess(getattr(detail, "species_list", None) or [])
    if not sap.n_scored and not sap.n_iec:
        return None
    ws = wb.create_sheet("Saproxylic")
    caution = "" if sap.reliable else f" Fewer than {sap.min_species} listed species: treat with caution."
    r = _title(ws, "Saproxylic indices",
               f"Saproxylic Quality Index {sap.sqi:g} ({sap.sqs_total} \u00f7 {sap.n_scored} species "
               f"\u00d7 100); Index of Ecological Continuity {sap.iec} from {sap.n_iec} species."
               + caution)
    r = _header(ws, r, ["Species", "Saproxylic score", "IEC", "Status (list)"], [40, 16, 10, 16])
    for row in sap.rows:
        ws.append([row["species"], row["sqi_score"] if row["sqi_score"] else "-",
                   row["iec"] or "-", row["status"] or "-"])
    r = ws.max_row + 2
    for note in (
            "Thresholds, shown side by side rather than as a verdict: " + band_text(sap),
            "The IEC is cumulative across all surveys of a site and counts post-1950 records "
            "only, so the figure for one survey is a minimum.",
            sap.citation + " Species list as compiled by W. Heeney from khepri.uk, updated "
            "from Alexander's revision; names matched to the current UKSI."):
        ws.cell(row=r, column=1, value=note).font = NOTE_FONT
        r += 1
    return ws


def _sheet_guilds(wb, result):
    ws = wb.create_sheet("Guilds")
    r = _title(ws, "Feeding guilds", "Composition of the recorded assemblage.")
    r = _header(ws, r, ["Life stage", "Guild", "Species"], [14, 28, 10])
    for stage, counts in (("Larval", result.larval_guild_counts),
                          ("Adult", result.adult_guild_counts)):
        for guild, n in sorted((counts or {}).items(), key=lambda kv: -kv[1]):
            ws.append([stage, guild, n])
    return ws


STATUS_DEFINITIONS = [
    ("Version 1 — Shirt (1987) and JNCC reviews", None),
    ("RDB 1, Endangered",
     "In danger of extinction; survival unlikely if causal factors continue."),
    ("RDB 2, Vulnerable",
     "Likely to move into the Endangered category if causal factors continue."),
    ("RDB 3, Rare",
     "Small populations at risk but not Endangered or Vulnerable; 15 or fewer "
     "10-km squares."),
    ("RDB I, Indeterminate",
     "Endangered, Vulnerable or Rare, but insufficient information to say which."),
    ("RDB K, Insufficiently Known",
     "Suspected to merit a threat category but lacking sufficient information."),
    ("Nationally Scarce A (Na)", "16-30 10-km squares."),
    ("Nationally Scarce B (Nb)", "31-100 10-km squares."),
    ("Nationally Scarce / Notable (N)",
     "16-100 10-km squares, where information was insufficient to divide A from B."),
    (None, None),
    ("Version 2 — IUCN (2001) criteria", None),
    ("CR, Critically Endangered", "Extremely high risk of extinction in the wild."),
    ("EN, Endangered", "Very high risk of extinction in the wild."),
    ("VU, Vulnerable", "High risk of extinction in the wild."),
    ("NT, Near Threatened",
     "Close to qualifying, or likely to qualify, for a threatened category."),
    ("DD, Data Deficient",
     "Inadequate information to assess the risk of extinction. Not a category "
     "of threat."),
    ("LC, Least Concern", "Does not qualify for any of the above."),
    ("NA / NE", "Not Applicable (non-native or vagrant) / Not Evaluated."),
    (None, None),
    ("Version 3 — GB Rarity status", None),
    ("Nationally Rare (NR)",
     "Recorded from 15 or fewer British hectads in recent decades."),
    ("Nationally Scarce (NS)",
     "Not Nationally Rare, and recorded from no more than 100 British hectads."),
    (None, None),
    ("Policy and legislation", None),
    ("S41 / SPI",
     "Species of Principal Importance for the conservation of biodiversity in "
     "England, listed under Section 41 of the NERC Act 2006."),
    ("S41 (research only)",
     "Widespread species added to draw attention to research requirements "
     "rather than site-level conservation. Not treated as Key Species."),
    ("Legal protection",
     "Wildlife and Countryside Act 1981 Schedule 5, the Conservation of "
     "Habitats and Species Regulations 2017, and international instruments."),
    (None, None),
    ("Conventions", None),
    ("[square brackets]",
     "Pantheon flags the status as unreliable pending formal reassessment."),
    ("p prefix (pNS, pNT)", "A provisional status from an unpublished review."),
    ("(derived)",
     "A Species Quality Score Pantheon does not hold, derived from the species' "
     "current status by Pantheon's published rule. Included in the SQI; the "
     "Summary also gives the SQI on Pantheon's own scores alone."),
    ("Grey italic",
     "A designation that does not count towards Key Species for this "
     "assessment: it applies in another jurisdiction (see Summary), or "
     "is listed for research only. Shown for completeness."),
]


def _sheet_status(wb):
    ws = wb.create_sheet("Status definitions")
    r = _title(ws, "Nature conservation status categories")
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 88
    for label, text in STATUS_DEFINITIONS:
        if label is None:
            r += 1
            continue
        c = ws.cell(row=r, column=1, value=label)
        if text is None:
            c.font = TITLE_FONT
        else:
            c.font = BOLD
            t = ws.cell(row=r, column=2, value=text)
            t.alignment = Alignment(wrap_text=True, vertical="top")
        r += 1
    return ws


# ============================================================
# Entry point
# ============================================================

def _mark_derived(wb, result, detail):
    """On the species sheets: "16 (derived)" for a score derived from the rule,
    and "no Pantheon data" where Pantheon holds nothing for the species."""
    derived = getattr(result, "derived_sqs_tvks", set()) or set()
    nopan = getattr(result, "no_pantheon_tvks", set()) or set()
    if not (derived or nopan) or detail is None:
        return
    by_name = {s.name: s.tvk for s in (getattr(detail, "species_list", None) or []) if s.tvk}
    for title in ("Key species", "Species appendix"):
        if title not in wb.sheetnames:
            continue
        ws = wb[title]
        head = None
        for row in ws.iter_rows(min_row=1, max_row=12):
            vals = [c.value for c in row]
            if "Species" in vals and "SQS" in vals:
                head = (row[0].row, vals.index("Species") + 1, vals.index("SQS") + 1,
                        vals.index("Broad biotope") + 1 if "Broad biotope" in vals else None)
                break
        if not head:
            continue
        hr, c_sp, c_sqs, c_bio = head
        for r in range(hr + 1, ws.max_row + 1):
            tvk = by_name.get(ws.cell(r, c_sp).value)
            if not tvk:
                continue
            cell = ws.cell(r, c_sqs)
            if tvk in derived and cell.value not in (None, ""):
                cell.value = f"{cell.value} (derived)"
            if c_bio and tvk in nopan and not ws.cell(r, c_bio).value:
                ws.cell(r, c_bio).value = "no Pantheon data"


def export_workbook(result, detail, project, path,
                    jurisdiction="England", sqs_basis="Pantheon published",
                    pooled_years=False):
    """Write the assessment workbook. Returns the path written."""
    site = getattr(detail, "site", None)
    year = getattr(site, "survey_year", "") or ""
    name = getattr(project, "project_name", "") or getattr(site, "site_name", "")
    client = getattr(project, "client", "") or getattr(site, "client", "")

    title = f"{name}{f' — {year}' if year else ''}{f' — {client}' if client else ''}"
    contributed = _contributions(name, client, None if pooled_years else (year or None))
    stamp = {
        "title": title,
        "project_name": name,
        "client": client,
        "survey_year": year or None,
        "jurisdiction": jurisdiction,
        "basis": [
            ("Assessment run", dmy(date.today().isoformat())),
            ("Survey dates", f"{dmy(getattr(site, 'first_date', ''))} to "
                             f"{dmy(getattr(site, 'last_date', ''))}"),
            ("Visits", getattr(site, "visit_count", "")),
            ("Sites", ", ".join(getattr(project, "site_names", []) or []) or
                      getattr(site, "site_name", "")),
        ] + ([("Contributed records", _contribution_line(contributed))]
             if contributed else []) + [
            ("Survey scope", "all years pooled" if pooled_years
                             else f"survey year {year}" if year else "all records"),
            ("Analysis mode", mode_label(getattr(result, "mode", ""))),
            ("SQS basis", sqs_basis),
            ("Jurisdiction", jurisdiction),
        ] + _codex_provenance() + [
            ("Survey validity", "Two years from the survey date (CIEEM, 2019)"),
        ],
        "attribution": [
            "Taxonomy: UK Species Inventory, Natural History Museum. CC BY 4.0.",
            "Conservation designations: JNCC. Open Government Licence.",
            "Ecology and assemblage types: Pantheon (Webb et al., 2018), "
            "Natural England and CEH. Open Government Licence.",
            "Key Species framework after Telfer (2023).",
        ],
    }

    refs = _reference_counts()
    thresholds = _sat_thresholds()

    wb = Workbook()
    wb.remove(wb.active)
    _sheet_summary(wb, result, detail, project, stamp)
    _sheet_key_species(wb, result, project, stamp)
    _sheet_appendix(wb, detail, result, stamp)
    _sheet_habitats(wb, result, refs)
    _sheet_assemblages(wb, result, refs, thresholds)
    _sheet_saproxylic(wb, detail)
    _sheet_guilds(wb, result)
    _sheet_status(wb)

    _mark_derived(wb, result, detail)
    wb.save(path)
    return path
