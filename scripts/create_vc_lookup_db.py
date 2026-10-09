"""
Vice County Lookup Database Generator.

Creates a SQLite database mapping 1km OS Grid squares to Watsonian Vice Counties.

Requires:
- A Vice County boundary shapefile (e.g., from NBN Atlas or BSBI)
- Python packages: geopandas, shapely

Usage:
    python create_vc_lookup_db.py --shapefile path/to/vc_boundaries.shp --output vc_lookup.db

The shapefile should have a column containing the VC number (typically named 
'VC_NUMBER', 'VCNUMBER', 'vc_num', 'VC', or similar).

Alternative: If you have a CSV with grid_ref,vc_number columns, use:
    python create_vc_lookup_db.py --csv path/to/vc_data.csv --output vc_lookup.db
"""

import argparse
import csv
import sqlite3
from typing import Optional

# Try to import spatial libraries
try:
    import geopandas as gpd
    from shapely.geometry import Point
    HAS_GEOPANDAS = True
except ImportError:
    HAS_GEOPANDAS = False


# OS Grid letter codes to 100km easting/northing
GRID_LETTERS = {
    'SV': (0, 0), 'SW': (1, 0), 'SX': (2, 0), 'SY': (3, 0), 'SZ': (4, 0), 'TV': (5, 0),
    'SQ': (0, 1), 'SR': (1, 1), 'SS': (2, 1), 'ST': (3, 1), 'SU': (4, 1), 'TQ': (5, 1), 'TR': (6, 1),
    'SL': (0, 2), 'SM': (1, 2), 'SN': (2, 2), 'SO': (3, 2), 'SP': (4, 2), 'TL': (5, 2), 'TM': (6, 2),
    'SF': (0, 3), 'SG': (1, 3), 'SH': (2, 3), 'SJ': (3, 3), 'SK': (4, 3), 'TF': (5, 3), 'TG': (6, 3),
    'SA': (0, 4), 'SB': (1, 4), 'SC': (2, 4), 'SD': (3, 4), 'SE': (4, 4), 'TA': (5, 4), 'TB': (6, 4),
    'NV': (0, 5), 'NW': (1, 5), 'NX': (2, 5), 'NY': (3, 5), 'NZ': (4, 5), 'OV': (5, 5),
    'NQ': (0, 6), 'NR': (1, 6), 'NS': (2, 6), 'NT': (3, 6), 'NU': (4, 6),
    'NL': (0, 7), 'NM': (1, 7), 'NN': (2, 7), 'NO': (3, 7), 'NP': (4, 7),
    'NF': (0, 8), 'NG': (1, 8), 'NH': (2, 8), 'NJ': (3, 8), 'NK': (4, 8),
    'NA': (0, 9), 'NB': (1, 9), 'NC': (2, 9), 'ND': (3, 9),
    'HW': (1, 10), 'HX': (2, 10), 'HY': (3, 10), 'HZ': (4, 10),
    'HP': (4, 12), 'HT': (3, 11), 'HU': (4, 11),
}

# Reverse lookup: (e100, n100) -> letters
GRID_LETTERS_REVERSE = {v: k for k, v in GRID_LETTERS.items()}


def easting_northing_to_gridref(easting: int, northing: int) -> Optional[str]:
    """Convert easting/northing to 4-figure grid reference (1km square)."""
    e100 = easting // 100000
    n100 = northing // 100000
    
    letters = GRID_LETTERS_REVERSE.get((e100, n100))
    if not letters:
        return None
    
    e_digits = (easting % 100000) // 1000
    n_digits = (northing % 100000) // 1000
    
    return f"{letters}{e_digits:02d}{n_digits:02d}"


