"""
Seed Database Script for Observatum V2.

Adds realistic test data to an existing database.
Clears existing data from observations, specimens, and recording_scheme first.

Usage:
    python scripts/seed_database.py
    python scripts/seed_database.py --yes  (skip confirmation)
    
This will:
1. Clear existing records from observations, specimens, recording_scheme
2. Insert 150 personal observations (with observatum_key for sync)
3. Insert 50 commercial observations (with observatum_key for sync)
4. Insert 80 specimen records
5. Insert 200 recording scheme records

Run reset_database.py first if you need to recreate the database structure.

UPDATED: Generates observatum_key for all seeded observations for iRecord sync.
"""

import sqlite3
import argparse
import sys; sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
import paths
from pathlib import Path
import random
import sys


# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_DB_PATH = paths.OBSERVATUM_DB

# Default user initials for seeded data
DEFAULT_INITIALS = "WJH"


# =============================================================================
# SAMPLE DATA
# =============================================================================

SAMPLE_SPECIES = [
    # Diptera - Tachinidae
    {'name': 'Gymnosoma rotundatum', 'common': None, 'order': 'Diptera', 'family': 'Tachinidae', 'subfamily': 'Phasiinae', 'tvk': None},
    {'name': 'Phasia hemiptera', 'common': None, 'order': 'Diptera', 'family': 'Tachinidae', 'subfamily': 'Phasiinae', 'tvk': None},
    {'name': 'Eriothrix rufomaculata', 'common': None, 'order': 'Diptera', 'family': 'Tachinidae', 'subfamily': 'Dexiinae', 'tvk': None},
    {'name': 'Tachina fera', 'common': None, 'order': 'Diptera', 'family': 'Tachinidae', 'subfamily': 'Tachininae', 'tvk': None},
    {'name': 'Nowickia ferox', 'common': None, 'order': 'Diptera', 'family': 'Tachinidae', 'subfamily': 'Tachininae', 'tvk': None},
    {'name': 'Phasia obesa', 'common': None, 'order': 'Diptera', 'family': 'Tachinidae', 'subfamily': 'Phasiinae', 'tvk': None},
    {'name': 'Cistogaster globosa', 'common': None, 'order': 'Diptera', 'family': 'Tachinidae', 'subfamily': 'Phasiinae', 'tvk': None},
    # Diptera - Syrphidae
    {'name': 'Volucella bombylans', 'common': 'Bumblebee Hoverfly', 'order': 'Diptera', 'family': 'Syrphidae', 'subfamily': None, 'tvk': 'NBNSYS0000007094'},
    {'name': 'Episyrphus balteatus', 'common': 'Marmalade Hoverfly', 'order': 'Diptera', 'family': 'Syrphidae', 'subfamily': None, 'tvk': 'NBNSYS0000006916'},
    {'name': 'Eristalis tenax', 'common': 'Drone Fly', 'order': 'Diptera', 'family': 'Syrphidae', 'subfamily': None, 'tvk': None},
    # Coleoptera - Cerambycidae
    {'name': 'Rutpela maculata', 'common': 'Spotted Longhorn', 'order': 'Coleoptera', 'family': 'Cerambycidae', 'subfamily': 'Lepturinae', 'tvk': 'NHMSYS0020109270'},
    {'name': 'Clytus arietis', 'common': 'Wasp Beetle', 'order': 'Coleoptera', 'family': 'Cerambycidae', 'subfamily': 'Cerambycinae', 'tvk': 'NBNSYS0000011045'},
    {'name': 'Rhagium mordax', 'common': 'Black-spotted Longhorn', 'order': 'Coleoptera', 'family': 'Cerambycidae', 'subfamily': 'Lepturinae', 'tvk': 'NBNSYS0000011004'},
    {'name': 'Rhagium bifasciatum', 'common': 'Two-banded Longhorn', 'order': 'Coleoptera', 'family': 'Cerambycidae', 'subfamily': 'Lepturinae', 'tvk': 'NBNSYS0000011002'},
    {'name': 'Grammoptera ruficornis', 'common': None, 'order': 'Coleoptera', 'family': 'Cerambycidae', 'subfamily': 'Lepturinae', 'tvk': 'NHMSYS0020152218'},
    {'name': 'Leiopus nebulosus', 'common': None, 'order': 'Coleoptera', 'family': 'Cerambycidae', 'subfamily': 'Lamiinae', 'tvk': 'NHMSYS0021125200'},
    {'name': 'Pogonocherus hispidus', 'common': 'Lesser Thorn-tipped Longhorn', 'order': 'Coleoptera', 'family': 'Cerambycidae', 'subfamily': 'Lamiinae', 'tvk': 'NBNSYS0000011054'},
    {'name': 'Agapanthia villosoviridescens', 'common': 'Golden-bloomed Grey Longhorn', 'order': 'Coleoptera', 'family': 'Cerambycidae', 'subfamily': 'Lamiinae', 'tvk': 'NHMSYS0020151160'},
    {'name': 'Aromia moschata', 'common': 'Musk Beetle', 'order': 'Coleoptera', 'family': 'Cerambycidae', 'subfamily': 'Cerambycinae', 'tvk': 'NBNSYS0000011038'},
    {'name': 'Prionus coriarius', 'common': 'Tanner Beetle', 'order': 'Coleoptera', 'family': 'Cerambycidae', 'subfamily': 'Prioninae', 'tvk': 'NBNSYS0000010996'},
    # Coleoptera - other families
    {'name': 'Cicindela campestris', 'common': 'Green Tiger Beetle', 'order': 'Coleoptera', 'family': 'Carabidae', 'subfamily': None, 'tvk': 'NBNSYS0000007122'},
    {'name': 'Lucanus cervus', 'common': 'Stag Beetle', 'order': 'Coleoptera', 'family': 'Lucanidae', 'subfamily': None, 'tvk': 'NBNSYS0000011448'},
    {'name': 'Cetonia aurata', 'common': 'Rose Chafer', 'order': 'Coleoptera', 'family': 'Scarabaeidae', 'subfamily': 'Cetoniinae', 'tvk': None},
    # Hymenoptera
    {'name': 'Bombus pascuorum', 'common': 'Common Carder Bee', 'order': 'Hymenoptera', 'family': 'Apidae', 'subfamily': None, 'tvk': 'NHMSYS0000875576'},
    {'name': 'Bombus lapidarius', 'common': 'Red-tailed Bumblebee', 'order': 'Hymenoptera', 'family': 'Apidae', 'subfamily': None, 'tvk': 'NHMSYS0000875567'},
    {'name': 'Andrena fulva', 'common': 'Tawny Mining Bee', 'order': 'Hymenoptera', 'family': 'Andrenidae', 'subfamily': None, 'tvk': None},
    {'name': 'Vespa crabro', 'common': 'European Hornet', 'order': 'Hymenoptera', 'family': 'Vespidae', 'subfamily': None, 'tvk': None},
    # Hemiptera
    {'name': 'Graphosoma italicum', 'common': 'Striped Shieldbug', 'order': 'Hemiptera', 'family': 'Pentatomidae', 'subfamily': None, 'tvk': 'NHMSYS0021371849'},
    {'name': 'Palomena prasina', 'common': 'Green Shield Bug', 'order': 'Hemiptera', 'family': 'Pentatomidae', 'subfamily': None, 'tvk': None},
    {'name': 'Coreus marginatus', 'common': 'Dock Bug', 'order': 'Hemiptera', 'family': 'Coreidae', 'subfamily': None, 'tvk': None},
    # Lepidoptera
    {'name': 'Aglais io', 'common': 'Peacock', 'order': 'Lepidoptera', 'family': 'Nymphalidae', 'subfamily': None, 'tvk': 'NHMSYS0021143568'},
    {'name': 'Vanessa atalanta', 'common': 'Red Admiral', 'order': 'Lepidoptera', 'family': 'Nymphalidae', 'subfamily': None, 'tvk': 'NHMSYS0000504624'},
    {'name': 'Pieris brassicae', 'common': 'Large White', 'order': 'Lepidoptera', 'family': 'Pieridae', 'subfamily': None, 'tvk': 'NHMSYS0000503827'},
]

