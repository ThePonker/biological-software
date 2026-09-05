"""
Site Register — Data Layer (v3 — mode-aware, fixed Pantheon routing)

Uses the same PANTHEON_GB_STATUS_MAP as CodexRepository for consistent
Pantheon-only mode results across all tools.
"""

import sqlite3
import sys; sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
import paths
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum


DB_PATH = paths.OBSERVATUM_DB
CODEX_PATH = paths.CODEX_DB
PANTHEON_PATH = paths.PANTHEON_DB

# Mirror of CodexRepository mapping — keep in sync
PANTHEON_GB_STATUS_MAP = {
    "NR": ("gb_rarity", "NR"), "(NR)": ("gb_rarity", "NR"),
    "NR (marine)": ("gb_rarity", "NR"),
    "NS": ("gb_rarity", "NS"), "(NS)": ("gb_rarity", "NS"),
    "NS (marine)": ("gb_rarity", "NS"),
    "Na": ("gb_rarity_legacy", "Na"),
    "Nb": ("gb_rarity_legacy", "Nb"),
    "Notable": ("gb_rarity_legacy", "Notable"),
    "RDB 1": ("gb_red_list_legacy", "RDB1"),
    "RDB 2": ("gb_red_list_legacy", "RDB2"),
    "RDB 3": ("gb_red_list_legacy", "RDB3"),
    "RDB K": ("gb_red_list_legacy", "RDBK"),
    "RDB I": ("gb_red_list_legacy", "RDBK"),
    "pRDB 1": ("gb_red_list_legacy", "RDB1"),
    "pRDB 2": ("gb_red_list_legacy", "RDB2"),
    "pRDB 3": ("gb_red_list_legacy", "RDB3"),
    "Extinct": ("gb_red_list_legacy", "EX"),
}


class AnalysisMode(Enum):
    CODEX_FULL = "codex_full"
    PANTHEON_ONLY = "pantheon_only"


@dataclass
class SiteRecord:
    site_name: str
    project_name: str = ""
    client: str = ""
    visit_count: int = 0
    visit_dates: list = field(default_factory=list)
    species_count: int = 0
    key_species_count: int = 0
    key_species_pct: float = 0.0
    rare_count: int = 0
    scarce_count: int = 0
    priority_count: int = 0
    sqi: float = 0.0
    sqi_reliable: bool = True
    species_with_sqs: int = 0
    record_count: int = 0
    first_date: str = ""
    last_date: str = ""
    accumulation: list = field(default_factory=list)
    mode: str = "codex_full"


@dataclass
class SiteSpecies:
    name: str
    tvk: str
    count: int = 0
    sqs: int = 0
    status: str = ""
    tier: str = ""
    broad_biotope: str = ""
    habitat: str = ""


@dataclass
class SiteDetail:
    site: SiteRecord
    species_list: list = field(default_factory=list)
    biotope_counts: dict = field(default_factory=dict)
    habitat_counts: dict = field(default_factory=dict)
    sat_counts: dict = field(default_factory=dict)


@dataclass
class ProjectRecord:
    """One row per project+client — pools all sites."""
    project_name: str
    client: str = ""
    site_count: int = 0
    site_names: list = field(default_factory=list)
    visit_count: int = 0
    species_count: int = 0
    key_species_count: int = 0
    key_species_pct: float = 0.0
    rare_count: int = 0
    scarce_count: int = 0
    priority_count: int = 0
    sqi: float = 0.0
    sqi_reliable: bool = True
    species_with_sqs: int = 0
    record_count: int = 0
    first_date: str = ""
    last_date: str = ""
    mode: str = "codex_full"


