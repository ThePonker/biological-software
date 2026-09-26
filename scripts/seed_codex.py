"""
Seed Codex -- SQS gap-fill for invertebrate species (v2)

Derives SQS (Species Quality Score) values for invertebrate species that
have a conservation status in Codex but no SQS score from Pantheon. This
gap-fill is essential because Pantheon's SQS data was keyed to 2017
taxonomy and has holes in it.

INVERTEBRATE-ONLY: This derivation is strictly scoped to invertebrates.
SQS is an invertebrate assemblage analysis construct (Pantheon / ISIS).
Applying the same 1/2/4/8/16 scale to a lichen or a plant produces
a number that is mathematically valid but ecologically meaningless.
Codex's design principle (Codex Strategy doc, section 2):

    Conservation statuses apply to all taxa.
    SQS scores apply only to invertebrates.

This script enforces that principle via the `category = 'Invertebrate'`
filter when deriving scores.

v2 changes:
  - Uses new 11-track scheme from build_codex_db.py v5:
        threat_iucn_2001, threat_iucn_legacy, rarity_modern, rarity_legacy
  - Invertebrate-only filter using designations.category column
  - Manual entries block removed (clean baseline -- add later via review imports)

SQS scoring rules (derived from Pantheon documentation):
  rarity_modern NR                -> 8
  rarity_modern NS                -> 4
  rarity_legacy Na                -> 4
  rarity_legacy Nb / Notable      -> 1
  threat_iucn_2001 CR / EN / VU   -> 8
  threat_iucn_2001 NT             -> 2
  threat_iucn_2001 DD             -> 2
  threat_iucn_legacy RDB1 / RDB2  -> 8
  threat_iucn_legacy RDB3         -> 16  (per Fowles original SQI)
  threat_iucn_legacy RDBK         -> 8

If a species qualifies under multiple tracks, we take the HIGHEST derived
SQS (not a sum) -- same approach as Pantheon's own scoring.

Usage: python scripts/seed_codex.py
"""

import sqlite3
import os
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
import paths

CODEX_PATH = str(paths.CODEX_DB)


# ============================================================
# SQS derivation rules
# ============================================================
# Keyed by (status_track, status_value) -> derived SQS score.
# Only invertebrate species get these -- enforced by category filter below.
# ============================================================
SQS_DEFAULTS = {
    # rarity_modern
    ("rarity_modern", "NR"):               8,
    ("rarity_modern", "NS"):               4,

    # rarity_legacy
    ("rarity_legacy", "Na"):               4,
    ("rarity_legacy", "Nb"):               1,
    ("rarity_legacy", "Notable"):          1,

    # threat_iucn_2001 (threatened categories get SQS)
    ("threat_iucn_2001", "CR"):            8,
    ("threat_iucn_2001", "EN"):            8,
    ("threat_iucn_2001", "VU"):            8,
    ("threat_iucn_2001", "NT"):            2,
    ("threat_iucn_2001", "DD"):            2,
    # LC, NE, NA, RE, EX, WL -- no SQS

    # threat_iucn_legacy
    ("threat_iucn_legacy", "RDB1"):        8,
    ("threat_iucn_legacy", "RDB2"):        8,
    ("threat_iucn_legacy", "RDB3"):        16,
    ("threat_iucn_legacy", "RDBK"):        8,
    # EN/VU/NT under 1994 IUCN -- conservative, treat like modern
    ("threat_iucn_legacy", "EN"):          8,
    ("threat_iucn_legacy", "VU"):          8,
    ("threat_iucn_legacy", "NT"):          2,
    # EX / DD / CR (1994) -- no SQS

    # specialist_panel (Spider Amber List)
    ("specialist_panel", "Amber"):         2,
}


