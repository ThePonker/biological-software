"""Examen reads assessment_records (your records + contributed) instead of observations.

  Examen/examen_data.py          11 queries
  Examen/site_analysis_view.py    1 query  (jurisdiction from vice-county)
  Examen/workbook_export.py       1 query  (occurrence sentences)

Only the table name changes. Each file must hold exactly the expected number of
`FROM observations`, or NOTHING is written. Backups: *.bak_view.
Afterwards: compiles all three, imports examen_data and workbook_export (not the
Qt view), and runs Examen's own project list to show what it now sees.

Run:  python scripts\\patch_examen_view.py
"""
import importlib, io, os, py_compile, re, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "Observatum"))

FILES = {"examen_data.py": 11, "site_analysis_view.py": 1, "workbook_export.py": 1}
PAT = re.compile(r"\bFROM(\s+)observations\b")

print("Examen -> assessment_records")
print("=" * 72)
plan, bad = [], []
for f, want in FILES.items():
    p = os.path.join(ROOT, "Examen", f)
    raw = io.open(p, "rb").read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    txt = raw.decode("utf-8-sig")
    n = len(PAT.findall(txt))
    print(f"  {f:<24} FROM observations x{n}  (expected {want})")
    if n != want:
        bad.append(f)
    if "assessment_records" in txt:
        bad.append(f + " (already mentions assessment_records)")
    plan.append((p, bom, txt))

if bad:
    print(f"\nABORTED -- {bad}. Nothing written.")
    sys.exit(1)

for p, bom, txt in plan:
    shutil.copy2(p, p + ".bak_view")
    new = PAT.sub(lambda m: "FROM" + m.group(1) + "assessment_records", txt)
    io.open(p, "w", encoding="utf-8-sig" if bom else "utf-8", newline="").write(new)
print("  + written (backups: *.bak_view)")

print("\n  Checking...")
for p, _, _ in plan:
    try:
        py_compile.compile(p, doraise=True)
        txt = io.open(p, encoding="utf-8-sig").read()
        n_view = len(re.findall(r"FROM\s+assessment_records", txt))
        n_obs = len(PAT.findall(txt))
        print(f"  ok compiles: {os.path.basename(p)}  "
              f"(FROM assessment_records x{n_view}, FROM observations x{n_obs})")
    except py_compile.PyCompileError as e:
        for q, _, _ in plan:
            shutil.copy2(q + ".bak_view", q)
        print(f"  x COMPILE FAILED in {os.path.basename(p)} -- all three restored\n{e}")
        sys.exit(1)

try:
    ed = importlib.import_module("Examen.examen_data")
    importlib.import_module("Examen.workbook_export")
    print("  ok imports: examen_data, workbook_export")
except Exception as e:
    print(f"  x IMPORT FAILED: {type(e).__name__}: {e}")
    sys.exit(1)

# What Examen's own project list now shows for the joint survey
try:
    projs = ed.load_all_projects()
    hit = [x for x in projs if "Wheels" in (x.project_name or "")]
    print(f"\n  Examen project list: {len(projs)} survey rows")
    for x in hit:
        print(f"    {x.project_name} {x.survey_year}: {x.record_count} records, "
              f"{x.species_count} species, sites {x.site_names}")
    if not hit:
        print("    (Birmingham - Wheels Park not listed)")
except Exception as e:
    print(f"  (project list not run: {type(e).__name__}: {e})")

print("\nDone. Undo: copy each Examen\\*.bak_view back over its file.")