def load_all_sites(mode=AnalysisMode.CODEX_FULL):
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA query_only = ON")
    c = conn.cursor()
    c.execute("PRAGMA table_info(observations)")
    cols = [r[1] for r in c.fetchall()]
    if "record_type" not in cols:
        conn.close()
        return []
    c.execute("""
        SELECT site_name, project_name, client,
               COUNT(*), COUNT(DISTINCT species_name),
               COUNT(DISTINCT date), MIN(date), MAX(date)
        FROM observations
        WHERE record_type = 'Commercial'
          AND site_name IS NOT NULL AND site_name != ''
        GROUP BY site_name, project_name ORDER BY site_name
    """)
    sites = []
    for row in c.fetchall():
        sites.append(SiteRecord(
            site_name=row[0], project_name=row[1] or "",
            client=row[2] or "", record_count=row[3],
            species_count=row[4], visit_count=row[5],
            first_date=row[6] or "", last_date=row[7] or "",
            mode=mode.value))
    conn.close()
    _enrich_sites(sites, mode)
    return sites


def load_site_detail(site_name, project_name="", mode=AnalysisMode.CODEX_FULL):
    if not DB_PATH.exists():
        return None
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA query_only = ON")
    c = conn.cursor()
    where = "record_type = 'Commercial' AND site_name = ?"
    params = [site_name]
    if project_name:
        where += " AND project_name = ?"
        params.append(project_name)

    c.execute(f"""SELECT site_name, project_name, client,
                         COUNT(*), COUNT(DISTINCT species_name),
                         COUNT(DISTINCT date), MIN(date), MAX(date)
                  FROM observations WHERE {where}""", params)
    row = c.fetchone()
    if not row or not row[0]:
        conn.close()
        return None

    site = SiteRecord(
        site_name=row[0], project_name=row[1] or "", client=row[2] or "",
        record_count=row[3], species_count=row[4], visit_count=row[5],
        first_date=row[6] or "", last_date=row[7] or "", mode=mode.value)

    c.execute(f"""SELECT species_name, species_tvk, COUNT(*) FROM observations
                  WHERE {where} AND species_name IS NOT NULL
                  GROUP BY species_name, species_tvk ORDER BY species_name""", params)
    species_rows = c.fetchall()

    c.execute(f"""SELECT date, species_name FROM observations
                  WHERE {where} AND date IS NOT NULL AND species_name IS NOT NULL
                  ORDER BY date""", params)
    seen = set()
    accum_by_date = {}
    for date, sp in c.fetchall():
        seen.add(sp)
        accum_by_date[date] = len(seen)
    site.visit_dates = sorted(accum_by_date.keys())
    site.accumulation = [(d, accum_by_date[d]) for d in site.visit_dates]
    conn.close()

    detail = SiteDetail(site=site)
    tvk_map = {row[1]: (row[0], row[2]) for row in species_rows if row[1]}
    tvks = list(tvk_map.keys())

    if mode == AnalysisMode.PANTHEON_ONLY:
        enrichment = _load_pantheon_only_data(tvks)
    else:
        enrichment = _load_codex_data(tvks)
    pantheon_eco = _load_pantheon_ecology(tvks)

    sqs_total = sqs_count = 0
    for tvk in tvks:
        name, count = tvk_map[tvk]
        cd = enrichment.get(tvk, {})
        pd = pantheon_eco.get(tvk, {})
        sqs = cd.get("sqs", 0)
        if sqs:
            sqs_total += sqs
            sqs_count += 1
        detail.species_list.append(SiteSpecies(
            name=name, tvk=tvk, count=count, sqs=sqs,
            status=cd.get("short_status", ""), tier=cd.get("tier", ""),
            broad_biotope=pd.get("biotope", ""), habitat=pd.get("habitat", "")))
        for b in pd.get("biotopes", []):
            detail.biotope_counts[b] = detail.biotope_counts.get(b, 0) + 1
        for h in pd.get("habitats", []):
            detail.habitat_counts[h] = detail.habitat_counts.get(h, 0) + 1

    if sqs_count > 0:
        site.sqi = round(sqs_total / sqs_count * 100)
        site.sqi_reliable = sqs_count >= 15
        site.species_with_sqs = sqs_count

    key = [s for s in detail.species_list if s.tier]
    site.key_species_count = len(key)
    site.rare_count = sum(1 for s in key if s.tier == "Rare")
    site.scarce_count = sum(1 for s in key if s.tier == "Scarce")
    site.priority_count = sum(1 for s in key if s.tier == "Priority")
    if site.species_count > 0:
        site.key_species_pct = round(len(key) / site.species_count * 100, 1)

    detail.species_list.sort(key=lambda s: (-s.sqs if s.tier else 0, s.name))
    for row in species_rows:
        if not row[1]:
            detail.species_list.append(SiteSpecies(name=row[0], tvk="", count=row[2]))
    return detail


