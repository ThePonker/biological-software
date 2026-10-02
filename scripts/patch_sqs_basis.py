"""SQS basis made visible: Pantheon-published vs derived, both SQIs reported.

Fault: get_sqs_scores returns Pantheon's stored score, else one derived live
from the published rule, in one dict with no marker. The SQI mixed them while
the stamp said "SQS basis: Pantheon published". Birmingham: Cistogaster globosa
(RDB1, absent from Pantheon) derived 16; SQI 146 with it, 128 without.
Also: "Analysed by Pantheon" counted any scored species, derived included.

  codex_repository.py   + get_stored_sqs_tvks(tvks): stored (not derived) scores
  pantheon_analysis_service.py
      AnalysisResult + derived_sqs_tvks, overall_sqi_published, no_pantheon_tvks
      analyse(): records derived scores; SQI on Pantheon scores only;
                 species_in_pantheon excludes derived-only species
  workbook_export.py
      Summary: both SQIs, derived species named; SQS basis states the mix
      species sheets: "16 (derived)"; "no Pantheon data" for blank ecology
      Status definitions: "(derived)" explained

Roadmap decision 7: compute both bases, state which was used.

All three files planned first; NOTHING written unless every anchor is found
exactly once. Backups *.bak_sqsbasis; all restored on any compile/import
failure. Then Birmingham's figures are printed from the real service.

Run:  python scripts\\patch_sqs_basis.py
"""
import ast, importlib, io, os, py_compile, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CR = os.path.join(ROOT, "shared", "repositories", "codex_repository.py")
SV = os.path.join(ROOT, "shared", "services", "pantheon_analysis_service.py")
WB = os.path.join(ROOT, "Examen", "workbook_export.py")


class F:
    def __init__(self, path):
        self.path = path
        raw = io.open(path, "rb").read()
        self.bom = raw.startswith(b"\xef\xbb\xbf")
        self.lines = raw.decode("utf-8-sig").split("\n")
        self.tree = ast.parse("\n".join(l.rstrip("\r") for l in self.lines))
        self.edits = []

    def node(self, name, kind=(ast.FunctionDef, ast.ClassDef)):
        h = [n for n in ast.walk(self.tree) if isinstance(n, kind) and n.name == name]
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
        shutil.copy2(self.path, self.path + ".bak_sqsbasis")
        io.open(self.path, "w", encoding="utf-8-sig" if self.bom else "utf-8",
                newline="").write("\n".join(self.lines))

    def restore(self):
        shutil.copy2(self.path + ".bak_sqsbasis", self.path)


problems = []


def need(c, m):
    if not c:
        problems.append(m)
    return c


print("SQS basis -- Pantheon-published vs derived")
print("=" * 76)
cr, sv, wb = F(CR), F(SV), F(WB)
for f in (cr, sv, wb):
    if "get_stored_sqs_tvks" in "\n".join(f.lines) or "_mark_derived" in "\n".join(f.lines):
        sys.exit(f"  {os.path.basename(f.path)} already patched -- nothing written")

# ---------------------------------------------------------------- codex_repository
d = cr.node("_derive_sqs_batch")
if need(d is not None, "codex: _derive_sqs_batch not found"):
    i = d.lineno - 1
    cr.edits.append((i, i, cr.blk(i, '''def get_stored_sqs_tvks(self, tvks):
    """TVKs whose SQS is STORED -- Pantheon's published score or a manual entry --
    as opposed to derived live from the rule by get_sqs_scores."""
    out = set()
    if not tvks:
        return out
    c = self._get_conn().cursor()
    for batch in _chunked(list(tvks), 500):
        ph = ",".join("?" * len(batch))
        c.execute(f"SELECT tvk FROM sqs_scores WHERE tvk IN ({ph}) AND source != 'derived'", batch)
        out.update(r[0] for r in c.fetchall())
    return out
''') + [cr.lines[i]]))

