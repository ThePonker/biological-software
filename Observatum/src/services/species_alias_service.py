"""
Species Alias Service for Observatum V2.

Manages a table of user-defined species name mappings that allow
automatic correction of species names during import. When a name
is mapped once, future imports will automatically use the correct
UKSI name.

Usage:
    from src.services.species_alias_service import SpeciesAliasService
    
    service = SpeciesAliasService(db)
    
    # Check if an alias exists
    result = service.get_alias("Rhagium mordax")
    if result:
        uksi_name, tvk, common_name, order, family, subfamily = result
    
    # Save a new alias
    service.save_alias(
        input_name="Rhagium mordax",
        uksi_name="Rhagium mordax (Degeer, 1775)",
        uksi_tvk="NBNSYS0000024691",
        uksi_common_name="Black-spotted Longhorn Beetle",
        uksi_order="Coleoptera",
        uksi_family="Cerambycidae"
    )
"""

from typing import Optional, Tuple, List, Dict
import sqlite3


class SpeciesAliasService:
    """
    Service for managing species name aliases.
    
    Stores mappings from user input names to correct UKSI names,
    enabling automatic resolution during import.
    """
    
    def __init__(self, db_manager=None, db_path: str = None):
        """
        Initialize the alias service.
        
        Args:
            db_manager: Database manager instance (preferred)
            db_path: Direct path to database (fallback)
        """
        self._db = db_manager
        self._db_path = db_path
        self._ensure_table_exists()
    
    def _get_connection(self) -> Optional[sqlite3.Connection]:
        """Get a database connection."""
        if self._db:
            # Use db manager's main database
            if hasattr(self._db, 'main_db_path') and self._db.main_db_path:
                return sqlite3.connect(str(self._db.main_db_path))
            elif hasattr(self._db, '_main_path') and self._db._main_path:
                return sqlite3.connect(str(self._db._main_path))
        
        if self._db_path:
            return sqlite3.connect(self._db_path)
        
        return None
    
    def _ensure_table_exists(self):
        """Create the species_aliases table if it doesn't exist."""
        conn = self._get_connection()
        if not conn:
            return
        
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS species_aliases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    input_name TEXT NOT NULL UNIQUE,
                    uksi_name TEXT NOT NULL,
                    uksi_tvk TEXT,
                    uksi_common_name TEXT,
                    uksi_order TEXT,
                    uksi_family TEXT,
                    uksi_subfamily TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    notes TEXT
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_alias_input 
                ON species_aliases(input_name)
            """)
            conn.commit()
        finally:
            conn.close()
    
    def get_alias(self, input_name: str) -> Optional[Tuple[str, str, str, str, str, str]]:
        """
        Look up an alias for a species name.
        
        Args:
            input_name: The name as entered by user
            
        Returns:
            Tuple of (uksi_name, tvk, common_name, order, family, subfamily) 
            or None if not found
        """
        conn = self._get_connection()
        if not conn:
            return None
        
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT uksi_name, uksi_tvk, uksi_common_name, 
                       uksi_order, uksi_family, uksi_subfamily
                FROM species_aliases
                WHERE LOWER(input_name) = LOWER(?)
            """, (input_name.strip(),))
            
            row = cursor.fetchone()
            if row:
                return row
            return None
        finally:
            conn.close()
    
    def save_alias(self, input_name: str, uksi_name: str, 
                   uksi_tvk: str = None, uksi_common_name: str = None,
                   uksi_order: str = None, uksi_family: str = None,
                   uksi_subfamily: str = None, notes: str = None) -> bool:
        """
        Save a new species alias.
        
        Args:
            input_name: The original user input name
            uksi_name: The correct UKSI scientific name
            uksi_tvk: The UKSI taxon version key
            uksi_common_name: The common name
            uksi_order: The order
            uksi_family: The family
            uksi_subfamily: The subfamily
            notes: Optional notes
            
        Returns:
            True if saved successfully
        """
        conn = self._get_connection()
        if not conn:
            return False
        
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO species_aliases 
                (input_name, uksi_name, uksi_tvk, uksi_common_name,
                 uksi_order, uksi_family, uksi_subfamily, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (input_name.strip(), uksi_name, uksi_tvk, uksi_common_name,
                  uksi_order, uksi_family, uksi_subfamily, notes))
            conn.commit()
            return True
        except Exception as e:
            print(f"[SpeciesAliasService] Error saving alias: {e}")
            return False
        finally:
            conn.close()
    
    def delete_alias(self, input_name: str) -> bool:
        """
        Delete an alias.
        
        Args:
            input_name: The input name to delete
            
        Returns:
            True if deleted successfully
        """
        conn = self._get_connection()
        if not conn:
            return False
        
        try:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM species_aliases
                WHERE LOWER(input_name) = LOWER(?)
            """, (input_name.strip(),))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
    
    def get_all_aliases(self) -> List[Dict]:
        """
        Get all saved aliases.
        
        Returns:
            List of alias dictionaries
        """
        conn = self._get_connection()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT input_name, uksi_name, uksi_tvk, uksi_common_name,
                       uksi_order, uksi_family, uksi_subfamily, created_at, notes
                FROM species_aliases
                ORDER BY input_name
            """)
            
            aliases = []
            for row in cursor.fetchall():
                aliases.append({
                    'input_name': row[0],
                    'uksi_name': row[1],
                    'uksi_tvk': row[2],
                    'uksi_common_name': row[3],
                    'uksi_order': row[4],
                    'uksi_family': row[5],
                    'uksi_subfamily': row[6],
                    'created_at': row[7],
                    'notes': row[8]
                })
            return aliases
        finally:
            conn.close()
    
    def get_alias_count(self) -> int:
        """Get the total number of aliases."""
        conn = self._get_connection()
        if not conn:
            return 0
        
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM species_aliases")
            return cursor.fetchone()[0]
        except:
            return 0
        finally:
            conn.close()