def create_database(db_path: str) -> sqlite3.Connection:
    """Create the SQLite database with the correct schema."""
    conn = sqlite3.connect(db_path)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS vc_lookup (
            grid_1km TEXT PRIMARY KEY,
            vc_number INTEGER NOT NULL
        )
    """)
    
    conn.execute("CREATE INDEX IF NOT EXISTS idx_vc_number ON vc_lookup(vc_number)")
    
    conn.commit()
    return conn


def populate_from_csv(conn: sqlite3.Connection, csv_path: str) -> int:
    """
    Populate database from a CSV file.
    
    Expected CSV format:
        grid_ref,vc_number
        SP5020,32
        SP5021,32
        ...
    
    Or with headers like: grid_1km, vc, vc_num, etc.
    """
    count = 0
    
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        
        # Find the grid ref column
        grid_col = None
        vc_col = None
        
        for col in reader.fieldnames:
            col_lower = col.lower().strip()
            if col_lower in ('grid_ref', 'grid_1km', 'gridref', 'grid', 'gr'):
                grid_col = col
            elif col_lower in ('vc_number', 'vc_num', 'vcnumber', 'vc', 'vice_county'):
                vc_col = col
        
        if not grid_col or not vc_col:
            raise ValueError(f"Could not find grid ref and VC columns. Found: {reader.fieldnames}")
        
        print(f"Using columns: grid_ref='{grid_col}', vc_number='{vc_col}'")
        
        batch = []
        for row in reader:
            grid_ref = row[grid_col].strip().upper().replace(' ', '')
            try:
                vc_num = int(row[vc_col])
            except (ValueError, TypeError):
                continue
            
            # Normalize to 4-figure (1km) grid ref
            if len(grid_ref) > 6:
                # Truncate to 1km
                letters = grid_ref[:2]
                digits = grid_ref[2:]
                half = len(digits) // 2
                e = digits[:half][:2]
                n = digits[half:][:2]
                grid_ref = f"{letters}{e}{n}"
            
            batch.append((grid_ref, vc_num))
            
            if len(batch) >= 10000:
                conn.executemany(
                    "INSERT OR REPLACE INTO vc_lookup (grid_1km, vc_number) VALUES (?, ?)",
                    batch
                )
                conn.commit()
                count += len(batch)
                print(f"  Inserted {count} records...")
                batch = []
        
        if batch:
            conn.executemany(
                "INSERT OR REPLACE INTO vc_lookup (grid_1km, vc_number) VALUES (?, ?)",
                batch
            )
            conn.commit()
            count += len(batch)
    
    return count


def populate_from_shapefile(conn: sqlite3.Connection, shp_path: str, vc_column: str = None) -> int:
    """
    Populate database from a Vice County boundary shapefile.
    
    For each 1km grid square in GB, determines which VC polygon contains its centroid.
    """
    if not HAS_GEOPANDAS:
        raise ImportError(
            "geopandas is required for shapefile processing.\n"
            "Install with: pip install geopandas shapely"
        )
    
    print(f"Loading shapefile: {shp_path}")
    gdf = gpd.read_file(shp_path)
    
    # Find the VC number column
    if vc_column:
        if vc_column not in gdf.columns:
            raise ValueError(f"Column '{vc_column}' not found. Available: {list(gdf.columns)}")
    else:
        # Try to auto-detect
        candidates = ['VC_NUMBER', 'VCNUMBER', 'VC_NUM', 'VC', 'VICECOUNT', 'vice_county']
        for col in candidates:
            if col in gdf.columns:
                vc_column = col
                break
            if col.lower() in [c.lower() for c in gdf.columns]:
                vc_column = [c for c in gdf.columns if c.lower() == col.lower()][0]
                break
        
        if not vc_column:
            raise ValueError(
                f"Could not find VC number column. Available columns: {list(gdf.columns)}\n"
                "Specify with --vc-column"
            )
    
    print(f"Using VC column: '{vc_column}'")
    print(f"Found {len(gdf)} VC polygons")
    
    # Ensure CRS is British National Grid (EPSG:27700)
    if gdf.crs and gdf.crs.to_epsg() != 27700:
        print(f"Reprojecting from {gdf.crs} to EPSG:27700 (British National Grid)")
        gdf = gdf.to_crs(epsg=27700)
    
    # Build spatial index
    print("Building spatial index...")
    sindex = gdf.sindex
    
    # Generate all 1km grid squares and find their VCs
    count = 0
    batch = []
    
    # GB extent in BNG (roughly)
    # Easting: 0 to 700000 (0 to 7 * 100km)
    # Northing: 0 to 1300000 (0 to 13 * 100km)
    
    print("Processing grid squares...")
    total_squares = 0
    
    for e100 in range(8):  # 0-7 (800km)
        for n100 in range(14):  # 0-13 (1400km)
            letters = GRID_LETTERS_REVERSE.get((e100, n100))
            if not letters:
                continue
            
            # Process each 1km square in this 100km block
            for e_km in range(100):
                for n_km in range(100):
                    # Centroid of 1km square
                    easting = e100 * 100000 + e_km * 1000 + 500
                    northing = n100 * 100000 + n_km * 1000 + 500
                    
                    point = Point(easting, northing)
                    
                    # Query spatial index
                    possible_matches_idx = list(sindex.intersection(point.bounds))
                    
                    vc_num = None
                    for idx in possible_matches_idx:
                        if gdf.iloc[idx].geometry.contains(point):
                            try:
                                vc_num = int(gdf.iloc[idx][vc_column])
                            except (ValueError, TypeError):
                                pass
                            break
                    
                    if vc_num:
                        grid_ref = f"{letters}{e_km:02d}{n_km:02d}"
                        batch.append((grid_ref, vc_num))
                        
                        if len(batch) >= 10000:
                            conn.executemany(
                                "INSERT OR REPLACE INTO vc_lookup (grid_1km, vc_number) VALUES (?, ?)",
                                batch
                            )
                            conn.commit()
                            count += len(batch)
                            print(f"  Inserted {count} records...")
                            batch = []
                    
                    total_squares += 1
            
            print(f"  Processed 100km square {letters} ({total_squares} total squares checked)")
    
    if batch:
        conn.executemany(
            "INSERT OR REPLACE INTO vc_lookup (grid_1km, vc_number) VALUES (?, ?)",
            batch
        )
        conn.commit()
        count += len(batch)
    
    return count


def main():
    parser = argparse.ArgumentParser(
        description="Generate Vice County lookup database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # From shapefile:
  python create_vc_lookup_db.py --shapefile vc_boundaries.shp --output vc_lookup.db
  
  # From CSV:
  python create_vc_lookup_db.py --csv grid_vc_mapping.csv --output vc_lookup.db
  
  # Specify VC column name:
  python create_vc_lookup_db.py --shapefile vc.shp --vc-column VICE_COUNTY --output vc_lookup.db
        """
    )
    
    parser.add_argument('--shapefile', '-s', help='Path to VC boundary shapefile')
    parser.add_argument('--csv', '-c', help='Path to CSV with grid_ref,vc_number columns')
    parser.add_argument('--output', '-o', required=True, help='Output SQLite database path')
    parser.add_argument('--vc-column', help='Name of VC number column in shapefile')
    
    args = parser.parse_args()
    
    if not args.shapefile and not args.csv:
        parser.error("Either --shapefile or --csv is required")
    
    if args.shapefile and args.csv:
        parser.error("Specify either --shapefile or --csv, not both")
    
    # Create database
    print(f"Creating database: {args.output}")
    conn = create_database(args.output)
    
    try:
        if args.csv:
            count = populate_from_csv(conn, args.csv)
        else:
            count = populate_from_shapefile(conn, args.shapefile, args.vc_column)
        
        print(f"\nDone! Inserted {count} grid square to VC mappings.")
        print(f"Database saved to: {args.output}")
        
        # Verify
        cursor = conn.execute("SELECT COUNT(*) FROM vc_lookup")
        total = cursor.fetchone()[0]
        
        cursor = conn.execute("SELECT COUNT(DISTINCT vc_number) FROM vc_lookup")
        vc_count = cursor.fetchone()[0]
        
        print(f"Database contains {total} 1km squares across {vc_count} vice counties")
        
    finally:
        conn.close()


if __name__ == '__main__':
    main()
