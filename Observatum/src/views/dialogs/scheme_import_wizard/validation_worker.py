"""
Validation Worker for Recording Scheme Import Wizard.
PANDAS REFACTOR: Uses vectorized operations for fast validation.

Handles iRecord, NBN Atlas, and generic CSV imports with
different validation rules and column mappings for each.
"""
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import paths  # noqa: F401  (sets up the suite paths)
from pathlib import Path
from typing import Optional, Dict, List, Any

import pandas as pd
from PySide6.QtCore import QThread, Signal


def _find_vc_database() -> Optional[str]:
    """Find the Vice County lookup database."""
    candidates = []
    try:
        from PySide6.QtCore import QSettings
        settings = QSettings()
        custom_path = settings.value("database/vc_lookup_path")
        if custom_path:
            candidates.append(Path(custom_path))
    except Exception:
        pass

    try:
        this_file = Path(__file__).resolve()
        candidates.append(this_file.parent.parent.parent.parent.parent / "data" / "vc_lookup.db")
        candidates.append(this_file.parent.parent.parent.parent / "data" / "vc_lookup.db")
    except Exception:
        pass

    cwd = Path(os.getcwd())
    candidates.append(cwd / "data" / "vc_lookup.db")
    candidates.append(cwd / "src" / "data" / "vc_lookup.db")

    if sys.path:
        candidates.append(Path(sys.path[0]) / "data" / "vc_lookup.db")

    candidates.append(Path("data") / "vc_lookup.db")

    for candidate in candidates:
        try:
            if candidate and candidate.exists():
                return str(candidate)
        except Exception:
            continue

    return None


class SchemeImportMode(Enum):
    """Import mode selection for Recording Scheme."""
    IRECORD = "irecord"
    NBN_ATLAS = "nbn_atlas"
    GENERIC_CSV = "generic_csv"


def _safe_get(row_data, key, default=None):
    """Safely get value from pandas Series, converting NaN to None."""
    val = row_data.get(key, default)
    if val is None:
        return default
    if pd.isna(val):
        return default
    return val

def _safe_int(row_data, key):
    """Safely get integer value, returning None for NaN/empty."""
    val = row_data.get(key)
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None

def _safe_float(row_data, key):
    """Safely get float value, returning None for NaN/empty."""
    val = row_data.get(key)
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None

def _safe_str(row_data, key, default=""):
    """Safely get string value, returning default for NaN/None."""
    val = row_data.get(key, default)
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return default
    return str(val) if val else default


from ..row_status import RowStatus  # noqa: F401  (I9: one copy; re-exported for the mixins)
from shared.species_lookup import lookup_names
from shared.species_lookup_entries import entries


# iRecord column names (for auto-detection)
IRECORD_COLUMNS = {
    'ID', 'RecordKey', 'External key', 'Source', 'Rank', 'Taxon',
    'Common name', 'Taxon group', 'Kingdom', 'Order', 'Family',
    'TaxonVersionKey', 'Site name', 'Sensitive site', 'Original map ref',
    'Latitude', 'Longitude', 'Projection (input)', 'Precision',
    'Output map ref', 'Projection (output)', 'Sensitive output map ref',
    'Biotope', 'VC number', 'Vice County', 'Date interpreted',
    'Date from', 'Date to', 'Date type', 'Sample method', 'Recorder',
    'Determiner', 'Recorder certainty', 'Sex', 'Stage',
    'Count of sex or stage', 'Zero abundance', 'Sensitive', 'Comment',
    'Sample comment', 'Images', 'Input on date', 'Last edited on date',
    'Verification status 1', 'Verification status 2', 'Query', 'Verifier',
    'Verified on', 'Licence', 'Automated checks'
}

# NBN Atlas column names (for auto-detection)
# Supports both human-readable and Darwin Core formats
NBN_ATLAS_COLUMNS = {
    # Darwin Core format (standard NBN Atlas download)
    'recordID', 'occurrenceID', 'eventID', 'catalogNumber', 'collectionCode',
    'scientificName', 'scientificNameAuthorship', 'taxonID', 'taxonRemarks',
    'identificationRemarks', 'identifiedBy', 'identificationVerificationStatus',
    'kingdom', 'phylum', 'class', 'order', 'family', 'genus',
    'specificEpithet', 'infraspecificEpithet',
    'eventDate', 'eventTime', 'verbatimEventDate', 'day', 'month', 'year', 'eventDateEnd',
    'locationID', 'gridReference', 'locality', 'county', 'countryCode',
    'decimalLatitude', 'decimalLongitude', 'coordinateUncertaintyInMeters',
    'georeferenceVerificationStatus', 'georeferenceRemarks',
    'basisOfRecord', 'occurrenceStatus', 'occurrenceRemarks', 'vitality',
    'individualCount', 'organismQuantity', 'organismQuantityType',
    'sex', 'lifeStage', 'behavior', 'preparations',
    'datasetID', 'datasetName', 'institutionCode',
    'dcterms:license', 'dcterms:rightsHolder',
    # Human-readable format (alternative NBN Atlas format)
    'NBN Atlas record ID', 'Occurrence ID', 'Licence', 'rightsHolder',
    'Scientific name', 'Taxon author', 'Common name', 'Species ID (TVK)',
    'Event Date', 'Grid reference', 'Locality', 'Country',
    'Latitude (WGS84)', 'Longitude (WGS84)', 'Coordinate Uncertainty (m)',
    'Recorder', 'Determiner', 'Individual count', 'Sex', 'Life stage',
    'Identification verification status', 'Basis of Record',
    'Dataset name', 'Institution code', 'Kingdom', 'Phylum', 'Class',
    'Order', 'Family', 'Genus'
}


