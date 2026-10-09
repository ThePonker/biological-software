"""
UKSI (UK Species Inventory) model for Observatum V2.

Handles all species reference data lookups including:
- Species search (fuzzy matching)
- Taxonomy lookups
- Common name retrieval
- Synonym resolution

Based on extracted uksi.db structure (from UKSI.mdb via uksi_extractor.py).
See UKSI_TROUBLESHOOTING_GUIDE.md for extraction details.

Usage:
    from src.models.uksi import UKSIModel
    from src.models.database import get_database

    uksi = UKSIModel(get_database())

    # Search for species
    results = uksi.search_species("Rutpela", limit=20)

    # Get full taxonomy
    taxonomy = uksi.get_taxonomy("NBNSYS0000024889")
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from .database import DatabaseManager


@dataclass
class Species:
    """Represents a species from UKSI."""
    tvk: str
    scientific_name: str
    common_name: Optional[str]
    rank: str
    kingdom: Optional[str]
    phylum: Optional[str]
    class_name: Optional[str]
    order_name: Optional[str]
    family: Optional[str]
    genus: Optional[str]


@dataclass
class SearchResult:
    """A species search result with ranking info."""
    tvk: str
    scientific_name: str
    common_name: Optional[str]
    family: Optional[str]
    order_name: Optional[str]
    rank: str
    match_type: str  # 'exact', 'starts_with', 'contains'
    score: int  # Lower is better


class UKSIModel:
    """
    Model for UKSI species reference data.

    Uses the extracted uksi.db with tables:
    - taxa: scientific names with embedded taxonomy
    - common_names: English vernacular names
    - synonyms: alternative scientific names
    - hierarchy: parent-child relationships
    """

    def __init__(self, db: DatabaseManager):
        self.db = db
        # Cache for taxonomy lookups (TVK -> {family, order, etc})
        self._taxonomy_cache: Dict[str, Dict[str, str]] = {}

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
            query = """
                SELECT scientific_name, rank, parent_tvk
                FROM taxa
                WHERE tvk = ?
            """
            results = self.db.execute_uksi(query, (current_tvk,))
            
            if not results:
                break
                
            row = results[0]
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

    def search_species(
        self,
        search_term: str,
        limit: int = 20,
        order_filter: Optional[str] = None,
        family_filter: Optional[str] = None,
        recorded_tvks: Optional[List[str]] = None
    ) -> List[SearchResult]:
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
            List of SearchResult objects, ranked by relevance
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
        # For "Rut mac": scientific_name LIKE '%Rut%' AND scientific_name LIKE '%mac%'
        def build_multi_term_clause(column: str, terms: List[str]) -> tuple:
            """Build AND clause for multiple search terms."""
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
              AND t.rank IN ('Species', 'Subspecies', 'Variety', 'Form')
              {filter_clause}
            LIMIT 300
        """
        sci_results = self.db.execute_uksi(sci_query, tuple(sci_params + filter_params))

        # Search common names - get ALL matching common names per TVK
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
              AND t.rank IN ('Species', 'Subspecies', 'Variety', 'Form')
              {filter_clause}
            LIMIT 300
        """
        cn_results = self.db.execute_uksi(cn_query, tuple(cn_params + filter_params))

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
              AND t.rank IN ('Species', 'Subspecies', 'Variety', 'Form')
              {filter_clause}
            LIMIT 100
        """
        syn_results = self.db.execute_uksi(syn_query, tuple(syn_params + filter_params))

        # Build a map of TVK -> best match info
        # Track the best-matching common name for each TVK
        tvk_data: Dict[str, Dict] = {}

        # Process scientific name matches
        for row in sci_results:
            tvk = row['tvk']
            if tvk not in tvk_data:
                tvk_data[tvk] = {
                    'tvk': tvk,
                    'scientific_name': row['scientific_name'],
                    'family': row['family'],
                    'order_name': row['order_name'],
                    'rank': row['rank'],
                    'common_name': None,
                    'best_common_score': 999,  # Lower is better
                    'matched_via': 'scientific'
                }

        # Process common name matches - find best matching common name per TVK
        for row in cn_results:
            tvk = row['tvk']
            common_name = row['common_name'] or ''
            common_lower = common_name.lower()

            # Calculate match score for this common name
            if common_lower == search_lower:
                score = 0  # Exact match
            elif common_lower.startswith(search_lower):
                score = 1  # Starts with
            else:
                score = 2  # Contains

            if tvk not in tvk_data:
                tvk_data[tvk] = {
                    'tvk': tvk,
                    'scientific_name': row['scientific_name'],
                    'family': row['family'],
                    'order_name': row['order_name'],
                    'rank': row['rank'],
                    'common_name': common_name,
                    'best_common_score': score,
                    'matched_via': 'common'
                }
            elif score < tvk_data[tvk]['best_common_score']:
                # Better common name match found
                tvk_data[tvk]['common_name'] = common_name
                tvk_data[tvk]['best_common_score'] = score
                tvk_data[tvk]['matched_via'] = 'common'

        # Process synonym matches
        for row in syn_results:
            tvk = row['tvk']
            if tvk not in tvk_data:
                tvk_data[tvk] = {
                    'tvk': tvk,
                    'scientific_name': row['scientific_name'],
                    'family': row['family'],
                    'order_name': row['order_name'],
                    'rank': row['rank'],
                    'common_name': None,
                    'best_common_score': 999,
                    'matched_via': 'synonym'
                }

        # For taxa without common names from search, try to get one
        tvks_without_common = [tvk for tvk, data in tvk_data.items() if data['common_name'] is None]
        if tvks_without_common:
            # Get first common name for each
            placeholders = ','.join(['?' for _ in tvks_without_common])
            cn_lookup = f"""
                SELECT tvk, common_name FROM common_names
                WHERE tvk IN ({placeholders})
                AND preferred = 1
            """
            cn_lookup_results = self.db.execute_uksi(cn_lookup, tuple(tvks_without_common))
            for row in cn_lookup_results:
                tvk = row['tvk']
                if tvk in tvk_data and tvk_data[tvk]['common_name'] is None:
                    tvk_data[tvk]['common_name'] = row['common_name']

        # Rank results
        ranked = []
        recorded_set = set(recorded_tvks) if recorded_tvks else set()

        for tvk, data in tvk_data.items():
            scientific_name = data['scientific_name'] or ''
            common_name = data['common_name'] or ''
            sci_lower = scientific_name.lower()
            common_lower = common_name.lower()

            # Determine match type and base score
            # For multi-term search, check if all terms match at start of words
            all_terms_start_word = self._all_terms_start_words(search_terms, sci_lower, common_lower)

            if sci_lower == search_lower or common_lower == search_lower:
                match_type = 'exact'
                score = 0
            elif all_terms_start_word:
                # "Rut mac" matches "Rutpela maculata" - both terms start words
                match_type = 'starts_with'
                score = 50  # Better than generic contains
            elif sci_lower.startswith(search_lower) or common_lower.startswith(search_lower):
                match_type = 'starts_with'
                score = 100
            else:
                match_type = 'contains'
                score = 200

            # Boost common name exact/starts-with matches (they're more likely what user wants)
            if data['matched_via'] == 'common' and data['best_common_score'] <= 1:
                score -= 25

            # Boost previously recorded species
            if tvk in recorded_set:
                score -= 50

            # Slight preference for shorter names (more likely to be what user wants)
            score += len(scientific_name) // 10
            
            # Get taxonomy from hierarchy if not in taxa table
            family = data['family']
            order_name = data['order_name']
            if not family or not order_name:
                taxonomy = self._get_taxonomy_by_hierarchy(tvk)
                if not family:
                    family = taxonomy.get('family')
                if not order_name:
                    order_name = taxonomy.get('order_name')

            ranked.append(SearchResult(
                tvk=tvk,
                scientific_name=scientific_name,
                common_name=common_name if common_name else None,
                family=family,
                order_name=order_name,
                rank=data['rank'],
                match_type=match_type,
                score=score
            ))

        # Sort by score and return limited results
        ranked.sort(key=lambda x: x.score)
        return ranked[:limit]

    def _all_terms_start_words(self, terms: List[str], sci_lower: str, common_lower: str) -> bool:
        """
        Check if all search terms match the start of words in the name.

        "Rut mac" matches "Rutpela maculata" because:
        - "rut" starts "rutpela"
        - "mac" starts "maculata"
        """
        # Split names into words
        sci_words = sci_lower.split()
        common_words = common_lower.split() if common_lower else []
        all_words = sci_words + common_words

        for term in terms:
            term_lower = term.lower()
            # Check if this term starts any word
            found = False
            for word in all_words:
                if word.startswith(term_lower):
                    found = True
                    break
            if not found:
                return False

        return True

    def get_species_by_tvk(self, tvk: str) -> Optional[Species]:
        """
        Get full species details by TaxonVersionKey.

        Args:
            tvk: The TaxonVersionKey (16-char identifier)

        Returns:
            Species object or None if not found
        """
        query = """
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
            ORDER BY CASE WHEN cn.common_name GLOB '[A-Z]*' THEN 0 ELSE 1 END
            LIMIT 1
        """
        results = self.db.execute_uksi(query, (tvk,))

        if not results:
            return None

        row = results[0]
        
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
        
        return Species(
            tvk=row['tvk'],
            scientific_name=row['scientific_name'],
            common_name=row['common_name'],
            rank=row['rank'],
            kingdom=kingdom,
            phylum=phylum,
            class_name=class_name,
            order_name=order_name,
            family=family,
            genus=genus
        )

    def get_species_by_name(self, scientific_name: str) -> Optional[Species]:
        """
        Get species details by exact scientific name.

        Args:
            scientific_name: The scientific name

        Returns:
            Species object or None if not found
        """
        query = """
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
            WHERE t.scientific_name = ?
            ORDER BY CASE WHEN cn.common_name GLOB '[A-Z]*' THEN 0 ELSE 1 END
            LIMIT 1
        """
        results = self.db.execute_uksi(query, (scientific_name,))

        if not results:
            return None

        row = results[0]
        tvk = row['tvk']
        
        # Get taxonomy from hierarchy if not in taxa table
        kingdom = row['kingdom']
        phylum = row['phylum']
        class_name = row['class']
        order_name = row['order_name']
        family = row['family']
        genus = row['genus']
        
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
        
        return Species(
            tvk=row['tvk'],
            scientific_name=row['scientific_name'],
            common_name=row['common_name'],
            rank=row['rank'],
            kingdom=kingdom,
            phylum=phylum,
            class_name=class_name,
            order_name=order_name,
            family=family,
            genus=genus
        )

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
            'kingdom': species.kingdom,
            'phylum': species.phylum,
            'class': species.class_name,
            'order': species.order_name,
            'family': species.family,
            'genus': species.genus,
            'species': species.scientific_name,
            'rank': species.rank
        }

    def get_common_names(self, tvk: str) -> List[str]:
        """
        Get all common names for a species.

        Args:
            tvk: The TaxonVersionKey

        Returns:
            List of common names
        """
        query = """
            SELECT common_name
            FROM common_names
            WHERE tvk = ?
        """
        results = self.db.execute_uksi(query, (tvk,))
        return [row['common_name'] for row in results if row['common_name']]


    def get_species_batch(self, names: List[str]) -> Dict[str, Optional[Species]]:
        """
        Batch lookup multiple species by exact name match.
        Much faster than calling get_species_by_name repeatedly.
        """
        if not names:
            return {}
        
        results = {}
        for name in names:
            results[name] = None
        
        placeholders = ",".join(["?" for _ in names])
        
        query = f"""
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
            WHERE LOWER(t.scientific_name) IN ({placeholders})
            ORDER BY t.scientific_name, CASE WHEN cn.common_name GLOB '[A-Z]*' THEN 0 ELSE 1 END
        """
        
        try:
            lower_names = [n.lower().strip() for n in names]
            rows = self.db.execute_uksi(query, tuple(lower_names))
            if not rows:
                return results
            
            # Group by scientific name (first result for each)
            found_by_lower = {}
            for row in rows:
                sci_name = row[1]
                lower_key = sci_name.lower().strip()
                if lower_key not in found_by_lower:
                    found_by_lower[lower_key] = row
            
            for name in names:
                lower_name = name.lower().strip()
                if lower_name in found_by_lower:
                    row = found_by_lower[lower_name]
                    # Species fields: tvk, scientific_name, common_name, rank, kingdom, phylum, class_name, order_name, family, genus
                    results[name] = Species(
                        tvk=row[0],
                        scientific_name=row[1],
                        common_name=row[9] or "",
                        rank=row[2] or "",
                        kingdom=row[3],
                        phylum=row[4],
                        class_name=row[5],
                        order_name=row[6],
                        family=row[7],
                        genus=row[8],
                    )
        except Exception as e:
            print(f"[uksi] get_species_batch: {e}")  # I7: was silent
        return results

    def get_synonyms(self, tvk: str) -> List[str]:
        """
        Get all synonyms for a species.

        Args:
            tvk: The TaxonVersionKey

        Returns:
            List of synonym names
        """
        query = """
            SELECT synonym
            FROM synonyms
            WHERE tvk = ?
        """
        results = self.db.execute_uksi(query, (tvk,))
        return [row['synonym'] for row in results if row['synonym']]

    def get_orders(self) -> List[str]:
        """
        Get list of distinct orders in UKSI.

        Returns:
            Sorted list of order names
        """
        query = """
            SELECT DISTINCT scientific_name
            FROM taxa
            WHERE rank = 'Order'
            ORDER BY scientific_name
        """
        results = self.db.execute_uksi(query, ())
        return [row['scientific_name'] for row in results if row['scientific_name']]

    def get_families(self, order_name: Optional[str] = None) -> List[str]:
        """
        Get list of distinct families, optionally filtered by order.

        Args:
            order_name: Filter to specific order (optional)

        Returns:
            Sorted list of family names
        """
        # Since taxa table doesn't have order populated, we need to use hierarchy
        # For now, just get all families
        query = """
            SELECT DISTINCT scientific_name
            FROM taxa
            WHERE rank = 'Family'
            ORDER BY scientific_name
        """
        results = self.db.execute_uksi(query, ())
        return [row['scientific_name'] for row in results if row['scientific_name']]

    def get_parent(self, tvk: str) -> Optional[str]:
        """
        Get the parent TVK for a taxon.

        Args:
            tvk: The TaxonVersionKey

        Returns:
            Parent TVK or None
        """
        query = "SELECT parent_tvk FROM taxa WHERE tvk = ?"
        results = self.db.execute_uksi(query, (tvk,))

        if results and results[0]['parent_tvk']:
            return results[0]['parent_tvk']
        return None

    def get_children(self, tvk: str) -> List[str]:
        """
        Get all child TVKs for a taxon.

        Args:
            tvk: The TaxonVersionKey

        Returns:
            List of child TVKs
        """
        query = "SELECT tvk FROM taxa WHERE parent_tvk = ?"
        results = self.db.execute_uksi(query, (tvk,))
        return [row['tvk'] for row in results]
