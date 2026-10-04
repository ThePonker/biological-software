"""Which reviews are worth loading species accounts from?  READ ONLY.

1. Runs the full assessment for every survey and collects the KEY species --
   the ones whose accounts go in a report.
2. For each key species: does an account exist already (yours, or a loaded
   review's)? If not, which is the most recent REVIEW behind its status
   (legislation and priority lists are skipped -- they have no accounts)?
3. Ranks reviews by how many key species without an account they would fill,
   then by how many species in all your records they cover.

Run:  python scripts\\rank_reviews_for_accounts.py
"""
import os, re, sqlite3, sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "Observatum")]
import paths
from shared.repositories.pantheon_repository import PantheonRepository
from shared.repositories.codex_repository import CodexRepository
from shared.services.pantheon_analysis_service import PantheonAnalysisService
from shared.species_accounts import get_species_accounts
from Examen import examen_data as ed

NOT_A_REVIEW = re.compile(r"act\b|regulations|directive|convention|biodiversity list|priority|"
                          r"schedule|cites|ospar|iucn red list of threatened|wildlife \(northern ireland\)|"
                          r"wildlife and countryside", re.I)

print("Reviews ranked by key species they would give an account to   READ ONLY")
print("=" * 96)

# 1. key species across every survey
svc = PantheonAnalysisService(PantheonRepository(), CodexRepository())
key = defaultdict(set)                  # tvk -> {survey, ...}
names = {}
for p in ed.load_all_projects():
    d = ed.load_project_detail(p.project_name, p.client, survey_year=p.survey_year or None)
    if not d:
        continue
    r = svc.analyse([s.tvk for s in d.species_list if s.tvk])
    for k in r.key_species:
        if k.tvk:
            key[k.tvk].add(f"{p.project_name} {p.survey_year}".strip())
            names[k.tvk] = k.species_name
print(f"  key species across all surveys: {len(key)}")

# 2. accounts held, and most recent review per species
have = {t for t in key if get_species_accounts(t).has_any}
codex = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)
obs = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
mine = {t for (t,) in obs.execute("SELECT DISTINCT species_tvk FROM assessment_records WHERE species_tvk IS NOT NULL")}
mine |= {t for (t,) in obs.execute("SELECT DISTINCT species_tvk FROM specimens WHERE species_tvk IS NOT NULL")}


def reviews_for(tvk):
    rows = codex.execute("""SELECT DISTINCT source, substr(COALESCE(date_designated,''),1,10)
                            FROM designations WHERE tvk=?""", (tvk,)).fetchall()
    rows += codex.execute("""SELECT r.review_name || ' (' || COALESCE(r.author,'') || ')', substr(r.date_published,1,10)
                             FROM manual_entries m JOIN reviews r ON r.id=m.review_id
                             WHERE m.tvk=? GROUP BY r.id""", (tvk,)).fetchall()
    return sorted({(s, d) for s, d in rows if s and not NOT_A_REVIEW.search(s)}, key=lambda x: x[1], reverse=True)


fill = defaultdict(list)                # review -> [key species it would fill]
nothing = []
latest_date = {}
for t in key:
    if t in have:
        continue
    rv = reviews_for(t)
    if rv:
        src, d = rv[0]
        fill[src].append(t)
        latest_date[src] = d
    else:
        nothing.append(t)

# breadth: species in your records whose most recent review is each source
breadth = defaultdict(int)
for t in mine:
    rv = reviews_for(t)
    if rv:
        breadth[rv[0][0]] += 1

print(f"  with an account already: {len(have)}   without: {len(key) - len(have)}"
      f"   of those, no review behind their status: {len(nothing)}\n")
print(f"  {'fills':>5} {'your spp':>8}  {'date':10}  review")
for src, ts in sorted(fill.items(), key=lambda kv: (-len(kv[1]), -breadth[kv[0]])):
    print(f"  {len(ts):>5} {breadth[src]:>8}  {latest_date[src] or '':10}  {src[:72]}")
    print(f"  {'':27}e.g. {', '.join(sorted(names[t] for t in ts)[:4])[:66]}")
if nothing:
    print(f"\n  Key species with no review behind their status (priority/legal only, or unbridged):")
    print("    " + ", ".join(sorted(names[t] for t in nothing))[:300])
print("\n  'fills' = key species without an account whose most recent review this is.")
print("  'your spp' = species in all your records whose most recent review this is.")
print("\nREAD ONLY -- nothing has been changed.")
