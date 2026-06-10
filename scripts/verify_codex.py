"""
Verify codex.db -- health, regression, and coverage checks (v2)

Three sections:
  1. Schema health    -- tables exist, schema correctness, sanity invariants
  2. Regression tests -- known reports' key species can be resolved by Codex
  3. Coverage stats   -- track distribution, category breakdown, profile coverage

Run after build_codex_db.py (and seed_codex.py) to confirm the database is
in a valid state. Each section is independent -- failures in one don't stop
the others.

v2 rewrite:
  - Fixed the conservation_status -> status_summary query bug
  - Updated to the 11-track scheme
  - Added schema health checks and coverage stats
  - Regression tests refactored to "any status counts as resolved" using
    status_summary across all tracks
"""

import sqlite3
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import paths

CODEX_PATH = str(paths.CODEX_DB)
UKSI_PATH = str(paths.UKSI_DB)


# ============================================================
# Tracks expected to exist in a healthy codex.db.
# (Some may be empty if no source data routes there yet -- that's fine.)
# ============================================================
EXPECTED_TRACKS = {
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
}

EXPECTED_TABLES = {
    "designations",
    "status_summary",
    "sqs_scores",
    "tvk_bridge",
    "manual_entries",
    "reviews",
    "species_profiles",
    "metadata",
    "build_log",
}


# ============================================================
# Real-world reports for regression testing
# ============================================================
REPORTS = {
    "Glory Park 2024 (8 key species)": [
        ("Alopecosa cuneata", "NS"),
        ("Platynaspis luteorubra", "Na"),
        ("Hylaeus cornutus", "Na"),
        ("Hippodamia variegata", "Nb"),
        ("Hypera meles", "Na"),
        ("Larinus carlinae", "Nb"),
        ("Graptopeltus lynceus", "Nb"),
        ("Merzomyia westermanni", "Notable"),
    ],
    "Bicester 2023 (27 key species)": [
        ("Lasioglossum pauxillum", "Na"),
        ("Lasioglossum malachurum", "Nb"),
        ("Lasioglossum puncticolle", "Nb"),
        ("Hylaeus signatus", "Nb"),
        ("Bombus rupestris", "Nb"),
        ("Philanthus triangulum", "RDB2"),
        ("Andrena similis", "Nb"),
        ("Pemphredon lethifer", "RDB3"),
        ("Epiphanis cornutus", "NT"),
        ("Larinus carlinae", "Nb"),
        ("Hippodamia variegata", "Nb"),
        ("Protapion difforme", "Nb"),
        ("Tanymecus palliatus", "Nb"),
        ("Zacladus exiguus", "Nb"),
        ("Agrilus angustulus", "NS"),
        ("Forficula lesnei", "NS"),
        ("Cistogaster globosa", "RDB1"),
        ("Atylotus rusticus", "NR"),
        ("Blaesoxipha plumicornis", "Notable"),
        ("Tephritis matricariae", "RDBK"),
        ("Tephritis divisa", "RDBK"),
        ("Coenonympha pamphilus", "S41"),
        ("Lasiommata megera", "S41"),
        ("Commophila aeneana", "Nb"),
        ("Sesia apiformis", "Nb"),
        ("Tyria jacobaeae", "S41"),
        ("Lygus pratensis", "RDB3"),
    ],
    "Badshot Lea 2023 (9 key species)": [
        ("Anisoxya fuscula", "NS"),
        ("Syntomus truncatellus", "NS"),
        ("Cassida prasina", "NS"),
        ("Polydrusus formosus", "Na"),
        ("Catapion pubescens", "Nb"),
        ("Andrena tibialis", "NS"),
        ("Nomada fucata", "Na"),
        ("Lasioglossum pauxillum", "Na"),
        ("Tyria jacobaeae", "S41"),
    ],
    "Long Hanborough 2025 (7 key species)": [
        ("Pardosa agrestis", "NS"),
        ("Brachinus crepitans", "NS"),
        ("Ophonus azureus", "NS"),
        ("Dolichopus virgultorum", "NS"),
        ("Lasioglossum pauxillum", "Na"),
        ("Hippodamia variegata", "Nb"),
        ("Lasioglossum malachurum", "Nb"),
    ],
}


# ============================================================
# Helpers
# ============================================================
def ok(msg):
    print(f"  PASS  {msg}")

def warn(msg):
    print(f"  WARN  {msg}")

def fail(msg):
    print(f"  FAIL  {msg}")

