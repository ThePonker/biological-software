"""
Base Repository for Observatum V2.

Provides common database operations that all repositories inherit.
Repositories handle all SQL queries - models become thin data containers.

Usage:
    class MyRepository(BaseRepository):
        TABLE = "my_table"
        
        def find_by_name(self, name: str):
            return self._execute("SELECT * FROM my_table WHERE name = ?", (name,))
"""

import sqlite3
from typing import Optional, List, Tuple, Any, TypeVar
from datetime import datetime

# Try to import from Observatum's database module
try:
    from src.models.database import DatabaseManager, get_database
    HAS_DB_MANAGER = True
except ImportError:
    HAS_DB_MANAGER = False
    DatabaseManager = None


T = TypeVar('T')


class BaseRepository:
    """
    Base class for all repositories.
    
    Provides:
    - Database connection management
    - Common query execution methods
    - Transaction support
    - Row mapping utilities
    """
    
    # Subclasses should override these
    TABLE: str = ""
    PRIMARY_KEY: str = "id"
    
    def __init__(self, db: 'DatabaseManager' = None):
        """
        Initialize repository with database connection.
        
        Args:
            db: DatabaseManager instance. If None, uses singleton.
        """
        if db is not None:
            self._db = db
        elif HAS_DB_MANAGER:
            self._db = get_database()
        else:
            raise ValueError("No database connection provided")
    
    @property
    def db(self) -> 'DatabaseManager':
        """Get the database manager."""
        return self._db
    
    # =========================================================================
    # QUERY EXECUTION
    # =========================================================================
    
    def _execute(self, query: str, params: Tuple = ()) -> List[sqlite3.Row]:
        """
        Execute a SELECT query and return results.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            List of Row objects
        """
        return self._db.execute_main(query, params)
    
    def _execute_write(self, query: str, params: Tuple = ()) -> int:
        """
        Execute an INSERT/UPDATE/DELETE query.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            lastrowid for INSERT, rowcount for UPDATE/DELETE
        """
        return self._db.execute_main_write(query, params)
    
    def _execute_many(self, query: str, params_list: List[Tuple]) -> int:
        """
        Execute multiple INSERT/UPDATE statements.
        
        Args:
            query: SQL query string
            params_list: List of parameter tuples
            
        Returns:
            Number of rows affected
        """
        return self._db.execute_main_many(query, params_list)
    
    def _scalar(self, query: str, params: Tuple = (), default: Any = None) -> Any:
        """
        Execute query and return single scalar value.
        
        Args:
            query: SQL query (should return single value)
            params: Query parameters
            default: Value to return if no results
            
        Returns:
            Single value from first row, first column
        """
        results = self._execute(query, params)
        if results and len(results) > 0:
            return results[0][0]
        return default
    
    # =========================================================================
    # COMMON CRUD OPERATIONS
    # =========================================================================
    
    def find_by_id(self, id: int) -> Optional[sqlite3.Row]:
        """
        Find a single record by primary key.
        
        Args:
            id: Primary key value
            
        Returns:
            Row or None if not found
        """
        query = f"SELECT * FROM {self.TABLE} WHERE {self.PRIMARY_KEY} = ?"
        results = self._execute(query, (id,))
        return results[0] if results else None
    
    def find_all(
        self, 
        limit: int = 100, 
        offset: int = 0,
        order_by: str = None
    ) -> List[sqlite3.Row]:
        """
        Find all records with pagination.
        
        Args:
            limit: Maximum records to return
            offset: Records to skip
            order_by: ORDER BY clause (validated by subclass)
            
        Returns:
            List of rows
        """
        order_clause = f"ORDER BY {order_by}" if order_by else ""
        query = f"""
            SELECT * FROM {self.TABLE}
            {order_clause}
            LIMIT ? OFFSET ?
        """
        return self._execute(query, (limit, offset))
    
    def count(self, where: str = None, params: Tuple = ()) -> int:
        """
        Count records, optionally with WHERE clause.
        
        Args:
            where: WHERE clause without 'WHERE' keyword
            params: Parameters for WHERE clause
            
        Returns:
            Count of matching records
        """
        where_clause = f"WHERE {where}" if where else ""
        query = f"SELECT COUNT(*) FROM {self.TABLE} {where_clause}"
        return self._scalar(query, params, default=0)
    
    def exists(self, where: str, params: Tuple) -> bool:
        """
        Check if any records match condition.
        
        Args:
            where: WHERE clause without 'WHERE' keyword
            params: Parameters for WHERE clause
            
        Returns:
            True if at least one record matches
        """
        query = f"SELECT 1 FROM {self.TABLE} WHERE {where} LIMIT 1"
        results = self._execute(query, params)
        return len(results) > 0
    
    def delete_by_id(self, id: int) -> bool:
        """
        Delete a record by primary key.
        
        Args:
            id: Primary key value
            
        Returns:
            True if deleted, False if not found
        """
        query = f"DELETE FROM {self.TABLE} WHERE {self.PRIMARY_KEY} = ?"
        return self._execute_write(query, (id,)) > 0
    
    # =========================================================================
    # UTILITIES
    # =========================================================================
    
    def _now(self) -> str:
        """Get current timestamp in ISO format."""
        return datetime.now().isoformat()
    
