"""Workbook Summary: SQI notes state the arithmetic actually used.

After the denominator fix the notes still read "From 174 scoring species",
while 118 = 217 / 184. A reader checking with the note's numbers would get 125.
Each SQI note now reads, e.g.:
  "217 / 184 species analysed x 100 (174 scoring; Pantheon species without a
   score count as 0)"

Three exact-text anchors in Examen/workbook_export.py, each found exactly once
or NOTHING is written. Backup: .bak_sqinotes. Compiles and imports.

Run:  python scripts\\patch_sqi_notes.py
"""
import importlib, io, os, py_compile, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "Examen", "workbook_export.py")

HELPER = '''def _sqi_arith(s):
    """The SQI's own arithmetic, so a reader can check it from the sheet."""
    if s is None:
        return ""
    n = getattr(s, "species_analysed", 0) or s.species_with_sqs
    unscored = n - s.species_with_sqs
    tail = (f"; {unscored} Pantheon species without a score count as 0"
            if unscored > 0 else "")
    return (f"{s.sqs_sum} \\u00f7 {n} species analysed \\u00d7 100 "
            f"({s.species_with_sqs} scoring{tail})")


'''

EDITS = [
    ('f"From {_sqi_n(result.overall_sqi)} scoring species. "',
     'f"{_sqi_arith(result.overall_sqi)}. "'),
    ('f"From {_sqi_n(result.overall_sqi)} scoring species, including "',
     'f"{_sqi_arith(result.overall_sqi)}, including "'),
    ('f"From {_sqi_n(_pub)} species with a score Pantheon published. "',
     'f"{_sqi_arith(_pub)}, on Pantheon\'s published scores only. "'),
    ("def _sheet_summary(", HELPER + "def _sheet_summary("),
]

raw = io.open(P, "rb").read()
bom = raw.startswith(b"\xef\xbb\xbf")
txt = raw.decode("utf-8-sig")
print("Workbook Summary -- SQI notes show their arithmetic")
print("=" * 72)
if "_sqi_arith" in txt:
    sys.exit("  already patched -- nothing written")
for old, new in EDITS:
    n = txt.count(old)
    print(f"  x{n}  {old[:64]}")
    if n != 1:
        sys.exit("ABORTED -- an anchor is not found exactly once. Nothing written.")
    if "\n" in new:
        eol = "\r\n" if "\r\n" in txt else "\n"
        new = new.replace("\n", eol)
    txt = txt.replace(old, new)

shutil.copy2(P, P + ".bak_sqinotes")
io.open(P, "w", encoding="utf-8-sig" if bom else "utf-8", newline="").write(txt)
try:
    py_compile.compile(P, doraise=True)
    sys.path[:0] = [ROOT, os.path.join(ROOT, "Observatum")]
    m = importlib.import_module("Examen.workbook_export")

    class S:
        sqs_sum, species_analysed, species_with_sqs = 217, 184, 174
    print(f"\n  ok written, compiles, imports (backup: .bak_sqinotes)")
    print(f"  example: {m._sqi_arith(S())}")
except Exception as e:
    shutil.copy2(P + ".bak_sqinotes", P)
    sys.exit(f"  x FAILED ({type(e).__name__}: {e}) -- restored")
print("\nDone. Re-export the Birmingham workbook.")
