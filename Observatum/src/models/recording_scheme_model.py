"""
Recording Scheme Model for Observatum V2.

Handles CRUD operations for the recording_scheme table.
For search and statistics, use RecordingSchemeRepository instead.

Usage:
    from src.models.recording_scheme_model import SchemeRecord, RecordingSchemeModel
    from src.repositories import RecordingSchemeRepository
    
    # CRUD operations - use Model
    model = RecordingSchemeModel(db)
    record = SchemeRecord(species_name="Rutpela maculata", date="2024-06-15")
    new_id = model.create(record)
    
    # Search and stats - use Repository
    repo = RecordingSchemeRepository()
    results = repo.search(species_name="Rutpela")
    stats = repo.get_quick_stats()
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime

from .database import DatabaseManager


@dataclass
class SchemeRecord:
    """Represents a single recording scheme record."""
    id: Optional[int] = None
    species_name: str = ""
    species_tvk: Optional[str] = None
    common_name: Optional[str] = None
    order_name: Optional[str] = None
    family: Optional[str] = None
    subfamily: Optional[str] = None
    date: str = ""
    grid_ref: Optional[str] = None
    vice_county: Optional[str] = None
    vc_number: Optional[int] = None
    site_name: Optional[str] = None
    recorder: Optional[str] = None
    determiner: Optional[str] = None
    source: Optional[str] = None  # iRecord, NBN, Email, etc.
    verification_status: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    def to_table_dict(self) -> Dict[str, Any]:
        """Convert to dict format expected by RecordsTableWidget."""
        return {
            'id': self.id,
            'species': self.species_name,
            'common': self.common_name or '',
            'date': self.date,
            'location': self.site_name or '',
            'gridRef': self.grid_ref or '',
            'vc': self.vc_number or '',
            'recorder': self.recorder or '',
            'source': self.source or 'Email',
            'verification': self.verification_status or 'Unconfirmed',
            'subfamily': self.subfamily or '',
        }


class RecordingSchemeModel:
    """
    Model for recording scheme CRUD operations.
    
    This model handles Create, Read, Update, Delete operations.
    For search queries and statistics, use RecordingSchemeRepository instead.
    
    Usage:
        model = RecordingSchemeModel(db)
        
        # Create
        record = SchemeRecord(species_name="Rutpela maculata", date="2024-06-15")
        new_id = model.create(record)
        
        # Read by ID
        record = model.get_by_id(new_id)
        
        # Update
        record.source = "iRecord"
        model.update(record)
        
        # Delete
        model.delete(new_id)
    """

    def __init__(self, db: DatabaseManager):
        self.db = db

    # =========================================================================
    # CREATE
    # =========================================================================

    def create(self, record: SchemeRecord) -> int:
        """
        Create a new recording scheme record.
        
        Args:
            record: SchemeRecord object (id will be ignored)
            
        Returns:
            The new record ID
        """
        now = datetime.now().isoformat()
        
        query = """
            INSERT INTO recording_scheme (
                species_name, species_tvk, common_name,
                order_name, family, subfamily,
                date, grid_ref, vice_county, vc_number, site_name,
                recorder, determiner, source, verification_status,
                created_at, updated_at
            ) VALUES (
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?
            )
        """
        
        params = (
            record.species_name,
            record.species_tvk,
            record.common_name,
            record.order_name,
            record.family,
            record.subfamily,
            record.date,
            record.grid_ref,
            record.vice_county,
            record.vc_number,
            record.site_name,
            record.recorder,
            record.determiner,
            record.source,
            record.verification_status,
            now,
            now
        )
        
        return self.db.execute_main_write(query, params)

    # =========================================================================
    # READ
    # =========================================================================

    def get_by_id(self, record_id: int) -> Optional[SchemeRecord]:
        """
        Get a single record by ID.
        
        Args:
            record_id: The record ID
            
        Returns:
            SchemeRecord object or None if not found
        """
        query = "SELECT * FROM recording_scheme WHERE id = ?"
        results = self.db.execute_main(query, (record_id,))
        
        if results:
            return self._row_to_record(results[0])
        return None

    # =========================================================================
    # UPDATE
    # =========================================================================

    def update(self, record: SchemeRecord) -> bool:
        """
        Update an existing record.
        
        Args:
            record: SchemeRecord object with id set
            
        Returns:
            True if updated, False if not found
        """
        if not record.id:
            return False
        
        now = datetime.now().isoformat()
        
        query = """
            UPDATE recording_scheme SET
                species_name = ?,
                species_tvk = ?,
                common_name = ?,
                order_name = ?,
                family = ?,
                subfamily = ?,
                date = ?,
                grid_ref = ?,
                vice_county = ?,
                vc_number = ?,
                site_name = ?,
                recorder = ?,
                determiner = ?,
                source = ?,
                verification_status = ?,
                updated_at = ?
            WHERE id = ?
        """
        
        params = (
            record.species_name,
            record.species_tvk,
            record.common_name,
            record.order_name,
            record.family,
            record.subfamily,
            record.date,
            record.grid_ref,
            record.vice_county,
            record.vc_number,
            record.site_name,
            record.recorder,
            record.determiner,
            record.source,
            record.verification_status,
            now,
            record.id
        )
        
        result = self.db.execute_main_write(query, params)
        return result > 0

    # =========================================================================
    # DELETE
    # =========================================================================

    def delete(self, record_id: int) -> bool:
        """
        Delete a record by ID.
        
        Args:
            record_id: The record ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        query = "DELETE FROM recording_scheme WHERE id = ?"
        result = self.db.execute_main_write(query, (record_id,))
        return result > 0

    # =========================================================================
    # HELPER
    # =========================================================================

    def _row_to_record(self, row) -> SchemeRecord:
        """Convert a database row to a SchemeRecord object."""
        def get_col(name, default=None):
            try:
                return row[name]
            except (IndexError, KeyError):
                return default

        return SchemeRecord(
            id=get_col('id'),
            species_name=get_col('species_name', ''),
            species_tvk=get_col('species_tvk'),
            common_name=get_col('common_name'),
            order_name=get_col('order_name'),
            family=get_col('family'),
            subfamily=get_col('subfamily'),
            date=get_col('date', ''),
            grid_ref=get_col('grid_ref'),
            vice_county=get_col('vice_county'),
            vc_number=get_col('vc_number'),
            site_name=get_col('site_name'),
            recorder=get_col('recorder'),
            determiner=get_col('determiner'),
            source=get_col('source'),
            verification_status=get_col('verification_status'),
            created_at=get_col('created_at'),
            updated_at=get_col('updated_at')
        )
