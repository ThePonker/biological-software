"""
Specimen Stats Service.

Centralized statistics for specimen/collection data.
Single source of truth for all collection-related stats.

PERFORMANCE OPTIMIZATIONS:
- TTL cache (30 seconds) prevents redundant refreshes
- Combined queries reduce database round trips
"""

from typing import Dict, Any, Optional
from datetime import datetime


CACHE_TTL_SECONDS = 30


class SpecimenStatsService:
    """
    Singleton service providing cached statistics for specimen data.
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
        """Insect Collection does not use observation exclusion filters.
        Genus-only and aggregate specimens are valid collection records."""
        return ""

    def _refresh(self):
        """Refresh all stats from database."""
        if not self._db:
            self._cache = {}
            self._valid = True
            self._last_refresh = datetime.now()
            return

        try:
            exclusion = self._get_exclusion_clause()

            # =============================================
            # BASIC COUNTS (combined query)
            # =============================================
            result = self._db.execute_main(f"""
                SELECT 
                    COUNT(*) as total_specimens,
                    COUNT(DISTINCT species_tvk) as total_species
                FROM specimens
                WHERE species_tvk IS NOT NULL
                {exclusion}
            """)
            if result:
                self._cache['total_specimens'] = result[0]['total_specimens'] or 0
                self._cache['total_species'] = result[0]['total_species'] or 0
            else:
                result = self._db.execute_main("SELECT COUNT(*) as cnt FROM specimens")
                self._cache['total_specimens'] = result[0]['cnt'] if result else 0
                self._cache['total_species'] = 0

            # =============================================
            # SPECIMENS BY ORDER
            # =============================================
            order_query = f"""
                SELECT 
                    order_name as label, 
                    COUNT(DISTINCT species_tvk) as species,
                    COUNT(*) as specimens
                FROM specimens
                WHERE order_name IS NOT NULL AND order_name != ''
                AND species_tvk IS NOT NULL
                {exclusion}
                GROUP BY order_name
                ORDER BY specimens DESC
            """
            result = self._db.execute_main(order_query)
            self._cache['specimens_by_order'] = [
                {'label': r['label'], 'species': r['species'], 'specimens': r['specimens']} 
                for r in result
            ] if result else []

            # =============================================
            # SPECIMENS BY FAMILY
            # =============================================
            family_query = f"""
                SELECT 
                    family,
                    COUNT(DISTINCT species_tvk) as species,
                    COUNT(*) as specimens
                FROM specimens
                WHERE family IS NOT NULL AND family != ''
                AND species_tvk IS NOT NULL
                {exclusion}
                GROUP BY family
                ORDER BY specimens DESC
            """
            result = self._db.execute_main(family_query)
            self._cache['specimens_by_family'] = [
                {'family': r['family'], 'species': r['species'], 'specimens': r['specimens']} 
                for r in result
            ] if result else []

            # =============================================
            # STORAGE LOCATION BREAKDOWN
            # =============================================
            storage_query = """
                SELECT 
                    COALESCE(storage_location, 'Unassigned') as location,
                    COUNT(*) as count
                FROM specimens
                GROUP BY storage_location
                ORDER BY count DESC
            """
            result = self._db.execute_main(storage_query)
            self._cache['specimens_by_storage'] = [
                {'location': r['location'], 'count': r['count']}
                for r in result
            ] if result else []

            # =============================================
            # CONDITION BREAKDOWN
            # =============================================
            condition_query = """
                SELECT 
                    COALESCE(condition, 'Unknown') as condition,
                    COUNT(*) as count
                FROM specimens
                GROUP BY condition
                ORDER BY count DESC
            """
            result = self._db.execute_main(condition_query)
            self._cache['specimens_by_condition'] = [
                {'condition': r['condition'], 'count': r['count']}
                for r in result
            ] if result else []

            # =============================================
            # PREPARATION TYPE BREAKDOWN
            # =============================================
            prep_query = """
                SELECT 
                    COALESCE(preparation_type, 'Unknown') as prep_type,
                    COUNT(*) as count
                FROM specimens
                GROUP BY preparation_type
                ORDER BY count DESC
            """
            result = self._db.execute_main(prep_query)
            self._cache['specimens_by_prep_type'] = [
                {'prep_type': r['prep_type'], 'count': r['count']}
                for r in result
            ] if result else []

            # =============================================
            # VICE COUNTY BREAKDOWN
            # =============================================
            vc_query = f"""
                SELECT 
                    vc_number,
                    vice_county as vc_name,
                    COUNT(*) as specimens,
                    COUNT(DISTINCT species_tvk) as species
                FROM specimens
                WHERE vc_number IS NOT NULL
                {exclusion}
                GROUP BY vc_number
                ORDER BY specimens DESC
            """
            result = self._db.execute_main(vc_query)
            self._cache['specimens_by_vc'] = [
                {
                    'vc_number': r['vc_number'],
                    'vc_name': r['vc_name'] or f"VC{r['vc_number']}",
                    'specimens': r['specimens'],
                    'species': r['species']
                }
                for r in result
            ] if result else []

            self._cache['unique_vice_counties'] = len(self._cache['specimens_by_vc'])

            # =============================================
            # RECENT ADDITIONS
            # =============================================
            recent_query = f"""
                SELECT s.id, s.species_name, s.specimen_code, s.date_collected,
                       s.site_name, s.storage_location, s.created_at
                FROM specimens s
                INNER JOIN (
                    SELECT species_name, MIN(date_collected) as first_collected
                    FROM specimens
                    WHERE species_name IS NOT NULL AND date_collected IS NOT NULL
                    GROUP BY species_name
                ) firsts ON s.species_name = firsts.species_name AND s.date_collected = firsts.first_collected
                WHERE s.species_name IS NOT NULL
                {exclusion}
                GROUP BY s.species_name
                ORDER BY s.date_collected DESC
                LIMIT 10
            """
            result = self._db.execute_main(recent_query)
            self._cache['recent_specimens'] = [
                {
                    'id': r['id'],
                    'species': r['species_name'],
                    'code': r['specimen_code'] or '',
                    'date': r['date_collected'] or '',
                    'location': r['site_name'] or '',
                    'storage': r['storage_location'] or ''
                }
                for r in result
            ] if result else []

            # =============================================
            # SPECIMENS BY YEAR
            # =============================================
            year_query = f"""
                SELECT
                    CASE 
                        WHEN date_collected LIKE '____-__-__' THEN SUBSTR(date_collected, 1, 4)
                        ELSE '20' || SUBSTR(TRIM(date_collected), -2)
                    END as year,
                    COUNT(*) as specimens,
                    COUNT(DISTINCT species_tvk) as species
                FROM specimens
                WHERE date_collected IS NOT NULL 
                AND date_collected != ''
                AND LENGTH(TRIM(date_collected)) >= 6
                AND species_tvk IS NOT NULL
                {exclusion}
                GROUP BY CASE 
                        WHEN date_collected LIKE '____-__-__' THEN SUBSTR(date_collected, 1, 4)
                        ELSE '20' || SUBSTR(TRIM(date_collected), -2)
                    END
                ORDER BY year DESC
            """
            result = self._db.execute_main(year_query)
            self._cache['specimens_by_year'] = [
                {'year': r['year'], 'specimens': r['specimens'], 'species': r['species']}
                for r in result
            ] if result else []

            # =============================================
            # NEW SPECIES BY YEAR (first recorded each year)
            # =============================================
            new_species_query = f"""
                SELECT 
                    first_year as year,
                    COUNT(*) as new_species
                FROM (
                    SELECT 
                        species_tvk,
                        CASE 
                        WHEN MIN(date_collected) LIKE '____-__-__' THEN SUBSTR(MIN(date_collected), 1, 4)
                        ELSE '20' || SUBSTR(TRIM(MIN(date_collected)), -2)
                    END as first_year
                    FROM specimens
                    WHERE species_tvk IS NOT NULL 
                    AND date_collected IS NOT NULL 
                    AND date_collected != ''
                    AND LENGTH(TRIM(date_collected)) >= 6
                    {exclusion}
                    GROUP BY species_tvk
                )
                WHERE first_year IS NOT NULL
                GROUP BY first_year
                ORDER BY year DESC
            """
            result = self._db.execute_main(new_species_query)
            self._cache['new_species_by_year'] = [
                {'year': r['year'], 'new_species': r['new_species']}
                for r in result
            ] if result else []

            self._valid = True
            self._last_refresh = datetime.now()

        except Exception as e:
            print(f"[SpecimenStatsService] Error refreshing stats: {e}")
            import traceback
            traceback.print_exc()
            self._cache = {}
            self._valid = True
            self._last_refresh = datetime.now()



    def get_species_list(self, filter_type: str, filter_value: str) -> list:
        """Get list of species with first/last recorded dates.
        
        Args:
            filter_type: Type of filter ('order', 'family', 'year', 'new_species_year')
            filter_value: Value to filter by
            
        Returns:
            List of dicts with species_name, first_date, last_date
        """
        if not self._db:
            return []
        
        try:
            # Build WHERE clause based on filter type
            if filter_type == 'order':
                where_clause = "WHERE order_name = ?"
                params = [filter_value]
            elif filter_type == 'family':
                where_clause = "WHERE family = ?"
                params = [filter_value]
            elif filter_type == 'year':
                # Handle mixed date formats for year extraction
                where_clause = """WHERE (
                    CASE 
                        WHEN date_collected LIKE '____-__-__' THEN SUBSTR(date_collected, 1, 4)
                        ELSE '20' || SUBSTR(TRIM(date_collected), -2)
                    END
                ) = ?"""
                params = [filter_value]
            elif filter_type == 'new_species_year':
                # Species first recorded in this year
                year = filter_value
                result = self._db.execute_main("""
                    SELECT species_name, MIN(date_collected) as first_date, MAX(date_collected) as last_date
                    FROM specimens
                    WHERE species_name IS NOT NULL AND species_name != ''
                    GROUP BY species_name
                    HAVING (
                        CASE 
                            WHEN MIN(date_collected) LIKE '____-__-__' THEN SUBSTR(MIN(date_collected), 1, 4)
                            ELSE '20' || SUBSTR(TRIM(MIN(date_collected)), -2)
                        END
                    ) = ?
                    ORDER BY species_name
                """, [year])
                return [dict(row) for row in result] if result else []
            else:
                where_clause = "WHERE 1=1"
                params = []
            
            query = f"""
                SELECT species_name, 
                       MIN(date_collected) as first_date, 
                       MAX(date_collected) as last_date
                FROM specimens
                {where_clause}
                AND species_name IS NOT NULL AND species_name != ''
                GROUP BY species_name
                ORDER BY species_name
            """
            
            result = self._db.execute_main(query, params)
            return [dict(row) for row in result] if result else []
            
        except Exception as e:
            print(f"Error getting species list: {e}")
            return []

_service_instance: Optional[SpecimenStatsService] = None



def get_specimen_stats() -> SpecimenStatsService:
    """Get the singleton SpecimenStatsService instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = SpecimenStatsService()
    return _service_instance


def invalidate_specimen_stats():
    """Invalidate the stats cache."""
    global _service_instance
    if _service_instance is not None:
        _service_instance.invalidate()