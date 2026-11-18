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
    preview_job: str = ""       # Data Entry job name when this is an uncommitted preview, else ""
    preview_held_back: int = 0  # staged rows commit would leave in staging (not in the preview)
    preview_years: str = ""     # "2023 (most common of 2023, 2024)" when the job spans years


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
    # A preview of an uncommitted Data Entry job: its staged rows (entry_row tuples), so the
    # exports read the job and not the committed records. None for a committed project.
    preview_rows: object = None


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
    return _commonest_country(rows)


def _commonest_country(vc_counts):
    """Commonest country from [(vice-county number, records)], or ''."""
    tally = {}
    for vc, n in vc_counts:
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
    return _jurisdiction_from_derived(derived)


def _jurisdiction_from_derived(derived):
    """(jurisdiction, how) from the country derived from vice-counties ('' if none)."""
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


def short_status_for(st, jurisdiction):
    """Codex's short label for a species-list row, for this jurisdiction.

    Codex returns a bare "Priority" for any priority listing, so a species on
    the Scottish Biodiversity List alone read as a priority species on an
    England site (Speckled Bush-cricket, Nottingham 17 Nov 2026). Only listings
    that apply here are shown, by name (e.g. "S41").
    """
    s = (getattr(st, "short_status", "") or "") if st else ""
    if s != "Priority":
        return s
    from shared.repositories.codex_repository import _priority_applies, _priority_label
    for e in getattr(st, "priority", None) or []:
        v = getattr(e, "value", "") or ""
        if _priority_applies(v, jurisdiction):
            return _priority_label(v)
    return ""


def analysis_service():
    """A PantheonAnalysisService on fresh repositories -- what the detail view uses."""
    from shared.services.pantheon_analysis_service import PantheonAnalysisService
    return PantheonAnalysisService(PantheonRepository(), CodexRepository())


# Codex / Pantheon read failures since the screen last asked (EXA19). A row
# whose analysis failed shows no figures; the screen reads this list and says
# why, rather than letting a blank pass for a real result.
_read_errors = []


def take_read_errors():
    """The distinct analysis / read failures recorded since the last call, and clear them."""
    errors = list(dict.fromkeys(_read_errors))
    _read_errors.clear()
    return errors


def _analyse(tvks, mode, jurisdiction, names=None, service=None):
    """The analysis the detail view shows, or None if it cannot be run."""
    try:
        svc = service or analysis_service()
        return svc.analyse(list(tvks), names or {}, mode, jurisdiction)
    except Exception as e:  # noqa: BLE001 -- degrade to unenriched, but say so
        print(f"[examen_data] analysis failed: {e}")
        _read_errors.append(f"{type(e).__name__}: {e}")
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
            status=short_status_for(st, jurisdiction),
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
    return _accumulate(conn.execute(
        f"""SELECT date, species_name FROM assessment_records
            WHERE {where} AND date IS NOT NULL AND species_name IS NOT NULL
            ORDER BY date""", params))


def _accumulate(date_species_pairs):
    """(dates, [(date, species seen so far)]) from (date, species) pairs in date order."""
    seen, by_date = set(), {}
    for date, sp in date_species_pairs:
        seen.add(sp)
        by_date[date] = len(seen)
    dates = sorted(by_date)
    return dates, [(d, by_date[d]) for d in dates]


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


def survey_records_where(project_name, client="", date_from=None, date_to=None, survey_year=None):
    """(WHERE, params) on assessment_records for one committed survey's records: the
    Commercial project, the client when one is given, and the survey year / dates. The one
    selection load_project_detail and the preview of a Data Entry job (which adds the job's
    staged rows to these) both use."""
    sc, sp = _scope(date_from, date_to, survey_year)
    where = "record_type = 'Commercial' AND project_name = ?"
    params = [project_name]
    if client:
        where += " AND client = ?"
        params.append(client)
    return where + sc, params + sp


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
    where, params = survey_records_where(project_name, client, date_from, date_to, survey_year)

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
    return _assemble_detail(site, species_rows, mode, jurisdiction)


def _assemble_detail(site, species_rows, mode, jurisdiction):
    """The SiteDetail for a summary record and its (name, tvk, count) rows -- one path for a
    committed project and a Data Entry preview, so their figures follow the same rules."""
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


