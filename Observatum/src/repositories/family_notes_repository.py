"""
Family Notes Repository - CRUD for family_notes table.

Manages user-editable notes and common names for taxonomic families
in the insect collection.
"""

import sqlite3
from typing import Optional, Dict


class FamilyNotesRepository:
    """Repository for family_notes table in observatum.db."""

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = db_path

    def set_db_path(self, db_path: str):
        self._db_path = db_path

    def _connect(self):
        return sqlite3.connect(self._db_path)

    def ensure_table(self):
        """Create family_notes table if it doesn't exist."""
        conn = self._connect()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS family_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_name TEXT NOT NULL,
                family TEXT NOT NULL,
                common_name TEXT,
                notes TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                UNIQUE(order_name, family)
            )
        """)
        conn.commit()
        conn.close()

    def get_notes(self, order_name: str, family: str) -> Optional[Dict]:
        """Get notes for a family. Returns dict or None."""
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM family_notes WHERE order_name = ? AND family = ?",
            (order_name, family)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def save_notes(self, order_name: str, family: str,
                   common_name: str = "", notes: str = ""):
        """Save or update notes for a family."""
        conn = self._connect()
        conn.execute("""
            INSERT INTO family_notes (order_name, family, common_name, notes)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(order_name, family) DO UPDATE SET
                common_name = excluded.common_name,
                notes = excluded.notes,
                updated_at = datetime('now')
        """, (order_name, family, common_name, notes))
        conn.commit()
        conn.close()

    def get_all_common_names(self) -> Dict[str, str]:
        """Get all family common names as {family: common_name} dict."""
        conn = self._connect()
        cursor = conn.execute(
            "SELECT family, common_name FROM family_notes WHERE common_name IS NOT NULL AND common_name != ''"
        )
        result = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()
        return result
