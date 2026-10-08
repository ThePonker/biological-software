"""
Examen — Data Layer (v5)

Queries observatum.db for commercial sites, projects, pooled species lists and
accumulation curves. Conservation enrichment and SQI are delegated to
CodexRepository; Pantheon ecology to PantheonRepository. This module owns no
conservation rules of its own.

v5 changes (Session 32)
-----------------------
SURVEY YEAR is now a first-class grouping. load_all_projects(by_year=True)
returns one row per project per survey year; by_year=False pools every year into
one row, as before.

Why it matters. Bicester Graven Hill is two surveys under one project name --
2023 (367 species, synced to iRecord) and 2025 (254 species, embargoed). Pooled,
they make a 519-species list that corresponds to no report. The 2025 report's
headline of 433 species turns out to be the cumulative 2023+2025 list, submitted
to Pantheon with every date restamped into the 2025 window because the tool
needed a single date range. Making the year explicit removes the reason for that.

v4 changes (retained)
---------------------
  - Optional date_from / date_to on every loader (ISO 'YYYY-MM-DD').
  - PANTHEON_GB_STATUS_MAP and _classify_tier DELETED. Both duplicated
    CodexRepository, and _classify_tier had drifted (RDB3/RDBK scarce here,
    treated differently there), so the two analysis modes classified by
    different rules. PANTHEON_ONLY now routes through
    CodexRepository.get_statuses_batch(tvks, PANTHEON_ONLY), which is correct
    and jurisdiction-aware.
  - The SQI arithmetic appeared in FOUR places. It is now one call to
    CodexRepository.compute_sqi.
  - Ecology lookups were one query per TVK -- over 1,500 round trips for a
    large project. Now batched via PantheonRepository.
  - Key-species percentage settled on TOTAL SPECIES RECORDED as the
    denominator, matching Wil's own reports ("34 ... equates to 7.8% of the
    species from the survey" = 34/433).
"""

import sqlite3
import sys; sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
import paths
from dataclasses import dataclass, field

try:
    from shared.repositories.codex_repository import CodexRepository, AnalysisMode
    from shared.repositories.pantheon_repository import PantheonRepository
except ImportError:  # standalone / older layout
    from src.repositories.codex_repository import CodexRepository, AnalysisMode
    from src.repositories.pantheon_repository import PantheonRepository


DB_PATH = paths.OBSERVATUM_DB

POOLED = ""     # survey_year value meaning "all years pooled"


# ============================================================
# Dataclasses (shapes unchanged -- views depend on these)
# ============================================================

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
    survey_year: str = POOLED


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
    order_name: str = ""
    family: str = ""
    common_name: str = ""
    status_full: str = ""          # jurisdiction-named, for exports


@dataclass
class SiteDetail:
    site: SiteRecord
    species_list: list = field(default_factory=list)
    biotope_counts: dict = field(default_factory=dict)
    habitat_counts: dict = field(default_factory=dict)
    sat_counts: dict = field(default_factory=dict)


@dataclass
class ProjectRecord:
    """One project. With by_year=True, one row per survey year."""
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
    survey_year: str = POOLED

    @property
    def display_name(self):
        return (f"{self.project_name} \u2014 {self.survey_year}"
                if self.survey_year else self.project_name)


# ============================================================
# Scoping
# ============================================================

def _scope(date_from=None, date_to=None, survey_year=None):
    """SQL fragment + params for a date window and/or a survey year.

    Dates are ISO throughout observatum.db, so both string comparison and
    substr(date,1,4) behave. Any argument may be omitted.
    """
    clause, params = "", []
    if survey_year:
        clause += " AND substr(date,1,4) = ?"
        params.append(str(survey_year))
    if date_from:
        clause += " AND date >= ?"
        params.append(date_from)
    if date_to:
        clause += " AND date <= ?"
        params.append(date_to)
    return clause, params


def survey_years():
    """Every survey year present in commercial records, newest first."""
    if not DB_PATH.exists():
        return []
    conn = _connect()
    try:
        return [r[0] for r in conn.execute(
            """SELECT DISTINCT substr(date,1,4) FROM assessment_records
               WHERE record_type = 'Commercial' AND date IS NOT NULL
                 AND date != '' ORDER BY 1 DESC""") if r[0]]
    finally:
        conn.close()


def date_range_available():
    """(min_date, max_date) across all commercial records, for UI defaults."""
    if not DB_PATH.exists():
        return ("", "")
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA query_only = ON")
    try:
        row = conn.execute(
            "SELECT MIN(date), MAX(date) FROM assessment_records "
            "WHERE record_type = 'Commercial' AND date IS NOT NULL").fetchone()
        return (row[0] or "", row[1] or "")
    finally:
        conn.close()


