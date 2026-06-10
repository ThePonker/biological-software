"""
Field Entry App - Vice County Lookup.

Look up vice county from grid reference using vc_lookup.db.
"""

import sqlite3
from pathlib import Path
from typing import Optional, Tuple

from .grid_ref import GridRefValidator


class VCLookup:
    """Interface to VC lookup database."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize VC lookup.
        
        Args:
            db_path: Path to vc_lookup.db, or None to search standard locations
        """
        self._conn: Optional[sqlite3.Connection] = None
        self._db_path = db_path
        
        if db_path is None:
            self._db_path = self._find_database()
    
    def _find_database(self) -> Optional[Path]:
        """Search standard locations for vc_lookup.db."""
        candidates = [
            Path('data/vc_lookup.db'),
            Path('../data/vc_lookup.db'),
            Path('../../data/vc_lookup.db'),
            Path.cwd() / 'data' / 'vc_lookup.db',
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
            print(f"[VCLookup] Database not found: {self._db_path}")
            return False
        
        try:
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
            return True
        except Exception as e:
            print(f"[VCLookup] Connection error: {e}")
            return False
    
    def close(self):
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
    
    def get_vc_number(self, grid_ref: str) -> Optional[int]:
        """
        Get vice county number from grid reference.
        
        Args:
            grid_ref: OS Grid Reference
            
        Returns:
            VC number or None if not found
        """
        if not self._conn or not grid_ref:
            return None
        
        # Extract 1km square
        grid_1km = GridRefValidator.extract_1km_square(grid_ref)
        if not grid_1km:
            return None
        
        try:
            cursor = self._conn.execute(
                "SELECT vc_number FROM vc_lookup WHERE grid_1km = ?",
                (grid_1km.upper(),)
            )
            row = cursor.fetchone()
            
            if row:
                return row['vc_number']
            
            return None
            
        except Exception as e:
            print(f"[VCLookup] Lookup error: {e}")
            return None
    
    def get_vc_name(self, vc_number: int) -> Optional[str]:
        """
        Get vice county name from VC number.
        
        Args:
            vc_number: Vice county number (1-112)
            
        Returns:
            VC name or None if not found
        """
        if not self._conn or not vc_number:
            return None
        
        try:
            cursor = self._conn.execute(
                "SELECT vc_name FROM vc_names WHERE vc_number = ?",
                (vc_number,)
            )
            row = cursor.fetchone()
            
            if row:
                return row['vc_name']
            
            return None
            
        except Exception as e:
            print(f"[VCLookup] Name lookup error: {e}")
            return None
    
    def get_vc_short_name(self, vc_number: int) -> Optional[str]:
        """
        Get vice county short name from VC number.
        
        Args:
            vc_number: Vice county number (1-112)
            
        Returns:
            Short name or None if not found
        """
        if not self._conn or not vc_number:
            return None
        
        try:
            cursor = self._conn.execute(
                "SELECT short_name FROM vc_names WHERE vc_number = ?",
                (vc_number,)
            )
            row = cursor.fetchone()
            
            if row:
                return row['short_name']
            
            return None
            
        except Exception as e:
            print(f"[VCLookup] Short name lookup error: {e}")
            return None
    
    def get_vice_county(self, grid_ref: str) -> Optional[Tuple[int, str]]:
        """
        Get vice county from grid reference.
        
        Args:
            grid_ref: OS Grid Reference
            
        Returns:
            Tuple of (vc_number, vc_name) or None if not found
        """
        vc_number = self.get_vc_number(grid_ref)
        if vc_number is None:
            return None
        
        vc_name = self.get_vc_name(vc_number)
        return (vc_number, vc_name or f"VC{vc_number}")
    
    def format_vc(self, grid_ref: str) -> str:
        """
        Get formatted vice county string for display.
        
        Args:
            grid_ref: OS Grid Reference
            
        Returns:
            "VC{number}: {name}" or "Unknown" if not found
        """
        result = self.get_vice_county(grid_ref)
        if result:
            vc_number, vc_name = result
            return f"VC{vc_number}: {vc_name}"
        return "Unknown"