# ============================================================
# Preview of an uncommitted Data Entry job (read-only)
# ============================================================
# Data Entry keeps a job's records in entry_staging until they are committed. The preview reads
# them without writing anything and runs them through the same _assemble_detail as a committed
# project. A staged row with no species name is ignored. As for committed records, a species
# that is not an invertebrate (a plant entered by mistake) stays in the list and the species
# count -- the analysis gives it no status or SQS and never makes it Key.

# Column order of a row as the preview carries it (SiteDetail.preview_rows): the job's eligible
# staged rows and the survey's records already in Observatum. The last column names the
# contributor of a contributed record ('' for the rest).
ENTRY_ROW_COLUMNS = ("species_name", "species_tvk", "date", "site_name", "sub_location",
                     "quantity", "vc_number", "grid_ref", "method", "determiner", "visit_number",
                     "contributor")


def preview_note(job_name, held_back=0, years=""):
    """The wording of the preview line in the workbook's basis block (and so the report pack)."""
    note = (f"Preview of the uncommitted Data Entry job '{job_name}': "
            "figures may change when the job is committed.")
    if years:
        note += f" Survey year {years}."
    if held_back:
        note += (f" {held_back} row{'s' if held_back != 1 else ''} held back (To check, undated "
                 "or unreadable) are not included.")
    return note


def _connect_ro():
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)


def _job_rows(conn, job_id, with_taxonomy=True):
    """(job dict, rows, held_back): the rows Data Entry's commit would write for the job, as
    ENTRY_ROW_COLUMNS tuples, written as commit writes them (commit_service.row_kwargs: a UKSI
    synonym under its recommended name and TVK, dates normalised, No. read). held_back counts
    the staged records commit would leave in staging; a row with no species name (an empty grid
    row) is not a record and is not counted. (None, [], 0) when the job is not there."""
    from DataEntry import commit_service as cs
    from DataEntry import staging_repo
    conn.row_factory = sqlite3.Row
    job = conn.execute("SELECT * FROM entry_jobs WHERE id = ?", (job_id,)).fetchone()
    if job is None:
        return None, [], 0
    job = dict(job)
    staged = staging_repo.fetch_rows(conn, job_id)
    reasons = [cs._eligibility(r) for r in staged]
    eligible = [r for r, why in zip(staged, reasons) if why is None]
    held_back = sum(1 for why in reasons if why not in (None, "no_species"))
    taxonomy = {}
    if with_taxonomy and eligible:
        try:
            taxonomy = cs.taxonomy_with_synonyms(eligible)
        except Exception:  # noqa: BLE001 -- as commit does: carry on without taxonomy
            taxonomy = {}
    rows = []
    for r in eligible:
        kw = cs.row_kwargs(r, job, None, taxonomy)[0]
        rows.append((kw["species_name"], kw.get("species_tvk"), kw.get("date"), kw.get("site_name"),
                     r.get("sub_location") or None, kw.get("quantity"), kw.get("vc_number"),
                     kw.get("grid_ref"), kw.get("method"), kw.get("determiner"),
                     r.get("visit_number") or None, ""))
    return job, rows, held_back


def _job_year(rows):
    """(survey year, note): the year of the rows' dates, the most common when there are several
    (the later on a tie); note is '' for one year, else says which was taken."""
    counts = {}
    for r in rows:
        if r[2]:
            counts[r[2][:4]] = counts.get(r[2][:4], 0) + 1
    if not counts:
        return "", ""
    year = max(counts, key=lambda y: (counts[y], y))
    if len(counts) == 1:
        return year, ""
    return year, (f"{year}, the most common of {', '.join(sorted(counts))}; the job's rows dated "
                  "in other years belong to other surveys and are not included")


def _survey_rows(project, client, year):
    """The survey's records already in Observatum (assessment_records: committed observations
    and contributed records), as ENTRY_ROW_COLUMNS tuples -- the selection of a committed
    project's detail. [] when observatum.db cannot be read."""
    if not project or not year:
        return []
    where, params = survey_records_where(project, client, survey_year=year)
    try:
        conn = _connect()
        try:
            return [(n, t, (d or "").strip() or None, s, sub, q, vc, g, m, det, vis,
                     (c or "unnamed contributor") if o == "contributed" else "")
                    for n, t, d, s, sub, q, vc, g, m, det, vis, o, c in conn.execute(
                        f"""SELECT species_name, species_tvk, date, site_name, sub_location,
                                   quantity, vc_number, grid_ref, method, determiner,
                                   visit_number, origin, contributor
                            FROM assessment_records
                            WHERE {where} AND species_name IS NOT NULL
                            ORDER BY date, id""", params)]
        finally:
            conn.close()
    except sqlite3.Error:
        return []


