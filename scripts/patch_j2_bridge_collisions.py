"""patch_j2_bridge_collisions.py -- bridge the merged taxa, keep the best SQS.

    python scripts/patch_j2_bridge_collisions.py

Then rebuild:  python scripts/build_codex_db.py
               python scripts/seed_codex.py

Background
----------
1,847 Pantheon taxa were deliberately left out of tvk_bridge. UKSI has merged
each into a species another Pantheon taxon already claimed, and since
sqs_scores is keyed on tvk alone, bridging both would let one silently
overwrite the other. That was backlog J2.

It was then asserted that PantheonRepository becoming bridge-aware made J2 moot,
because the read layer unions ecology and keeps the highest SQS. **Measured, and
the assertion was wrong**: `_to_pantheon` can only return TVKs that are IN the
bridge, and these never were.

But the measurement also shrank the job. Of the 1,617 colliders holding ecology:

    1,528  the incumbent already has the same ecology -- nothing lost
       89  hold habitats or biotopes NOTHING can currently reach
       85  hold an SQS higher than the incumbent's

Most are spelling corrections recording the same animal twice (Bembidion
caeruleum / coeruleum, Aulonium trisulcum / trisulcus). The ones that matter are
real synonymisations -- Baryphyma duffeyi -> Praestigia duffeyi adds coastal and
saltmarsh; Arctophila superbiens -> Sericomyia superbiens adds running water.

200 of the merged species appear in Wil's commercial records.

What this changes
-----------------
1. The third pass now bridges collisions instead of skipping them. The read
   layer already implements the agreed merge rule -- union the ecology, keep
   the highest SQS -- so nothing else is needed for ecology.

2. The SQS import keeps the HIGHEST score per current species instead of
   whichever row was written last. Without this, bridging the collisions would
   reintroduce exactly the arbitrary overwrite they were excluded to prevent,
   and with it Infrastructure item 59's instability between rebuilds.

Safe to re-run. Backs up as build_codex_db.py.bak_fix4.
"""
import os
import shutil
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(_ROOT, "scripts", "build_codex_db.py")
BACKUP = TARGET + ".bak_fix4"

OLD_THIRD = '''        # Third pass -- synonym resolution for what the first two missed.
        # Accept ONLY where no other Pantheon species has already claimed
        # the target TVK. A collision means UKSI has merged two Pantheon
        # taxa into one species, each with its own SQS and ecology; since
        # sqs_scores is keyed on tvk alone, inserting one would silently
        # overwrite the other. Those need a merge rule -- backlog J2.
        syn_match = 0
        syn_collision = 0
        claimed = {r[1] for r in bridge_rows}
        resolved_pan = {r[0] for r in bridge_rows}
        for pan_tvk, pan_name in pan_species:
            if pan_tvk in resolved_pan or not pan_name:
                continue
            new_tvk = uksi_syn_tvk.get(pan_name.lower())
            if not new_tvk:
                continue
            if new_tvk in claimed:
                syn_collision += 1
                continue
            bridge_rows.append((pan_tvk, new_tvk, pan_name, "name"))
            claimed.add(new_tvk)
            syn_match += 1
            unmatched -= 1'''

NEW_THIRD = '''        # Third pass -- synonym resolution for what the first two missed.
        #
        # Collisions ARE bridged (J2, Session 32). Where UKSI has merged two
        # Pantheon taxa into one current species, both are mapped to it and the
        # merge happens at read time: PantheonRepository unions the ecology and
        # keeps the highest SQS. Excluding them lost habitat data for 89 species
        # that nothing else could reach, and a higher SQS for 85.
        #
        # The SQS import below must keep the highest score per species, not the
        # last one written, or this reintroduces the arbitrary overwrite the
        # exclusion was there to prevent.
        syn_match = 0
        syn_collision = 0
        claimed = {r[1] for r in bridge_rows}
        resolved_pan = {r[0] for r in bridge_rows}
        for pan_tvk, pan_name in pan_species:
            if pan_tvk in resolved_pan or not pan_name:
                continue
            new_tvk = uksi_syn_tvk.get(pan_name.lower())
            if not new_tvk:
                continue
            if new_tvk in claimed:
                syn_collision += 1      # counted, and now also bridged
            bridge_rows.append((pan_tvk, new_tvk, pan_name, "name"))
            claimed.add(new_tvk)
            syn_match += 1
            unmatched -= 1'''

