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
    Taxonomic summary    taxa and species with status per order (E8b)
    Compartments         figures per sub-location, when there are 2+ (E6)
    Habitats           biotope -> habitat, SQI, % national pool
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

# openpyxl (about 0.15 s to import) is loaded only when a workbook is made (Round 16, D2): the
# names below are filled in by _load_openpyxl(), which every function that needs them calls first,
# so opening Examen no longer imports it.
Workbook = Alignment = Border = Font = PatternFill = Side = get_column_letter = None
CellRichText = TextBlock = InlineFont = None
_RICH = False
HEAD_FILL = HEAD_FONT = TITLE_FONT = NOTE_FONT = BOLD = GOOD_FILL = NEAR_FILL = THIN = BOX = None
_XL_LOADED = False


def _load_openpyxl() -> None:
    """Import openpyxl and make the module's styles (once)."""
    global _XL_LOADED, Workbook, Alignment, Border, Font, PatternFill, Side, get_column_letter
    global CellRichText, TextBlock, InlineFont, _RICH
    global HEAD_FILL, HEAD_FONT, TITLE_FONT, NOTE_FONT, BOLD, GOOD_FILL, NEAR_FILL, THIN, BOX
    if _XL_LOADED:
        return
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
    HEAD_FILL = PatternFill("solid", fgColor="4A7C59")      # Moss green
    HEAD_FONT = Font(bold=True, color="FFFFFF", size=10)
    TITLE_FONT = Font(bold=True, size=13, color="2F4858")
    NOTE_FONT = Font(italic=True, size=9, color="6B6B6B")
    BOLD = Font(bold=True, size=10)
    GOOD_FILL = PatternFill("solid", fgColor="D6E9D6")      # meets threshold
    NEAR_FILL = PatternFill("solid", fgColor="F6E6C8")      # >= PTT_NEAR % of threshold
    THIN = Side(style="thin", color="D0D0D0")
    BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
    _XL_LOADED = True


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

# Status names, the vernacular fallback and the SQI scale text (E8): one home,
# shared with the Examen screen.
try:
    from Examen.presentation import SQI_SCALE, vernacular
except ImportError:  # pragma: no cover
    from presentation import SQI_SCALE, vernacular


# ============================================================
# Presentation
# ============================================================


# "Near" a Favourable Condition threshold: the amber band, here and on the
# Assemblages tab (EXA15).
PTT_NEAR = 80

# Pantheon does not trust an SQI computed from fewer than this many scoring
# species. Telfer calls an assemblage above it "well represented".
SQI_MIN_SPECIES = 15

# The occurrence sentence is written by the author, not generated. This marker
# opens the cell, followed by the evidence needed to write it.
OCCURRENCE_PLACEHOLDER = "[write occurrence]"


_TAX_CACHE = {}


# CIEEM Advice Note on the Lifespan of Ecological Reports and Surveys (April 2019), as the
# summary prints it -- Wil's decision (Q80), 24 Oct 2026, replacing "two years".
CIEEM_VALIDITY = ("Age of survey data: under 12 months, likely valid; 12-18 months, likely valid "
                  "with exceptions (flag where an update may be needed); 18 months to 3 years, "
                  "an ecologist revisits the site and reviews validity; over 3 years, unlikely "
                  "to be valid (CIEEM, 2019)")


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


def spp(n) -> str:
    """'sp.' for one species, 'spp.' for any other number (L25: "1 spp." read wrongly)."""
    return "sp." if n == 1 else "spp."


def _sqi_cell(s):
    """SQI for display: the number, or the evidence when it cannot be trusted.
    The Habitats and Assemblages tabs show this same cell (EXA15)."""
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
    if _is_not_native(entry):
        return ""
    axis = _axis_tier(entry)
    if axis:
        return axis
    if getattr(entry, "priority", None) or getattr(entry, "legal", None):
        return "scarce"          # SPI and protected species are Key, not Rare Key
    return "scarce" if getattr(entry, "tier", "") else ""


