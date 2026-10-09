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

v6 changes (fix round, 9 Oct 2026)
----------------------------------
  - The project table, the species list and the detail all read ONE
    PantheonAnalysisService.analyse result. The table had its own path
    (compute_sqi dividing by scoring species, Key species always under England,
    two TVKs of one species counted twice): Glory Park 120 against the report's
    117 (EXA1, EXA2, EXA14).
  - Jurisdiction (auto from vice-county, or chosen) is resolved here, for the
    table and the detail header alike: resolve_jurisdiction.
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
    note: str = ""                 # "recorded as s.l. and s.s." (EXA14)
    status_note: str = ""          # "status held at sensu lato" (not its own)


@dataclass
class SiteDetail:
    site: SiteRecord
    species_list: list = field(default_factory=list)
    biotope_counts: dict = field(default_factory=dict)
    habitat_counts: dict = field(default_factory=dict)
    sat_counts: dict = field(default_factory=dict)
    # Compartment analysis (backlog E6): computed once by Examen.compartments.for_detail
    # and read from here by the Overview and the workbook.
    compartments: object = None
    # The AnalysisResult the list was built from, and its jurisdiction.
    analysis: object = None
    jurisdiction: str = ""
    # Every TVK recorded, before a species' s.l. TVK was folded into it (EXA14).
    # Analyse THESE, not the species list's TVKs, to reproduce `analysis`.
    recorded_tvks: list = field(default_factory=list)


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
    jurisdiction: str = ""         # what the row's Key species were classified under

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
# Jurisdiction -- one rule for the project table and the detail (EXA2)
# ============================================================

AUTO_JURISDICTION = "Auto (vice-county)"
DEFAULT_JURISDICTION = "England"

# Watsonian vice-counties. VC is already on every record and derived from the
# grid reference, so the country can be read from the data rather than chosen
# from a menu that can be forgotten.
_VC_COUNTRY = ([("England", range(1, 35))] +
               [("Wales", [35])] +
               [("England", range(36, 41))] +
               [("Wales", range(41, 53))] +
               [("England", range(53, 71))] +
               [("Isle of Man", [71])] +
               [("Scotland", range(72, 113))])


def country_for_vc(vc):
    for country, rng in _VC_COUNTRY:
        if vc in rng:
            return country
    return ""


def derive_jurisdiction(project_name, client="", survey_year=None, date_from=None,
                        date_to=None):
    """Commonest country across the project's records, or '' if unknown."""
    if not project_name or not DB_PATH.exists():
        return ""
    where = "record_type='Commercial' AND project_name=?"
    params = [project_name]
    if client:
        where += " AND client=?"
        params.append(client)
    sc, sp = _scope(date_from, date_to, survey_year)
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        try:
            rows = conn.execute(
                f"""SELECT vc_number, COUNT(1) FROM assessment_records
                    WHERE {where}{sc} AND vc_number IS NOT NULL AND vc_number != ''
                    GROUP BY 1 ORDER BY 2 DESC""", params + sp).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return ""
    tally = {}
    for vc, n in rows:
        try:
            country = country_for_vc(int(vc))
        except (TypeError, ValueError):
            continue
        if country:
            tally[country] = tally.get(country, 0) + n
    if not tally:
        return ""
    return max(tally, key=tally.get)


def resolve_jurisdiction(project, chosen=AUTO_JURISDICTION):
    """(jurisdiction, how) -- the choice if one was made, else from the VCs.

    project: anything with project_name / client / survey_year, or None (an
    imported list: no records, so no vice-county). The project table and the
    detail header both come here, so they cannot classify Key species under
    different rules (EXA2).
    """
    if chosen and chosen != AUTO_JURISDICTION:
        return chosen, "chosen"
    derived = ""
    if project is not None:
        derived = derive_jurisdiction(getattr(project, "project_name", ""),
                                      getattr(project, "client", ""),
                                      getattr(project, "survey_year", "") or None)
    if derived in ("", "Isle of Man"):
        # No usable vice-county, or a jurisdiction with no separate priority
        # list. England is the documented default; say so rather than assert a
        # country the records do not support.
        return DEFAULT_JURISDICTION, ("default" if not derived else f"default, VC in {derived}")
    return derived, "from vice-county"


# ============================================================
# Analysis -- one path for the table, the detail and the exports
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
    note = getattr(st, "status_note", "") or ""
    head = [p for p in parts if p != note]
    return ", ".join(head + [f"Legal: {n}" for n in names if n] + ([note] if note else []))