def list_entry_jobs():
    """Active Data Entry jobs with at least one row commit would write, for the preview picker:
    [{'id', 'name', 'project', 'client', 'rows', 'species', 'first_date', 'last_date',
    'held_back'}]. rows counts only those eligible rows; held_back the rows commit would leave
    in staging."""
    if not DB_PATH.exists():
        return []
    try:
        conn = _connect_ro()
        try:
            ids = [r[0] for r in conn.execute(
                "SELECT id FROM entry_jobs WHERE status = 'active' "
                "ORDER BY name COLLATE NOCASE, id").fetchall()]
            out = []
            for jid in ids:
                job, rows, held = _job_rows(conn, jid, with_taxonomy=False)
                if not rows:
                    continue
                dates = [r[2] for r in rows if r[2]]
                out.append({"id": jid, "name": job.get("name") or "",
                            "project": job.get("project") or "", "client": job.get("client") or "",
                            "rows": len(rows), "species": len({r[0] for r in rows}),
                            "first_date": min(dates) if dates else "",
                            "last_date": max(dates) if dates else "", "held_back": held})
        finally:
            conn.close()
    except sqlite3.Error:
        return []
    return out


def resolve_entry_jurisdiction(rows, chosen=AUTO_JURISDICTION):
    """(jurisdiction, how) for a preview -- resolve_jurisdiction's rule on the rows' VCs."""
    if chosen and chosen != AUTO_JURISDICTION:
        return chosen, "chosen"
    counts = {}
    for r in rows:
        if r[6] not in (None, ""):
            counts[r[6]] = counts.get(r[6], 0) + 1
    return _jurisdiction_from_derived(_commonest_country(counts.items()))


def load_entry_job_detail(job_id, mode=AnalysisMode.CODEX_FULL, jurisdiction=None):
    """The SiteDetail load_project_detail gives for the survey as it will be once this job is
    committed: the job's rows commit would write plus the records already in Observatum for the
    same project, client and survey year (the year of the job's dates; the most common when
    there are several). Nothing is written.

    Project and client are the job's as typed, as commit writes them (the job's name when it has
    no project). Returns None if the job is not there or has no row to commit. site.preview_job
    names the job; preview_held_back counts the rows left out; preview_rows carries the rows.
    """
    if not DB_PATH.exists():
        return None
    try:
        conn = _connect_ro()
        try:
            job, staged, held_back = _job_rows(conn, job_id)
        finally:
            conn.close()
    except sqlite3.Error:
        return None
    if not job or not staged:
        return None
    name = job.get("name") or ""
    project = job.get("project") or name
    client = job.get("client") or ""
    year, years_note = _job_year(staged)
    staged = [r for r in staged if r[2] and r[2][:4] == year]
    rows = _survey_rows(project, client, year) + staged
    if not jurisdiction or jurisdiction == AUTO_JURISDICTION:
        jurisdiction, _how = resolve_entry_jurisdiction(rows)
    dates = [r[2] for r in rows if r[2]]
    site = SiteRecord(
        site_name=project, project_name=project, client=client,
        record_count=len(rows), species_count=len({r[0] for r in rows}),
        visit_count=len(set(dates)), first_date=min(dates) if dates else "",
        last_date=max(dates) if dates else "", mode=mode.value,
        survey_year=year or POOLED, preview_job=name, preview_held_back=held_back,
        preview_years=years_note)
    site.visit_dates, site.accumulation = _accumulate(
        sorted(((r[2], r[0]) for r in rows if r[2]), key=lambda x: x[0]))
    counts = {}
    for r in rows:
        counts[(r[0], r[1])] = counts.get((r[0], r[1]), 0) + 1
    species_rows = [(n, t, c) for (n, t), c in sorted(counts.items(), key=lambda x: (x[0][0], x[0][1] or ""))]
    detail = _assemble_detail(site, species_rows, mode, jurisdiction)
    detail.preview_rows = rows
    return detail
