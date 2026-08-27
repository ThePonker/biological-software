"""
Recording Scheme Stats Service.

Centralized statistics for recording scheme data.
Single source of truth for all scheme-related stats.

PERFORMANCE OPTIMIZATIONS:
- TTL cache (30 seconds) prevents redundant refreshes
- Combined queries reduce database round trips
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from PySide6.QtCore import QSettings


CACHE_TTL_SECONDS = 300


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
        """Get SQL clause for excluding species based on filter settings.
        
        Each filter works independently.
        """
        settings = QSettings()
        col = f"{prefix}species_name" if prefix else "species_name"
        clauses = []
        
        # Family-only: exclude names ending in -idae or -inae (e.g., "Cerambycidae")
        if settings.value("stats/scheme_exclude_family", False, type=bool):
            clauses.append(f"{col} NOT LIKE '%idae'")
            clauses.append(f"{col} NOT LIKE '%inae'")
        
        # Genus-only: exclude single-word names (no space), "sp." entries, and subgenus-only names
        # Subgenus-only: "Genus (subgenus)" pattern without species epithet
        # A valid species has format "Genus epithet" or "Genus (subgenus) epithet"
        # But preserve family names (-idae/-inae) as valid identifications
        if settings.value("stats/scheme_exclude_genus", False, type=bool):
            # Must have a space followed by a letter (not just parenthesis)
            # OR be a family name (-idae/-inae)
            # This excludes: "Rhagium", "Rhagium sp.", "Rhagium (hagrium)"
            # But keeps: "Rhagium mordax", "Rhagium (hagrium) mordax", "Cerambycidae"
            clauses.append(f"""(
                ({col} LIKE '%idae' OR {col} LIKE '%inae')
                OR (
                    {col} LIKE '% %' 
                    AND {col} NOT GLOB '*([a-z]*)'
                    AND {col} NOT LIKE '% sp.%'
                    AND {col} NOT LIKE '% sp'
                    AND {col} NOT LIKE '%indet%'
                )
            )""")
        
        # s.s. (sensu stricto)
        if settings.value("stats/scheme_exclude_ss", False, type=bool):
            clauses.append(f"{col} NOT LIKE '%s.s.%'")
            clauses.append(f"{col} NOT LIKE '%sensu stricto%'")
        
        # s.l. (sensu lato)
        if settings.value("stats/scheme_exclude_sl", False, type=bool):
            clauses.append(f"{col} NOT LIKE '%s.l.%'")
            clauses.append(f"{col} NOT LIKE '%sensu lato%'")
        
        # Aggregates
        if settings.value("stats/scheme_exclude_agg", False, type=bool):
            clauses.append(f"{col} NOT LIKE '%agg.%'")
            clauses.append(f"{col} NOT LIKE '%agg %'")
            clauses.append(f"{col} NOT LIKE '% agg'")
        
        if clauses:
            result = " AND " + " AND ".join(clauses)
            return result
        return ""

    def _get_family_clause(self, prefix: str = "") -> str:
        """Get SQL WHERE clause for scheme family scope from settings."""
        from PySide6.QtCore import QSettings
        fam_str = QSettings().value("scheme/families", "", str).strip()
        if not fam_str:
            return ""
        families = [f.strip() for f in fam_str.split(',') if f.strip()]
        if not families:
            return ""
        col = f"{prefix}family" if prefix else "family"
        placeholders = ','.join([f"'{f}'" for f in families])
        return f" AND {col} IN ({placeholders})"

    def _extract_grid_squares(self, grid_ref: str) -> Dict[str, str]:
        """Extract monad, tetrad, hectad from a grid reference."""
        if not grid_ref or len(grid_ref) < 4:
            return {}
        
        gr = grid_ref.upper().replace(" ", "")
        
        letters = ""
        digits = ""
        for i, c in enumerate(gr):
            if c.isalpha():
                letters += c
            else:
                digits = gr[i:]
                break
        
        if len(letters) < 1 or len(digits) < 2:
            return {}
        
        result = {}
        
        if len(digits) >= 2:
            result['hectad'] = f"{letters}{digits[0]}{digits[len(digits)//2]}"
        
        if len(digits) >= 4:
            e = int(digits[1])
            n = int(digits[len(digits)//2 + 1])
            tetrad_letter = chr(ord('A') + (n // 2) * 5 + (e // 2))
            if tetrad_letter > 'O':
                tetrad_letter = chr(ord(tetrad_letter) + 1)
            result['tetrad'] = f"{result['hectad']}{tetrad_letter}"
        
        if len(digits) >= 4:
            result['monad'] = f"{letters}{digits[0]}{digits[1]}{digits[len(digits)//2]}{digits[len(digits)//2 + 1]}"
        
        return result

    def _refresh(self):
        """Refresh all stats from database."""
        if not self._db:
            self._cache = {}
            self._valid = True
            self._last_refresh = datetime.now()
            return

        try:
            exclusion = self._get_exclusion_clause()
            family_clause = self._get_family_clause()
            current_year = datetime.now().year

            # =============================================
            # BASIC COUNTS (combined query)
            # =============================================
            result = self._db.execute_main(f"""
                SELECT
                    COUNT(*) as total_records,
                    COUNT(DISTINCT species_name) as total_species
                FROM recording_scheme
                WHERE species_name IS NOT NULL AND species_name != ''
                {exclusion}{family_clause}
            """)
            if result:
                self._cache['total_records'] = result[0]['total_records'] or 0
                self._cache['total_species'] = result[0]['total_species'] or 0
            else:
                # Get record count without species filter
                result = self._db.execute_main(f"SELECT COUNT(*) as cnt FROM recording_scheme WHERE 1=1{family_clause}")
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
            result = self._db.execute_main(grid_query)
            
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
                    COUNT(DISTINCT species_name) as species
                FROM recording_scheme
                WHERE vc_number IS NOT NULL
                {exclusion}{family_clause}
                GROUP BY vc_number
                ORDER BY records DESC
            """
            result = self._db.execute_main(vc_query)
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
            result = self._db.execute_main(species_list_query)
            self._cache['species_list'] = [
                {
                    'species': r['species_name'],
                    'records': r['records'],
                    'vc_count': r['vc_count']
                }
                for r in result
            ] if result else []

            # =============================================
            # SPECIES BY ORDER
            # =============================================
            order_query = f"""
                SELECT 
                    order_name as label, 
                    COUNT(DISTINCT species_tvk) as species,
                    COUNT(*) as records
                FROM recording_scheme
                WHERE order_name IS NOT NULL AND order_name != ''
                AND species_tvk IS NOT NULL
                
                GROUP BY order_name
                ORDER BY species DESC
            """
            result = self._db.execute_main(order_query)
            self._cache['species_by_order'] = [
                {'label': r['label'], 'species': r['species'], 'records': r['records']} 
                for r in result
            ] if result else []

            # =============================================
            # SPECIES BY FAMILY
            # =============================================
            family_query = f"""
                SELECT 
                    family,
                    COUNT(DISTINCT species_tvk) as species,
                    COUNT(*) as records
                FROM recording_scheme
                WHERE family IS NOT NULL AND family != ''
                AND species_tvk IS NOT NULL
                
                GROUP BY family
                ORDER BY species DESC
            """
            result = self._db.execute_main(family_query)
            self._cache['species_by_family'] = [
                {'family': r['family'], 'species': r['species'], 'records': r['records']} 
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
                {family_clause}
                GROUP BY month
                ORDER BY month
            """
            result = self._db.execute_main(monthly_query)
            monthly_data = {r['month']: r['count'] for r in result} if result else {}
            self._cache['monthly_counts'] = [monthly_data.get(m, 0) for m in range(1, 13)]

            # =============================================
            # RECORDING GAPS - Species not recorded in X years
            # =============================================
            gaps_query = f"""
                SELECT 
                    species_name,
                    MAX(species_tvk) as species_tvk,
                    MAX(date) as last_recorded,
                    COUNT(*) as total_records
                FROM recording_scheme
                WHERE species_name IS NOT NULL AND date IS NOT NULL AND species_name LIKE '% %' AND species_name NOT LIKE '%(%'
                
                GROUP BY species_name
                HAVING MAX(date) < date('now', '-3 years')
                ORDER BY last_recorded ASC
                LIMIT 50
            """
            result = self._db.execute_main(gaps_query)
            
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
                    except:
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
                    AND date IS NOT NULL
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
                        AND fr.vc_number = rs.vc_number
                    GROUP BY fr.species_tvk, fr.vc_number
                )
                SELECT species_name, vc_number, first_date, record_id
                FROM first_with_id
                WHERE first_date IS NOT NULL
                ORDER BY first_date DESC
                LIMIT 100
            """
            result = self._db.execute_main(county_firsts_query)
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

        except Exception as e:
            print(f"[RecordingSchemeStatsService] Error refreshing stats: {e}")
            import traceback
            traceback.print_exc()
            self._cache = {}
            self._valid = True
            self._last_refresh = datetime.now()


    def get_vc_details(self, vc_number: int) -> Dict[str, Any]:
        """Get detailed statistics for a specific Vice County."""
        from ..core.vc_shortnames import VC_FULL_NAMES
        from ..utils.date_utils import format_date_for_display
        
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
            
            # Basic counts
            count_query = f"""
                SELECT 
                    COUNT(DISTINCT species_tvk) as species,
                    COUNT(*) as records
                FROM recording_scheme
                WHERE vc_number = ?
                AND species_tvk IS NOT NULL
                {exclusion}{family_clause}
            """
            count_result = self._db.execute_main(count_query, (vc_number,))
            if count_result:
                result['species'] = count_result[0]['species'] or 0
                result['records'] = count_result[0]['records'] or 0
            
            # Species list with record counts and first dates
            species_query = f"""
                SELECT 
                    species_name,
                    species_tvk,
                    COUNT(*) as record_count,
                    MIN(date) as first_date
                FROM recording_scheme
                WHERE vc_number = ?
                AND species_tvk IS NOT NULL
                {exclusion}{family_clause}
                GROUP BY species_name
                ORDER BY species_name
            """
            species_result = self._db.execute_main(species_query, (vc_number,))
            if species_result:
                # Get common names from UKSI
                from ..repositories.uksi_repository import UKSIRepository
                uksi = UKSIRepository()
                
                result['species_list'] = []
                for r in species_result:
                    common_name = ""
                    try:
                        species_info = uksi.get_by_tvk(r['species_tvk'])
                        if species_info:
                            common_name = species_info.common_name or ""
                    except:
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
                    AND date IS NOT NULL
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
                    AND rs.vc_number = ?
                ORDER BY fr.first_date DESC
                LIMIT 100
            """
            firsts_result = self._db.execute_main(firsts_query, (vc_number, vc_number))
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
                        species_info = uksi.get_by_name(r['species_name'])
                        if species_info:
                            common_name = species_info.common_name or ""
                    except:
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
                {family_clause}
                GROUP BY month
                ORDER BY month
            """
            monthly_result = self._db.execute_main(monthly_query, (vc_number,))
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
            gaps_result = self._db.execute_main(gaps_query, (vc_number,))
            if gaps_result:
                from ..repositories.uksi_repository import UKSIRepository
                uksi = UKSIRepository()
                result['recording_gaps'] = []
                for r in gaps_result:
                    common_name = ""
                    try:
                        species_info = uksi.get_by_tvk(r['species_tvk'])
                        if species_info:
                            common_name = species_info.common_name or ""
                    except:
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


def invalidate_recording_scheme_stats():
    """Invalidate the stats cache."""
    global _service_instance
    if _service_instance is not None:
        _service_instance.invalidate()