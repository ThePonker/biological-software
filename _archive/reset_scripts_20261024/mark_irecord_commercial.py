"""
Observatum V2 - Mark Commercial Records from iRecord Downloads

Reads iRecord download CSVs for commercial sites and marks matching
records in the observations table as Commercial with project/client metadata.

Run after importing the main iRecord download as Personal data.

Usage:
    python scripts/mark_irecord_commercial.py

CSV files are expected in:
    test data/Commercial/iRecord Downloads/
"""

import sqlite3
import csv
import sys; sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
import paths
from pathlib import Path


# Base path for iRecord commercial downloads
IRECORD_DIR = Path(__file__).parent.parent / "Observatum" / "test data" / "Commercial" / "iRecord Downloads"
DB_PATH = paths.OBSERVATUM_DB

# =========================================================================
# CONFIGURATION: Add/edit entries as you download more commercial sites
# =========================================================================
COMMERCIAL_SITES = [
    {
        "csv": "Bicester 1 iRecord download.csv",
        "project": "Bicester Graven Hill",
        "client": "Watermans",
    },
    {
        "csv": "Badshot Lea iRecord Commercial.csv",
        "project": "Badshot Lea",
        "client": "Nicholsons",
    },
    # Kent Deadwood - 28 records identified by ID directly (no separate CSV)
    # These are handled in MANUAL_IDS below
]

# Manual IDs for records identified from the main iRecord download
# (where no separate site download exists)
MANUAL_ENTRIES = [
    {
        "description": "Kent Deadwood (from main iRecord download - Ranscombe, Shoreham, Ashenbank)",
        "project": "Kent Deadwood",
        "client": "NNR Declaration",
        "ids": [
            # Ranscombe - 16/04/2024
            # Shoreham, Kent - 15/04/2024
            # Ashen Bank Wood - 15/04/2024
            # IDs extracted from iRecord download matching VC 15/16 Kent sites
        ],
    },
]


def load_ids_from_csv(csv_path: Path) -> set:
    """Load iRecord IDs from a site-specific iRecord download CSV."""
    ids = set()
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for r in reader:
            rid = r.get('ID', '').strip()
            if rid:
                try:
                    ids.add(int(rid))
                except ValueError:
                    pass
    return ids


def extract_kent_ids(main_download: Path) -> list:
    """Extract Kent Deadwood IDs from the main iRecord download."""
    kent_sites = ['ranscombe', 'shoreham', 'ashen bank', 'ashenbank']
    ids = []
    with open(main_download, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for r in reader:
            site = r.get('Site name', '').strip().lower()
            vc = r.get('VC number', '').strip()
            if vc in ('15', '16') and any(s in site for s in kent_sites):
                rid = r.get('ID', '').strip()
                if rid:
                    try:
                        ids.append(int(rid))
                    except ValueError:
                        pass
    return ids


def main():
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        return

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    total_updated = 0
    results = []

    # Process CSV-based sites
    for site in COMMERCIAL_SITES:
        csv_path = IRECORD_DIR / site["csv"]
        if not csv_path.exists():
            print(f"  WARNING: CSV not found: {csv_path}")
            results.append((site["project"], 0, "CSV not found"))
            continue

        ids = load_ids_from_csv(csv_path)
        if not ids:
            results.append((site["project"], 0, "No IDs in CSV"))
            continue

        placeholders = ','.join(str(i) for i in ids)
        cursor.execute(f"SELECT COUNT(*) as cnt FROM observations WHERE irecord_id IN ({placeholders})")
        found = cursor.fetchone()['cnt']

        cursor.execute(f"""
            UPDATE observations
            SET record_type = 'Commercial',
                project_name = ?,
                client = ?
            WHERE irecord_id IN ({placeholders})
        """, (site["project"], site["client"]))

        updated = cursor.rowcount
        total_updated += updated
        results.append((site["project"], updated, f"of {len(ids)} IDs, {found} found"))

    # Process Kent Deadwood from main download
    main_download = Path(__file__).parent.parent / "Observatum" / "test data" / "iRecord Data Download" / "download-695d696d275028.29502661.csv"
    if not main_download.exists():
        # Try test data location
        main_download = Path(__file__).parent.parent / "Observatum" / "test data" / "iRecord Data Download" / "download-695d696d275028.29502661.csv"

    if main_download.exists():
        kent_ids = extract_kent_ids(main_download)
        if kent_ids:
            placeholders = ','.join(str(i) for i in kent_ids)
            cursor.execute(f"""
                UPDATE observations
                SET record_type = 'Commercial',
                    project_name = 'Kent Deadwood',
                    client = 'NNR Declaration'
                WHERE irecord_id IN ({placeholders})
            """)
            updated = cursor.rowcount
            total_updated += updated
            results.append(("Kent Deadwood (auto)", updated, f"of {len(kent_ids)} IDs"))
    else:
        print("  Note: Main iRecord download not found for Kent ID extraction")

    conn.commit()

    # Summary
    print("\n========================================")
    print("MARK iRECORD COMMERCIAL - RESULTS")
    print("========================================\n")

    for project, count, detail in results:
        status = "✓" if count > 0 else "✗"
        print(f"  {status} {project:30s}  {count:5d} records  ({detail})")

    print(f"\n  Total records marked Commercial: {total_updated}")

    # Verify totals
    cursor.execute("""
        SELECT record_type, COUNT(*) as cnt
        FROM observations
        GROUP BY record_type
        ORDER BY record_type
    """)
    print("\n  Database totals:")
    for r in cursor.fetchall():
        print(f"    {r['record_type'] or 'NULL':15s}  {r['cnt']:6d} records")

    conn.close()


if __name__ == "__main__":
    main()