def _is_not_native(entry):
    # NA -- not an established native -- is never Key, whatever its rarity.
    # Mirrors CodexRepository._classify; see patch_na_not_key.py.
    return _norm(getattr(entry, "threat", "")) == "NA"


def _axis_tier(entry):
    """'rare' | 'scarce' | '' from the rarity and threat statuses alone."""
    r = _norm(getattr(entry, "rarity", ""))
    t = _norm(getattr(entry, "threat", ""))
    tl = _norm(getattr(entry, "threat_legacy", ""))
    if r in _RARE_V3 or t in _RARE_V2 or tl in _RARE_V1:
        return "rare"
    if r in _SCARCE_V3 or r in _SCARCE_V1 or t in _SCARCE_V2 or tl in _SCARCE_V1:
        return "scarce"
    return ""


def status_only_tier(entry):
    """telfer_tier without Species of Principal Importance or legal protection.

    A species that is Key only because it is on a priority list (S41 etc.) or
    legally protected -- Codex tier "Priority" -- is not counted. Codex gives a
    Rare or Scarce tier only for a status (a specialist panel such as Spider
    Amber included), so such a tier still counts when its code is not in the
    sets above, whatever priority or legal listings the species also has.
    """
    if _is_not_native(entry):
        return ""
    axis = _axis_tier(entry)
    if axis:
        return axis
    return "scarce" if getattr(entry, "tier", "") in ("Rare", "Scarce") else ""


def status_string(entry):
    """Comma-separated status, both axes, as published reports write it."""
    parts = []
    for v in (getattr(entry, "threat", ""), getattr(entry, "threat_legacy", ""),
              getattr(entry, "rarity", "")):
        if v and v not in parts:
            parts.append(v)
    for j in getattr(entry, "priority", None) or []:
        parts.append(_short_jurisdiction(j))
    # Each legal instrument named, as non-key rows are (EXA10).
    for x in getattr(entry, "legal", None) or []:
        parts.append(f"Legal: {x}")
    if getattr(entry, "status_note", ""):
        parts.append(entry.status_note)
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
    # Each legal instrument named, greyed where it does not apply -- the same
    # cell a non-key row gets from _parts_from_string (EXA10; was "Legal (3)").
    for x in getattr(entry, "legal", None) or []:
        parts.append((f"Legal: {x}", _legal_ok(x, jurisdiction)))
    if getattr(entry, "status_note", ""):
        parts.append((entry.status_note, True))      # "status held at sensu lato"
    return parts


def _parts_from_string(s, jurisdiction):
    """Same, for a non-key species' Codex display string."""
    return [(t, _label_ok(t, jurisdiction))
            for t in (x.strip() for x in (s or "").split(",")) if t]


# Rarity and threat codes: the statuses a review can downgrade, so the only ones bracketed.
STATUS_CODES = frozenset(_norm(c) for c in (_RARE_V1 | _RARE_V2 | _SCARCE_V2 | _RARE_V3
                                            | _SCARCE_V3 | _SCARCE_V1))


# Never bracketed: the IUCN threat categories that are not a status -- least concern, not
# applicable, not evaluated, waiting list (as codex_repository treats them). Matched by exact
# spelling: Codex writes the threat category "NA" but the rarity Notable A "Na", which is a
# status and is bracketed. DD (data deficient) counts towards Rare Key Species, so it can be.
NEVER_BRACKET = frozenset({"LC", "NA", "NE", "WL"})


def never_bracket(code) -> bool:
    """True for a threat category that is not a status (exact spelling; see NEVER_BRACKET)."""
    return (code or "").strip() in NEVER_BRACKET


def status_codes(entry):
    """The entry's own rarity and threat codes that can be bracketed (never a priority, legal or
    note label, and never the threat categories LC / NA / NE / WL)."""
    out = []
    for v in (getattr(entry, "threat", ""), getattr(entry, "threat_legacy", ""),
              getattr(entry, "rarity", "")):
        if v and v not in out and not never_bracket(v):
            out.append(v)
    return tuple(out)


