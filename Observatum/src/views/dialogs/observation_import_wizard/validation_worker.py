"""
Validation Worker for Observation Import Wizard.
PANDAS REFACTOR: Uses vectorized operations for fast validation.

Handles iRecord Sync and Personal Upload modes with
different validation rules and column mappings for each.
"""

import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import paths
from pathlib import Path
from typing import Optional, Dict, List, Tuple

import pandas as pd
from PySide6.QtCore import QThread, Signal


def _find_vc_database() -> Optional[str]:
    """
    Find the Vice County lookup database.
    Searches multiple locations in order of priority.
    Returns path as string, or None if not found.
    """
    candidates = []

    # 1. Check QSettings for user-configured path
    try:
        from PySide6.QtCore import QSettings
        settings = QSettings()
        custom_path = settings.value("database/vc_lookup_path")
        if custom_path:
            candidates.append(Path(custom_path))
    except Exception:
        pass

    # 2. From this file's location
    try:
        this_file = Path(__file__).resolve()
        candidates.append(this_file.parent.parent.parent.parent.parent / "data" / "vc_lookup.db")
        candidates.append(this_file.parent.parent.parent.parent / "data" / "vc_lookup.db")
    except Exception:
        pass

    # 3. From current working directory
    cwd = Path(os.getcwd())
    candidates.append(cwd / "data" / "vc_lookup.db")
    candidates.append(cwd / "src" / "data" / "vc_lookup.db")

    # 4. From sys.path
    if sys.path:
        candidates.append(Path(sys.path[0]) / "data" / "vc_lookup.db")

    # 5. Relative paths
    candidates.append(Path("data") / "vc_lookup.db")

    # 6. User's home directory
    try:
        home = Path.home()
        candidates.append(paths.VC_LOOKUP_DB)
        candidates.append(paths.VC_LOOKUP_DB)
    except Exception:
        pass

    # 7. For frozen executables
    if getattr(sys, 'frozen', False):
        exe_dir = Path(sys.executable).parent
        candidates.append(exe_dir / "data" / "vc_lookup.db")
        candidates.append(exe_dir / "vc_lookup.db")

    for path in candidates:
        try:
            if path.exists():
                return str(path)
        except Exception:
            pass

    return None


class ImportMode(Enum):
    """Import mode selection."""
    IRECORD_SYNC = "irecord_sync"
    PERSONAL_UPLOAD = "personal_upload"
    COMMERCIAL_UPLOAD = "commercial_upload"


class RowStatus(Enum):
    """Status of a row during validation."""
    PENDING = "pending"
    VALID = "valid"
    WARNING = "warning"
    ERROR = "error"


# Valid dropdown values
VALID_SEX_VALUES = ["", "female", "male", "mixed", "not recorded"]
VALID_STAGE_VALUES = ["", "adult", "larva", "pupa", "egg", "nymph", "teneral", "not recorded"]
VALID_CERTAINTY_VALUES = ["", "certain", "likely", "uncertain"]
VALID_METHOD_VALUES = [
    "", "unknown", "field observation", "quadrat", "transect", "net",
    "pitfall trap", "light trap", "transect section", "parent sample",
    "child sample", "timed count", "timed count count", "treeinitialregistration",
    "treevisit", "garden bird survey count", "visit", "seasearch buddy pair",
    "seasearch habitat", "grid square", "mv light", "actinic light",
    "daytime observation", "dusking", "attracted to a lighted window",
    "sugaring", "wine roping", "beating tray", "pheromone trap",
    "other method (add comment)"
]


def _safe_get(row_data, key, default=None):
    """Safely get value from pandas Series, converting NaN to None."""
    val = row_data.get(key, default)
    if val is None:
        return default
    if pd.isna(val):
        return default
    if isinstance(val, str):
        return val.strip()
    return val


@dataclass
class ObservationImportRow:
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

    is_irecord: bool = False
    irecord_id: Optional[int] = None
    record_key: str = ""
    external_key: str = ""

    species_name: str = ""
    species_tvk: str = ""
    common_name: str = ""
    order_name: str = ""
    family: str = ""
    kingdom: str = ""
    taxon_group: str = ""
    taxon_rank: str = ""

    date: str = ""
    date_from: str = ""
    date_to: str = ""
    date_type: str = "D"

    grid_ref: str = ""
    grid_precision: Optional[int] = None
    vice_county: str = ""
    vc_number: Optional[int] = None
    site_name: str = ""

    latitude: Optional[float] = None
    longitude: Optional[float] = None
    geodetic_datum: str = ""

    sensitive: int = 0
    sensitive_site: str = ""
    sensitive_output_map_ref: str = ""

    recorder: str = ""
    determiner: str = ""
    recorder_certainty: str = ""

    sex: str = ""
    stage: str = ""
    quantity: int = 1
    zero_abundance: int = 0
    method: str = ""

    comment: str = ""
    sample_comment: str = ""
    biotope: str = ""

    verification_status: str = ""
    verification_status_2: str = ""
    verifier: str = ""
    verified_on: str = ""
    automated_checks: str = ""

    source: str = ""
    images: str = ""
    licence: str = ""
    input_on_date: str = ""
    last_edited_date: str = ""

    record_type: str = "Personal"
    never_upload_to_irecord: int = 0

    is_duplicate: bool = False
    existing_record_id: Optional[int] = None
    import_notes: str = ""

    def add_warning(self, msg: str):
        if msg not in self.warnings:
            self.warnings.append(msg)

    def add_error(self, msg: str):
        if self.error_message:
            self.error_message += "; " + msg
        else:
            self.error_message = msg
        self.status = RowStatus.ERROR



# UKSI order -> iRecord taxon_group mapping
from src.utils.constants import INSECT_ORDER_POSITION, compute_taxonomic_sort_key

