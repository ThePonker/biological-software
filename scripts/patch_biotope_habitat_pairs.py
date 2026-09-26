"""patch_biotope_habitat_pairs.py -- real biotope/habitat pairs from the sample.

    python scripts/patch_biotope_habitat_pairs.py

Run this FIRST, then patch_habitat_tab.py, which reads what this computes.

The fault
---------
habitat_tab._load_biotope_habitat_mapping builds the tree from:

    SELECT DISTINCT bb.biotope, h.habitat
    FROM broad_biotope bb JOIN habitats h ON bb.tvk = h.tvk

-- across the WHOLE of pantheon.db, not the sample. So every biotope/habitat
pair that exists anywhere appears for every site. Then each habitat row is
filled with `result.habitat_counts`, which is the SITE-WIDE count.

Glory Park showed "coastal" with 1 species, and beneath it "short sward & bare
ground: 41" and "tall sward & scrub: 52" -- the site totals, listed under a
biotope holding one species. Every habitat appeared under every biotope, with
the same numbers and the same SQI repeated.

The biotope rows themselves were right. The children were a cross-product.

The fix
-------
The analysis service now computes, per species, the cross of that species' own
biotopes with its own habitats, and counts them:

    result.biotope_habitat_counts = {biotope: {habitat: species_count}}
    result.biotope_habitat_sqi    = {biotope: {habitat: SQIResult}}

so the tab can render the pairs that are actually present, with the counts and
SQI belonging to that pair.

Safe to re-run. Backs up as pantheon_analysis_service.py.bak_fix4.
"""
import os
import shutil
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(_ROOT, "shared", "services", "pantheon_analysis_service.py")
BACKUP = TARGET + ".bak_fix4"

OLD_FIELDS = """    biotope_counts: dict = field(default_factory=dict)
    habitat_counts: dict = field(default_factory=dict)
    sat_counts: dict = field(default_factory=dict)"""

NEW_FIELDS = """    biotope_counts: dict = field(default_factory=dict)
    habitat_counts: dict = field(default_factory=dict)
    sat_counts: dict = field(default_factory=dict)

    # Real pairs from THIS sample -- {biotope: {habitat: count}} and the
    # matching SQI per pair. Without these the habitat tree is a cross-product
    # of every pair in Pantheon, carrying site-wide counts.
    biotope_habitat_counts: dict = field(default_factory=dict)
    biotope_habitat_sqi: dict = field(default_factory=dict)"""

OLD_HAB = """        for label, tvk_set in self._group_by(habitats).items():
            result.habitat_sqi.append(self._calc_sqi(label, tvk_set, sqs_scores))
        result.habitat_counts = {h: len(s) for h, s in self._group_by(habitats).items()}"""

NEW_HAB = """        for label, tvk_set in self._group_by(habitats).items():
            result.habitat_sqi.append(self._calc_sqi(label, tvk_set, sqs_scores))
        result.habitat_counts = {h: len(s) for h, s in self._group_by(habitats).items()}

        # Biotope x habitat, per species -- only pairs this sample actually
        # holds, each with its own species set.
        pairs = {}
        for tvk in unique_tvks:
            for bio in biotopes.get(tvk, []):
                for hab in habitats.get(tvk, []):
                    pairs.setdefault(bio, {}).setdefault(hab, set()).add(tvk)
        result.biotope_habitat_counts = {
            bio: {hab: len(tvks_) for hab, tvks_ in habs.items()}
            for bio, habs in pairs.items()}
        result.biotope_habitat_sqi = {
            bio: {hab: self._calc_sqi(f"{bio} / {hab}", tvks_, sqs_scores)
                  for hab, tvks_ in habs.items()}
            for bio, habs in pairs.items()}"""

EDITS = [
    ("AnalysisResult fields", OLD_FIELDS, NEW_FIELDS),
    ("pair computation", OLD_HAB, NEW_HAB),
]


def main():
    if not os.path.exists(TARGET):
        print(f"NOT FOUND: {TARGET}")
        return 1
    with open(TARGET, "r", encoding="utf-8") as f:
        text = f.read()

    print("")
    print("Patching pantheon_analysis_service.py -- biotope/habitat pairs")
    print("=" * 70)

    if "biotope_habitat_counts" in text:
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
        print(f"    restore: copy {os.path.basename(BACKUP)} pantheon_analysis_service.py")
        return 1

    print("")
    print("  NEXT: python scripts/patch_habitat_tab.py")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
