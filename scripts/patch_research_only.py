"""S41 'research only' species are not Key Species -- one rule, in Codex.

Pantheon lists 72 species as "Section 41 Priority Species - research only":
widespread species added to S41 to flag research needs, not site conservation
(Cinnabar, Latticed Heath ...). JNCC lists them as plain S41, so Codex Full
counted them as Key Species; Pantheon Only labelled them "(research)" but the
label still contained "S.41", so they counted there too.

  shared/repositories/codex_repository.py
    + _get_research_only_tvks(): Pantheon's list, through the TVK BRIDGE
      (Pantheon is keyed on 2017 TVKs), cached
    _apply_track (Codex Full): an S41 entry for a research-only species is
      labelled "NERC S.41 England (research)" -- the same label Pantheon Only uses
    _priority_applies: a research-only entry confers no key status, anywhere
    _priority_label: shows "S41 (research only)"
  Examen/workbook_export.py   grey-out recognises "S41 (research only)"
  Examen/conservation_tab.py  greyed row says "research only", not "not applicable"

Before/after: every survey's key-species count is printed both sides, so the
change shows itself. Functions located by parsing; NOTHING is written unless
every anchor is found exactly once; *.bak_research; all three restored if any
fails to compile or import.

Run:  python scripts\\patch_research_only.py
"""
import ast, importlib, io, os, py_compile, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CR = os.path.join(ROOT, "shared", "repositories", "codex_repository.py")
WB = os.path.join(ROOT, "Examen", "workbook_export.py")
CT = os.path.join(ROOT, "Examen", "conservation_tab.py")

PROBE = r'''
import sys, os
R = __ROOT__
sys.path[:0] = [R, os.path.join(R, "Observatum")]
from Examen import examen_data as ed
for p in ed.load_all_projects():
    print(f"{p.project_name[:30]:30} {str(p.survey_year):5} key {p.key_species_count:>3}  {p.key_species_pct}%")
'''.replace("__ROOT__", repr(ROOT))

PROBE_AFTER = PROBE + r'''
import sqlite3, paths
from shared.repositories.codex_repository import CodexRepository
repo = CodexRepository()
print("research-only species (current TVKs, via bridge):", len(repo._get_research_only_tvks()))
u = sqlite3.connect(str(paths.UKSI_DB))
for name in ("Tyria jacobaeae", "Chiasmia clathrata", "Coenonympha pamphilus", "Lasiommata megera"):
    t = u.execute("SELECT tvk FROM taxa WHERE scientific_name=? AND rank='Species'", (name,)).fetchone()
    if t:
        s = repo.get_status_summary(t[0])
        print(f"  {name:24} key={s.is_key!s:5} tier={getattr(s.tier, 'value', s.tier)!s:9} {s.display_status}")
'''


def run(code):
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT)
    return (r.stdout + (("\n" + r.stderr[-800:]) if r.returncode else "")).strip()


class F:
    def __init__(self, path):
        self.path = path
        raw = io.open(path, "rb").read()
        self.bom = raw.startswith(b"\xef\xbb\xbf")
        self.lines = raw.decode("utf-8-sig").split("\n")
        self.tree = ast.parse("\n".join(l.rstrip("\r") for l in self.lines))
        self.edits = []

    def fn(self, name):
        h = [n for n in ast.walk(self.tree) if isinstance(n, ast.FunctionDef) and n.name == name]
        return h[0] if len(h) == 1 else None

    def find(self, node, pred):
        lo, hi = (node.lineno - 1, node.end_lineno) if node else (0, len(self.lines))
        return [i for i in range(lo, hi) if pred(self.lines[i].rstrip("\r"))]

    def blk(self, i, body, ind=None):
        s = self.lines[i].rstrip("\r")
        ind = s[:len(s) - len(s.lstrip())] if ind is None else ind
        e = "\r" if self.lines[i].endswith("\r") else ""
        return [(ind + b if b else "") + e for b in body.split("\n")]

    def write(self):
        for s, e, new in sorted(self.edits, key=lambda t: -t[0]):
            self.lines[s:e + 1] = new
        shutil.copy2(self.path, self.path + ".bak_research")
        io.open(self.path, "w", encoding="utf-8-sig" if self.bom else "utf-8",
                newline="").write("\n".join(self.lines))

    def restore(self):
        shutil.copy2(self.path + ".bak_research", self.path)


print("S41 research-only species -- not Key Species")
print("=" * 76)
problems = []
cr, wb, ct = F(CR), F(WB), F(CT)
if "_get_research_only_tvks" in "\n".join(cr.lines):
    sys.exit("  already patched -- nothing written")

# ---- codex_repository
pa, pl, at = cr.fn("_priority_applies"), cr.fn("_priority_label"), cr.fn("_apply_track")
ap = [i for i, l in enumerate(cr.lines) if l.strip().startswith("def _apply_pantheon_row(self")]
for nm, ok in (("_priority_applies", pa), ("_priority_label", pl), ("_apply_track", at)):
    if not ok:
        problems.append(f"{nm}() not found exactly once")