@dataclass
class SchemeImportRow:
    """A single row from the import file with validation results."""
    row_number: int
    raw_data: Dict[str, str]
    status: RowStatus = RowStatus.PENDING
    error_message: str = ""
    warnings: List[str] = field(default_factory=list)
    species_name: str = ""
    species_tvk: str = ""
    common_name: str = ""
    order_name: str = ""
    family: str = ""
    subfamily: str = ""
    superfamily: str = ""
    taxon_group: str = ""
    taxonomic_sort_key: Optional[int] = None
    date: str = ""
    date_type: str = ""
    grid_ref: str = ""
    grid_precision: str = ""
    vc_number: Optional[int] = None
    vice_county: str = ""
    site_name: str = ""
    import_notes: str = ""
    irecord_id: str = ""
    recorder: str = ""
    latitude: str = ""
    longitude: str = ""
    verification_status: str = ""
    record_key: str = ""

    # Import mode context
    source_type: str = ""  # 'iRecord', 'NBN Atlas', 'Generic'

    # Core identification
    irecord_id: Optional[int] = None
    nbn_atlas_id: str = ""
    occurrence_id: str = ""
    record_key: str = ""
    external_key: str = ""
    event_id: str = ""

    # Dataset info
    collection_code: str = ""
    dataset_name: str = ""
    institution_code: str = ""
    source: str = ""

    # Species fields
    species_name: str = ""
    species_tvk: str = ""
    common_name: str = ""
    taxon_author: str = ""
    order_name: str = ""
    family: str = ""
    subfamily: str = ""
    genus: str = ""
    kingdom: str = ""
    phylum: str = ""
    class_name: str = ""
    taxon_group: str = ""
    superfamily: str = ""
    taxonomic_sort_key: Optional[int] = None
    taxon_rank: str = ""
    identification_qualifier: str = ""
    identification_remarks: str = ""
    recorder_certainty: str = ""

    # Date
    date: str = ""
    date_type: str = "D"

    # Location - grid
    grid_ref: str = ""
    grid_precision: Optional[int] = None
    vice_county: str = ""
    vc_number: Optional[int] = None
    site_name: str = ""
    site_name_local: str = ""
    country: str = ""
    state_province: str = ""

    # Location - coordinates
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    geodetic_datum: str = ""
    coordinate_uncertainty: Optional[int] = None
    location_id: str = ""
    location_remarks: str = ""
    georeference_verification_status: str = ""
    sensitive_site: str = ""
    sensitive_output_map_ref: str = ""

    # Occurrence details
    recorder: str = ""
    determiner: str = ""
    sex: str = ""
    stage: str = ""
    quantity: int = 1
    individual_count: Optional[int] = None
    organism_quantity: str = ""
    organism_quantity_type: str = ""
    zero_abundance: int = 0
    method: str = ""
    biotope: str = ""
    sensitive: int = 0
    occurrence_status: str = ""

    # Comments
    comment: str = ""
    sample_comment: str = ""
    occurrence_remarks: str = ""
    internal_notes: str = ""

    # Verification
    verification_status: str = ""
    verification_status_2: str = ""
    verifier: str = ""
    verified_on: str = ""
    automated_checks: str = ""
    query: str = ""

    # Media/Metadata
    images: str = ""
    input_on_date: str = ""
    last_edited_date: str = ""
    licence: str = ""
    basis_of_record: str = ""
    rights_holder: str = ""

    # Duplicate tracking
    is_duplicate: bool = False
    existing_record_id: Optional[int] = None
    import_notes: str = ""

    def add_warning(self, warning: str):
        """Add a warning message."""
        if warning and warning not in self.warnings:
            self.warnings.append(warning)