def string_codes(text):
    """The rarity and threat codes in a non-key species' Codex display string (the same parts
    bracket_parts brackets when it is given no codes)."""
    return tuple(t for t, _ in _parts_from_string(text, "England")
                 if _norm(t) in STATUS_CODES and not never_bracket(t))


def bracket_parts(parts, bracketed, codes=None):
    """[(text, applies)] with the rarity and threat codes in [square brackets] when the species
    is marked as likely to be downgraded. Priority listings, legal protection and notes (such as
    "status held at sensu lato") are not statuses that review downgrades, so they stay as they
    are. codes: a key species' own codes (status_codes); without it, a part is bracketed when it
    is a known rarity or threat code."""
    if not bracketed:
        return parts
    own = ({_norm(c) for c in codes if not never_bracket(c)} if codes is not None
           else STATUS_CODES)
    return [(f"[{t}]" if _norm(t) in own and not never_bracket(t) else t, a) for t, a in parts]


UNCHECKED_NOTE = ("Status marks could not be checked against Codex; they are applied as saved.")


def _bracket_for(stamp):
    """tvk -> bool: is the species bracketed in the survey this stamp describes."""
    from Examen import status_marks as sm
    return sm.bracket_checker(stamp.get("project_name", ""), stamp.get("client", ""),
                              stamp.get("survey_year") or "")


def status_cell(parts, jurisdiction):
    """Cell value: plain text, with other jurisdictions' designations in grey."""
    _load_openpyxl()
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

# What "% national pool" means, stated wherever the figure is shown (EXA13).
NATIONAL_POOL_NOTE = (
    "% national pool: species recorded here coded for the biotope, habitat or SAT, as a "
    "share of the national pool -- every current UKSI species bridged to a Pantheon taxon "
    "coded for it, each species counted once however many Pantheon taxa were merged into it.")


def _reference_counts():
    """National species pool per biotope / habitat / SAT, for '% national pool'.

    PantheonRepository.national_pool_counts -- the one definition, shared with the
    Habitats and Assemblages tabs."""
    try:
        from shared.repositories.pantheon_repository import PantheonRepository
        repo = PantheonRepository()
        try:
            return repo.national_pool_counts()
        finally:
            repo.close()
    except Exception as e:  # noqa: BLE001 -- the column shows "-" rather than failing
        print(f"[workbook_export] national pool unavailable: {e}")
        return {"biotope": {}, "habitat": {}, "sat": {}}


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


def _occurrences(tvks, project_name, client="", survey_year=None, preview_rows=None):
    """{tvk: 'Recorded from <sites> in <months>.'} generated from the records.

    The reusable profile is stored; the site-specific sentence is generated,
    because it differs per assessment. Published accounts always close with one.
    A species with contributed records names the contributor (backlog E21).
    """
    if not tvks:
        return {}
    out = {}
    if preview_rows is not None:       # a Data Entry preview: the survey's records as they will be
        rows = [(r[1], r[3], r[4], r[2], r[5], (r[11] or None) if len(r) > 11 else None)
                for r in preview_rows if r[1]]
    else:
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
    _load_openpyxl()
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
    _load_openpyxl()
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


def _analysed(result):
    """Species analysed -- the SQI's divisor, one figure everywhere (EXA5)."""
    n = getattr(result, "species_analysed", 0)
    if n:
        return n
    o = getattr(result, "overall_sqi", None)
    return getattr(o, "species_analysed", 0) or getattr(result, "species_in_pantheon", 0)


def _analysed_note(result):
    held = getattr(result, "species_in_pantheon", 0)
    extra = _analysed(result) - held
    note = (f"{held} held by Pantheon (ecology or a published score, through the TVK "
            "bridge)")
    if extra > 0:
        note += (f", plus {extra} Pantheon does not hold, scored from current status by "
                 "Pantheon's rule")
    return note + ". The SQI divides by this figure; the rest cannot be analysed."