# ============================================================
# Project-level queries (pools all sites in a project)
# ============================================================

def load_all_projects(mode=AnalysisMode.CODEX_FULL):
    """Load commercial projects grouped by project_name + client."""
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA query_only = ON")
    c = conn.cursor()
    c.execute("PRAGMA table_info(observations)")
    cols = [r[1] for r in c.fetchall()]
    if "record_type" not in cols:
        conn.close()
        return []
    c.execute("""
        SELECT project_name, client,
               COUNT(DISTINCT site_name) as site_count,
               COUNT(*) as records,
               COUNT(DISTINCT species_name) as species,
               COUNT(DISTINCT date) as visits,
               MIN(date), MAX(date),
               GROUP_CONCAT(DISTINCT site_name) as sites
        FROM observations
        WHERE record_type = 'Commercial'
          AND project_name IS NOT NULL AND project_name != ''
        GROUP BY project_name, client
        ORDER BY project_name
    """)
    projects = []
    for row in c.fetchall():
        site_names = sorted(set(row[8].split(",") if row[8] else []))
        projects.append(ProjectRecord(
            project_name=row[0], client=row[1] or "",
            site_count=row[2], record_count=row[3],
            species_count=row[4], visit_count=row[5],
            first_date=row[6] or "", last_date=row[7] or "",
            site_names=site_names, mode=mode.value))
    conn.close()
    _enrich_projects(projects, mode)
    return projects