def main():
    if not os.path.exists(CODEX_PATH):
        print(f"codex.db not found at {CODEX_PATH}")
        print("Run build_codex_db.py first")
        return

    conn = sqlite3.connect(CODEX_PATH)
    c = conn.cursor()

    print("=" * 60)
    print("CODEX SEED -- SQS GAP-FILL (INVERTEBRATE-ONLY)")
    print("=" * 60)

    # --------------------------------------------------------
    # Pre-state: what's in codex currently?
    # --------------------------------------------------------
    pre_sqs = c.execute("SELECT COUNT(*) FROM sqs_scores").fetchone()[0]
    pre_sqs_pan = c.execute(
        "SELECT COUNT(*) FROM sqs_scores WHERE source = 'pantheon'"
    ).fetchone()[0]
    pre_sqs_der = c.execute(
        "SELECT COUNT(*) FROM sqs_scores WHERE source = 'derived'"
    ).fetchone()[0]
    pre_sqs_man = c.execute(
        "SELECT COUNT(*) FROM sqs_scores WHERE source = 'manual'"
    ).fetchone()[0]

    print(f"\nPre-seed state:")
    print(f"  Total SQS scores:   {pre_sqs:,}")
    print(f"    pantheon source:  {pre_sqs_pan:,}")
    print(f"    derived source:   {pre_sqs_der:,}")
    print(f"    manual source:    {pre_sqs_man:,}")

    # --------------------------------------------------------
    # Clean out any prior derived SQS
    # These would be stale if track names changed, and the source-of-truth
    # derivation happens in this script.
    # --------------------------------------------------------
    if pre_sqs_der > 0:
        c.execute("DELETE FROM sqs_scores WHERE source = 'derived'")
        print(f"\nCleared {pre_sqs_der:,} prior derived SQS entries "
              f"(will re-derive below)")

    # --------------------------------------------------------
    # SQS gap-fill -- INVERTEBRATE-ONLY
    # --------------------------------------------------------
    print(f"\nDeriving SQS for invertebrate species with status but no SQS...")

    # Find invertebrate species that have a status but no SQS score.
    # We join status_summary against designations (to filter by category)
    # and left-join sqs_scores (to find the gap).
    #
    # Note: a species is invertebrate if ANY of its designations has
    # category='Invertebrate'. Using EXISTS handles this cleanly.
    c.execute("""
        SELECT DISTINCT s.tvk, s.status_track, s.status_value
        FROM status_summary s
        LEFT JOIN sqs_scores q ON s.tvk = q.tvk
        WHERE q.tvk IS NULL
          AND EXISTS (
              SELECT 1 FROM designations d
              WHERE d.tvk = s.tvk
                AND d.category = 'Invertebrate'
          )
        ORDER BY s.tvk
    """)
    gap_rows = c.fetchall()

    # Group by species: each species may have multiple qualifying statuses;
    # we take the max derived SQS across all tracks.
    by_species = {}
    for tvk, track, value in gap_rows:
        sqs = SQS_DEFAULTS.get((track, value))
        if sqs is None:
            continue
        if tvk not in by_species or sqs > by_species[tvk][1]:
            by_species[tvk] = (tvk, sqs, (track, value))

    # DERIVED SCORES ARE NO LONGER STORED (Session 32).
    #
    # SQS_DEFAULTS below is not Pantheon's published rule -- it scores RDB3 at
    # 16 "per Fowles original SQI", a different index, and takes the maximum of
    # single (track, value) pairs where the rule is a function of rarity AND
    # threat together. 525 of the 816 scores it produced disagreed with the
    # published rule.
    #
    # CodexRepository.get_sqs_scores now derives on demand via
    # shared/sqs_derivation.py, so sqs_scores holds only what Pantheon
    # published (plus manual entries). The candidate count below is reported
    # for information; nothing is written.
    filled = 0
    track_counts = {}
    if False:  # retained for reference; see patch_sqs_derive_live.py
        for tvk, (tvk_, sqs, winning) in by_species.items():
            c.execute("""INSERT OR IGNORE INTO sqs_scores (tvk, sqs, source)
                         VALUES (?, ?, 'derived')""", (tvk, sqs))
            if c.rowcount > 0:
                filled += 1
                track_counts[winning[0]] = track_counts.get(winning[0], 0) + 1

    print(f"  Candidate invertebrate species: {len(by_species):,}")
    print(f"  SQS scores STORED:              {filled:,}  "
          f"(derivation is now live -- see shared/sqs_derivation.py)")
    if track_counts:
        print(f"\n  Breakdown by winning track:")
        for track, cnt in sorted(track_counts.items(), key=lambda x: -x[1]):
            print(f"    {track:25s}  {cnt:>5,}")

    # --------------------------------------------------------
    # Sanity check: no non-invertebrate derived SQS should exist
    # --------------------------------------------------------
    c.execute("""
        SELECT COUNT(DISTINCT s.tvk) FROM sqs_scores s
        WHERE s.source = 'derived'
          AND NOT EXISTS (
              SELECT 1 FROM designations d
              WHERE d.tvk = s.tvk AND d.category = 'Invertebrate'
          )
    """)
    leakage = c.fetchone()[0]
    if leakage > 0:
        print(f"\n  WARNING: {leakage} derived SQS entries on non-invertebrate "
              f"species detected. This should not happen.")
    else:
        print(f"\n  Invertebrate filter verified: 0 non-invertebrate derived SQS.")

    # --------------------------------------------------------
    # Final summary
    # --------------------------------------------------------
    c.execute("SELECT COUNT(DISTINCT tvk) FROM status_summary")
    total_species = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM sqs_scores")
    total_sqs = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM manual_entries")
    total_manual = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM species_profiles")
    total_profiles = c.fetchone()[0]

    print(f"\n{'=' * 60}")
    print(f"CODEX AFTER SEEDING")
    print(f"{'=' * 60}")
    print(f"  Species with status:    {total_species:,}")
    print(f"  Species with SQS:       {total_sqs:,}")
    print(f"  Manual entries:         {total_manual:,}")
    print(f"  Species profiles:       {total_profiles:,}")

    print(f"\n  SQS by source:")
    for source, cnt in c.execute(
        "SELECT source, COUNT(*) FROM sqs_scores GROUP BY source ORDER BY source"
    ):
        print(f"    {source:15s}  {cnt:>6,}")

    # --------------------------------------------------------
    # Verification spot-checks
    # --------------------------------------------------------
    print(f"\n{'=' * 60}")
    print(f"VERIFICATION")
    print(f"{'=' * 60}")

    test_species = {
        "NHMSYS0000876200": "Lasioglossum pauxillum",
        "NHMSYS0000876203": "Lasioglossum puncticolle",
        "NHMSYS0000876116": "Hylaeus signatus",
        "NHMSYS0000875273": "Andrena similis",
        "NBNSYS0000149897": "Larinus carlinae",
        "NHMSYS0000519083": "Coenonympha pamphilus",
        "NHMSYS0000503020": "Lasiommata megera",
        "NHMSYS0001387336": "Forficula lesnei",
        "NHMSYS0020309273": "Graptopeltus lynceus",
        "NHMSYS0000876577": "Philanthus triangulum",
        "NHMSYS0000876422": "Nomada fucata",
        # Non-invert test (should NOT have SQS)
        "NHMSYS0000530120": "Accipiter nisus (bird -- should have no SQS)",
    }

    found = 0
    for tvk, name in test_species.items():
        c.execute("""SELECT status_track, status_value, status_detail, origin
                     FROM status_summary WHERE tvk = ?""", (tvk,))
        rows = c.fetchall()
        c.execute("SELECT sqs, source FROM sqs_scores WHERE tvk = ?", (tvk,))
        sqs_row = c.fetchone()
        sqs_s = f"SQS:{sqs_row[0]}({sqs_row[1][:3]})" if sqs_row else "no SQS"

        if rows:
            found += 1
            flags = []
            for t, v, d, o in rows:
                if d:
                    flags.append(f"{t}={v}/{d}")
                else:
                    flags.append(f"{t}={v}")
            # Show up to 3 tracks on one line
            summary = "; ".join(flags[:3])
            if len(flags) > 3:
                summary += f" (+{len(flags) - 3} more)"
            print(f"  + {name:50s}  {sqs_s:15s}  {summary}")
        else:
            print(f"  - {name:50s}  {sqs_s:15s}  MISSING")

    print(f"\n  Resolved: {found}/{len(test_species)}")

    conn.commit()
    conn.close()
    print(f"\nDone.")


if __name__ == "__main__":
    main()