SAMPLE_LOCATIONS = [
    {'site': 'Bernwood Forest', 'grid': 'SP610115', 'vc': 'Oxfordshire', 'vc_num': 23},
    {'site': 'Otmoor', 'grid': 'SP570130', 'vc': 'Oxfordshire', 'vc_num': 23},
    {'site': 'Shotover Country Park', 'grid': 'SP560060', 'vc': 'Oxfordshire', 'vc_num': 23},
    {'site': 'Wytham Woods', 'grid': 'SP460080', 'vc': 'Berkshire', 'vc_num': 22},
    {'site': 'Aston Rowant NNR', 'grid': 'SU730970', 'vc': 'Oxfordshire', 'vc_num': 23},
    {'site': 'Warburg Reserve', 'grid': 'SU720880', 'vc': 'Oxfordshire', 'vc_num': 23},
    {'site': 'Savernake Forest', 'grid': 'SU230670', 'vc': 'North Wiltshire', 'vc_num': 7},
    {'site': 'Windsor Great Park', 'grid': 'SU950730', 'vc': 'Berkshire', 'vc_num': 22},
    {'site': 'Burnham Beeches', 'grid': 'SU950850', 'vc': 'Buckinghamshire', 'vc_num': 24},
    {'site': 'Chesham Bois Wood', 'grid': 'SU960000', 'vc': 'Buckinghamshire', 'vc_num': 24},
    {'site': 'College Lake', 'grid': 'SP930140', 'vc': 'Buckinghamshire', 'vc_num': 24},
    {'site': 'Finemere Wood', 'grid': 'SP710200', 'vc': 'Buckinghamshire', 'vc_num': 24},
]

