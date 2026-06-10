"""
Import Codex Review -- Batch import a species status review into codex.db (v2)

Takes a CSV with species names/TVKs and status values, validates against UKSI,
shows a preview, then imports into manual_entries + status_summary with
review tracking. If the CSV includes a profile-text column, those paragraphs
populate species_profiles at the same time (per Codex Strategy doc, sec 5.2).

CSV format (minimum columns):
    species_name, status_value

Optional columns:
    tvk             -- explicit TVK (avoids name resolution)
    iucn_version    -- "2001", "1994", "pre 1994"
    detail          -- status detail (e.g. "Breeding" for bird IUCN entries,
                       "WCA Sch5" for legal protection, jurisdiction for priority)
    notes           -- free-text per-species notes
    profile_text    -- paragraph of ecological/habitat info to store as profile

Column header detection is flexible (case-insensitive, common synonyms).

v2 changes:
  - VALID_TRACKS updated to the 11-track scheme
  - status_detail support throughout
  - species_profiles population from profile_text column
  - origin = 'manual' (was 'review' -- aligned with codex.db v5 schema)
  - removed dead `from seed_codex import` line

Usage:
    python scripts/import_codex_review.py review.csv \\
        --name "GB Macro-moth Red List" \\
        --author "Fox, Parsons & Harrower, 2019" \\
        --group "Lepidoptera" \\
        --track threat_iucn_2001 \\
        [--detail "Breeding"] \\
        [--supersedes 1] \\
        [--dry-run]
"""

import argparse
import csv
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import paths

CODEX_PATH = str(paths.CODEX_DB)
UKSI_PATH = str(paths.UKSI_DB)

# 11-track scheme (Codex Strategy doc, section 3)
VALID_TRACKS = [
    "threat_iucn_2001",
    "threat_iucn_legacy",
    "threat_global_iucn",
    "rarity_modern",
    "rarity_legacy",
    "bocc",
    "specialist_panel",
    "legal_protection",
    "priority",
    "red_list_england",
    "red_list_wales",
]


def resolve_species(uksi_conn, name, tvk=None):
    """Resolve a species name to a UKSI TVK.
    Returns (tvk, matched_name) or (None, None).
    """
    # If TVK provided, verify it exists
    if tvk:
        row = uksi_conn.execute(
            "SELECT scientific_name FROM taxa WHERE tvk = ?", (tvk,)
        ).fetchone()
        if row:
            return tvk, row[0]

    # Try exact name match (species rank)
    row = uksi_conn.execute(
        """SELECT tvk, scientific_name FROM taxa
           WHERE scientific_name = ? AND rank = 'Species' LIMIT 1""",
        (name,)
    ).fetchone()
    if row:
        return row[0], row[1]

    # Case-insensitive
    row = uksi_conn.execute(
        """SELECT tvk, scientific_name FROM taxa
           WHERE LOWER(scientific_name) = LOWER(?) AND rank = 'Species' LIMIT 1""",
        (name,)
    ).fetchone()
    if row:
        return row[0], row[1]

    return None, None


