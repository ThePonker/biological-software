"""
Observation Model for Observatum V2.

Handles CRUD operations for the observations table.
Search and statistics delegate to ObservationRepository for consistency.

Updated for NBN Atlas / Darwin Core schema expansion (74 columns).

Usage:
    from src.models.observation import Observation, ObservationModel
    
    model = ObservationModel(db)
    obs = Observation(species_name="Rutpela maculata", date="2024-06-15")
    new_id = model.create(obs)
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime

from .database import DatabaseManager

# Try to import repository for delegation
try:
    from ..repositories import ObservationRepository
    HAS_REPOSITORY = True
except ImportError:
    HAS_REPOSITORY = False


@dataclass
class Observation:
    """
    Represents a single observation record.
    
    Supports full NBN Atlas / Darwin Core schema for iRecord imports (74 columns).
    """
    # Primary key
    id: Optional[int] = None
    
    # External identity
    irecord_id: Optional[int] = None
    record_key: Optional[str] = None
    external_key: Optional[str] = None
    event_id: Optional[str] = None
    collection_code: Optional[str] = None
    dataset_name: Optional[str] = None
    institution_code: Optional[str] = None
    source: Optional[str] = None
    
    # Species identification
    species_name: str = ""
    species_tvk: Optional[str] = None
    common_name: Optional[str] = None
    order_name: Optional[str] = None
    family: Optional[str] = None
    kingdom: Optional[str] = None  # NEW
    taxon_group: Optional[str] = None  # NEW
    taxon_rank: Optional[str] = None
    identification_qualifier: Optional[str] = None  # cf., agg., etc.
    identification_remarks: Optional[str] = None
    recorder_certainty: Optional[str] = None  # NEW - Certain, Likely, etc.
    
    # Date
    date: str = ""  # ISO format YYYY-MM-DD
    date_type: str = "D"  # D=Day, O=Month, Y=Year
    
    # Location - grid reference
    grid_ref: Optional[str] = None
    grid_precision: Optional[int] = None
    vice_county: Optional[str] = None
    vc_number: Optional[int] = None
    site_name: Optional[str] = None
    site_name_local: Optional[str] = None
    
    # Location - coordinates
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    geodetic_datum: Optional[str] = None  # WGS84, OSGB36, etc.
    location_id: Optional[str] = None
    location_remarks: Optional[str] = None
    georeference_verification_status: Optional[str] = None
    
    # People
    recorder: Optional[str] = None
    determiner: Optional[str] = None
    verifier: Optional[str] = None
    verified_on: Optional[str] = None
    
    # Occurrence details
    sex: Optional[str] = None
    stage: Optional[str] = None
    quantity: int = 1
    individual_count: Optional[int] = None
    organism_quantity: Optional[str] = None
    organism_quantity_type: Optional[str] = None
    zero_abundance: int = 0  # NEW
    method: Optional[str] = None  # sampling protocol
    basis_of_record: Optional[str] = "HumanObservation"
    occurrence_status: Optional[str] = "present"
    
    # Notes and comments
    comment: Optional[str] = None
    internal_notes: Optional[str] = None
    sample_comment: Optional[str] = None
    biotope: Optional[str] = None
    
    # Verification
    verification_status: Optional[str] = None
    verification_status_2: Optional[str] = None
    automated_checks: Optional[str] = None  # NEW
    
    # Record management
    record_type: Optional[str] = "Personal"  # Personal or Commercial
    project_name: Optional[str] = None
    client: Optional[str] = None
    embargo_status: Optional[str] = None
    embargo_until: Optional[str] = None
    
    # Metadata
    licence: Optional[str] = None
    rights_holder: Optional[str] = None
    images: Optional[str] = None
    sensitive: int = 0
    sensitive_site: Optional[str] = None  # NEW
    sensitive_output_map_ref: Optional[str] = None  # NEW
    input_on_date: Optional[str] = None
    last_edited_date: Optional[str] = None
    
    # Sync management
    sync_status: Optional[str] = "active"  # active, excluded, pending
    never_upload_to_irecord: int = 0

    # Import tracking
    import_notes: Optional[str] = None

    # iRecord sync
    observatum_key: Optional[str] = None
    irecord_key: Optional[str] = None
    last_synced: Optional[str] = None

    # Timestamps
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    synced_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class ObservationModel:
    """
    Model for observation CRUD operations.
    
    Search and stats methods delegate to ObservationRepository.
    """

    def __init__(self, db: DatabaseManager):
        self.db = db
        self._repo = None
        
        # Try to create repository for delegation
        if HAS_REPOSITORY:
            try:
                self._repo = ObservationRepository()
            except Exception as e:
                print(f"[observation] __init__: {e}")  # I7: was silent

    # =========================================================================
    # CREATE
    # =========================================================================

    def _generate_observatum_key(self) -> str:
        """Generate a unique observatum key for syncing with iRecord.
        
        Format: OBS-{initials}-{YYYYMMDD}-{sequence}
        Example: OBS-WJH-20250103-0001
        """
        from PySide6.QtCore import QSettings
        from ..core.config import Settings, Defaults
        
        settings = QSettings()
        initials = settings.value(Settings.USER_INITIALS, Defaults.USER_INITIALS) or 'USR'
        date_str = datetime.now().strftime('%Y%m%d')
        
        # Find the next sequence number for today
        prefix = f'OBS-{initials}-{date_str}-'
        query = """
            SELECT observatum_key FROM observations
            WHERE observatum_key LIKE ?
            ORDER BY observatum_key DESC
            LIMIT 1
        """
        result = self.db.execute_main(query, (f'{prefix}%',))
        
        if result and len(result) > 0 and result[0]['observatum_key']:
            last_key = result[0]['observatum_key']
            try:
                last_seq = int(last_key.split('-')[-1])
                next_seq = last_seq + 1
            except (ValueError, IndexError):
                next_seq = 1
        else:
            next_seq = 1
        
        return f'{prefix}{next_seq:06d}'
    
    def create(self, observation: Observation) -> int:
        """Create a new observation record."""
        now = datetime.now().isoformat()

        query = """
            INSERT INTO observations (
                irecord_id, record_key, external_key, event_id,
                collection_code, dataset_name, institution_code, source,
                species_name, species_tvk, common_name, order_name, family,
                kingdom, taxon_group, taxon_rank,
                identification_qualifier, identification_remarks, recorder_certainty,
                date, date_type,
                grid_ref, grid_precision, vice_county, vc_number,
                site_name, site_name_local,
                latitude, longitude, geodetic_datum, location_id, location_remarks,
                georeference_verification_status,
                recorder, determiner, verifier, verified_on,
                sex, stage, quantity, individual_count,
                organism_quantity, organism_quantity_type, zero_abundance,
                method, basis_of_record, occurrence_status,
                comment, internal_notes, sample_comment, biotope,
                verification_status, verification_status_2, automated_checks,
                record_type, project_name, client, embargo_status, embargo_until,
                licence, rights_holder, images, sensitive,
                sensitive_site, sensitive_output_map_ref,
                input_on_date, last_edited_date,
                sync_status, never_upload_to_irecord,
                observatum_key,
                created_at, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?,
                ?, ?, ?, ?,
                ?, ?,
                ?, ?, ?, ?, ?,
                ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?,
                ?, ?,
                ?, ?,
                ?,
                ?, ?
            )
        """

        observatum_key = self._generate_observatum_key()

        params = (
            # External identity (8)
            observation.irecord_id,
            observation.record_key,
            observation.external_key,
            observation.event_id,
            observation.collection_code,
            observation.dataset_name,
            observation.institution_code,
            observation.source,
            # Species identification (13)
            observation.species_name,
            observation.species_tvk,
            observation.common_name,
            observation.order_name,
            observation.family,
            observation.kingdom,
            observation.taxon_group,
            observation.taxon_rank,
            observation.identification_qualifier,
            observation.identification_remarks,
            observation.recorder_certainty,
            # Date (2)
            observation.date,
            observation.date_type,
            # Location - grid (6)
            observation.grid_ref,
            observation.grid_precision,
            observation.vice_county,
            observation.vc_number,
            observation.site_name,
            observation.site_name_local,
            # Location - coordinates (6)
            observation.latitude,
            observation.longitude,
            observation.geodetic_datum,
            observation.location_id,
            observation.location_remarks,
            observation.georeference_verification_status,
            # People (4)
            observation.recorder,
            observation.determiner,
            observation.verifier,
            observation.verified_on,
            # Occurrence (12)
            observation.sex,
            observation.stage,
            observation.quantity,
            observation.individual_count,
            observation.organism_quantity,
            observation.organism_quantity_type,
            observation.zero_abundance,
            observation.method,
            observation.basis_of_record,
            observation.occurrence_status,
            # Notes (4)
            observation.comment,
            observation.internal_notes,
            observation.sample_comment,
            observation.biotope,
            # Verification (3)
            observation.verification_status,
            observation.verification_status_2,
            observation.automated_checks,
            # Record management (5)
            observation.record_type,
            observation.project_name,
            observation.client,
            observation.embargo_status,
            observation.embargo_until,
            # Metadata (8)
            observation.licence,
            observation.rights_holder,
            observation.images,
            observation.sensitive,
            observation.sensitive_site,
            observation.sensitive_output_map_ref,
            observation.input_on_date,
            observation.last_edited_date,
            # Sync (2)
            observation.sync_status,
            observation.never_upload_to_irecord,
            # Timestamps (2)
            observatum_key,
            now,  # created_at
            now,  # updated_at
        )

        result = self.db.execute_main_write(query, params)
        return result

    # =========================================================================
    # READ
    # =========================================================================

    def get_by_id(self, observation_id: int) -> Optional[Observation]:
        """Get a single observation by ID."""
        query = "SELECT * FROM observations WHERE id = ?"
        results = self.db.execute_main(query, (observation_id,))
        if results and len(results) > 0:
            return self._row_to_observation(results[0])
        return None

    def get_by_irecord_id(self, irecord_id: int) -> Optional[Observation]:
        """Get observation by iRecord ID."""
        query = "SELECT * FROM observations WHERE irecord_id = ?"
        results = self.db.execute_main(query, (irecord_id,))
        if results and len(results) > 0:
            return self._row_to_observation(results[0])
        return None

    def get_all(self, limit: int = 1000, offset: int = 0) -> List[Observation]:
        """Get all observations with pagination."""
        query = "SELECT * FROM observations ORDER BY date DESC LIMIT ? OFFSET ?"
        results = self.db.execute_main(query, (limit, offset))
        return [self._row_to_observation(row) for row in results]

    # =========================================================================
    # UPDATE
    # =========================================================================

    def update(self, observation: Observation) -> bool:
        """Update an existing observation."""
        if not observation.id:
            raise ValueError("Cannot update observation without ID")

        now = datetime.now().isoformat()

        query = """
            UPDATE observations SET
                irecord_id = ?, record_key = ?, external_key = ?, event_id = ?,
                collection_code = ?, dataset_name = ?, institution_code = ?, source = ?,
                species_name = ?, species_tvk = ?, common_name = ?, order_name = ?, family = ?,
                kingdom = ?, taxon_group = ?, taxon_rank = ?,
                identification_qualifier = ?, identification_remarks = ?, recorder_certainty = ?,
                date = ?, date_type = ?,
                grid_ref = ?, grid_precision = ?, vice_county = ?, vc_number = ?,
                site_name = ?, site_name_local = ?,
                latitude = ?, longitude = ?, geodetic_datum = ?, location_id = ?, location_remarks = ?,
                georeference_verification_status = ?,
                recorder = ?, determiner = ?, verifier = ?, verified_on = ?,
                sex = ?, stage = ?, quantity = ?, individual_count = ?,
                organism_quantity = ?, organism_quantity_type = ?, zero_abundance = ?,
                method = ?, basis_of_record = ?, occurrence_status = ?,
                comment = ?, internal_notes = ?, sample_comment = ?, biotope = ?,
                verification_status = ?, verification_status_2 = ?, automated_checks = ?,
                record_type = ?, project_name = ?, client = ?, embargo_status = ?, embargo_until = ?,
                licence = ?, rights_holder = ?, images = ?, sensitive = ?,
                sensitive_site = ?, sensitive_output_map_ref = ?,
                input_on_date = ?, last_edited_date = ?,
                sync_status = ?, never_upload_to_irecord = ?,
                irecord_key = ?, last_synced = ?, observatum_key = ?,
                updated_at = ?
            WHERE id = ?
        """

        params = (
            # External identity
            observation.irecord_id,
            observation.record_key,
            observation.external_key,
            observation.event_id,
            observation.collection_code,
            observation.dataset_name,
            observation.institution_code,
            observation.source,
            # Species identification
            observation.species_name,
            observation.species_tvk,
            observation.common_name,
            observation.order_name,
            observation.family,
            observation.kingdom,
            observation.taxon_group,
            observation.taxon_rank,
            observation.identification_qualifier,
            observation.identification_remarks,
            observation.recorder_certainty,
            # Date
            observation.date,
            observation.date_type,
            # Location - grid
            observation.grid_ref,
            observation.grid_precision,
            observation.vice_county,
            observation.vc_number,
            observation.site_name,
            observation.site_name_local,
            # Location - coordinates
            observation.latitude,
            observation.longitude,
            observation.geodetic_datum,
            observation.location_id,
            observation.location_remarks,
            observation.georeference_verification_status,
            # People
            observation.recorder,
            observation.determiner,
            observation.verifier,
            observation.verified_on,
            # Occurrence
            observation.sex,
            observation.stage,
            observation.quantity,
            observation.individual_count,
            observation.organism_quantity,
            observation.organism_quantity_type,
            observation.zero_abundance,
            observation.method,
            observation.basis_of_record,
            observation.occurrence_status,
            # Notes
            observation.comment,
            observation.internal_notes,
            observation.sample_comment,
            observation.biotope,
            # Verification
            observation.verification_status,
            observation.verification_status_2,
            observation.automated_checks,
            # Record management
            observation.record_type,
            observation.project_name,
            observation.client,
            observation.embargo_status,
            observation.embargo_until,
            # Metadata
            observation.licence,
            observation.rights_holder,
            observation.images,
            observation.sensitive,
            observation.sensitive_site,
            observation.sensitive_output_map_ref,
            observation.input_on_date,
            observation.last_edited_date,
            # Sync
            observation.sync_status,
            observation.never_upload_to_irecord,
            observation.irecord_key,
            observation.last_synced,
            observation.observatum_key,
            # Timestamps
            now,
            observation.id,
        )

        result = self.db.execute_main_write(query, params)
        return result > 0

    # =========================================================================
    # DELETE
    # =========================================================================

    def delete(self, observation_id: int) -> bool:
        """Delete an observation by ID."""
        query = "DELETE FROM observations WHERE id = ?"
        result = self.db.execute_main_write(query, (observation_id,))
        return result > 0

    # =========================================================================
    # BACKWARD-COMPATIBLE METHODS (delegate to repository)
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get quick stats. Delegates to repository."""
        if self._repo:
            stats = self._repo.get_quick_stats()
            return {
                'total_species': stats.get('total_species', 0),
                'total_records': stats.get('total_records', 0),
                'this_year_species': stats.get('this_year_species', 0),
                'this_year_records': stats.get('this_year_records', 0),
                'last_month_records': stats.get('last_month_records', 0)
            }
        return {'total_species': 0, 'total_records': 0, 'this_year_species': 0, 'this_year_records': 0}

    def get_species_record_count(self, species_tvk: str) -> int:
        """Get the count of records for a specific species by TVK."""
        if not species_tvk:
            return 0
        try:
            query = "SELECT COUNT(*) FROM observations WHERE species_tvk = ?"
            results = self.db.execute_main(query, (species_tvk,))
            if results and results[0]:
                return results[0][0] if isinstance(results[0], (list, tuple)) else results[0]['COUNT(*)']
            return 0
        except Exception as e:
            print(f"Error getting species record count: {e}")
            return 0

    def get_recent_new_species(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent first records. Delegates to repository."""
        if self._repo:
            results = self._repo.get_new_species_first_records(limit=limit)
            return [
                {
                    'species_name': r.get('species_name', ''),
                    'common_name': r.get('common_name', ''),
                    'species_tvk': r.get('species_tvk', ''),
                    'first_date': r.get('date', ''),
                    'date': r.get('date', ''),
                    'site_name': r.get('site_name', ''),
                    'grid_ref': r.get('grid_ref', '')
                }
                for r in results
            ]
        return []

    def get_species_by_order(self, record_type: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Get species count by order. Delegates to repository."""
        if self._repo:
            results = self._repo.count_by_order(limit=limit)
            return [{'label': r.get('order_name', ''), 'value': r.get('count', 0)} for r in results]
        return []

    def get_top_families(self, limit: int = 5, record_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get top families. Delegates to repository."""
        if self._repo:
            results = self._repo.count_by_family(limit=limit)
            return [
                {
                    'family': r.get('family', ''),
                    'species': r.get('species_count', 0),
                    'records': r.get('record_count', 0)
                }
                for r in results
            ]
        return []

    def get_monthly_activity(self, year: Optional[int] = None, record_type: Optional[str] = None) -> List[int]:
        """Get monthly counts. Delegates to repository."""
        if self._repo:
            return self._repo.count_by_month()
        return [0] * 12

    def get_monthly_counts(self) -> List[int]:
        """Alias for get_monthly_activity."""
        return self.get_monthly_activity()

    def get_year_by_year_stats(self, record_type: Optional[str] = None) -> Dict[int, Dict[str, int]]:
        """Get yearly stats. Delegates to repository."""
        if self._repo:
            return self._repo.count_by_year()
        return {}

    def get_yearly_stats(self) -> Dict[int, Dict[str, int]]:
        """Alias for get_year_by_year_stats."""
        return self.get_year_by_year_stats()

    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count observations. Delegates to repository."""
        if self._repo:
            return self._repo.count_all()
        return 0

    # =========================================================================
    # HELPER
    # =========================================================================

    def _row_to_observation(self, row) -> Observation:
        """Convert a database row to an Observation object."""
        def get_col(name, default=None):
            try:
                return row[name]
            except (IndexError, KeyError):
                return default
        
        return Observation(
            # Primary key
            id=get_col('id'),
            # External identity
            irecord_id=get_col('irecord_id'),
            record_key=get_col('record_key'),
            external_key=get_col('external_key'),
            event_id=get_col('event_id'),
            collection_code=get_col('collection_code'),
            dataset_name=get_col('dataset_name'),
            institution_code=get_col('institution_code'),
            source=get_col('source'),
            # Species
            species_name=get_col('species_name', ''),
            species_tvk=get_col('species_tvk'),
            common_name=get_col('common_name'),
            order_name=get_col('order_name'),
            family=get_col('family'),
            kingdom=get_col('kingdom'),
            taxon_group=get_col('taxon_group'),
            taxon_rank=get_col('taxon_rank'),
            identification_qualifier=get_col('identification_qualifier'),
            identification_remarks=get_col('identification_remarks'),
            recorder_certainty=get_col('recorder_certainty'),
            # Date
            date=get_col('date', ''),
            date_type=get_col('date_type', 'D'),
            # Location - grid
            grid_ref=get_col('grid_ref'),
            grid_precision=get_col('grid_precision'),
            vice_county=get_col('vice_county'),
            vc_number=get_col('vc_number'),
            site_name=get_col('site_name'),
            site_name_local=get_col('site_name_local'),
            # Location - coordinates
            latitude=get_col('latitude'),
            longitude=get_col('longitude'),
            geodetic_datum=get_col('geodetic_datum'),
            location_id=get_col('location_id'),
            location_remarks=get_col('location_remarks'),
            georeference_verification_status=get_col('georeference_verification_status'),
            # People
            recorder=get_col('recorder'),
            determiner=get_col('determiner'),
            verifier=get_col('verifier'),
            verified_on=get_col('verified_on'),
            # Occurrence
            sex=get_col('sex'),
            stage=get_col('stage'),
            quantity=get_col('quantity', 1) or 1,
            individual_count=get_col('individual_count'),
            organism_quantity=get_col('organism_quantity'),
            organism_quantity_type=get_col('organism_quantity_type'),
            zero_abundance=get_col('zero_abundance', 0) or 0,
            method=get_col('method'),
            basis_of_record=get_col('basis_of_record'),
            occurrence_status=get_col('occurrence_status'),
            # Notes
            comment=get_col('comment'),
            internal_notes=get_col('internal_notes'),
            sample_comment=get_col('sample_comment'),
            biotope=get_col('biotope'),
            # Verification
            verification_status=get_col('verification_status'),
            verification_status_2=get_col('verification_status_2'),
            automated_checks=get_col('automated_checks'),
            # Record management
            record_type=get_col('record_type', 'Personal'),
            project_name=get_col('project_name'),
            client=get_col('client'),
            embargo_status=get_col('embargo_status'),
            embargo_until=get_col('embargo_until'),
            import_notes=get_col('import_notes'),
            # Metadata
            licence=get_col('licence'),
            rights_holder=get_col('rights_holder'),
            images=get_col('images'),
            sensitive=get_col('sensitive', 0) or 0,
            sensitive_site=get_col('sensitive_site'),
            sensitive_output_map_ref=get_col('sensitive_output_map_ref'),
            input_on_date=get_col('input_on_date'),
            last_edited_date=get_col('last_edited_date'),
            # Sync
            sync_status=get_col('sync_status'),
            never_upload_to_irecord=get_col('never_upload_to_irecord', 0) or 0,
            # Timestamps
            observatum_key=get_col('observatum_key'),
            irecord_key=get_col('irecord_key'),
            last_synced=get_col('last_synced'),
            created_at=get_col('created_at'),
            updated_at=get_col('updated_at'),
            synced_at=get_col('synced_at'),
        )