# ---------------------------------------------------------------- analysis service
ar = sv.node("AnalysisResult", ast.ClassDef)
if need(ar is not None, "service: class AnalysisResult not found"):
    fields = [n for n in ar.body if isinstance(n, ast.AnnAssign)]
    if need(fields, "service: AnalysisResult has no fields"):
        i = fields[-1].end_lineno - 1
        sv.edits.append((i, i, [sv.lines[i]] + sv.blk(i, '''# SQS basis (patch_sqs_basis.py): which scores were derived from the rule
# rather than published by Pantheon, the SQI on Pantheon's scores alone, and
# species Pantheon holds no data for at all.
derived_sqs_tvks: set = field(default_factory=set)
overall_sqi_published: object = None
no_pantheon_tvks: set = field(default_factory=set)''')))
an = sv.node("analyse")
if need(an is not None, "service: analyse() not found"):
    h = sv.find(an, lambda l: l.strip() == "result.species_with_sqs = len(sqs_scores)")
    if need(len(h) == 1, f"service: species_with_sqs line x{len(h)}"):
        i = h[0]
        sv.edits.append((i, i, [sv.lines[i]] + sv.blk(i, '''
# Which scores Pantheon published, which were derived from the rule (Codex
# Full gap-fill). Both bases are reported; neither is hidden. (Decision 7.)
derived = set()
if self._codex is not None and hasattr(self._codex, "get_stored_sqs_tvks") \\
        and mode != AnalysisMode.PANTHEON_ONLY:
    derived = set(sqs_scores) - self._codex.get_stored_sqs_tvks(unique_tvks)
result.derived_sqs_tvks = derived
result.overall_sqi_published = self._calc_sqi(
    "Overall (Pantheon scores)", unique_tvks,
    {t: s for t, s in sqs_scores.items() if t not in derived})
# A derived score is not Pantheon data: such a species is not "in Pantheon".
result.species_in_pantheon = len((set(sqs_scores) - derived) | set(biotopes.keys()))
result.no_pantheon_tvks = set(unique_tvks) - (
    (set(sqs_scores) - derived) | set(biotopes) | set(habitats))''')))

# ---------------------------------------------------------------- workbook
ss = wb.node("_sheet_summary")
if need(ss is not None, "workbook: _sheet_summary not found"):
    h = wb.find(ss, lambda l: l.strip() == "for label, value, note in rows:")
    if need(len(h) == 1, f"workbook: rows loop x{len(h)}"):
        i = h[0]
        wb.edits.append((i, i, wb.blk(i, '''# Both SQS bases, when any score was derived (patch_sqs_basis.py).
_der = getattr(result, "derived_sqs_tvks", set()) or set()
_pub = getattr(result, "overall_sqi_published", None)
if _der and _pub is not None:
    _nm = {s.tvk: s.name for s in (getattr(detail, "species_list", None) or []) if s.tvk}
    _names = ", ".join(sorted(_nm.get(t, t) for t in _der))
    _i = next(n for n, row in enumerate(rows) if row[0] == "Species Quality Index (SQI)")
    rows[_i] = ("Species Quality Index (SQI)", _sqi_cell(result.overall_sqi),
                f"From {_sqi_n(result.overall_sqi)} scoring species, including "
                f"{len(_der)} scored from current status by Pantheon's published "
                f"rule because Pantheon holds no score ({_names}).")
    rows.insert(_i + 1, ("SQI on Pantheon scores only", _sqi_cell(_pub),
                f"From {_sqi_n(_pub)} species with a score Pantheon published. "
                "Comparable with the Pantheon website and the literature."))
''') + [wb.lines[i]]))
    h = wb.find(ss, lambda l: l.strip() == 'for label, value in stamp["basis"]:')
    if need(len(h) == 1, f"workbook: stamp loop x{len(h)}"):
        i = h[0]
        wb.edits.append((i, i, [wb.lines[i]] + wb.blk(i, '''    if label == "SQS basis" and _der:
        value = f"Pantheon published, plus {len(_der)} derived (both SQIs above)"''')))