OLD_REPORT = '''        if syn_collision:
            print(f"  Synonym collisions (not bridged): {syn_collision:,}"
                  f"  -- two Pantheon taxa merged into one species; see J2")'''

NEW_REPORT = '''        if syn_collision:
            print(f"  of which merged taxa:             {syn_collision:,}"
                  f"  -- two Pantheon taxa in one current species;"
                  f" ecology unioned, highest SQS kept")'''

OLD_SQS = '''        for pan_tvk, sqs in pc.fetchall():
            uksi_tvk = bridge.get(pan_tvk, pan_tvk)
            if uksi_tvk != pan_tvk:
                sqs_rekeyed += 1
            # Filter: only invertebrates per Codex's category column
            if uksi_tvk not in invert_tvks:
                sqs_dropped_noninvert += 1
                continue
            sqs_rows.append((uksi_tvk, sqs, "pantheon"))'''

NEW_SQS = '''        # Several Pantheon taxa can now map to one current species (J2), so
        # keep the HIGHEST score rather than whichever row is written last.
        # sqs_scores is keyed on tvk alone; INSERT OR REPLACE would otherwise
        # let row order decide the value, which is not reproducible between
        # rebuilds (Infrastructure 59).
        best_sqs = {}
        sqs_merged = 0
        for pan_tvk, sqs in pc.fetchall():
            uksi_tvk = bridge.get(pan_tvk, pan_tvk)
            if uksi_tvk != pan_tvk:
                sqs_rekeyed += 1
            # Filter: only invertebrates per Codex's category column
            if uksi_tvk not in invert_tvks:
                sqs_dropped_noninvert += 1
                continue
            if uksi_tvk in best_sqs:
                sqs_merged += 1
                if sqs > best_sqs[uksi_tvk]:
                    best_sqs[uksi_tvk] = sqs
            else:
                best_sqs[uksi_tvk] = sqs
        sqs_rows = [(t, s, "pantheon") for t, s in best_sqs.items()]'''

OLD_SQS_MSG = '''        print(f"  {sqs_count:,} SQS scores ({sqs_rekeyed:,} re-keyed via bridge)")'''
NEW_SQS_MSG = '''        print(f"  {sqs_count:,} SQS scores ({sqs_rekeyed:,} re-keyed via bridge)")
        if sqs_merged:
            print(f"  {sqs_merged:,} merged onto an existing species "
                  f"(highest score kept)")'''

EDITS = [
    ("third pass bridges collisions", OLD_THIRD, NEW_THIRD),
    ("bridge reporting", OLD_REPORT, NEW_REPORT),
    ("SQS import keeps the highest", OLD_SQS, NEW_SQS),
    ("SQS reporting", OLD_SQS_MSG, NEW_SQS_MSG),
]


def main():
    if not os.path.exists(TARGET):
        print(f"NOT FOUND: {TARGET}")
        return 1
    with open(TARGET, "r", encoding="utf-8") as f:
        text = f.read()

    print("")
    print("Patching build_codex_db.py -- J2, bridge the merged taxa")
    print("=" * 70)

    if "best_sqs" in text:
        print("  = already patched -- nothing to do")
        return 0

    failed = 0
    for label, old, new in EDITS:
        n = text.count(old)
        if n == 1:
            text = text.replace(old, new)
            print(f"  + {label}")
        else:
            print(f"  x {label}  ({n} matches, expected 1)")
            failed += 1

    print("")
    if failed:
        print(f"  {failed} edit(s) failed -- NOTHING WRITTEN.")
        return 1

    shutil.copy2(TARGET, BACKUP)
    print(f"  backup written: {os.path.basename(BACKUP)}")
    with open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(text)

    print("")
    try:
        import py_compile
        py_compile.compile(TARGET, doraise=True)
        print("  + compiles cleanly")
    except Exception as e:  # noqa: BLE001
        print(f"  x COMPILE FAILED: {e}")
        print(f"    restore: copy {os.path.basename(BACKUP)} build_codex_db.py")
        return 1

    print("")
    print("  BACK UP codex.db, then:")
    print("        python scripts/build_codex_db.py")
    print("        python scripts/seed_codex.py")
    print("        python scripts/check_j2_still_needed.py")
    print("")
    print("  Expect: bridge total 12,314 -> ~14,161; 'unmatched' drops to ~68;")
    print("  SQS around 5,522 with ~1,600 reported as merged; and the J2 check")
    print("  should find 0 colliding taxa left outside the bridge.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
