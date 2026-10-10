"""
Search Service.

Provides species search functionality with smart ranking.
Used by species search components across the application.

Features:
- Searches scientific names, common names, and synonyms
- Smart ranking (exact > starts_with > contains)
- Boosts previously recorded species
- Caches recorded species for performance

Now uses UKSIRepository for species lookups (preferred) with
fallback to UKSIModel for backward compatibility.
"""

from typing import List, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.uksi import UKSIModel
    from src.models.database import DatabaseManager

# Try to import repositories (preferred)
try:
    from src.repositories import UKSIRepository, ObservationRepository
    HAS_REPOSITORIES = True
except ImportError:
    HAS_REPOSITORIES = False


class SearchService:
    """
    Service for species search and ranking.
    
    Uses UKSIRepository for species lookups when available,
    with fallback to UKSIModel for backward compatibility.
    
    Features:
    - Recorded species caching and boosting
    - Result formatting for UI consumption
    - Filter management
    """
    
    def __init__(self, uksi_model: 'UKSIModel' = None, db: 'DatabaseManager' = None):
        """
        Initialize the search service.
        
        Args:
            uksi_model: UKSIModel instance for species lookups (legacy)
            db: DatabaseManager for querying recorded species (legacy)
        """
        self.uksi_model = uksi_model
        self.db = db
        self._uksi_repo = None  # UKSIRepository (preferred)
        self._obs_repo = None   # ObservationRepository for recorded species
        self._recorded_tvks: set = set()
        self._cache_loaded = False
        
        # Try to initialize repositories
        if HAS_REPOSITORIES:
            try:
                self._uksi_repo = UKSIRepository()
            except Exception as e:
                print(f"[SearchService] Could not create UKSIRepository: {e}")
            
            try:
                self._obs_repo = ObservationRepository()
            except Exception as e:
                print(f"[SearchService] Could not create ObservationRepository: {e}")
    
    def set_uksi_model(self, uksi_model: 'UKSIModel') -> None:
        """Set the UKSI model (for deferred initialization, legacy)."""
        self.uksi_model = uksi_model
    
    def set_database(self, db: 'DatabaseManager') -> None:
        """Set the database manager (for deferred initialization, legacy)."""
        self.db = db
    
    def search_species(
        self,
        search_term: str,
        limit: int = 20,
        order_filter: Optional[str] = None,
        family_filter: Optional[str] = None,
        boost_recorded: bool = True
    ) -> List[Dict]:
        """
        Search for species with smart ranking.
        
        Args:
            search_term: Text to search for (min 2 characters)
            limit: Maximum results to return
            order_filter: Filter to specific order (e.g., 'Coleoptera')
            family_filter: Filter to specific family (e.g., 'Cerambycidae')
            boost_recorded: Whether to boost previously recorded species
            
        Returns:
            List of species dicts with keys:
            - tvk: TaxonVersionKey
            - scientific_name: Scientific name
            - common_name: Common name (or None)
            - family: Family name
            - order: Order name  
            - rank: Taxonomic rank
            - match_type: 'exact', 'starts_with', or 'contains'
            - is_recorded: Whether user has recorded this species
        """
        if len(search_term) < 2:
            return []
        
        # Ensure recorded species cache is loaded
        if boost_recorded and not self._cache_loaded:
            self.refresh_recorded_species()
        
        # Get recorded TVKs for boosting
        recorded_tvks = list(self._recorded_tvks) if boost_recorded else None
        
        # The shared matcher (backlog item 1, 10 Oct 2026): typing slips, old names, common
        # names, aggregates -- the same search as every other species box in the suite.
        results = self._search_shared(search_term, limit, order_filter, family_filter)
        if results is not None:
            alias_results = self._search_aliases(search_term)
            existing_tvks = {r.get('tvk') for r in results}
            for alias_match in alias_results or []:
                if alias_match.get('tvk') not in existing_tvks:
                    results.append(alias_match)
            return results[:limit]

        # Use repository if available (the old SQL search, if uksi.db can't be indexed)
        if self._uksi_repo:
            results = self._search_via_repository(
                search_term, limit, order_filter, family_filter, recorded_tvks
            )
            # Also search aliases and merge (avoiding duplicates)
            alias_results = self._search_aliases(search_term)
            if alias_results:
                existing_tvks = {r.get('tvk') for r in results}
                for alias_match in alias_results:
                    if alias_match.get('tvk') not in existing_tvks:
                        results.append(alias_match)
            return results[:limit]
        
        # Fallback to model
        if self.uksi_model:
            results = self._search_via_model(
                search_term, limit, order_filter, family_filter, recorded_tvks
            )
        else:
            results = []
        
        # Also search aliases and merge (avoiding duplicates)
        alias_results = self._search_aliases(search_term)
        if alias_results:
            existing_tvks = {r.get('tvk') for r in results}
            for alias_match in alias_results:
                if alias_match.get('tvk') not in existing_tvks:
                    results.append(alias_match)
        
        return results[:limit]
    
    def _search_shared(self, search_term: str, limit: int, order_filter: Optional[str],
                       family_filter: Optional[str]) -> Optional[List[Dict]]:
        """shared.species_search over the species-level ranks this box has always offered;
        None if the index can't be built (the old search is used then)."""
        try:
            from shared.species_search import SPECIES_LEVEL, search
            want = None if (order_filter or family_filter) else limit
            results = search(search_term, limit=want, ranks=SPECIES_LEVEL,
                             recorded=self._recorded_tvks)
        except Exception as e:
            print(f"[SearchService] shared species search unavailable: {e}")
            return None
        if order_filter:
            results = [r for r in results if r.get('order') == order_filter]
        if family_filter:
            results = [r for r in results if r.get('family') == family_filter]
        return results[:limit]

    def _search_via_repository(
        self,
        search_term: str,
        limit: int,
        order_filter: Optional[str],
        family_filter: Optional[str],
        recorded_tvks: Optional[List[str]]
    ) -> List[Dict]:
        """Search using UKSIRepository (preferred method)."""
        results = self._uksi_repo.search_species(
            search_term=search_term,
            limit=limit,
            order_filter=order_filter,
            family_filter=family_filter,
            recorded_tvks=recorded_tvks
        )
        
        # Repository returns dicts, add is_recorded flag
        output = []
        for result in results:
            item = {
                'tvk': result.get('tvk'),
                'scientific_name': result.get('scientific_name'),
                'common_name': result.get('common_name'),
                'family': result.get('family'),
                'order': result.get('order_name'),
                'rank': result.get('rank'),
                'match_type': result.get('match_type'),
                'is_recorded': result.get('tvk') in self._recorded_tvks
            }
            output.append(item)
        
        return output
    
    def _search_via_model(
        self,
        search_term: str,
        limit: int,
        order_filter: Optional[str],
        family_filter: Optional[str],
        recorded_tvks: Optional[List[str]]
    ) -> List[Dict]:
        """Search using UKSIModel (legacy fallback)."""
        results = self.uksi_model.search_species(
            search_term=search_term,
            limit=limit,
            order_filter=order_filter,
            family_filter=family_filter,
            recorded_tvks=recorded_tvks
        )
        
        # Model returns SearchResult dataclasses, convert to dicts
        output = []
        for result in results:
            item = {
                'tvk': result.tvk,
                'scientific_name': result.scientific_name,
                'common_name': result.common_name,
                'family': result.family,
                'order': result.order_name,
                'rank': result.rank,
                'match_type': result.match_type,
                'is_recorded': result.tvk in self._recorded_tvks
            }
            output.append(item)
        
        return output
    
    def _search_aliases(self, search_term: str) -> List[Dict]:
        """Search species_aliases table for matching input names.
        
        This allows finding species by old/alternative names that users
        have mapped during imports.
        
        Args:
            search_term: Text to search for
            
        Returns:
            List of species dicts from alias matches
        """
        try:
            from ..models.database import get_database
            db = get_database()
            
            # Search aliases by input_name
            query = """
                SELECT input_name, uksi_name, uksi_tvk, uksi_common_name, 
                       uksi_order, uksi_family
                FROM species_aliases
                WHERE input_name LIKE ?
                LIMIT 20
            """
            results = db.execute_main(query, (f'%{search_term}%',))
            
            output = []
            seen_tvks = set()
            
            for row in results:
                tvk = row['uksi_tvk']
                if tvk and tvk not in seen_tvks:
                    seen_tvks.add(tvk)
                    output.append({
                        'tvk': tvk,
                        'scientific_name': row['uksi_name'],
                        'common_name': row['uksi_common_name'],
                        'family': row['uksi_family'],
                        'order': row['uksi_order'],
                        'rank': 'Species',
                        'match_type': 'alias',
                        'is_recorded': tvk in self._recorded_tvks,
                        'matched_alias': row['input_name']
                    })
            
            return output
        except Exception as e:
            print(f"[SearchService] Alias search error: {e}")
            return []
    
    def get_species_details(self, tvk: str) -> Optional[Dict]:
        """
        Get full details for a species by TVK.
        
        Args:
            tvk: TaxonVersionKey
            
        Returns:
            Dict with species details or None
        """
        # Use repository if available (preferred)
        if self._uksi_repo:
            return self._get_species_details_via_repository(tvk)
        
        # Fallback to model
        if self.uksi_model:
            return self._get_species_details_via_model(tvk)
        
        return None
    
    def _get_species_details_via_repository(self, tvk: str) -> Optional[Dict]:
        """Get species details using UKSIRepository."""
        species = self._uksi_repo.get_species_by_tvk(tvk)
        if not species:
            return None
        
        return {
            'tvk': species.get('tvk'),
            'scientific_name': species.get('scientific_name'),
            'common_name': species.get('common_name'),
            'rank': species.get('rank'),
            'kingdom': species.get('kingdom'),
            'phylum': species.get('phylum'),
            'class': species.get('class_name'),
            'order': species.get('order_name'),
            'family': species.get('family'),
            'genus': species.get('genus'),
            'common_names': self._uksi_repo.get_common_names(tvk),
            'synonyms': self._uksi_repo.get_synonyms(tvk),
            'is_recorded': tvk in self._recorded_tvks
        }
    
    def _get_species_details_via_model(self, tvk: str) -> Optional[Dict]:
        """Get species details using UKSIModel (legacy)."""
        species = self.uksi_model.get_species_by_tvk(tvk)
        if not species:
            return None
        
        return {
            'tvk': species.tvk,
            'scientific_name': species.scientific_name,
            'common_name': species.common_name,
            'rank': species.rank,
            'kingdom': species.kingdom,
            'phylum': species.phylum,
            'class': species.class_name,
            'order': species.order_name,
            'family': species.family,
            'genus': species.genus,
            'common_names': self.uksi_model.get_common_names(tvk),
            'synonyms': self.uksi_model.get_synonyms(tvk),
            'is_recorded': tvk in self._recorded_tvks
        }
    
    def refresh_recorded_species(self) -> None:
        """
        Refresh the cache of recorded species TVKs.
        
        Call this after importing data or when starting the app.
        """
        self._recorded_tvks = set()
        
        # Use repository if available (preferred)
        if self._obs_repo:
            try:
                # Try to get recorded TVKs from repository
                if hasattr(self._obs_repo, 'get_recorded_species_tvks'):
                    tvks = self._obs_repo.get_recorded_species_tvks()
                    self._recorded_tvks = set(tvks)
                    self._cache_loaded = True
                    return
            except Exception as e:
                print(f"[SearchService] Error getting recorded TVKs from repo: {e}")
        
        # Fallback to direct database query
        if not self.db:
            self._cache_loaded = True
            return
        
        try:
            # Query distinct TVKs from observations table
            query = "SELECT DISTINCT species_tvk FROM observations WHERE species_tvk IS NOT NULL"
            results = self.db.execute_main(query, ())
            self._recorded_tvks = {row['species_tvk'] for row in results}
        except Exception as e:
            # Table might not exist yet
            print(f"[search_service] refresh_recorded_species: {e}")  # I7: was silent
        
        self._cache_loaded = True
    
    def add_recorded_tvk(self, tvk: str) -> None:
        """
        Add a TVK to the recorded species cache.
        
        Call this after saving a new observation.
        """
        self._recorded_tvks.add(tvk)
    
    def get_recorded_tvks(self) -> set:
        """Get the set of TVKs the user has recorded."""
        if not self._cache_loaded:
            self.refresh_recorded_species()
        return self._recorded_tvks.copy()
    
    def get_recorded_count(self) -> int:
        """Get the count of distinct species recorded."""
        if not self._cache_loaded:
            self.refresh_recorded_species()
        return len(self._recorded_tvks)
    
    def get_orders(self) -> List[str]:
        """Get list of all orders for filtering."""
        # Use repository if available
        if self._uksi_repo:
            return self._uksi_repo.get_orders()
        
        # Fallback to model
        if self.uksi_model:
            return self.uksi_model.get_orders()
        
        return []
    
    def get_families(self, order_name: Optional[str] = None) -> List[str]:
        """Get list of families, optionally filtered by order."""
        # Use repository if available
        if self._uksi_repo:
            return self._uksi_repo.get_families(order_name)
        
        # Fallback to model
        if self.uksi_model:
            return self.uksi_model.get_families(order_name)
        
        return []


# Singleton instance
_search_service: Optional[SearchService] = None


def get_search_service() -> SearchService:
    """
    Get the singleton SearchService instance.
    
    Usage:
        from src.services.search_service import get_search_service
        search = get_search_service()
        results = search.search_species("robin")
    """
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
    return _search_service