ORDER_TO_GROUP = {
    'Coleoptera': 'insect - beetle (Coleoptera)',
    'Diptera': 'insect - true fly (Diptera)',
    'Hymenoptera': 'insect - hymenopteran',
    'Hemiptera': 'insect - true bug (Hemiptera)',
    'Lepidoptera': 'insect - moth',
    'Orthoptera': 'insect - orthopteran',
    'Odonata': 'insect - dragonfly (Odonata)',
    'Dermaptera': 'insect - earwig (Dermaptera)',
    'Mecoptera': 'insect - scorpion fly (Mecoptera)',
    'Neuroptera': 'insect - lacewing (Neuroptera)',
    'Trichoptera': 'insect - caddis fly (Trichoptera)',
    'Raphidioptera': 'insect - snakefly (Raphidioptera)',
    'Thysanoptera': 'insect - thrips (Thysanoptera)',
    'Siphonaptera': 'insect - flea (Siphonaptera)',
    'Araneae': 'spider (Araneae)',
    'Opiliones': 'harvestman (Opiliones)',
    'Pseudoscorpiones': 'false scorpion (Pseudoscorpiones)',
    'Passeriformes': 'bird',
    'Anseriformes': 'bird',
    'Charadriiformes': 'bird',
    'Accipitriformes': 'bird',
    'Strigiformes': 'bird',
    'Rodentia': 'terrestrial mammal',
    'Carnivora': 'terrestrial mammal',
    'Chiroptera': 'terrestrial mammal',
    'Anura': 'amphibian',
    'Caudata': 'amphibian',
    'Squamata': 'reptile',
    'Julida': 'millipede',
    'Polydesmida': 'millipede',
    'Lithobiomorpha': 'centipede',
    'Geophilomorpha': 'centipede',
    'Stylommatophora': 'mollusc',
    'Isopoda': 'crustacean',
    'Decapoda': 'crustacean',
    'Agaricales': 'fungus',
    'Polyporales': 'fungus',
}

# Class-level fallbacks
CLASS_TO_GROUP = {
    'Arachnida': 'spider (Araneae)',
    'Gastropoda': 'mollusc',
    'Malacostraca': 'crustacean',
    'Chilopoda': 'centipede',
    'Diplopoda': 'millipede',
    'Collembola': 'springtail (Collembola)',
    'Amphibia': 'amphibian',
    'Aves': 'bird',
    'Mammalia': 'terrestrial mammal',
    'Reptilia': 'reptile',
    'Insecta': 'insect',
}


def _osgb36_to_wgs84(easting, northing):
    """Convert OSGB36 eastings/northings to WGS84 lat/lon."""
    import math
    a, b = 6377563.396, 6356256.909
    F0 = 0.9996012717
    lat0, lon0 = math.radians(49), math.radians(-2)
    N0, E0 = -100000, 400000
    e2 = 1 - (b*b)/(a*a)
    n = (a-b)/(a+b)
    lat, M = lat0, 0
    for _ in range(20):
        lat = (northing - N0 - M)/(a*F0) + lat
        Ma = (1 + n + 1.25*n**2 + 1.25*n**3) * (lat-lat0)
        Mb = (3*n + 3*n**2 + 2.625*n**3) * math.sin(lat-lat0) * math.cos(lat+lat0)
        Mc = (1.875*n**2 + 1.875*n**3) * math.sin(2*(lat-lat0)) * math.cos(2*(lat+lat0))
        Md = (35/24)*n**3 * math.sin(3*(lat-lat0)) * math.cos(3*(lat+lat0))
        M = b * F0 * (Ma - Mb + Mc - Md)
        if abs(northing - N0 - M) < 0.00001:
            break
    cosLat, sinLat = math.cos(lat), math.sin(lat)
    nu = a*F0/math.sqrt(1-e2*sinLat**2)
    rho = a*F0*(1-e2)*(1-e2*sinLat**2)**(-1.5)
    eta2 = nu/rho-1
    tanLat = math.tan(lat)
    VII = tanLat/(2*rho*nu)
    VIII = tanLat/(24*rho*nu**3)*(5+3*tanLat**2+eta2-9*tanLat**2*eta2)
    IX = tanLat/(720*rho*nu**5)*(61+90*tanLat**2+45*tanLat**4)
    X = 1/(cosLat*nu)
    XI = 1/(cosLat*6*nu**3)*(nu/rho+2*tanLat**2)
    XII = 1/(cosLat*120*nu**5)*(5+28*tanLat**2+24*tanLat**4)
    dE = easting - E0
    latitude = math.degrees(lat - VII*dE**2 + VIII*dE**4 - IX*dE**6)
    longitude = math.degrees(lon0 + X*dE - XI*dE**3 + XII*dE**5)
    return round(latitude, 6), round(longitude, 6)