class SchemeValidationWorker(QThread):
    """
    Worker thread for validating recording scheme import data.
    
    PANDAS REFACTOR: Uses batch operations for species and VC lookups.
    """
    progress = Signal(int, int)  # current, total
    row_validated = Signal(int, object)  # row_index, SchemeImportRow
    counts_updated = Signal(int, int, int)  # valid, warning, error
    finished = Signal(list)  # List[SchemeImportRow]

    def __init__(
        self,
        rows: List[SchemeImportRow],
        import_mode: SchemeImportMode,
        column_mapping: Dict[str, str] = None,
        uksi_model=None,
        vc_db_path: str = None,
        db_manager=None,
        parent=None
    ):
        super().__init__(parent)
        self.rows = rows
        self.import_mode = import_mode
        self.column_mapping = column_mapping or {}
        self.uksi_model = uksi_model
        self.vc_db_path = vc_db_path
        self.db_manager = db_manager

        self._vc_service = None
        self._cancelled = False

        # Live counters
        self.valid_count = 0
        self.warning_count = 0
        self.error_count = 0

    def cancel(self):
        self._cancelled = True

    def run(self):
        """
        Validate all rows using pandas batch operations.
        
        Process:
        1. Build DataFrame from raw data based on import mode
        2. Batch species lookup (exact match -> fuzzy)
        3. Batch VC lookup from grid refs
        4. Check duplicates
        5. Build final SchemeImportRow objects
        """
        db_path = self.vc_db_path or _find_vc_database()

        if db_path:
            try:
                from src.services.vc_lookup_service import VCLookupService
                self._vc_service = VCLookupService(db_path)
            except ImportError:
                try:
                    from services.vc_lookup_service import VCLookupService
                    self._vc_service = VCLookupService(db_path)
                except ImportError:
                    self._vc_service = None

        total = len(self.rows)
        if total == 0:
            self.finished.emit([])
            return

        # Step 1: Build DataFrame based on import mode
        self.progress.emit(int(total * 0.05), total)
        df = self._build_dataframe()

        if self._cancelled:
            self.finished.emit([])
            return

        # Step 2: Batch species lookup
        self.progress.emit(int(total * 0.20), total)
        df = self._batch_species_lookup(df)

        if self._cancelled:
            self.finished.emit([])
            return

        # Step 3: Batch VC lookup
        self.progress.emit(int(total * 0.30), total)
        df = self._batch_vc_lookup(df)

        # Enrich with sort key + superfamily from UKSI
        df = self._enrich_sort_and_superfamily(df)

        if self._cancelled:
            self.finished.emit([])
            return

        # Step 4: Check duplicates
        self.progress.emit(int(total * 0.50), total)
        df = self._batch_duplicate_check(df)

        if self._cancelled:
            self.finished.emit([])
            return

        # Step 5: Build final SchemeImportRow objects
        self.progress.emit(int(total * 0.70), total)
        validated_rows = self._build_import_rows(df)

        if self._vc_service:
            try:
                self._vc_service.close()
            except Exception:
                pass

        # Emit final counts
        self.counts_updated.emit(self.valid_count, self.warning_count, self.error_count)

        # Emit 90% - main thread will update to 100% during table population
        self.progress.emit(int(total * 0.90), total)
        self.finished.emit(validated_rows)

    def _build_dataframe(self) -> pd.DataFrame:
        """Build DataFrame based on import mode."""
        data = []

        for i, row in enumerate(self.rows):
            raw = row.raw_data

            if self.import_mode == SchemeImportMode.IRECORD:
                data.append(self._extract_irecord_data(i, row.row_number, raw))
            elif self.import_mode == SchemeImportMode.NBN_ATLAS:
                data.append(self._extract_nbn_data(i, row.row_number, raw))
            else:
                data.append(self._extract_generic_data(i, row.row_number, raw))

        return pd.DataFrame(data)

    def _extract_irecord_data(self, idx: int, row_num: int, raw: Dict[str, str]) -> Dict[str, Any]:
        """Extract data from iRecord format."""
        # Get grid ref - prefer sensitive if available
        grid_ref = raw.get('Output map ref', '').strip() or raw.get('Original map ref', '').strip()
        sensitive_grid = raw.get('Sensitive output map ref', '').strip()
        if sensitive_grid:
            grid_ref = sensitive_grid

        return {
            "row_idx": idx,
            "row_number": row_num,
            "source_type": "iRecord",
            "source": raw.get('Source', '').strip() or 'iRecord',
            # IDs
            "irecord_id": self._parse_int(raw.get('ID', '')),
            "record_key": raw.get('RecordKey', '').strip(),
            "external_key": raw.get('External key', '').strip(),
            # Species
            "species_name": raw.get('Taxon', '').strip(),
            "species_tvk": raw.get('TaxonVersionKey', '').strip(),
            "common_name": raw.get('Common name', '').strip(),
            "taxon_group": raw.get('Taxon group', '').strip(),
            "kingdom": raw.get('Kingdom', '').strip(),
            "phylum": raw.get('Phylum', '').strip(),
            "class_name": raw.get('Class', '').strip(),
            "order_name": raw.get('Order', '').strip(),
            "family": raw.get('Family', '').strip(),
            "subfamily": raw.get('Subfamily', '').strip(),
            "genus": raw.get('Genus', '').strip(),
            "taxon_author": raw.get('Species authority', '').strip() or raw.get('Taxon author', '').strip(),
            "taxon_rank": raw.get('Rank', '').strip(),
            # Date
            "date": self._parse_irecord_date(raw),
            "date_type": raw.get('Date type', 'D').strip() or 'D',
            "_date_note": self._last_date_note,
            # Location
            "grid_ref": grid_ref.upper().replace(" ", "") if grid_ref else "",
            "site_name": raw.get('Site name', '').strip(),
            "sensitive_site": raw.get('Sensitive site', '').strip(),
            "grid_precision": self._parse_int(raw.get('Precision', '')),
            "latitude": self._parse_float(raw.get('Latitude', '')),
            "longitude": self._parse_float(raw.get('Longitude', '')),
            "geodetic_datum": raw.get('Projection (input)', '').strip(),
            "vc_number": self._parse_int(raw.get('VC number', '')),
            "vice_county": raw.get('Vice County', '').strip(),
            # People
            "recorder": raw.get('Recorder', '').strip(),
            "determiner": raw.get('Determiner', '').strip(),
            "recorder_certainty": raw.get('Recorder certainty', '').strip(),
            # Occurrence
            "sex": raw.get('Sex', '').strip(),
            "stage": raw.get('Stage', '').strip(),
            "quantity": self._parse_count(raw.get('Count of sex or stage', ''))[0] or 1,
            "organism_quantity": self._parse_count(raw.get('Count of sex or stage', ''))[1] or "",
            "zero_abundance": 1 if raw.get('Zero abundance', '').upper() == 'TRUE' else 0,
            "method": raw.get('Sample method', '').strip(),
            "sensitive": 1 if raw.get('Sensitive', '').upper() == 'TRUE' else 0,
            # Comments
            "comment": raw.get('Comment', '').strip(),
            "sample_comment": raw.get('Sample comment', '').strip(),
            "biotope": raw.get('Biotope', '').strip(),
            # Verification
            "verification_status": raw.get('Verification status 1', '').strip(),
            "verification_status_2": raw.get('Verification status 2', '').strip(),
            "verifier": raw.get('Verifier', '').strip(),
            "verified_on": raw.get('Verified on', '').strip(),
            "query": raw.get('Query', '').strip(),
            "automated_checks": raw.get('Automated checks', '').strip(),
            # Media/Metadata
            "images": raw.get('Images', '').strip(),
            "input_on_date": raw.get('Input on date', '').strip(),
            "last_edited_date": raw.get('Last edited on date', '').strip(),
            "licence": raw.get('Licence', '').strip(),
            # For batch processing
            "species_error": "",
            "species_warning": "",
            "vc_error": "",
            "vc_warning": "",
            "import_notes": "",
            "is_duplicate": False,
            "existing_record_id": None,
        }

    def _get_nbn_value(self, raw: Dict[str, str], *keys) -> str:
        """Get value trying multiple possible column names (Darwin Core and human-readable)."""
        for key in keys:
            val = raw.get(key, '').strip()
            if val:
                return val
        return ''

    def _extract_nbn_data(self, idx: int, row_num: int, raw: Dict[str, str]) -> Dict[str, Any]:
        """Extract data from NBN Atlas format (supports Darwin Core and human-readable columns)."""
        g = lambda *keys: self._get_nbn_value(raw, *keys)
        
        # Parse date - try multiple column names, fall back to year
        date_str = g('eventDate', 'Event Date', 'verbatimEventDate')
        if not date_str:
            date_str = g('year')
        if date_str:
            parsed_date = self._parse_date(date_str)
            _date_note = self._last_date_note
        else:
            parsed_date = ''
            _date_note = ''
        
        return {
            "row_idx": idx,
            "row_number": row_num,
            "source_type": "NBN Atlas",
            "_date_note": _date_note,
            "source": g('datasetName', 'Data provider', 'Dataset name') or 'NBN Atlas',
            # IDs
            "nbn_atlas_id": g('recordID', 'NBN Atlas record ID'),
            "occurrence_id": g('occurrenceID', 'Occurrence ID'),
            "event_id": g('eventID'),
            "dataset_name": g('datasetName', 'Dataset name'),
            "dataset_id": g('datasetID', 'Dataset ID'),
            "institution_code": g('institutionCode', 'Institution code'),
            "collection_code": g('collectionCode', 'Survey key'),
            # Species
            "species_name": g('scientificName', 'Scientific name'),
            "species_tvk": g('taxonID', 'Species ID (TVK)'),
            "common_name": g('Common name'),  # Darwin Core doesn't have common name
            "taxon_author": g('scientificNameAuthorship', 'Taxon author'),
            "taxon_rank": g('Taxon Rank'),
            "kingdom": g('kingdom', 'Kingdom'),
            "phylum": g('phylum', 'Phylum'),
            "class_name": g('class', 'Class'),
            "order_name": g('order', 'Order'),
            "family": g('family', 'Family'),
            "genus": g('genus', 'Genus'),
            # Date
            "date": parsed_date,
            "date_type": "D",
            # Location
            "grid_ref": g('gridReference', 'Grid reference').upper().replace(" ", ""),
            "site_name": g('locality', 'Locality'),
            "county": g('county'),
            "country": g('countryCode', 'Country'),
            "state_province": g('State/Province'),
            "latitude": self._parse_float(g('decimalLatitude', 'Latitude (WGS84)')),
            "longitude": self._parse_float(g('decimalLongitude', 'Longitude (WGS84)')),
            "coordinate_uncertainty": self._parse_int(g('coordinateUncertaintyInMeters', 'Coordinate Uncertainty (m)')),
            "vc_number": None,
            "vice_county": "",
            "location_id": g('locationID'),
            "georeference_verification_status": g('georeferenceVerificationStatus'),
            # People
            "recorder": g('Recorder'),  # Darwin Core doesn't have recorder directly
            "determiner": g('identifiedBy', 'Determiner'),
            # Occurrence
            "sex": g('sex', 'Sex'),
            "stage": g('lifeStage', 'Life stage'),
            "quantity": (self._parse_count(g('individualCount', 'Individual count'))[0]
                         or self._parse_count(g('organismQuantity'))[0] or 1),
            "individual_count": self._parse_count(g('individualCount', 'Individual count'))[0],
            "organism_quantity": g('organismQuantity'),
            "organism_quantity_type": g('organismQuantityType'),
            "occurrence_remarks": g('occurrenceRemarks', 'Occurrence remarks'),
            "occurrence_status": g('occurrenceStatus', 'Occurrence status'),
            "vitality": g('vitality', 'Vitality'),
            # Verification
            "verification_status": g('identificationVerificationStatus', 'Identification verification status'),
            "identification_remarks": g('identificationRemarks'),
            "basis_of_record": g('basisOfRecord', 'Basis of Record'),
            "licence": g('dcterms:license', 'Licence'),
            "rights_holder": g('dcterms:rightsHolder', 'rightsHolder'),
            # For batch processing
            "species_error": "",
            "species_warning": "",
            "vc_error": "",
            "vc_warning": "",
            "import_notes": "",
            "is_duplicate": False,
            "existing_record_id": None,
        }

    def _extract_generic_data(self, idx: int, row_num: int, raw: Dict[str, str]) -> Dict[str, Any]:
        """Extract data from generic CSV using column mapping."""
        mapping = self.column_mapping
        date_str = raw.get(mapping.get('date', ''), '').strip()
        if date_str:
            parsed_date = self._parse_date(date_str)
            _date_note = self._last_date_note
        else:
            parsed_date = ''
            _date_note = ''

        return {
            "row_idx": idx,
            "row_number": row_num,
            "source_type": "Generic",
            "_date_note": _date_note,
            "source": "CSV Import",
            # Species
            "species_name": raw.get(mapping.get('species_name', ''), '').strip(),
            "species_tvk": "",
            "common_name": "",
            # Date
            "date": parsed_date,
            "date_raw": date_str,  # Keep original for error messages
            "date_type": "D",
            # Location
            "grid_ref": raw.get(mapping.get('grid_ref', ''), '').strip().upper().replace(" ", ""),
            "site_name": raw.get(mapping.get('site_name', ''), '').strip(),
            "vc_number": None,
            "vice_county": "",
            # People
            "recorder": raw.get(mapping.get('recorder', ''), '').strip(),
            "determiner": raw.get(mapping.get('determiner', ''), '').strip(),
            # Occurrence
            "sex": raw.get(mapping.get('sex', ''), '').strip(),
            "stage": raw.get(mapping.get('stage', ''), '').strip(),
            "quantity": self._parse_count(raw.get(mapping.get('quantity', ''), ''))[0] or 1,
            "organism_quantity": self._parse_count(raw.get(mapping.get('quantity', ''), ''))[1] or "",
            "comment": raw.get(mapping.get('comment', ''), '').strip(),
            # For batch processing
            "species_error": "",
            "species_warning": "",
            "vc_error": "",
            "vc_warning": "",
            "import_notes": "",
            "is_duplicate": False,
            "existing_record_id": None,
        }

    def _batch_species_lookup(self, df: pd.DataFrame) -> pd.DataFrame:
        """Batch lookup species in UKSI."""
        # Initialize columns if not present
        for col in ["species_tvk", "common_name", "order_name", "family", "kingdom",
                    "phylum", "class_name", "genus", "subfamily",
                    "taxon_group", "taxon_rank", "species_error", "species_warning", "import_notes"]:
            if col not in df.columns:
                df[col] = ""

        if not self.uksi_model:
            # Mark rows that need lookup as warnings
            mask = (df["species_name"] != "") & (df["species_tvk"] == "")
            df.loc[mask, "species_warning"] = "UKSI lookup not available"
            return df

        # Get unique species that need lookup (have name but no TVK)
        needs_lookup = df[df["species_name"] != ""]["species_name"].unique().tolist()

        if not needs_lookup:
            return df

        # One rule set for all three wizards (shared/species_lookup.py): exact names and
        # synonyms; anything else is an error naming the closest UKSI names, to be confirmed
        # with Resolve Species or the Match Report.
        species_lookup = entries(lookup_names(needs_lookup, self.uksi_model,
                                              cancelled=lambda: self._cancelled))

        def apply_species(row):
            name = row["species_name"]
            if not name:  # No species name to lookup
                return row
            
            original_tvk = row.get("species_tvk", "")

            if name in species_lookup:
                result = species_lookup[name]
                if "error" in result:
                    row["species_error"] = result["error"]
                else:
                    new_tvk = result.get("tvk", "")
                    if original_tvk and new_tvk and original_tvk != new_tvk:
                        existing_notes = row.get("import_notes", "") or ""
                        tvk_note = f"TVK normalized: {original_tvk} -> {new_tvk}"
                        row["import_notes"] = f"{existing_notes}; {tvk_note}" if existing_notes else tvk_note
                    row["species_tvk"] = new_tvk
                    row["species_name"] = result["species_name"]      # UKSI's name (IMP-15)
                    if not row.get("common_name"):
                        row["common_name"] = result.get("common_name", "")
                    if not row.get("order_name"):
                        row["order_name"] = result.get("order_name", "")
                    if not row.get("family"):
                        row["family"] = result.get("family", "")
                    if not row.get("kingdom"):
                        row["kingdom"] = result.get("kingdom", "")
                    if not row.get("phylum"):
                        row["phylum"] = result.get("phylum", "")
                    if not row.get("class_name"):
                        row["class_name"] = result.get("class_name", "")
                    if not row.get("genus"):
                        row["genus"] = result.get("genus", "")
                    if not row.get("taxon_rank"):
                        row["taxon_rank"] = result.get("rank", "")
                    if result.get("warning"):
                        row["species_warning"] = result["warning"]
                    if result.get("import_notes"):
                        notes = row.get("import_notes", "") or ""
                        row["import_notes"] = (f"{notes}; {result['import_notes']}" if notes
                                               else result["import_notes"])
            return row

        df = df.apply(apply_species, axis=1)
        return df

    def _batch_vc_lookup(self, df: pd.DataFrame) -> pd.DataFrame:
        """Batch lookup Vice Counties from grid references."""
        # Initialize columns if not present
        for col in ["vc_number", "vice_county", "vc_error", "vc_warning"]:
            if col not in df.columns:
                if col == "vc_number":
                    df[col] = None
                else:
                    df[col] = ""

        if not self._vc_service:
            return df

        # Get unique grid refs that need VC lookup
        needs_lookup = df[
            (df["grid_ref"] != "") & 
            (df["vc_number"].isna() | (df["vc_number"] == 0) | (df["vc_number"] == ""))
        ]["grid_ref"].unique().tolist()

        if not needs_lookup:
            return df

        # Batch lookup
        if hasattr(self._vc_service, "get_vc_batch"):
            vc_lookup = self._vc_service.get_vc_batch(needs_lookup)
        else:
            # Fallback to individual lookups
            vc_lookup = {}
            total_grids = len(needs_lookup)
            for _gi, grid in enumerate(needs_lookup):
                if self._cancelled:
                    break
                if _gi % 200 == 0 and total_grids > 0:
                    _pct = 0.30 + (_gi / total_grids) * 0.20
                    self.progress.emit(int(len(self.rows) * _pct), len(self.rows))
                try:
                    is_valid, msg = self._vc_service.validate_grid_ref(grid)
                    if is_valid:
                        result = self._vc_service.get_vc_from_grid_ref(grid)
                        if result:
                            vc_lookup[grid] = {
                                "vc_number": result[0],
                                "vc_name": result[1],
                                "warning": "",
                                "error": ""
                            }
                        else:
                            vc_lookup[grid] = {
                                "vc_number": None,
                                "vc_name": "",
                                "warning": "Could not determine Vice County",
                                "error": ""
                            }
                    else:
                        vc_lookup[grid] = {
                            "vc_number": None,
                            "vc_name": "",
                            "warning": "",
                            "error": f"Invalid grid reference: {msg}"
                        }
                except Exception as e:
                    vc_lookup[grid] = {
                        "vc_number": None,
                        "vc_name": "",
                        "warning": "",
                        "error": f"VC lookup error: {str(e)}"
                    }

        # Apply VC lookup results to DataFrame
        def apply_vc(row):
            grid = row["grid_ref"]
            if not grid or (row.get("vc_number") and row["vc_number"] not in [None, 0, ""]):
                return row

            if grid in vc_lookup:
                result = vc_lookup[grid]
                if result.get("error"):
                    row["vc_error"] = result["error"]
                else:
                    row["vc_number"] = result.get("vc_number")
                    row["vice_county"] = result.get("vc_name", "")
                    if result.get("warning"):
                        row["vc_warning"] = result["warning"]
            return row

        df = df.apply(apply_vc, axis=1)
        return df

    def _enrich_sort_and_superfamily(self, df: pd.DataFrame) -> pd.DataFrame:
        """Enrich with taxonomic_sort_key and superfamily from UKSI (batch)."""
        from src.utils.constants import compute_taxonomic_sort_key

        if not self.uksi_model or not hasattr(self.uksi_model, 'db'):
            return df

        if 'superfamily' not in df.columns:
            df['superfamily'] = ''
        if 'taxonomic_sort_key' not in df.columns:
            df['taxonomic_sort_key'] = None

        # Batch: get unique TVKs and look them all up at once
        unique_tvks = df[df['species_tvk'].notna() & (df['species_tvk'] != '')]['species_tvk'].unique().tolist()
        if not unique_tvks:
            return df

        tvk_data = {}
        batch_size = 500
        for i in range(0, len(unique_tvks), batch_size):
            batch = unique_tvks[i:i+batch_size]
            placeholders = ','.join(['?' for _ in batch])
            try:
                results = self.uksi_model.db.execute_uksi(
                    f'SELECT tvk, sort_code, "order", superfamily FROM taxa WHERE tvk IN ({placeholders})',
                    tuple(batch)
                )
                for r in results:
                    tvk = r[0] if isinstance(r, (list, tuple)) else r['tvk']
                    sort_code = (r[1] if isinstance(r, (list, tuple)) else r['sort_code']) or 0
                    order_name = (r[2] if isinstance(r, (list, tuple)) else r['order']) or ''
                    superfamily = (r[3] if isinstance(r, (list, tuple)) else r['superfamily']) or ''
                    tvk_data[tvk] = {
                        'sort_key': compute_taxonomic_sort_key(order_name, sort_code),
                        'superfamily': superfamily
                    }
            except Exception as e:
                print(f"[validation_worker] _enrich_sort_and_superfamily: {e}")  # I7: was silent
            if i % 2000 == 0:
                self.progress.emit(int(len(self.rows) * (0.30 + (i / max(len(unique_tvks), 1)) * 0.10)), len(self.rows))

        # Apply lookup results
        for idx, row in df.iterrows():
            tvk = row.get('species_tvk', '')
            if tvk and tvk in tvk_data:
                df.at[idx, 'taxonomic_sort_key'] = tvk_data[tvk]['sort_key']
                df.at[idx, 'superfamily'] = tvk_data[tvk]['superfamily']

        return df

    def _batch_duplicate_check(self, df: pd.DataFrame) -> pd.DataFrame:
        """Find rows already held, and rows repeated within the file (9 Oct 2026, F35).

        Lookups are chunked and NOT swallowed: if one fails, every row is marked with the
        error, so nothing imports by default -- it used to carry on as though there were no
        duplicates, re-importing a whole NBN file. iRecord rows are also matched on
        record_key ('iBRC' + ID) for records held without their iRecord ID (35,104 scheme
        rows lost theirs to the byte-order-mark fault). A row repeating an earlier row's id
        within the same file is an error, not a second record.
        """
        from shared.import_core import chunked_select

        df["is_duplicate"] = False
        df["existing_record_id"] = None
        df["dup_error"] = ""
        if not self.db_manager:
            return df

        def present(col):
            if col not in df.columns:
                return pd.Series(False, index=df.index)
            return df[col].notna() & (df[col].astype(str).str.strip() != "")

        def mark(col, db_col, normalise=lambda v: v):
            if col not in df.columns:      # IMP-2: e.g. no nbn_atlas_id in an iRecord file --
                return                     # df.loc[...] raised KeyError and nothing imported
            m = present(col) & ~df["is_duplicate"]
            values = sorted({normalise(v) for v in df.loc[m, col]})
            if not values:
                return
            found = {}
            for r in chunked_select(self.db_manager,
                                    f"SELECT id, {db_col} FROM recording_scheme WHERE {db_col} IN ({{ph}})",
                                    values):
                rid = r[0] if isinstance(r, (list, tuple)) else r["id"]
                key = r[1] if isinstance(r, (list, tuple)) else r[db_col]
                found[normalise(key)] = rid
            for idx in df.index[m]:
                rid = found.get(normalise(df.at[idx, col]))
                if rid is not None:
                    df.at[idx, "is_duplicate"] = True
                    df.at[idx, "existing_record_id"] = rid

        def as_int(v):
            try:
                return int(float(v))
            except (TypeError, ValueError):
                return v

        try:
            mark("irecord_id", "irecord_id", as_int)
            mark("record_key", "record_key", lambda v: str(v).strip())
            mark("nbn_atlas_id", "nbn_atlas_id", lambda v: str(v).strip())
        except Exception as e:
            print(f"[SchemeValidation] duplicate check FAILED: {e}")
            df["dup_error"] = f"Duplicate check failed ({e}) -- not imported, to be safe"
            return df

        # The same record twice in one file
        for col, norm in (("irecord_id", as_int), ("nbn_atlas_id", lambda v: str(v).strip()),
                          ("record_key", lambda v: str(v).strip())):
            m = present(col)
            if not m.any():
                continue
            keys = df.loc[m, col].map(norm)
            repeated = keys.duplicated(keep="first")
            if repeated.any():
                first_row = {}
                for idx, k in keys.items():
                    first_row.setdefault(k, df.at[idx, "row_number"])
                for idx in keys.index[repeated]:
                    if not df.at[idx, "dup_error"]:
                        df.at[idx, "dup_error"] = (f"Same record as row {first_row[keys[idx]]} "
                                                   f"of this file ({col} {keys[idx]})")
        return df

    def _build_import_rows(self, df: pd.DataFrame) -> List[SchemeImportRow]:
        """Build final SchemeImportRow objects from DataFrame."""
        validated_rows = []

        total_rows = len(df)
        for row_num, (_, row_data) in enumerate(df.iterrows()):
            if row_num % 500 == 0:
                pct = 0.70 + (row_num / max(total_rows, 1)) * 0.20
                self.progress.emit(int(len(self.rows) * pct), len(self.rows))
                self.counts_updated.emit(self.valid_count, self.warning_count, self.error_count)
            idx = int(row_data["row_idx"])
            original_row = self.rows[idx]

            # Create new row with all fields populated
            validated_row = SchemeImportRow(
                row_number=int(row_data["row_number"]),
                raw_data=original_row.raw_data
            )

            # Copy all fields from DataFrame
            validated_row.source_type = row_data.get("source_type", "")
            validated_row.source = row_data.get("source", "")

            # IDs
            validated_row.irecord_id = _safe_int(row_data, "irecord_id")
            validated_row.nbn_atlas_id = row_data.get("nbn_atlas_id", "")
            validated_row.occurrence_id = row_data.get("occurrence_id", "")
            validated_row.record_key = row_data.get("record_key", "")
            validated_row.external_key = row_data.get("external_key", "")
            validated_row.event_id = row_data.get("event_id", "")
            validated_row.collection_code = row_data.get("collection_code", "")
            validated_row.dataset_name = row_data.get("dataset_name", "")
            validated_row.institution_code = row_data.get("institution_code", "")

            # Species
            validated_row.species_name = row_data.get("species_name", "")
            validated_row.species_tvk = row_data.get("species_tvk", "")
            validated_row.common_name = row_data.get("common_name", "")
            validated_row.taxon_author = row_data.get("taxon_author", "")
            validated_row.order_name = row_data.get("order_name", "")
            validated_row.family = row_data.get("family", "")
            validated_row.subfamily = row_data.get("subfamily", "")
            validated_row.genus = row_data.get("genus", "")
            validated_row.kingdom = row_data.get("kingdom", "")
            validated_row.phylum = row_data.get("phylum", "")
            validated_row.class_name = row_data.get("class_name", "")
            validated_row.taxon_group = row_data.get("taxon_group", "")
            validated_row.superfamily = row_data.get("superfamily", "")
            validated_row.taxonomic_sort_key = int(row_data["taxonomic_sort_key"]) if row_data.get("taxonomic_sort_key") and str(row_data.get("taxonomic_sort_key", "")).replace('.0','').isdigit() else None
            validated_row.taxon_rank = row_data.get("taxon_rank", "")
            validated_row.identification_qualifier = row_data.get("identification_qualifier", "")
            validated_row.identification_remarks = row_data.get("identification_remarks", "")
            validated_row.recorder_certainty = row_data.get("recorder_certainty", "")

            # Date
            validated_row.date = row_data.get("date", "")
            validated_row.date_type = row_data.get("date_type", "D")

            # Location
            validated_row.grid_ref = row_data.get("grid_ref", "")
            validated_row.grid_precision = _safe_int(row_data, "grid_precision")
            validated_row.vice_county = row_data.get("vice_county", "")
            validated_row.vc_number = _safe_int(row_data, "vc_number")
            # Fallback: resolve vc_number from pipe-separated vice_county text
            if not validated_row.vc_number and validated_row.vice_county:
                try:
                    from ...core.vc_shortnames import VC_FULL_NAMES
                    _name_to_num = {v.lower().strip(): int(k) for k, v in VC_FULL_NAMES.items() if k.isdigit()}
                    first_vc = validated_row.vice_county.split("|")[0].strip().lower()
                    resolved = _name_to_num.get(first_vc)
                    if resolved:
                        validated_row.vc_number = resolved
                except Exception:
                    pass
            validated_row.site_name = row_data.get("site_name", "")
            validated_row.site_name_local = row_data.get("site_name_local", "")
            validated_row.country = row_data.get("country", "")
            validated_row.state_province = row_data.get("state_province", "")
            validated_row.latitude = _safe_float(row_data, "latitude")
            validated_row.longitude = _safe_float(row_data, "longitude")
            validated_row.geodetic_datum = row_data.get("geodetic_datum", "")
            validated_row.coordinate_uncertainty = _safe_float(row_data, "coordinate_uncertainty")
            validated_row.location_id = row_data.get("location_id", "")
            validated_row.location_remarks = row_data.get("location_remarks", "")
            validated_row.georeference_verification_status = row_data.get("georeference_verification_status", "")
            validated_row.sensitive_site = row_data.get("sensitive_site", "")
            validated_row.sensitive_output_map_ref = row_data.get("sensitive_output_map_ref", "")

            # People
            validated_row.recorder = row_data.get("recorder", "")
            validated_row.determiner = row_data.get("determiner", "")

            # Occurrence
            validated_row.sex = row_data.get("sex", "")
            validated_row.stage = row_data.get("stage", "")
            validated_row.quantity = row_data.get("quantity", 1) or 1
            validated_row.individual_count = _safe_int(row_data, "individual_count")
            validated_row.organism_quantity = row_data.get("organism_quantity", "")
            validated_row.organism_quantity_type = row_data.get("organism_quantity_type", "")
            validated_row.zero_abundance = row_data.get("zero_abundance", 0)
            validated_row.method = row_data.get("method", "")
            validated_row.biotope = row_data.get("biotope", "")
            validated_row.sensitive = row_data.get("sensitive", 0)
            validated_row.occurrence_status = row_data.get("occurrence_status", "")

            # Comments
            validated_row.comment = row_data.get("comment", "")
            validated_row.sample_comment = row_data.get("sample_comment", "")
            validated_row.occurrence_remarks = row_data.get("occurrence_remarks", "")
            validated_row.internal_notes = row_data.get("internal_notes", "")

            # Verification
            validated_row.verification_status = row_data.get("verification_status", "")
            validated_row.verification_status_2 = row_data.get("verification_status_2", "")
            validated_row.verifier = row_data.get("verifier", "")
            validated_row.verified_on = row_data.get("verified_on", "")
            validated_row.automated_checks = row_data.get("automated_checks", "")
            validated_row.query = row_data.get("query", "")

            # Media/Metadata
            validated_row.images = row_data.get("images", "")
            validated_row.input_on_date = row_data.get("input_on_date", "")
            validated_row.last_edited_date = row_data.get("last_edited_date", "")
            validated_row.licence = row_data.get("licence", "")
            validated_row.basis_of_record = row_data.get("basis_of_record", "")
            validated_row.rights_holder = row_data.get("rights_holder", "")

            # Duplicate tracking
            validated_row.is_duplicate = bool(row_data.get("is_duplicate", False))
            validated_row.existing_record_id = row_data.get("existing_record_id")
            notes = row_data.get("import_notes", "")
            if not notes:
                warning = row_data.get("species_warning", "") or row_data.get("warning", "")
                if warning:
                    notes = warning
            validated_row.import_notes = notes
            date_note = row_data.get("_date_note", "")
            if date_note:
                if validated_row.import_notes:
                    validated_row.import_notes += f"; {date_note}"
                else:
                    validated_row.import_notes = date_note

            # Build errors and warnings
            errors = []
            warnings = []

            # Collect errors from batch processing
            if row_data.get("species_error"):
                errors.append(row_data["species_error"])
            if row_data.get("vc_error"):
                errors.append(row_data["vc_error"])
            if row_data.get("dup_error"):
                errors.append(row_data["dup_error"])

            # Collect warnings from batch processing
            if row_data.get("species_warning"):
                warnings.append(row_data["species_warning"])
            if row_data.get("vc_warning"):
                warnings.append(row_data["vc_warning"])

            # Filter non-species records (genus-only, subgenus, family-level)
            if validated_row.species_name:
                sn = validated_row.species_name.strip()
                if ' ' not in sn:
                    # Genus-only or family-level (single word)
                    errors.append(f"Not a species-level record: {sn}")
                else:
                    # Check for "Genus (Subgenus)" with no epithet after closing paren
                    import re
                    if re.match(r'^[A-Z][a-z]+ \([A-Z][a-z]+\)$', sn):
                        errors.append(f"Subgenus-level record, not species: {sn}")

            # Validation rules based on import mode
            if self.import_mode == SchemeImportMode.GENERIC_CSV:
                # Strict validation for generic imports
                if not validated_row.species_name:
                    errors.append("Species name is required")
                if not validated_row.date:
                    date_raw = row_data.get("date_raw", "")
                    if date_raw:
                        errors.append(f"Invalid date format: {date_raw}")
                    else:
                        errors.append("Date is required")
                if not validated_row.grid_ref:
                    errors.append("Grid reference is required")
                if (validated_row.species_name and not validated_row.species_tvk
                        and not row_data.get("species_error")):
                    errors.append(f"Species not found in UKSI: {validated_row.species_name}")
            else:
                # Lenient validation for iRecord/NBN (they already have some validation)
                if not validated_row.species_name:
                    errors.append("Missing species name")
                if not validated_row.species_tvk and not row_data.get("species_error"):
                    warnings.append("Missing TVK - will attempt UKSI lookup")
                if not validated_row.date:
                    if not row_data.get("_date_note"):
                        warnings.append("Missing date")
                if not validated_row.grid_ref:
                    warnings.append("Missing grid reference")

            # Duplicate warning
            if validated_row.is_duplicate:
                warnings.append(f"Duplicate found (ID: {validated_row.existing_record_id})")
                validated_row.import_notes = f"Duplicate found (ID: {validated_row.existing_record_id})"

            # Deduplicate warnings and errors while preserving order
            warnings = list(dict.fromkeys(warnings))
            errors = list(dict.fromkeys(errors))

            # Set final status
            validated_row.warnings = warnings
            if errors:
                validated_row.status = RowStatus.ERROR
                validated_row.error_message = "; ".join(errors)
                self.error_count += 1
            elif warnings:
                validated_row.status = RowStatus.WARNING
                validated_row.error_message = "; ".join(warnings)
                self.warning_count += 1
            else:
                validated_row.status = RowStatus.VALID
                self.valid_count += 1

            # Copy warnings to import_notes if still empty
            if not validated_row.import_notes and warnings:
                validated_row.import_notes = "; ".join(warnings)

            # Emit counts periodically (every 500 rows)
            row_idx = len(validated_rows)
            if row_idx % 500 == 0:
                self.counts_updated.emit(self.valid_count, self.warning_count, self.error_count)

            validated_rows.append(validated_row)

        return validated_rows

    def _parse_irecord_date(self, raw: dict) -> str:
        """Parse date from iRecord row, trying multiple columns."""
        self._last_date_note = ""
        for col in ('Date interpreted', 'Date from'):
            val = raw.get(col, '').strip()
            if val:
                result = self._parse_date(val)
                if result:
                    return result
        return ''

    def _parse_date(self, date_str: str) -> Optional[str]:
        """Parse various date formats to ISO format (YYYY-MM-DD).
        
        Handles NBN Atlas date ranges (2024-05-01/2024-05-15) by taking
        the start date, and vague dates (2024, 2024-05) by padding.
        Sets self._last_date_note with details of any transformation.
        """
        self._last_date_note = ""
        if not date_str:
            return None

        date_str = date_str.strip()
        original = date_str

        # Handle ISO 8601 date ranges: "2024-05-01/2024-05-15" → take start date
        if '/' in date_str:
            parts = date_str.split('/')
            if len(parts) == 2 and len(parts[0]) >= 4 and parts[0][0].isdigit():
                date_str = parts[0].strip()
                self._last_date_note = f"Date interpreted: '{original}' -> {date_str}"

        # Handle vague dates: year only or year-month
        import re
        if re.match(r'^\d{4}$', date_str):
            self._last_date_note = f"Date interpreted: '{original}' -> {date_str}-01-01"
            return f"{date_str}-01-01"
        if re.match(r'^\d{4}-\d{2}$', date_str):
            self._last_date_note = f"Date interpreted: '{original}' -> {date_str}-01"
            return f"{date_str}-01"

        formats = [
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%Y-%m-%d",
            "%d/%m/%y",
            "%d-%m-%y",
            "%Y/%m/%d",
            "%d %b %Y",
            "%d %B %Y",
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue

        return None

    def _parse_count(self, value):
        """(number, original text) -- 'c.20' is 20, not 1, and the text is kept (9 Oct 2026)."""
        from shared.import_core import parse_quantity
        return parse_quantity(value)

    def _parse_int(self, value: str) -> Optional[int]:
        """Safely parse string to int."""
        if not value:
            return None
        try:
            return int(float(str(value).strip()))
        except (ValueError, TypeError):
            return None

    def _parse_float(self, value: str) -> Optional[float]:
        """Safely parse string to float."""
        if not value:
            return None
        try:
            return float(str(value).strip())
        except (ValueError, TypeError):
            return None
