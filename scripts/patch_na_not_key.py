"""patch_na_not_key.py -- an NA species is never a Key Species.

    python scripts/patch_na_not_key.py

Apply BEFORE importing the NECR702 leaf-beetle review.

The rule
--------
A species review gives each species two separate labels:

    threat    CR / EN / VU / NT / LC / DD ... or NA -- "not applicable": not an
              established native, so not eligible for assessment. Recent
              arrivals and one-off strays get NA.
    rarity    NR / NS -- purely a count of 10 km squares.

For a species that has barely arrived, the two pull in opposite directions: NA
because it is not established, Nationally Rare because it has only been seen in
a handful of squares. NECR702 (Lane 2026) has two such:

    Chrysomela vigintipunctata   NA, NR   a recent arrival
    Smaragdina salicina          NA, NR   known from a single stray male

`_classify` counted a species as Key if EITHER label qualified, so both would
have become Rare Key Species -- the top tier, alongside genuinely threatened
natives -- and lifted the Rare Key percentage, the national-significance
figure, for any site recording one.

Decided 26 September 2026: a species the review itself says is not an
established native does not count as Key. Its rarity status is still stored
and still shown in the species list; it simply confers no key status.

Where it applies
----------------
    shared/repositories/codex_repository.py   _classify -- Examen's tiers
    Examen/workbook_export.py                 telfer_tier -- the workbook

The rule applies to every group, not only leaf beetles, so the patch reports how
many species ALREADY in Codex are NA with a rarity status -- those stop counting
as Key at the same moment.

Safe to re-run. Backs up as .bak_na alongside each file.
"""
import os
import shutil
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.join(_ROOT, "shared", "repositories", "codex_repository.py")
WORKBOOK = os.path.join(_ROOT, "Examen", "workbook_export.py")

REPO_ANCHOR = "    is_rare = is_scarce = is_priority = False"
REPO_NEW = '''    # An NA species -- not applicable: not an established native, so not
    # eligible for IUCN assessment -- is never a Key Species, whatever its
    # rarity status. A recent arrival or a single stray can be "Nationally Rare"
    # simply because it has barely been recorded. Its rarity is still stored
    # and displayed; it confers no key status. Decided 26 September 2026 on
    # NECR702 (Chrysomela vigintipunctata, Smaragdina salicina).
    if status.threat_iucn_2001 and \\
            (status.threat_iucn_2001.value or "").strip().upper() == "NA":
        return KeySpeciesTier.NONE

    is_rare = is_scarce = is_priority = False'''

WB_ANCHOR = "    if r in _RARE_V3 or t in _RARE_V2 or tl in _RARE_V1:"
WB_NEW = '''    # NA -- not an established native -- is never Key, whatever its rarity.
    # Mirrors CodexRepository._classify; see patch_na_not_key.py.
    if t == "NA":
        return ""
    if r in _RARE_V3 or t in _RARE_V2 or tl in _RARE_V1:'''


def patch(path, anchor, new, marker):
    name = os.path.relpath(path, _ROOT)
    if not os.path.exists(path):
        print(f"  x NOT FOUND: {name}")
        return False
    with open(path, "r", encoding="utf-8") as f:
        t = f.read()
    if marker in t:
        print(f"  = {name}: already patched")
        return True
    n = t.count(anchor)
    if n != 1:
        print(f"  x {name}: anchor matched {n} times, expected 1 -- not written")
        return False
    shutil.copy2(path, path + ".bak_na")
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(t.replace(anchor, new))
    # re-read rather than trust the write
    with open(path, "r", encoding="utf-8") as f:
        if marker not in f.read():
            print(f"  x {name}: re-read does not show the guard")
            return False
    import py_compile
    py_compile.compile(path, doraise=True)
    print(f"  + {name}: guard added, compiles")
    return True


def main():
    print("")
    print("Patching -- an NA species is never a Key Species")
    print("=" * 70)

    ok = patch(REPO, REPO_ANCHOR, REPO_NEW, "is never a Key Species")
    ok &= patch(WORKBOOK, WB_ANCHOR, WB_NEW, "NA -- not an established native")
    if not ok:
        print("")
        print("  Not complete -- do not import the review until both files pass.")
        return 1

    # Which species already in Codex does this change?
    try:
        sys.path.insert(0, _ROOT)
        import sqlite3
        import paths
        c = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)
        rows = c.execute("""
            SELECT d.species_name, r.status_value
            FROM status_summary t
            JOIN status_summary r ON r.tvk = t.tvk
                 AND r.status_track = 'rarity_modern'
            LEFT JOIN (SELECT tvk, MIN(species_name) species_name
                       FROM designations GROUP BY tvk) d ON d.tvk = t.tvk
            WHERE t.status_track = 'threat_iucn_2001'
              AND UPPER(t.status_value) = 'NA'
              AND r.status_value IN ('NR', 'NS')
            ORDER BY 1""").fetchall()
        c.close()
        print("")
        print(f"  Species already in Codex that are NA with a rarity status: {len(rows)}")
        print("  (these stop counting as Key now; before the import this should")
        print("   not include the two leaf beetles)")
        for name, rarity in rows[:20]:
            print(f"    {str(name)[:40]:40} {rarity}")
        if len(rows) > 20:
            print(f"    ... and {len(rows) - 20} more")
    except Exception as e:  # noqa: BLE001
        print(f"  (could not query codex.db: {e})")

    print("")
    print("  NEXT: replace scripts/import_status_review.py with the updated copy,")
    print("  then re-run the NECR702 dry run. Chrysomela vigintipunctata and")
    print("  Smaragdina salicina should no longer appear under Rare Key.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
