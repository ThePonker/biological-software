"""patch_j2_incumbent_wins.py -- correct the merge rule: incumbent, not highest.

    python scripts/patch_j2_incumbent_wins.py

Then rebuild:  python scripts/build_codex_db.py
               python scripts/seed_codex.py

What went wrong
---------------
patch_j2_bridge_collisions.py merged colliding taxa by keeping the HIGHEST SQS.
That was not the rule we agreed, and it is the wrong one.

Session 32 examined the 18 merges where the two Pantheon records disagree on
SQS. The pattern was consistent: the SUNK taxon usually carries the higher
score, because it was a scarce segregate, and the incumbent's score is the one
that describes the merged species. The agreed rule was **incumbent wins**.

Highest-wins produced exactly the distortion that reasoning predicted:

    Sympetrum striolatum   1 -> 4    Common Darter, one of the commonest
                                     dragonflies in Britain, inherited the
                                     score of S. nigrescens, the Highland
                                     Darter form sunk into it.

That inflates SQI on any site holding a common species, which is the opposite
of what a quality index is for.

Hylaeus annularis at 8 is the case where highest-wins happens to agree with the
published rule (it carries RDB 3, which scores 8). But that is an argument for
deriving from status, not for taking a maximum across merged taxa -- and under
incumbent-wins it returns to 1, where its disagreement with the rule stays
visible as Infrastructure 54 rather than being silently patched by an unrelated
mechanism.

The rule
--------
    Incumbent wins. The incumbent is the Pantheon taxon bridged by the direct
    or name pass -- the one whose TVK matches, or whose name matches, the
    current species. A collider's score is used only where the incumbent has
    none.

Ecology is still unioned across all merged taxa; that was never in question,
and it is where J2's real value lies (89 species gaining habitats nothing else
could reach).

Safe to re-run. Backs up as build_codex_db.py.bak_fix5.
"""
import os
import shutil
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(_ROOT, "scripts", "build_codex_db.py")
BACKUP = TARGET + ".bak_fix5"

# The third pass must mark colliders so the SQS import can tell them from
# incumbents. match_method stays within its CHECK constraint ('direct'/'name');
# the distinction is carried in a Python set instead.
OLD_THIRD_TAIL = '''            if new_tvk in claimed:
                syn_collision += 1      # counted, and now also bridged
            bridge_rows.append((pan_tvk, new_tvk, pan_name, "name"))
            claimed.add(new_tvk)
            syn_match += 1
            unmatched -= 1'''

NEW_THIRD_TAIL = '''            if new_tvk in claimed:
                syn_collision += 1      # counted, and now also bridged
                collider_pan_tvks.add(pan_tvk)
            bridge_rows.append((pan_tvk, new_tvk, pan_name, "name"))
            claimed.add(new_tvk)
            syn_match += 1
            unmatched -= 1'''

OLD_THIRD_HEAD = '''        syn_match = 0
        syn_collision = 0
        claimed = {r[1] for r in bridge_rows}'''

NEW_THIRD_HEAD = '''        syn_match = 0
        syn_collision = 0
        # Pantheon taxa that landed on a species another taxon already claimed.
        # Their SQS must not displace the incumbent's -- see the merge rule in
        # patch_j2_incumbent_wins.py.
        collider_pan_tvks = set()
        claimed = {r[1] for r in bridge_rows}'''

# Persist the collider set for the SQS import stage.
OLD_WRITE = '''        c.executemany("INSERT OR REPLACE INTO tvk_bridge VALUES (?,?,?,?)", bridge_rows)
        bridge_count = len(bridge_rows)'''

NEW_WRITE = '''        c.executemany("INSERT OR REPLACE INTO tvk_bridge VALUES (?,?,?,?)", bridge_rows)
        bridge_count = len(bridge_rows)
        # Carried to the SQS import below.
        globals()["_COLLIDER_PAN_TVKS"] = collider_pan_tvks'''

OLD_SQS = '''        # Several Pantheon taxa can now map to one current species (J2), so
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

NEW_SQS = '''        # Several Pantheon taxa can map to one current species (J2). The
        # INCUMBENT wins -- the taxon bridged by the direct or name pass, whose
        # TVK or name matches the current species. A collider's score is used
        # only where the incumbent has none.
        #
        # NOT the highest score: the sunk taxon usually carries the higher one
        # because it was a scarce segregate, so taking the maximum inflates the
        # merged species. Sympetrum striolatum (Common Darter, one of the
        # commonest British dragonflies) went 1 -> 4 by inheriting the score of
        # S. nigrescens, the Highland Darter form sunk into it.
        colliders = globals().get("_COLLIDER_PAN_TVKS", set())
        best_sqs = {}
        sqs_merged = 0
        rows_raw = pc.fetchall()
        # Incumbents first, then colliders, so setdefault gives the incumbent.
        for is_collider in (False, True):
            for pan_tvk, sqs in rows_raw:
                if (pan_tvk in colliders) != is_collider:
                    continue
                uksi_tvk = bridge.get(pan_tvk, pan_tvk)
                if not is_collider and uksi_tvk != pan_tvk:
                    sqs_rekeyed += 1
                if uksi_tvk not in invert_tvks:
                    if not is_collider:
                        sqs_dropped_noninvert += 1
                    continue
                if uksi_tvk in best_sqs:
                    sqs_merged += 1
                else:
                    best_sqs[uksi_tvk] = sqs
        sqs_rows = [(t, s, "pantheon") for t, s in best_sqs.items()]'''

OLD_MSG = '''        if sqs_merged:
            print(f"  {sqs_merged:,} merged onto an existing species "
                  f"(highest score kept)")'''
NEW_MSG = '''        if sqs_merged:
            print(f"  {sqs_merged:,} merged onto an existing species "
                  f"(incumbent's score kept)")'''

EDITS = [
    ("collider set declared", OLD_THIRD_HEAD, NEW_THIRD_HEAD),
    ("colliders recorded", OLD_THIRD_TAIL, NEW_THIRD_TAIL),
    ("collider set carried forward", OLD_WRITE, NEW_WRITE),
    ("SQS merge rule -> incumbent wins", OLD_SQS, NEW_SQS),
    ("reporting", OLD_MSG, NEW_MSG),
]


def main():
    if not os.path.exists(TARGET):
        print(f"NOT FOUND: {TARGET}")
        return 1
    with open(TARGET, "r", encoding="utf-8") as f:
        text = f.read()

    print("")
    print("Patching build_codex_db.py -- merge rule: incumbent wins")
    print("=" * 70)

    if "_COLLIDER_PAN_TVKS" in text:
        print("  = already patched -- nothing to do")
        return 0
    if "best_sqs" not in text:
        print("  x patch_j2_bridge_collisions.py has not been applied.")
        print("    Run that first -- this corrects its merge rule.")
        return 1

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
    print("  THEN:")
    print("        python scripts/build_codex_db.py")
    print("        python scripts/seed_codex.py")
    print("")
    print("  Verify with:")
    print("    Sympetrum striolatum  should be 1  (was 4 under highest-wins)")
    print("    Hylaeus annularis     should be 1  (its RDB 3 disagreement is")
    print("                                        Infrastructure 54, not this)")
    print("    Osmia bicornis        should stay 1")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
