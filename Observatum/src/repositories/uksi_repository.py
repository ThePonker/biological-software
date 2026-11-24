"""
UKSI Repository for Observatum V2.

Provides clean data access layer for UK Species Inventory reference data.
Read-only repository for species search, taxonomy lookups, and synonym resolution.

Usage:
    from src.repositories import UKSIRepository
    
    repo = UKSIRepository()
    
    # Search for species
    results = repo.search_species("Rutpela", limit=20)
    
    # Get species details
    species = repo.get_species_by_tvk("NBNSYS0000024889")
    
    # Get taxonomy
    taxonomy = repo.get_taxonomy("NBNSYS0000024889")
"""

import sqlite3
from dataclasses import asdict
from typing import List, Dict, Any, Optional
import paths
from shared.db_open import connect_ro  # D9: reference data, read-only
from ..models.uksi import UKSIModel   # the one implementation (24 Nov 2026)

# Try to import from config
try:
    from src.core.config import get_db_path  # noqa: F401  (availability check / re-export)
    USE_CONFIG = True
except ImportError:
    USE_CONFIG = False


class UKSIRepository:
    """
    Repository for UKSI species reference data.
    
    Provides a clean interface for species lookups without raw SQL
    in the rest of the application. Read-only - no create/update/delete.
    
    Uses uksi.db with tables:
    - taxa: scientific names with embedded taxonomy
    - common_names: English vernacular names
    - synonyms: alternative scientific names

    Since 24 Nov 2026 this is a thin wrapper: every lookup is UKSIModel's (one search, one
    common-name rule, one set of limits); this class only opens uksi.db read-only and
    returns plain dicts instead of dataclasses.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize repository.
        
        Args:
            db_path: Path to uksi.db. If None, uses config or default.
        """
        if db_path:
            self._db_path = db_path
        else:
            self._db_path = str(paths.UKSI_DB)

        self._model = UKSIModel(self)       # UKSIModel only needs .execute_uksi(query, params)
    
    # =========================================================================
    # CONNECTION MANAGEMENT
    # =========================================================================
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = connect_ro(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def execute_uksi(self, query: str, params: tuple = ()) -> List[sqlite3.Row]:
        """The one query door UKSIModel uses (same name as DatabaseManager.execute_uksi)."""
        return self._execute(query, params)

    def _execute(self, query: str, params: tuple = ()) -> List[sqlite3.Row]:
        """Execute a query and return all results."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()
        finally:
            conn.close()
    
    # =========================================================================
    # LOOKUPS (all UKSIModel's; results as dicts)
    # =========================================================================

    @staticmethod
    def _as_dict(species) -> Optional[Dict[str, Any]]:
        """A Species as the dict this class has always returned (plus the 'taxon_name' alias)."""
        if species is None:
            return None
        d = asdict(species)
        d['taxon_name'] = d['scientific_name']  # Alias for compatibility
        return d

    def search_species(
        self,
        search_term: str,
        limit: int = 20,
        order_filter: Optional[str] = None,
        family_filter: Optional[str] = None,
        recorded_tvks: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """UKSIModel.search_species, as dicts with tvk, scientific_name, common_name, family,
        order_name, rank, match_type, score."""
        return [asdict(r) for r in self._model.search_species(
            search_term, limit, order_filter, family_filter, recorded_tvks)]

    def get_species_by_tvk(self, tvk: str) -> Optional[Dict[str, Any]]:
        """Species details by TVK (dict) or None."""
        return self._as_dict(self._model.get_species_by_tvk(tvk))

    def get_species_by_name(self, scientific_name: str) -> Optional[Dict[str, Any]]:
        """Species details by exact scientific name (dict) or None."""
        return self._as_dict(self._model.get_species_by_name(scientific_name))

    def get_species_batch(self, names: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """Exact-name lookup of many names at once: {name: dict or None}."""
        return {n: self._as_dict(sp) for n, sp in self._model.get_species_batch(names).items()}

    def get_taxonomy(self, tvk: str) -> Optional[Dict[str, Any]]:
        """Full taxonomy for a species, or None."""
        return self._model.get_taxonomy(tvk)

    def get_common_names(self, tvk: str) -> List[str]:
        """All common names for a species."""
        return self._model.get_common_names(tvk)

    def get_synonyms(self, tvk: str) -> List[str]:
        """All synonyms for a species."""
        return self._model.get_synonyms(tvk)

    def get_orders(self) -> List[str]:
        """Sorted list of order names."""
        return self._model.get_orders()

    def get_families(self, order_name: Optional[str] = None) -> List[str]:
        """Sorted list of family names (all of them; order_name is not used, as before)."""
        return self._model.get_families(order_name)

    def get_parent(self, tvk: str) -> Optional[str]:
        """The parent TVK, or None."""
        return self._model.get_parent(tvk)

    def get_children(self, tvk: str) -> List[str]:
        """All child TVKs."""
        return self._model.get_children(tvk)

    # =========================================================================
    # STATISTICS
    # =========================================================================
    
    def count_species(self) -> int:
        """Count total species in UKSI."""
        rows = self._execute("""
            SELECT COUNT(*) as count FROM taxa
            WHERE rank IN ('Species', 'Subspecies')
        """)
        return rows[0]['count'] if rows else 0
    
    def count_by_order(self) -> Dict[str, int]:
        """Get species counts grouped by order."""
        rows = self._execute("""
            SELECT "order" as order_name, COUNT(*) as count
            FROM taxa
            WHERE rank IN ('Species', 'Subspecies')
              AND "order" IS NOT NULL
            GROUP BY "order"
            ORDER BY count DESC
        """)
        return {row['order_name']: row['count'] for row in rows}
    
    def count_by_family(self) -> Dict[str, int]:
        """Get species counts grouped by family."""
        rows = self._execute("""
            SELECT family, COUNT(*) as count
            FROM taxa
            WHERE rank IN ('Species', 'Subspecies')
              AND family IS NOT NULL
            GROUP BY family
            ORDER BY count DESC
        """)
        return {row['family']: row['count'] for row in rows}
    
    def get_quick_stats(self) -> Dict[str, Any]:
        """
        Get quick statistics for UKSI database.
        
        Returns:
            Dict with total_species, order_count, family_count, etc.
        """
        stats = {}
        
        # Total species
        stats['total_species'] = self.count_species()
        
        # Order count
        rows = self._execute("""
            SELECT COUNT(DISTINCT "order") as count FROM taxa
            WHERE "order" IS NOT NULL
        """)
        stats['order_count'] = rows[0]['count'] if rows else 0
        
        # Family count
        rows = self._execute("""
            SELECT COUNT(DISTINCT family) as count FROM taxa
            WHERE family IS NOT NULL
        """)
        stats['family_count'] = rows[0]['count'] if rows else 0
        
        # Genus count
        rows = self._execute("""
            SELECT COUNT(*) as count FROM taxa WHERE rank = 'Genus'
        """)
        stats['genus_count'] = rows[0]['count'] if rows else 0
        
        return stats
    
    # =========================================================================
    # VALIDATION
    # =========================================================================
    