def _stenotopic(result):
    """Distinct species in at least one SAT (EXA4), not one per SAT membership."""
    n = getattr(result, "stenotopic_count", None)
    if n is not None:
        return n
    return 0


def _sheet_summary(wb, result, detail, project, stamp):
    _load_openpyxl()
    ws = wb.create_sheet("Summary")
    r = _title(ws, stamp["title"],
               "Invertebrate assemblage assessment — figures and their basis")

    ws.column_dimensions["A"].width = 38
    ws.column_dimensions["B"].width = 22
    ws.column_dimensions["C"].width = 60

    keys = list(result.key_species)
    rare = [k for k in keys if telfer_tier(k) == "rare"]
    status_only = [k for k in keys if status_only_tier(k)]
    total = result.total_species or 1
    from Examen import status_marks as sm
    br0 = _bracket_for(stamp)
    coded = {getattr(k, "tvk", "") for k in keys if status_codes(k)}
    # bracketed on a code, as shown, and only while the status marked still stands (Codex's)
    br = lambda tvk: tvk in coded and br0(tvk)  # noqa: E731
    any_bracketed = any(br(getattr(k, "tvk", "")) for k in keys)
    so_rev, rare_rev = sm.revised_key_figures(keys, br)
    revised_note = ("Leaves out species marked as likely to be downgraded on review "
                    "(shown in [square brackets]).")

    rows = [
        ("Species recorded", result.total_species,
         "One per taxon; a species recorded as s.l. and s.s. counts once."
         if getattr(result, "merged_tvks", None) else ""),
        ("Species analysed", _analysed(result), _analysed_note(result)),
        ("Scoring species (SQS)", result.species_with_sqs,
         "Species carrying a Species Quality Score."),
        (None, None, None),
        ("Key Species", len(keys),
         "Rare, scarce, threatened or near threatened conservation status, "
         "plus Species of Principal Importance."),
        ("% Key Species", f"{round(len(keys) / total * 100, 1)}%",
         "Compare with surveys of similar effort. About 10% is commonly treated "
         "as indicating potential national significance."),
        ("Key Species (status only)", len(status_only),
         "Rarity and threat statuses only. Species of Principal Importance and "
         "protected species without such a status are left out; report them "
         "separately."),
        ("% Key Species (status only)", f"{round(len(status_only) / total * 100, 1)}%",
         "Comparable between surveys whatever the priority lists."),
        *([("Key Species (status only, revised)", so_rev, revised_note),
           ("% Key Species (status only, revised)", f"{round(so_rev / total * 100, 1)}%",
            revised_note)] if any_bracketed else []),
        ("Rare Key Species", len(rare),
         "Red Data Book, IUCN Threatened, Data Deficient, or Nationally Rare."),
        ("% Rare Key Species", f"{round(len(rare) / total * 100, 1)}%",
         "More than 1% is commonly treated as indicating potential national "
         "significance."),
        *([("Rare Key Species (revised)", rare_rev, revised_note)] if any_bracketed else []),
        (None, None, None),
        ("Codex tiers — Rare", result.rare_count,
         "Codex's own classification; not the same split as Rare Key above."),
        ("Codex tiers — Scarce", result.scarce_count, ""),
        ("Codex tiers — Priority", result.priority_count, ""),
        (None, None, None),
        ("Species Quality Index (SQI)", _sqi_cell(result.overall_sqi),
         f"{_sqi_arith(result.overall_sqi)}. "
         f"Pantheon does not trust an SQI below {SQI_MIN_SPECIES}."),
        ("What the SQI means", "", SQI_SCALE),
        ("Stenotopic species (in SATs)", _stenotopic(result),
         "Species restricted to specific assemblage types, each counted once "
         "however many SATs it belongs to."),
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
    if getattr(br0, "unchecked", False):
        ws.cell(row=r, column=1, value=UNCHECKED_NOTE).font = NOTE_FONT
        r += 1

    r += 1
    for line in stamp["attribution"]:
        c = ws.cell(row=r, column=1, value=line)
        c.font = NOTE_FONT
        r += 1
    return ws


def _sheet_key_species(wb, result, project, stamp):
    _load_openpyxl()
    ws = wb.create_sheet("Key species")
    r = _title(ws, "Key Species",
               "Rare Key Species first, then Scarce Key Species; "
               "taxonomic order within each.")

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
                               stamp["survey_year"], stamp.get("preview_rows"))
    br = _bracket_for(stamp)

    # Taxonomic order within each tier, as the subtitle says (backlog E19).
    _tax = lambda ks: _in_taxonomic_order(ks, name=lambda k: k.species_name)  # noqa: E731
    ordered = (_tax(k for k in keys if telfer_tier(k) == "rare")
               + _tax(k for k in keys if telfer_tier(k) != "rare"))

    for k in ordered:
        tier = "Rare Key" if telfer_tier(k) == "rare" else "Scarce Key"
        prof, prof_source = profiles.get(k.tvk, ("", ""))
        order = getattr(k, "order_name", "") or _taxon(k).get("order", "")
        family = k.family or _taxon(k).get("family", "")
        ws.append([tier,
                   order,
                   family,
                   (f"{k.species_name} ({k.recorded_note})"
                    if getattr(k, "recorded_note", "") else k.species_name),
                   vernacular(getattr(k, "common_name", "") or _taxon(k).get("common", ""),
                              family, order),
                   status_cell(bracket_parts(status_parts(k, stamp["jurisdiction"]),
                                             br(k.tvk), status_codes(k)), stamp["jurisdiction"]),
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
    _load_openpyxl()
    ws = wb.create_sheet("Species appendix")
    r = _title(ws, "Species appendix",
               "All species recorded, in taxonomic order. Key species carry a "
               "conservation status. Where UKSI holds no common name the group is "
               "described instead (“A ground beetle”).")

    r = _header(ws, r,
                ["Order", "Family", "Species", "Common name",
                 "Conservation status", "SQS", "Broad biotope", "Habitat",
                 "Records"],
                [16, 20, 28, 22, 24, 6, 22, 26, 9])

    key_by_tvk = {k.tvk: k for k in result.key_species if k.tvk}
    br = _bracket_for(stamp)
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
        status = status_cell(bracket_parts(
            status_parts(k, juris) if k
            else _parts_from_string(getattr(sp, "status_full", "") or sp.status, juris),
            br(sp.tvk),
            status_codes(k) if k else None), juris)
        if sp.sqs:
            scoring += 1
            sqs_total += sp.sqs
        ws.append([getattr(sp, "order_name", "") or "",
                   getattr(sp, "family", "") or "",
                   appendix_name(sp),
                   vernacular(getattr(sp, "common_name", ""), getattr(sp, "family", ""),
                              getattr(sp, "order_name", "")),
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
    analysed = _analysed(result) or scoring
    for label, value in [
            ("Species recorded", len(species)),
            ("Without a TVK (not analysed)", no_tvk),
            ("Species analysed", analysed),
            ("Scoring taxa", scoring),
            ("Species Quality Score (SQS)", getattr(osqi, "sqs_sum", None) or sqs_total),
            ("Species Quality Index (SQI)", _sqi_cell(osqi) if osqi is not None else "-")]:
        ws.cell(row=r, column=2, value=label).font = BOLD
        ws.cell(row=r, column=3, value=value).font = BOLD
        r += 1
    return ws


def appendix_name(sp):
    """The species cell: the name, and "(recorded as s.l. and s.s.)" where the
    survey recorded the species under its own TVK and its s.l. counterpart."""
    note = getattr(sp, "note", "") or ""
    return f"{sp.name} ({note})" if note else sp.name


def _sheet_habitats(wb, result, refs):
    _load_openpyxl()
    ws = wb.create_sheet("Habitats")
    r = _title(ws, "Habitats", "Biotope and habitat associations. " + NATIONAL_POOL_NOTE)

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
    ws.cell(row=r + 1, column=1, value=NATIONAL_POOL_NOTE).font = NOTE_FONT
    return ws


def _sheet_assemblages(wb, result, refs, thresholds):
    _load_openpyxl()
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
                   f" — {n} {spp(n)}, threshold {fct}"
        else:
            cond = f"{n} {spp(n)}, no threshold published"
        ws.append([sat, n, _sqi_n(s), _sqi_cell(s),
                   f"{round(n / tot * 100, 1)}%" if tot else "-",
                   fct or "-", f"{ptt}%" if ptt is not None else "-", cond])
        if ptt is not None:
            row = ws.max_row
            if ptt >= 100:
                for col in range(1, 9):
                    ws.cell(row=row, column=col).fill = GOOD_FILL
            elif ptt >= PTT_NEAR:
                for col in range(1, 9):
                    ws.cell(row=row, column=col).fill = NEAR_FILL

    r = ws.max_row + 2
    ws.cell(row=r, column=1,
            value="Cross-cutting SATs (rich flower resource, scrub edge, "
                  "scrub-heath and moorland) occur in many situations and have "
                  "poor discriminatory value; exceeding the threshold is not on "
                  "its own sufficient to conclude national significance "
                  "(Webb et al., 2018).").font = NOTE_FONT
    ws.cell(row=r + 1, column=1, value=NATIONAL_POOL_NOTE).font = NOTE_FONT
    return ws


def _sheet_saproxylic(wb, detail):
    """Saproxylic SQI and IEC (backlog E7). Only written when listed species occur."""
    _load_openpyxl()
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


def _sheet_table(wb, sheet, title, sub, table, widths, bold_rows=()):
    """A sheet laid out from (heads, rows, notes) -- the figures computed elsewhere."""
    _load_openpyxl()
    heads, rows, notes = table
    ws = wb.create_sheet(sheet)
    _header(ws, _title(ws, title, sub), heads, widths)
    for row in rows:
        ws.append(row)
        if row and row[0] in bold_rows:
            for col in range(1, len(heads) + 1):
                ws.cell(row=ws.max_row, column=col).font = BOLD
    r = ws.max_row + 2
    for note in notes:
        ws.cell(row=r, column=1, value=note).font = NOTE_FONT
        r += 1
    return ws


def _sheet_taxonomic(wb, result, detail):
    """Taxonomic summary (backlog E8b), from Examen.taxonomic_summary."""
    _load_openpyxl()
    try:
        from Examen import taxonomic_summary as tx
    except ImportError:  # pragma: no cover
        import taxonomic_summary as tx
    ts = tx.for_result(result, detail)
    if ts is None or not ts.rows:
        return None
    return _sheet_table(wb, "Taxonomic summary", "Taxonomic summary",
                        "Species with a conservation status in each group (Key Species, as on "
                        "the Summary). Groups are orders, most taxa first.",
                        ts.table(), [26, 52, 9, 16, 14],
                        bold_rows=(tx.SAPROXYLIC_LABEL, tx.TOTAL_LABEL))


def _sheet_compartments(wb, result, detail, project, jurisdiction):
    """Figures per compartment (backlog E6), from Examen.compartments. Only written
    when the survey's records name two or more compartments."""
    _load_openpyxl()
    try:
        from Examen import compartments as cp
    except ImportError:  # pragma: no cover
        import compartments as cp
    try:
        res = cp.for_detail(result, detail, project, jurisdiction)
    except Exception as e:  # noqa: BLE001 -- the extra sheet must not stop the export
        print(f"[workbook_export] compartments: {e}")
        return None
    if res is None or not res.shown:
        return None
    flagged = "; ".join(r.name for r in res.flagged)
    return _sheet_table(wb, "Compartments", "Compartments",
                        f"{len(res.rows)} compartments from the records' sub-locations. "
                        f"Threshold {res.threshold_pct:g}% of records"
                        + (f"; below it: {flagged}." if flagged else "; none below it."),
                        res.table(), [24, 10, 12, 10, 12, 9, 10, 9, 22],
                        bold_rows=(cp.COMBINED,))


def _sheet_guilds(wb, result):
    _load_openpyxl()
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
    _load_openpyxl()
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
    by_name = {}
    for s in (getattr(detail, "species_list", None) or []):
        if s.tvk:
            by_name[s.name] = s.tvk
            by_name[appendix_name(s)] = s.tvk
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


def _not_counted_line(result):
    """[("Not counted", sentence)] when taxa that are not invertebrates were left out of the
    species figures (shared.invertebrate_filter), else []."""
    left = getattr(result, "non_invertebrates", None) or {}
    if not left:
        return []
    n = len(left)
    names = ", ".join(sorted({str(v) for v in left.values()}, key=str.lower))
    return [("Not counted", f"{n} non-invertebrate taxa recorded incidentally are not counted: {names}."
             if n != 1 else
             f"1 non-invertebrate taxon recorded incidentally is not counted: {names}.")]


def export_workbook(result, detail, project, path,
                    jurisdiction="England", sqs_basis="Pantheon published",
                    pooled_years=False):
    """Write the assessment workbook. Returns the path written."""
    _load_openpyxl()
    site = getattr(detail, "site", None)
    year = getattr(site, "survey_year", "") or ""
    name = getattr(project, "project_name", "") or getattr(site, "site_name", "")
    client = getattr(project, "client", "") or getattr(site, "client", "")

    title = f"{name}{f' — {year}' if year else ''}{f' — {client}' if client else ''}"
    try:
        from Examen.examen_data import preview_note
    except ImportError:  # pragma: no cover
        from examen_data import preview_note
    preview_job = getattr(site, "preview_job", "") or ""
    preview_rows = getattr(detail, "preview_rows", None) if preview_job else None
    contributed = _contributions(name, client, None if pooled_years else (year or None))
    stamp = {
        "title": title,
        "project_name": name,
        "client": client,
        "survey_year": year or None,
        "jurisdiction": jurisdiction,
        "preview_rows": preview_rows,
        "basis": ([("Preview", preview_note(preview_job, getattr(site, "preview_held_back", 0),
                                            getattr(site, "preview_years", "")))]
                  if preview_job else []) + [
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
        ] + _not_counted_line(result) + [
            ("Analysis mode", mode_label(getattr(result, "mode", ""))),
            ("SQS basis", sqs_basis),
            ("Jurisdiction", jurisdiction),
        ] + _codex_provenance() + [
            ("Survey validity", CIEEM_VALIDITY),
        ],
        "attribution": [
            "Taxonomy: UK Species Inventory, Natural History Museum. CC BY 4.0.",
            "Conservation designations: JNCC. Open Government Licence.",
            "Ecology and assemblage types: Pantheon (Webb et al., 2018), "
            "Natural England and CEH. Open Government Licence.",
        ],
    }

    refs = _reference_counts()
    thresholds = _sat_thresholds()

    wb = Workbook()
    wb.remove(wb.active)
    _sheet_summary(wb, result, detail, project, stamp)
    _sheet_key_species(wb, result, project, stamp)
    _sheet_appendix(wb, detail, result, stamp)
    _sheet_taxonomic(wb, result, detail)
    _sheet_compartments(wb, result, detail, project, jurisdiction)
    _sheet_habitats(wb, result, refs)
    _sheet_assemblages(wb, result, refs, thresholds)
    _sheet_saproxylic(wb, detail)
    _sheet_guilds(wb, result)
    _sheet_status(wb)

    _mark_derived(wb, result, detail)
    wb.save(path)
    return path
