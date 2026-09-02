"""
Observation Stats Service.

Centralized statistics for observation data.
Single source of truth for all observation-related stats.

PERFORMANCE OPTIMIZATIONS:
- TTL cache (30 seconds) prevents redundant refreshes
- Lazy refresh only when data is requested
- Background refresh capability
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from PySide6.QtCore import QSettings


# Cache TTL in seconds
CACHE_TTL_SECONDS = 300


def get_observation_exclusion_clause(prefix: str = "") -> str:
    """Get SQL WHERE clause for species name exclusion filters. Shared by stats service and dashboards."""
    from PySide6.QtCore import QSettings
    settings = QSettings()
    exclude = settings.value("display/exclude_incomplete_species", True, type=bool)
    col = f"{prefix}species_name" if prefix else "species_name"
    if exclude:
        return f"""
            AND {col} LIKE '% %'
            AND {col} NOT LIKE '%agg.%'
            AND {col} NOT LIKE '%agg %'
            AND {col} NOT LIKE '% agg'
            AND {col} NOT LIKE '%s.l.%'
            AND {col} NOT LIKE '%sensu lato%'
        """
    return ""


class ObservationStatsService:
    """
    Singleton service providing cached statistics for observation data.
    
    Performance features:
    - TTL-based cache invalidation
    - Lazy refresh on first access
    - Manual invalidation for data changes
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
        # Don't auto-refresh here - lazy load on first get()

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
        """Get SQL clause for excluding incomplete species."""
        settings = QSettings()
        exclude = settings.value("display/exclude_incomplete_species", True, type=bool)
        
        col = f"{prefix}species_name" if prefix else "species_name"

        if exclude:
            return f"""
                AND {col} LIKE '% %'
                AND {col} NOT LIKE '%agg.%'
                AND {col} NOT LIKE '%agg %'
                AND {col} NOT LIKE '% agg'
                AND {col} NOT LIKE '%s.l.%'
                AND {col} NOT LIKE '%sensu lato%'
            """
        return ""

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
            current_year = datetime.now().year

            # =============================================
            # BASIC COUNTS
            # =============================================
            result = self._db.execute_main("""
                SELECT 
                    COUNT(*) as total_records,
                    COUNT(CASE WHEN record_type = 'Personal' THEN 1 END) as personal_records,
                    COUNT(CASE WHEN record_type = 'Commercial' THEN 1 END) as commercial_records
                FROM observations
            """)
            if result:
                self._cache['total_records'] = result[0]['total_records'] or 0
                self._cache['personal_records'] = result[0]['personal_records'] or 0
                self._cache['commercial_records'] = result[0]['commercial_records'] or 0

            # Species counts - combined query
            species_query = f"""
                SELECT 
                    COUNT(DISTINCT species_tvk) as total_species,
                    COUNT(DISTINCT CASE WHEN record_type = 'Personal' THEN species_tvk END) as personal_species,
                    COUNT(DISTINCT CASE WHEN record_type = 'Commercial' THEN species_tvk END) as commercial_species
                FROM observations
                WHERE species_tvk IS NOT NULL
                {exclusion}
            """
            result = self._db.execute_main(species_query)
            if result:
                self._cache['total_species'] = result[0]['total_species'] or 0
                self._cache['personal_species'] = result[0]['personal_species'] or 0
                self._cache['commercial_species'] = result[0]['commercial_species'] or 0

            # =============================================
            # THIS YEAR COUNTS
            # =============================================
            year_query = f"""
                SELECT 
                    COUNT(*) as records,
                    COUNT(DISTINCT species_tvk) as species
                FROM observations
                WHERE strftime('%Y', date) = ?
                AND species_tvk IS NOT NULL
                {exclusion}
            """
            result = self._db.execute_main(year_query, (str(current_year),))
            if result:
                self._cache['records_this_year'] = result[0]['records'] or 0
                self._cache['species_this_year'] = result[0]['species'] or 0

            # =============================================
            # GRID SQUARE COVERAGE (combined for all + commercial)
            # =============================================
            grid_query = """
                SELECT grid_ref, record_type
                FROM observations
                WHERE grid_ref IS NOT NULL AND grid_ref != ''
            """
            result = self._db.execute_main(grid_query)
            
            all_monads, all_tetrads, all_hectads = set(), set(), set()
            com_monads, com_tetrads, com_hectads = set(), set(), set()
            per_monads, per_tetrads, per_hectads = set(), set(), set()
            
            for row in (result or []):
                squares = self._extract_grid_squares(row['grid_ref'])
                is_commercial = row['record_type'] == 'Commercial'
                
                is_personal = row['record_type'] == 'Personal'
                if 'monad' in squares:
                    all_monads.add(squares['monad'])
                    if is_commercial:
                        com_monads.add(squares['monad'])
                    if is_personal:
                        per_monads.add(squares['monad'])
                if 'tetrad' in squares:
                    all_tetrads.add(squares['tetrad'])
                    if is_commercial:
                        com_tetrads.add(squares['tetrad'])
                    if is_personal:
                        per_tetrads.add(squares['tetrad'])
                if 'hectad' in squares:
                    all_hectads.add(squares['hectad'])
                    if is_commercial:
                        com_hectads.add(squares['hectad'])
                    if is_personal:
                        per_hectads.add(squares['hectad'])
            
            self._cache['monads_count'] = len(all_monads)
            self._cache['tetrads_count'] = len(all_tetrads)
            self._cache['hectads_count'] = len(all_hectads)
            self._cache['commercial_monads_count'] = len(com_monads)
            self._cache['commercial_tetrads_count'] = len(com_tetrads)
            self._cache['commercial_hectads_count'] = len(com_hectads)
            self._cache['personal_monads_count'] = len(per_monads)
            self._cache['personal_tetrads_count'] = len(per_tetrads)
            self._cache['personal_hectads_count'] = len(per_hectads)

            # =============================================
            # SPECIES BY ORDER (combined query)
            # =============================================
            order_query = f"""
                SELECT 
                    order_name as label, 
                    COUNT(DISTINCT species_tvk) as species,
                    COUNT(*) as records,
                    COUNT(DISTINCT CASE WHEN record_type = 'Commercial' THEN species_tvk END) as commercial_species,
                    COUNT(CASE WHEN record_type = 'Commercial' THEN 1 END) as commercial_records,
                    COUNT(DISTINCT CASE WHEN record_type = 'Personal' THEN species_tvk END) as personal_species,
                    COUNT(CASE WHEN record_type = 'Personal' THEN 1 END) as personal_records
                FROM observations
                WHERE order_name IS NOT NULL AND order_name != ''
                AND species_tvk IS NOT NULL
                {exclusion}
                GROUP BY order_name
                ORDER BY species DESC
            """
            result = self._db.execute_main(order_query)
            
            all_orders = []
            commercial_orders = []
            personal_orders = []
            for r in (result or []):
                all_orders.append({
                    'label': r['label'], 
                    'species': r['species'], 
                    'records': r['records']
                })
                if r['commercial_species'] > 0:
                    commercial_orders.append({
                        'label': r['label'],
                        'species': r['commercial_species'],
                        'records': r['commercial_records']
                    })
                if r['personal_species'] > 0:
                    personal_orders.append({
                        'label': r['label'],
                        'species': r['personal_species'],
                        'records': r['personal_records']
                    })
            
            self._cache['species_by_order'] = all_orders
            self._cache['commercial_species_by_order'] = sorted(
                commercial_orders, key=lambda x: x['species'], reverse=True
            )
            self._cache['personal_species_by_order'] = sorted(
                personal_orders, key=lambda x: x['species'], reverse=True
            )

            # =============================================
            # SPECIES BY FAMILY (combined query)
            # =============================================
            family_query = f"""
                SELECT 
                    family,
                    COUNT(DISTINCT species_tvk) as species,
                    COUNT(*) as records,
                    COUNT(DISTINCT CASE WHEN record_type = 'Commercial' THEN species_tvk END) as commercial_species,
                    COUNT(CASE WHEN record_type = 'Commercial' THEN 1 END) as commercial_records,
                    COUNT(DISTINCT CASE WHEN record_type = 'Personal' THEN species_tvk END) as personal_species,
                    COUNT(CASE WHEN record_type = 'Personal' THEN 1 END) as personal_records
                FROM observations
                WHERE family IS NOT NULL AND family != ''
                AND species_tvk IS NOT NULL
                {exclusion}
                GROUP BY family
                ORDER BY species DESC
            """
            result = self._db.execute_main(family_query)
            
            all_families = []
            commercial_families = []
            personal_families = []
            for r in (result or []):
                all_families.append({
                    'family': r['family'],
                    'species': r['species'],
                    'records': r['records']
                })
                if r['commercial_species'] > 0:
                    commercial_families.append({
                        'family': r['family'],
                        'species': r['commercial_species'],
                        'records': r['commercial_records']
                    })
                if r['personal_species'] > 0:
                    personal_families.append({
                        'family': r['family'],
                        'species': r['personal_species'],
                        'records': r['personal_records']
                    })
            
            self._cache['species_by_family'] = all_families
            self._cache['commercial_species_by_family'] = sorted(
                commercial_families, key=lambda x: x['species'], reverse=True
            )
            self._cache['personal_species_by_family'] = sorted(
                personal_families, key=lambda x: x['species'], reverse=True
            )

            # =============================================
            # MONTHLY COUNTS (all time distribution)
            # =============================================
            monthly_query = """
                SELECT 
                    CAST(strftime('%m', date) AS INTEGER) as month,
                    COUNT(*) as count,
                    COUNT(CASE WHEN record_type = 'Commercial' THEN 1 END) as commercial_count
                FROM observations
                WHERE date IS NOT NULL
                GROUP BY month
                ORDER BY month
            """
            result = self._db.execute_main(monthly_query)
            monthly_data = {r['month']: r['count'] for r in result} if result else {}
            commercial_monthly = {r['month']: r['commercial_count'] for r in result} if result else {}
            self._cache['monthly_counts'] = [monthly_data.get(m, 0) for m in range(1, 13)]
            self._cache['commercial_monthly_counts'] = [commercial_monthly.get(m, 0) for m in range(1, 13)]
            self._cache['personal_monthly_counts'] = [monthly_data.get(m, 0) - commercial_monthly.get(m, 0) for m in range(1, 13)]

            # Commercial monthly species counts
            result = self._db.execute_main(f"""
                SELECT CAST(strftime('%m', date) AS INTEGER) as month,
                    COUNT(DISTINCT species_tvk) as species_count
                FROM observations
                WHERE record_type = 'Commercial'
                AND date IS NOT NULL AND date != ''
                AND species_tvk IS NOT NULL AND species_tvk != ''
                {exclusion}
                GROUP BY month
            """)
            commercial_monthly_species = {r['month']: r['species_count'] for r in result} if result else {}
            self._cache['commercial_monthly_species_counts'] = [commercial_monthly_species.get(m, 0) for m in range(1, 13)]

            # Personal monthly species ? need separate query
            personal_monthly_species_q = f"""
                SELECT CAST(strftime('%m', date) AS INTEGER) as month,
                       COUNT(DISTINCT species_tvk) as species_count
                FROM observations
                WHERE date IS NOT NULL AND species_tvk IS NOT NULL
                AND record_type = 'Personal'
                {exclusion}
                GROUP BY month
            """
            result = self._db.execute_main(personal_monthly_species_q)
            personal_monthly_species = {r['month']: r['species_count'] for r in (result or [])}

            # Commercial vice counties
            result = self._db.execute_main("""
                SELECT COUNT(DISTINCT vc_number) as vc_count
                FROM observations
                WHERE record_type = 'Commercial'
                AND vc_number IS NOT NULL
            """)
            self._cache['commercial_unique_vice_counties'] = result[0]['vc_count'] if result else 0

            # =============================================
            # MONTHLY SPECIES COUNTS (unique species per month, all time)
            # =============================================
            monthly_species_query = f"""
                SELECT
                    CAST(strftime('%m', date) AS INTEGER) as month,
                    COUNT(DISTINCT species_name) as species_count
                FROM observations
                WHERE date IS NOT NULL
                AND species_name IS NOT NULL AND species_name != ''
                {exclusion}
                GROUP BY month
                ORDER BY month
            """
            ms_result = self._db.execute_main(monthly_species_query)
            monthly_species_data = {r['month']: r['species_count'] for r in ms_result} if ms_result else {}
            self._cache['monthly_species_counts'] = [monthly_species_data.get(m, 0) for m in range(1, 13)]
            self._cache['personal_monthly_species_counts'] = [personal_monthly_species.get(m, 0) for m in range(1, 13)]

            # =============================================
            # YEARLY STATS
            # =============================================
            yearly_query = f"""
                SELECT 
                    strftime('%Y', date) as year,
                    COUNT(*) as records,
                    COUNT(DISTINCT species_tvk) as species,
                    COUNT(CASE WHEN record_type = 'Commercial' THEN 1 END) as commercial_records,
                    COUNT(DISTINCT CASE WHEN record_type = 'Commercial' THEN species_tvk END) as commercial_species,
                    COUNT(CASE WHEN record_type = 'Personal' THEN 1 END) as personal_records,
                    COUNT(DISTINCT CASE WHEN record_type = 'Personal' THEN species_tvk END) as personal_species
                FROM observations
                WHERE date IS NOT NULL
                AND species_tvk IS NOT NULL
                {exclusion}
                GROUP BY year
                ORDER BY year DESC
            """
            result = self._db.execute_main(yearly_query)
            
            # Calculate new species per year
            all_species_query = f"""
                SELECT strftime('%Y', date) as year, species_tvk, record_type
                FROM observations
                WHERE date IS NOT NULL AND species_tvk IS NOT NULL
                {exclusion}
                ORDER BY date ASC
            """
            species_result = self._db.execute_main(all_species_query)
            
            # Track first year for each species (all and commercial)
            all_first_year = {}
            commercial_first_year = {}
            personal_first_year = {}
            for r in (species_result or []):
                tvk = r['species_tvk']
                year = r['year']
                if tvk not in all_first_year:
                    all_first_year[tvk] = year
                if r['record_type'] == 'Commercial' and tvk not in commercial_first_year:
                    commercial_first_year[tvk] = year
                if r['record_type'] == 'Personal' and tvk not in personal_first_year:
                    personal_first_year[tvk] = year
            
            # Count new species per year
            new_by_year = {}
            commercial_new_by_year = {}
            personal_new_by_year = {}
            for tvk, year in all_first_year.items():
                new_by_year[year] = new_by_year.get(year, 0) + 1
            for tvk, year in commercial_first_year.items():
                commercial_new_by_year[year] = commercial_new_by_year.get(year, 0) + 1
            for tvk, year in personal_first_year.items():
                personal_new_by_year[year] = personal_new_by_year.get(year, 0) + 1
            
            yearly_data = {}
            commercial_yearly_data = {}
            personal_yearly_data = {}
            if result:
                for r in result:
                    year = int(r['year'])
                    yearly_data[year] = {
                        'species': r['species'],
                        'records': r['records'],
                        'newSpecies': new_by_year.get(r['year'], 0)
                    }
                    if r['commercial_records'] > 0:
                        commercial_yearly_data[year] = {
                            'species': r['commercial_species'],
                            'records': r['commercial_records'],
                            'newSpecies': commercial_new_by_year.get(r['year'], 0)
                        }
                    if r['personal_records'] > 0:
                        personal_yearly_data[year] = {
                            'species': r['personal_species'],
                            'records': r['personal_records'],
                            'newSpecies': personal_new_by_year.get(r['year'], 0)
                        }
            
            self._cache['yearly_stats'] = yearly_data
            self._cache['commercial_yearly_stats'] = commercial_yearly_data
            self._cache['personal_yearly_stats'] = personal_yearly_data

            # =============================================
            # ACCUMULATION CURVE
            # =============================================
            accumulation_by_year = {}
            cumulative = 0
            for year in sorted(set(all_first_year.values())):
                cumulative += new_by_year.get(year, 0)
                accumulation_by_year[int(year)] = cumulative
            
            self._cache['accumulation_curve'] = [
                {'year': year, 'cumulative': count}
                for year, count in sorted(accumulation_by_year.items())
            ]

            personal_accumulation_by_year = {}
            personal_cumulative = 0
            for year in sorted(set(personal_first_year.values())):
                personal_cumulative += personal_new_by_year.get(year, 0)
                personal_accumulation_by_year[int(year)] = personal_cumulative
            self._cache['personal_accumulation_curve'] = [
                {'year': year, 'cumulative': count}
                for year, count in sorted(personal_accumulation_by_year.items())
            ]
            
            # Commercial accumulation
            commercial_accumulation = {}
            cumulative = 0
            for year in sorted(set(commercial_first_year.values())):
                cumulative += commercial_new_by_year.get(year, 0)
                commercial_accumulation[int(year)] = cumulative
            
            self._cache['commercial_accumulation_curve'] = [
                {'year': year, 'cumulative': count}
                for year, count in sorted(commercial_accumulation.items())
            ]

            # =============================================
            # RECENT NEW SPECIES (unique per species)
            # =============================================
            recent_query = f"""
                WITH first_records AS (
                    SELECT 
                        species_tvk,
                        MIN(date) as first_date
                    FROM observations
                    WHERE species_tvk IS NOT NULL AND date IS NOT NULL
                    {exclusion}
                    GROUP BY species_tvk
                )
                SELECT 
                    o.species_name,
                    o.date,
                    o.site_name,
                    o.grid_ref
                FROM observations o
                INNER JOIN first_records f 
                    ON o.species_tvk = f.species_tvk 
                    AND o.date = f.first_date
                WHERE o.species_tvk IS NOT NULL
                {exclusion}
                GROUP BY o.species_tvk
                ORDER BY o.date DESC
                LIMIT 10
            """
            result = self._db.execute_main(recent_query)
            self._cache['recent_new_species'] = [
                {
                    'species': r['species_name'],
                    'date': r['date'] or '',
                    'location': r['site_name'] or r['grid_ref'] or ''
                }
                for r in result
            ] if result else []

            # Commercial recent new species
            commercial_recent_query = f"""
                WITH first_records AS (
                    SELECT 
                        species_tvk,
                        MIN(date) as first_date
                    FROM observations
                    WHERE species_tvk IS NOT NULL AND date IS NOT NULL
                    AND record_type = 'Commercial'
                    {exclusion}
                    GROUP BY species_tvk
                )
                SELECT 
                    o.species_name,
                    o.date,
                    o.site_name,
                    o.grid_ref
                FROM observations o
                INNER JOIN first_records f 
                    ON o.species_tvk = f.species_tvk 
                    AND o.date = f.first_date
                WHERE o.species_tvk IS NOT NULL
                AND o.record_type = 'Commercial'
                {exclusion}
                GROUP BY o.species_tvk
                ORDER BY o.date DESC
                LIMIT 10
            """
            result = self._db.execute_main(commercial_recent_query)
            self._cache['commercial_recent_new_species'] = [
                {
                    'species': r['species_name'],
                    'date': r['date'] or '',
                    'location': r['site_name'] or r['grid_ref'] or ''
                }
                for r in result
            ] if result else []

            # Personal recent new species
            personal_recent_query = f"""
                WITH first_records AS (
                    SELECT
                        species_tvk,
                        MIN(date) as first_date
                    FROM observations
                    WHERE species_tvk IS NOT NULL AND date IS NOT NULL
                    AND record_type = 'Personal'
                    {exclusion}
                    GROUP BY species_tvk
                )
                SELECT
                    o.species_name,
                    o.date,
                    o.site_name,
                    o.grid_ref
                FROM observations o
                INNER JOIN first_records f
                    ON o.species_tvk = f.species_tvk
                    AND o.date = f.first_date
                WHERE o.species_tvk IS NOT NULL
                AND o.record_type = 'Personal'
                {exclusion}
                GROUP BY o.species_tvk
                ORDER BY o.date DESC
                LIMIT 10
            """
            result = self._db.execute_main(personal_recent_query)
            self._cache['personal_recent_new_species'] = [
                {
                    'species': r['species_name'],
                    'date': r['date'] or '',
                    'location': r['site_name'] or r['grid_ref'] or ''
                }
                for r in result
            ] if result else []

            # =============================================
            # UNIQUE VICE COUNTIES
            # =============================================
            vc_query = """
                SELECT COUNT(DISTINCT vc_number) as count
                FROM observations
                WHERE vc_number IS NOT NULL
            """
            result = self._db.execute_main(vc_query)
            self._cache['unique_vice_counties'] = result[0]['count'] if result else 0

            result = self._db.execute_main(
                "SELECT COUNT(DISTINCT vc_number) as count FROM observations WHERE vc_number IS NOT NULL AND record_type = 'Personal'"
            )
            self._cache['personal_unique_vice_counties'] = result[0]['count'] if result else 0

            # =============================================
            # ORDER CURVE DATA (per taxon_group accumulation)
            # =============================================
            curve_query = f"""
                SELECT taxon_group, species_name,
                       CAST(SUBSTR(MIN(date), 1, 4) AS INTEGER) as first_year,
                       record_type
                FROM observations
                WHERE taxon_group IS NOT NULL AND taxon_group != ''
                AND species_tvk IS NOT NULL
                AND date IS NOT NULL AND date != ''
                {exclusion}
                GROUP BY species_name, record_type
            """
            curve_result = self._db.execute_main(curve_query)

            # Build per-group data for all, personal, commercial
            def _build_curve_data(rows):
                groups = {}
                for r in rows:
                    tg = r['taxon_group']
                    if tg not in groups:
                        groups[tg] = {}
                    yr = r['first_year']
                    if yr and yr > 0:
                        sp = r['species_name']
                        if sp not in groups[tg]:
                            groups[tg][sp] = yr
                        else:
                            groups[tg][sp] = min(groups[tg][sp], yr)
                # Convert to {taxon_group: {'species_count': N, 'yearly_new': {year: count}}}
                result = {}
                for tg, species_years in groups.items():
                    yearly_new = {}
                    for sp, yr in species_years.items():
                        yearly_new[yr] = yearly_new.get(yr, 0) + 1
                    result[tg] = {
                        'species_count': len(species_years),
                        'yearly_new': yearly_new
                    }
                return result

            all_curve_rows = curve_result or []
            personal_curve_rows = [r for r in all_curve_rows if r['record_type'] == 'Personal']
            commercial_curve_rows = [r for r in all_curve_rows if r['record_type'] == 'Commercial']

            self._cache['order_curve_raw'] = _build_curve_data(all_curve_rows)
            self._cache['personal_order_curve_raw'] = _build_curve_data(personal_curve_rows)
            self._cache['commercial_order_curve_raw'] = _build_curve_data(commercial_curve_rows)

            self._valid = True
            self._last_refresh = datetime.now()

        except Exception as e:
            print(f"[ObservationStatsService] Error refreshing stats: {e}")
            import traceback
            traceback.print_exc()
            self._cache = {}


# Module-level singleton access
_service_instance: Optional[ObservationStatsService] = None


def get_observation_stats() -> Dict[str, Any]:
    """Get all observation stats as a dictionary."""
    global _service_instance
    if _service_instance is None:
        _service_instance = ObservationStatsService()
    
    # Auto-initialize with database if not already done
    if _service_instance._db is None:
        from ..models.database import get_database
        _service_instance.initialize(get_database())
    
    return _service_instance.get_all()


def get_observation_stats_service() -> ObservationStatsService:
    """Get the singleton ObservationStatsService instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = ObservationStatsService()
    return _service_instance


def invalidate_observation_stats():
    """Invalidate the stats cache (call after data changes)."""
    global _service_instance
    if _service_instance is not None:
        _service_instance.invalidate()