def analysis_service():
    """A PantheonAnalysisService on fresh repositories -- what the detail view uses."""
    from shared.services.pantheon_analysis_service import PantheonAnalysisService
    return PantheonAnalysisService(PantheonRepository(), CodexRepository())


def _analyse(tvks, mode, jurisdiction, names=None, service=None):
    """The analysis the detail view shows, or None if it cannot be run."""
    try:
        svc = service or analysis_service()
        return svc.analyse(list(tvks), names or {}, mode, jurisdiction)
    except Exception as e:  # noqa: BLE001 -- degrade to unenriched, but say so
        print(f"[examen_data] analysis failed: {e}")
        return None


def _apply_metrics(record, result):
    """Fill species, SQI and key-species figures on a SiteRecord / ProjectRecord
    from an AnalysisResult -- the same object the Overview reads, so the table
    and the detail cannot disagree (EXA1, EXA2, EXA14)."""
    if result is None:
        return
    o = result.overall_sqi
    if o is not None:
        record.sqi = o.sqi
        record.sqi_reliable = o.reliable
        record.species_with_sqs = o.species_with_sqs
    # Species: one per TVK, a species recorded as s.l. and s.s. once -- the
    # Overview's count.
    record.species_count = result.total_species
    record.key_species_count = result.key_species_count
    record.rare_count = result.rare_count
    record.scarce_count = result.scarce_count
    record.priority_count = result.priority_count
    # Denominator is total species recorded, matching Wil's reports:
    # "34 ... equates to 7.8% of the species from the survey" = 34/433.
    record.key_species_pct = result.key_species_pct


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


def _build_species_list(species_rows, mode, jurisdiction=DEFAULT_JURISDICTION,
                        service=None):
    """(species_list, biotope_counts, habitat_counts, recorded_tvks, result).

    recorded_tvks is every TVK recorded, before the merge below -- what to pass
    to PantheonAnalysisService.analyse to reproduce `result`.

    Every figure on a row comes from the analysis result, so the list, the
    Overview and the exports agree. A species recorded under its own TVK and
    its s.l. / aggregate counterpart is one row (the species TVK), its records
    summed, noted "recorded as s.l. and s.s." (EXA14).
    """
    try:
        from shared.services.pantheon_analysis_service import RECORDED_SL_SS
    except ImportError:  # pragma: no cover
        RECORDED_SL_SS = "recorded as s.l. and s.s."
    tvk_map = {}
    for name, tvk, count in species_rows:
        if not tvk:
            continue
        if tvk in tvk_map:              # one TVK under two names: one species
            tvk_map[tvk] = (tvk_map[tvk][0], tvk_map[tvk][1] + count)
        else:
            tvk_map[tvk] = (name, count)
    all_tvks = list(tvk_map)
    names = {t: v[0] for t, v in tvk_map.items()}
    result = _analyse(all_tvks, mode, jurisdiction, names, service)
    merged = dict(getattr(result, "merged_tvks", {}) or {}) if result else {}
    folded = {}
    for broad, sp in merged.items():
        folded[sp] = folded.get(sp, 0) + tvk_map[broad][1]
    tvks = [t for t in all_tvks if t not in merged]
    taxonomy = load_taxonomy(tvks)

    statuses = getattr(result, "statuses", {}) if result else {}
    sqs = getattr(result, "sqs_by_tvk", {}) if result else {}
    bios = getattr(result, "biotopes_by_tvk", {}) if result else {}
    habs = getattr(result, "habitats_by_tvk", {}) if result else {}

    species_list, biotope_counts, habitat_counts = [], {}, {}
    for tvk in tvks:
        name, count = tvk_map[tvk]
        st = statuses.get(tvk)
        tier = getattr(st, "tier", None) if st else None
        tier_s = str(getattr(tier, "value", tier or "")).strip()
        b, h = bios.get(tvk, []), habs.get(tvk, [])
        tx = taxonomy.get(tvk, {})
        species_list.append(SiteSpecies(
            name=name, tvk=tvk, count=count + folded.get(tvk, 0), sqs=sqs.get(tvk, 0) or 0,
            status=(getattr(st, "short_status", "") or "") if st else "",
            status_full=_full_status(st),
            tier="" if tier_s.lower() in ("none", "") else tier_s,
            broad_biotope=", ".join(b[:2]), habitat=", ".join(h[:2]),
            order_name=tx.get("order", ""), family=tx.get("family", ""),
            common_name=tx.get("common", ""),
            note=RECORDED_SL_SS if tvk in folded else "",
            status_note=(getattr(st, "status_note", "") or "") if st else ""))
        for x in b:
            biotope_counts[x] = biotope_counts.get(x, 0) + 1
        for x in h:
            habitat_counts[x] = habitat_counts.get(x, 0) + 1

    species_list.sort(key=lambda s: (-s.sqs if s.tier else 0, s.name))
    # Species with no TVK cannot be analysed; they are listed last so the
    # exclusion is visible rather than silent.
    for r in species_rows:
        if not r[1]:
            species_list.append(SiteSpecies(name=r[0], tvk="", count=r[2]))
    return species_list, biotope_counts, habitat_counts, all_tvks, result


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
                   survey_year=None, jurisdiction=DEFAULT_JURISDICTION):
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
    _enrich_sites(sites, mode, date_from, date_to, survey_year, jurisdiction)
    return sites