def _connect():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA query_only = ON")
    return conn


def _has_record_type(conn):
    cols = [r[1] for r in conn.execute("PRAGMA table_info(observations)")]
    return "record_type" in cols


# ============================================================
# Enrichment -- one path, both modes
# ============================================================

def _full_status(st):
    """Codex's display_status, with "Legal (n)" expanded to the instruments.

    For exports: the workbook greys each instrument that does not apply in the
    assessment's jurisdiction, and a bare count cannot be greyed. Codex's own
    displays keep the count.
    """
    if not st:
        return ""
    s = getattr(st, "display_status", "") or ""
    legal = list(getattr(st, "legal_protection", None) or [])
    if not legal:
        return s
    names = [((getattr(e, "detail", None) or getattr(e, "value", "")) or "").strip()
             for e in legal]
    parts = [p.strip() for p in s.split(",")
             if p.strip() and not p.strip().startswith("Legal (")]
    return ", ".join(parts + [f"Legal: {n}" for n in names if n])


def _load_status_data(tvks, mode=AnalysisMode.CODEX_FULL):
    """Conservation status + SQS per TVK, via CodexRepository.

    Both CODEX_FULL and PANTHEON_ONLY go through the same repository call, so
    the two modes cannot classify by different rules. Jurisdiction filtering
    (England by default) is applied inside the repository.

    Returns {tvk: {"sqs": int, "short_status": str, "tier": str}}.
    """
    if not tvks:
        return {}
    try:
        repo = CodexRepository()
        statuses = repo.get_statuses_batch(tvks, mode)
        scores = repo.get_sqs_scores(tvks, mode)
    except Exception as e:  # noqa: BLE001 -- degrade to unenriched, but say so
        print(f"[examen_data] enrichment failed: {e}")
        return {}

    result = {}
    for tvk in tvks:
        st = statuses.get(tvk)
        tier = getattr(st, "tier", None) if st else None
        tier_s = str(getattr(tier, "value", tier or "")).strip()
        result[tvk] = {
            "sqs": scores.get(tvk, 0) or 0,
            "short_status": (getattr(st, "short_status", "") or "") if st else "",
            "display_status": _full_status(st),
            "tier": "" if tier_s.lower() in ("none", "") else tier_s,
        }
    return result


def _load_pantheon_ecology(tvks):
    """Biotopes and habitats per TVK, batched.

    Previously one query per TVK -- over 1,500 round trips for a large project.
    """
    if not tvks:
        return {}
    try:
        repo = PantheonRepository()
        biotopes = repo.get_broad_biotopes(tvks)
        habitats = repo.get_habitats(tvks)
        sats = repo.get_sats(tvks)
        repo.close()
    except Exception as e:  # noqa: BLE001
        print(f"[examen_data] Pantheon ecology unavailable: {e}")
        return {}

    result = {}
    for tvk in tvks:
        b = biotopes.get(tvk, [])
        h = habitats.get(tvk, [])
        result[tvk] = {
            "biotope": ", ".join(b[:2]),
            "habitat": ", ".join(h[:2]),
            "biotopes": b,
            "habitats": h,
            "sats": sats.get(tvk, []),
        }
    return result


def _apply_metrics(record, tvks, species_list, mode):
    """Fill SQI and key-species counts on a SiteRecord / ProjectRecord.

    The single place the SQI is computed -- it previously appeared in four.
    CodexRepository.compute_sqi owns the arithmetic and the 15-species
    reliability threshold.
    """
    if tvks:
        try:
            sqi = CodexRepository().compute_sqi(tvks, mode)
            record.sqi = sqi["sqi"]
            record.sqi_reliable = sqi["reliable"]
            record.species_with_sqs = sqi["scoring_species"]
        except Exception as e:  # noqa: BLE001
            print(f"[examen_data] SQI failed: {e}")

    key = [s for s in species_list if s.tier]
    record.key_species_count = len(key)
    record.rare_count = sum(1 for s in key if s.tier == "Rare")
    record.scarce_count = sum(1 for s in key if s.tier == "Scarce")
    record.priority_count = sum(1 for s in key if s.tier == "Priority")
    # Denominator is total species recorded, matching Wil's reports:
    # "34 ... equates to 7.8% of the species from the survey" = 34/433.
    if record.species_count > 0:
        record.key_species_pct = round(len(key) / record.species_count * 100, 1)


