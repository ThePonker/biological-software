"""
Observatum V2 - Reset Insect Collection (Specimens) Table Only
Drops and recreates the specimens table. All other tables are preserved.
"""

import sqlite3
import sys; sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
import paths
from pathlib import Path


DB_PATH = paths.OBSERVATUM_DB

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
    site_name_local TEXT,
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
            taxon_group TEXT,
    superfamily TEXT,
    taxonomic_sort_key INTEGER,
    observation_id INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (observation_id) REFERENCES observations(id)
);
"""

SPEC_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_spec_species ON specimens(species_name);
CREATE INDEX IF NOT EXISTS idx_spec_tvk ON specimens(species_tvk);
CREATE INDEX IF NOT EXISTS idx_spec_code ON specimens(specimen_code);
CREATE INDEX IF NOT EXISTS idx_spec_date ON specimens(date_collected);
CREATE INDEX IF NOT EXISTS idx_spec_location ON specimens(storage_location);
CREATE INDEX IF NOT EXISTS idx_spec_family ON specimens(family);
CREATE INDEX IF NOT EXISTS idx_spec_order ON specimens(order_name);
CREATE INDEX IF NOT EXISTS idx_spec_subfamily ON specimens(subfamily);
CREATE INDEX IF NOT EXISTS idx_spec_taxonomic_sort ON specimens(taxonomic_sort_key);
"""


def main():
    db_path = DB_PATH
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return

    confirm = input(
        "\n========================================"
        "\nRESET INSECT COLLECTION TABLE ONLY"
        "\n========================================"
        "\nThis will DELETE all specimen/insect collection data."
        "\nObservations, Recording Scheme, and Species Aliases will be preserved."
        f"\n\nDatabase: {db_path}"
        "\n\nType 'yes' to continue: "
    )

    if confirm.strip().lower() != 'yes':
        print("Cancelled.")
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT COUNT(*) FROM specimens")
        count = cursor.fetchone()[0]
        print(f"\nDropping specimens table ({count} records)...")

        cursor.execute("DROP TABLE IF EXISTS specimens")
        cursor.executescript(CREATE_SPECIMENS)
        cursor.executescript(SPEC_INDEXES)
        conn.commit()

        cursor.execute("PRAGMA table_info(specimens)")
        cols = len(cursor.fetchall())
        print(f"  \u2713 specimens table recreated ({cols} columns)")
        print(f"  \u2713 Indexes created")
        print("\nInsect Collection reset complete. All other tables preserved.")

    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
