"""
Observation Repository for Observatum V2.

Handles all database operations for the observations table.
This is the single source of truth for observation queries.

Usage:
    from src.repositories import ObservationRepository
    
    repo = ObservationRepository()
    
    # Find observations
    obs = repo.find_by_id(123)
    recent = repo.find_recent(limit=10)
    
    # Search with filters
    results = repo.search(species_name="Rutpela", record_type="Personal")
    
    # Stats
    stats = repo.get_quick_stats()
    by_order = repo.count_species_by_order()
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass

from .base import BaseRepository


# =============================================================================
# DATA CLASSES
# =============================================================================
# Observation is imported from models - re-exported here for backwards compatibility
try:
    from ..models.observation import Observation
except ImportError:
    Observation = None  # Will be resolved at runtime


# {row column names: the Observation fields among them} -- see _row_to_observation
_FIELDS_FOR_KEYS: dict = {}

@dataclass

class ObservationSearchFilters:
    """Search filter parameters for observations."""
    species_name: Optional[str] = None
    species_tvk: Optional[str] = None
    common_name: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    grid_ref: Optional[str] = None
    site_name: Optional[str] = None
    vc_number: Optional[int] = None
    recorder: Optional[str] = None
    determiner: Optional[str] = None
    verification_status: Optional[str] = None
    record_type: Optional[str] = None
    order_name: Optional[str] = None
    family: Optional[str] = None
    method: Optional[str] = None
    embargo_status: Optional[str] = None
    project_name: Optional[str] = None
    client: Optional[str] = None
    limit: int = 100
    offset: int = 0


# =============================================================================
# REPOSITORY
# =============================================================================

class ObservationRepository(BaseRepository):
    """
    Repository for observation database operations.
    
    All SQL queries for observations live here.
    """
    
    TABLE = "observations"
    PRIMARY_KEY = "id"
    
    # Valid columns for ORDER BY (prevents SQL injection)
    VALID_ORDER_COLUMNS = {
        'id', 'species_name', 'common_name', 'date', 'grid_ref', 
        'site_name', 'recorder', 'created_at', 'updated_at', 
        'record_type', 'order_name', 'family', 'vc_number'
    }
    
    # ==========================================================================
    # CREATE
    # ==========================================================================
    
    # ==========================================================================
    # READ - Single Record
    # ==========================================================================
    
    def find_by_id(self, observation_id: int) -> Optional[Observation]:
        """
        Find an observation by ID.
        
        Args:
            observation_id: The record ID
            
        Returns:
            Observation or None if not found
        """
        row = super().find_by_id(observation_id)
        return self._row_to_observation(row) if row else None
    
    def find_by_irecord_id(self, irecord_id: int) -> Optional[Observation]:
        """
        Find an observation by iRecord ID.
        
        Args:
            irecord_id: The iRecord ID
            
        Returns:
            Observation or None if not found
        """
        results = self._execute(
            "SELECT * FROM observations WHERE irecord_id = ?",
            (irecord_id,)
        )
        return self._row_to_observation(results[0]) if results else None
    
    def find_duplicate(
        self, 
        species_name: str, 
        date: str, 
        grid_ref: str
    ) -> Optional[int]:
        """
        Check if a duplicate observation exists.
        
        Args:
            species_name: Species name to match
            date: Date to match (ISO format)
            grid_ref: Grid reference to match
            
        Returns:
            ID of existing record, or None if no duplicate
        """
        query = """
            SELECT id FROM observations 
            WHERE species_name = ? AND date = ? AND grid_ref = ?
            LIMIT 1
        """
        results = self._execute(query, (species_name, date, grid_ref))
        return results[0][0] if results else None
    
    # ==========================================================================
    # READ - Multiple Records
    # ==========================================================================
    
    def find_all(
        self, 
        limit: int = 100, 
        offset: int = 0,
        order_by: str = "date DESC"
    ) -> List[Observation]:
        """
        Find all observations with pagination.
        
        Args:
            limit: Maximum records to return
            offset: Records to skip
            order_by: ORDER BY clause
            
        Returns:
            List of Observations
        """
        order_by = self._validate_order_by(order_by)
        
        query = f"""
            SELECT * FROM observations
            ORDER BY {order_by}
            LIMIT ? OFFSET ?
        """
        
        results = self._execute(query, (limit, offset))
        return [self._row_to_observation(row) for row in results]
    
    def search(self, filters: ObservationSearchFilters = None, **kwargs) -> List[Observation]:
        """
        Search observations with filters.
        
        Args:
            filters: ObservationSearchFilters object
            **kwargs: Alternative to filters - passed as individual parameters
            
        Returns:
            List of matching Observations
        """
        if filters is None:
            filters = ObservationSearchFilters(**kwargs)
        
        conditions = []
        params = []
        
        # Text search fields (LIKE %value%)
        if filters.species_name:   # by TVK through the shared species search (10 Oct 2026)
            from shared.species_filter import sql_for_table
            clause, sp_params = sql_for_table(filters.species_name, self._execute, "observations")
            conditions.append(clause)
            params.extend(sp_params)
        
        if filters.site_name:
            conditions.append("site_name LIKE ?")
            params.append(f"%{filters.site_name}%")
        
        if filters.recorder:
            conditions.append("recorder LIKE ?")
            params.append(f"%{filters.recorder}%")
        
        # Prefix search (LIKE value%)
        if filters.grid_ref:
            conditions.append("grid_ref LIKE ?")
            params.append(f"{filters.grid_ref}%")
        
        # Exact match fields
        exact_fields = {
            'species_tvk': filters.species_tvk,
            'vc_number': filters.vc_number,
            'verification_status': filters.verification_status,
            'record_type': filters.record_type,
            'order_name': filters.order_name,
            'family': filters.family,
            'method': filters.method,
            'embargo_status': filters.embargo_status,
            'project_name': filters.project_name,
            'client': filters.client,
        }
        
        for field, value in exact_fields.items():
            if value is not None:
                conditions.append(f"{field} = ?")
                params.append(value)
        
        # Date range
        if filters.date_from:
            conditions.append("date >= ?")
            params.append(filters.date_from)
        
        if filters.date_to:
            conditions.append("date <= ?")
            params.append(filters.date_to)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        query = f"""
            SELECT * FROM observations
            WHERE {where_clause}
            ORDER BY date DESC
            LIMIT ? OFFSET ?
        """
        
        params.extend([filters.limit, filters.offset])
        results = self._execute(query, tuple(params))
        return [self._row_to_observation(row) for row in results]
    
    def find_by_species(self, species_tvk: str, limit: int = 100) -> List[Observation]:
        """
        Find all observations for a species.
        
        Args:
            species_tvk: Species TVK
            limit: Maximum records
            
        Returns:
            List of Observations
        """
        query = """
            SELECT * FROM observations
            WHERE species_tvk = ?
            ORDER BY date DESC
            LIMIT ?
        """
        results = self._execute(query, (species_tvk, limit))
        return [self._row_to_observation(row) for row in results]
    
    def find_by_grid_ref_prefix(self, grid_prefix: str, limit: int = 1000) -> List[Observation]:
        """
        Find observations within a grid square.
        
        Args:
            grid_prefix: Grid reference prefix (e.g., "TQ1" or "TQ12")
            limit: Maximum records
            
        Returns:
            List of Observations
        """
        query = """
            SELECT * FROM observations
            WHERE grid_ref LIKE ?
            ORDER BY date DESC
            LIMIT ?
        """
        results = self._execute(query, (f"{grid_prefix}%", limit))
        return [self._row_to_observation(row) for row in results]
    
    def find_unsynced(self, limit: int = 100) -> List[Observation]:
        """
        Find observations that haven't been synced to iRecord.
        
        Args:
            limit: Maximum records
            
        Returns:
            List of Observations without irecord_id
        """
        query = """
            SELECT * FROM observations
            WHERE irecord_id IS NULL
            ORDER BY date DESC
            LIMIT ?
        """
        results = self._execute(query, (limit,))
        return [self._row_to_observation(row) for row in results]
    
    def find_by_vice_county(self, vc_number: int, limit: int = 1000) -> List[Observation]:
        """
        Find observations in a vice county.
        
        Args:
            vc_number: Vice county number
            limit: Maximum records
            
        Returns:
            List of Observations
        """
        query = """
            SELECT * FROM observations
            WHERE vc_number = ?
            ORDER BY date DESC
            LIMIT ?
        """
        results = self._execute(query, (vc_number, limit))
        return [self._row_to_observation(row) for row in results]
    
    # ==========================================================================
    # READ - Recent/New Species
    # ==========================================================================
    
    def find_recent_species(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get most recently observed species (latest observation per species).
        
        Args:
            limit: Number of species to return
            
        Returns:
            List of dicts with species info
        """
        query = """
            SELECT
                o.species_name,
                o.common_name,
                o.species_tvk,
                o.date,
                o.site_name,
                o.grid_ref
            FROM observations o
            INNER JOIN (
                SELECT species_tvk, MAX(date) as max_date
                FROM observations
                WHERE species_tvk IS NOT NULL
                GROUP BY species_tvk
            ) latest ON o.species_tvk = latest.species_tvk
                    AND o.date = latest.max_date
            ORDER BY o.date DESC
            LIMIT ?
        """
        
        results = self._execute(query, (limit,))
        return [
            {
                'species_name': row['species_name'],
                'common_name': row['common_name'],
                'species_tvk': row['species_tvk'],
                'date': row['date'],
                'site_name': row['site_name'],
                'grid_ref': row['grid_ref']
            }
            for row in results
        ]
    
    def find_new_species(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get most recent first records (species recorded for first time).
        
        Args:
            limit: Number of species to return
            
        Returns:
            List of dicts with species info and first_date
        """
        query = """
            SELECT
                species_name,
                common_name,
                species_tvk,
                MIN(date) as first_date,
                MIN(id) as first_id
            FROM observations
            WHERE species_tvk IS NOT NULL
            GROUP BY species_tvk
            ORDER BY first_date DESC, first_id DESC
            LIMIT ?
        """
        
        results = self._execute(query, (limit,))
        return [
            {
                'species_name': row['species_name'],
                'common_name': row['common_name'],
                'species_tvk': row['species_tvk'],
                'first_date': row['first_date']
            }
            for row in results
        ]
    
    # ==========================================================================
    # UPDATE
    # ==========================================================================
    
    # ==========================================================================
    # DELETE
    # ==========================================================================
    
    def delete(self, observation_id: int) -> bool:
        """
        Delete an observation by ID.
        
        Args:
            observation_id: Record ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        return self.delete_by_id(observation_id)
    
    def delete_many(self, observation_ids: List[int]) -> int:
        """
        Delete multiple observations.
        
        Args:
            observation_ids: List of IDs to delete
            
        Returns:
            Number of records deleted
        """
        if not observation_ids:
            return 0
        
        placeholders = ",".join(["?" for _ in observation_ids])
        query = f"DELETE FROM observations WHERE id IN ({placeholders})"
        return self._execute_write(query, tuple(observation_ids))
    
    # ==========================================================================
    # COUNTS
    # ==========================================================================
    
    def count_all(self) -> int:
        """Count all observations."""
        return self.count()
    
    _cached_exclusion_setting = None  # Class-level cache
    
    def _get_species_exclusion_clause(self, force_refresh: bool = False) -> str:
        """Get SQL clause to exclude incomplete species based on settings."""
        if force_refresh or ObservationRepository._cached_exclusion_setting is None:
            from PySide6.QtCore import QSettings
            settings = QSettings()
            ObservationRepository._cached_exclusion_setting = settings.value("display/exclude_incomplete_species", True, type=bool)
        
        if ObservationRepository._cached_exclusion_setting:
            return """ AND species_name LIKE '% %' AND species_name NOT LIKE '%agg.%' AND species_name NOT LIKE '%agg %' AND species_name NOT LIKE '% agg' AND species_name NOT LIKE '%s.l.%' AND species_name NOT LIKE '%sensu lato%'"""
        return ""
    
    @classmethod
    def refresh_exclusion_setting(cls):
        """Call this when settings change to refresh the cached value."""
        cls._cached_exclusion_setting = None

    def count_by_record_type(self, record_type: str) -> int:
        """Count observations by record type."""
        return self.count("record_type = ?", (record_type,))
    
    def count_by_species(self, species_tvk: str) -> int:
        """Count observations for a species."""
        return self.count("species_tvk = ?", (species_tvk,))
    
    def count_unique_species(self, record_type: str = None, exclude_incomplete: bool = None) -> int:
        """
        Count distinct species.
        
        Args:
            record_type: Optional filter for Personal/Commercial
            
        Returns:
            Number of unique species
        """
        # Get setting if not explicitly provided
        if exclude_incomplete is None:
            from PySide6.QtCore import QSettings
            settings = QSettings()
            exclude_incomplete = settings.value("display/exclude_incomplete_species", True, type=bool)
        
        # Build exclusion clause
        exclusion = ""
        if exclude_incomplete:
            exclusion = """ AND species_name LIKE '% %' AND species_name NOT LIKE '%agg.%' AND species_name NOT LIKE '%agg %' AND species_name NOT LIKE '% agg' AND species_name NOT LIKE '%s.l.%' AND species_name NOT LIKE '%sensu lato%'"""
        
        if record_type:
            query = f"""
                SELECT COUNT(DISTINCT species_tvk)
                FROM observations
                WHERE species_tvk IS NOT NULL AND record_type = ?
                {exclusion}
            """
            return self._scalar(query, (record_type,), default=0)
        else:
            query = f"""
                SELECT COUNT(DISTINCT species_tvk)
                FROM observations
                WHERE species_tvk IS NOT NULL
                {exclusion}
            """
            return self._scalar(query, default=0)
    
    def count_unique_species_by_year(self, year: int) -> int:
        """Count distinct species for a specific year."""
        exclusion = self._get_species_exclusion_clause()
        query = f"""
            SELECT COUNT(DISTINCT species_tvk)
            FROM observations
            WHERE species_tvk IS NOT NULL
              AND strftime('%Y', date) = ?
              {exclusion}
        """
        return self._scalar(query, (str(year),), default=0)
    
    def count_for_year(self, year: int) -> int:
        """Count observations for a specific year."""
        query = """
            SELECT COUNT(*) FROM observations
            WHERE strftime('%Y', date) = ?
        """
        return self._scalar(query, (str(year),), default=0)
    
    def count_for_month(self, year: int, month: int) -> int:
        """Count observations for a specific month."""
        month_str = f"{year}-{month:02d}"
        query = """
            SELECT COUNT(*) FROM observations
            WHERE strftime('%Y-%m', date) = ?
        """
        return self._scalar(query, (month_str,), default=0)
    
    def count_by_vice_county(self) -> Dict[int, int]:
        """
        Count observations per vice county.
        
        Returns:
            Dict mapping vc_number to count
        """
        query = """
            SELECT vc_number, COUNT(*) as count
            FROM observations
            WHERE vc_number IS NOT NULL
            GROUP BY vc_number
        """
        results = self._execute(query)
        return {row['vc_number']: row['count'] for row in results}
    
    # ==========================================================================
    # STATISTICS
    # ==========================================================================
    
    def get_quick_stats(self) -> Dict[str, Any]:
        """
        Get quick stats for Home tab.
        
        Returns:
            Dict with total_species, total_records, this_year_species,
            this_year_records, last_month_records
        """
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        # Calculate last month
        if current_month == 1:
            last_month = 12
            last_month_year = current_year - 1
        else:
            last_month = current_month - 1
            last_month_year = current_year
        
        last_month_str = f"{last_month_year}-{last_month:02d}"
        
        return {
            'total_species': self.count_unique_species(),
            'total_records': self.count_all(),
            'this_year_species': self.count_unique_species_by_year(current_year),
            'this_year_records': self.count_by_year(current_year),
            'last_month_records': self._scalar(
                "SELECT COUNT(*) FROM observations WHERE strftime('%Y-%m', date) = ?",
                (last_month_str,),
                default=0
            ),
        }
    
    def count_species_by_order(self, record_type: str = None) -> List[Dict[str, Any]]:
        """
        Count species grouped by taxonomic order.
        
        Args:
            record_type: Optional filter for Personal/Commercial
            
        Returns:
            List of {label, value} dicts
        """
        where = "WHERE species_tvk IS NOT NULL AND order_name IS NOT NULL"
        params = []
        
        if record_type:
            where += " AND record_type = ?"
            params.append(record_type)
        
        query = f"""
            SELECT order_name, COUNT(DISTINCT species_tvk) as species_count
            FROM observations
            {where}
            GROUP BY order_name
            ORDER BY species_count DESC
            LIMIT 10
        """
        
        results = self._execute(query, tuple(params) if params else ())
        return [
            {'label': row['order_name'], 'value': row['species_count']}
            for row in results
        ]
    
    def get_top_families(self, limit: int = 5, record_type: str = None) -> List[Dict[str, Any]]:
        """
        Get top families by species count.
        
        Args:
            limit: Number of families
            record_type: Optional filter
            
        Returns:
            List of {family, species, records} dicts
        """
        where = "WHERE species_tvk IS NOT NULL AND family IS NOT NULL"
        params = []
        
        if record_type:
            where += " AND record_type = ?"
            params.append(record_type)
        
        query = f"""
            SELECT 
                family,
                COUNT(DISTINCT species_tvk) as species_count,
                COUNT(*) as record_count
            FROM observations
            {where}
            GROUP BY family
            ORDER BY species_count DESC
            LIMIT ?
        """
        params.append(limit)
        
        results = self._execute(query, tuple(params))
        return [
            {
                'family': row['family'],
                'species': row['species_count'],
                'records': row['record_count']
            }
            for row in results
        ]
    
    def get_monthly_activity(self, year: int = None, record_type: str = None) -> List[int]:
        """
        Get record counts by month.
        
        Args:
            year: Specific year (None for all years combined)
            record_type: Optional filter
            
        Returns:
            List of 12 integers (Jan-Dec counts)
        """
        conditions = []
        params = []
        
        if year:
            conditions.append("strftime('%Y', date) = ?")
            params.append(str(year))
        
        if record_type:
            conditions.append("record_type = ?")
            params.append(record_type)
        
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        
        query = f"""
            SELECT 
                CAST(strftime('%m', date) AS INTEGER) as month,
                COUNT(*) as count
            FROM observations
            {where}
            GROUP BY month
            ORDER BY month
        """
        
        results = self._execute(query, tuple(params) if params else ())
        
        monthly = [0] * 12
        for row in results:
            month_idx = row['month'] - 1
            if 0 <= month_idx < 12:
                monthly[month_idx] = row['count']
        
        return monthly
    
    def get_year_by_year_stats(self, record_type: str = None) -> Dict[int, Dict[str, int]]:
        """
        Get statistics per year.
        
        Args:
            record_type: Optional filter
            
        Returns:
            Dict keyed by year with species, records, newSpecies counts
        """
        where = ""
        params = []
        
        if record_type:
            where = "WHERE record_type = ?"
            params.append(record_type)
        
        # Species and records per year
        query = f"""
            SELECT 
                CAST(strftime('%Y', date) AS INTEGER) as year,
                COUNT(DISTINCT species_tvk) as species_count,
                COUNT(*) as record_count
            FROM observations
            {where}
            GROUP BY year
            ORDER BY year DESC
            LIMIT 10
        """
        
        results = self._execute(query, tuple(params) if params else ())
        
        year_stats = {}
        for row in results:
            year = row['year']
            year_stats[year] = {
                'species': row['species_count'],
                'records': row['record_count'],
                'newSpecies': 0
            }
        
        # Calculate new species per year
        first_seen_query = f"""
            SELECT 
                species_tvk,
                MIN(CAST(strftime('%Y', date) AS INTEGER)) as first_year
            FROM observations
            WHERE species_tvk IS NOT NULL
            {('AND record_type = ?' if record_type else '')}
            GROUP BY species_tvk
        """
        
        first_params = [record_type] if record_type else []
        first_seen = self._execute(first_seen_query, tuple(first_params) if first_params else ())
        
        new_per_year = {}
        for row in first_seen:
            first_year = row['first_year']
            new_per_year[first_year] = new_per_year.get(first_year, 0) + 1
        
        for year in year_stats:
            year_stats[year]['newSpecies'] = new_per_year.get(year, 0)
        
        return year_stats
    
    def get_distinct_tvks(self) -> List[str]:
        """
        Get all distinct TVKs (for search boosting).
        
        Returns:
            List of TVK strings
        """
        query = """
            SELECT DISTINCT species_tvk
            FROM observations
            WHERE species_tvk IS NOT NULL
        """
        results = self._execute(query)
        return [row['species_tvk'] for row in results]
    
    def get_covered_vice_counties(self) -> List[int]:
        """
        Get list of vice counties with at least one observation.
        
        Returns:
            List of vc_numbers
        """
        query = """
            SELECT DISTINCT vc_number
            FROM observations
            WHERE vc_number IS NOT NULL
        """
        results = self._execute(query)
        return [row['vc_number'] for row in results]
    
    # ==========================================================================
    # AGGREGATION METHODS (for stats dashboards)
    # ==========================================================================
    
    def count_by_order(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get species counts grouped by order.
        
        Args:
            limit: Maximum number of orders to return
            
        Returns:
            List of dicts with order_name and count
        """
        rows = self._execute("""
            SELECT order_name, COUNT(DISTINCT species_name) as count
            FROM observations
            WHERE order_name IS NOT NULL AND order_name != ''
            GROUP BY order_name
            ORDER BY count DESC
            LIMIT ?
        """, (limit,))
        return [{'order_name': row['order_name'], 'count': row['count']} for row in rows]

    def count_by_family(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get species/record counts grouped by family.
        
        Args:
            limit: Maximum families to return
            
        Returns:
            List of dicts with family, species_count, record_count
        """
        rows = self._execute("""
            SELECT family, COUNT(DISTINCT species_name) as species_count, COUNT(*) as record_count
            FROM observations
            WHERE family IS NOT NULL AND family != ''
            GROUP BY family
            ORDER BY species_count DESC
            LIMIT ?
        """, (limit,))
        return [{'family': row['family'], 'species_count': row['species_count'], 'record_count': row['record_count']} for row in rows]

    def count_by_month(self, year: Optional[int] = None, month: Optional[int] = None) -> Any:
        """
        Get observation counts by month.
        
        Args:
            year: If provided with month, returns count for that specific month.
            month: If provided with year, returns count for that specific month.
                   If both are None, returns list of 12 monthly totals.
        
        Returns:
            If year and month provided: int count for that month
            If both None: List of 12 integers, one per month (all-time totals)
        """
        # If year and month provided, return count for that specific month
        if year is not None and month is not None:
            month_str = f"{year}-{month:02d}"
            query = """
                SELECT COUNT(*) FROM observations
                WHERE strftime('%Y-%m', date) = ?
            """
            return self._scalar(query, (month_str,), default=0)
        
        # Otherwise return all 12 months totals
        rows = self._execute("""
            SELECT CAST(strftime('%m', date) AS INTEGER) as month, COUNT(*) as count
            FROM observations WHERE date IS NOT NULL
            GROUP BY month ORDER BY month
        """)
        monthly = [0] * 12
        for row in rows:
            m = row['month']
            if m and 1 <= m <= 12:
                monthly[m - 1] = row['count']
        return monthly

    def count_by_year(self, year: Optional[int] = None) -> Any:
        """
        Get yearly statistics or count for a specific year.
        
        Args:
            year: If provided, returns count for that year (int).
                  If None, returns dict of all yearly stats.
        
        Returns:
            If year provided: int count
            If year is None: Dict keyed by year with species, records, newSpecies counts
        """
        # If year is provided, return count for that specific year
        if year is not None:
            query = """
                SELECT COUNT(*) FROM observations
                WHERE strftime('%Y', date) = ?
            """
            return self._scalar(query, (str(year),), default=0)
        
        # Otherwise return full yearly stats
        rows = self._execute("""
            SELECT CAST(strftime('%Y', date) AS INTEGER) as year,
                   COUNT(DISTINCT species_name) as species, COUNT(*) as records
            FROM observations WHERE date IS NOT NULL
            GROUP BY year ORDER BY year DESC LIMIT 10
        """)
        result = {}
        for row in rows:
            yr = row['year']
            if yr:
                result[yr] = {'species': row['species'], 'records': row['records'], 'newSpecies': 0}
        return result

    def get_new_species_first_records(self, limit: int = 10,
                                      record_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get the most recent "first records" - species seen for the first time.
        
        Args:
            limit: Maximum number of species to return
            record_type: 'Personal' or 'Commercial' to count firsts within that data
                only (review OBS-24: the New Species List ignored the toggle); None = all
            
        Returns:
            List of dicts with species info and first record details
        """
        exclusion = self._get_species_exclusion_clause()
        params: list = []
        if record_type:
            exclusion += " AND record_type = ?"
            params.append(record_type)
        params.append(limit)
        query = f"""
            SELECT species_name, common_name, species_tvk, date, site_name, grid_ref
            FROM (
                SELECT 
                    species_name,
                    common_name,
                    species_tvk,
                    date,
                    site_name,
                    grid_ref,
                    ROW_NUMBER() OVER (PARTITION BY species_tvk
                        ORDER BY (date IS NULL OR date = ''), date ASC, id ASC) as rn
                FROM observations
                WHERE species_tvk IS NOT NULL
                  {exclusion}
            )
            WHERE rn = 1
            ORDER BY date DESC
            LIMIT ?
        """
        results = self._execute(query, tuple(params))
        return [
            {
                'species_name': row['species_name'],
                'common_name': row['common_name'],
                'species_tvk': row['species_tvk'],
                'date': row['date'],
                'site_name': row['site_name'],
                'grid_ref': row['grid_ref']
            }
            for row in results
        ]

    # ==========================================================================
    # UTILITIES
    # ==========================================================================
    
    def _validate_order_by(self, order_by: str) -> str:
        """Validate ORDER BY clause to prevent SQL injection."""
        parts = order_by.replace(',', ' ').split()
        for part in parts:
            part_lower = part.lower()
            if part_lower not in self.VALID_ORDER_COLUMNS and part_lower not in ('asc', 'desc'):
                return "date DESC"
        return order_by
    
    def _row_to_observation(self, row):
        """Convert a database row to an Observation object, mapping all dataclass fields."""
        if row is None:
            return None

        from ..models.observation import Observation

        # Get all available column names from the row
        try:
            row_keys = row.keys()
        except AttributeError:
            row_keys = []

        # The Observation fields this row holds, worked out once per set of columns: it
        # was dataclasses.fields() and a search of the key list for every field of every
        # row -- 2.5 of the 3.3 s the Observation tab took to open (speed, 10 Oct 2026)
        key = tuple(row_keys)
        names = _FIELDS_FOR_KEYS.get(key)
        if names is None:
            from dataclasses import fields as dc_fields
            present = set(key)
            names = tuple(f.name for f in dc_fields(Observation) if f.name in present)
            _FIELDS_FOR_KEYS[key] = names

        kwargs = {}
        for name in names:
            try:
                kwargs[name] = row[name]
            except (IndexError, KeyError):
                pass

        return Observation(**kwargs)

