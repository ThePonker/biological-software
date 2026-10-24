"""
Observatum V2 - Reset Observations Table Only
Drops and recreates the observations table. All other tables are preserved.
"""

import sqlite3
import sys; sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
import paths


DB_PATH = paths.OBSERVATUM_DB

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
    -- Taxonomic sort
    taxonomic_sort_key INTEGER,

    -- iRecord sync keys
    observatum_key TEXT,
    irecord_key TEXT,
    last_synced TEXT,
    
    -- Timestamps
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

OBS_INDEXES = """
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
CREATE INDEX IF NOT EXISTS idx_obs_taxonomic_sort ON observations(taxonomic_sort_key);
"""


def main():
    db_path = DB_PATH
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return

    confirm = input(
        "\n========================================"
        "\nRESET OBSERVATIONS TABLE ONLY"
        "\n========================================"
        "\nThis will DELETE all observation data."
        "\nRecording Scheme, Insect Collection, and Species Aliases will be preserved."
        f"\n\nDatabase: {db_path}"
        "\n\nType 'yes' to continue: "
    )

    if confirm.strip().lower() != 'yes':
        print("Cancelled.")
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT COUNT(*) FROM observations")
        count = cursor.fetchone()[0]
        print(f"\nDropping observations table ({count} records)...")

        cursor.execute("DROP TABLE IF EXISTS observations")
        cursor.executescript(CREATE_OBSERVATIONS)
        cursor.executescript(OBS_INDEXES)
        conn.commit()

        cursor.execute("PRAGMA table_info(observations)")
        cols = len(cursor.fetchall())
        print(f"  \u2713 observations table recreated ({cols} columns)")
        print(f"  \u2713 Indexes created")
        print("\nObservations reset complete. All other tables preserved.")

    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
