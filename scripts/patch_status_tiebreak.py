"""patch_status_tiebreak.py -- break precedence ties by date in build_codex_db.py

    python scripts/patch_status_tiebreak.py

What it fixes
-------------
When two designations compete for one status_summary slot, the winner is chosen
by ABBR_PRIORITY. But all modern Red List codes score 100, so ties are common,
and a tie was resolved by whichever row the database returned first -- not by
any rule. date_designated was carried in the tuple but never consulted.

Effect on the current data (from check_contested_status.py):

    34 slots where competitors disagree on the value
    22 already resolve to the most recent
    12 would change -- 11 of them correctly

The 11 are all vascular plants where a 2014 England list says EX/EW and the
2021 GB list says RE (Regionally Extinct). The newer list is right.

The 12th is Cercyon nigriceps: stored Nb (Hyman 1992), with a 1994 review
saying the generic "Notable". Date order alone would replace the specific value
with the vaguer one. That case is already handled deliberately -- ABBR_PRIORITY
scores Notable-B at 40 and Notable at 30 -- so the fix must keep precedence
FIRST and use date only to break a tie:

    higher ABBR_PRIORITY wins
      -> if tied, later date_designated wins
        -> if still tied, first seen (unchanged)

This fixes the 11 plants and leaves Cercyon alone.

Dates are ISO (YYYY-MM-DD) in this data, so a string comparison orders them
correctly. Missing dates sort as "" and therefore lose a tie, which is the
right default -- an undated designation should not displace a dated one.

Safe to re-run. Backs up as build_codex_db.py.bak_fix2 before writing.
"""
import os
import shutil
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(_ROOT, "scripts", "build_codex_db.py")
BACKUP = TARGET + ".bak_fix2"

OLD_COMMENT = \
    "        # best[(track, detail)] = (value, abbr, source, iucn_ver, date_d, origin, priority)"
NEW_COMMENT = (
    "        # best[(track, detail)] = (value, abbr, source, iucn_ver, date_d, origin, priority)\n"
    "        # Winner = highest priority, then latest date_designated. Precedence must\n"
    "        # come first: Notable-B (40) must still beat the generic Notable (30) even\n"
    "        # though the generic review is newer. See patch_status_tiebreak.py."
)

OLD_TEST = "            if key not in best or prio > best[key][6]:"
NEW_TEST = (
    "            if (key not in best\n"
    "                    or (prio, date_d or \"\") > (best[key][6], best[key][4] or \"\")):"
)

EDITS = [
    ("comment above the collapse", OLD_COMMENT, NEW_COMMENT),
    ("the comparison itself", OLD_TEST, NEW_TEST),
]


def main():
    if not os.path.exists(TARGET):
        print(f"NOT FOUND: {TARGET}")
        return 1

    with open(TARGET, "r", encoding="utf-8") as f:
        text = f.read()

    print("")
    print("Patching build_codex_db.py -- date tiebreak on status collapse")
    print("=" * 70)

    applied = failed = 0
    for desc, old, new in EDITS:
        if new in text:
            print(f"  = {desc:34} already patched")
        elif old in text:
            if text.count(old) != 1:
                print(f"  x {desc:34} NOT UNIQUE ({text.count(old)} matches)")
                failed += 1
                continue
            text = text.replace(old, new)
            print(f"  + {desc:34} patched")
            applied += 1
        else:
            print(f"  x {desc:34} ANCHOR NOT FOUND")
            failed += 1

    print("")
    if failed:
        print(f"  {failed} edit(s) failed -- NOTHING WRITTEN.")
        return 1
    if not applied:
        print("  Nothing to do -- already patched.")
        return 0

    if not os.path.exists(BACKUP):
        shutil.copy2(TARGET, BACKUP)
        print(f"  backup written: {os.path.basename(BACKUP)}")

    with open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    print(f"  {applied} edit(s) applied")

    # Verify the file still parses -- a broken build script is worse than a
    # wrong one, because the rebuild is the only way to fix the data.
    print("")
    print("  Checking the file still compiles...")
    try:
        import py_compile
        py_compile.compile(TARGET, doraise=True)
        print("  + compiles cleanly")
    except Exception as e:  # noqa: BLE001
        print(f"  x COMPILE FAILED: {e}")
        print(f"    restore with: copy {os.path.basename(BACKUP)} build_codex_db.py")
        return 1

    print("")
    print("  NEXT:")
    print("        python scripts/build_codex_db.py")
    print("        python scripts/seed_codex.py")
    print("        python scripts/check_contested_status.py")
    print("")
    print("  Expect: 'WOULD CHANGE' drops from 12 to 1 (Cercyon nigriceps,")
    print("  which is correct as it stands and must not move).")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
