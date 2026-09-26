"""patch_overview_sentence.py -- the Overview label and the summary sentence.

    python scripts/patch_overview_sentence.py

Two fixes to Examen/overview_tab.py.

1. THE LABEL
------------
The key-species card read "6.2% of Pantheon species". Since the denominator was
settled on 5 September, that figure is key species over TOTAL SPECIES RECORDED --
matching Wil's reports ("8 of 128"). The number was right; the label was a
hardcoded string left over from before.

2. THE SENTENCE
---------------
Every clause went into a list joined with ". ", so

    128 species recorded. across 4 visits. 8 key species (6.2%). SQI 134
    (reliable). This indicates a site of some conservation value..

-- "across 4 visits" became a sentence of its own, and the interpretation
clause, which already ended in a full stop, got a second one. It is prose
written to be lifted into a report, which is why it matters.

Now:

    128 species recorded across 4 visits. 8 key species (6.2% of species
    recorded). SQI 134 (reliable). This indicates a site of some conservation
    value.

Also handles "1 visit" rather than "1 visits".

NOT CHANGED -- the interpretation
---------------------------------
The SQI bands (200 national, 150 regional, 125 some value) are left exactly as
they were. They have no source found -- not Pantheon's, not Fowles's -- and the
published reports surveyed in 38_Report_Survey.md cite percentages and name
their convention rather than applying fixed bands. Whether to keep, cite or
remove them is Wil's decision, not a formatting fix.

Line-based replacement for the sentence block; mixed line endings.
Safe to re-run. Backs up as overview_tab.py.bak_fix1.
"""
import os
import shutil
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(_ROOT, "Examen", "overview_tab.py")
BACKUP = TARGET + ".bak_fix1"

OLD_LABEL = 'f"{result.key_species_pct}% of Pantheon species",'
NEW_LABEL = 'f"{result.key_species_pct}% of species recorded",'

NEW_SENTENCE = '''        # Summary sentence. Built as whole sentences, then joined -- the old
        # version joined clauses with ". ", which split "across 4 visits" into
        # a sentence of its own and doubled the final full stop.
        first = f"{result.total_species} species recorded"
        if visits:
            first += f" across {visits} visit{'s' if visits != 1 else ''}"
        sentences = [
            first,
            f"{result.key_species_count} key species "
            f"({result.key_species_pct}% of species recorded)",
        ]
        sqi_text = f"SQI {sqi_val}"
        if sqi_reliable:
            sqi_text += " (reliable)"
        else:
            sqi_text += " (fewer than 15 scoring species \\u2014 treat with caution)"
        sentences.append(sqi_text)

        # SQI interpretation. NOTE: these bands have no published source -- they
        # are not Pantheon's and not Fowles's. Left unchanged pending a decision;
        # see patch_overview_sentence.py.
        if sqi and sqi.sqi:
            if sqi.sqi >= 200: sentences.append("This indicates a site of national importance")
            elif sqi.sqi >= 150: sentences.append("This indicates a site of regional importance")
            elif sqi.sqi >= 125: sentences.append("This indicates a site of some conservation value")
            elif sqi.sqi >= 100: sentences.append("No significant concentration of rare species")
        self.summary_sentence.setText(". ".join(sentences) + ".")'''


def main():
    if not os.path.exists(TARGET):
        print(f"NOT FOUND: {TARGET}")
        return 1
    with open(TARGET, "r", encoding="utf-8", newline="") as f:
        raw = f.read()
    ending = "\r\n" if "\r\n" in raw else "\n"

    print("")
    print("Patching Examen/overview_tab.py -- label and summary sentence")
    print("=" * 70)

    if "% of species recorded" in raw:
        print("  = already patched -- nothing to do")
        return 0

    # 1. label
    n = raw.count(OLD_LABEL)
    if n != 1:
        print(f"  x label  ({n} matches, expected 1)")
        print("  NOTHING WRITTEN.")
        return 1
    raw = raw.replace(OLD_LABEL, NEW_LABEL)
    print("  + key-species card label")

    # 2. sentence block, located by markers rather than a multi-line anchor
    lines = raw.split(ending)
    start = next((i for i, l in enumerate(lines)
                  if l.strip() == "# Summary sentence"), -1)
    end = next((i for i, l in enumerate(lines)
                if 'self.summary_sentence.setText(". ".join(parts)' in l), -1)
    if start < 0 or end < 0 or end < start:
        print(f"  x sentence block not found (start={start}, end={end})")
        print("  NOTHING WRITTEN.")
        return 1
    lines[start:end + 1] = NEW_SENTENCE.split("\n")
    raw = ending.join(lines)
    print(f"  + summary sentence (replaced lines {start + 1}-{end + 1})")

    shutil.copy2(TARGET, BACKUP)
    print(f"  backup written: {os.path.basename(BACKUP)}")
    with open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(raw)

    # Re-read and check, rather than trust the line index -- mixed endings
    # have made line counts misleading before.
    print("")
    try:
        import py_compile
        py_compile.compile(TARGET, doraise=True)
        with open(TARGET, "r", encoding="utf-8") as f:
            t = f.read()
        assert 'join(parts)' not in t, "old join still present"
        assert "sentences.append(sqi_text)" in t, "new block missing"
        print("  + compiles, and re-read confirms the new block is in place")
    except Exception as e:  # noqa: BLE001
        print(f"  x FAILED: {type(e).__name__}: {e}")
        print(f"    restore: copy {os.path.basename(BACKUP)} overview_tab.py")
        return 1

    # Exercise the sentence logic directly, without importing the Qt module.
    def build(total, visits, key, pct, sqi, reliable):
        first = f"{total} species recorded"
        if visits:
            first += f" across {visits} visit{'s' if visits != 1 else ''}"
        s = [first, f"{key} key species ({pct}% of species recorded)",
             f"SQI {sqi}" + (" (reliable)" if reliable else "")]
        if sqi >= 125:
            s.append("This indicates a site of some conservation value")
        return ". ".join(s) + "."

    print("")
    print("  The Glory Park sentence will now read:")
    print("    " + build(128, 4, 8, 6.2, 134, True))
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
