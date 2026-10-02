"""Exports name each legal instrument, so one that does not apply is greyed.

Fault: non-key species exported legal protection as a count, "Legal (1)" -- for
Holly Blue, the NI Wildlife Order. A count cannot be greyed, so it read as
English protection. Codex keeps the count for its own displays; for exports the
full label now names each instrument ("Legal: NI Wildlife Order 1985 Sch5"),
and the workbook judges each with _legal_applies -- the classifier's own rule.

  examen_data.py      + _full_status(st): display_status with "Legal (n)"
                        expanded to "Legal: <instrument>" per instrument
                        status_full now uses it
  workbook_export.py  _label_ok greys "Legal: ..." by jurisdiction
                      Grey italic definition also covers research-only

Exact-text anchors, each found exactly once or NOTHING is written. Backups:
*.bak_legal. All restored if any file fails to compile or import. Then shows
what the workbook prints for Birmingham's non-key species with legal protection.

Run:  python scripts\\patch_examen_legal_named.py
"""
import importlib, io, os, py_compile, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EX = os.path.join(ROOT, "Examen")

FULL_STATUS = '''def _full_status(st):
    """Codex's display_status, with "Legal (n)" expanded to the instruments.

    For exports: the workbook greys each instrument that does not apply in the
    assessment's jurisdiction, and a bare count cannot be greyed. Codex's own
    displays keep the count.
    """
    if not st:
        return ""
    s = getattr(st, "display_status", "") or ""
    legal = list(getattr(st, "legal_protection", None) or [])
    if not legal:
        return s
    names = [((getattr(e, "detail", None) or getattr(e, "value", "")) or "").strip()
             for e in legal]
    parts = [p.strip() for p in s.split(",")
             if p.strip() and not p.strip().startswith("Legal (")]
    return ", ".join(parts + [f"Legal: {n}" for n in names if n])


'''

EDITS = {
    "examen_data.py": [
        ('"display_status": (getattr(st, "display_status", "") or "") if st else "",',
         '"display_status": _full_status(st),'),
        ("def _load_status_data(", FULL_STATUS + "def _load_status_data("),
    ],
    "workbook_export.py": [
        ("def _label_ok(token, jurisdiction):",
         'def _label_ok(token, jurisdiction):\n'
         '    if token.startswith("Legal:"):\n'
         '        return _legal_ok(token[len("Legal:"):].strip(), jurisdiction)'),
        ('"A designation that applies in another jurisdiction. Shown for "',
         '"A designation that does not count towards Key Species for this "'),
        ('"completeness; it does not count towards Key Species under the "',
         '"assessment: it applies in another jurisdiction (see Summary), or "'),
        ('"jurisdiction this assessment was made for (see Summary)."),',
         '"is listed for research only. Shown for completeness."),'),
    ],
}

PROBE = r'''
import sys, os
R = __ROOT__
sys.path[:0] = [R, os.path.join(R, "Observatum")]
from Examen import examen_data as ed
from Examen import workbook_export as wb
d = ed.load_project_detail("Birmingham - Wheels Park", "", survey_year="2026")
rows = [s for s in d.species_list if "Legal" in (s.status_full or "")]
print(f"species with legal protection: {len(rows)}")
for s in rows:
    parts = wb._parts_from_string(s.status_full, "England")
    shown = ", ".join(t if a else f"[grey] {t}" for t, a in parts)
    print(f"  {s.name[:26]:26} key={'yes' if s.tier else 'no ':3} -> {shown}")
'''.replace("__ROOT__", repr(ROOT))

print("Examen exports -- legal instruments named and greyed")
print("=" * 76)
plan = {}
for name, reps in EDITS.items():
    path = os.path.join(EX, name)
    raw = io.open(path, "rb").read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    txt = raw.decode("utf-8-sig")
    if "_full_status" in txt or 'startswith("Legal:")' in txt:
        sys.exit(f"  {name} already patched -- nothing written")
    for old, new in reps:
        n = txt.count(old)
        print(f"  {name:<20} x{n}  {old[:58]}")
        if n != 1:
            sys.exit("ABORTED -- an anchor is not found exactly once. Nothing written.")
        line = next(l for l in txt.split("\n") if old in l)
        ind = line[:len(line) - len(line.lstrip())]
        eol = "\r" if line.endswith("\r") else ""
        if "\n" in new:
            first, *rest = new.split("\n")
            # top-level insertions (FULL_STATUS) keep their own indentation
            pad = "" if old.startswith("def _load_status_data(") else ind
            new = first + "".join(eol + "\n" + (pad + r if r else "") for r in rest)
        txt = txt.replace(old, new)
    plan[path] = (bom, txt)

for path, (bom, txt) in plan.items():
    shutil.copy2(path, path + ".bak_legal")
    io.open(path, "w", encoding="utf-8-sig" if bom else "utf-8", newline="").write(txt)
try:
    for path in plan:
        py_compile.compile(path, doraise=True)
    sys.path[:0] = [ROOT, os.path.join(ROOT, "Observatum")]
    for m in ("Examen.examen_data", "Examen.workbook_export"):
        importlib.import_module(m)
    print("\n  ok written; both compile and import (backups: *.bak_legal)")
except Exception as e:
    for path in plan:
        shutil.copy2(path + ".bak_legal", path)
    sys.exit(f"  x FAILED ({type(e).__name__}: {e}) -- both restored")

r = subprocess.run([sys.executable, "-c", PROBE], capture_output=True, text=True, cwd=ROOT)
print("\n  " + (r.stdout + (r.stderr[-800:] if r.returncode else "")).strip().replace("\n", "\n  "))
print("\nDone. Re-export the Birmingham workbook.")