class ObservationValidationWorker(QThread):
    """
    Background worker for validating observation import data.
    PANDAS REFACTOR: Uses batch operations for species and VC lookups.
    """
    progress = Signal(int, int)
    row_validated = Signal(int, object)
    counts_updated = Signal(int, int, int)
    finished = Signal(list)

    def __init__(
        self,
        rows: List[ObservationImportRow],
        column_mapping: Dict[str, str],
        import_mode: ImportMode,
        uksi_model=None,
        vc_db_path: str = None,
        db_manager=None,
        species_aliases: Dict = None,
    ):
        super().__init__()
        self.rows = rows
        self.column_mapping = column_mapping
        self.import_mode = import_mode
        self.uksi_model = uksi_model
        self.vc_db_path = vc_db_path
        self.db_manager = db_manager
        self.species_aliases = species_aliases or {}
        self._cancelled = False
        self._vc_service = None

        self.valid_count = 0
        self.warning_count = 0
        self.error_count = 0

    def cancel(self):
        self._cancelled = True

    def run(self):
        """Validate all rows using pandas batch operations."""
        # Initialize VC service
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

        self.valid_count = 0
        self.warning_count = 0
        self.error_count = 0

        # Step 1: Build DataFrame from rows
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

        # Step 3: Batch VC lookup (for personal uploads)
        self.progress.emit(int(total * 0.50), total)
        if self.import_mode != ImportMode.IRECORD_SYNC:
            df = self._batch_vc_lookup(df)

            # Enrich: derive taxon_group from order, lat/lon from grid_ref
            df = self._enrich_data(df)

        if self._cancelled:
            self.finished.emit([])
            return

        # Step 4: Batch duplicate check
        self.progress.emit(int(total * 0.70), total)
        df = self._batch_duplicate_check(df)

        if self._cancelled:
            self.finished.emit([])
            return

        # Step 5: Build final ObservationImportRow objects
        self.progress.emit(int(total * 0.85), total)
        validated = self._build_validated_rows(df)

        # Close VC service
        if self._vc_service:
            try:
                self._vc_service.close()
            except Exception:
                pass

        self.progress.emit(total, total)
        self.finished.emit(validated)

    def _build_dataframe(self) -> pd.DataFrame:
        """Build DataFrame from raw rows based on import mode."""
        records = []

        for row in self.rows:
            if self._cancelled:
                break

            raw = row.raw_data

            if self.import_mode == ImportMode.IRECORD_SYNC:
                record = self._extract_irecord_fields(raw)
            else:
                record = self._extract_personal_fields(raw)

            record["row_number"] = row.row_number
            record["raw_data"] = raw
            records.append(record)

        return pd.DataFrame(records)

    def _extract_irecord_fields(self, raw: dict) -> dict:
        """Extract fields from iRecord CSV format."""
        def g(key):
            return raw.get(key, "").strip() if raw.get(key) else ""

        date_val = self._parse_date(g("Date interpreted")) or ""
        date_from = self._parse_date(g("Date from")) or ""
        if not date_val and date_from:
            date_val = date_from

        grid_ref = g("Output map ref") or g("Original map ref")
        sensitive_map_ref = g("Sensitive output map ref")
        if sensitive_map_ref:
            grid_ref = sensitive_map_ref

        return {
            "irecord_id": self._parse_int(g("ID")),
            "record_key": g("RecordKey"),
            "external_key": g("External key"),
            "source": g("Source"),
            "species_name": g("Taxon"),
            "species_tvk": g("TaxonVersionKey"),
            "common_name": g("Common name"),
            "taxon_group": g("Taxon group"),
            "kingdom": g("Kingdom"),
            "order_name": g("Order"),
            "family": g("Family"),
            "taxon_rank": g("Rank"),
            "date": date_val,
            "date_from": date_from,
            "date_to": self._parse_date(g("Date to")) or "",
            "date_type": g("Date type") or "D",
            "grid_ref": grid_ref,
            "grid_precision": self._parse_int(g("Precision")),
            "latitude": self._parse_float(g("Latitude")),
            "longitude": self._parse_float(g("Longitude")),
            "geodetic_datum": g("Projection (input)"),
            "vc_number": self._parse_int(g("VC number")),
            "vice_county": g("Vice County"),
            "site_name": g("Site name"),
            "sensitive_site": g("Sensitive site"),
            "sensitive_output_map_ref": sensitive_map_ref,
            "sensitive": 1 if g("Sensitive").upper() == "TRUE" else 0,
            "recorder": g("Recorder"),
            "determiner": g("Determiner"),
            "recorder_certainty": g("Recorder certainty"),
            "sex": g("Sex"),
            "stage": g("Stage"),
            "quantity": self._parse_int(g("Count of sex or stage")) or 1,
            "zero_abundance": 1 if g("Zero abundance").upper() == "TRUE" else 0,
            "method": g("Sample method"),
            "comment": g("Comment"),
            "sample_comment": g("Sample comment"),
            "biotope": g("Biotope"),
            "verification_status": g("Verification status 1"),
            "verification_status_2": g("Verification status 2"),
            "verifier": g("Verifier"),
            "verified_on": g("Verified on"),
            "automated_checks": g("Automated checks"),
            "images": g("Images"),
            "licence": g("Licence"),
            "input_on_date": g("Input on date"),
            "last_edited_date": g("Last edited on date"),
            "is_irecord": True,
            "species_error": "",
            "species_warning": "",
            "vc_error": "",
            "vc_warning": "",
            "is_duplicate": False,
            "existing_record_id": None,
            "import_notes": "",
        }

    def _extract_personal_fields(self, raw: dict) -> dict:
        """Extract fields from personal CSV using column mapping."""
        mapping = self.column_mapping

        def g(field):
            col = mapping.get(field, "")
            return raw.get(col, "").strip() if col and raw.get(col) else ""

        date_raw = g("date")
        date_val = self._parse_date(date_raw) if date_raw else ""

        return {
            "irecord_id": None,
            "record_key": "",
            "external_key": g("external_key"),
            "source": "",
            "species_name": g("species_name"),
            "species_tvk": "",
            "common_name": "",
            "taxon_group": "",
            "kingdom": "",
            "order_name": "",
            "family": "",
            "taxon_rank": "",
            "date": date_val,
            "date_raw": date_raw,
            "date_from": "",
            "date_to": "",
            "date_type": "D",
            "grid_ref": g("grid_ref").upper().replace(" ", "") if g("grid_ref") else "",
            "grid_precision": None,
            "latitude": None,
            "longitude": None,
            "geodetic_datum": "",
            "vc_number": None,
            "vice_county": "",
            "site_name": g("site_name"),
            "sensitive_site": "",
            "sensitive_output_map_ref": "",
            "sensitive": 0,
            "recorder": g("recorder"),
            "determiner": g("determiner"),
            "recorder_certainty": g("certainty"),
            "sex": g("sex"),
            "stage": g("stage"),
            "quantity": self._parse_int(g("quantity")) or 1,
            "zero_abundance": 0,
            "method": g("method"),
            "comment": g("comment"),
            "sample_comment": "",
            "biotope": "",
            "verification_status": "",
            "verification_status_2": "",
            "verifier": "",
            "verified_on": "",
            "automated_checks": "",
            "images": "",
            "licence": "",
            "input_on_date": "",
            "last_edited_date": "",
            "is_irecord": False,
            "species_error": "",
            "species_warning": "",
            "vc_error": "",
            "vc_warning": "",
            "is_duplicate": False,
            "existing_record_id": None,
            "import_notes": "",
        }

    def _normalize_species_name(self, name: str) -> dict:
        """Parse species name for cf./agg. qualifiers.
        
        Returns dict with:
            cleaned: name with qualifier stripped
            qualifier: 'cf.' or 'agg.' or None
            original: original name
        """
        import re
        result = {'original': name, 'cleaned': name, 'qualifier': None}
        
        # Check for cf. (e.g. "Anthocoris cf. confusus")
        cf_match = re.match(r'^(\w+)\s+cf\.\s+(.+)$', name, re.IGNORECASE)
        if cf_match:
            result['cleaned'] = f"{cf_match.group(1)} {cf_match.group(2)}"
            result['qualifier'] = 'cf.'
            return result
        
        # Check for agg. (e.g. "Bombus lucorum agg.")
        agg_match = re.match(r'^(.+?)\s+agg\.?\s*$', name, re.IGNORECASE)
        if agg_match:
            result['cleaned'] = agg_match.group(1).strip()
            result['qualifier'] = 'agg.'
            return result
        
        return result

    def _batch_species_lookup(self, df: pd.DataFrame) -> pd.DataFrame:
        """Batch lookup species in UKSI."""
        if not self.uksi_model:
            return df

        # Find rows needing species lookup
        if self.import_mode == ImportMode.IRECORD_SYNC:
            # iRecord: lookup only if TVK is missing
            needs_lookup = df[
                (df["species_name"].notna()) &
                (df["species_name"] != "") &
                ((df["species_tvk"].isna()) | (df["species_tvk"] == ""))
            ]["species_name"].unique().tolist()
        else:
            # Personal: always lookup to populate taxonomy
            needs_lookup = df[
                (df["species_name"].notna()) &
                (df["species_name"] != "")
            ]["species_name"].unique().tolist()

        if not needs_lookup:
            return df

        species_lookup = {}

        # Check aliases first
        for name in needs_lookup:
            alias_key = name.lower().strip()
            if alias_key in self.species_aliases:
                alias = self.species_aliases[alias_key]
                species_lookup[name] = {
                    "tvk": alias.get("uksi_tvk", ""),
                    "common_name": alias.get("uksi_common_name", ""),
                    "order_name": alias.get("uksi_order", ""),
                    "family": alias.get("uksi_family", ""),
                    "kingdom": "",
                    "taxon_group": "",
                    "rank": "",
                    "matched_name": alias.get("uksi_name", name),
                    "_alias": True,
                }


        # Batch exact match
        if hasattr(self.uksi_model, "get_species_batch"):
            batch_results = self.uksi_model.get_species_batch(needs_lookup)
            for name, result in batch_results.items():
                if result:
                    species_lookup[name] = {
                        "tvk": result.get("tvk", "") if isinstance(result, dict) else getattr(result, "tvk", ""),
                        "common_name": result.get("common_name", "") if isinstance(result, dict) else getattr(result, "common_name", ""),
                        "order_name": result.get("order_name", "") if isinstance(result, dict) else getattr(result, "order_name", ""),
                        "family": result.get("family", "") if isinstance(result, dict) else getattr(result, "family", ""),
                        "kingdom": result.get("kingdom", "") if isinstance(result, dict) else getattr(result, "kingdom", ""),
                        "taxon_group": result.get("taxon_group", "") if isinstance(result, dict) else getattr(result, "taxon_group", ""),
                        "rank": result.get("rank", "") if isinstance(result, dict) else getattr(result, "rank", ""),
                        "matched_name": result.get("scientific_name", name) if isinstance(result, dict) else getattr(result, "scientific_name", name),
                    }
        else:
            # Fallback to individual lookups
            for name in needs_lookup:
                if self._cancelled:
                    break
                try:
                    results = self.uksi_model.search_species(name, limit=1)
                    if results:
                        match = results[0]
                        species_lookup[name] = {
                            "tvk": getattr(match, "tvk", "") or "",
                            "common_name": getattr(match, "common_name", "") or "",
                            "order_name": getattr(match, "order_name", "") or "",
                            "family": getattr(match, "family", "") or "",
                            "kingdom": getattr(match, "kingdom", "") or "",
                            "taxon_group": getattr(match, "taxon_group", "") or "",
                            "rank": getattr(match, "rank", "") or "",
                            "matched_name": getattr(match, "scientific_name", name) or name,
                        }
                except Exception:
                    pass

        # Apply lookups to DataFrame

        # Retry failed lookups with normalized names (handle cf./agg.)
        found_names = set(species_lookup.keys())
        for name in needs_lookup:
            parsed = self._normalize_species_name(name)
            if parsed["qualifier"] is None:
                continue
            # For agg.: override existing match with sensu lato TVK
            # For cf.: skip if already matched
            if name in found_names and parsed["qualifier"] != "agg.":
                continue

            cleaned = parsed['cleaned']
            # Try cleaned name in existing results first
            if cleaned in species_lookup and parsed["qualifier"] != "agg.":
                species_lookup[name] = dict(species_lookup[cleaned])
                species_lookup[name]['_qualifier'] = parsed['qualifier']
                species_lookup[name]['_original'] = name
                continue
            
            # For agg. species: search for aggregate/sensu lato rank in UKSI
            # For cf. species: search for the base species
            try:
                if parsed["qualifier"] == "agg.":
                    # Try direct DB query for sensu lato / aggregate rank
                    if hasattr(self.uksi_model, "db") and self.uksi_model.db:
                        agg_results = self.uksi_model.db.execute_uksi(
                            "SELECT t.tvk, t.scientific_name, t.rank, t.kingdom, "
                            "t.\"order\" as order_name, t.family, cn.common_name "
                            "FROM taxa t LEFT JOIN common_names cn ON t.tvk = cn.tvk "
                            "WHERE t.scientific_name LIKE ? "
                            "AND (t.rank = 'Species sensu lato' OR t.rank = 'Species aggregate') "
                            "ORDER BY CASE WHEN t.rank = 'Species sensu lato' THEN 0 ELSE 1 END "
                            "LIMIT 1",
                            (cleaned + "%",)
                        )
                        if agg_results:
                            r = agg_results[0]
                            species_lookup[name] = {
                                "tvk": r["tvk"] or "",
                                "common_name": (r["common_name"] if r["common_name"] else ""),
                                "order_name": (r["order_name"] if r["order_name"] else ""),
                                "family": (r["family"] if r["family"] else ""),
                                "kingdom": (r["kingdom"] if r["kingdom"] else ""),
                                "taxon_group": "",
                                "rank": (r["rank"] if r["rank"] else ""),
                                "matched_name": r["scientific_name"] or cleaned,
                                "_qualifier": "agg.",
                                "_original": name,
                            }
                            continue
                # Fallback: search with cleaned name (works for cf. and unmatched agg.)
                results = self.uksi_model.search_species(cleaned, limit=1)
                if results:
                    match = results[0]
                    species_lookup[name] = {
                        "tvk": getattr(match, "tvk", "") or "",
                        "common_name": getattr(match, "common_name", "") or "",
                        "order_name": getattr(match, "order_name", "") or "",
                        "family": getattr(match, "family", "") or "",
                        "kingdom": getattr(match, "kingdom", "") or "",
                        "taxon_group": getattr(match, "taxon_group", "") or "",
                        "rank": getattr(match, "rank", "") or "",
                        "matched_name": getattr(match, "scientific_name", cleaned) or cleaned,
                        "_qualifier": parsed["qualifier"],
                        "_original": name,
                    }
            except Exception:
                pass

        still_missing = []
        for idx, row in df.iterrows():
            species = row.get("species_name", "")
            if not species:
                if self.import_mode != ImportMode.IRECORD_SYNC:
                    df.at[idx, "species_error"] = "Species name is required"
                continue

            if species in species_lookup:
                info = species_lookup[species]
                if self.import_mode != ImportMode.IRECORD_SYNC or not row.get("species_tvk"):
                    df.at[idx, "species_tvk"] = info["tvk"]
                    df.at[idx, "species_error"] = ""
                    df.at[idx, "common_name"] = info["common_name"]
                    df.at[idx, "order_name"] = info["order_name"]
                    df.at[idx, "family"] = info["family"]
                    df.at[idx, "kingdom"] = info["kingdom"]
                    df.at[idx, "taxon_group"] = info["taxon_group"]
                    df.at[idx, "taxon_rank"] = info["rank"]

                    matched = info["matched_name"]
                    if matched.lower() != species.lower():
                        df.at[idx, "species_warning"] = f"Fuzzy matched to '{matched}'"
                        df.at[idx, "import_notes"] = f"Fuzzy matched: '{species}' -> '{matched}'"

                    # Handle cf./agg. qualifiers
                    qualifier = info.get("_qualifier")
                    if qualifier == "cf.":
                        df.at[idx, "species_warning"] = f"cf. identification: matched to '{matched}' (uncertain ID)"
                        df.at[idx, "import_notes"] = f"Original: '{species}' (cf. = uncertain identification)"
                    elif qualifier == "agg.":
                        if matched.lower() != species.lower():
                            df.at[idx, "species_warning"] = f"Aggregate matched to base species '{matched}'"
                            df.at[idx, "import_notes"] = f"Original: '{species}' -> matched to '{matched}'"
            else:
                still_missing.append(species)
                if self.import_mode != ImportMode.IRECORD_SYNC:
                    df.at[idx, "species_error"] = f"Species not found in UKSI: {species}"
                else:
                    df.at[idx, "species_warning"] = "Missing TVK - species not found in UKSI"

        return df

    def _batch_vc_lookup(self, df: pd.DataFrame) -> pd.DataFrame:
        """Batch lookup Vice Counties from grid references."""
        if not self._vc_service:
            return df

        # Find unique grid refs needing lookup
        needs_lookup = df[
            (df["grid_ref"].notna()) &
            (df["grid_ref"] != "") &
            ((df["vc_number"].isna()) | (df["vc_number"] == 0))
        ]["grid_ref"].unique().tolist()

        if not needs_lookup:
            return df

        # Batch VC lookup
        vc_lookup = {}
        if hasattr(self._vc_service, "get_vc_batch"):
            vc_lookup = self._vc_service.get_vc_batch(needs_lookup)
        else:
            # Fallback to individual lookups
            for grid_ref in needs_lookup:
                if self._cancelled:
                    break
                try:
                    is_valid, msg = self._vc_service.validate_grid_ref(grid_ref)
                    if is_valid:
                        result = self._vc_service.get_vc_from_grid_ref(grid_ref)
                        if result:
                            vc_lookup[grid_ref] = {"vc_number": result[0], "vc_name": result[1]}
                        else:
                            vc_lookup[grid_ref] = {"error": "Could not determine Vice County"}
                    else:
                        vc_lookup[grid_ref] = {"error": f"Invalid grid reference: {msg}"}
                except Exception as e:
                    vc_lookup[grid_ref] = {"error": str(e)}

        # Apply lookups to DataFrame
        for idx, row in df.iterrows():
            grid_ref = row.get("grid_ref", "")
            if not grid_ref:
                if self.import_mode != ImportMode.IRECORD_SYNC:
                    df.at[idx, "vc_error"] = "Grid reference is required"
                continue

            if grid_ref in vc_lookup:
                info = vc_lookup[grid_ref]
                if "error" in info:
                    df.at[idx, "vc_error"] = info["error"]
                else:
                    df.at[idx, "vc_number"] = info["vc_number"]
                    df.at[idx, "vice_county"] = info.get("vc_name", "")

        return df

    def _batch_duplicate_check(self, df: pd.DataFrame) -> pd.DataFrame:
        """Check for duplicates in batches."""
        if not self.db_manager:
            return df

        if self.import_mode == ImportMode.IRECORD_SYNC:
            # Check by external_key first, then irecord_id
            external_keys = df[df["external_key"].notna() & (df["external_key"] != "")]["external_key"].unique().tolist()
            irecord_ids = df[df["irecord_id"].notna()]["irecord_id"].unique().tolist()

            # Fault F37 (8 Oct 2026): iRecord's external key is NOT unique per record --
            # 1,276 keys are shared by 4,303 different records (one key per app sample).
            # Matching on it first sent every record of a sample to ONE existing record,
            # which the update path then overwrote. Now: the iRecord ID first (unique);
            # the external key only when it identifies exactly one record. Lookups are
            # chunked (SQLite's variable limit was a silent failure) and failures are
            # reported, not swallowed.
            ext_key_lookup = {}      # key -> {record id: (its irecord_id, species, date)}
            irecord_lookup = {}

            def _lookup(sql, values):
                out = []
                for i in range(0, len(values), 900):
                    chunk = values[i:i + 900]
                    ph = ",".join(["?"] * len(chunk))
                    out += list(self.db_manager.execute_main(sql.format(ph=ph), tuple(chunk)) or [])
                return out

            if irecord_ids:
                try:
                    for r in _lookup("SELECT irecord_id, id FROM observations WHERE irecord_id IN ({ph})",
                                     irecord_ids):
                        iid = r[0] if isinstance(r, (list, tuple)) else r["irecord_id"]
                        rid = r[1] if isinstance(r, (list, tuple)) else r["id"]
                        irecord_lookup[iid] = rid
                        irecord_lookup[str(iid)] = rid
                except Exception as e:
                    print(f"[ImportValidation] iRecord ID duplicate check FAILED: {e}")
                # 9 Oct 2026: 284 records held the iRecord number only in irecord_key (ID
                # blank), so the sync did not recognise them and added 248 again. A
                # number held either way is the same record.
                try:
                    keys = sorted({str(int(float(v))) for v in irecord_ids
                                   if str(v).strip() not in ("", "nan")})
                    for r in _lookup("SELECT irecord_key, id FROM observations "
                                     "WHERE irecord_id IS NULL AND irecord_key IN ({ph})", keys):
                        k = r[0] if isinstance(r, (list, tuple)) else r["irecord_key"]
                        rid = r[1] if isinstance(r, (list, tuple)) else r["id"]
                        k = str(k).strip()
                        irecord_lookup.setdefault(k, rid)
                        irecord_lookup.setdefault(int(k), rid)
                except Exception as e:
                    print(f"[ImportValidation] iRecord key duplicate check FAILED: {e}")
            if external_keys:
                try:
                    for r in _lookup("SELECT observatum_key, id, irecord_id, species_name, date "
                                     "FROM observations WHERE observatum_key IN ({ph})", external_keys):
                        key, rid, iid, sp, dt = (tuple(r) if isinstance(r, (list, tuple)) else
                                                 (r["observatum_key"], r["id"], r["irecord_id"],
                                                  r["species_name"], r["date"]))
                        ext_key_lookup.setdefault(key, {})[rid] = (iid, sp, dt)
                except Exception as e:
                    print(f"[ImportValidation] external key duplicate check FAILED: {e}")

            # Apply to DataFrame
            for idx, row in df.iterrows():
                irecord_id = row.get("irecord_id")
                rid = None
                if irecord_id is not None and irecord_id == irecord_id and irecord_id != "":
                    rid = irecord_lookup.get(irecord_id, irecord_lookup.get(str(irecord_id)))
                    if rid is None:
                        try:
                            rid = irecord_lookup.get(str(int(float(irecord_id))))
                        except (TypeError, ValueError):
                            pass
                if rid is not None:
                    df.at[idx, "is_duplicate"] = True
                    df.at[idx, "existing_record_id"] = rid
                    df.at[idx, "import_notes"] = f"Will update via iRecord ID (ID: {rid})"
                    continue

                ext_key = row.get("external_key", "")
                ids = ext_key_lookup.get(ext_key) if ext_key else None
                has_iid = irecord_id is not None and irecord_id == irecord_id and irecord_id != ""
                if ids and len(ids) > 1 and has_iid:
                    # Several records share the key (one per record of an app sample, or a
                    # sample iRecord holds twice). One already held with its own iRecord
                    # number and the same species and date is this sighting (9 Oct 2026:
                    # 35 such were added again because the key named more than one record).
                    sp = " ".join(str(row.get("species_name") or "").split()).casefold()
                    dt = str(row.get("date") or "")[:10]
                    held = [rid for rid, (eiid, esp, edt) in ids.items()
                            if eiid not in (None, "")
                            and " ".join(str(esp or "").split()).casefold() == sp
                            and str(edt or "")[:10] == dt]
                    if held:
                        df.at[idx, "is_duplicate"] = True
                        df.at[idx, "existing_record_id"] = held[0]
                        df.at[idx, "import_notes"] = (f"iRecord holds this twice; already held "
                                                      f"as record {held[0]}")
                    continue
                if ids and len(ids) == 1:
                    rid, (existing_iid, ex_sp, ex_dt) = next(iter(ids.items()))
                    has_iid = irecord_id is not None and irecord_id == irecord_id and irecord_id != ""
                    if has_iid and existing_iid not in (None, ""):
                        # Tied to a DIFFERENT iRecord ID. iRecord holds some records twice
                        # (an app sample sent twice: same external key, same content, two
                        # IDs -- 374 found 8 Oct 2026). Same species and date: the copy we
                        # already hold, so not imported again. Otherwise: another record.
                        same = (" ".join(str(row.get("species_name") or "").split()).casefold()
                                == " ".join(str(ex_sp or "").split()).casefold()
                                and str(row.get("date") or "")[:10] == str(ex_dt or "")[:10])
                        if same:
                            df.at[idx, "is_duplicate"] = True
                            df.at[idx, "existing_record_id"] = rid
                            try:
                                shown = int(float(irecord_id))
                            except (TypeError, ValueError):
                                shown = irecord_id
                            df.at[idx, "import_notes"] = (f"iRecord holds this twice (ID {shown} "
                                                          f"and {existing_iid}); already held as record {rid}")
                        continue
                    df.at[idx, "is_duplicate"] = True
                    df.at[idx, "existing_record_id"] = rid
                    df.at[idx, "import_notes"] = f"Will update via External key (ID: {rid})"

        else:
            # Personal upload: check by species + date + grid_ref
            # Build lookup keys
            df["_dup_key"] = df["species_name"] + "|" + df["date"].astype(str) + "|" + df["grid_ref"]
            unique_keys = df[
                (df["species_name"].notna()) & (df["species_name"] != "") &
                (df["date"].notna()) & (df["date"] != "") &
                (df["grid_ref"].notna()) & (df["grid_ref"] != "")
            ]["_dup_key"].unique().tolist()

            dup_lookup = {}
            for key in unique_keys:
                if self._cancelled:
                    break
                parts = key.split("|")
                if len(parts) == 3:
                    species, date, grid = parts
                    try:
                        result = self.db_manager.execute_main(
                            "SELECT id FROM observations WHERE species_name = ? AND date = ? AND grid_ref = ?",
                            (species, date, grid)
                        )
                        if result and len(result) > 0:
                            rid = result[0][0] if isinstance(result[0], (list, tuple)) else result[0]["id"]
                            dup_lookup[key] = rid
                    except Exception:
                        pass

            # Apply to DataFrame
            for idx, row in df.iterrows():
                dup_key = row.get("_dup_key", "")
                if dup_key and dup_key in dup_lookup:
                    df.at[idx, "is_duplicate"] = True
                    df.at[idx, "existing_record_id"] = dup_lookup[dup_key]

            # Remove temp column
            if "_dup_key" in df.columns:
                df = df.drop(columns=["_dup_key"])

        return df


    def _enrich_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Enrich data with derived fields: taxon_group from order, lat/lon from grid_ref."""
        # Derive taxon_group from order_name where missing
        for idx, row in df.iterrows():
            if not row.get("taxon_group") and row.get("order_name"):
                order = row["order_name"]
                group = ORDER_TO_GROUP.get(order)
                if group:
                    df.at[idx, "taxon_group"] = group

            # Derive lat/lon from grid_ref where missing
            if row.get("grid_ref") and (not row.get("latitude") or not row.get("longitude")):
                try:
                    if self._vc_service:
                        parsed = self._vc_service.parse_grid_ref(row["grid_ref"])
                        if parsed:
                            easting, northing, precision = parsed
                            # Centre of the square, with the OSGB36 -> WGS84 shift (9 Oct
                            # 2026, F30). _osgb36_to_wgs84 used the corner and no shift.
                            from shared.osgb import gridref_to_wgs84
                            lat, lon = gridref_to_wgs84(row["grid_ref"])
                            df.at[idx, "latitude"] = lat
                            df.at[idx, "longitude"] = lon
                            df.at[idx, "geodetic_datum"] = "WGS84"
                            if not row.get("grid_precision"):
                                df.at[idx, "grid_precision"] = precision
                except Exception:
                    pass

        # Compute taxonomic sort key from TVK
        if 'species_tvk' in df.columns:
            def _get_sort_key(tvk):
                if not tvk:
                    return None
                try:
                    cursor = self.uksi_conn.execute(
                        'SELECT sort_code, "order" FROM taxa WHERE tvk = ?', (tvk,)
                    )
                    result = cursor.fetchone()
                    if result:
                        sort_code = result[0] or 0
                        order_name = result[1] or ''
                        return compute_taxonomic_sort_key(order_name, sort_code)
                except Exception:
                    pass
                return None

            def _get_superfamily(tvk):
                if not tvk:
                    return ''
                try:
                    cursor = self.uksi_conn.execute(
                        'SELECT superfamily FROM taxa WHERE tvk = ?', (tvk,)
                    )
                    result = cursor.fetchone()
                    return result[0] or '' if result else ''
                except Exception:
                    return ''

            def _get_subfamily(tvk):
                if not tvk:
                    return ''
                try:
                    cursor = self.uksi_conn.execute(
                        'SELECT sf.scientific_name FROM taxa sp '
                              'JOIN taxa g ON sp.parent_tvk = g.tvk '
                              'JOIN taxa sf ON g.parent_tvk = sf.tvk AND sf.rank = "Subfamily" '
                              'WHERE sp.tvk = ? '
                              'UNION '
                              'SELECT sf.scientific_name FROM taxa sp '
                              'JOIN taxa g ON sp.parent_tvk = g.tvk '
                              'JOIN taxa t ON g.parent_tvk = t.tvk '
                              'JOIN taxa sf ON t.parent_tvk = sf.tvk AND sf.rank = "Subfamily" '
                              'WHERE sp.tvk = ? '
                              'LIMIT 1', (tvk, tvk)
                    )
                    result = cursor.fetchone()
                    return result[0] or '' if result else ''
                except Exception:
                    return ''

            df['taxonomic_sort_key'] = df['species_tvk'].apply(_get_sort_key)
            df['superfamily'] = df['species_tvk'].apply(_get_superfamily)
            df['subfamily'] = df['species_tvk'].apply(_get_subfamily)

        return df
    def _build_validated_rows(self, df: pd.DataFrame) -> List[ObservationImportRow]:
        """Build final ObservationImportRow objects from DataFrame."""
        validated = []
        total = len(df)

        for idx, row_data in df.iterrows():
            if self._cancelled:
                break

            errors = []
            warnings = []

            # Collect errors from batch processing
            if row_data.get("species_error"):
                errors.append(row_data["species_error"])
            if row_data.get("vc_error"):
                errors.append(row_data["vc_error"])

            # Collect warnings
            if row_data.get("species_warning"):
                warnings.append(row_data["species_warning"])
            if row_data.get("vc_warning"):
                warnings.append(row_data["vc_warning"])

            # Additional validation for personal uploads
            if self.import_mode != ImportMode.IRECORD_SYNC:
                if not row_data.get("date"):
                    errors.append("Date is required")
                if not row_data.get("recorder"):
                    errors.append("Recorder is required")

                # Validate dropdown values
                sex = str(row_data.get("sex", "")).lower()
                if sex and sex not in VALID_SEX_VALUES:
                    warnings.append(f"Non-standard Sex: {sex}")

                stage = str(row_data.get("stage", "")).lower()
                if stage and stage not in VALID_STAGE_VALUES:
                    warnings.append(f"Non-standard Stage: {stage}")
            else:
                # iRecord validation
                if not row_data.get("species_name"):
                    errors.append("Missing species name")
                if not row_data.get("date"):
                    errors.append("Missing date")
                if not row_data.get("grid_ref"):
                    warnings.append("Missing grid reference")

            # Determine status
            if errors:
                status = RowStatus.ERROR
                error_msg = "; ".join(errors)
            elif warnings:
                status = RowStatus.WARNING
                error_msg = "; ".join(warnings)
            else:
                status = RowStatus.VALID
                error_msg = ""

            # Build row object
            import_row = ObservationImportRow(
                row_number=int(row_data.get("row_number", idx)),
                raw_data=row_data.get("raw_data", {}),
                status=status,
                error_message=error_msg,
                warnings=warnings,
                is_irecord=bool(row_data.get("is_irecord", False)),
                irecord_id=_safe_get(row_data, "irecord_id"),
                record_key=_safe_get(row_data, "record_key", ""),
                external_key=_safe_get(row_data, "external_key", ""),
                species_name=_safe_get(row_data, "species_name", ""),
                species_tvk=_safe_get(row_data, "species_tvk", ""),
                common_name=_safe_get(row_data, "common_name", ""),
                order_name=_safe_get(row_data, "order_name", ""),
                family=_safe_get(row_data, "family", ""),
                kingdom=_safe_get(row_data, "kingdom", ""),
                taxon_group=_safe_get(row_data, "taxon_group", ""),
                taxon_rank=_safe_get(row_data, "taxon_rank", ""),
                date=_safe_get(row_data, "date", ""),
                date_from=_safe_get(row_data, "date_from", ""),
                date_to=_safe_get(row_data, "date_to", ""),
                date_type=_safe_get(row_data, "date_type", "D"),
                grid_ref=_safe_get(row_data, "grid_ref", ""),
                grid_precision=_safe_get(row_data, "grid_precision"),
                vice_county=_safe_get(row_data, "vice_county", ""),
                vc_number=_safe_get(row_data, "vc_number"),
                site_name=_safe_get(row_data, "site_name", ""),
                latitude=_safe_get(row_data, "latitude"),
                longitude=_safe_get(row_data, "longitude"),
                geodetic_datum=_safe_get(row_data, "geodetic_datum", ""),
                sensitive=int(row_data.get("sensitive", 0) or 0),
                sensitive_site=_safe_get(row_data, "sensitive_site", ""),
                sensitive_output_map_ref=_safe_get(row_data, "sensitive_output_map_ref", ""),
                recorder=_safe_get(row_data, "recorder", ""),
                determiner=_safe_get(row_data, "determiner", ""),
                recorder_certainty=_safe_get(row_data, "recorder_certainty", ""),
                sex=_safe_get(row_data, "sex", ""),
                stage=_safe_get(row_data, "stage", ""),
                quantity=int(row_data.get("quantity", 1) or 1),
                zero_abundance=int(row_data.get("zero_abundance", 0) or 0),
                method=_safe_get(row_data, "method", ""),
                comment=_safe_get(row_data, "comment", ""),
                sample_comment=_safe_get(row_data, "sample_comment", ""),
                biotope=_safe_get(row_data, "biotope", ""),
                verification_status=_safe_get(row_data, "verification_status", ""),
                verification_status_2=_safe_get(row_data, "verification_status_2", ""),
                verifier=_safe_get(row_data, "verifier", ""),
                verified_on=_safe_get(row_data, "verified_on", ""),
                automated_checks=_safe_get(row_data, "automated_checks", ""),
                source=_safe_get(row_data, "source", ""),
                images=_safe_get(row_data, "images", ""),
                licence=_safe_get(row_data, "licence", ""),
                input_on_date=_safe_get(row_data, "input_on_date", ""),
                last_edited_date=_safe_get(row_data, "last_edited_date", ""),
                is_duplicate=bool(row_data.get("is_duplicate", False)),
                existing_record_id=_safe_get(row_data, "existing_record_id"),
                import_notes=_safe_get(row_data, "import_notes", "") or
                             _safe_get(row_data, "species_warning", "") or
                             _safe_get(row_data, "warning", ""),
            )

            validated.append(import_row)

            # Update counters
            if status == RowStatus.VALID:
                self.valid_count += 1
            elif status == RowStatus.WARNING:
                self.warning_count += 1
            elif status == RowStatus.ERROR:
                self.error_count += 1

            # Emit signals for UI update
            self.row_validated.emit(import_row.row_number, import_row)
            self.counts_updated.emit(self.valid_count, self.warning_count, self.error_count)

        return validated

    def _parse_date(self, date_str: str) -> Optional[str]:
        """Parse various date formats to ISO format."""
        if not date_str:
            return None
        date_str = date_str.strip()
        formats = [
            "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y",
            "%d-%m-%y", "%Y/%m/%d", "%d %b %Y", "%d %B %Y",
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    def _parse_int(self, value) -> Optional[int]:
        """Safely parse to int."""
        if not value:
            return None
        try:
            return int(float(str(value).strip()))
        except (ValueError, TypeError):
            return None

    def _parse_float(self, value) -> Optional[float]:
        """Safely parse to float."""
        if not value:
            return None
        try:
            return float(str(value).strip())
        except (ValueError, TypeError):
            return None