SAMPLE_PROJECTS = [
    {'name': 'Thames Valley Ecology Survey', 'client': 'Environment Agency'},
    {'name': 'Bernwood Biodiversity Assessment', 'client': 'Forestry England'},
    {'name': 'HS2 Invertebrate Survey', 'client': 'HS2 Ltd'},
]


# =============================================================================
# KEY GENERATION
# =============================================================================

class ObservatumKeyGenerator:
    """Generates unique observatum keys for sync with iRecord."""
    
    def __init__(self, initials: str = DEFAULT_INITIALS):
        self.initials = initials
        self._date_counters = {}  # {date_str: next_sequence}
    
    def generate(self, date_str: str) -> str:
        """
        Generate a unique key for a given date.
        
        Format: OBS-{initials}-{YYYYMMDD}-{sequence}
        Example: OBS-WJH-20240615-0001
        
        Args:
            date_str: ISO date string (YYYY-MM-DD)
            
        Returns:
            Unique observatum_key
        """
        # Convert date to compact format
        date_compact = date_str.replace('-', '')
        
        # Get or initialize counter for this date
        if date_compact not in self._date_counters:
            self._date_counters[date_compact] = 1
        
        sequence = self._date_counters[date_compact]
        self._date_counters[date_compact] += 1
        
        return f"OBS-{self.initials}-{date_compact}-{sequence:04d}"


# =============================================================================
# DATA GENERATION FUNCTIONS
# =============================================================================

def random_date(start_year=2020, end_year=2025):
    """Generate a random date string in ISO format (YYYY-MM-DD)."""
    year = random.randint(start_year, end_year)
    # Weight towards summer months for realistic entomology data
    if random.random() > 0.3:
        month = random.randint(5, 9)
    else:
        month = random.randint(1, 12)
    
    if month in [4, 6, 9, 11]:
        max_day = 30
    elif month == 2:
        if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
            max_day = 29
        else:
            max_day = 28
    else:
        max_day = 31
    
    day = random.randint(1, max_day)
    return f"{year}-{month:02d}-{day:02d}"


