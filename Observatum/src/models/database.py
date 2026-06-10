"""
Database connection manager for Observatum V2.

Handles connections to:
- Observatum.db (main application data)
- UKSI_Extract.db (species reference data)

Usage:
    from src.models.database import DatabaseManager
    
    db = DatabaseManager()
    db.set_paths(main_db="path/to/Observatum.db", uksi_db="path/to/UKSI_Extract.db")
    
    # Query main database
    results = db.execute_main("SELECT * FROM observations WHERE species_name = ?", ("Rutpela maculata",))
    
    # Query UKSI database
    species = db.execute_uksi("SELECT * FROM taxa WHERE taxon_name LIKE ?", ("%Rutpela%",))
"""

import sqlite3
import threading
from pathlib import Path
from typing import Optional, List, Tuple, Any, Dict
from contextlib import contextmanager


class DatabaseManager:
    """
    Manages SQLite database connections for Observatum.
    
    Provides separate connections for the main database and UKSI reference database.
    Uses context managers for safe connection handling.
    """
    
    def __init__(self):
        self._main_db_path: Optional[Path] = None
        self._uksi_db_path: Optional[Path] = None
    
    def set_paths(self, main_db: str, uksi_db: str) -> None:
        """
        Set the database file paths.
        
        Args:
            main_db: Path to Observatum.db
            uksi_db: Path to UKSI_Extract.db
        """
        self._main_db_path = Path(main_db)
        self._uksi_db_path = Path(uksi_db)
        
        # Validate paths exist
        if not self._main_db_path.exists():
            raise FileNotFoundError(f"Main database not found: {main_db}")
        if not self._uksi_db_path.exists():
            raise FileNotFoundError(f"UKSI database not found: {uksi_db}")
    
    def set_main_path(self, main_db: str) -> None:
        """Set only the main database path (useful for initial setup)."""
        self._main_db_path = Path(main_db)
    
    def set_uksi_path(self, uksi_db: str) -> None:
        """Set only the UKSI database path."""
        self._uksi_db_path = Path(uksi_db)
    
    @property
    def main_db_path(self) -> Optional[Path]:
        """Get the main database path."""
        return self._main_db_path
    
    @property
    def uksi_db_path(self) -> Optional[Path]:
        """Get the UKSI database path."""
        return self._uksi_db_path
    
    @contextmanager
    def _get_connection(self, db_path: Path, enable_foreign_keys: bool = True):
        """
        Context manager for database connections.
        
        Ensures connections are properly closed after use.
        Configures row_factory for dict-like access.
        
        Args:
            db_path: Path to the database file
            enable_foreign_keys: Whether to enable FK constraints (default True)
        """
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row  # Enables column access by name
        
        # Enable foreign key constraints for data integrity
        if enable_foreign_keys:
            conn.execute("PRAGMA foreign_keys = ON")
        
        # Performance optimizations
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA cache_size = -64000")  # 64MB cache
        conn.execute("PRAGMA mmap_size = 268435456")  # 256MB memory-mapped I/O
        conn.execute("PRAGMA synchronous = NORMAL")
        
        try:
            yield conn
        finally:
            conn.close()
    
    @contextmanager
    def main_connection(self):
        """Get a connection to the main database."""
        if not self._main_db_path:
            raise ValueError("Main database path not set. Call set_paths() first.")
        with self._get_connection(self._main_db_path) as conn:
            yield conn
    
    @contextmanager
    def uksi_connection(self):
        """Get a connection to the UKSI database (FK constraints disabled for read-only reference DB)."""
        if not self._uksi_db_path:
            raise ValueError("UKSI database path not set. Call set_paths() first.")
        # UKSI is read-only reference data, FK constraints not needed
        with self._get_connection(self._uksi_db_path, enable_foreign_keys=False) as conn:
            yield conn
    
    def execute_main(self, query: str, params: Tuple = ()) -> List[sqlite3.Row]:
        """
        Execute a SELECT query on the main database.
        
        Args:
            query: SQL query string
            params: Query parameters (tuple)
            
        Returns:
            List of Row objects (dict-like access)
        """
        with self.main_connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchall()
    
    def execute_uksi(self, query: str, params: Tuple = ()) -> List[sqlite3.Row]:
        """
        Execute a SELECT query on the UKSI database.
        
        Args:
            query: SQL query string
            params: Query parameters (tuple)
            
        Returns:
            List of Row objects (dict-like access)
        """
        with self.uksi_connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchall()
    
    def execute_main_write(self, query: str, params: Tuple = ()) -> int:
        """
        Execute an INSERT/UPDATE/DELETE on the main database.
        
        Args:
            query: SQL query string
            params: Query parameters (tuple)
            
        Returns:
            lastrowid for INSERT, or rowcount for UPDATE/DELETE
        """
        with self.main_connection() as conn:
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor.lastrowid if cursor.lastrowid else cursor.rowcount
    
    def execute_main_many(self, query: str, params_list: List[Tuple]) -> int:
        """
        Execute multiple INSERT/UPDATE statements on the main database.
        
        Args:
            query: SQL query string
            params_list: List of parameter tuples
            
        Returns:
            Number of rows affected
        """
        with self.main_connection() as conn:
            cursor = conn.executemany(query, params_list)
            conn.commit()
            return cursor.rowcount
    
    def table_exists(self, table_name: str, database: str = 'main') -> bool:
        """
        Check if a table exists in the specified database.
        
        Args:
            table_name: Name of the table
            database: 'main' or 'uksi'
            
        Returns:
            True if table exists
        """
        query = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
        if database == 'main':
            results = self.execute_main(query, (table_name,))
        else:
            results = self.execute_uksi(query, (table_name,))
        return len(results) > 0
    
    def get_table_info(self, table_name: str, database: str = 'main') -> List[Dict]:
        """
        Get column information for a table.
        
        Args:
            table_name: Name of the table
            database: 'main' or 'uksi'
            
        Returns:
            List of column info dicts
        """
        query = f"PRAGMA table_info({table_name})"
        if database == 'main':
            with self.main_connection() as conn:
                cursor = conn.execute(query)
                return [dict(row) for row in cursor.fetchall()]
        else:
            with self.uksi_connection() as conn:
                cursor = conn.execute(query)
                return [dict(row) for row in cursor.fetchall()]
    
    def vacuum_main(self) -> None:
        """Compact the main database (removes unused space)."""
        with self.main_connection() as conn:
            conn.execute("VACUUM")
    
    def backup_main(self, backup_path: str) -> None:
        """
        Create a backup of the main database.
        
        Args:
            backup_path: Path for the backup file
        """
        with self.main_connection() as conn:
            backup_conn = sqlite3.connect(backup_path)
            conn.backup(backup_conn)
            backup_conn.close()


# Singleton instance for app-wide use
_db_manager: Optional[DatabaseManager] = None
_db_manager_lock = threading.Lock()


def get_database() -> DatabaseManager:
    """
    Get the singleton DatabaseManager instance.
    
    Thread-safe: uses double-checked locking pattern.
    
    Usage:
        from src.models.database import get_database
        db = get_database()
    """
    global _db_manager
    
    # Fast path: if already initialized, return immediately
    if _db_manager is not None:
        return _db_manager
    
    # Slow path: acquire lock and check again
    with _db_manager_lock:
        # Double-check after acquiring lock (another thread may have initialized it)
        if _db_manager is None:
            _db_manager = DatabaseManager()
        return _db_manager