def load_project_detail(project_name, client="", mode=AnalysisMode.CODEX_FULL):
    """Load all species across all sites in a project. Returns SiteDetail."""
    if not DB_PATH.exists():
        return None
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA query_only = ON")
    c = conn.cursor()
    where = "record_type = 'Commercial' AND project_name = ?"
    params = [project_name]
    if client:
        where += " AND client = ?"
        params.append(client)

    c.execute(f"""SELECT project_name, client,
                         COUNT(*), COUNT(DISTINCT species_name),
                         COUNT(DISTINCT date), MIN(date), MAX(date),
                         COUNT(DISTINCT site_name)
                  FROM observations WHERE {where}""", params)
    row = c.fetchone()
    if not row or not row[0]:
        conn.close()
        return None

    # Use SiteRecord to hold project-level summary (compatible with existing code)
    site = SiteRecord(
        site_name=row[0], project_name=row[0], client=row[1] or "",
        record_count=row[2], species_count=row[3], visit_count=row[4],
        first_date=row[5] or "", last_date=row[6] or "", mode=mode.value)

    # Pool all species across all sites
    c.execute(f"""SELECT species_name, species_tvk, COUNT(*) FROM observations
                  WHERE {where} AND species_name IS NOT NULL
                  GROUP BY species_name, species_tvk ORDER BY species_name""", params)
    species_rows = c.fetchall()

    # Accumulation across project
    c.execute(f"""SELECT date, species_name FROM observations
                  WHERE {where} AND date IS NOT NULL AND species_name IS NOT NULL
                  ORDER BY date""", params)
    seen = set()
    accum_by_date = {}
    for date, sp in c.fetchall():
        seen.add(sp)
        accum_by_date[date] = len(seen)
    site.visit_dates = sorted(accum_by_date.keys())
    site.accumulation = [(d, accum_by_date[d]) for d in site.visit_dates]
    conn.close()

    detail = SiteDetail(site=site)
    tvk_map = {row[1]: (row[0], row[2]) for row in species_rows if row[1]}
    tvks = list(tvk_map.keys())

    enrichment = (_load_pantheon_only_data(tvks) if mode == AnalysisMode.PANTHEON_ONLY
                  else _load_codex_data(tvks))
    pantheon_eco = _load_pantheon_ecology(tvks)

    sqs_total = sqs_count = 0
    for tvk in tvks:
        name, count = tvk_map[tvk]
        cd = enrichment.get(tvk, {})
        pd = pantheon_eco.get(tvk, {})
        sqs = cd.get("sqs", 0)
        if sqs:
            sqs_total += sqs
            sqs_count += 1
        detail.species_list.append(SiteSpecies(
            name=name, tvk=tvk, count=count, sqs=sqs,
            status=cd.get("short_status", ""), tier=cd.get("tier", ""),
            broad_biotope=pd.get("biotope", ""), habitat=pd.get("habitat", "")))
        for b in pd.get("biotopes", []):
            detail.biotope_counts[b] = detail.biotope_counts.get(b, 0) + 1
        for h in pd.get("habitats", []):
            detail.habitat_counts[h] = detail.habitat_counts.get(h, 0) + 1

    if sqs_count > 0:
        site.sqi = round(sqs_total / sqs_count * 100)
        site.sqi_reliable = sqs_count >= 15
        site.species_with_sqs = sqs_count

    key = [s for s in detail.species_list if s.tier]
    site.key_species_count = len(key)
    site.rare_count = sum(1 for s in key if s.tier == "Rare")
    site.scarce_count = sum(1 for s in key if s.tier == "Scarce")
    site.priority_count = sum(1 for s in key if s.tier == "Priority")
    if site.species_count > 0:
        site.key_species_pct = round(len(key) / site.species_count * 100, 1)

    detail.species_list.sort(key=lambda s: (-s.sqs if s.tier else 0, s.name))
    for row in species_rows:
        if not row[1]:
            detail.species_list.append(SiteSpecies(name=row[0], tvk="", count=row[2]))
    return detail


