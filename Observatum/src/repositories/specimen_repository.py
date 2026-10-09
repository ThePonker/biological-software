"""
Specimen Repository for Observatum V2.

Provides clean data access layer for specimen records (Insect Collection).
Mirrors ObservationRepository pattern for consistency.

Usage:
    from src.repositories import SpecimenRepository
    
    repo = SpecimenRepository()
    
    # Get specimens
    specimens = repo.get_all(limit=100)
    specimen = repo.get_by_id(123)
    
    # Search
    results = repo.search(species_name="Pterostichus", family="Carabidae")
    
    # Stats
    stats = repo.get_quick_stats()
    count = repo.count_all()
"""

import sqlite3
from pathlib import Path
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Tuple
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
    # src/repositories/specimen_repository.py -> repositories -> src -> project
    project_root = this_file.parent.parent.parent
    return project_root / "data"


class SpecimenRepository:
    """
    Repository for specimen data access.
    
    Provides a clean interface for all specimen database operations,
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
    
    def _execute_many(self, query: str, params_list: List[tuple]) -> int:
        """Execute a query with multiple parameter sets."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()
    
    # =========================================================================
    # BASIC CRUD
    # =========================================================================
    
    def get_by_id(self, specimen_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a single specimen by ID.
        
        Args:
            specimen_id: The specimen ID
            
        Returns:
            Dict with specimen data, or None if not found
        """
        rows = self._execute(
            "SELECT * FROM specimens WHERE id = ?",
            (specimen_id,)
        )
        return dict(rows[0]) if rows else None
    
    def get_all(
        self,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "date_collected DESC"
    ) -> List[Dict[str, Any]]:
        """
        Get all specimens with pagination.
        
        Args:
            limit: Maximum records to return
            offset: Number of records to skip
            order_by: SQL ORDER BY clause
            
        Returns:
            List of specimen dicts
        """
        # Validate order_by to prevent SQL injection
        valid_columns = {
            'id', 'specimen_code', 'species_name', 'date_collected',
            'grid_ref', 'site_name', 'collector', 'family', 'order_name',
            'storage_location', 'created_at', 'updated_at'
        }
        order_parts = order_by.replace(',', ' ').split()
        for part in order_parts:
            if part.lower() not in valid_columns and part.lower() not in ('asc', 'desc'):
                order_by = "date_collected DESC"
                break
        
        rows = self._execute(
            f"SELECT * FROM specimens ORDER BY {order_by} LIMIT ? OFFSET ?",
            (limit, offset)
        )
        return [dict(row) for row in rows]
    
    def create(self, data: Dict[str, Any]) -> int:
        """
        Create a new specimen record.
        
        Args:
            data: Dict with specimen fields
            
        Returns:
            The new specimen ID
        """
        now = datetime.now().isoformat()
        
        # Build field list dynamically based on provided data
        fields = []
        values = []
        placeholders = []
        
        # taxonomic_sort_key and superfamily were absent from this list, so
        # every caller that set them had them silently dropped. The Insect
        # Collection sidebar filters on the sort key, so those specimens became
        # invisible to it -- 244 of them before anyone noticed.
        allowed_fields = {
            'specimen_code', 'species_name', 'species_tvk', 'common_name',
            'order_name', 'family', 'subfamily', 'superfamily',
            'taxonomic_sort_key', 'taxon_group',
            'date_collected', 'grid_ref',
            'vice_county', 'vc_number', 'site_name', 'site_name_local', 'collector', 'determiner',
            'sex', 'preparation_type', 'storage_location', 'drawer_number',
            'condition', 'label_data', 'notes', 'import_notes', 'observation_id'
        }
        
        for field in allowed_fields:
            if field in data:
                fields.append(field)
                values.append(data[field])
                placeholders.append('?')
        
        # Add timestamps
        fields.extend(['created_at', 'updated_at'])
        values.extend([now, now])
        placeholders.extend(['?', '?'])
        
        query = f"""
            INSERT INTO specimens ({', '.join(fields)})
            VALUES ({', '.join(placeholders)})
        """
        
        return self._execute_write(query, tuple(values))
    
    def update(self, specimen_id: int, data: Dict[str, Any]) -> bool:
        """
        Update an existing specimen.
        
        Args:
            specimen_id: The specimen ID to update
            data: Dict with fields to update
            
        Returns:
            True if updated, False if not found
        """
        now = datetime.now().isoformat()
        
        # Build SET clause dynamically
        # Same omission as create(): without these two, correcting a species
        # on an existing specimen would leave a sort key belonging to the old
        # determination, or none at all.
        allowed_fields = {
            'specimen_code', 'species_name', 'species_tvk', 'common_name',
            'order_name', 'family', 'subfamily', 'superfamily',
            'taxonomic_sort_key', 'taxon_group',
            'date_collected', 'grid_ref',
            'vice_county', 'vc_number', 'site_name', 'site_name_local', 'collector', 'determiner',
            'sex', 'preparation_type', 'storage_location', 'drawer_number',
            'condition', 'label_data', 'notes', 'import_notes', 'observation_id'
        }
        
        set_parts = []
        values = []
        
        for field in allowed_fields:
            if field in data:
                set_parts.append(f"{field} = ?")
                values.append(data[field])
        
        if not set_parts:
            return False
        
        # Add updated_at
        set_parts.append("updated_at = ?")
        values.append(now)
        
        # Add WHERE clause parameter
        values.append(specimen_id)
        
        query = f"UPDATE specimens SET {', '.join(set_parts)} WHERE id = ?"
        result = self._execute_write(query, tuple(values))
        return result > 0
    
    def delete(self, specimen_id: int) -> bool:
        """
        Delete a specimen by ID.
        
        Args:
            specimen_id: The specimen ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        result = self._execute_write(
            "DELETE FROM specimens WHERE id = ?",
            (specimen_id,)
        )
        return result > 0
    
    def delete_many(self, specimen_ids: List[int]) -> int:
        """
        Delete multiple specimens.
        
        Args:
            specimen_ids: List of IDs to delete
            
        Returns:
            Number of records deleted
        """
        if not specimen_ids:
            return 0
        
        placeholders = ','.join('?' * len(specimen_ids))
        result = self._execute_write(
            f"DELETE FROM specimens WHERE id IN ({placeholders})",
            tuple(specimen_ids)
        )
        return result
    
    # =========================================================================
    # SEARCH & FILTERING
    # =========================================================================
    
    def search(
        self,
        species_name: Optional[str] = None,
        species_tvk: Optional[str] = None,
        common_name: Optional[str] = None,
        order_name: Optional[str] = None,
        family: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        site_name: Optional[str] = None,
        grid_ref: Optional[str] = None,
        vc_number: Optional[int] = None,
        collector: Optional[str] = None,
        determiner: Optional[str] = None,
        storage_location: Optional[str] = None,
        preparation_type: Optional[str] = None,
        has_import_notes: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Search specimens with filters.
        
        All text searches are case-insensitive partial matches.
        
        Returns:
            List of matching specimen dicts
        """
        conditions = []
        params = []
        
        if species_name:
            conditions.append("(species_name LIKE ? OR common_name LIKE ?)")
            params.extend([f"%{species_name}%", f"%{species_name}%"])
        
        if species_tvk:
            conditions.append("species_tvk = ?")
            params.append(species_tvk)
        
        if common_name:
            conditions.append("common_name LIKE ?")
            params.append(f"%{common_name}%")
        
        if order_name:
            conditions.append("order_name = ?")
            params.append(order_name)
        
        if family:
            conditions.append("family = ?")
            params.append(family)
        
        if date_from:
            conditions.append("date_collected >= ?")
            params.append(date_from)
        
        if date_to:
            conditions.append("date_collected <= ?")
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
        
        if collector:
            conditions.append("collector LIKE ?")
            params.append(f"%{collector}%")
        
        if determiner:
            conditions.append("determiner LIKE ?")
            params.append(f"%{determiner}%")
        
        if storage_location:
            conditions.append("storage_location LIKE ?")
            params.append(f"%{storage_location}%")
        
        if preparation_type:
            conditions.append("preparation_type = ?")
            params.append(preparation_type)
        
        if has_import_notes is True:
            conditions.append("import_notes IS NOT NULL AND import_notes != ''")
        elif has_import_notes is False:
            conditions.append("(import_notes IS NULL OR import_notes = '')")
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        query = f"""
            SELECT * FROM specimens
            WHERE {where_clause}
            ORDER BY date_collected DESC
            LIMIT ? OFFSET ?
        """
        
        params.extend([limit, offset])
        rows = self._execute(query, tuple(params))
        return [dict(row) for row in rows]
    
    def search_by_text(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Full-text search across multiple fields.
        
        Searches: species_name, common_name, site_name, collector, notes
        
        Args:
            query: Search text
            limit: Max results
            
        Returns:
            List of matching specimens
        """
        search_term = f"%{query}%"
        rows = self._execute("""
            SELECT * FROM specimens
            WHERE species_name LIKE ?
               OR common_name LIKE ?
               OR site_name LIKE ?
               OR collector LIKE ?
               OR notes LIKE ?
            ORDER BY date_collected DESC
            LIMIT ?
        """, (search_term, search_term, search_term, search_term, search_term, limit))
        return [dict(row) for row in rows]
    
    # =========================================================================
    # COUNT METHODS
    # =========================================================================
    
    def count_all(self) -> int:
        """Count total specimens."""
        rows = self._execute("SELECT COUNT(*) as count FROM specimens")
        return rows[0]['count'] if rows else 0
    
    def count_unique_species(self) -> int:
        """Count unique species in collection."""
        rows = self._execute("""
            SELECT COUNT(DISTINCT species_tvk) as count
            FROM specimens
            WHERE species_tvk IS NOT NULL
        """)
        return rows[0]['count'] if rows else 0
    
    def count_by_species(self, species_tvk: str) -> int:
        """Count specimens for a specific species."""
        rows = self._execute(
            "SELECT COUNT(*) as count FROM specimens WHERE species_tvk = ?",
            (species_tvk,)
        )
        return rows[0]['count'] if rows else 0
    
    def count_with_import_notes(self) -> int:
        """Count specimens that have import notes (need review)."""
        rows = self._execute("""
            SELECT COUNT(*) as count FROM specimens
            WHERE import_notes IS NOT NULL AND import_notes != ''
        """)
        return rows[0]['count'] if rows else 0
    
    def count_by_family(self) -> Dict[str, int]:
        """Get specimen counts grouped by family."""
        rows = self._execute("""
            SELECT family, COUNT(*) as count
            FROM specimens
            WHERE family IS NOT NULL
            GROUP BY family
            ORDER BY count DESC
        """)
        return {row['family']: row['count'] for row in rows}
    
    def count_by_order(self) -> Dict[str, int]:
        """Get specimen counts grouped by order."""
        rows = self._execute("""
            SELECT order_name, COUNT(*) as count
            FROM specimens
            WHERE order_name IS NOT NULL
            GROUP BY order_name
            ORDER BY count DESC
        """)
        return {row['order_name']: row['count'] for row in rows}
    
    def count_by_storage_location(self) -> Dict[str, int]:
        """Get specimen counts grouped by storage location."""
        rows = self._execute("""
            SELECT storage_location, COUNT(*) as count
            FROM specimens
            WHERE storage_location IS NOT NULL
            GROUP BY storage_location
            ORDER BY count DESC
        """)
        return {row['storage_location']: row['count'] for row in rows}
    
    # =========================================================================
    # STATISTICS
    # =========================================================================
    
    def get_quick_stats(self) -> Dict[str, Any]:
        """
        Get quick statistics for the collection.
        
        Returns:
            Dict with total_specimens, unique_species, top_families, etc.
        """
        stats = {}
        
        # Total specimens
        stats['total_specimens'] = self.count_all()
        
        # Unique species
        stats['unique_species'] = self.count_unique_species()
        
        # Specimens needing review
        stats['needs_review'] = self.count_with_import_notes()
        
        # Top 5 families
        family_counts = self.count_by_family()
        stats['top_families'] = [
            {'family': family, 'count': count}
            for family, count in list(family_counts.items())[:5]
        ]
        
        # Top 5 orders
        order_counts = self.count_by_order()
        stats['top_orders'] = [
            {'order': order, 'count': count}
            for order, count in list(order_counts.items())[:5]
        ]
        
        # This year stats
        current_year = date.today().year
        rows = self._execute("""
            SELECT COUNT(*) as count FROM specimens
            WHERE date_collected LIKE ?
        """, (f"{current_year}%",))
        stats['this_year_specimens'] = rows[0]['count'] if rows else 0
        
        rows = self._execute("""
            SELECT COUNT(DISTINCT species_tvk) as count FROM specimens
            WHERE date_collected LIKE ? AND species_tvk IS NOT NULL
        """, (f"{current_year}%",))
        stats['this_year_species'] = rows[0]['count'] if rows else 0
        
        return stats
    
    def get_collection_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive collection summary.
        
        Returns:
            Dict with detailed collection statistics
        """
        summary = self.get_quick_stats()
        
        # Add storage breakdown
        summary['storage_locations'] = self.count_by_storage_location()
        
        # Add preparation type breakdown
        rows = self._execute("""
            SELECT preparation_type, COUNT(*) as count
            FROM specimens
            WHERE preparation_type IS NOT NULL
            GROUP BY preparation_type
            ORDER BY count DESC
        """)
        summary['preparation_types'] = {
            row['preparation_type']: row['count'] for row in rows
        }
        
        # Add date range
        rows = self._execute("""
            SELECT MIN(date_collected) as earliest, MAX(date_collected) as latest
            FROM specimens
            WHERE date_collected IS NOT NULL
        """)
        if rows and rows[0]['earliest']:
            summary['date_range'] = {
                'earliest': rows[0]['earliest'],
                'latest': rows[0]['latest']
            }
        
        # Vice county coverage
        rows = self._execute("""
            SELECT COUNT(DISTINCT vc_number) as count
            FROM specimens
            WHERE vc_number IS NOT NULL
        """)
        summary['vice_counties_covered'] = rows[0]['count'] if rows else 0
        
        return summary
    
    # =========================================================================
    # SPECIAL QUERIES
    # =========================================================================
    
    def get_recent_additions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get most recently added specimens."""
        rows = self._execute("""
            SELECT * FROM specimens
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in rows]
    
    def get_new_species_first_specimens(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get the first specimen of each species, ordered by collection date.
        
        Useful for "New to Collection" view.
        """
        rows = self._execute("""
            SELECT * FROM specimens
            WHERE id IN (
                SELECT MIN(id) FROM specimens
                WHERE species_name IS NOT NULL
                AND (species_name, date_collected) IN (
                    SELECT species_name, MIN(date_collected)
                    FROM specimens
                    WHERE species_name IS NOT NULL
                    GROUP BY species_name
                )
                GROUP BY species_name
            )
            ORDER BY date_collected DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in rows]
    
    def get_specimens_needing_review(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get specimens with import notes (need review)."""
        rows = self._execute("""
            SELECT * FROM specimens
            WHERE import_notes IS NOT NULL AND import_notes != ''
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in rows]
    
    def get_distinct_values(self, column: str) -> List[str]:
        """
        Get distinct values for a column (for filter dropdowns).
        
        Args:
            column: Column name (validated against whitelist)
            
        Returns:
            List of distinct values
        """
        valid_columns = {
            'order_name', 'family', 'subfamily', 'collector', 'determiner',
            'sex', 'preparation_type', 'storage_location', 'drawer_number',
            'condition', 'vice_county'
        }
        
        if column not in valid_columns:
            return []
        
        rows = self._execute(f"""
            SELECT DISTINCT {column}
            FROM specimens
            WHERE {column} IS NOT NULL AND {column} != ''
            ORDER BY {column}
        """)
        return [row[column] for row in rows]
    
    # =========================================================================
    # BATCH OPERATIONS
    # =========================================================================
    
    def create_many(self, specimens: List[Dict[str, Any]]) -> int:
        """
        Create multiple specimens efficiently.
        
        Args:
            specimens: List of specimen data dicts
            
        Returns:
            Number of specimens created
        """
        if not specimens:
            return 0
        
        now = datetime.now().isoformat()
        
        # Define all fields for batch insert
        # The batch path had the same gap. Missing one of the three would
        # leave a route that still loses the columns, which is how this
        # survived unnoticed.
        fields = [
            'specimen_code', 'species_name', 'species_tvk', 'common_name',
            'order_name', 'family', 'subfamily', 'superfamily',
            'taxonomic_sort_key', 'taxon_group',
            'date_collected', 'grid_ref',
            'vice_county', 'vc_number', 'site_name', 'site_name_local', 'collector', 'determiner',
            'sex', 'preparation_type', 'storage_location', 'drawer_number',
            'condition', 'label_data', 'notes', 'import_notes', 'observation_id',
            'created_at', 'updated_at'
        ]
        
        placeholders = ','.join(['?'] * len(fields))
        query = f"INSERT INTO specimens ({','.join(fields)}) VALUES ({placeholders})"
        
        params_list = []
        for spec in specimens:
            values = []
            for field in fields:
                if field in ('created_at', 'updated_at'):
                    values.append(now)
                else:
                    values.append(spec.get(field))
            params_list.append(tuple(values))
        
        return self._execute_many(query, params_list)
    
    def update_many(self, updates: List[Tuple[int, Dict[str, Any]]]) -> int:
        """
        Update multiple specimens.
        
        Args:
            updates: List of (specimen_id, data_dict) tuples
            
        Returns:
            Number of specimens updated
        """
        count = 0
        for specimen_id, data in updates:
            if self.update(specimen_id, data):
                count += 1
        return count
    
    # =========================================================================
    # DUPLICATE CHECKING
    # =========================================================================
    
    def check_duplicate(
        self,
        species_tvk: str,
        date_collected: str,
        grid_ref: str
    ) -> Optional[Dict[str, Any]]:
        """
        Check if a duplicate specimen exists.
        
        Args:
            species_tvk: Species TVK
            date_collected: Collection date
            grid_ref: Grid reference
            
        Returns:
            Existing specimen dict if duplicate found, None otherwise
        """
        rows = self._execute("""
            SELECT * FROM specimens
            WHERE species_tvk = ?
              AND date_collected = ?
              AND grid_ref = ?
            LIMIT 1
        """, (species_tvk, date_collected, grid_ref))
        return dict(rows[0]) if rows else None
    
    def find_potential_duplicates(self) -> List[Dict[str, Any]]:
        """
        Find potential duplicate specimens.
        
        Returns specimens with same species/date/grid combinations.
        """
        rows = self._execute("""
            SELECT s1.*, COUNT(*) as duplicate_count
            FROM specimens s1
            JOIN specimens s2 ON s1.species_tvk = s2.species_tvk
                AND s1.date_collected = s2.date_collected
                AND s1.grid_ref = s2.grid_ref
                AND s1.id != s2.id
            WHERE s1.species_tvk IS NOT NULL
            GROUP BY s1.id
            ORDER BY duplicate_count DESC, s1.species_name
        """)
        return [dict(row) for row in rows]
