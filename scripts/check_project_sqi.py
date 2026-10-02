"""One project's SQI in the form a report gives it -- to compare with an issued
report. READ ONLY.

  python scripts\\check_project_sqi.py "BAM Glory Park" 2024

Prints: overall SQI (both bases), biotope and habitat SQIs with species
counts, and every species WITHOUT a Pantheon score -- split into derived,
in-Pantheon-but-unscored, and absent -- so a difference from the report can be
traced to particular species.
"""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "Observatum")]
from shared.repositories.pantheon_repository import PantheonRepository
from shared.repositories.codex_repository import CodexRepository
from shared.services.pantheon_analysis_service import PantheonAnalysisService
from Examen import examen_data as ed

project = sys.argv[1] if len(sys.argv) > 1 else "BAM Glory Park"
year = sys.argv[2] if len(sys.argv) > 2 else None

d = ed.load_project_detail(project, "", survey_year=year)
if not d:
    sys.exit(f"no project {project!r} {year}")
names = {s.tvk: s.name for s in d.species_list if s.tvk}
codex = CodexRepository()
r = PantheonAnalysisService(PantheonRepository(), codex).analyse(list(names))
o, p = r.overall_sqi, getattr(r, "overall_sqi_published", None) or r.overall_sqi

print(f"{project} {year or ''}  --  READ ONLY")
print("=" * 72)
print(f"  species {r.total_species}   in Pantheon {r.species_in_pantheon}")
print(f"  SQI                {o.sqi:>4}  from {o.species_with_sqs} scoring (sum {o.sqs_sum})")
print(f"  SQI Pantheon only  {p.sqi:>4}  from {p.species_with_sqs} scoring (sum {p.sqs_sum})")

print("\n  Biotope / habitat     species  scoring  SQI")
bsq = {s.label: s for s in r.biotope_sqi}
for bio in sorted(r.biotope_counts, key=lambda b: -r.biotope_counts[b]):
    s = bsq.get(bio)
    print(f"  {bio:<28} {r.biotope_counts[bio]:>5} {s.species_with_sqs if s else '':>8} {s.sqi if s else '':>5}")
    for hab, hs in sorted((r.biotope_habitat_sqi.get(bio) or {}).items(),
                          key=lambda kv: -kv[1].species_total):
        print(f"    {hab:<26} {hs.species_total:>5} {hs.species_with_sqs:>8} {hs.sqi:>5}")

stored = codex.get_stored_sqs_tvks(list(names))
scores = codex.get_sqs_scores(list(names))
derived = sorted(names[t] for t in names if t in scores and t not in stored)
noscore = [t for t in names if t not in scores]
nopan = getattr(r, "no_pantheon_tvks", set())
print(f"\n  derived (not Pantheon's): {derived or 'none'}")
print(f"  no score, in Pantheon: {sorted(names[t] for t in noscore if t not in nopan) or 'none'}")
print(f"  no score, no Pantheon data: {sorted(names[t] for t in noscore if t in nopan) or 'none'}")
print("\nREAD ONLY -- nothing has been changed.")
