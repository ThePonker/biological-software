"""patch_workbook_occurrence.py -- occurrence becomes a placeholder to write into.

    python scripts/patch_workbook_occurrence.py

Why
---
The exporter generated a closing sentence for each key species -- "3 individuals
were recorded from Wooburn Green in June and July." Published accounts always
end with one, but they are written, not assembled, and a generated sentence
would be uniform in a way that reads mechanically across eight or eighty species.

The column now carries the raw evidence instead, so the sentence can be written
without going back to the records:

    [write occurrence]  ·  3 individuals · Wooburn Green (FIT 2) · June, July

Everything after the marker is fact from this survey's records: how many, where
(sub-location in brackets where recorded), and which months. The author writes
the sentence; the software supplies what it would otherwise have to be looked up.

Safe to re-run. Backs up as workbook_export.py.bak_fix2.
"""
import os
import shutil
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(_ROOT, "Examen", "workbook_export.py")
BACKUP = TARGET + ".bak_fix2"

OLD_DOC = '''Species accounts
----------------
Accounts come from observatum.db.species_profiles. The stored profile is the
reusable part; the site-specific closing sentence ("a single adult was taken
from FIT 3 in July") is generated here from the records. Where no profile
exists the cell is left blank, which also shows which accounts are worth
writing next.'''

NEW_DOC = '''Species accounts
----------------
Accounts come from observatum.db.species_profiles. The stored profile is the
reusable part; the site-specific closing sentence ("a single adult was taken
from FIT 3 in July") is WRITTEN, not generated -- a manufactured sentence reads
uniformly across a whole table in a way a real account does not.

The occurrence column therefore carries a placeholder followed by the evidence
needed to write it: count, places, months. Where no profile exists the account
cell is left blank, which also shows which accounts are worth writing next.'''

OLD_BUILD = '''    for tvk, g in grouped.items():
        months = [MONTHS[m - 1] for m in sorted(g["months"]) if 1 <= m <= 12]
        places = sorted(g["places"])
        bits = []
        if g["n"] == 1:
            bits.append("A single individual was recorded")
        else:
            bits.append(f"{g['n']} individuals were recorded")
        if places:
            shown = ", ".join(places[:3]) + (" and elsewhere" if len(places) > 3 else "")
            bits.append(f"from {shown}")
        if months:
            bits.append("in " + (" and ".join(months) if len(months) <= 2
                                 else ", ".join(months[:-1]) + " and " + months[-1]))
        out[tvk] = " ".join(bits) + "."
    return out'''

NEW_BUILD = '''    for tvk, g in grouped.items():
        months = [MONTHS[m - 1] for m in sorted(g["months"]) if 1 <= m <= 12]
        places = sorted(g["places"])
        bits = [OCCURRENCE_PLACEHOLDER]
        bits.append("1 individual" if g["n"] == 1 else f"{g['n']} individuals")
        if places:
            bits.append(", ".join(places[:4])
                        + (" and elsewhere" if len(places) > 4 else ""))
        if months:
            bits.append(", ".join(months))
        out[tvk] = "  \\u00b7  ".join(bits)
    return out'''

OLD_CONST = '''# Pantheon does not trust an SQI computed from fewer than this many scoring
# species. Telfer calls an assemblage above it "well represented".
SQI_MIN_SPECIES = 15'''

NEW_CONST = '''# Pantheon does not trust an SQI computed from fewer than this many scoring
# species. Telfer calls an assemblage above it "well represented".
SQI_MIN_SPECIES = 15

# The occurrence sentence is written by the author, not generated. This marker
# opens the cell, followed by the evidence needed to write it.
OCCURRENCE_PLACEHOLDER = "[write occurrence]"'''

OLD_HEADER = '''                ["Tier", "Order", "Family", "Species", "Common name",
                 "Conservation status", "SQS", "Broad biotope", "Habitat",
                 "Species account", "Occurrence during this survey"],'''

NEW_HEADER = '''                ["Tier", "Order", "Family", "Species", "Common name",
                 "Conservation status", "SQS", "Broad biotope", "Habitat",
                 "Species account", "Occurrence — to write (evidence follows)"],'''

OLD_NOTE = '''    ws.cell(row=r, column=1,
            value="Species accounts are drawn from the species profile store; "
                  "the occurrence sentence is generated from the records for "
                  "this survey. Blank account cells have no profile written "
                  "yet.").font = NOTE_FONT'''

NEW_NOTE = '''    ws.cell(row=r, column=1,
            value="Species accounts are drawn from the species profile store. "
                  "The occurrence sentence is written by the author; the "
                  "column gives the evidence from this survey — count, places "
                  "and months — after the marker. Blank account cells have no "
                  "profile written yet.").font = NOTE_FONT'''

EDITS = [
    ("module docstring", OLD_DOC, NEW_DOC),
    ("placeholder constant", OLD_CONST, NEW_CONST),
    ("occurrence built as evidence", OLD_BUILD, NEW_BUILD),
    ("column heading", OLD_HEADER, NEW_HEADER),
    ("sheet note", OLD_NOTE, NEW_NOTE),
]


def main():
    if not os.path.exists(TARGET):
        print(f"NOT FOUND: {TARGET}")
        return 1
    with open(TARGET, "r", encoding="utf-8") as f:
        text = f.read()

    print("")
    print("Patching Examen/workbook_export.py -- occurrence placeholder")
    print("=" * 70)

    if "OCCURRENCE_PLACEHOLDER" in text:
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
        sys.path.insert(0, _ROOT)
        import importlib
        m = importlib.import_module("Examen.workbook_export")
        importlib.reload(m)
        print("  + imports cleanly; marker:", m.OCCURRENCE_PLACEHOLDER)
    except Exception as e:  # noqa: BLE001
        print(f"  x FAILED: {type(e).__name__}: {e}")
        print(f"    restore: copy {os.path.basename(BACKUP)} workbook_export.py")
        return 1

    print("")
    print("  Re-run scripts/test_workbook.py. The occurrence column should read")
    print("  e.g.  [write occurrence]  ·  3 individuals  ·  Wooburn Green  ·  June, July")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
