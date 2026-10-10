"""
Recording Scheme Repository for Observatum V2.

Provides clean data access layer for recording scheme records.
Used for Longhorn Beetle Recording Scheme data management.

Usage:
    from src.repositories import RecordingSchemeRepository
    
    repo = RecordingSchemeRepository()
    
    # Get records
    records = repo.search(species_name="Rhagium")
    
    # Stats
    stats = repo.get_quick_stats()
    county_stats = repo.get_county_stats()
"""

import sqlite3
from pathlib import Path
from datetime import datetime, date
from typing import List, Dict, Any, Optional
import paths

# Try to import from config
try:
    from src.core.config import get_db_path  # noqa: F401  (availability check / re-export)
    USE_CONFIG = True
except ImportError:
    USE_CONFIG = False


def _find_data_dir() -> Path:
    """Find the data directory when config is not available."""
    this_file = Path(__file__).resolve()
    project_root = this_file.parent.parent.parent
    return project_root / "data"


class RecordingSchemeRepository:
    """
    Repository for recording scheme data access.
    
    Provides a clean interface for all recording scheme database operations,
    abstracting away raw SQL from the rest of the application.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize repository.
        
        Args:
            db_path: Path to observatum.db. If None, uses config or default.
        """
        if db_path:
            self._db_path = db_path
        else:
            self._db_path = str(paths.OBSERVATUM_DB)
    
    # =========================================================================
    # CONNECTION MANAGEMENT
    # =========================================================================
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _execute(self, query: str, params: tuple = ()) -> List[sqlite3.Row]:
        """Execute a query and return all results."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()
        finally:
            conn.close()
    
    def _execute_write(self, query: str, params: tuple = ()) -> int:
        """Execute a write query and return lastrowid or rowcount."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.lastrowid if cursor.lastrowid else cursor.rowcount
        finally:
            conn.close()
    
    # =========================================================================
    # SEARCH & FILTERING
    # =========================================================================
    
    def search(
        self,
        species_name: Optional[str] = None,
        species_tvk: Optional[str] = None,
        common_name: Optional[str] = None,
        subfamily: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        site_name: Optional[str] = None,
        grid_ref: Optional[str] = None,
        vc_number: Optional[int] = None,
        recorder: Optional[str] = None,
        determiner: Optional[str] = None,
        source: Optional[str] = None,
        verification_status: Optional[str] = None,
        limit: int = 10000,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Search recording scheme records with filters.
        
        All text searches are case-insensitive partial matches.
        
        Returns:
            List of matching record dicts
        """
        conditions = []
        params = []
        
        if species_name:   # by TVK through the shared species search (10 Oct 2026)
            from shared.species_filter import sql_for_table
            clause, sp_params = sql_for_table(species_name, self._execute, "recording_scheme")
            conditions.append(clause)
            params.extend(sp_params)
        
        if species_tvk:
            conditions.append("species_tvk = ?")
            params.append(species_tvk)
        
        if common_name:
            conditions.append("common_name LIKE ?")
            params.append(f"%{common_name}%")
        
        if subfamily:
            conditions.append("subfamily = ?")
            params.append(subfamily)
        
        if date_from:
            conditions.append("date >= ?")
            params.append(date_from)
        
        if date_to:
            conditions.append("date <= ?")
            params.append(date_to)
        
        if site_name:
            conditions.append("site_name LIKE ?")
            params.append(f"%{site_name}%")
        
        if grid_ref:
            conditions.append("grid_ref LIKE ?")
            params.append(f"{grid_ref}%")
        
        if vc_number is not None:
            conditions.append("vc_number = ?")
            params.append(vc_number)
        
        if recorder:
            conditions.append("recorder LIKE ?")
            params.append(f"%{recorder}%")
        
        if determiner:
            conditions.append("determiner LIKE ?")
            params.append(f"%{determiner}%")
        
        if source:
            conditions.append("LOWER(source) = ?")
            params.append(source.lower())
        
        if verification_status:
            conditions.append("verification_status = ?")
            params.append(verification_status)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        query = f"""
            SELECT * FROM recording_scheme
            WHERE {where_clause}
            ORDER BY date DESC
            LIMIT ? OFFSET ?
        """
        
        params.extend([limit, offset])
        rows = self._execute(query, tuple(params))
        return [self._row_to_dict(row) for row in rows]
    
    def get_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        """Get a single record by ID."""
        rows = self._execute(
            "SELECT * FROM recording_scheme WHERE id = ?",
            (record_id,)
        )
        return self._row_to_dict(rows[0]) if rows else None
    
    # =========================================================================
    # COUNT METHODS
    # =========================================================================
    
    def count_all(self) -> int:
        """Count total records."""
        rows = self._execute("SELECT COUNT(*) as count FROM recording_scheme")
        return rows[0]['count'] if rows else 0
    
    def count_unique_species(self) -> int:
        """Count unique species."""
        rows = self._execute("""
            SELECT COUNT(DISTINCT species_tvk) as count
            FROM recording_scheme
            WHERE species_tvk IS NOT NULL
        """)
        return rows[0]['count'] if rows else 0
    
    def count_by_source(self) -> Dict[str, int]:
        """Get record counts grouped by source."""
        rows = self._execute("""
            SELECT source, COUNT(*) as count
            FROM recording_scheme
            WHERE source IS NOT NULL
            GROUP BY source
            ORDER BY count DESC
        """)
        return {row['source']: row['count'] for row in rows}
    
    def count_by_subfamily(self) -> Dict[str, int]:
        """Get record counts grouped by subfamily."""
        rows = self._execute("""
            SELECT subfamily, COUNT(*) as count
            FROM recording_scheme
            WHERE subfamily IS NOT NULL
            GROUP BY subfamily
            ORDER BY count DESC
        """)
        return {row['subfamily']: row['count'] for row in rows}
    
    def count_by_verification_status(self) -> Dict[str, int]:
        """Get record counts grouped by verification status."""
        rows = self._execute("""
            SELECT verification_status, COUNT(*) as count
            FROM recording_scheme
            WHERE verification_status IS NOT NULL
            GROUP BY verification_status
            ORDER BY count DESC
        """)
        return {row['verification_status']: row['count'] for row in rows}
    
    # =========================================================================
    # STATISTICS
    # =========================================================================
    
    def get_quick_stats(self) -> Dict[str, Any]:
        """
        Get quick statistics for the recording scheme.
        
        Returns:
            Dict with total_records, unique_species, sources breakdown, etc.
        """
        stats = {}
        
        # Total records
        stats['total_records'] = self.count_all()
        
        # Unique species
        stats['unique_species'] = self.count_unique_species()
        
        # Source breakdown
        stats['by_source'] = self.count_by_source()
        
        # Verification status breakdown
        stats['by_verification'] = self.count_by_verification_status()
        
        # This year stats
        current_year = date.today().year
        rows = self._execute("""
            SELECT COUNT(*) as count FROM recording_scheme
            WHERE date LIKE ?
        """, (f"{current_year}%",))
        stats['this_year_records'] = rows[0]['count'] if rows else 0
        
        rows = self._execute("""
            SELECT COUNT(DISTINCT species_tvk) as count FROM recording_scheme
            WHERE date LIKE ? AND species_tvk IS NOT NULL
        """, (f"{current_year}%",))
        stats['this_year_species'] = rows[0]['count'] if rows else 0
        
        # Vice counties covered
        rows = self._execute("""
            SELECT COUNT(DISTINCT vc_number) as count
            FROM recording_scheme
            WHERE vc_number IS NOT NULL
        """)
        stats['vice_counties_covered'] = rows[0]['count'] if rows else 0
        
        return stats
    
    def get_county_stats(self) -> List[Dict[str, Any]]:
        """
        Get statistics grouped by vice county.
        
        Returns:
            List of dicts with vc_number, name, records, species, last_record
        """
        rows = self._execute("""
            SELECT 
                vc_number,
                vice_county,
                COUNT(*) as records,
                COUNT(DISTINCT species_tvk) as species,
                MAX(date) as last_record
            FROM recording_scheme
            WHERE vc_number IS NOT NULL
            GROUP BY vc_number
            ORDER BY vc_number
        """)
        return [
            {
                'vc_number': row['vc_number'],
                'name': row['vice_county'] or f"VC{row['vc_number']}",
                'records': row['records'],
                'species': row['species'],
                'last_record': row['last_record'] or ''
            }
            for row in rows
        ]
    
    def get_species_list(self) -> List[Dict[str, Any]]:
        """
        Get list of all species with record counts.
        
        Returns:
            List of dicts with species_name, common_name, species_tvk, count
        """
        rows = self._execute("""
            SELECT 
                species_name,
                common_name,
                species_tvk,
                subfamily,
                COUNT(*) as record_count,
                MIN(date) as first_record,
                MAX(date) as last_record
            FROM recording_scheme
            WHERE species_name IS NOT NULL
            GROUP BY species_tvk
            ORDER BY species_name
        """)
        return [
            {
                'species_name': row['species_name'],
                'common_name': row['common_name'],
                'species_tvk': row['species_tvk'],
                'subfamily': row['subfamily'],
                'record_count': row['record_count'],
                'first_record': row['first_record'],
                'last_record': row['last_record']
            }
            for row in rows
        ]
    
    # =========================================================================
    # DISTINCT VALUES (for filter dropdowns)
    # =========================================================================
    
    def get_distinct_values(self, column: str) -> List[str]:
        """
        Get distinct values for a column (for filter dropdowns).
        
        Args:
            column: Column name (validated against whitelist)
            
        Returns:
            List of distinct values
        """
        valid_columns = {
            'subfamily', 'source', 'verification_status', 'recorder',
            'determiner', 'vice_county'
        }
        
        if column not in valid_columns:
            return []
        
        rows = self._execute(f"""
            SELECT DISTINCT {column}
            FROM recording_scheme
            WHERE {column} IS NOT NULL AND {column} != ''
            ORDER BY {column}
        """)
        return [row[column] for row in rows]
    
    def get_distinct_subfamilies(self) -> List[str]:
        """Get distinct subfamily values."""
        return self.get_distinct_values('subfamily')
    
    def get_distinct_sources(self) -> List[str]:
        """Get distinct source values."""
        return self.get_distinct_values('source')
    
    def get_distinct_verification_statuses(self) -> List[str]:
        """Get distinct verification status values."""
        return self.get_distinct_values('verification_status')
    
    # =========================================================================
    # CRUD OPERATIONS
    # =========================================================================
    
    def create(self, data: Dict[str, Any]) -> int:
        """
        Create a new recording scheme record.
        
        Args:
            data: Dict with record fields
            
        Returns:
            The new record ID
        """
        now = datetime.now().isoformat()
        
        allowed_fields = {
            'species_name', 'species_tvk', 'common_name', 'order_name',
            'family', 'subfamily', 'date', 'grid_ref', 'vice_county',
            'vc_number', 'site_name', 'recorder', 'determiner', 'source',
            'verification_status'
        }
        
        fields = []
        values = []
        placeholders = []
        
        for field in allowed_fields:
            if field in data:
                fields.append(field)
                values.append(data[field])
                placeholders.append('?')
        
        fields.extend(['created_at', 'updated_at'])
        values.extend([now, now])
        placeholders.extend(['?', '?'])
        
        query = f"""
            INSERT INTO recording_scheme ({', '.join(fields)})
            VALUES ({', '.join(placeholders)})
        """
        
        return self._execute_write(query, tuple(values))
    
    def update(self, record_id: int, data: Dict[str, Any]) -> bool:
        """
        Update an existing record.
        
        Args:
            record_id: The record ID to update
            data: Dict with fields to update
            
        Returns:
            True if updated, False if not found
        """
        now = datetime.now().isoformat()
        
        allowed_fields = {
            'species_name', 'species_tvk', 'common_name', 'order_name',
            'family', 'subfamily', 'date', 'grid_ref', 'vice_county',
            'vc_number', 'site_name', 'recorder', 'determiner', 'source',
            'verification_status'
        }
        
        set_parts = []
        values = []
        
        for field in allowed_fields:
            if field in data:
                set_parts.append(f"{field} = ?")
                values.append(data[field])
        
        if not set_parts:
            return False
        
        set_parts.append("updated_at = ?")
        values.append(now)
        values.append(record_id)
        
        query = f"UPDATE recording_scheme SET {', '.join(set_parts)} WHERE id = ?"
        result = self._execute_write(query, tuple(values))
        return result > 0
    
    def delete(self, record_id: int) -> bool:
        """
        Delete a record by ID.
        
        Args:
            record_id: The record ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        result = self._execute_write(
            "DELETE FROM recording_scheme WHERE id = ?",
            (record_id,)
        )
        return result > 0
    
    # =========================================================================
    # HELPERS
    # =========================================================================
    
    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a database row to a dict with table widget format."""
        return {
            'id': row['id'],
            'species_name': row['species_name'],
            'species': row['species_name'],
            'species_tvk': row['species_tvk'],
            'common_name': row['common_name'] or '',
            'common': row['common_name'] or '',
            'order_name': row['order_name'] if 'order_name' in row.keys() else '',
            'family': row['family'] if 'family' in row.keys() else '',
            'subfamily': row['subfamily'] or '',
            'date': row['date'] or '',
            'site_name': row['site_name'] or '',
            'location': row['site_name'] or '',
            'grid_ref': row['grid_ref'] or '',
            'gridRef': row['grid_ref'] or '',
            'vice_county': row['vice_county'] or '',
            'vc_number': row['vc_number'] or '',
            'vc': row['vc_number'] or '',
            'recorder': row['recorder'] or '',
            'determiner': row['determiner'] or '',
            'source': row['source'] or '',
            'verification_status': row['verification_status'] or '',
            'verification': row['verification_status'] or '',
        }