def header(text):
    print(f"\n{'=' * 70}")
    print(text)
    print('=' * 70)


# ============================================================
# Section 1: Schema health
# ============================================================
def check_schema(codex):
    header("SECTION 1 -- SCHEMA HEALTH")
    c = codex.cursor()
    failures = 0

    # Tables exist
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    actual_tables = {r[0] for r in c.fetchall()}
    missing_tables = EXPECTED_TABLES - actual_tables
    if missing_tables:
        fail(f"Missing tables: {sorted(missing_tables)}")
        failures += 1
    else:
        ok(f"All {len(EXPECTED_TABLES)} expected tables present")

    # designations.category column exists and is mostly populated
    c.execute("PRAGMA table_info(designations)")
    cols = {r[1] for r in c.fetchall()}
    if "category" not in cols:
        fail("designations.category column is missing -- old schema")
        failures += 1
    else:
        c.execute("SELECT COUNT(*) FROM designations WHERE category IS NULL OR category = ''")
        empty = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM designations")
        total = c.fetchone()[0]
        if empty == 0:
            ok(f"designations.category populated for all {total:,} rows")
        elif empty < total * 0.05:
            warn(f"designations.category empty for {empty:,}/{total:,} rows "
                 f"({empty / total * 100:.1f}%)")
        else:
            fail(f"designations.category mostly empty ({empty:,}/{total:,})")
            failures += 1

    # status_summary tracks are all in EXPECTED_TRACKS
    c.execute("SELECT DISTINCT status_track FROM status_summary")
    actual_tracks = {r[0] for r in c.fetchall()}
    unexpected = actual_tracks - EXPECTED_TRACKS
    missing_tracks = EXPECTED_TRACKS - actual_tracks
    if unexpected:
        fail(f"Unexpected tracks in status_summary: {sorted(unexpected)}")
        failures += 1
    else:
        ok(f"All {len(actual_tracks)} tracks in status_summary are valid")
    if missing_tracks:
        # Tracks not appearing at all is a soft warning -- may be no source data
        # routed there yet (e.g. red_list_wales might be empty)
        warn(f"Expected tracks with no entries: {sorted(missing_tracks)}")

    # SQS scores: source values are valid
    c.execute("SELECT DISTINCT source FROM sqs_scores")
    sqs_sources = {r[0] for r in c.fetchall()}
    valid_sqs_sources = {"pantheon", "derived", "manual"}
    bad = sqs_sources - valid_sqs_sources
    if bad:
        fail(f"Unexpected sqs_scores.source values: {sorted(bad)}")
        failures += 1
    else:
        ok(f"sqs_scores.source values all valid: {sorted(sqs_sources)}")

    # SQS values are in 1/2/4/8/16/32
    c.execute("""SELECT DISTINCT sqs FROM sqs_scores
                 WHERE sqs NOT IN (1, 2, 4, 8, 16, 32)""")
    bad_sqs = [r[0] for r in c.fetchall()]
    if bad_sqs:
        fail(f"Out-of-range SQS values: {bad_sqs}")
        failures += 1
    else:
        ok("All SQS values in valid set {1, 2, 4, 8, 16, 32}")

    # Invertebrate-only SQS invariant
    c.execute("""
        SELECT COUNT(DISTINCT s.tvk) FROM sqs_scores s
        WHERE NOT EXISTS (
            SELECT 1 FROM designations d
            WHERE d.tvk = s.tvk AND d.category = 'Invertebrate'
        )
    """)
    leak = c.fetchone()[0]
    if leak == 0:
        ok("SQS invariant holds: 0 non-invertebrate SQS scores")
    else:
        # Distinguish derived vs pantheon -- derived is a real bug,
        # pantheon could legitimately leak via TVK collisions (unlikely but possible)
        c.execute("""
            SELECT s.source, COUNT(*) FROM sqs_scores s
            WHERE NOT EXISTS (
                SELECT 1 FROM designations d
                WHERE d.tvk = s.tvk AND d.category = 'Invertebrate'
            )
            GROUP BY s.source
        """)
        breakdown = dict(c.fetchall())
        if breakdown.get("derived", 0) > 0:
            fail(f"{breakdown['derived']:,} non-invertebrate DERIVED SQS scores -- "
                 f"seed_codex.py invertebrate filter is broken")
            failures += 1
        if breakdown.get("pantheon", 0) > 0:
            warn(f"{breakdown['pantheon']:,} non-invertebrate Pantheon-source "
                 f"SQS scores. Pantheon's TVKs may collide with non-invert UKSI.")

    # status_summary primary key uses status_detail -- check no nulls
    # in non-detail-track rows that should have a clean PK
    c.execute("""SELECT COUNT(*) FROM status_summary
                 WHERE status_detail IS NULL""")
    null_detail = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM status_summary")
    total_summary = c.fetchone()[0]
    # NULL detail is normal for tracks that don't use it (rarity_modern, etc.)
    # Just report -- not a failure
    ok(f"status_summary: {total_summary:,} rows total, "
       f"{null_detail:,} with NULL status_detail")

    # build_log has at least one entry
    c.execute("SELECT COUNT(*) FROM build_log")
    bl = c.fetchone()[0]
    if bl == 0:
        warn("build_log empty -- no build has logged itself")
    else:
        ok(f"build_log: {bl} build(s) recorded")

    print()
    if failures == 0:
        print("  All schema health checks passed.")
    else:
        print(f"  {failures} schema check(s) failed.")
    return failures


