"""patch_key_pct_denominator.py -- one denominator for the key-species percentage.

    python scripts/patch_key_pct_denominator.py

The problem
-----------
Two percentages for the same quantity appeared on one screen. For Glory Park the
project table read 6.2% and the Overview card 8.0%, because the table divides by
total species recorded and the card by species-in-Pantheon.

Wil's own reports settle it. Bicester 2025: "34 have a National Conservation
Status ... which equates to 7.8% of the species from the survey" -- 34/433 =
7.85%, the recorded total, not the 414 Pantheon could analyse. Glory Park: eight
of 128 = 6.25%.

So the denominator is TOTAL SPECIES RECORDED. examen_data v4 already uses it;
this brings the analysis service into line.

Note on the card label
----------------------
overview_tab renders the subtitle "N% of Pantheon species", which is no longer
what the figure means. The label needs to read "of species recorded" -- that is
a separate one-line edit in Examen/overview_tab.py, not made here.

Safe to re-run. Backs up as pantheon_analysis_service.py.bak_fix3.
"""
import os
import shutil
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(_ROOT, "shared", "services", "pantheon_analysis_service.py")
BACKUP = TARGET + ".bak_fix3"

OLD = """        if result.species_in_pantheon > 0:
            result.key_species_pct = round(
                result.key_species_count / result.species_in_pantheon * 100, 1)"""

NEW = """        # Denominator is total species recorded, not species Pantheon knows.
        # Wil's reports: "34 ... equates to 7.8% of the species from the
        # survey" = 34/433, where Pantheon analysed only 414 of them.
        # species_in_pantheon remains available on the result for display.
        if result.total_species > 0:
            result.key_species_pct = round(
                result.key_species_count / result.total_species * 100, 1)"""


def main():
    if not os.path.exists(TARGET):
        print(f"NOT FOUND: {TARGET}")
        return 1
    with open(TARGET, "r", encoding="utf-8") as f:
        text = f.read()

    print("")
    print("Patching pantheon_analysis_service.py -- key-species denominator")
    print("=" * 70)

    if "Denominator is total species recorded" in text:
        print("  = already patched -- nothing to do")
        return 0

    n = text.count(OLD)
    if n != 1:
        print(f"  x percentage block  ({n} matches, expected 1)")
        print("  NOTHING WRITTEN.")
        return 1
    text = text.replace(OLD, NEW)
    print("  + percentage block")

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
        print(f"    restore: copy {os.path.basename(BACKUP)} pantheon_analysis_service.py")
        return 1

    print("")
    print("  Glory Park's Overview card should now read 6.2%, matching the")
    print("  project table and the report's own 8-of-128.")
    print("  The card's subtitle still says 'of Pantheon species' -- send")
    print("  Examen/overview_tab.py to correct the wording.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