def load_taxonomy(tvks):
    """{tvk: {'common', 'family', 'order'}} from UKSI.

    The one lookup: the species list, the Species tab and every export use it.
    """
    import paths
    tvks = [t for t in dict.fromkeys(tvks) if t]
    if not tvks or not paths.UKSI_DB.exists():
        return {}
    out = {}
    conn = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)
    try:
        for i in range(0, len(tvks), 500):
            batch = tvks[i:i + 500]
            ph = ",".join("?" * len(batch))
            for t, cn, fam, order in conn.execute(
                    "SELECT t.tvk, COALESCE(cn.common_name, ''), COALESCE(t.family, ''), "
                    'COALESCE(t."order", \'\') FROM taxa t LEFT JOIN common_names cn '
                    f"ON t.tvk = cn.tvk AND cn.preferred = 1 WHERE t.tvk IN ({ph})", batch):
                out[t] = {"common": cn, "family": fam, "order": order}
    finally:
        conn.close()
    return out


# Sorts after every real key: species UKSI does not hold, and species with no TVK.
UNSORTED = 10 ** 12


def taxonomic_sort_keys(tvks):
    """{tvk: key} for taxonomic order -- the specimen collection's rule (backlog E19).

    Insect order in the conventional sequence, then UKSI's sort_code within the
    order: Observatum's compute_taxonomic_sort_key, imported, not copied. Orders
    outside the insect list (spiders, woodlice...) follow the insects, still in
    UKSI order. TVKs UKSI does not hold are absent; sort them last with UNSORTED.
    """
    import paths
    try:
        from Observatum.src.utils.constants import compute_taxonomic_sort_key
    except ImportError:  # pragma: no cover -- UKSI order alone
        def compute_taxonomic_sort_key(_order, sort_code):
            return sort_code or 0
    tvks = [t for t in dict.fromkeys(tvks) if t]
    if not tvks or not paths.UKSI_DB.exists():
        return {}
    out = {}
    conn = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)
    try:
        for i in range(0, len(tvks), 500):
            batch = tvks[i:i + 500]
            ph = ",".join("?" * len(batch))
            for t, order, code in conn.execute(
                    f'SELECT tvk, "order", sort_code FROM taxa WHERE tvk IN ({ph})', batch):
                out[t] = compute_taxonomic_sort_key(order or "", code)
    finally:
        conn.close()
    return out


def in_taxonomic_order(items, tvk=lambda x: x.tvk, name=lambda x: x.name):
    """items sorted taxonomically; anything without a key last, alphabetically."""
    items = list(items)
    keys = taxonomic_sort_keys([tvk(x) for x in items])
    return sorted(items, key=lambda x: (keys.get(tvk(x), UNSORTED), (name(x) or "").lower()))


def _build_species_list(species_rows, mode):
    """(species_list, biotope_counts, habitat_counts, tvks) from grouped rows."""
    tvk_map = {r[1]: (r[0], r[2]) for r in species_rows if r[1]}
    tvks = list(tvk_map)
    enrichment = _load_status_data(tvks, mode)
    ecology = _load_pantheon_ecology(tvks)
    taxonomy = load_taxonomy(tvks)

    species_list, biotope_counts, habitat_counts = [], {}, {}
    for tvk in tvks:
        name, count = tvk_map[tvk]
        cd = enrichment.get(tvk, {})
        pd = ecology.get(tvk, {})
        tx = taxonomy.get(tvk, {})
        species_list.append(SiteSpecies(
            name=name, tvk=tvk, count=count, sqs=cd.get("sqs", 0),
            status=cd.get("short_status", ""), status_full=cd.get("display_status", ""),
            tier=cd.get("tier", ""),
            broad_biotope=pd.get("biotope", ""), habitat=pd.get("habitat", ""),
            order_name=tx.get("order", ""), family=tx.get("family", ""),
            common_name=tx.get("common", "")))
        for b in pd.get("biotopes", []):
            biotope_counts[b] = biotope_counts.get(b, 0) + 1
        for h in pd.get("habitats", []):
            habitat_counts[h] = habitat_counts.get(h, 0) + 1

    species_list.sort(key=lambda s: (-s.sqs if s.tier else 0, s.name))
    # Species with no TVK cannot be analysed; they are listed last so the
    # exclusion is visible rather than silent.
    for r in species_rows:
        if not r[1]:
            species_list.append(SiteSpecies(name=r[0], tvk="", count=r[2]))
    return species_list, biotope_counts, habitat_counts, tvks