def generate_observations(count=150, key_generator=None):
    """Generate sample observation records with observatum_key."""
    records = []
    irecord_base = 10000000
    
    methods = ['Hand search', 'Sweep-net', 'Beating tray', 'Visual encounter', 
               'Pitfall trap', 'Malaise trap', 'Light trap', None, None]
    obs_types = ['Field sighting', 'Field record', 'Collected', 'Voucher specimen', 
                 'Swept', 'Caught', None, None]
    
    for i in range(count):
        species = random.choice(SAMPLE_SPECIES)
        location = random.choice(SAMPLE_LOCATIONS)
        date = random_date()
        
        record = {
            'irecord_id': irecord_base + i if random.random() > 0.3 else None,
            'species_name': species['name'],
            'species_tvk': species['tvk'],
            'common_name': species['common'],
            'order_name': species['order'],
            'family': species['family'],
            'date': date,
            'date_type': 'D',
            'grid_ref': location['grid'],
            'grid_precision': 100,
            'vice_county': location['vc'],
            'vc_number': location['vc_num'],
            'site_name': location['site'],
            'recorder': 'Heeney, W',
            'determiner': random.choice(['Heeney, W', 'Heeney, W', 'Heeney, W', 'Smith, J']),
            'sex': random.choice([None, 'Male', 'Female', None, None]),
            'stage': random.choice(['Adult', 'Larva', 'Pupa', 'Adult', 'Adult']),
            'quantity': random.choices([1, 2, 3, 5, 10], weights=[60, 20, 10, 7, 3])[0],
            'method': random.choice(methods),
            'observation_type': random.choice(obs_types),
            'comment': random.choice([None, None, 'On flower', 'Under bark', 'Swept from grassland']),
            'verification_status': random.choice(['Accepted', 'Accepted', 'Unconfirmed', 'Pending']),
            'record_type': 'Personal',
            'project_name': None,
            'client': None,
            'embargo_status': None,
            'embargo_until': None,
            'observatum_key': key_generator.generate(date) if key_generator else None,
            'sync_status': 'local',
        }
        records.append(record)
    
    return records


def generate_commercial_records(count=50, key_generator=None):
    """Generate sample commercial observation records with observatum_key."""
    records = []
    irecord_base = 20000000
    
    methods = ['Hand search', 'Sweep-net', 'Beating tray', 'Pitfall trap', 'Malaise trap']
    
    for i in range(count):
        species = random.choice(SAMPLE_SPECIES)
        location = random.choice(SAMPLE_LOCATIONS)
        project = random.choice(SAMPLE_PROJECTS)
        date = random_date(2022, 2025)
        
        record = {
            'irecord_id': irecord_base + i if random.random() > 0.5 else None,
            'species_name': species['name'],
            'species_tvk': species['tvk'],
            'common_name': species['common'],
            'order_name': species['order'],
            'family': species['family'],
            'date': date,
            'date_type': 'D',
            'grid_ref': location['grid'],
            'grid_precision': 100,
            'vice_county': location['vc'],
            'vc_number': location['vc_num'],
            'site_name': location['site'],
            'recorder': random.choice(['Heeney, W', 'Jones, A', 'Brown, M']),
            'determiner': 'Heeney, W',
            'sex': random.choice([None, 'Male', 'Female', None]),
            'stage': random.choice(['Adult', 'Larva', 'Adult', 'Adult']),
            'quantity': random.choices([1, 2, 5, 10, 25], weights=[40, 25, 20, 10, 5])[0],
            'method': random.choice(methods),
            'observation_type': 'Field record',
            'comment': random.choice([None, 'Survey transect', 'Targeted search', None]),
            'verification_status': 'Accepted',
            'record_type': 'Commercial',
            'project_name': project['name'],
            'client': project['client'],
            'embargo_status': random.choice(['Active', 'Active', 'Released']),
            'embargo_until': '2026-12-31' if random.random() > 0.5 else None,
            'observatum_key': key_generator.generate(date) if key_generator else None,
            'sync_status': 'local',
        }
        records.append(record)
    
    return records


def generate_specimens(count=80):
    """Generate sample specimen records."""
    records = []
    
    # Focus on Coleoptera for specimens
    beetle_species = [s for s in SAMPLE_SPECIES if s['order'] == 'Coleoptera']
    prep_types = ['Pinned', 'Carded', 'In alcohol', 'Slide mounted']
    conditions = ['Excellent', 'Good', 'Fair', 'Poor']
    
    for i in range(count):
        species = random.choice(beetle_species)
        location = random.choice(SAMPLE_LOCATIONS)
        
        record = {
            'specimen_code': f"COL-{2020 + (i // 20)}-{(i % 100) + 1:04d}",
            'species_name': species['name'],
            'species_tvk': species['tvk'],
            'common_name': species['common'],
            'order_name': species['order'],
            'family': species['family'],
            'subfamily': species['subfamily'],
            'date_collected': random_date(2018, 2025),
            'grid_ref': location['grid'],
            'vice_county': location['vc'],
            'vc_number': location['vc_num'],
            'site_name': location['site'],
            'collector': 'Heeney, W',
            'determiner': random.choice(['Heeney, W', 'Heeney, W', 'Expert, A']),
            'sex': random.choice([None, 'Male', 'Female']),
            'preparation_type': random.choice(prep_types),
            'storage_location': f"Cabinet {random.randint(1, 5)}",
            'drawer_number': f"Unit {random.randint(1, 20)}",
            'condition': random.choices(conditions, weights=[40, 35, 20, 5])[0],
            'import_notes': None,
        }
        records.append(record)
    
    return records


