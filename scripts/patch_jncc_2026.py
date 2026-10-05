"""Point the Codex build at the June 2026 JNCC spreadsheet.

  paths.py              JNCC_DIR -> data/conservation-designations-20260609
  build_codex_db.py     JNCC_XLSX found by pattern in JNCC_DIR (any '*esignations-*.xlsx',
                        newest by name), not the hard-coded 2023 filename -- JNCC also changed
                        its capitalisation; build_log note names the actual file

Every anchor must be found exactly once or NOTHING is written. Backups *.bak_jncc2026;
both restored if either fails to compile.

Run:  python scripts\\patch_jncc_2026.py
"""
import io, os, py_compile, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "paths.py")
B = os.path.join(ROOT, "scripts", "build_codex_db.py")
EDITS = {
    P: [("JNCC_DIR        = DATA_DIR / 'conservation-designations-20231206'",
         "JNCC_DIR        = DATA_DIR / 'conservation-designations-20260609'")],
    B: [('JNCC_XLSX = os.path.join(JNCC_DIR, "Taxon-designations-20231206.xlsx")',
         'import glob as _glob   # the newest designations workbook in JNCC_DIR, whatever its capitalisation\n'
         '_found = sorted(_glob.glob(os.path.join(JNCC_DIR, "*esignations-*.xlsx")))\n'
         'JNCC_XLSX = _found[-1] if _found else os.path.join(JNCC_DIR, "taxon-designations.xlsx")'),
        ('JNCC Dec 2023, Pantheon v3.7.4', 'JNCC {os.path.basename(JNCC_XLSX)}, Pantheon v3.7.4')],
}
print("Point the Codex build at the June 2026 JNCC spreadsheet")
print("=" * 60)
plan, problems = {}, []
for path, edits in EDITS.items():
    raw = io.open(path, "rb").read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    t = raw.decode("utf-8-sig")
    for old, new in edits:
        n = t.count(old)
        print(f"  x{n}  {os.path.basename(path)}: {old[:60]}")
        if n != 1:
            problems.append(f"{os.path.basename(path)}: {old[:50]} found {n} times")
        else:
            nl = "\r\n" if "\r\n" in t else "\n"
            t = t.replace(old, new.replace("\n", nl))
    plan[path] = (t, bom)
if problems:
    sys.exit("\n".join("  x " + p for p in problems) + "\nABORTED -- nothing written.")
for path, (t, bom) in plan.items():
    shutil.copy2(path, path + ".bak_jncc2026")
    io.open(path, "w", encoding="utf-8-sig" if bom else "utf-8", newline="").write(t)
try:
    for path in plan:
        py_compile.compile(path, doraise=True)
except py_compile.PyCompileError as e:
    for path in plan:
        shutil.copy2(path + ".bak_jncc2026", path)
    sys.exit(f"  x COMPILE FAILED -- both restored\n{e}")
sys.path.insert(0, ROOT)
import importlib, paths
importlib.reload(paths)
import glob
found = sorted(glob.glob(os.path.join(str(paths.JNCC_DIR), "*esignations-*.xlsx")))
print(f"\n  ok -- written, both compile")
print(f"  JNCC_DIR  -> {paths.JNCC_DIR}")
print(f"  workbook  -> {found[-1] if found else 'NOT FOUND -- check the folder'}")