# ============================================================
# Section 2: Regression tests against real reports
# ============================================================
def regression_tests(codex, uksi):
    header("SECTION 2 -- REGRESSION TESTS (real-world reports)")

    cc = codex.cursor()
    uc = uksi.cursor()

    # Build name -> TVK lookup
    uc.execute("SELECT scientific_name, tvk FROM taxa WHERE rank = 'Species'")
    name_to_tvk = {r[0].lower(): r[1] for r in uc.fetchall()}

    def get_tvk(name):
        clean = name.strip().rstrip("*")
        if clean.lower() in name_to_tvk:
            return name_to_tvk[clean.lower()]
        # Strip subgenus brackets
        no_subg = re.sub(r"\s*\([^)]+\)\s*", " ", clean).strip()
        if no_subg.lower() in name_to_tvk:
            return name_to_tvk[no_subg.lower()]
        return None

    def lookup(tvk):
        """Return (status_entries, sqs) for a TVK.
        status_entries is list of (track, value, detail).
        """
        cc.execute("""SELECT status_track, status_value, status_detail
                      FROM status_summary WHERE tvk = ?""", (tvk,))
        statuses = cc.fetchall()
        cc.execute("SELECT sqs FROM sqs_scores WHERE tvk = ?", (tvk,))
        sqs_row = cc.fetchone()
        return statuses, sqs_row[0] if sqs_row else None

    total_found = total_missing = total_tested = total_no_tvk = 0

    for report_name, key_species in REPORTS.items():
        print(f"\n{report_name}")
        print("-" * 70)

        found = missing = no_tvk = 0

        for species_name, expected in key_species:
            total_tested += 1
            tvk = get_tvk(species_name)
            if not tvk:
                print(f"  -- {species_name:35s}  no TVK in UKSI")
                no_tvk += 1
                total_no_tvk += 1
                continue

            statuses, sqs = lookup(tvk)
            sqs_str = f"SQS:{sqs}" if sqs else "no SQS"

            if statuses:
                found += 1
                total_found += 1
                # Show up to 2 status entries, summarised
                shown = []
                for track, value, detail in statuses[:2]:
                    if detail:
                        shown.append(f"{track}={value}/{detail}")
                    else:
                        shown.append(f"{track}={value}")
                more = f" (+{len(statuses) - 2})" if len(statuses) > 2 else ""
                print(f"  +  {species_name:35s}  {sqs_str:8s}  "
                      f"{'; '.join(shown)}{more}  [expected {expected}]")
            else:
                missing += 1
                total_missing += 1
                print(f"  -  {species_name:35s}  {sqs_str:8s}  "
                      f"MISSING -- expected {expected}")

        n = len(key_species)
        pct = round(found / n * 100) if n else 0
        print(f"\n  Result: {found}/{n} resolved ({pct}%)")
        if missing:
            print(f"          {missing} missing (need manual entries via review import)")
        if no_tvk:
            print(f"          {no_tvk} unresolvable in UKSI (taxonomy mismatch?)")

    print(f"\n{'=' * 70}")
    overall_pct = round(total_found / total_tested * 100) if total_tested else 0
    print(f"OVERALL: {total_found}/{total_tested} resolved ({overall_pct}%)")
    print(f"  Missing in Codex:    {total_missing}")
    print(f"  Unresolvable TVK:    {total_no_tvk}")

    return total_missing


