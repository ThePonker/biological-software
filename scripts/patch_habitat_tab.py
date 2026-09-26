"""patch_habitat_tab.py -- render the habitat tree from real pairs.

    python scripts/patch_habitat_tab.py

Run patch_biotope_habitat_pairs.py FIRST -- this reads what it computes.

What changes
------------
1. THE TREE. `_load_biotope_habitat_mapping` queried every biotope/habitat pair
   in the whole of pantheon.db, so every habitat appeared under every biotope,
   each carrying the SITE-WIDE count and the SITE-WIDE SQI. Glory Park showed
   "coastal" holding 1 species with "short sward & bare ground: 41" beneath it.
   The tree now uses result.biotope_habitat_counts -- the pairs this sample
   actually holds, with the counts and SQI for that pair.

2. UNRELIABLE SQI SUPPRESSED. A habitat with three scoring species was showing
   "SQI 200*". The asterisk was honest but the number invites misreading in a
   report; Pantheon withholds it. Below the 15-species threshold the SQI column
   now shows the scoring count in brackets instead, e.g. "(3 spp)".

3. COLUMN HEADER. "% Rep" is sample species divided by Pantheon's national
   total for that habitat -- renamed "% National Pool", matching the wording
   the Assemblages tab already uses.

Safe to re-run. Backs up as habitat_tab.py.bak_fix1.
"""
import os
import re
import shutil
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(_ROOT, "Examen", "habitat_tab.py")
BACKUP = TARGET + ".bak_fix1"

OLD_HEADERS = ('        self.tree.setHeaderLabels(["Biotope / Habitat", "Species", '
               '"Scoring", "SQI", "% Rep"])')
NEW_HEADERS = ('        self.tree.setHeaderLabels(["Biotope / Habitat", "Species", '
               '"Scoring", "SQI", "% National Pool"])')

NEW_BUILD = '''    @staticmethod
    def _sqi_text(sqi):
        """SQI cell text. Withheld below the reliability threshold.

        A habitat with three scoring species was rendering "SQI 200*". The
        asterisk was honest, but the figure invites misreading in a report and
        Pantheon withholds it. Show the evidence instead.
        """
        if not sqi or not sqi.species_with_sqs:
            return "-"
        if not sqi.reliable:
            return f"({sqi.species_with_sqs} spp)"
        return str(int(sqi.sqi))

    @staticmethod
    def _sqi_colour(sqi):
        if not sqi or not sqi.reliable or not sqi.sqi:
            return None
        if sqi.sqi >= 150:
            return QColor(MOSS_GREEN)
        if sqi.sqi >= 125:
            return QColor(AMBER)
        return None

    def _fill(self, item, count, sqi, pct):
        item.setText(1, str(count))
        item.setTextAlignment(1, Qt.AlignmentFlag.AlignCenter)
        item.setText(2, str(sqi.species_with_sqs) if sqi else "0")
        item.setTextAlignment(2, Qt.AlignmentFlag.AlignCenter)
        item.setText(3, self._sqi_text(sqi))
        item.setTextAlignment(3, Qt.AlignmentFlag.AlignCenter)
        col = self._sqi_colour(sqi)
        if col:
            item.setForeground(3, col)
        elif sqi and not sqi.reliable:
            item.setForeground(3, QColor(TEXT_MUTED))
        item.setText(4, f"{pct}%" if pct > 0 else "-")
        item.setTextAlignment(4, Qt.AlignmentFlag.AlignCenter)
        if pct >= 21:
            item.setForeground(4, QColor(MOSS_GREEN))
        elif pct >= 10:
            item.setForeground(4, QColor(AMBER))

    def _build_tree(self, result):
        """Biotope -> habitat, using only the pairs this sample holds.

        Previously the pairs came from a join across the whole of pantheon.db,
        so every habitat appeared under every biotope carrying the site-wide
        count -- "coastal" with one species listed "short sward & bare ground:
        41" beneath it.
        """
        self.tree.clear()
        refs = _load_reference_counts()
        bio_refs = refs.get("biotope", {})
        hab_refs = refs.get("habitat", {})

        bio_map = {s.label: s for s in result.biotope_sqi}
        pair_counts = getattr(result, "biotope_habitat_counts", {}) or {}
        pair_sqi = getattr(result, "biotope_habitat_sqi", {}) or {}

        for bio_name in sorted(result.biotope_counts.keys()):
            bio_count = result.biotope_counts.get(bio_name, 0)
            bio_total = bio_refs.get(bio_name, 0)
            pct = round(bio_count / bio_total * 100, 1) if bio_total else 0

            bio_item = QTreeWidgetItem()
            bio_item.setText(0, bio_name)
            bio_item.setFont(0, QFont("Segoe UI", 10, QFont.Weight.Bold))
            self._fill(bio_item, bio_count, bio_map.get(bio_name), pct)

            habs = pair_counts.get(bio_name, {})
            for hab_name in sorted(habs, key=lambda h: -habs[h]):
                hab_count = habs[hab_name]
                hab_total = hab_refs.get(hab_name, 0)
                h_pct = round(hab_count / hab_total * 100, 1) if hab_total else 0
                hab_item = QTreeWidgetItem()
                hab_item.setText(0, hab_name)
                self._fill(hab_item, hab_count,
                           pair_sqi.get(bio_name, {}).get(hab_name), h_pct)
                bio_item.addChild(hab_item)

            self.tree.addTopLevelItem(bio_item)

        self.tree.expandAll()
'''


def main():
    if not os.path.exists(TARGET):
        print(f"NOT FOUND: {TARGET}")
        return 1
    with open(TARGET, "r", encoding="utf-8", newline="") as f:
        raw = f.read()
    ending = "\r\n" if "\r\n" in raw else "\n"

    print("")
    print("Patching Examen/habitat_tab.py -- real biotope/habitat pairs")
    print("=" * 70)

    if "def _sqi_text" in raw:
        print("  = already patched -- nothing to do")
        return 0

    text = raw
    failed = 0

    # 1. Column header
    if text.count(OLD_HEADERS) == 1:
        text = text.replace(OLD_HEADERS, NEW_HEADERS)
        print("  + column header")
    else:
        print(f"  x column header  ({text.count(OLD_HEADERS)} matches)")
        failed += 1

    # 2. Replace _build_tree .. _load_biotope_habitat_mapping (both go)
    lines = text.split(ending) if ending in text else text.split("\n")

    def find(prefix, after=0):
        for i in range(after, len(lines)):
            if lines[i].startswith(prefix):
                return i
        return -1

    start = find("    def _build_tree(self, result):")
    end = find("    def _build_fidelity(self, fidelity_data):",
               start if start >= 0 else 0)
    if start < 0 or end < 0:
        print("  x could not locate _build_tree .. _build_fidelity")
        failed += 1
    else:
        print(f"  + _build_tree and _load_biotope_habitat_mapping "
              f"(lines {start + 1}-{end}) replaced")
        lines = lines[:start] + NEW_BUILD.split("\n") + lines[end:]
        text = ending.join(lines)

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
        print(f"    restore: copy {os.path.basename(BACKUP)} habitat_tab.py")
        return 1

    print("")
    print("  NEXT: python -m Examen -> Glory Park -> Habitats")
    print("  'coastal' should hold one species and one or two habitats, not")
    print("  eleven with site-wide counts. Habitats sort by species count.")
    print("  Small samples show '(3 spp)' where an SQI would mislead.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