ew = wb.node("export_workbook")
if need(ew is not None, "workbook: export_workbook not found"):
    args = [a.arg for a in ew.args.args]
    h = wb.find(ew, lambda l: l.strip().startswith("wb.save("))
    if need(len(h) == 1, f"workbook: wb.save( in export_workbook x{len(h)}") and \
            need(len(args) >= 2, f"workbook: export_workbook args {args}"):
        i = h[0]
        wb.edits.append((i, i, wb.blk(i, f"_mark_derived(wb, {args[0]}, {args[1]})") + [wb.lines[i]]))
    j = ew.lineno - 1
    wb.edits.append((j, j, wb.blk(j, '''def _mark_derived(wb, result, detail):
    """On the species sheets: "16 (derived)" for a score derived from the rule,
    and "no Pantheon data" where Pantheon holds nothing for the species."""
    derived = getattr(result, "derived_sqs_tvks", set()) or set()
    nopan = getattr(result, "no_pantheon_tvks", set()) or set()
    if not (derived or nopan) or detail is None:
        return
    by_name = {s.name: s.tvk for s in (getattr(detail, "species_list", None) or []) if s.tvk}
    for title in ("Key species", "Species appendix"):
        if title not in wb.sheetnames:
            continue
        ws = wb[title]
        head = None
        for row in ws.iter_rows(min_row=1, max_row=12):
            vals = [c.value for c in row]
            if "Species" in vals and "SQS" in vals:
                head = (row[0].row, vals.index("Species") + 1, vals.index("SQS") + 1,
                        vals.index("Broad biotope") + 1 if "Broad biotope" in vals else None)
                break
        if not head:
            continue
        hr, c_sp, c_sqs, c_bio = head
        for r in range(hr + 1, ws.max_row + 1):
            tvk = by_name.get(ws.cell(r, c_sp).value)
            if not tvk:
                continue
            cell = ws.cell(r, c_sqs)
            if tvk in derived and cell.value not in (None, ""):
                cell.value = f"{cell.value} (derived)"
            if c_bio and tvk in nopan and not ws.cell(r, c_bio).value:
                ws.cell(r, c_bio).value = "no Pantheon data"

''', ind="") + [wb.lines[j]]))
h = wb.find(None, lambda l: l.strip() == '("p prefix (pNS, pNT)", "A provisional status from an unpublished review."),')
if need(len(h) == 1, f"workbook: p prefix definition x{len(h)}"):
    i = h[0]
    wb.edits.append((i, i, [wb.lines[i]] + wb.blk(i, '''("(derived)",
 "A Species Quality Score Pantheon does not hold, derived from the species' "
 "current status by Pantheon's published rule. Included in the SQI; the "
 "Summary also gives the SQI on Pantheon's own scores alone."),''')))

# ---------------------------------------------------------------- write
for f in (cr, sv, wb):
    print(f"  {os.path.relpath(f.path, ROOT):<46} edits planned: {len(f.edits)}")
if problems:
    for p in problems:
        print(f"  x {p}")
    sys.exit("\nABORTED -- nothing written.")
for f in (cr, sv, wb):
    f.write()
try:
    for f in (cr, sv, wb):
        py_compile.compile(f.path, doraise=True)
    sys.path[:0] = [ROOT, os.path.join(ROOT, "Observatum")]
    for m in ("shared.repositories.codex_repository", "shared.services.pantheon_analysis_service",
              "Examen.workbook_export"):
        importlib.import_module(m)
    print("  ok written; all three compile and import (backups: *.bak_sqsbasis)")
except Exception as e:
    for f in (cr, sv, wb):
        f.restore()
    sys.exit(f"  x FAILED ({type(e).__name__}: {e}) -- all three restored")

PROBE = r'''
import sys, os
R = __ROOT__
sys.path[:0] = [R, os.path.join(R, "Observatum")]
from shared.repositories.pantheon_repository import PantheonRepository
from shared.repositories.codex_repository import CodexRepository
from shared.services.pantheon_analysis_service import PantheonAnalysisService
from Examen import examen_data as ed
d = ed.load_project_detail("Birmingham - Wheels Park", "", survey_year="2026")
nm = {s.tvk: s.name for s in d.species_list if s.tvk}
r = PantheonAnalysisService(PantheonRepository(), CodexRepository()).analyse(list(nm))
o, p = r.overall_sqi, r.overall_sqi_published
print(f"SQI (as reported)        {o.sqi:>5}  from {o.species_with_sqs} scoring, sum {o.sqs_sum}")
print(f"SQI (Pantheon scores)    {p.sqi:>5}  from {p.species_with_sqs} scoring, sum {p.sqs_sum}")
print(f"derived scores: {sorted(nm.get(t, t) for t in r.derived_sqs_tvks)}")
print(f"in Pantheon: {r.species_in_pantheon} of {r.total_species}; no Pantheon data: {len(r.no_pantheon_tvks)}")
'''.replace("__ROOT__", repr(ROOT))
p = subprocess.run([sys.executable, "-c", PROBE], capture_output=True, text=True, cwd=ROOT)
print("\n  Birmingham - Wheels Park 2026:")
print("    " + (p.stdout + (p.stderr[-800:] if p.returncode else "")).strip().replace("\n", "\n    "))
print("\nDone. Re-export the Birmingham workbook.")
