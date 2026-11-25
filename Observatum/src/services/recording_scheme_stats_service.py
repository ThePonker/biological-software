"""
Recording Scheme Stats Service.

Centralized statistics for recording scheme data.
Single source of truth for all scheme-related stats.

PERFORMANCE OPTIMIZATIONS:
- TTL cache (30 seconds) prevents redundant refreshes
- Combined queries reduce database round trips
"""

from typing import Dict, Any, Optional
from datetime import datetime
from shared.species_counting import counted_clause, species_key_expr
from shared.stats_refresh import refresh_failed, refresh_ok


CACHE_TTL_SECONDS = 300

# Month charts place only records dated to a day: year-only, month-only and range dates
# (date_type Y/YY, O/OO, DD) are left out rather than counted in their first month --
# 34 / 62 / 81 scheme records on 10 Oct (decision D3, 11 Oct 2026; the observation month
# charts do the same since decision 9).
DAY_ONLY = "AND COALESCE(date_type, 'D') = 'D'"


def scheme_families() -> list:
    """The family scope from settings (Settings > Recording Scheme families), as a list."""
    from PySide6.QtCore import QSettings
    fam_str = QSettings().value("scheme/families", "", str).strip()
    return [f.strip() for f in fam_str.split(',') if f.strip()] if fam_str else []


def scheme_scope(db, prefix: str = "") -> str:
    """The scheme scope every figure uses, as SQL with `?` marks for the family names (their
    values are scheme_families(), passed as parameters): the family scope from settings, and
    the marked NBN copies of iRecord records left out (shared/scheme_duplicates.py, Q59)."""
    from shared.scheme_duplicates import live_sql
    copies = live_sql(db, prefix) if db else ""
    families = scheme_families()
    if not families:
        return copies
    col = f"{prefix}family" if prefix else "family"
    return f" AND {col} IN ({','.join('?' * len(families))})" + copies


def scheme_totals(db) -> Dict[str, int]:
    """Counted Recording Scheme species and records: the dashboard's figures, and Home's.
    Species are counted as the observation statistics count them (subspecies rolled up to
    their species by TVK); the counting switches and the family scope apply."""
    sk = species_key_expr("recording_scheme", "", db)
    rows = db.execute_main(f"""
        SELECT COUNT(*) as total_records,
               COUNT(DISTINCT CASE WHEN species_tvk IS NOT NULL THEN {sk} END) as total_species
        FROM recording_scheme
        WHERE species_name IS NOT NULL AND species_name != ''
        {counted_clause("recording_scheme", "", db)}{scheme_scope(db)}
    """, tuple(scheme_families()))
    return {'total_records': rows[0]['total_records'] or 0 if rows else 0,
            'total_species': rows[0]['total_species'] or 0 if rows else 0}


