"""
Specimen Model for Observatum V2.

Handles CRUD operations for the specimens table (Insect Collection).
For search and statistics, use SpecimenRepository instead.

Usage:
    from src.models.specimen import Specimen, SpecimenModel
    from src.repositories import SpecimenRepository
    
    # CRUD operations - use Model
    model = SpecimenModel(db)
    spec = Specimen(species_name="Rutpela maculata", date_collected="2024-06-15")
    new_id = model.create(spec)
    
    # Search and stats - use Repository
    repo = SpecimenRepository()
    results = repo.search(species_name="Rutpela")
    stats = repo.get_quick_stats()
"""

from typing import Dict, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class Specimen:
    """Represents a single specimen record."""
    id: Optional[int] = None
    specimen_code: Optional[str] = None
    species_name: str = ""
    species_tvk: Optional[str] = None
    common_name: Optional[str] = None
    order_name: Optional[str] = None
    family: Optional[str] = None
    subfamily: Optional[str] = None
    date_collected: str = ""
    grid_ref: Optional[str] = None
    vice_county: Optional[str] = None
    vc_number: Optional[int] = None
    site_name: Optional[str] = None
    site_name_local: Optional[str] = None  # Local site name (protected during sync)
    collector: Optional[str] = None
    determiner: Optional[str] = None
    sex: Optional[str] = None
    preparation_type: Optional[str] = None
    storage_location: Optional[str] = None
    drawer_unit: Optional[str] = None
    condition: Optional[str] = None
    label_data: Optional[str] = None
    notes: Optional[str] = None
    import_notes: Optional[str] = None
    observation_id: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class SpecimenModel:
    """
    Model for specimen CRUD operations.
    
    This model handles Create, Read, Update, Delete operations.
    For search queries and statistics, use SpecimenRepository instead.
    
    Usage:
        model = SpecimenModel(db)
        
        # Create
        spec = Specimen(species_name="Rutpela maculata", date_collected="2024-06-15")
        new_id = model.create(spec)
        
        # Read by ID
        spec = model.get_by_id(new_id)
        
        # Update
        spec.notes = "Updated"
        model.update(spec)
        
        # Delete
        model.delete(new_id)
    """
    
    def __init__(self, db):
        """
        Initialize with database connection.
        
        Args:
            db: DatabaseManager instance
        """
        self.db = db
    
    # =========================================================================
    # CREATE
    # =========================================================================
    
    def create(self, specimen: Specimen) -> int:
        """
        Create a new specimen record.
        
        Args:
            specimen: Specimen object (id will be ignored)
            
        Returns:
            The new record ID
        """
        now = datetime.now().isoformat()
        
        query = """
            INSERT INTO specimens (
                specimen_code, species_name, species_tvk, common_name,
                order_name, family, subfamily,
                date_collected, grid_ref, vice_county, vc_number, site_name,
                collector, determiner, sex,
                preparation_type, storage_location, drawer_unit, condition,
                label_data, notes, import_notes, observation_id,
                created_at, updated_at
            ) VALUES (
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?
            )
        """
        
        params = (
            specimen.specimen_code,
            specimen.species_name,
            specimen.species_tvk,
            specimen.common_name,
            specimen.order_name,
            specimen.family,
            specimen.subfamily,
            specimen.date_collected,
            specimen.grid_ref,
            specimen.vice_county,
            specimen.vc_number,
            specimen.site_name,
            specimen.collector,
            specimen.determiner,
            specimen.sex,
            specimen.preparation_type,
            specimen.storage_location,
            specimen.drawer_unit,
            specimen.condition,
            specimen.label_data,
            specimen.notes,
            specimen.import_notes,
            specimen.observation_id,
            now,
            now
        )
        
        return self.db.execute_main_write(query, params)
    
    # =========================================================================
    # READ
    # =========================================================================
    
    def get_by_id(self, specimen_id: int) -> Optional[Specimen]:
        """
        Get a single specimen by ID.
        
        Args:
            specimen_id: The record ID
            
        Returns:
            Specimen object or None if not found
        """
        query = "SELECT * FROM specimens WHERE id = ?"
        results = self.db.execute_main(query, (specimen_id,))
        
        if results:
            return self._row_to_specimen(results[0])
        return None
    
    # =========================================================================
    # UPDATE
    # =========================================================================
    
    def update(self, specimen: Specimen) -> bool:
        """
        Update an existing specimen.
        
        Args:
            specimen: Specimen object with id set
            
        Returns:
            True if updated, False if not found
        """
        if not specimen.id:
            return False
        
        now = datetime.now().isoformat()
        
        query = """
            UPDATE specimens SET
                specimen_code = ?,
                species_name = ?,
                species_tvk = ?,
                common_name = ?,
                order_name = ?,
                family = ?,
                subfamily = ?,
                date_collected = ?,
                grid_ref = ?,
                vice_county = ?,
                vc_number = ?,
                site_name = ?,
                collector = ?,
                determiner = ?,
                sex = ?,
                preparation_type = ?,
                storage_location = ?,
                drawer_unit = ?,
                condition = ?,
                label_data = ?,
                notes = ?,
                import_notes = ?,
                observation_id = ?,
                updated_at = ?
            WHERE id = ?
        """
        
        params = (
            specimen.specimen_code,
            specimen.species_name,
            specimen.species_tvk,
            specimen.common_name,
            specimen.order_name,
            specimen.family,
            specimen.subfamily,
            specimen.date_collected,
            specimen.grid_ref,
            specimen.vice_county,
            specimen.vc_number,
            specimen.site_name,
            specimen.collector,
            specimen.determiner,
            specimen.sex,
            specimen.preparation_type,
            specimen.storage_location,
            specimen.drawer_unit,
            specimen.condition,
            specimen.label_data,
            specimen.notes,
            specimen.import_notes,
            specimen.observation_id,
            now,
            specimen.id
        )
        
        result = self.db.execute_main_write(query, params)
        return result > 0
    
    # =========================================================================
    # DELETE
    # =========================================================================
    
    def delete(self, specimen_id: int) -> bool:
        """
        Delete a specimen by ID.
        
        Args:
            specimen_id: The record ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        query = "DELETE FROM specimens WHERE id = ?"
        result = self.db.execute_main_write(query, (specimen_id,))
        return result > 0
    
    # =========================================================================
    # HELPER
    # =========================================================================
    
    def _row_to_specimen(self, row) -> Specimen:
        """Convert a database row to a Specimen object."""
        if row is None:
            return None
        
        def get_col(name, default=None):
            try:
                return row[name]
            except (IndexError, KeyError):
                return default
        
        return Specimen(
            id=get_col('id'),
            specimen_code=get_col('specimen_code'),
            species_name=get_col('species_name', ''),
            species_tvk=get_col('species_tvk'),
            common_name=get_col('common_name'),
            order_name=get_col('order_name'),
            family=get_col('family'),
            subfamily=get_col('subfamily'),
            date_collected=get_col('date_collected', ''),
            grid_ref=get_col('grid_ref'),
            vice_county=get_col('vice_county'),
            vc_number=get_col('vc_number'),
            site_name=get_col('site_name'),
            collector=get_col('collector'),
            determiner=get_col('determiner'),
            sex=get_col('sex'),
            preparation_type=get_col('preparation_type'),
            storage_location=get_col('storage_location'),
            drawer_unit=get_col('drawer_unit'),
            condition=get_col('condition'),
            label_data=get_col('label_data'),
            notes=get_col('notes'),
            import_notes=get_col('import_notes'),
            observation_id=get_col('observation_id'),
            created_at=get_col('created_at'),
            updated_at=get_col('updated_at')
        )
