"""
Observatum V2 - Reset Commercial Observations Only
Deletes observations where record_type is Commercial.
Personal/iRecord data and table schema are preserved.
"""

import sqlite3
import sys; sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
import paths


DB_PATH = paths.OBSERVATUM_DB


def main():
    db_path = DB_PATH
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Count what will be deleted
    cursor.execute("SELECT COUNT(*) FROM observations WHERE record_type = 'Commercial'")
    commercial_count = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM observations WHERE record_type = 'Personal' OR record_type IS NULL OR record_type = ''"
    )
    personal_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM observations")
    total_count = cursor.fetchone()[0]

    # Show breakdown by project
    cursor.execute(
        "SELECT project_name, client, COUNT(*) FROM observations "
        "WHERE record_type = 'Commercial' GROUP BY project_name, client ORDER BY COUNT(*) DESC"
    )
    projects = cursor.fetchall()

    confirm_text = (
        "\n========================================"
        "\nRESET COMMERCIAL OBSERVATIONS ONLY"
        "\n========================================"
        f"\n\nTotal observations: {total_count}"
        f"\nCommercial records to DELETE: {commercial_count}"
        f"\nPersonal records to KEEP: {personal_count}"
    )

    if projects:
        confirm_text += "\n\nCommercial data breakdown:"
        for proj, client, count in projects:
            confirm_text += f"\n  {proj or '(no project)'} / {client or '(no client)'}: {count} records"

    confirm_text += (
        "\n\nPersonal data, Insect Collection, Recording Scheme,"
        "\nand Species Aliases will be preserved."
        f"\n\nDatabase: {db_path}"
        "\n\nType 'yes' to continue: "
    )

    confirm = input(confirm_text)

    if confirm.strip().lower() != 'yes':
        print("Cancelled.")
        conn.close()
        return

    try:
        cursor.execute("DELETE FROM observations WHERE record_type = 'Commercial'")
        deleted = cursor.rowcount
        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM observations")
        remaining = cursor.fetchone()[0]

        print(f"\n  \u2713 Deleted {deleted} commercial observation records")
        print(f"  \u2713 Remaining observations: {remaining}")
        print("\nCommercial observations reset complete. Personal data preserved.")

    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
