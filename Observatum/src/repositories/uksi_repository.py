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
from pathlib import Path
from typing import List, Dict, Any, Optional
import paths

# Try to import from config
try:
    from src.core.config import get_db_path
    USE_CONFIG = True
except ImportError:
    USE_CONFIG = False


def _find_data_dir() -> Path:
    """Find the data directory when config is not available."""
    this_file = Path(__file__).resolve()
    project_root = this_file.parent.parent.parent
    return project_root / "data"


class UKSIRepository:
    """
    Repository for UKSI species reference data.
    
    Provides a clean interface for species lookups without raw SQL
    in the rest of the application. Read-only - no create/update/delete.
    
    Uses uksi.db with tables:
    - taxa: scientific names with embedded taxonomy
    - common_names: English vernacular names
    - synonyms: alternative scientific names
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
        
        # Cache for taxonomy lookups (TVK -> {family, order, etc})
        self._taxonomy_cache: Dict[str, Dict[str, str]] = {}
    
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
    
    # =========================================================================
    # TAXONOMY HIERARCHY
    # =========================================================================
    
    def _get_taxonomy_by_hierarchy(self, tvk: str) -> Dict[str, Optional[str]]:
        """
        Walk up the parent hierarchy to find taxonomy (Family, Order, etc).
        
        Args:
            tvk: The TaxonVersionKey to look up
            
        Returns:
            Dict with 'family', 'order_name', 'genus', 'class_name', 'phylum', 'kingdom'
        """
        # Check cache first
        if tvk in self._taxonomy_cache:
            return self._taxonomy_cache[tvk]
        
        taxonomy = {
            'genus': None,
            'family': None,
            'order_name': None,
            'class_name': None,
            'phylum': None,
            'kingdom': None
        }
        
        current_tvk = tvk
        max_depth = 20  # Safety limit
        depth = 0
        
        while current_tvk and depth < max_depth:
            rows = self._execute(
                "SELECT scientific_name, rank, parent_tvk FROM taxa WHERE tvk = ?",
                (current_tvk,)
            )
            
            if not rows:
                break
                
            row = rows[0]
            rank = row['rank']
            name = row['scientific_name']
            parent = row['parent_tvk']
            
            # Map rank to taxonomy field
            if rank == 'Genus' and not taxonomy['genus']:
                taxonomy['genus'] = name
            elif rank == 'Family' and not taxonomy['family']:
                taxonomy['family'] = name
            elif rank == 'Order' and not taxonomy['order_name']:
                taxonomy['order_name'] = name
            elif rank == 'Class' and not taxonomy['class_name']:
                taxonomy['class_name'] = name
            elif rank == 'Phylum' and not taxonomy['phylum']:
                taxonomy['phylum'] = name
            elif rank == 'Kingdom' and not taxonomy['kingdom']:
                taxonomy['kingdom'] = name
            
            # Stop if we've found Family and Order (most common need)
            if taxonomy['family'] and taxonomy['order_name']:
                break
                
            current_tvk = parent
            depth += 1
        
        # Cache the result
        self._taxonomy_cache[tvk] = taxonomy
        return taxonomy
    
    def _get_preferred_common_name(self, tvk: str) -> Optional[str]:
        """
        Get the preferred (English) common name for a species.
        
        Filters out Scottish Gaelic and Welsh names by:
        1. Excluding names with accented characters (Gaelic)
        2. Preferring names starting with uppercase (English convention)
        3. Falling back to any name if no English name exists
        """
        # Try English name (no accents, starts uppercase)
        rows = self._execute(
            '''SELECT common_name FROM common_names 
               WHERE tvk = ? 
               AND common_name NOT GLOB '*[àáâãäåèéêëìíîïòóôõöùúûüýÿŵŷwy]*'
               AND SUBSTR(common_name, 1, 1) = UPPER(SUBSTR(common_name, 1, 1))
               ORDER BY LENGTH(common_name)
               LIMIT 1''',
            (tvk,)
        )
        if rows:
            return rows[0]['common_name']
        
        # Fall back to any name if no English name exists
        rows = self._execute(
            "SELECT common_name FROM common_names WHERE tvk = ? LIMIT 1",
            (tvk,)
        )
        return rows[0]['common_name'] if rows else None

    # =========================================================================
    # SPECIES SEARCH
    # =========================================================================
    
    def search_species(
        self,
        search_term: str,
        limit: int = 20,
        order_filter: Optional[str] = None,
        family_filter: Optional[str] = None,
        recorded_tvks: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for species by scientific name or common name.
        
        Supports multi-term search: "Rut mac" finds "Rutpela maculata"
        
        Implements smart ranking:
        1. Exact matches first
        2. Starts-with matches second
        3. Contains matches third
        4. Previously recorded species boosted
        
        Args:
            search_term: Text to search for (can be multiple space-separated terms)
            limit: Maximum results to return
            order_filter: Filter to specific order (e.g., 'Coleoptera')
            family_filter: Filter to specific family (e.g., 'Cerambycidae')
            recorded_tvks: List of TVKs for species user has recorded (for boosting)
            
        Returns:
            List of dicts with tvk, scientific_name, common_name, family, order_name, rank, match_type, score
        """
        if len(search_term.strip()) < 2:
            return []
        
        # Split search into terms (for "Rut mac" -> ["Rut", "mac"])
        search_terms = [t.strip() for t in search_term.split() if t.strip()]
        
        if not search_terms:
            return []
        
        # For single short term, require at least 2 chars
        if len(search_terms) == 1 and len(search_terms[0]) < 2:
            return []
        
        search_lower = search_term.lower()
        
        # Build base filter clause
        filter_clause = ""
        filter_params = []
        
        if order_filter:
            filter_clause += ' AND t."order" = ?'
            filter_params.append(order_filter)
        
        if family_filter:
            filter_clause += " AND t.family = ?"
            filter_params.append(family_filter)
        
        # Build multi-term LIKE conditions
        def build_multi_term_clause(column: str, terms: List[str]) -> tuple:
            clauses = []
            params = []
            for term in terms:
                clauses.append(f"{column} LIKE ?")
                params.append(f"%{term}%")
            return " AND ".join(clauses), params
        
        sci_clause, sci_params = build_multi_term_clause("t.scientific_name", search_terms)
        cn_clause, cn_params = build_multi_term_clause("cn.common_name", search_terms)
        syn_clause, syn_params = build_multi_term_clause("s.synonym", search_terms)
        
        # Search scientific names
        sci_query = f"""
            SELECT
                t.tvk,
                t.scientific_name,
                t.family,
                t."order" as order_name,
                t.rank
            FROM taxa t
            WHERE ({sci_clause})
              AND t.rank IN ('Species', 'Subspecies', 'Variety', 'Form', 'Species aggregate', 'Species sensu lato', 'Microspecies')
              {filter_clause}
            LIMIT 300
        """
        sci_results = self._execute(sci_query, tuple(sci_params + filter_params))
        
        # Search common names
        cn_query = f"""
            SELECT
                t.tvk,
                t.scientific_name,
                t.family,
                t."order" as order_name,
                t.rank,
                cn.common_name
            FROM common_names cn
            JOIN taxa t ON cn.tvk = t.tvk
            WHERE ({cn_clause})
              AND t.rank IN ('Species', 'Subspecies', 'Variety', 'Form', 'Species aggregate', 'Species sensu lato', 'Microspecies')
              {filter_clause}
            LIMIT 300
        """
        cn_results = self._execute(cn_query, tuple(cn_params + filter_params))
        
        # Search synonyms
        syn_query = f"""
            SELECT
                t.tvk,
                t.scientific_name,
                t.family,
                t."order" as order_name,
                t.rank,
                s.synonym
            FROM synonyms s
            JOIN taxa t ON s.tvk = t.tvk
            WHERE ({syn_clause})
              AND t.rank IN ('Species', 'Subspecies', 'Variety', 'Form', 'Species aggregate', 'Species sensu lato', 'Microspecies')
              {filter_clause}
            LIMIT 300
        """
        syn_results = self._execute(syn_query, tuple(syn_params + filter_params))
        
        # Build results dict (keyed by TVK to deduplicate)
        results_dict: Dict[str, Dict[str, Any]] = {}
        recorded_set = set(recorded_tvks) if recorded_tvks else set()
        
        # Helper to calculate score
        def calc_score(text: str, match_type: str, is_recorded: bool) -> int:
            text_lower = text.lower()
            base_score = 1000
            
            # Exact match
            if text_lower == search_lower:
                base_score = 100
                match_type = 'exact'
            # Starts with
            elif text_lower.startswith(search_lower):
                base_score = 200
                match_type = 'starts_with'
            # Contains
            else:
                base_score = 300
                match_type = 'contains'
            
            # Boost recorded species
            if is_recorded:
                base_score -= 50
            
            return base_score, match_type
        
        # Process scientific name results
        for row in sci_results:
            tvk = row['tvk']
            is_recorded = tvk in recorded_set
            score, match_type = calc_score(row['scientific_name'], 'contains', is_recorded)
            
            if tvk not in results_dict or score < results_dict[tvk]['score']:
                results_dict[tvk] = {
                    'tvk': tvk,
                    'scientific_name': row['scientific_name'],
                    'common_name': None,
                    'family': row['family'],
                    'order_name': row['order_name'],
                    'rank': row['rank'],
                    'match_type': match_type,
                    'score': score
                }
        
        # Process common name results
        for row in cn_results:
            tvk = row['tvk']
            is_recorded = tvk in recorded_set
            score, match_type = calc_score(row['common_name'], 'contains', is_recorded)
            
            # Common name matches score slightly higher to prioritize
            score -= 10
            
            if tvk not in results_dict:
                results_dict[tvk] = {
                    'tvk': tvk,
                    'scientific_name': row['scientific_name'],
                    'common_name': row['common_name'],
                    'family': row['family'],
                    'order_name': row['order_name'],
                    'rank': row['rank'],
                    'match_type': match_type,
                    'score': score
                }
            else:
                # Update common name if not set
                if not results_dict[tvk]['common_name']:
                    results_dict[tvk]['common_name'] = row['common_name']
                # Update score if better match
                if score < results_dict[tvk]['score']:
                    results_dict[tvk]['score'] = score
                    results_dict[tvk]['match_type'] = match_type
        
        # Process synonym results
        for row in syn_results:
            tvk = row['tvk']
            is_recorded = tvk in recorded_set
            score, match_type = calc_score(row['synonym'], 'contains', is_recorded)
            
            # Synonym matches score a bit lower
            score += 20
            
            if tvk not in results_dict:
                results_dict[tvk] = {
                    'tvk': tvk,
                    'scientific_name': row['scientific_name'],
                    'common_name': None,
                    'family': row['family'],
                    'order_name': row['order_name'],
                    'rank': row['rank'],
                    'match_type': match_type,
                    'score': score
                }
        
        # Get common names for results that don't have them
        for tvk, result in results_dict.items():
            if not result['common_name']:
                result['common_name'] = self._get_preferred_common_name(tvk)
        
        # Sort by score and return
        sorted_results = sorted(results_dict.values(), key=lambda x: x['score'])
        return sorted_results[:limit]
    
    # =========================================================================
    # SPECIES LOOKUP
    # =========================================================================
    
    def get_species_by_tvk(self, tvk: str) -> Optional[Dict[str, Any]]:
        """
        Get species details by TVK.
        
        Args:
            tvk: The TaxonVersionKey
            
        Returns:
            Dict with species details or None if not found
        """
        rows = self._execute("""
            SELECT
                t.tvk,
                t.scientific_name,
                t.rank,
                t.kingdom,
                t.phylum,
                t.class,
                t."order" as order_name,
                t.family,
                t.genus,
                cn.common_name
            FROM taxa t
            LEFT JOIN common_names cn ON t.tvk = cn.tvk
            WHERE t.tvk = ?
            LIMIT 1
        """, (tvk,))
        
        if not rows:
            return None
        
        row = rows[0]
        
        # Get taxonomy from hierarchy if not in taxa table
        kingdom = row['kingdom']
        phylum = row['phylum']
        class_name = row['class']
        order_name = row['order_name']
        family = row['family']
        genus = row['genus']
        
        # If any key taxonomy fields are missing, walk the hierarchy
        if not family or not order_name:
            taxonomy = self._get_taxonomy_by_hierarchy(tvk)
            if not genus:
                genus = taxonomy.get('genus')
            if not family:
                family = taxonomy.get('family')
            if not order_name:
                order_name = taxonomy.get('order_name')
            if not class_name:
                class_name = taxonomy.get('class_name')
            if not phylum:
                phylum = taxonomy.get('phylum')
            if not kingdom:
                kingdom = taxonomy.get('kingdom')
        
        return {
            'tvk': row['tvk'],
            'scientific_name': row['scientific_name'],
            'taxon_name': row['scientific_name'],  # Alias for compatibility
            'common_name': self._get_preferred_common_name(row['tvk']),
            'rank': row['rank'],
            'kingdom': kingdom,
            'phylum': phylum,
            'class_name': class_name,
            'order_name': order_name,
            'family': family,
            'genus': genus
        }
    
    def get_species_by_name(self, scientific_name: str) -> Optional[Dict[str, Any]]:
        """
        Get species details by exact scientific name.
        
        Args:
            scientific_name: The scientific name
            
        Returns:
            Dict with species details or None if not found
        """
        rows = self._execute("""
            SELECT tvk FROM taxa WHERE scientific_name = ? LIMIT 1
        """, (scientific_name,))
        
        if not rows:
            return None
        
        return self.get_species_by_tvk(rows[0]['tvk'])
    
    def get_taxonomy(self, tvk: str) -> Optional[Dict[str, Any]]:
        """
        Get full taxonomy hierarchy for a species.
        
        Args:
            tvk: The TaxonVersionKey
            
        Returns:
            Dict with taxonomy fields or None
        """
        species = self.get_species_by_tvk(tvk)
        if not species:
            return None
        
        return {
            'kingdom': species.get('kingdom'),
            'phylum': species.get('phylum'),
            'class': species.get('class_name'),
            'order': species.get('order_name'),
            'family': species.get('family'),
            'genus': species.get('genus'),
            'species': species.get('scientific_name'),
            'rank': species.get('rank')
        }
    
    # =========================================================================
    # COMMON NAMES & SYNONYMS
    # =========================================================================
    
    def get_common_names(self, tvk: str) -> List[str]:
        """
        Get all common names for a species.
        
        Args:
            tvk: The TaxonVersionKey
            
        Returns:
            List of common names
        """
        rows = self._execute(
            "SELECT common_name FROM common_names WHERE tvk = ?",
            (tvk,)
        )
        return [row['common_name'] for row in rows if row['common_name']]
    

    def get_species_batch(self, names: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Batch lookup multiple species by exact name match.
        
        Much faster than calling get_species_by_name repeatedly.
        Uses a single SQL query with IN clause.
        """
        if not names:
            return {}
        
        results = {}
        for name in names:
            results[name] = None
        
        placeholders = ",".join(["?" for _ in names])
        lower_names = [n.lower().strip() for n in names]
        
        query = f"""
            SELECT 
                t.INPUT_NAME as scientific_name,
                t.TAXON_VERSION_KEY as tvk,
                t.AUTHORITY as authority,
                t.TAXON_GROUP_NAME as taxon_group,
                t.ORGANISM_GROUP as organism_group,
                t.RECOMMENDED_NAME as recommended_name
            FROM uksi t
            WHERE LOWER(t.INPUT_NAME) IN ({placeholders})
            AND t.INPUT_NAME = t.RECOMMENDED_NAME
        """
        
        try:
            rows = self._execute(query, tuple(lower_names))
            
            found_by_lower = {}
            for row in rows:
                sci_name = row["scientific_name"]
                found_by_lower[sci_name.lower().strip()] = row
            
            for name in names:
                lower_name = name.lower().strip()
                if lower_name in found_by_lower:
                    row = found_by_lower[lower_name]
                    tvk = row["tvk"]
                    taxonomy = self._get_taxonomy_by_hierarchy(tvk)
                    common_name = self._get_preferred_common_name(tvk)
                    
                    results[name] = {
                        "scientific_name": row["scientific_name"],
                        "tvk": tvk,
                        "authority": row["authority"],
                        "common_name": common_name or "",
                        "taxon_group": row["taxon_group"],
                        "order_name": taxonomy.get("order", ""),
                        "family": taxonomy.get("family", ""),
                        "subfamily": taxonomy.get("subfamily", ""),
                    }
        except Exception as e:
            print(f"[UKSIRepository] Batch lookup error: {e}")
        
        return results

    def get_synonyms(self, tvk: str) -> List[str]:
        """
        Get all synonyms for a species.
        
        Args:
            tvk: The TaxonVersionKey
            
        Returns:
            List of synonym names
        """
        rows = self._execute(
            "SELECT synonym FROM synonyms WHERE tvk = ?",
            (tvk,)
        )
        return [row['synonym'] for row in rows if row['synonym']]
    
    # =========================================================================
    # REFERENCE LISTS
    # =========================================================================
    
    def get_orders(self) -> List[str]:
        """
        Get list of distinct orders in UKSI.
        
        Returns:
            Sorted list of order names
        """
        rows = self._execute("""
            SELECT DISTINCT scientific_name
            FROM taxa
            WHERE rank = 'Order'
            ORDER BY scientific_name
        """)
        return [row['scientific_name'] for row in rows if row['scientific_name']]
    
    def get_families(self, order_name: Optional[str] = None) -> List[str]:
        """
        Get list of distinct families, optionally filtered by order.
        
        Args:
            order_name: Filter to specific order (optional)
            
        Returns:
            Sorted list of family names
        """
        # For now, just get all families (order filtering requires hierarchy walking)
        rows = self._execute("""
            SELECT DISTINCT scientific_name
            FROM taxa
            WHERE rank = 'Family'
            ORDER BY scientific_name
        """)
        return [row['scientific_name'] for row in rows if row['scientific_name']]
    
    def get_genera(self, family: Optional[str] = None) -> List[str]:
        """
        Get list of distinct genera, optionally filtered by family.
        
        Args:
            family: Filter to specific family (optional)
            
        Returns:
            Sorted list of genus names
        """
        if family:
            rows = self._execute("""
                SELECT DISTINCT scientific_name
                FROM taxa
                WHERE rank = 'Genus' AND family = ?
                ORDER BY scientific_name
            """, (family,))
        else:
            rows = self._execute("""
                SELECT DISTINCT scientific_name
                FROM taxa
                WHERE rank = 'Genus'
                ORDER BY scientific_name
            """)
        return [row['scientific_name'] for row in rows if row['scientific_name']]
    
    # =========================================================================
    # HIERARCHY NAVIGATION
    # =========================================================================
    
    def get_parent(self, tvk: str) -> Optional[str]:
        """
        Get the parent TVK for a taxon.
        
        Args:
            tvk: The TaxonVersionKey
            
        Returns:
            Parent TVK or None
        """
        rows = self._execute(
            "SELECT parent_tvk FROM taxa WHERE tvk = ?",
            (tvk,)
        )
        if rows and rows[0]['parent_tvk']:
            return rows[0]['parent_tvk']
        return None
    
    def get_children(self, tvk: str) -> List[str]:
        """
        Get all child TVKs for a taxon.
        
        Args:
            tvk: The TaxonVersionKey
            
        Returns:
            List of child TVKs
        """
        rows = self._execute(
            "SELECT tvk FROM taxa WHERE parent_tvk = ?",
            (tvk,)
        )
        return [row['tvk'] for row in rows]
    
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
    
    def validate_tvk(self, tvk: str) -> bool:
        """
        Check if a TVK exists in UKSI.
        
        Args:
            tvk: The TaxonVersionKey to validate
            
        Returns:
            True if valid, False otherwise
        """
        rows = self._execute(
            "SELECT 1 FROM taxa WHERE tvk = ? LIMIT 1",
            (tvk,)
        )
        return len(rows) > 0
    
    def resolve_synonym(self, name: str) -> Optional[str]:
        """
        Resolve a synonym to its accepted TVK.
        
        Args:
            name: The scientific name (possibly a synonym)
            
        Returns:
            The accepted TVK or None if not found
        """
        # First check if it's an accepted name
        rows = self._execute(
            "SELECT tvk FROM taxa WHERE scientific_name = ? LIMIT 1",
            (name,)
        )
        if rows:
            return rows[0]['tvk']
        
        # Check synonyms
        rows = self._execute(
            "SELECT tvk FROM synonyms WHERE synonym = ? LIMIT 1",
            (name,)
        )
        if rows:
            return rows[0]['tvk']
        
        return None
