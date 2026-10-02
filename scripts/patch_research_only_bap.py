"""Research-only applies to the UK BAP entry too.

The research-only category comes from the 2007 UK BAP review; S41 inherited
it. patch_research_only.py relabelled the S41 entry, but UK BAP also confers key
status in England, so Cinnabar and Latticed Heath stayed key through it.

  codex_repository.py  _apply_track: the UK BAP entry of a research-only species
                       is labelled "UK BAP (research)" as well
                       _priority_label: "UK BAP (research only)"
  workbook_export.py   grey-out recognises "UK BAP (research only)"
  conservation_tab.py  greyed text no longer says "S41" specifically

Exact-text edits to lines the previous patch wrote; each must be found exactly
once or NOTHING is written. Backups: *.bak_research2. Prints key species per
survey before and after.

Run:  python scripts\\patch_research_only_bap.py
"""
import importlib, io, os, py_compile, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDITS = {
    os.path.join(ROOT, "shared", "repositories", "codex_repository.py"): [
        ('any(k in (value or "").lower() for k in ("s.41", "s41", "section 41")):',
         'any(k in (value or "").lower() for k in ("s.41", "s41", "section 41", "bap")):'),
        ('entry.value = "NERC S.41 England (research)"',
         'entry.value = ("UK BAP (research)" if "bap" in (value or "").lower()\n'
         '               else "NERC S.41 England (research)")'),
        ('return "S41 (research only)"',
         'return "UK BAP (research only)" if "bap" in v else "S41 (research only)"'),
    ],
    os.path.join(ROOT, "Examen", "workbook_export.py"): [
        ('_LABEL_KEYS = (("S41 (research", "research"),',
         '_LABEL_KEYS = (("S41 (research", "research"), ("UK BAP (research", "research"),'),
    ],
    os.path.join(ROOT, "Examen", "conservation_tab.py"): [
        ("S41 research only, not a Key Species status",
         "research only, not a Key Species status"),
    ],
}

PROBE = r'''
import sys, os, sqlite3
R = __ROOT__
sys.path[:0] = [R, os.path.join(R, "Observatum")]
from Examen import examen_data as ed
for p in ed.load_all_projects():
    print(f"{p.project_name[:30]:30} {str(p.survey_year):5} key {p.key_species_count:>3}  {p.key_species_pct}%")
import paths
from shared.repositories.codex_repository import CodexRepository
repo = CodexRepository()
u = sqlite3.connect(str(paths.UKSI_DB))
for name in ("Tyria jacobaeae", "Chiasmia clathrata", "Coenonympha pamphilus", "Lasiommata megera"):
    t = u.execute("SELECT tvk FROM taxa WHERE scientific_name=? AND rank='Species'", (name,)).fetchone()
    if t:
        s = repo.get_status_summary(t[0])
        print(f"  {name:24} key={s.is_key!s:5} {s.display_status}")
'''.replace("__ROOT__", repr(ROOT))


def run():
    r = subprocess.run([sys.executable, "-c", PROBE], capture_output=True, text=True, cwd=ROOT)
    return (r.stdout + (("\n" + r.stderr[-800:]) if r.returncode else "")).strip()


print("Research-only: UK BAP entry too")
print("=" * 76)
plan = {}
for path, reps in EDITS.items():
    raw = io.open(path, "rb").read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    txt = raw.decode("utf-8-sig")
    crlf = "\r\n" in txt
    for old, new in reps:
        n = txt.count(old)
        print(f"  {os.path.basename(path):<24} x{n}  {old[:60]}")
        if n != 1:
            sys.exit("ABORTED -- an anchor is not found exactly once "
                     "(was patch_research_only.py applied?). Nothing written.")
        if "\n" in new:
            # keep the original line's indentation and line ending for continuation lines
            line = next(l for l in txt.split("\n") if old in l)
            ind = line[:len(line) - len(line.lstrip())]
            eol = "\r" if line.endswith("\r") else ""
            first, *rest = new.split("\n")
            new = first + "".join(eol + "\n" + ind + r for r in rest)
        txt = txt.replace(old, new)
    plan[path] = (bom, txt)

print("\n  BEFORE:")
print("    " + run().replace("\n", "\n    "))

for path, (bom, txt) in plan.items():
    shutil.copy2(path, path + ".bak_research2")
    io.open(path, "w", encoding="utf-8-sig" if bom else "utf-8", newline="").write(txt)
try:
    for path in plan:
        py_compile.compile(path, doraise=True)
    sys.path[:0] = [ROOT, os.path.join(ROOT, "Observatum")]
    importlib.import_module("shared.repositories.codex_repository")
    importlib.import_module("Examen.workbook_export")
    print("\n  ok written; all three compile; modules import")
except Exception as e:
    for path in plan:
        shutil.copy2(path + ".bak_research2", path)
    sys.exit(f"  x FAILED ({type(e).__name__}: {e}) -- all three restored")

print("\n  AFTER:")
print("    " + run().replace("\n", "\n    "))