# ============================================================
# Section 3: Coverage stats
# ============================================================
def coverage_stats(codex):
    header("SECTION 3 -- COVERAGE STATS")

    c = codex.cursor()

    # Total species across all categories
    c.execute("SELECT COUNT(DISTINCT tvk) FROM designations")
    total_species = c.fetchone()[0]
    print(f"\nTotal species in Codex: {total_species:,}")

    # Category breakdown
    c.execute("""SELECT category, COUNT(DISTINCT tvk) FROM designations
                 GROUP BY category ORDER BY COUNT(DISTINCT tvk) DESC""")
    print(f"\nBy category:")
    for cat, n in c.fetchall():
        print(f"  {(cat or '(uncategorised)'):30s}  {n:>5,}")

    # Track distribution
    c.execute("""SELECT status_track, COUNT(*) FROM status_summary
                 GROUP BY status_track ORDER BY COUNT(*) DESC""")
    print(f"\nBy status track:")
    for track, n in c.fetchall():
        print(f"  {track:25s}  {n:>5,}")

    # SQS coverage (invert-only meaningful)
    c.execute("""SELECT COUNT(DISTINCT s.tvk) FROM sqs_scores s
                 WHERE EXISTS (
                     SELECT 1 FROM designations d
                     WHERE d.tvk = s.tvk AND d.category = 'Invertebrate'
                 )""")
    sqs_invert = c.fetchone()[0]
    c.execute("""SELECT COUNT(DISTINCT tvk) FROM designations
                 WHERE category = 'Invertebrate'""")
    total_invert = c.fetchone()[0]
    invert_pct = round(sqs_invert / total_invert * 100) if total_invert else 0
    print(f"\nSQS coverage (invertebrates):")
    print(f"  Invertebrate species in Codex:    {total_invert:,}")
    print(f"  With SQS score:                   {sqs_invert:,} ({invert_pct}%)")

    c.execute("SELECT source, COUNT(*) FROM sqs_scores GROUP BY source ORDER BY COUNT(*) DESC")
    for source, n in c.fetchall():
        print(f"    source={source:10s}                {n:>5,}")

    # Profile coverage
    c.execute("SELECT COUNT(*) FROM species_profiles")
    profile_count = c.fetchone()[0]
    profile_pct = round(profile_count / total_species * 100, 1) if total_species else 0
    print(f"\nSpecies profiles:")
    print(f"  Total profiles:                   {profile_count:,} ({profile_pct}%)")
    if profile_count:
        c.execute("""SELECT added_by, COUNT(*) FROM species_profiles
                     GROUP BY added_by""")
        for source, n in c.fetchall():
            print(f"    added_by={source or '(unknown)':18s}        {n:>5,}")

    # Reviews
    c.execute("SELECT COUNT(*) FROM reviews")
    review_count = c.fetchone()[0]
    print(f"\nImported reviews: {review_count}")
    if review_count:
        c.execute("""SELECT id, review_name, author, taxon_group,
                            status_track, species_count, date_imported
                     FROM reviews ORDER BY id""")
        for rid, name, author, group, track, sp, imported in c.fetchall():
            print(f"  #{rid}: {name[:45]:45s}  "
                  f"{group or '?':15s}  -> {track:20s}  ({sp} species)")


# ============================================================
# Main
# ============================================================
def main():
    if not os.path.exists(CODEX_PATH):
        print(f"codex.db not found at {CODEX_PATH}")
        print("Run build_codex_db.py first.")
        return 1
    if not os.path.exists(UKSI_PATH):
        print(f"uksi.db not found at {UKSI_PATH}")
        print("Regression tests will be skipped.")

    codex = sqlite3.connect(CODEX_PATH)

    # Section 1
    schema_failures = check_schema(codex)

    # Section 2
    if os.path.exists(UKSI_PATH):
        uksi = sqlite3.connect(UKSI_PATH)
        regression_missing = regression_tests(codex, uksi)
        uksi.close()
    else:
        regression_missing = 0

    # Section 3
    coverage_stats(codex)

    # Final
    header("VERIFICATION SUMMARY")
    if schema_failures == 0 and regression_missing == 0:
        print("  All checks passed.")
        rc = 0
    else:
        if schema_failures:
            print(f"  Schema health:   {schema_failures} failure(s)")
        if regression_missing:
            print(f"  Regression tests: {regression_missing} missing species")
        rc = 1

    codex.close()
    return rc


if __name__ == "__main__":
    sys.exit(main())
