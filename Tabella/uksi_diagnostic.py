#!/usr/bin/env python3
"""
UKSI Database Diagnostic Script

Run this to check:
1. What ranks exist in the database
2. How aggregates are stored  
3. If Welsh names exist and how to filter them

Usage: python uksi_diagnostic.py
"""

import sqlite3
from pathlib import Path


def find_database() -> Path:
    """Find the UKSI database."""
    candidates = [
        Path('data/uksi.db'),
        Path('../data/uksi.db'),
        Path('../../data/uksi.db'),
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def main():
    db_path = find_database()
    if not db_path:
        print("ERROR: Could not find data/uksi.db")
        return
    
    print(f"Database: {db_path.resolve()}")
    print("=" * 60)
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    
    # 1. Check what ranks exist
    print("\n1. RANKS IN DATABASE:")
    print("-" * 40)
    cursor = conn.execute("""
        SELECT rank, COUNT(*) as count 
        FROM taxa 
        GROUP BY rank 
        ORDER BY count DESC
    """)
    for row in cursor.fetchall():
        print(f"  {row['rank']}: {row['count']:,}")
    
    # 2. Search for Taraxacum entries
    print("\n2. TARAXACUM ENTRIES:")
    print("-" * 40)
    cursor = conn.execute("""
        SELECT scientific_name, rank 
        FROM taxa 
        WHERE scientific_name LIKE 'Taraxacum%'
        ORDER BY scientific_name
        LIMIT 30
    """)
    rows = cursor.fetchall()
    if rows:
        for row in rows:
            print(f"  {row['scientific_name']} [{row['rank']}]")
        if len(rows) == 30:
            print("  ... (more entries, limit 30 shown)")
    else:
        print("  No Taraxacum entries found!")
    
    # 3. Check common_names table structure
    print("\n3. COMMON_NAMES TABLE STRUCTURE:")
    print("-" * 40)
    cursor = conn.execute("PRAGMA table_info(common_names)")
    columns = cursor.fetchall()
    for col in columns:
        print(f"  {col['name']} ({col['type']})")
    
    # 4. Check if there's a language column or Welsh names
    print("\n4. SAMPLE COMMON NAMES (checking for Welsh):")
    print("-" * 40)
    cursor = conn.execute("""
        SELECT t.scientific_name, c.common_name
        FROM common_names c
        JOIN taxa t ON c.tvk = t.tvk
        WHERE c.common_name LIKE '%wennol%'  -- Welsh for swallow
           OR c.common_name LIKE '%Gwenynen%'  -- Welsh for bee
           OR c.common_name LIKE 'Y %'  -- Common Welsh article
           OR c.common_name LIKE 'Yr %'
        LIMIT 20
    """)
    rows = cursor.fetchall()
    if rows:
        print("  Possible Welsh names found:")
        for row in rows:
            print(f"    {row['scientific_name']}: {row['common_name']}")
    else:
        print("  No obvious Welsh names found in sample")
    
    # 5. Check for Bombus common names
    print("\n5. BOMBUS COMMON NAMES:")
    print("-" * 40)
    cursor = conn.execute("""
        SELECT t.scientific_name, c.common_name
        FROM common_names c
        JOIN taxa t ON c.tvk = t.tvk
        WHERE t.scientific_name LIKE 'Bombus%'
        LIMIT 30
    """)
    for row in cursor.fetchall():
        print(f"  {row['scientific_name']}: {row['common_name']}")
    
    # 6. Check if multiple common names per species
    print("\n6. SPECIES WITH MULTIPLE COMMON NAMES:")
    print("-" * 40)
    cursor = conn.execute("""
        SELECT t.scientific_name, COUNT(c.common_name) as name_count
        FROM common_names c
        JOIN taxa t ON c.tvk = t.tvk
        GROUP BY t.tvk
        HAVING name_count > 1
        ORDER BY name_count DESC
        LIMIT 10
    """)
    rows = cursor.fetchall()
    if rows:
        for row in rows:
            print(f"  {row['scientific_name']}: {row['name_count']} names")
        
        # Show example of multiple names
        if rows:
            example = rows[0]['scientific_name']
            print(f"\n  Example names for {example}:")
            cursor = conn.execute("""
                SELECT c.common_name
                FROM common_names c
                JOIN taxa t ON c.tvk = t.tvk
                WHERE t.scientific_name = ?
            """, (example,))
            for row in cursor.fetchall():
                print(f"    - {row['common_name']}")
    else:
        print("  All species have single common names")
    
    conn.close()
    
    print("\n" + "=" * 60)
    print("RECOMMENDATIONS:")
    print("-" * 40)
    print("""
1. If Taraxacum agg. not found: Check the exact rank name used
   for aggregates in your UKSI extract.

2. If Welsh names appear: The UKSI export may include multiple
   languages. Consider adding a filter in uksi_lookup.py to
   prefer English names (if a language column exists) or take
   only the first common name per species.

3. Run this script after any UKSI database changes to verify
   the data structure.
""")


if __name__ == '__main__':
    main()
