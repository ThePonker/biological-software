"""SQI: divide by every species analysed -- Pantheon's own definition.

Examen divided the sum of SQS by the number of species WITH a score. Pantheon
divides by every species it analysed, scored or not (an unscored species counts
0). Glory Park proves it: 144 / 120 = 120 (Examen) but 144 / 123 x 100 = 117.07,
the issued report's figure exactly. The report's method says the same.

  pantheon_analysis_service.py
    SQIResult + species_analysed; calculate() divides by it (falls back to
      scoring species where no pool is known). Reliability still counts
      scoring species (Pantheon's caution below 15).
    _calc_sqi(..., pool=None): species_analysed = the group's species that are
      in the pool or scored. Default pool set per analyse() run.
    analyse(): pool = scored or carrying Pantheon ecology; the Pantheon-only
      SQI uses the pool without derived scores.

Prints Glory Park and Birmingham before and after. Writes NOTHING unless every
anchor is found exactly once. Backup: .bak_sqidenom.

Run:  python scripts\\patch_sqi_denominator.py
"""
import ast, importlib, io, os, py_compile, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "shared", "services", "pantheon_analysis_service.py")

PROBE = r'''
import sys, os
R = __ROOT__
sys.path[:0] = [R, os.path.join(R, "Observatum")]
from shared.repositories.pantheon_repository import PantheonRepository
from shared.repositories.codex_repository import CodexRepository
from shared.services.pantheon_analysis_service import PantheonAnalysisService
from Examen import examen_data as ed
svc = PantheonAnalysisService(PantheonRepository(), CodexRepository())
for proj, yr in (("BAM Glory Park", "2024"), ("Birmingham - Wheels Park", "2026")):
    d = ed.load_project_detail(proj, "", survey_year=yr)
    r = svc.analyse([s.tvk for s in d.species_list if s.tvk])
    o = r.overall_sqi
    p = getattr(r, "overall_sqi_published", None) or o
    print(f"{proj[:26]:26} SQI {o.sqi:>4} (sum {o.sqs_sum} / {getattr(o, 'species_analysed', 0) or o.species_with_sqs})"
          f"   Pantheon-only {p.sqi:>4} (sum {p.sqs_sum} / {getattr(p, 'species_analysed', 0) or p.species_with_sqs})")
    for s in r.biotope_sqi:
        if s.label == "open habitats":
            print(f"{'':26} open habitats {s.sqi}")
'''.replace("__ROOT__", repr(ROOT))


def probe():
    r = subprocess.run([sys.executable, "-c", PROBE], capture_output=True, text=True, cwd=ROOT)
    return "    " + (r.stdout + (r.stderr[-800:] if r.returncode else "")).strip().replace("\n", "\n    ")


raw = io.open(P, "rb").read()
bom = raw.startswith(b"\xef\xbb\xbf")
lines = raw.decode("utf-8-sig").split("\n")
tree = ast.parse("\n".join(l.rstrip("\r") for l in lines))
print("SQI denominator -- every species analysed")
print("=" * 76)
if any("species_analysed" in l for l in lines):
    sys.exit("  already patched -- nothing written")


def node(name):
    h = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name == name]
    return h[0] if len(h) == 1 else None


def find(n, s):
    return [i for i in range(n.lineno - 1, n.end_lineno) if lines[i].strip().rstrip("\r") == s]


def blk(i, body):
    s = lines[i].rstrip("\r")
    ind = s[:len(s) - len(s.lstrip())]
    e = "\r" if lines[i].endswith("\r") else ""
    return [(ind + b if b else "") + e for b in body.split("\n")]


edits, problems = [], []
sq, cs, an = node("SQIResult"), node("_calc_sqi"), node("analyse")
for nm, n in (("SQIResult", sq), ("_calc_sqi", cs), ("analyse", an)):
    if n is None:
        problems.append(f"{nm} not found exactly once")
if not problems:
    for nm, n, s in (
            ("SQIResult reliable field", sq, "reliable: bool = True"),
            ("SQIResult sqi line", sq, "self.sqi = round(self.sqs_sum / self.species_with_sqs * 100)"),
            ("_calc_sqi def", cs, "def _calc_sqi(self, label, tvks_or_set, sqs_scores):"),
            ("_calc_sqi species_total", cs, "sqi.species_total = len(tvk_set)"),
            ("analyse derived assign", an, "result.derived_sqs_tvks = derived"),
            ("analyse published dict", an, "{t: s for t, s in sqs_scores.items() if t not in derived})")):
        h = find(n, s)
        print(f"  {nm:<28} x{len(h)}")
        if len(h) != 1:
            problems.append(f"{nm}: x{len(h)}")
        else:
            i = h[0]
            if nm == "SQIResult reliable field":
                edits.append((i, [lines[i]] + blk(i, "species_analysed: int = 0     # Pantheon's denominator")))
            elif nm == "SQIResult sqi line":
                edits.append((i, blk(i, "# Pantheon's definition: divide by every species analysed, scored\n"
                                        "# or not (Glory Park: 144 / 123 = 117, the issued report).\n"
                                        "_denom = self.species_analysed or self.species_with_sqs\n"
                                        "self.sqi = round(self.sqs_sum / _denom * 100)")))
            elif nm == "_calc_sqi def":
                edits.append((i, [lines[i].replace("sqs_scores):", "sqs_scores, pool=None):")]))
            elif nm == "_calc_sqi species_total":
                edits.append((i, [lines[i]] + blk(i,
                    'pool = pool if pool is not None else getattr(self, "_sqi_pool", None)\n'
                    "if pool is not None:\n"
                    "    sqi.species_analysed = len({t for t in tvk_set if t in pool or t in sqs_scores})")))
            elif nm == "analyse derived assign":
                edits.append((i, [lines[i]] + blk(i,
                    "# SQI denominator (Pantheon's definition): every species analysed --\n"
                    "# scored, or in Pantheon with ecology but no score (counts 0).\n"
                    "self._sqi_pool = set(sqs_scores) | set(biotopes) | set(habitats)")))
            elif nm == "analyse published dict":
                edits.append((i, [lines[i].replace("if t not in derived})",
                                                   "if t not in derived},")] +
                              blk(i, "pool=(set(sqs_scores) - derived) | set(biotopes) | set(habitats))")))

if problems:
    for p in problems:
        print(f"  x {p}")
    sys.exit("\nABORTED -- nothing written.")

print("\n  BEFORE:")
print(probe())

for i, new in sorted(edits, key=lambda t: -t[0]):
    lines[i:i + 1] = new
shutil.copy2(P, P + ".bak_sqidenom")
io.open(P, "w", encoding="utf-8-sig" if bom else "utf-8", newline="").write("\n".join(lines))
try:
    py_compile.compile(P, doraise=True)
    sys.path[:0] = [ROOT, os.path.join(ROOT, "Observatum")]
    importlib.import_module("shared.services.pantheon_analysis_service")
    print("\n  ok written, compiles, imports (backup: .bak_sqidenom)")
except Exception as e:
    shutil.copy2(P + ".bak_sqidenom", P)
    sys.exit(f"  x FAILED ({type(e).__name__}: {e}) -- restored")

print("\n  AFTER:")
print(probe())
print("\nGlory Park Pantheon-only should now read 117 (sum 144 / 123) -- the issued report.")