def main():
    parser = argparse.ArgumentParser(
        description="Import a species status review into Codex"
    )
    parser.add_argument("csv_file",
                        help="Path to CSV file with species + statuses")
    parser.add_argument("--name", required=True,
                        help="Review name (e.g. 'GB Macro-moth Red List')")
    parser.add_argument("--author", required=True,
                        help="Author(s) and year (e.g. 'Fox et al., 2019')")
    parser.add_argument("--group", required=True,
                        help="Taxon group (e.g. 'Lepidoptera')")
    parser.add_argument("--track", required=True, choices=VALID_TRACKS,
                        help="Status track to populate")
    parser.add_argument("--detail", default=None,
                        help="Default status_detail for all entries (e.g. 'Breeding')")
    parser.add_argument("--supersedes", type=int, default=None,
                        help="Review ID this supersedes")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview only, don't import")
    parser.add_argument("--date", default=None,
                        help="Publication date (YYYY-MM-DD), defaults to today")
    args = parser.parse_args()

    csv_path = Path(args.csv_file)
    if not csv_path.exists():
        print(f"CSV file not found: {csv_path}")
        return 1

    if not Path(CODEX_PATH).exists():
        print(f"codex.db not found: {CODEX_PATH}")
        return 1

    if not Path(UKSI_PATH).exists():
        print(f"uksi.db not found: {UKSI_PATH}")
        return 1

    pub_date = args.date or datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().isoformat()

    codex = sqlite3.connect(CODEX_PATH)

    # ============================================================
    # Read CSV
    # ============================================================
    print(f"Reading: {csv_path}")
    entries = []
    has_profile_col = False
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        print(f"  Columns: {', '.join(headers)}")

        # Detect column names (case-insensitive synonyms)
        name_col = next((h for h in headers if h.lower() in
                         ("species_name", "species", "taxon",
                          "scientific_name", "name")), None)
        value_col = next((h for h in headers if h.lower() in
                          ("status_value", "status", "category",
                           "red_list", "rarity", "value")), None)
        tvk_col = next((h for h in headers if h.lower() in
                        ("tvk", "taxonversionkey", "tvk_key")), None)
        notes_col = next((h for h in headers if h.lower() in
                          ("notes", "comment", "criteria")), None)
        iucn_col = next((h for h in headers if h.lower() in
                         ("iucn_version", "iucn", "criteria_version")), None)
        detail_col = next((h for h in headers if h.lower() in
                           ("detail", "status_detail", "specifier")), None)
        profile_col = next((h for h in headers if h.lower() in
                            ("profile_text", "profile", "ecology",
                             "description", "habitat_notes")), None)

        if not name_col:
            print(f"ERROR: No species name column found. "
                  f"Expected: species_name, species, taxon, or name")
            return 1
        if not value_col:
            print(f"ERROR: No status value column found. "
                  f"Expected: status_value, status, category, or value")
            return 1

        print(f"  Species column: {name_col}")
        print(f"  Status column:  {value_col}")
        if tvk_col:
            print(f"  TVK column:     {tvk_col}")
        if detail_col:
            print(f"  Detail column:  {detail_col}")
        if profile_col:
            has_profile_col = True
            print(f"  Profile column: {profile_col}  (will populate species_profiles)")

        for row in reader:
            name = (row.get(name_col) or "").strip()
            value = (row.get(value_col) or "").strip()
            if not name or not value:
                continue
            tvk = (row.get(tvk_col) or "").strip() if tvk_col else ""
            notes = (row.get(notes_col) or "").strip() if notes_col else ""
            iucn = (row.get(iucn_col) or "").strip() if iucn_col else ""
            detail = (row.get(detail_col) or "").strip() if detail_col else ""
            profile = (row.get(profile_col) or "").strip() if profile_col else ""
            entries.append({
                "name": name,
                "value": value,
                "tvk": tvk,
                "notes": notes,
                "iucn_version": iucn,
                "detail": detail or args.detail or None,
                "profile": profile,
            })

    print(f"  Read {len(entries)} entries with statuses")
    if has_profile_col:
        with_profile = sum(1 for e in entries if e["profile"])
        print(f"  Of which {with_profile} have profile text")

    # ============================================================
    # Resolve species against UKSI
    # ============================================================
    print(f"\nResolving species against UKSI...")
    uksi = sqlite3.connect(UKSI_PATH)
    resolved = []
    unresolved = []

    for entry in entries:
        tvk, matched_name = resolve_species(uksi, entry["name"], entry["tvk"])
        if tvk:
            entry["resolved_tvk"] = tvk
            entry["resolved_name"] = matched_name
            resolved.append(entry)
        else:
            unresolved.append(entry)

    uksi.close()
    print(f"  Resolved:   {len(resolved)}")
    print(f"  Unresolved: {len(unresolved)}")

    if unresolved:
        print(f"\n  First 10 unresolved:")
        for e in unresolved[:10]:
            print(f"    {e['name']}")

    # ============================================================
    # Diff against existing status_summary
    # Primary key is (tvk, track, detail), so we match all three.
    # ============================================================
    c = codex.cursor()
    new_entries = []
    updated_entries = []
    unchanged = 0

    for entry in resolved:
        tvk = entry["resolved_tvk"]
        detail = entry["detail"] or ""
        c.execute("""SELECT status_value, origin FROM status_summary
                     WHERE tvk = ? AND status_track = ?
                       AND COALESCE(status_detail, '') = ?""",
                  (tvk, args.track, detail))
        existing = c.fetchone()
        if existing:
            if existing[0] == entry["value"]:
                unchanged += 1
            else:
                updated_entries.append(entry)
        else:
            new_entries.append(entry)

    # Existing profiles (for diff)
    profile_new = profile_updated = profile_unchanged = 0
    if has_profile_col:
        for entry in resolved:
            if not entry["profile"]:
                continue
            tvk = entry["resolved_tvk"]
            c.execute("SELECT profile_text FROM species_profiles WHERE tvk = ?", (tvk,))
            existing = c.fetchone()
            if existing:
                if existing[0] == entry["profile"]:
                    profile_unchanged += 1
                else:
                    profile_updated += 1
            else:
                profile_new += 1

    # ============================================================
    # Preview
    # ============================================================
    print(f"\n{'=' * 60}")
    print(f"IMPORT PREVIEW")
    print(f"{'=' * 60}")
    print(f"  Review:     {args.name}")
    print(f"  Author:     {args.author}")
    print(f"  Group:      {args.group}")
    print(f"  Track:      {args.track}")
    if args.detail:
        print(f"  Detail:     {args.detail}  (default for all entries)")
    print(f"  Published:  {pub_date}")
    if args.supersedes:
        print(f"  Supersedes: review #{args.supersedes}")
    print(f"")
    print(f"  Status entries:")
    print(f"    New:             {len(new_entries)}")
    print(f"    Updated:         {len(updated_entries)}")
    print(f"    Unchanged:       {unchanged}")
    print(f"    Unresolved:      {len(unresolved)}")
    print(f"    Total to write:  {len(new_entries) + len(updated_entries)}")
    if has_profile_col:
        print(f"")
        print(f"  Species profiles:")
        print(f"    New:             {profile_new}")
        print(f"    Updated:         {profile_updated}")
        print(f"    Unchanged:       {profile_unchanged}")

    if args.dry_run:
        print(f"\n  DRY RUN -- no changes made")
        codex.close()
        return 0

    if (len(new_entries) + len(updated_entries) == 0
            and not has_profile_col):
        print(f"\n  Nothing to import.")
        codex.close()
        return 0

    # ============================================================
    # Import
    # ============================================================
    print(f"\nImporting...")

    # Register the review
    c.execute("""INSERT INTO reviews
        (review_name, author, taxon_group, status_track, date_published,
         date_imported, source_file, species_count, supersedes_id, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (args.name, args.author, args.group, args.track, pub_date,
         now, str(csv_path.name), len(resolved), args.supersedes,
         f"Imported from {csv_path.name}"))
    review_id = c.lastrowid
    print(f"  Review registered: #{review_id}")

    source = f"{args.name} ({args.author})"

    # Insert manual_entries + update status_summary
    all_status_writes = new_entries + updated_entries
    for entry in all_status_writes:
        tvk = entry["resolved_tvk"]
        name = entry["resolved_name"]
        value = entry["value"]
        detail = entry["detail"]
        notes = entry.get("notes", "")
        iucn = entry.get("iucn_version", "")

        # manual_entries (the override register)
        c.execute("""INSERT INTO manual_entries
            (tvk, species_name, status_track, status_value, status_detail,
             source_review, date_added, added_by, notes, review_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (tvk, name, args.track, value, detail,
             source, now, "review-import", notes, review_id))

        # status_summary (what consumers query)
        # PK is (tvk, status_track, status_detail) so detail must be consistent
        c.execute("""INSERT OR REPLACE INTO status_summary
            (tvk, status_track, status_value, status_detail,
             source, iucn_version, date_designated, origin)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'manual')""",
            (tvk, args.track, value, detail, source, iucn, pub_date))

    # Profiles
    profile_writes = 0
    if has_profile_col:
        for entry in resolved:
            text = entry["profile"]
            if not text:
                continue
            tvk = entry["resolved_tvk"]
            # Check if exists -- distinguish add vs update for date tracking
            c.execute("SELECT 1 FROM species_profiles WHERE tvk = ?", (tvk,))
            if c.fetchone():
                c.execute("""UPDATE species_profiles
                             SET profile_text = ?, source = ?,
                                 date_updated = ?, added_by = 'review-import'
                             WHERE tvk = ?""",
                          (text, source, now, tvk))
            else:
                c.execute("""INSERT INTO species_profiles
                    (tvk, profile_text, source, date_added, date_updated, added_by)
                    VALUES (?, ?, ?, ?, NULL, 'review-import')""",
                    (tvk, text, source, now))
            profile_writes += 1

    codex.commit()

    # ============================================================
    # Summary
    # ============================================================
    print(f"  Imported {len(all_status_writes)} status entries")
    if profile_writes:
        print(f"  Imported {profile_writes} species profiles")
    print(f"  Run 'python scripts/seed_codex.py' to refresh derived SQS scores")

    c.execute("SELECT COUNT(DISTINCT tvk) FROM status_summary")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM reviews")
    review_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM species_profiles")
    profile_count = c.fetchone()[0]

    print(f"\n{'=' * 60}")
    print(f"CODEX AFTER IMPORT")
    print(f"{'=' * 60}")
    print(f"  Total species with status: {total:,}")
    print(f"  Total reviews registered:  {review_count}")
    print(f"  Total species profiles:    {profile_count:,}")
    print(f"  Review #{review_id}: {args.name}  "
          f"({len(all_status_writes)} statuses, {profile_writes} profiles)")

    codex.close()
    print(f"\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