def generate_recording_scheme(count=200):
    """Generate sample recording scheme records."""
    records = []
    
    sources = ['iRecord', 'NBN Atlas', 'BWARS database', 'Direct submission', None]
    
    for i in range(count):
        species = random.choice(SAMPLE_SPECIES)
        location = random.choice(SAMPLE_LOCATIONS)
        
        record = {
            'species_name': species['name'],
            'species_tvk': species['tvk'],
            'common_name': species['common'],
            'order_name': species['order'],
            'family': species['family'],
            'subfamily': species.get('subfamily'),
            'date': random_date(2015, 2025),
            'date_type': random.choice(['D', 'D', 'DD', 'M', 'Y']),
            'grid_ref': location['grid'],
            'grid_precision': random.choice([100, 1000, 2000]),
            'vice_county': location['vc'],
            'vc_number': location['vc_num'],
            'site_name': location['site'] if random.random() > 0.3 else None,
            'recorder': random.choice(['Heeney, W', 'Smith, J', 'Brown, M', 'Jones, A', 'Wilson, B']),
            'determiner': random.choice(['Heeney, W', 'Smith, J', None, None]),
            'sex': random.choice([None, 'Male', 'Female', None, None]),
            'stage': random.choice(['Adult', 'Larva', None, None, 'Adult']),
            'quantity': random.choices([1, 2, 5, None], weights=[50, 20, 10, 20])[0],
            'source': random.choice(sources),
            'verification_status': random.choice(['Accepted', 'Accepted', 'Accepted', 'Unconfirmed']),
        }
        records.append(record)
    
    return records


# =============================================================================
# DATABASE OPERATIONS
# =============================================================================

def clear_tables(cursor):
    """Clear existing data from main tables."""
    print("\n[1/2] Clearing existing data...")
    
    tables = ['observations', 'specimens', 'recording_scheme']
    for table in tables:
        cursor.execute(f"DELETE FROM {table}")
        print(f"  ✓ Cleared {table}")


def insert_observations(cursor, records):
    """Insert observation records."""
    cursor.executemany("""
        INSERT INTO observations (
            irecord_id, species_name, species_tvk, common_name, order_name, family,
            date, date_type, grid_ref, grid_precision, vice_county, vc_number, site_name,
            recorder, determiner, sex, stage, quantity, method, observation_type,
            comment, verification_status, record_type, project_name, client, 
            embargo_status, embargo_until, observatum_key, sync_status
        ) VALUES (
            :irecord_id, :species_name, :species_tvk, :common_name, :order_name, :family,
            :date, :date_type, :grid_ref, :grid_precision, :vice_county, :vc_number, :site_name,
            :recorder, :determiner, :sex, :stage, :quantity, :method, :observation_type,
            :comment, :verification_status, :record_type, :project_name, :client,
            :embargo_status, :embargo_until, :observatum_key, :sync_status
        )
    """, records)


def insert_specimens(cursor, records):
    """Insert specimen records."""
    cursor.executemany("""
        INSERT INTO specimens (
            specimen_code, species_name, species_tvk, common_name, order_name, family, subfamily,
            date_collected, grid_ref, vice_county, vc_number, site_name,
            collector, determiner, sex, preparation_type, storage_location, drawer_number, condition,
            import_notes
        ) VALUES (
            :specimen_code, :species_name, :species_tvk, :common_name, :order_name, :family, :subfamily,
            :date_collected, :grid_ref, :vice_county, :vc_number, :site_name,
            :collector, :determiner, :sex, :preparation_type, :storage_location, :drawer_number, :condition,
            :import_notes
        )
    """, records)


