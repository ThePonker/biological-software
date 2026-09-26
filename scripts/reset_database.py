"""
Reset Database Script for Observatum V2.

Deletes existing databases and creates fresh EMPTY tables.
This is a DESTRUCTIVE operation - all existing data will be lost.

Usage:
    python scripts/reset_database.py
    python scripts/reset_database.py --yes  (skip confirmation)
    
This will:
1. Delete existing observatum.db
2. Delete existing gamification.db
3. Create all tables with correct schema (76-column observations table)
4. Create all indexes
5. Insert default settings only (NO test data)

To add test data after reset, run: python scripts/seed_database.py

UPDATED: Now includes full NBN Atlas / Darwin Core schema for iRecord imports.
UPDATED: Includes observatum_key and irecord_key for iRecord sync support.
"""

import sqlite3
import argparse
import sys; sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
import paths
from pathlib import Path
import sys


# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_DB_PATH = paths.OBSERVATUM_DB


# =============================================================================
# TABLE CREATION SQL
# =============================================================================

CREATE_OBSERVATIONS = """
CREATE TABLE IF NOT EXISTS observations (
    -- Primary key
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- External identity (iRecord/NBN)
    irecord_id INTEGER UNIQUE,
    record_key TEXT,
    external_key TEXT,
    event_id TEXT,
    collection_code TEXT,
    dataset_name TEXT,
    institution_code TEXT,
    source TEXT,
    
    -- Species identification
    species_name TEXT NOT NULL,
    species_tvk TEXT,
    common_name TEXT,
    order_name TEXT,
    family TEXT,
    kingdom TEXT,
    taxon_group TEXT,
    taxon_rank TEXT,
    identification_qualifier TEXT,
    identification_remarks TEXT,
    recorder_certainty TEXT,
    
    -- Date
    date TEXT NOT NULL,
    date_type TEXT DEFAULT 'D',
    
    -- Location - grid reference
    grid_ref TEXT,
    grid_precision INTEGER,
    vice_county TEXT,
    vc_number INTEGER,
    site_name TEXT,
    site_name_local TEXT,
    
    -- Location - coordinates
    latitude REAL,
    longitude REAL,
    geodetic_datum TEXT,
    location_id TEXT,
    location_remarks TEXT,
    georeference_verification_status TEXT,
    
    -- People
    recorder TEXT,
    determiner TEXT,
    verifier TEXT,
    verified_on TEXT,
    
    -- Occurrence details
    sex TEXT,
    stage TEXT,
    quantity INTEGER DEFAULT 1,
    individual_count INTEGER,
    organism_quantity TEXT,
    organism_quantity_type TEXT,
    zero_abundance INTEGER DEFAULT 0,
    method TEXT,
    observation_type TEXT,
    basis_of_record TEXT DEFAULT 'HumanObservation',
    occurrence_status TEXT DEFAULT 'present',
    
    -- Notes and comments
    comment TEXT,
    internal_notes TEXT,
    sample_comment TEXT,
    -- Sub-location / sampling context (internal; excluded from iRecord export)
    sub_location TEXT,
    trap_number TEXT,
    visit_number TEXT,
    biotope TEXT,
    
    -- Verification
    verification_status TEXT,
    verification_status_2 TEXT,
    automated_checks TEXT,
    
    -- Record management
    record_type TEXT DEFAULT 'Personal',
    project_name TEXT,
    client TEXT,
    embargo_status TEXT,
    embargo_until TEXT,
    
    -- Metadata
    licence TEXT,
    rights_holder TEXT,
    images TEXT,
    sensitive INTEGER DEFAULT 0,
    sensitive_site TEXT,
    sensitive_output_map_ref TEXT,
    input_on_date TEXT,
    last_edited_date TEXT,
    
    -- Import tracking

    import_notes TEXT,
    -- Sync management
    sync_status TEXT DEFAULT 'active',
    never_upload_to_irecord INTEGER DEFAULT 0,

    superfamily TEXT,
                subfamily TEXT,
    taxonomic_sort_key INTEGER,
    -- iRecord sync keys (NEW)
    observatum_key TEXT,
    irecord_key TEXT,
    last_synced TEXT,
    
    -- Timestamps
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_ENTRY_JOBS = """
CREATE TABLE IF NOT EXISTS entry_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    mode TEXT DEFAULT 'Personal',        -- Personal | Commercial
    client TEXT,
    project TEXT,
    embargo_until TEXT,                  -- intended embargo, applied at commit
    status TEXT DEFAULT 'active',        -- active | committed | exported | discarded
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_ENTRY_STAGING = """
CREATE TABLE IF NOT EXISTS entry_staging (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    row_order INTEGER,

    -- Species (permissive: rows may be in-progress / half-typed)
    species_name TEXT,
    species_tvk TEXT,
    common_name TEXT,
    order_name TEXT,
    family TEXT,
    taxon_rank TEXT,

    -- Per-record
    stage TEXT,
    sex TEXT,
    quantity INTEGER,

    -- Carry / context fields
    determiner TEXT,
    sub_location TEXT,
    trap_number TEXT,
    visit_number TEXT,
    date TEXT,
    site_name TEXT,
    grid_ref TEXT,
    vice_county TEXT,
    vc_number INTEGER,
    recorder TEXT,
    method TEXT,
    certainty TEXT,
    comment TEXT,

    -- Commercial
    project_name TEXT,
    client TEXT,
    embargo_until TEXT,

    -- Timestamps
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (job_id) REFERENCES entry_jobs(id)
);
"""