def _accumulation(conn, where, params):
    """Species-accumulation curve by date."""
    seen, by_date = set(), {}
    for date, sp in conn.execute(
            f"""SELECT date, species_name FROM assessment_records
                WHERE {where} AND date IS NOT NULL AND species_name IS NOT NULL
                ORDER BY date""", params):
        seen.add(sp)
        by_date[date] = len(seen)
    dates = sorted(by_date)
    return dates, [(d, by_date[d]) for d in dates]


# ============================================================
# Sites
# ============================================================

def load_all_sites(mode=AnalysisMode.CODEX_FULL, date_from=None, date_to=None,
                   survey_year=None):
    if not DB_PATH.exists():
        return []
    conn = _connect()
    try:
        if not _has_record_type(conn):
            return []
        sc, sp = _scope(date_from, date_to, survey_year)
        rows = conn.execute(f"""
            SELECT site_name, project_name, client,
                   COUNT(*), COUNT(DISTINCT species_name),
                   COUNT(DISTINCT date), MIN(date), MAX(date)
            FROM assessment_records
            WHERE record_type = 'Commercial'
              AND site_name IS NOT NULL AND site_name != ''{sc}
            GROUP BY site_name, project_name ORDER BY site_name""", sp).fetchall()
    finally:
        conn.close()

    sites = [SiteRecord(
        site_name=r[0], project_name=r[1] or "", client=r[2] or "",
        record_count=r[3], species_count=r[4], visit_count=r[5],
        first_date=r[6] or "", last_date=r[7] or "", mode=mode.value,
        survey_year=str(survey_year or POOLED)) for r in rows]
    _enrich_sites(sites, mode, date_from, date_to, survey_year)
    return sites


def load_site_detail(site_name, project_name="", mode=AnalysisMode.CODEX_FULL,
                     date_from=None, date_to=None, survey_year=None):
    if not DB_PATH.exists():
        return None
    sc, sp = _scope(date_from, date_to, survey_year)
    where = "record_type = 'Commercial' AND site_name = ?"
    params = [site_name]
    if project_name:
        where += " AND project_name = ?"
        params.append(project_name)
    where += sc
    params += sp

    conn = _connect()
    try:
        row = conn.execute(
            f"""SELECT site_name, project_name, client,
                       COUNT(*), COUNT(DISTINCT species_name),
                       COUNT(DISTINCT date), MIN(date), MAX(date)
                FROM assessment_records WHERE {where}""", params).fetchone()
        if not row or not row[0]:
            return None
        site = SiteRecord(
            site_name=row[0], project_name=row[1] or "", client=row[2] or "",
            record_count=row[3], species_count=row[4], visit_count=row[5],
            first_date=row[6] or "", last_date=row[7] or "", mode=mode.value,
            survey_year=str(survey_year or POOLED))

        species_rows = conn.execute(
            f"""SELECT species_name, species_tvk, COUNT(*) FROM assessment_records
                WHERE {where} AND species_name IS NOT NULL
                GROUP BY species_name, species_tvk ORDER BY species_name""",
            params).fetchall()
        site.visit_dates, site.accumulation = _accumulation(conn, where, params)
    finally:
        conn.close()

    species_list, bio, hab, tvks = _build_species_list(species_rows, mode)
    detail = SiteDetail(site=site, species_list=species_list,
                        biotope_counts=bio, habitat_counts=hab)
    _apply_metrics(site, tvks, species_list, mode)
    return detail


def _enrich_sites(sites, mode, date_from=None, date_to=None, survey_year=None):
    sc, sp = _scope(date_from, date_to, survey_year)
    conn = _connect()
    try:
        for site in sites:
            where = "record_type = 'Commercial' AND site_name = ?"
            params = [site.site_name]
            if site.project_name:
                where += " AND project_name = ?"
                params.append(site.project_name)
            tvks = [r[0] for r in conn.execute(
                f"""SELECT DISTINCT species_tvk FROM assessment_records WHERE {where}{sc}
                    AND species_tvk IS NOT NULL AND species_tvk != ''""",
                params + sp)]
            if not tvks:
                continue
            enrichment = _load_status_data(tvks, mode)
            stub = [SiteSpecies(name="", tvk=t,
                                tier=enrichment.get(t, {}).get("tier", ""))
                    for t in tvks]
            _apply_metrics(site, tvks, stub, mode)
    finally:
        conn.close()


# ============================================================
# Projects
# ============================================================