def insert_recording_scheme(cursor, records):
    """Insert recording scheme records."""
    cursor.executemany("""
        INSERT INTO recording_scheme (
            species_name, species_tvk, common_name, order_name, family, subfamily,
            date, date_type, grid_ref, grid_precision, vice_county, vc_number,
            site_name, recorder, determiner, sex, stage, quantity, source, verification_status
        ) VALUES (
            :species_name, :species_tvk, :common_name, :order_name, :family, :subfamily,
            :date, :date_type, :grid_ref, :grid_precision, :vice_county, :vc_number,
            :site_name, :recorder, :determiner, :sex, :stage, :quantity, :source, :verification_status
        )
    """, records)


def seed_data(cursor, initials: str = DEFAULT_INITIALS):
    """Generate and insert all test data."""
    print("\n[2/2] Inserting test data...")
    
    # Create key generator
    key_gen = ObservatumKeyGenerator(initials)
    
    # Generate data
    observations = generate_observations(150, key_gen)
    commercial = generate_commercial_records(50, key_gen)
    specimens = generate_specimens(80)
    recording_scheme = generate_recording_scheme(200)
    
    # Insert data
    insert_observations(cursor, observations)
    print(f"  ✓ 150 personal observations (with observatum_key)")
    
    insert_observations(cursor, commercial)
    print(f"  ✓ 50 commercial observations (with observatum_key)")
    
    insert_specimens(cursor, specimens)
    print(f"  ✓ 80 specimens")
    
    insert_recording_scheme(cursor, recording_scheme)
    print(f"  ✓ 200 recording scheme records")


# =============================================================================
# MAIN
# =============================================================================

def seed_database(db_path: Path, initials: str = DEFAULT_INITIALS):
    """
    Seed the database with test data.
    
    Args:
        db_path: Path to database file
        initials: User initials for observatum_key generation
    """
    print("\n" + "=" * 60)
    print("OBSERVATUM V2 - SEED DATABASE")
    print("=" * 60)
    print(f"\nTarget: {db_path}")
    print(f"User initials for keys: {initials}")
    
    if not db_path.exists():
        print(f"\n✗ Error: Database not found: {db_path}")
        print("Run reset_database.py first to create the database.")
        return False
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Step 1: Clear existing data
        clear_tables(cursor)
        
        # Step 2: Seed new data
        seed_data(cursor, initials)
        
        conn.commit()
        
        # Summary
        print("\n" + "=" * 60)
        print("DATABASE SEEDED SUCCESSFULLY")
        print("=" * 60)
        
        # Show record counts
        tables = ['observations', 'specimens', 'recording_scheme']
        print("\nRecord counts:")
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  {table}: {count:,} records")
        
        # Show observation breakdown
        cursor.execute("SELECT record_type, COUNT(*) FROM observations GROUP BY record_type")
        print("\nObservation breakdown:")
        for row in cursor.fetchall():
            print(f"  - {row[0]}: {row[1]:,}")
        
        # Show observatum_key sample
        cursor.execute("SELECT observatum_key FROM observations WHERE observatum_key IS NOT NULL LIMIT 3")
        keys = cursor.fetchall()
        if keys:
            print("\nSample observatum_keys:")
            for key in keys:
                print(f"  - {key[0]}")
        
        print("\n" + "=" * 60 + "\n")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description='Seed Observatum database with test data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/seed_database.py          # Seed with confirmation prompt
  python scripts/seed_database.py --yes    # Skip confirmation prompt
  python scripts/seed_database.py --initials ABC  # Use custom initials
  
This will CLEAR existing data in observations, specimens, and recording_scheme.
Run reset_database.py first if you need to recreate the database structure.
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
    parser.add_argument(
        '--initials', '-i',
        type=str,
        default=DEFAULT_INITIALS,
        help=f'User initials for observatum_key (default: {DEFAULT_INITIALS})'
    )
    
    args = parser.parse_args()
    db_path = Path(args.path)
    
    # Confirmation prompt
    if not args.yes:
        print("\n" + "!" * 60)
        print("WARNING: This will CLEAR existing data in:")
        print("  - observations")
        print("  - specimens")
        print("  - recording_scheme")
        print(f"\nDatabase: {db_path}")
        print(f"User initials: {args.initials}")
        print("!" * 60)
        
        response = input("\nType 'yes' to continue: ").strip().lower()
        if response != 'yes':
            print("\nAborted.")
            sys.exit(0)
    
    # Run seed
    success = seed_database(db_path, args.initials)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