CREATE_COMMERCIAL_RECORDS = """
CREATE TABLE IF NOT EXISTS commercial_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name TEXT NOT NULL,
    client TEXT,
    species_name TEXT NOT NULL,
    species_tvk TEXT,
    common_name TEXT,
    order_name TEXT,
    family TEXT,
    date TEXT NOT NULL,
    grid_ref TEXT,
    vice_county TEXT,
    vc_number INTEGER,
    site_name TEXT,
    recorder TEXT,
    determiner TEXT,
    sex TEXT,
    stage TEXT,
    quantity INTEGER DEFAULT 1,
    comment TEXT,
    embargo_status TEXT DEFAULT 'Active',
    embargo_until TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_SPECIMENS = """
CREATE TABLE IF NOT EXISTS specimens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    specimen_code TEXT UNIQUE,
    species_name TEXT NOT NULL,
    species_tvk TEXT,
    common_name TEXT,
    order_name TEXT,
    family TEXT,
    subfamily TEXT,
    date_collected TEXT NOT NULL,
    grid_ref TEXT,
    vice_county TEXT,
    vc_number INTEGER,
    site_name TEXT,
    collector TEXT,
    determiner TEXT,
    sex TEXT,
    preparation_type TEXT,
    storage_location TEXT,
    drawer_unit TEXT,
    condition TEXT,
    label_data TEXT,
    notes TEXT,
    import_notes TEXT,
    observation_id INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    superfamily TEXT,
    taxonomic_sort_key INTEGER,
    taxon_group TEXT,
    FOREIGN KEY (observation_id) REFERENCES observations(id)
);
"""

CREATE_RECORDING_SCHEME = """
CREATE TABLE IF NOT EXISTS recording_scheme (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- External identity (for future iRecord sync)
    irecord_id INTEGER UNIQUE,
    record_key TEXT,
    external_key TEXT,
    event_id TEXT,
    collection_code TEXT,
    dataset_name TEXT,
    institution_code TEXT,
    source TEXT,
    
    -- Species identification
    species_name TEXT NOT NULL,
    species_tvk TEXT,
    common_name TEXT,
    order_name TEXT,
    family TEXT,
    subfamily TEXT,
    
    -- NBN Atlas / Darwin Core extensions
    nbn_atlas_id TEXT,
    occurrence_id TEXT,
    taxon_author TEXT,
    phylum TEXT,
    class_name TEXT,
    genus TEXT,
    country TEXT,
    state_province TEXT,
    
    kingdom TEXT,
    taxon_group TEXT,
    taxon_rank TEXT,
    identification_qualifier TEXT,
    identification_remarks TEXT,
    recorder_certainty TEXT,
    
    -- Date
    date TEXT NOT NULL,
    date_type TEXT DEFAULT 'D',
    
    -- Location - grid reference
    grid_ref TEXT,
    grid_precision INTEGER,
    vice_county TEXT,
    vc_number INTEGER,
    site_name TEXT,
    site_name_local TEXT,
    
    -- Location - coordinates
    latitude REAL,
    longitude REAL,
    geodetic_datum TEXT,
    location_id TEXT,
    location_remarks TEXT,
    georeference_verification_status TEXT,
    
    -- People
    recorder TEXT,
    determiner TEXT,
    verifier TEXT,
    verified_on TEXT,
    
    -- Occurrence details
    sex TEXT,
    stage TEXT,
    quantity INTEGER DEFAULT 1,
    individual_count INTEGER,
    organism_quantity TEXT,
    organism_quantity_type TEXT,
    zero_abundance INTEGER DEFAULT 0,
    method TEXT,
    basis_of_record TEXT DEFAULT 'HumanObservation',
    occurrence_status TEXT DEFAULT 'present',
    
    -- Notes and comments
    comment TEXT,
    internal_notes TEXT,
    sample_comment TEXT,
    biotope TEXT,
    
    -- Verification
    verification_status TEXT,
    verification_status_2 TEXT,
    automated_checks TEXT,
    
    -- Record management
    record_type TEXT DEFAULT 'Recording Scheme',
    project_name TEXT,
    client TEXT,
    embargo_status TEXT,
    embargo_until TEXT,
    
    -- Metadata
    licence TEXT,
    rights_holder TEXT,
    images TEXT,
    sensitive INTEGER DEFAULT 0,
    sensitive_site TEXT,
    sensitive_output_map_ref TEXT,
    input_on_date TEXT,
    last_edited_date TEXT,
    
    -- Sync management
    sync_status TEXT DEFAULT 'active',
    never_upload_to_irecord INTEGER DEFAULT 0,
    
    -- Timestamps
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                superfamily TEXT,
                taxonomic_sort_key INTEGER,
                import_notes TEXT
);
"""

CREATE_SPECIES_PROFILES = """
CREATE TABLE IF NOT EXISTS species_profiles (
    -- Wil's own species accounts. Review accounts live in
    -- codex.db.species_profiles, one per species per review.
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    species_name TEXT NOT NULL,
    species_tvk TEXT UNIQUE NOT NULL,
    common_name TEXT,
    order_name TEXT,
    family TEXT,
    conservation_status TEXT,
    uk_status TEXT,
    flight_period TEXT,
    habitat TEXT,
    notes TEXT,
    profile_text TEXT,
    image_path TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_CONSERVATION_OVERRIDES = """
CREATE TABLE IF NOT EXISTS conservation_overrides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    species_name TEXT NOT NULL,
    species_tvk TEXT,
    conservation_status TEXT NOT NULL,
    reason TEXT,
    source TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(species_name, conservation_status)
);
"""

CREATE_SAVED_FILTERS = """
CREATE TABLE IF NOT EXISTS saved_filters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    tab TEXT NOT NULL,
    filter_data TEXT NOT NULL,
    is_presaved INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, tab)
);
"""

CREATE_SETTINGS = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""

CREATE_SPECIMEN_NOTIFICATIONS = """
CREATE TABLE IF NOT EXISTS specimen_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    observation_id INTEGER NOT NULL,
    species_name TEXT NOT NULL,
    date TEXT NOT NULL,
    site_name TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (observation_id) REFERENCES observations(id)
);
"""



CREATE_INDEXES = """
-- Observations indexes
CREATE INDEX IF NOT EXISTS idx_obs_species ON observations(species_name);
CREATE INDEX IF NOT EXISTS idx_obs_tvk ON observations(species_tvk);
CREATE INDEX IF NOT EXISTS idx_obs_date ON observations(date);
CREATE INDEX IF NOT EXISTS idx_obs_vc ON observations(vc_number);
CREATE INDEX IF NOT EXISTS idx_obs_grid ON observations(grid_ref);
CREATE INDEX IF NOT EXISTS idx_obs_irecord ON observations(irecord_id);
CREATE INDEX IF NOT EXISTS idx_obs_order ON observations(order_name);
CREATE INDEX IF NOT EXISTS idx_obs_family ON observations(family);
CREATE INDEX IF NOT EXISTS idx_obs_record_type ON observations(record_type);
CREATE INDEX IF NOT EXISTS idx_obs_method ON observations(method);
CREATE INDEX IF NOT EXISTS idx_obs_obstype ON observations(observation_type);
CREATE INDEX IF NOT EXISTS idx_obs_project ON observations(project_name);
CREATE INDEX IF NOT EXISTS idx_obs_verification ON observations(verification_status);
CREATE INDEX IF NOT EXISTS idx_obs_record_key ON observations(record_key);
CREATE INDEX IF NOT EXISTS idx_obs_kingdom ON observations(kingdom);
CREATE INDEX IF NOT EXISTS idx_obs_taxon_group ON observations(taxon_group);
CREATE INDEX IF NOT EXISTS idx_obs_sync_status ON observations(sync_status);
CREATE INDEX IF NOT EXISTS idx_obs_never_upload ON observations(never_upload_to_irecord);
CREATE INDEX IF NOT EXISTS idx_obs_observatum_key ON observations(observatum_key);
CREATE INDEX IF NOT EXISTS idx_obs_irecord_key ON observations(irecord_key);

-- Specimens indexes
CREATE INDEX IF NOT EXISTS idx_spec_species ON specimens(species_name);
CREATE INDEX IF NOT EXISTS idx_spec_tvk ON specimens(species_tvk);
CREATE INDEX IF NOT EXISTS idx_spec_code ON specimens(specimen_code);
CREATE INDEX IF NOT EXISTS idx_spec_date ON specimens(date_collected);
CREATE INDEX IF NOT EXISTS idx_spec_location ON specimens(storage_location);
CREATE INDEX IF NOT EXISTS idx_spec_family ON specimens(family);
CREATE INDEX IF NOT EXISTS idx_spec_order ON specimens(order_name);
CREATE INDEX IF NOT EXISTS idx_spec_subfamily ON specimens(subfamily);

-- Recording scheme indexes
CREATE INDEX IF NOT EXISTS idx_scheme_species ON recording_scheme(species_name);
CREATE INDEX IF NOT EXISTS idx_scheme_tvk ON recording_scheme(species_tvk);
CREATE INDEX IF NOT EXISTS idx_scheme_date ON recording_scheme(date);
CREATE INDEX IF NOT EXISTS idx_scheme_vc ON recording_scheme(vc_number);
CREATE INDEX IF NOT EXISTS idx_scheme_grid ON recording_scheme(grid_ref);
CREATE INDEX IF NOT EXISTS idx_scheme_family ON recording_scheme(family);
CREATE INDEX IF NOT EXISTS idx_scheme_irecord ON recording_scheme(irecord_id);
CREATE INDEX IF NOT EXISTS idx_scheme_record_key ON recording_scheme(record_key);

-- Species profiles index
CREATE INDEX IF NOT EXISTS idx_profile_species ON species_profiles(species_name);
CREATE INDEX IF NOT EXISTS idx_profile_tvk ON species_profiles(species_tvk);

-- Conservation overrides index
CREATE INDEX IF NOT EXISTS idx_cons_species ON conservation_overrides(species_name);
CREATE INDEX IF NOT EXISTS idx_cons_tvk ON conservation_overrides(species_tvk);

-- Data entry staging indexes
CREATE INDEX IF NOT EXISTS idx_entry_staging_job ON entry_staging(job_id);
CREATE INDEX IF NOT EXISTS idx_entry_jobs_status ON entry_jobs(status);

"""


# =============================================================================
# DEFAULT SETTINGS
# =============================================================================

DEFAULT_SETTINGS = [
    ('default_recorder', 'Heeney, W'),
    ('default_determiner', 'Heeney, W'),
    ('date_format', 'dd/mm/yyyy'),
    ('grid_ref_format', '6-figure'),
    ('auto_calculate_vc', '1'),
    ('font_size', 'medium'),
    ('irecord_sync_frequency', 'manual'),
    ('irecord_last_sync', ''),
]


# =============================================================================
# DATABASE FUNCTIONS
# =============================================================================

def delete_databases(db_path: Path) -> bool:
    """Delete the database files if they exist."""
    success = True
    
    # Delete main database
    if db_path.exists():
        try:
            db_path.unlink()
            print(f"  ✓ Deleted: {db_path}")
        except Exception as e:
            print(f"  ✗ Failed to delete: {e}")
            success = False
    else:
        print(f"  - No existing database: {db_path.name}")
    
    # Delete gamification database
    gamification_db = db_path.parent / "gamification.db"
    if gamification_db.exists():
        try:
            gamification_db.unlink()
            print(f"  ✓ Deleted: {gamification_db}")
        except Exception as e:
            print(f"  ✗ Failed to delete gamification.db: {e}")
    
    return success


def create_tables(cursor):
    """Create all tables."""
    print("\n[2/4] Creating tables...")
    
    tables = [
        ('observations', CREATE_OBSERVATIONS),
        ('commercial_records', CREATE_COMMERCIAL_RECORDS),
        ('specimens', CREATE_SPECIMENS),
        ('recording_scheme', CREATE_RECORDING_SCHEME),
        ('species_profiles', CREATE_SPECIES_PROFILES),
        ('conservation_overrides', CREATE_CONSERVATION_OVERRIDES),
        ('saved_filters', CREATE_SAVED_FILTERS),
        ('settings', CREATE_SETTINGS),
        ('specimen_notifications', CREATE_SPECIMEN_NOTIFICATIONS),
        ('entry_jobs', CREATE_ENTRY_JOBS),
        ('entry_staging', CREATE_ENTRY_STAGING),
    ]
    
    for name, sql in tables:
        cursor.execute(sql)
        print(f"  ✓ {name}")


def create_indexes(cursor):
    """Create all indexes."""
    print("\n[3/4] Creating indexes...")
    cursor.executescript(CREATE_INDEXES)
    print("  ✓ All indexes created")


def insert_settings(cursor):
    """Insert default settings."""
    cursor.executemany(
        "INSERT INTO settings (key, value) VALUES (?, ?)",
        DEFAULT_SETTINGS
    )


def verify_schema(cursor):
    """Verify the observations table has the expected column count."""
    cursor.execute("PRAGMA table_info(observations)")
    columns = cursor.fetchall()
    count = len(columns)
    
    # Check for key sync columns
    column_names = [col[1] for col in columns]
    has_observatum_key = 'observatum_key' in column_names
    has_irecord_key = 'irecord_key' in column_names
    has_last_synced = 'last_synced' in column_names
    
    if count >= 76:
        print(f"  ✓ observations table: {count} columns")
    else:
        print(f"  ⚠ observations table: {count} columns (expected 76+)")
    
    if has_observatum_key and has_irecord_key and has_last_synced:
        print(f"  ✓ iRecord sync columns present")
    else:
        missing = []
        if not has_observatum_key:
            missing.append('observatum_key')
        if not has_irecord_key:
            missing.append('irecord_key')
        if not has_last_synced:
            missing.append('last_synced')
        print(f"  ⚠ Missing sync columns: {', '.join(missing)}")
    
    return count


# =============================================================================
# MAIN
# =============================================================================

def reset_database(db_path: Path):
    """
    Delete and recreate the database with empty tables.
    
    Args:
        db_path: Path to database file
    """
    print("\n" + "=" * 60)
    print("OBSERVATUM V2 - DATABASE RESET")
    print("=" * 60)
    print(f"\nTarget: {db_path}")
    print("Mode: Empty database (no test data)")
    print("Schema: Full 76-column observations table (iRecord compatible)")
    print("        Includes observatum_key/irecord_key for sync")
    
    # Step 1: Delete existing databases
    print("\n[1/4] Deleting existing databases...")
    if not delete_databases(db_path):
        print("\nAborted: Could not delete existing database.")
        return False
    
    # Ensure data directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Connect and create new database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Step 2: Create tables
        create_tables(cursor)
        
        # Step 3: Create indexes
        create_indexes(cursor)
        
        # Step 4: Insert default settings
        print("\n[4/4] Inserting default settings...")
        insert_settings(cursor)
        print(f"  ✓ {len(DEFAULT_SETTINGS)} settings")
        
        conn.commit()
        
        # Verify schema
        print("\n[Verification]")
        verify_schema(cursor)
        
        # Summary
        print("\n" + "=" * 60)
        print("DATABASE RESET COMPLETE")
        print("=" * 60)
        print("\nEmpty tables created:")
        print("  - observations (76 columns - full iRecord schema + sync keys)")
        print("  - specimens") 
        print("  - recording_scheme (expanded schema)")
        print("  - commercial_records")
        print("  - species_profiles")
        print("  - conservation_overrides")
        print("  - saved_filters")
        print("  - settings")
        print("  - specimen_notifications")
        print("  - entry_jobs (data-entry grid: job registry)")
        print("  - entry_staging (data-entry grid: in-progress rows)")
        
        print(f"\nDatabase: {db_path}")
        print(f"Size: {db_path.stat().st_size / 1024:.1f} KB")
        print("\nTo add test data, run: python scripts/seed_database.py")
        print("=" * 60 + "\n")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description='Reset Observatum database (DELETE and recreate empty)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/reset_database.py          # Reset with confirmation prompt
  python scripts/reset_database.py --yes    # Skip confirmation prompt
  
To add test data after reset:
  python scripts/seed_database.py
        """
    )
    parser.add_argument(
        '--path', '-p',
        type=str,
        default=str(DEFAULT_DB_PATH),
        help=f'Path to database (default: data/observatum.db)'
    )
    parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help='Skip confirmation prompt'
    )
    
    args = parser.parse_args()
    db_path = Path(args.path)
    
    # Confirmation prompt
    if not args.yes:
        print("\n" + "!" * 60)
        print("WARNING: This will DELETE all data in:")
        print(f"  {db_path}")
        print(f"  {db_path.parent / 'gamification.db'}")
        print("!" * 60)
        
        response = input("\nType 'yes' to continue: ").strip().lower()
        if response != 'yes':
            print("\nAborted.")
            sys.exit(0)
    
    # Run reset
    success = reset_database(db_path)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
