"""Record statuses a newer review WITHDREW: species it assessed and judged not to
qualify, but left out of its lists -- so the older status was never replaced.

Rule (4 Oct 2026): for a group, the newest review's verdict stands -- whether it
changes a status, removes one, or excludes a species by judgement. Exclusion by
SCOPE (e.g. NECR234 leaving the Tachinidae for a later volume) does not apply.

NECR234 (Falk & Pont 2017), review #21, excluded four species as "neither scarce
nor threatened enough to be included". Their Shirt 1987 / Falk 1991 statuses are
cleared, recorded against review #21 with the reason, as manual entries so the
withdrawal survives every Codex rebuild (a 'none' value = status removed).

Uses resolve / apply_status / key_tiers / backup / CLEAR from
import_status_review.py -- the same rules as every review load.

DRY RUN by default; --apply to write.

Run:  python scripts\\withdraw_statuses.py
      python scripts\\withdraw_statuses.py --apply
"""
import ast, os, sqlite3, sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "scripts")]
import paths

src = open(os.path.join(ROOT, "scripts", "import_status_review.py"), encoding="utf-8-sig").read()
if not any(isinstance(n, ast.If) and "__main__" in ast.dump(n.test) for n in ast.parse(src).body):
    sys.exit("  x import_status_review.py has no __main__ guard -- not importing it")
from import_status_review import resolve, apply_status, key_tiers, backup, CLEAR

REVIEW_ID = 21
SPECIES = ["Phaonia siebecki", "Phaonia atriceps", "Thricops innocuus", "Sarcophaga africa"]
REASON = ("Excluded by NECR234 (Falk & Pont 2017) as 'neither scarce nor threatened enough "
          "to be included'; earlier Shirt 1987 / Falk 1991 status withdrawn")
TRACKS = ("threat_iucn_2001", "threat_iucn_legacy", "rarity_modern", "rarity_legacy")
APPLY = "--apply" in sys.argv

uksi = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)
codex = sqlite3.connect(str(paths.CODEX_DB))
c = codex.cursor()
rv = c.execute("SELECT review_name, author, date_published FROM reviews WHERE id=?", (REVIEW_ID,)).fetchone()
if not rv:
    sys.exit(f"  x review #{REVIEW_ID} not found")
source = f"{rv[0]} ({rv[1]}, {str(rv[2])[:4]})"
date = str(rv[2])

print("Withdraw statuses -- " + ("APPLY" if APPLY else "DRY RUN"))
print("=" * 78)
print(f"  review #{REVIEW_ID}: {rv[0]}\n  reason: {REASON}\n")
obs = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
plan = []
for name in SPECIES:
    hit = resolve(uksi, name, None)
    if not hit:
        print(f"  x {name}: no UKSI match -- skipped");  continue
    tvk, sci = hit[0], hit[1]
    done = c.execute("""SELECT 1 FROM manual_entries WHERE tvk=? AND review_id=? AND added_by='review-withdrawal'""",
                     (tvk, REVIEW_ID)).fetchone()
    cur = {tr: v for tr, v in c.execute(
        f"SELECT status_track, status_value FROM status_summary WHERE tvk=? AND COALESCE(status_detail,'')='' "
        f"AND status_track IN ({','.join('?' * len(TRACKS))})", (tvk,) + TRACKS)}
    other = [f"{tr}={v}" for tr, v in c.execute(
        f"SELECT status_track, status_value FROM status_summary WHERE tvk=? AND status_track NOT IN "
        f"({','.join('?' * len(TRACKS))})", (tvk,) + TRACKS)]
    n = obs.execute("SELECT COUNT(1) FROM assessment_records WHERE species_tvk=?", (tvk,)).fetchone()[0]
    k0, r0 = key_tiers(cur)
    print(f"  {sci:<24} {tvk}  your records: {n}")
    print(f"      now: {', '.join(f'{t}={v}' for t, v in cur.items()) or 'no threat/rarity status'}"
          f"   key: {'Rare Key' if r0 else 'Key' if k0 else 'no'}")
    if other:
        print(f"      other listings (untouched): {', '.join(other)}")
    if done:
        print("      already withdrawn -- skipped");  continue
    if not cur:
        print("      nothing to clear");  continue
    print(f"      after: no threat/rarity status   key: no")
    plan.append((tvk, sci, list(cur)))
uksi.close(); obs.close()

print(f"\n  {len(plan)} species to clear, {sum(len(p[2]) for p in plan)} status entries")
if not APPLY:
    sys.exit("\n  DRY RUN -- nothing changed. Re-run with --apply.\n")
if not plan:
    sys.exit("  nothing to do")

print(f"  backup: {backup(paths.CODEX_DB, 'codex')}")
now = datetime.now().isoformat()
try:
    for tvk, sci, tracks in plan:
        for tr in tracks:
            c.execute("""INSERT INTO manual_entries (tvk, species_name, status_track, status_value, status_detail,
                         source_review, date_added, added_by, notes, review_id)
                         VALUES (?,?,?,?,NULL,?,?,?,?,?)""",
                      (tvk, sci, tr, CLEAR, source, date, "review-withdrawal", REASON, REVIEW_ID))
            apply_status(c, tvk, tr, CLEAR, None, source, date)
    codex.commit()
except Exception as e:
    codex.rollback()
    sys.exit(f"  x FAILED, rolled back: {type(e).__name__}: {e}")
left = [sci for tvk, sci, _ in plan if c.execute(
    f"SELECT 1 FROM status_summary WHERE tvk=? AND status_track IN ({','.join('?' * len(TRACKS))})",
    (tvk,) + TRACKS).fetchone()]
dup = c.execute("""SELECT COUNT(1) FROM (SELECT tvk, status_track, COALESCE(status_detail,'')
                   FROM status_summary GROUP BY 1,2,3 HAVING COUNT(1) > 1)""").fetchone()[0]
print(f"  withdrawn: {len(plan)} species   still holding a threat/rarity status: {left or 'none'}")
print(f"  verify: duplicated statuses {dup} (should be 0)\n")
codex.close()
