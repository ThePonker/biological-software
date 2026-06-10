# Vice County Lookup Database Generator

This folder contains scripts to generate the `vc_lookup.db` SQLite database that maps 1km OS Grid squares to Watsonian Vice Counties.

## Quick Start

### Option 1: Extract from Existing Data (Easiest)

If you already have observation records with grid references and vice counties assigned (from iRecord exports, MapMate, or other sources):

```bash
# From your Observatum database:
python extract_vc_from_observations.py --db path/to/observatum.db --output vc_lookup.db

# Or from a CSV export:
python extract_vc_from_observations.py --csv path/to/records.csv --output vc_lookup.db
```

**Note:** This only includes grid squares present in your data. For full GB coverage, use Option 2.

### Option 2: From a Shapefile (Recommended for Full Coverage)

1. **Download VC boundary data** from one of these sources:
   
   - **NBN Atlas** (free, registration required):
     - Go to: https://registry.nbnatlas.org/public/show/dr2791
     - Download "Vice County boundaries (Great Britain)"
   
   - **BSBI** (Botanical Society of Britain & Ireland):
     - Contact BSBI for their VC shapefile
   
   - **UK Data Service**:
     - Search for "Watsonian Vice Counties"

2. **Install dependencies**:
   ```bash
   pip install geopandas shapely
   ```

3. **Run the generator**:
   ```bash
   python create_vc_lookup_db.py --shapefile path/to/vc_boundaries.shp --output vc_lookup.db
   ```

4. **Copy the database** to your Observatum data folder:
   ```
   data/vc_lookup.db
   ```

### Option 3: From a CSV

If you have existing data mapping grid references to vice counties:

1. Create a CSV file with columns `grid_ref` and `vc_number`:
   ```csv
   grid_ref,vc_number
   SP5020,32
   SP5021,32
   SP5022,32
   ...
   ```

2. Run:
   ```bash
   python create_vc_lookup_db.py --csv your_data.csv --output vc_lookup.db
   ```

## Database Schema

The generated database contains:

```sql
-- Main lookup table
CREATE TABLE vc_lookup (
    grid_1km TEXT PRIMARY KEY,  -- e.g., "SP5020"
    vc_number INTEGER NOT NULL  -- e.g., 32
);

-- VC names reference table  
CREATE TABLE vc_names (
    vc_number INTEGER PRIMARY KEY,
    vc_name TEXT NOT NULL
);
```

## Requirements

- Python 3.8+
- For shapefile processing: `geopandas`, `shapely`
- For CSV processing: No additional dependencies

## Troubleshooting

### "Could not find VC number column"
Specify the column name explicitly:
```bash
python create_vc_lookup_db.py --shapefile vc.shp --vc-column VICE_COUNTY --output vc_lookup.db
```

### Processing is slow
The shapefile processor checks ~900,000 potential 1km squares. This takes time but only needs to be done once.

### Missing some grid squares
Some coastal/edge squares may not have VC assignments. This is normal for areas outside GB.

## File Locations

Place the generated `vc_lookup.db` in one of these locations:
- `data/vc_lookup.db` (relative to Observatum root)
- `src/data/vc_lookup.db`

The VCLookupService will automatically find it.
