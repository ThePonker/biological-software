"""Exports: non-key species show the full, jurisdiction-named status.

Fault: a non-key species with only priority listings exported as a bare
"Priority" (Codex's short label). A reader takes that as English S41; it was
SBL / NI / Wales S7. The full label names each jurisdiction, and the workbook
greys those that do not apply.

  examen_data.py     _load_status_data also returns display_status;
                     SiteSpecies gains status_full; _build_species_list fills it
  workbook_export.py non-key species use status_full (then greyed by jurisdiction)
  appendix_export.py non-key species use status_full

The short label is untouched: the Species tab, snapshots and key-species lists
still use it. Exact-text anchors, each found exactly once or NOTHING is written.
Backups: *.bak_status. All restored if any file fails to compile or import.
Then shows what the workbook will print for Birmingham's priority-only species.

Run:  python scripts\\patch_examen_status_full.py
"""
import importlib, io, os, py_compile, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EX = os.path.join(ROOT, "Examen")
EDITS = {
    "examen_data.py": [
        ('"short_status": (getattr(st, "short_status", "") or "") if st else "",',
         '"short_status": (getattr(st, "short_status", "") or "") if st else "",\n'
         '"display_status": (getattr(st, "display_status", "") or "") if st else "",'),
        ('common_name: str = ""',
         'common_name: str = ""\nstatus_full: str = ""          # jurisdiction-named, for exports'),
        ('status=cd.get("short_status", ""), tier=cd.get("tier", ""),',
         'status=cd.get("short_status", ""), status_full=cd.get("display_status", ""),\n'
         'tier=cd.get("tier", ""),'),
    ],
    "workbook_export.py": [
        ('else _parts_from_string(sp.status, juris), juris)',
         'else _parts_from_string(getattr(sp, "status_full", "") or sp.status, juris), juris)'),
    ],
    "appendix_export.py": [
        ('values = [sp.name, tax.get("common", ""), sp.status or "",',
         'values = [sp.name, tax.get("common", ""), getattr(sp, "status_full", "") or sp.status or "",'),
    ],
}

PROBE = r'''
import sys, os
R = __ROOT__
sys.path[:0] = [R, os.path.join(R, "Observatum")]
from Examen import examen_data as ed
from Examen import workbook_export as wb
d = ed.load_project_detail("Birmingham - Wheels Park", "", survey_year="2026")
rows = [s for s in d.species_list if s.status_full and not s.tier
        and any(k in s.status_full for k in ("Priority", "SBL", "S7", "S41", "BAP"))]
print(f"non-key species with priority listings: {len(rows)}")
for s in rows:
    parts = wb._parts_from_string(s.status_full, "England")
    shown = ", ".join(t if a else f"[grey] {t}" for t, a in parts)
    print(f"  {s.name[:28]:28} short={s.status!r:12} -> {shown}")
'''.replace("__ROOT__", repr(ROOT))

print("Examen -- jurisdiction-named status in exports")
print("=" * 76)
plan = {}
for name, reps in EDITS.items():
    path = os.path.join(EX, name)
    raw = io.open(path, "rb").read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    txt = raw.decode("utf-8-sig")
    if "status_full" in txt:
        sys.exit(f"  {name} already mentions status_full -- patched? Nothing written.")
    for old, new in reps:
        n = txt.count(old)
        print(f"  {name:<20} x{n}  {old[:58]}")
        if n != 1:
            sys.exit("ABORTED -- an anchor is not found exactly once. Nothing written.")
        if "\n" in new:
            line = next(l for l in txt.split("\n") if old in l)
            ind = line[:len(line) - len(line.lstrip())]
            eol = "\r" if line.endswith("\r") else ""
            first, *rest = new.split("\n")
            new = first + "".join(eol + "\n" + ind + r for r in rest)
        txt = txt.replace(old, new)
    plan[path] = (bom, txt)

for path, (bom, txt) in plan.items():
    shutil.copy2(path, path + ".bak_status")
    io.open(path, "w", encoding="utf-8-sig" if bom else "utf-8", newline="").write(txt)
try:
    for path in plan:
        py_compile.compile(path, doraise=True)
    sys.path[:0] = [ROOT, os.path.join(ROOT, "Observatum")]
    for m in ("Examen.examen_data", "Examen.workbook_export", "Examen.appendix_export"):
        importlib.import_module(m)
    print("\n  ok written; all three compile and import (backups: *.bak_status)")
except Exception as e:
    for path in plan:
        shutil.copy2(path + ".bak_status", path)
    sys.exit(f"  x FAILED ({type(e).__name__}: {e}) -- all three restored")

r = subprocess.run([sys.executable, "-c", PROBE], capture_output=True, text=True, cwd=ROOT)
print("\n  " + (r.stdout + (r.stderr[-800:] if r.returncode else "")).strip().replace("\n", "\n  "))
print("\nDone. Re-export the Birmingham workbook and check the Species appendix.")
