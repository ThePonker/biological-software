"""patch_guild_casing.py -- stop Pantheon's guild casing splitting the counts.

    python scripts/patch_guild_casing.py

The fault
---------
pantheon.db stores four feeding-guild values in two casings:

    Herbivore / herbivore
    Predator / predator
    Saprophagous / saprophagous
    Unknown / unknown

PantheonAnalysisService.analyse counts guilds with a Counter keyed on the raw
string, so each pair is counted as two guilds. Glory Park showed:

    Larval: predator (37), herbivore (19), saprophagous (11), ... Predator (4)

Larval predators are 41, not 37 and 4. The figure is wrong wherever guild
composition is reported.

Scope: guilds only. habitats (17 values), broad_biotope (4) and
specific_assemblage_types (26) were checked and have no case variants, so no SQI
figure is affected -- only the guild counts.

The fix
-------
Normalise to lower case at the point of counting, which is where the grouping
happens. Pantheon's predominant form is lower case ("decaying wood", "heartwood
decay"), so the capitalised entries are the outliers.

_group_by is left alone deliberately: it feeds biotope/habitat/SAT SQI, those
are clean, and changing it would alter labels in output that is currently
correct.

Safe to re-run. Backs up as pantheon_analysis_service.py.bak_fix1.
"""
import os
import shutil
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(_ROOT, "shared", "services", "pantheon_analysis_service.py")
BACKUP = TARGET + ".bak_fix1"

OLD_LARVAL = '                larval[g["larval guild"]] += 1'
NEW_LARVAL = '                larval[g["larval guild"].strip().lower()] += 1'

OLD_ADULT = '                adult[g["adult guild"]] += 1'
NEW_ADULT = '                adult[g["adult guild"].strip().lower()] += 1'

OLD_COMMENT = "        # Guilds"
NEW_COMMENT = (
    "        # Guilds\n"
    "        # Pantheon stores Herbivore/herbivore, Predator/predator,\n"
    "        # Saprophagous/saprophagous and Unknown/unknown, so the raw string\n"
    "        # would count each pair twice. Normalised to lower case, which is\n"
    "        # Pantheon's predominant form. See patch_guild_casing.py."
)

EDITS = [
    ("comment", OLD_COMMENT, NEW_COMMENT),
    ("larval guild count", OLD_LARVAL, NEW_LARVAL),
    ("adult guild count", OLD_ADULT, NEW_ADULT),
]


def main():
    if not os.path.exists(TARGET):
        print(f"NOT FOUND: {TARGET}")
        print("  (the 240-byte file in Observatum/src/services is the re-export")
        print("   shim, not the implementation)")
        return 1

    with open(TARGET, "r", encoding="utf-8") as f:
        text = f.read()

    print("")
    print("Patching shared/services/pantheon_analysis_service.py -- guild casing")
    print("=" * 70)

    applied = failed = 0
    for desc, old, new in EDITS:
        if new in text:
            print(f"  = {desc:22} already patched")
        elif old in text:
            if text.count(old) != 1:
                print(f"  x {desc:22} NOT UNIQUE ({text.count(old)} matches)")
                failed += 1
                continue
            text = text.replace(old, new)
            print(f"  + {desc:22} patched")
            applied += 1
        else:
            print(f"  x {desc:22} ANCHOR NOT FOUND")
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

    print("")
    print("  Checking the file still compiles...")
    try:
        import py_compile
        py_compile.compile(TARGET, doraise=True)
        print("  + compiles cleanly")
    except Exception as e:  # noqa: BLE001
        print(f"  x COMPILE FAILED: {e}")
        print(f"    restore: copy {os.path.basename(BACKUP)} pantheon_analysis_service.py")
        return 1

    print("")
    print("  NEXT: python -m Examen -> Glory Park -> Overview")
    print("  Expect the larval row to read predator (41) with no separate")
    print("  Predator (4), and adult nectivore to merge likewise.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