def load_all_projects(mode=AnalysisMode.CODEX_FULL, date_from=None, date_to=None,
                      by_year=True):
    """Commercial projects, one row per survey year by default.

    by_year=True   one row per project per year -- a survey, which is what a
                   report covers
    by_year=False  one row per project, all years pooled

    A project may span several surveys: Bicester Graven Hill holds 2023 and 2025
    under one name, and pooling them produces a species list that corresponds to
    no report.
    """
    if not DB_PATH.exists():
        return []
    conn = _connect()
    try:
        if not _has_record_type(conn):
            return []
        sc, sp = _scope(date_from, date_to)
        year_sel = "substr(date,1,4)" if by_year else "''"
        year_grp = ", substr(date,1,4)" if by_year else ""
        rows = conn.execute(f"""
            SELECT project_name, client, {year_sel},
                   COUNT(DISTINCT site_name), COUNT(*),
                   COUNT(DISTINCT species_name), COUNT(DISTINCT date),
                   MIN(date), MAX(date),
                   GROUP_CONCAT(DISTINCT site_name)
            FROM assessment_records
            WHERE record_type = 'Commercial'
              AND project_name IS NOT NULL AND project_name != ''{sc}
            GROUP BY project_name, client{year_grp}
            ORDER BY project_name, 3 DESC""", sp).fetchall()
    finally:
        conn.close()

    projects = [ProjectRecord(
        project_name=r[0], client=r[1] or "", survey_year=r[2] or POOLED,
        site_count=r[3], record_count=r[4], species_count=r[5],
        visit_count=r[6], first_date=r[7] or "", last_date=r[8] or "",
        site_names=sorted(set(r[9].split(",") if r[9] else [])),
        mode=mode.value) for r in rows]
    _enrich_projects(projects, mode, date_from, date_to)
    return projects


def load_project_detail(project_name, client="", mode=AnalysisMode.CODEX_FULL,
                        date_from=None, date_to=None, survey_year=None):
    """All species across all sites in a project, scoped to a survey year."""
    if not DB_PATH.exists():
        return None
    sc, sp = _scope(date_from, date_to, survey_year)
    where = "record_type = 'Commercial' AND project_name = ?"
    params = [project_name]
    if client:
        where += " AND client = ?"
        params.append(client)
    where += sc
    params += sp

    conn = _connect()
    try:
        row = conn.execute(
            f"""SELECT project_name, client, COUNT(*),
                       COUNT(DISTINCT species_name), COUNT(DISTINCT date),
                       MIN(date), MAX(date), COUNT(DISTINCT site_name)
                FROM assessment_records WHERE {where}""", params).fetchone()
        if not row or not row[0]:
            return None
        # SiteRecord doubles as the project summary -- the views expect it.
        site = SiteRecord(
            site_name=row[0], project_name=row[0], client=row[1] or "",
            record_count=row[2], species_count=row[3], visit_count=row[4],
            first_date=row[5] or "", last_date=row[6] or "", mode=mode.value,
            survey_year=str(survey_year or POOLED))

        species_rows = conn.execute(
            f"""SELECT species_name, species_tvk, COUNT(*) FROM assessment_records
                WHERE {where} AND species_name IS NOT NULL
                GROUP BY species_name, species_tvk ORDER BY species_name""",
            params).fetchall()
        site.visit_dates, site.accumulation = _accumulation(conn, where, params)
    finally:
        conn.close()

    species_list, bio, hab, tvks = _build_species_list(species_rows, mode)
    detail = SiteDetail(site=site, species_list=species_list,
                        biotope_counts=bio, habitat_counts=hab)
    _apply_metrics(site, tvks, species_list, mode)
    return detail


def _enrich_projects(projects, mode, date_from=None, date_to=None):
    conn = _connect()
    try:
        for proj in projects:
            # Each row carries its own survey year, so scope per row.
            sc, sp = _scope(date_from, date_to, proj.survey_year or None)
            where = "record_type = 'Commercial' AND project_name = ?"
            params = [proj.project_name]
            if proj.client:
                where += " AND client = ?"
                params.append(proj.client)
            tvks = [r[0] for r in conn.execute(
                f"""SELECT DISTINCT species_tvk FROM assessment_records WHERE {where}{sc}
                    AND species_tvk IS NOT NULL AND species_tvk != ''""",
                params + sp)]
            if not tvks:
                continue
            enrichment = _load_status_data(tvks, mode)
            stub = [SiteSpecies(name="", tvk=t,
                                tier=enrichment.get(t, {}).get("tier", ""))
                    for t in tvks]
            _apply_metrics(proj, tvks, stub, mode)
    finally:
        conn.close()