if len(ap) != 1:
    problems.append(f"def _apply_pantheon_row found {len(ap)} times")
if pa and pl and at and len(ap) == 1:
    i = pa.lineno - 1
    cr.edits.append((i, i, [cr.lines[i]] + cr.blk(i, '''# S41 "research only" flags research needs, not site conservation: it never
# confers Key Species status, in any jurisdiction (Pantheon; 02_Current_State).
if "research" in (value or "").lower():
    return False''', ind=cr.lines[i][:len(cr.lines[i]) - len(cr.lines[i].lstrip())] + "    ")))
    h = cr.find(pl, lambda l: l.strip() == 'v = (value or "").lower()')
    if len(h) == 1:
        cr.edits.append((h[0], h[0], [cr.lines[h[0]]] + cr.blk(h[0],
            'if "research" in v:\n    return "S41 (research only)"')))
    else:
        problems.append(f"_priority_label: 'v = (value or \"\").lower()' x{len(h)}")
    h = cr.find(at, lambda l: l.strip() == "status.priority.append(entry)")
    if len(h) == 1:
        cr.edits.append((h[0], h[0], cr.blk(h[0], '''# JNCC lists research-only species as plain S41; Pantheon distinguishes them.
if status.tvk in self._get_research_only_tvks() and \\
        any(k in (value or "").lower() for k in ("s.41", "s41", "section 41")):
    entry.value = "NERC S.41 England (research)"''') + [cr.lines[h[0]]]))
    else:
        problems.append(f"_apply_track: 'status.priority.append(entry)' x{len(h)}")
    i = ap[0]
    cr.edits.append((i, i, cr.blk(i, '''def _get_research_only_tvks(self):
    """Current UKSI TVKs that Pantheon lists as S41 'research only'.

    Pantheon is keyed on 2017 TVKs, so the list goes through the TVK bridge.
    Cached for the life of the repository.
    """
    if getattr(self, "_research_only", None) is not None:
        return self._research_only
    out = set()
    try:
        pan = self._get_pantheon_conn()
        if pan is not None:
            pan_tvks = [r[0] for r in pan.execute(
                "SELECT DISTINCT tvk FROM conservation_status WHERE reporting_category = ?",
                ("Section 41 Priority Species - research only",))]
            c = self._get_conn()
            for batch in _chunked(pan_tvks, 500):
                ph = ",".join("?" * len(batch))
                out.update(r[0] for r in c.execute(
                    f"SELECT uksi_tvk FROM tvk_bridge WHERE pantheon_tvk IN ({ph})", batch))
    except Exception:
        pass
    self._research_only = out
    return out
''') + [cr.lines[i]]))

# ---- workbook_export
h = wb.find(None, lambda l: l.strip().startswith('_LABEL_KEYS = (("S41", "s41"),'))
if len(h) == 1:
    wb.edits.append((h[0], h[0], [wb.lines[h[0]].replace(
        '_LABEL_KEYS = (("S41", "s41"),',
        '_LABEL_KEYS = (("S41 (research", "research"), ("S41", "s41"),')]))
else:
    problems.append(f"workbook_export: _LABEL_KEYS line x{len(h)}")

# ---- conservation_tab
h = ct.find(None, lambda l: 'not applicable in {self._juris}"' in l and l.strip().startswith("label = "))
if len(h) == 1:
    ct.edits.append((h[0], h[0], ct.blk(h[0],
        'label = (f"{label} \\u2014 S41 research only, not a Key Species status"\n'
        '         if "research" in label.lower() else\n'
        '         f"{label} \\u2014 not applicable in {self._juris}")')))
else:
    problems.append(f"conservation_tab: grey label line x{len(h)}")

for f in (cr, wb, ct):
    print(f"  {os.path.relpath(f.path, ROOT):<42} edits planned: {len(f.edits)}")
if problems:
    for p in problems:
        print(f"  x {p}")
    sys.exit("\nABORTED -- nothing written.")

print("\n  BEFORE -- key species per survey:")
before = run(PROBE)
print("    " + before.replace("\n", "\n    "))

for f in (cr, wb, ct):
    f.write()
try:
    for f in (cr, wb, ct):
        py_compile.compile(f.path, doraise=True)
    sys.path[:0] = [ROOT, os.path.join(ROOT, "Observatum")]
    importlib.import_module("shared.repositories.codex_repository")
    importlib.import_module("Examen.workbook_export")
    print("\n  ok written; all three compile; codex_repository and workbook_export import")
except Exception as e:
    for f in (cr, wb, ct):
        f.restore()
    sys.exit(f"  x FAILED ({type(e).__name__}: {e}) -- all three restored")

print("\n  AFTER -- key species per survey:")
after = run(PROBE_AFTER)
print("    " + after.replace("\n", "\n    "))
print("\nBackups: *.bak_research. Wall and Small Heath should stay key (Pantheon")
print("removed them from the research-only list); Cinnabar and Latticed Heath should not.")
