"""
Field Entry App - UKSI Database Lookup.

Species autocomplete and taxonomy lookup from uksi.db.
"""

import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any


class UKSILookup:
    """Interface to UKSI database for species autocomplete."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize UKSI lookup.
        
        Args:
            db_path: Path to uksi.db, or None to search standard locations
        """
        self._conn: Optional[sqlite3.Connection] = None
        self._db_path = db_path
        
        if db_path is None:
            self._db_path = self._find_database()
    
    def _find_database(self) -> Optional[Path]:
        """Search standard locations for uksi.db."""
        candidates = [
            Path('data/uksi.db'),
            Path('../data/uksi.db'),
            Path('../../data/uksi.db'),
            Path.cwd() / 'data' / 'uksi.db',
        ]
        
        for path in candidates:
            if path.exists():
                return path
        
        return None
    
    def connect(self) -> bool:
        """
        Connect to the database.
        
        Returns:
            True if connected successfully
        """
        if not self._db_path or not self._db_path.exists():
            print(f"[UKSILookup] Database not found: {self._db_path}")
            return False
        
        try:
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
            return True
        except Exception as e:
            print(f"[UKSILookup] Connection error: {e}")
            return False
    
    def close(self):
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
    
    def search(self, term: str, limit: int = 15) -> List[str]:
        """
        Search for species by scientific name, common name, or synonym.
        
        Also supports:
        - Genus-level search: "Bembidion" returns all Bembidion species
        - Family-level search: "Cerambycidae" returns all longhorn beetles
        - Synonyms shown as "OldName → PreferredName"
        - Aggregates (e.g., "Taraxacum agg.")
        
        Args:
            term: Search term (minimum 2 characters)
            limit: Maximum results to return
            
        Returns:
            List of display strings
        """
        if not self._conn or len(term.strip()) < 2:
            return []
        
        try:
            terms = term.strip().split()
            results = []
            seen = set()
            
            # Build search pattern
            if len(terms) == 1:
                search_pattern = f"%{term}%"
                start_pattern = f"{term}%"
            else:
                search_pattern = f"%{terms[0]}%{terms[1]}%"
                start_pattern = search_pattern
            
            # 1. Check if searching for a genus or family name
            #    If term matches a genus/family exactly, show all species in it
            genus_family_results = self._search_genus_or_family(term.strip(), limit)
            if genus_family_results:
                return genus_family_results
            
            # 2. Search preferred names in taxa table (highest priority)
            # Include Species, Subspecies, Variety, Form, and Aggregate ranks
            cursor = self._conn.execute("""
                SELECT t.scientific_name, (SELECT common_name FROM common_names cn2 
                     WHERE cn2.tvk = t.tvk 
                     AND cn2.common_name NOT GLOB '*[àáâãäåèéêëìíîïòóôõöùúûüýÿŵŷ]*'
                     AND SUBSTR(cn2.common_name, 1, 1) = UPPER(SUBSTR(cn2.common_name, 1, 1))
                     ORDER BY LENGTH(cn2.common_name) LIMIT 1) as common_name,
                       CASE 
                           WHEN t.scientific_name LIKE ? THEN 0
                           WHEN (SELECT common_name FROM common_names cn2 
                     WHERE cn2.tvk = t.tvk 
                     AND cn2.common_name NOT GLOB '*[àáâãäåèéêëìíîïòóôõöùúûüýÿŵŷ]*'
                     AND SUBSTR(cn2.common_name, 1, 1) = UPPER(SUBSTR(cn2.common_name, 1, 1))
                     ORDER BY LENGTH(cn2.common_name) LIMIT 1) LIKE ? THEN 1
                           ELSE 2 
                       END as priority
                FROM taxa t
                WHERE t.rank IN ('Species', 'Subspecies', 'Variety', 'Form', 
                                 'Species Aggregate', 'Species Hybrid', 'Aggregate')
                  AND (t.scientific_name LIKE ? OR (SELECT common_name FROM common_names cn2 
                     WHERE cn2.tvk = t.tvk 
                     AND cn2.common_name NOT GLOB '*[àáâãäåèéêëìíîïòóôõöùúûüýÿŵŷ]*'
                     AND SUBSTR(cn2.common_name, 1, 1) = UPPER(SUBSTR(cn2.common_name, 1, 1))
                     ORDER BY LENGTH(cn2.common_name) LIMIT 1) LIKE ?)
                ORDER BY priority, t.scientific_name
                LIMIT ?
            """, (start_pattern, start_pattern, search_pattern, search_pattern, limit))
            
            for row in cursor.fetchall():
                scientific = row[0]
                common = row[1]
                
                if scientific not in seen:
                    seen.add(scientific)
                    if common:
                        results.append(f"{scientific} ({common})")
                    else:
                        results.append(scientific)
            
            # 3. Search synonyms table (old/alternative names)
            if len(results) < limit:
                remaining = limit - len(results)
                
                cursor = self._conn.execute("""
                    SELECT s.synonym, t.scientific_name, (SELECT common_name FROM common_names cn2 
                     WHERE cn2.tvk = t.tvk 
                     AND cn2.common_name NOT GLOB '*[àáâãäåèéêëìíîïòóôõöùúûüýÿŵŷ]*'
                     AND SUBSTR(cn2.common_name, 1, 1) = UPPER(SUBSTR(cn2.common_name, 1, 1))
                     ORDER BY LENGTH(cn2.common_name) LIMIT 1) as common_name
                    FROM synonyms s
                    JOIN taxa t ON s.tvk = t.tvk
                    WHERE t.rank IN ('Species', 'Subspecies', 'Variety', 'Form', 
                                     'Species Aggregate', 'Species Hybrid', 'Aggregate')
                      AND s.synonym LIKE ?
                    ORDER BY s.synonym
                    LIMIT ?
                """, (search_pattern, remaining))
                
                for row in cursor.fetchall():
                    synonym = row[0]
                    preferred = row[1]
                    common = row[2]
                    
                    if preferred not in seen:
                        seen.add(preferred)
                        if common:
                            results.append(f"{synonym} → {preferred} ({common})")
                        else:
                            results.append(f"{synonym} → {preferred}")
            
            return results
            
        except Exception as e:
            print(f"[UKSILookup] Search error: {e}")
            return []
    
    def _search_genus_or_family(self, term: str, limit: int) -> List[str]:
        """
        Check if term is a genus or family name, return species if so.
        
        Args:
            term: Search term (single word, exact match)
            limit: Maximum results
            
        Returns:
            List of species in that genus/family, or empty list if not a genus/family
        """
        if ' ' in term:  # Only single-word terms can be genus/family
            return []
        
        try:
            # Check if it's a genus
            cursor = self._conn.execute("""
                SELECT tvk FROM taxa 
                WHERE rank = 'Genus' AND scientific_name = ?
                LIMIT 1
            """, (term,))
            
            genus_row = cursor.fetchone()
            if genus_row:
                # It's a genus - return all species/aggregates in this genus
                cursor = self._conn.execute("""
                    SELECT t.scientific_name, (SELECT common_name FROM common_names cn2 
                     WHERE cn2.tvk = t.tvk 
                     AND cn2.common_name NOT GLOB '*[àáâãäåèéêëìíîïòóôõöùúûüýÿŵŷ]*'
                     AND SUBSTR(cn2.common_name, 1, 1) = UPPER(SUBSTR(cn2.common_name, 1, 1))
                     ORDER BY LENGTH(cn2.common_name) LIMIT 1) as common_name
                    FROM taxa t
                    WHERE t.rank IN ('Species', 'Species Aggregate', 'Aggregate') 
                      AND t.genus = ?
                    ORDER BY t.scientific_name
                    LIMIT ?
                """, (term, limit))
                
                results = []
                for row in cursor.fetchall():
                    if row[1]:
                        results.append(f"{row[0]} ({row[1]})")
                    else:
                        results.append(row[0])
                return results
            
            # Check if it's a family
            cursor = self._conn.execute("""
                SELECT tvk FROM taxa 
                WHERE rank = 'Family' AND scientific_name = ?
                LIMIT 1
            """, (term,))
            
            family_row = cursor.fetchone()
            if family_row:
                # It's a family - return species/aggregates in this family
                cursor = self._conn.execute("""
                    SELECT t.scientific_name, (SELECT common_name FROM common_names cn2 
                     WHERE cn2.tvk = t.tvk 
                     AND cn2.common_name NOT GLOB '*[àáâãäåèéêëìíîïòóôõöùúûüýÿŵŷ]*'
                     AND SUBSTR(cn2.common_name, 1, 1) = UPPER(SUBSTR(cn2.common_name, 1, 1))
                     ORDER BY LENGTH(cn2.common_name) LIMIT 1) as common_name
                    FROM taxa t
                    WHERE t.rank IN ('Species', 'Species Aggregate', 'Aggregate') 
                      AND t.family = ?
                    ORDER BY t.scientific_name
                    LIMIT ?
                """, (term, limit))
                
                results = []
                for row in cursor.fetchall():
                    if row[1]:
                        results.append(f"{row[0]} ({row[1]})")
                    else:
                        results.append(row[0])
                return results
            
            return []
            
        except Exception as e:
            print(f"[UKSILookup] Genus/family search error: {e}")
            return []
    
    def lookup(self, scientific_name: str) -> Optional[Dict[str, Any]]:
        """
        Get full species details by scientific name.
        
        Walks the taxonomic hierarchy to find Family and Order.
        
        Args:
            scientific_name: Exact scientific name
            
        Returns:
            Dict with tvk, scientific_name, common_name, family, order
            or None if not found
        """
        if not self._conn or not scientific_name:
            return None
        
        try:
            # Find the taxon (species, aggregate, subspecies, etc.)
            cursor = self._conn.execute("""
                SELECT tvk, scientific_name, rank, parent_tvk
                FROM taxa 
                WHERE scientific_name = ? 
                  AND rank IN ('Species', 'Subspecies', 'Variety', 'Form', 
                               'Species Aggregate', 'Species Hybrid', 'Aggregate')
            """, (scientific_name.strip(),))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            species_tvk = row['tvk']
            
            # Get common name
            common_cursor = self._conn.execute(
                "SELECT common_name FROM common_names WHERE tvk = ? AND preferred = 1 LIMIT 1",
                (species_tvk,)
            )
            common_row = common_cursor.fetchone()
            common_name = common_row['common_name'] if common_row else ''
            
            # Walk hierarchy to find Family and Order
            family = ''
            order = ''
            parent_tvk = row['parent_tvk']
            
            for _ in range(15):  # Max depth to prevent infinite loop
                if not parent_tvk:
                    break
                
                parent = self._conn.execute("""
                    SELECT scientific_name, rank, parent_tvk
                    FROM taxa WHERE tvk = ?
                """, (parent_tvk,)).fetchone()
                
                if not parent:
                    break
                
                if parent['rank'] == 'Family' and not family:
                    family = parent['scientific_name']
                elif parent['rank'] == 'Order' and not order:
                    order = parent['scientific_name']
                
                # Stop if we have both
                if family and order:
                    break
                
                parent_tvk = parent['parent_tvk']
            
            return {
                'tvk': species_tvk,
                'scientific_name': row['scientific_name'],
                'common_name': common_name,
                'family': family,
                'order': order,
            }
            
        except Exception as e:
            print(f"[UKSILookup] Lookup error: {e}")
            return None
    
    def lookup_by_tvk(self, tvk: str) -> Optional[Dict[str, Any]]:
        """
        Get species details by TVK.
        
        Args:
            tvk: TaxonVersionKey
            
        Returns:
            Dict with species details or None
        """
        if not self._conn or not tvk:
            return None
        
        try:
            cursor = self._conn.execute("""
                SELECT scientific_name FROM taxa WHERE tvk = ?
            """, (tvk.strip(),))
            
            row = cursor.fetchone()
            if row:
                return self.lookup(row['scientific_name'])
            
            return None
            
        except Exception as e:
            print(f"[UKSILookup] TVK lookup error: {e}")
            return None
    
    @staticmethod
    def extract_scientific_name(display_text: str) -> str:
        """
        Extract scientific name from display formats:
        - "Scientific Name (Common Name)" → "Scientific Name"
        - "OldName → PreferredName (Common Name)" → "PreferredName"
        - "OldName → PreferredName" → "PreferredName"
        
        Args:
            display_text: Display string from search results
            
        Returns:
            The preferred scientific name
        """
        text = display_text.strip()
        
        # Handle synonym format: "OldName → PreferredName..."
        if ' → ' in text:
            # Take everything after the arrow
            text = text.split(' → ', 1)[1]
        
        # Remove common name in parentheses
        if '(' in text and text.endswith(')'):
            text = text.split('(')[0].strip()
        
        return text.strip()
