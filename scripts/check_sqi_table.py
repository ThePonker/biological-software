"""SQI for every survey, on both bases -- save before a change, compare after.
READ ONLY on the databases.

  python scripts\\check_sqi_table.py                       print
  python scripts\\check_sqi_table.py --save sqi_before.txt  print and save
  python scripts\\check_sqi_table.py --compare sqi_before.txt  print beside saved
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "Observatum")]

from shared.repositories.pantheon_repository import PantheonRepository
from shared.repositories.codex_repository import CodexRepository
from shared.services.pantheon_analysis_service import PantheonAnalysisService
from Examen import examen_data as ed

svc = PantheonAnalysisService(PantheonRepository(), CodexRepository())
rows = {}
for p in ed.load_all_projects():
    d = ed.load_project_detail(p.project_name, p.client, survey_year=p.survey_year or None)
    if not d:
        continue
    # Every TVK recorded: a species recorded as s.l. and s.s. is merged by the
    # analysis, which needs both TVKs to do it (EXA14).
    tvks = getattr(d, "recorded_tvks", None) or [s.tvk for s in d.species_list if s.tvk]
    r = svc.analyse(tvks)
    o = r.overall_sqi
    pub = getattr(r, "overall_sqi_published", None) or o
    rows[f"{p.project_name} {p.survey_year}"] = [
        r.total_species, o.species_with_sqs, o.sqi, pub.species_with_sqs, pub.sqi,
        p.key_species_count]

old = {}
if "--compare" in sys.argv:
    with open(sys.argv[sys.argv.index("--compare") + 1]) as f:
        old = json.load(f)

print(f"{'Survey':34} {'spp':>4} {'key':>4}  {'scoring':>7} {'SQI':>4}  {'Pantheon-only':>13}"
      + ("   <- before: key scoring  SQI  Pan-only" if old else ""))
for k in sorted(rows):
    n, ns, sqi, np_, ps, key = rows[k]
    line = f"{k[:34]:34} {n:>4} {key:>4}  {ns:>7} {sqi:>4}  {np_:>7} {ps:>5}"
    if k in old:
        o = old[k]
        okey = o[5] if len(o) > 5 else "-"
        line += f"   <- {okey:>3} {o[1]:>7} {o[2]:>4}  {o[4]:>5}"
        if okey != "-" and okey != key:
            line += "   KEY CHANGED"
    print(line)

if "--save" in sys.argv:
    out = sys.argv[sys.argv.index("--save") + 1]
    with open(out, "w") as f:
        json.dump(rows, f, indent=1)
    print(f"\nsaved: {out}")
print("\nREAD ONLY -- nothing in the databases has been changed.")