def _enrich_projects(projects, mode):
    """Enrich project records with SQI and key species from pooled species."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA query_only = ON")
    c = conn.cursor()
    for proj in projects:
        where = "record_type = 'Commercial' AND project_name = ?"
        params = [proj.project_name]
        if proj.client:
            where += " AND client = ?"
            params.append(proj.client)
        c.execute(f"""SELECT DISTINCT species_tvk FROM observations
                      WHERE {where} AND species_tvk IS NOT NULL AND species_tvk != ''""", params)
        tvks = [r[0] for r in c.fetchall()]
        if not tvks:
            continue
        enrichment = (_load_pantheon_only_data(tvks) if mode == AnalysisMode.PANTHEON_ONLY
                      else _load_codex_data(tvks))
        sqs_total = sqs_count = key_count = rare = scarce = priority = 0
        for tvk in tvks:
            cd = enrichment.get(tvk, {})
            sqs = cd.get("sqs", 0)
            if sqs:
                sqs_total += sqs
                sqs_count += 1
            tier = cd.get("tier", "")
            if tier:
                key_count += 1
                if tier == "Rare": rare += 1
                elif tier == "Scarce": scarce += 1
                elif tier == "Priority": priority += 1
        if sqs_count > 0:
            proj.sqi = round(sqs_total / sqs_count * 100)
            proj.sqi_reliable = sqs_count >= 15
            proj.species_with_sqs = sqs_count
        proj.key_species_count = key_count
        proj.rare_count = rare
        proj.scarce_count = scarce
        proj.priority_count = priority
        if proj.species_count > 0:
            proj.key_species_pct = round(key_count / proj.species_count * 100, 1)
    conn.close()


# ============================================================
# Codex-full
# ============================================================

def _tier_str(tier):
    # CodexRepository returns a KeySpeciesTier enum; callers expect a string.
    # Empty string for no tier, so `if species.tier` stays falsy for non-key
    # species and `tier == "Rare"` continues to work.
    if tier is None:
        return ""
    v = str(getattr(tier, "value", tier)).strip()
    return "" if v.lower() in ("none", "") else v


def _load_codex_data(tvks):
    """Conservation enrichment from Codex, via the canonical repository.

    Delegates to CodexRepository rather than querying codex.db directly. The
    repository is 11-track aware and is what PantheonAnalysisService already
    uses, so Examen and the analysis service cannot disagree.

    Returns {tvk: {"sqs": int, "short_status": str, "tier": str}} -- the same
    shape as before, so callers are unaffected.
    """
    if not tvks:
        return {}
    try:
        from shared.repositories.codex_repository import CodexRepository
    except ImportError:
        try:
            from src.repositories.codex_repository import CodexRepository
        except ImportError as e:
            print(f"[examen_data] CodexRepository unavailable: {e}")
            return {}

    try:
        repo = CodexRepository()
        statuses = repo.get_statuses_batch(tvks)
        scores = repo.get_sqs_scores(tvks)
    except Exception as e:
        print(f"[examen_data] Codex enrichment failed: {e}")
        return {}

    result = {}
    for tvk in tvks:
        st = statuses.get(tvk)
        result[tvk] = {
            "sqs": scores.get(tvk, 0) or 0,
            "short_status": getattr(st, "short_status", "") or "" if st else "",
            "tier": _tier_str(getattr(st, "tier", None)) if st else "",
        }
    return result


# ============================================================
# Pantheon-only (fixed routing)
# ============================================================

def _load_pantheon_only_data(tvks):
    if not tvks or not PANTHEON_PATH.exists():
        return {}
    pan = sqlite3.connect(str(PANTHEON_PATH))
    pc = pan.cursor()
    result = {}

    for tvk in tvks:
        pc.execute("SELECT sqs FROM sqs_scores WHERE tvk = ?", (tvk,))
        r = pc.fetchone()
        sqs = r[0] if r else 0

        # Parse GB Status + GB Red List + Section 41
        pc.execute("""SELECT reporting_category, abbreviation
                      FROM conservation_status WHERE tvk = ?""", (tvk,))

        gb_rarity = ""
        gb_rarity_legacy = ""
        gb_red_list = ""
        gb_red_list_legacy = ""
        section41 = False
        legal = False

        for cat, abbr in pc.fetchall():
            if cat == "GB Status":
                mapping = PANTHEON_GB_STATUS_MAP.get(abbr)
                if mapping:
                    track, value = mapping
                    if track == "gb_rarity" and not gb_rarity:
                        gb_rarity = value
                    elif track == "gb_rarity_legacy" and not gb_rarity_legacy:
                        gb_rarity_legacy = value
                    elif track == "gb_red_list_legacy" and not gb_red_list_legacy:
                        gb_red_list_legacy = value
            elif cat == "GB Red List":
                if abbr not in ("None", "Unknown", "Not reviewed"):
                    gb_red_list = abbr
            elif "Section 41" in cat:
                section41 = True
            elif cat == "Legal Protection":
                legal = True

        # Classify
        tracks = {}
        if gb_rarity:
            tracks["gb_rarity"] = gb_rarity
        if gb_rarity_legacy:
            tracks["gb_rarity_legacy"] = gb_rarity_legacy
        if gb_red_list:
            tracks["gb_red_list"] = gb_red_list
        if gb_red_list_legacy:
            tracks["gb_red_list_legacy"] = gb_red_list_legacy
        if section41:
            tracks["section_41"] = "England"
        if legal:
            tracks["legal_protection"] = "Yes"

        tier = _classify_tier(tracks)

        # Short status
        short = gb_rarity or gb_rarity_legacy or ""
        if not short:
            if gb_red_list and gb_red_list not in ("LC", "NA", "NE"):
                short = gb_red_list
            elif gb_red_list_legacy:
                short = gb_red_list_legacy
            elif section41:
                short = "S41"

        result[tvk] = {"sqs": sqs, "short_status": short, "tier": tier}

    pan.close()
    return result


# ============================================================
# Pantheon ecology (mode-independent)
# ============================================================

def _load_pantheon_ecology(tvks):
    if not tvks or not PANTHEON_PATH.exists():
        return {}
    pan = sqlite3.connect(str(PANTHEON_PATH))
    pc = pan.cursor()
    result = {}
    for tvk in tvks:
        pc.execute("SELECT biotope FROM broad_biotope WHERE tvk = ?", (tvk,))
        biotopes = [r[0] for r in pc.fetchall()]
        pc.execute("SELECT habitat FROM habitats WHERE tvk = ?", (tvk,))
        habitats = [r[0] for r in pc.fetchall()]
        result[tvk] = {"biotope": ", ".join(biotopes[:2]),
                       "habitat": ", ".join(habitats[:2]),
                       "biotopes": biotopes, "habitats": habitats}
    pan.close()
    return result


# ============================================================
# Site enrichment
# ============================================================

def _enrich_sites(sites, mode):
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA query_only = ON")
    c = conn.cursor()
    for site in sites:
        where = "record_type = 'Commercial' AND site_name = ?"
        params = [site.site_name]
        if site.project_name:
            where += " AND project_name = ?"
            params.append(site.project_name)
        c.execute(f"""SELECT DISTINCT species_tvk FROM observations
                      WHERE {where} AND species_tvk IS NOT NULL AND species_tvk != ''""", params)
        tvks = [r[0] for r in c.fetchall()]
        if not tvks:
            continue
        enrichment = (_load_pantheon_only_data(tvks) if mode == AnalysisMode.PANTHEON_ONLY
                      else _load_codex_data(tvks))
        sqs_total = sqs_count = key_count = rare = scarce = priority = 0
        for tvk in tvks:
            cd = enrichment.get(tvk, {})
            sqs = cd.get("sqs", 0)
            if sqs:
                sqs_total += sqs
                sqs_count += 1
            tier = cd.get("tier", "")
            if tier:
                key_count += 1
                if tier == "Rare": rare += 1
                elif tier == "Scarce": scarce += 1
                elif tier == "Priority": priority += 1
        if sqs_count > 0:
            site.sqi = round(sqs_total / sqs_count * 100)
            site.sqi_reliable = sqs_count >= 15
            site.species_with_sqs = sqs_count
        site.key_species_count = key_count
        site.rare_count = rare
        site.scarce_count = scarce
        site.priority_count = priority
        if site.species_count > 0:
            site.key_species_pct = round(key_count / site.species_count * 100, 1)
    conn.close()


# ============================================================
# Tier classification (mirrors CodexRepository)
# ============================================================

def _classify_tier(tracks):
    is_rare = is_scarce = is_priority = False
    rl = tracks.get("gb_red_list", "")
    if rl in ("CR", "EN", "VU", "DD", "EX", "RE"):
        is_rare = True
    elif rl == "NT":
        is_scarce = True
    if tracks.get("gb_rarity") == "NR":
        is_rare = True
    elif tracks.get("gb_rarity") == "NS":
        is_scarce = True
    legacy_rl = tracks.get("gb_red_list_legacy", "")
    if legacy_rl in ("RDB1", "RDB2"):
        is_rare = True
    elif legacy_rl in ("RDB3", "RDBK"):
        is_scarce = True
    if tracks.get("gb_rarity_legacy") in ("Na", "Nb", "Notable", "Spider-Amber"):
        is_scarce = True
    if tracks.get("section_41") or tracks.get("legal_protection"):
        is_priority = True
    if is_rare: return "Rare"
    if is_scarce: return "Scarce"
    if is_priority: return "Priority"
    return ""