def load_site_detail(site_name, project_name="", mode=AnalysisMode.CODEX_FULL,
                     date_from=None, date_to=None, survey_year=None,
                     jurisdiction=DEFAULT_JURISDICTION):
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

    species_list, bio, hab, tvks, result = _build_species_list(species_rows, mode, jurisdiction)
    detail = SiteDetail(site=site, species_list=species_list,
                        biotope_counts=bio, habitat_counts=hab,
                        analysis=result, jurisdiction=jurisdiction, recorded_tvks=tvks)
    _apply_metrics(site, result)
    return detail


def _enrich_sites(sites, mode, date_from=None, date_to=None, survey_year=None,
                  jurisdiction=DEFAULT_JURISDICTION):
    sc, sp = _scope(date_from, date_to, survey_year)
    service = analysis_service()
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
            if tvks:
                _apply_metrics(site, _analyse(tvks, mode, jurisdiction, service=service))
    finally:
        conn.close()


# ============================================================
# Projects
# ============================================================

def load_all_projects(mode=AnalysisMode.CODEX_FULL, date_from=None, date_to=None,
                      by_year=True, jurisdiction=AUTO_JURISDICTION):
    """Commercial projects, one row per survey year by default.

    by_year=True   one row per project per year -- a survey, which is what a
                   report covers
    by_year=False  one row per project, all years pooled
    jurisdiction   AUTO_JURISDICTION (from each project's vice-counties) or a
                   country -- resolved per row exactly as the detail header does

    A project may span several surveys: Bicester Graven Hill holds 2023 and 2025
    under one name, and pooling them produces a species list that corresponds to
    no report.

    Each row's figures come from the same analysis the detail view runs
    (PantheonAnalysisService.analyse), so the table, the Overview and the
    exports show one SQI, one key-species count and one species count.
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
    _enrich_projects(projects, mode, date_from, date_to, jurisdiction)
    return projects


def load_project_detail(project_name, client="", mode=AnalysisMode.CODEX_FULL,
                        date_from=None, date_to=None, survey_year=None,
                        jurisdiction=None):
    """All species across all sites in a project, scoped to a survey year.

    jurisdiction: a country, or None / AUTO_JURISDICTION to read it from the
    records' vice-counties (resolve_jurisdiction).
    """
    if not DB_PATH.exists():
        return None
    if not jurisdiction or jurisdiction == AUTO_JURISDICTION:
        from types import SimpleNamespace
        jurisdiction, _how = resolve_jurisdiction(SimpleNamespace(
            project_name=project_name, client=client, survey_year=survey_year or ""))
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

    species_list, bio, hab, tvks, result = _build_species_list(species_rows, mode, jurisdiction)
    detail = SiteDetail(site=site, species_list=species_list,
                        biotope_counts=bio, habitat_counts=hab,
                        analysis=result, jurisdiction=jurisdiction, recorded_tvks=tvks)
    _apply_metrics(site, result)
    return detail


def _enrich_projects(projects, mode, date_from=None, date_to=None,
                     jurisdiction=AUTO_JURISDICTION):
    service = analysis_service()
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
            proj.jurisdiction, _how = resolve_jurisdiction(proj, jurisdiction)
            if not tvks:
                continue
            _apply_metrics(proj, _analyse(tvks, mode, proj.jurisdiction, service=service))
    finally:
        conn.close()