class RecordingSchemeStatsService:
    """
    Singleton service providing cached statistics for recording scheme data.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._db = None
            cls._instance._cache = {}
            cls._instance._valid = False
            cls._instance.last_error = None
            cls._instance._last_refresh = None
        return cls._instance

    def initialize(self, db_manager):
        """Initialize with database manager."""
        self._db = db_manager

    def get(self, key: str, default: Any = None) -> Any:
        """Get a stat value, refreshing cache if needed."""
        if self._needs_refresh():
            self._refresh()
        return self._cache.get(key, default if default is not None else 0)

    def get_all(self) -> Dict[str, Any]:
        """Get all cached stats."""
        if self._needs_refresh():
            self._refresh()
        return self._cache.copy()

    def _needs_refresh(self) -> bool:
        """Check if cache needs refresh based on validity and TTL."""
        if not self._valid:
            return True
        if self._last_refresh is None:
            return True
        elapsed = datetime.now() - self._last_refresh
        return elapsed.total_seconds() > CACHE_TTL_SECONDS

    def invalidate(self):
        """Mark cache as dirty. Next get() will refresh."""
        self._valid = False

    def refresh(self):
        """Force refresh of all stats (bypasses TTL)."""
        self._valid = False
        self._refresh()

    def _get_exclusion_clause(self, prefix: str = "") -> str:
        """' AND id NOT IN (...)': the records the Recording Scheme species-counting
        switches leave out (Settings > Species counting, or the chips on the Scheme
        dashboard; shared/species_counting.py)."""
        return counted_clause("recording_scheme", prefix, self._db)

    def _copies_out(self, prefix: str = "") -> str:
        """' AND <prefix>duplicate_of IS NULL' (or ''): for a join back to the scheme table,
        so a county first never points at the NBN copy of an iRecord record (Q59)."""
        from shared.scheme_duplicates import live_sql
        return live_sql(self._db, prefix) if self._db else ""

    def _get_family_clause(self, prefix: str = "") -> str:
        """The scheme scope used by every query here (scheme_scope): its `?` marks take
        _family_params()."""
        return scheme_scope(self._db, prefix)

    def _family_params(self) -> tuple:
        """The family names for the `?` marks in _get_family_clause."""
        return tuple(scheme_families())

    def _extract_grid_squares(self, grid_ref: str) -> Dict[str, str]:
        """Same squares and DINTY tetrad letters as the Observation statistics (one source, R19)."""
        from src.services.observation_stats_service import extract_grid_squares
        return extract_grid_squares(grid_ref)

    def _refresh(self):
        """Refresh all stats from database."""
        if not self._db:
            self._cache = {}
            self._valid = True
            self._last_refresh = datetime.now()
            return

        last_good = self._cache
        self._cache = {}
        try:
            exclusion = self._get_exclusion_clause()
            family_clause = self._get_family_clause()
            fp = self._family_params()
            sk = species_key_expr("recording_scheme", "", self._db)
            current_year = datetime.now().year

            # =============================================
            # BASIC COUNTS (combined query)
            # =============================================
            result = self._db.execute_main(f"""
                SELECT
                    COUNT(*) as total_records,
                    COUNT(DISTINCT CASE WHEN species_tvk IS NOT NULL THEN {sk} END) as total_species
                FROM recording_scheme
                WHERE species_name IS NOT NULL AND species_name != ''
                {exclusion}{family_clause}
            """, fp)
            if result:
                self._cache['total_records'] = result[0]['total_records'] or 0
                self._cache['total_species'] = result[0]['total_species'] or 0
            else:
                # Get record count without species filter
                result = self._db.execute_main(f"SELECT COUNT(*) as cnt FROM recording_scheme WHERE 1=1{family_clause}", fp)
                self._cache['total_records'] = result[0]['cnt'] if result else 0
                self._cache['total_species'] = 0

            # =============================================
            # GRID SQUARE COVERAGE
            # =============================================
            grid_query = f"""
                SELECT DISTINCT grid_ref
                FROM recording_scheme
                WHERE grid_ref IS NOT NULL AND grid_ref != ''
                {family_clause}
            """
            result = self._db.execute_main(grid_query, fp)
            
            monads = set()
            tetrads = set()
            hectads = set()
            
            for row in (result or []):
                squares = self._extract_grid_squares(row['grid_ref'])
                if 'monad' in squares:
                    monads.add(squares['monad'])
                if 'tetrad' in squares:
                    tetrads.add(squares['tetrad'])
                if 'hectad' in squares:
                    hectads.add(squares['hectad'])
            
            self._cache['monads_count'] = len(monads)
            self._cache['tetrads_count'] = len(tetrads)
            self._cache['hectads_count'] = len(hectads)

            # =============================================
            # VICE COUNTY BREAKDOWN
            # =============================================
            vc_query = f"""
                SELECT
                    vc_number,
                    vice_county as vc_name,
                    COUNT(*) as records,
                    COUNT(DISTINCT CASE WHEN species_tvk IS NOT NULL THEN {sk} END) as species
                FROM recording_scheme
                WHERE vc_number IS NOT NULL
                {exclusion}{family_clause}
                GROUP BY vc_number
                ORDER BY records DESC
            """
            result = self._db.execute_main(vc_query, fp)
            self._cache['records_by_vc'] = [
                {
                    'vc_number': r['vc_number'],
                    'vc_name': r['vc_name'] or f"VC{r['vc_number']}",
                    'records': r['records'],
                    'species': r['species']
                }
                for r in result
            ] if result else []
            
            self._cache['unique_vice_counties'] = len(self._cache['records_by_vc'])

            # =============================================
            # SPECIES LIST (species, records, VCs)
            # =============================================
            species_list_query = f'''
                SELECT
                    species_name,
                    COUNT(*) as records,
                    COUNT(DISTINCT vc_number) as vc_count
                FROM recording_scheme
                WHERE species_name IS NOT NULL AND species_name != ''
                {exclusion}{family_clause}
                GROUP BY species_name
                ORDER BY records DESC
            '''
            result = self._db.execute_main(species_list_query, fp)
            self._cache['species_list'] = [
                {
                    'species': r['species_name'],
                    'records': r['records'],
                    'vc_count': r['vc_count']
                }
                for r in result
            ] if result else []

            # =============================================
            # MONTHLY DISTRIBUTION (all time)
            # =============================================
            monthly_query = f"""
                SELECT 
                    CAST(strftime('%m', date) AS INTEGER) as month,
                    COUNT(*) as count
                FROM recording_scheme
                WHERE date IS NOT NULL
                {DAY_ONLY}{family_clause}
                GROUP BY month
                ORDER BY month
            """
            result = self._db.execute_main(monthly_query, fp)
            monthly_data = {r['month']: r['count'] for r in result} if result else {}
            self._cache['monthly_counts'] = [monthly_data.get(m, 0) for m in range(1, 13)]

            # =============================================
            # RECORDING GAPS - Species not recorded in X years
            # =============================================
            sk = species_key_expr("recording_scheme", "", self._db)
            # grouped by taxon, not name: a record kept under a second name of the same taxon
            # (e.g. an "agg." form) must not make the taxon look unrecorded (Round 4 review)
            gaps_query = f"""
                SELECT 
                    MIN(species_name) as species_name,
                    MAX(species_tvk) as species_tvk,
                    MAX(date) as last_recorded,
                    COUNT(*) as total_records
                FROM recording_scheme
                WHERE species_name IS NOT NULL AND date IS NOT NULL AND date != ''   -- undated is not a gap
                AND species_name LIKE '% %' AND species_name NOT LIKE '%(%'
                {exclusion}{family_clause}
                GROUP BY {sk}
                HAVING MAX(date) < date('now', '-3 years')
                ORDER BY last_recorded ASC
                LIMIT 50
            """
            result = self._db.execute_main(gaps_query, fp)
            
            gaps = []
            for r in (result or []):
                last_date = r['last_recorded']
                if last_date:
                    try:
                        last_year = int(last_date[:4])
                        years_ago = current_year - last_year
                        gaps.append({
                            'species': r['species_name'],
                            'tvk': r['species_tvk'],
                            'last_recorded': last_date,
                            'years_ago': years_ago,
                            'total_records': r['total_records']
                        })
                    except Exception:
                        pass
            
            self._cache['recording_gaps'] = gaps
            self._cache['gaps_3_years'] = len([g for g in gaps if g['years_ago'] >= 3])
            self._cache['gaps_5_years'] = len([g for g in gaps if g['years_ago'] >= 5])
            self._cache['gaps_10_years'] = len([g for g in gaps if g['years_ago'] >= 10])

            # =============================================
            # COUNTY FIRSTS (recent first records per VC)
            # =============================================
            county_firsts_query = f"""
                WITH first_records AS (
                    SELECT
                        species_tvk,
                        species_name,
                        vc_number,
                        MIN(date) as first_date
                    FROM recording_scheme
                    WHERE species_tvk IS NOT NULL
                    AND vc_number IS NOT NULL
                    AND date IS NOT NULL AND date != ''   -- undated is not a first (OBS-21)
                    {exclusion}{family_clause}
                    GROUP BY species_tvk, vc_number
                ),
                first_with_id AS (
                    SELECT
                        fr.species_name,
                        fr.vc_number,
                        fr.first_date,
                        MIN(rs.id) as record_id
                    FROM first_records fr
                    LEFT JOIN recording_scheme rs ON fr.species_tvk = rs.species_tvk
                        AND fr.first_date = rs.date
                        AND fr.vc_number = rs.vc_number{self._copies_out('rs.')}
                    GROUP BY fr.species_tvk, fr.vc_number
                )
                SELECT species_name, vc_number, first_date, record_id
                FROM first_with_id
                WHERE first_date IS NOT NULL
                ORDER BY first_date DESC
                LIMIT 100
            """
            result = self._db.execute_main(county_firsts_query, fp)
            self._cache['county_firsts'] = [
                {
                    'species': r['species_name'],
                    'vc_number': r['vc_number'],
                    'date': r['first_date'],
                    'record_id': r['record_id']
                }
                for r in result
            ] if result else []

            self._valid = True
            self._last_refresh = datetime.now()
            refresh_ok(self)

        except Exception as e:
            # keep the last good figures, try again on the next read, say why (R4B)
            refresh_failed(self, "RecordingSchemeStatsService", e, last_good)


    def get_monthly_counts_by_species(self, species_name: str) -> list:
        """Twelve monthly record counts for one species (the Monthly Distribution chart's
        species picker), selected as the all-species chart: day dates only, family scope.
        The picker called this but it did not exist, so picking a species did nothing."""
        if not self._db:
            return [0] * 12
        try:
            result = self._db.execute_main(f"""
                SELECT CAST(strftime('%m', date) AS INTEGER) as month, COUNT(*) as count
                FROM recording_scheme
                WHERE species_name = ? AND date IS NOT NULL
                {DAY_ONLY}{self._get_family_clause()}
                GROUP BY month
            """, (species_name, *self._family_params()))
            data = {r['month']: r['count'] for r in result} if result else {}
            return [data.get(m, 0) for m in range(1, 13)]
        except Exception as e:
            print(f"[RecordingSchemeStatsService] monthly counts for {species_name}: {e}")
            return [0] * 12

    def get_vc_details(self, vc_number: int) -> Dict[str, Any]:
        """Get detailed statistics for a specific Vice County."""
        from ..core.vc_shortnames import VC_FULL_NAMES
        
        result = {
            'vc_number': vc_number,
            'vc_name': VC_FULL_NAMES.get(str(vc_number), f"Vice County {vc_number}"),
            'species': 0,
            'records': 0,
            'species_list': [],
            'county_firsts': [],
            'monthly_records': []
        }
        
        if not self._db:
            return result
        
        try:
            exclusion = self._get_exclusion_clause()
            family_clause = self._get_family_clause()
            fp = self._family_params()
            sk = species_key_expr("recording_scheme", "", self._db)
            
            # Basic counts
            count_query = f"""
                SELECT 
                    COUNT(DISTINCT {sk}) as species,
                    COUNT(*) as records
                FROM recording_scheme
                WHERE vc_number = ?
                AND species_tvk IS NOT NULL
                {exclusion}{family_clause}
            """
            count_result = self._db.execute_main(count_query, (vc_number, *fp))
            if count_result:
                result['species'] = count_result[0]['species'] or 0
                result['records'] = count_result[0]['records'] or 0
            
            # Species list with record counts and first dates
            species_query = f"""
                SELECT 
                    species_name,
                    species_tvk,
                    COUNT(*) as record_count,
                    MIN(NULLIF(date, '')) as first_date   -- '' is undated, not earliest
                FROM recording_scheme
                WHERE vc_number = ?
                AND species_tvk IS NOT NULL
                {exclusion}{family_clause}
                GROUP BY species_name
                ORDER BY species_name
            """
            species_result = self._db.execute_main(species_query, (vc_number, *fp))
            if species_result:
                # Get common names from UKSI
                from ..repositories.uksi_repository import UKSIRepository
                uksi = UKSIRepository()
                
                result['species_list'] = []
                for r in species_result:
                    common_name = ""
                    try:
                        species_info = uksi.get_species_by_tvk(r['species_tvk'])
                        if species_info:
                            common_name = species_info.get('common_name') or ""
                    except Exception:
                        pass
                    
                    result['species_list'].append({
                        'species_name': r['species_name'],
                        'common_name': common_name,
                        'record_count': r['record_count'],
                        'first_date': r['first_date'] or ''
                    })
            
            # County firsts (first record of each species in this VC)
            firsts_query = f"""
                WITH first_records AS (
                    SELECT 
                        species_tvk,
                        species_name,
                        MIN(date) as first_date
                    FROM recording_scheme
                    WHERE vc_number = ?
                    AND species_tvk IS NOT NULL
                    AND date IS NOT NULL AND date != ''   -- undated is not a first (OBS-21)
                    {exclusion}{family_clause}
                    GROUP BY species_tvk
                )
                SELECT 
                    fr.species_name,
                    fr.first_date,
                    rs.recorder
                FROM first_records fr
                LEFT JOIN recording_scheme rs ON fr.species_tvk = rs.species_tvk 
                    AND fr.first_date = rs.date 
                    AND rs.vc_number = ?{self._copies_out('rs.')}
                ORDER BY fr.first_date DESC
                LIMIT 100
            """
            firsts_result = self._db.execute_main(firsts_query, (vc_number, *fp, vc_number))
            if firsts_result:
                from ..repositories.uksi_repository import UKSIRepository
                uksi = UKSIRepository()
                
                seen_species = set()
                result['county_firsts'] = []
                for r in firsts_result:
                    if r['species_name'] in seen_species:
                        continue
                    seen_species.add(r['species_name'])
                    
                    common_name = ""
                    try:
                        species_info = uksi.get_species_by_name(r['species_name'])
                        if species_info:
                            common_name = species_info.get('common_name') or ""
                    except Exception:
                        pass
                    
                    result['county_firsts'].append({
                        'date': r['first_date'] or '',
                        'species_name': r['species_name'],
                        'common_name': common_name,
                        'recorder': r['recorder'] or ''
                    })
            
            # Monthly distribution
            monthly_query = f"""
                SELECT 
                    CAST(strftime('%m', date) AS INTEGER) as month,
                    COUNT(*) as count
                FROM recording_scheme
                WHERE vc_number = ?
                AND date IS NOT NULL
                {DAY_ONLY}{family_clause}
                GROUP BY month
                ORDER BY month
            """
            monthly_result = self._db.execute_main(monthly_query, (vc_number, *fp))
            monthly_data = {r['month']: r['count'] for r in monthly_result} if monthly_result else {}
            result['monthly_records'] = [monthly_data.get(m, 0) for m in range(1, 13)]
            
            # Recording gaps -- species not seen in 3+ years in this VC
            gaps_query = f"""
                SELECT
                    species_name,
                    species_tvk,
                    MAX(date) as last_recorded,
                    CAST((julianday('now') - julianday(MAX(date))) / 365.25 AS INTEGER) as years_ago
                FROM recording_scheme
                WHERE vc_number = ?
                AND date IS NOT NULL
                AND species_tvk IS NOT NULL
                {exclusion}{family_clause}
                GROUP BY species_tvk
                HAVING years_ago >= 3
                ORDER BY years_ago DESC
            """
            gaps_result = self._db.execute_main(gaps_query, (vc_number, *fp))
            if gaps_result:
                from ..repositories.uksi_repository import UKSIRepository
                uksi = UKSIRepository()
                result['recording_gaps'] = []
                for r in gaps_result:
                    common_name = ""
                    try:
                        species_info = uksi.get_species_by_tvk(r['species_tvk'])
                        if species_info:
                            common_name = species_info.get('common_name') or ""
                    except Exception:
                        pass
                    result['recording_gaps'].append({
                        'species_name': r['species_name'],
                        'common_name': common_name,
                        'last_recorded': r['last_recorded'] or '',
                        'years_ago': r['years_ago']
                    })

        except Exception as e:
            print(f"[RecordingSchemeStatsService] Error getting VC details: {e}")
            import traceback
            traceback.print_exc()
        
        return result


_service_instance: Optional[RecordingSchemeStatsService] = None


def get_recording_scheme_stats() -> RecordingSchemeStatsService:
    """Get the singleton RecordingSchemeStatsService instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = RecordingSchemeStatsService()
    return _service_instance
