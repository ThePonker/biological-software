"""
Observatum V2 - Reset Personal Observations Only
Deletes observations where record_type is Personal, NULL, or empty.
Commercial data and table schema are preserved.
"""

import sqlite3
import sys; sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
import paths
from pathlib import Path


DB_PATH = paths.OBSERVATUM_DB


def main():
    db_path = DB_PATH
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Count what will be deleted
    cursor.execute(
        "SELECT COUNT(*) FROM observations WHERE record_type = 'Personal' OR record_type IS NULL OR record_type = ''"
    )
    personal_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM observations WHERE record_type = 'Commercial'")
    commercial_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM observations")
    total_count = cursor.fetchone()[0]

    confirm = input(
        "\n========================================"
        "\nRESET PERSONAL OBSERVATIONS ONLY"
        "\n========================================"
        f"\n\nTotal observations: {total_count}"
        f"\nPersonal records to DELETE: {personal_count}"
        f"\nCommercial records to KEEP: {commercial_count}"
        "\n\nCommercial data, Insect Collection, Recording Scheme,"
        "\nand Species Aliases will be preserved."
        f"\n\nDatabase: {db_path}"
        "\n\nType 'yes' to continue: "
    )

    if confirm.strip().lower() != 'yes':
        print("Cancelled.")
        conn.close()
        return

    try:
        cursor.execute(
            "DELETE FROM observations WHERE record_type = 'Personal' OR record_type IS NULL OR record_type = ''"
        )
        deleted = cursor.rowcount
        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM observations")
        remaining = cursor.fetchone()[0]

        print(f"\n  \u2713 Deleted {deleted} personal observation records")
        print(f"  \u2713 Remaining observations: {remaining}")
        print("\nPersonal observations reset complete. Commercial data preserved.")

    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
