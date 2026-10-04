"""Why does Chlorops rufinus still show RDB K?  And are other old statuses hidden
in threat/rarity rows that carry a status_detail?  READ ONLY.

Every check and clearance on 4 Oct looked only at rows with an EMPTY detail.
"""
import os, sqlite3, sys
from collections import Counter
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import paths

c = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)
u = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)
TR = ("threat_iucn_2001", "threat_iucn_legacy", "rarity_modern", "rarity_legacy")

tvk = u.execute("SELECT tvk FROM taxa WHERE scientific_name='Chlorops rufinus'").fetchone()
print("1. Chlorops rufinus", tvk)
if tvk:
    for r in c.execute("SELECT status_track, status_value, status_detail, source, origin FROM status_summary WHERE tvk=?", tvk):
        print("   status_summary:", r)
    for r in c.execute("SELECT status_track, status_value, added_by, review_id FROM manual_entries WHERE tvk=? ORDER BY id", tvk):
        print("   manual_entries:", r)
    for r in c.execute("SELECT species_name, designation_abbreviation, source FROM designations WHERE tvk=?", tvk):
        print("   designations:  ", r)

print("\n2. Threat/rarity rows WITH a detail (invisible to today's checks):")
rows = c.execute(f"""SELECT status_track, status_value, status_detail, origin FROM status_summary
                     WHERE COALESCE(status_detail,'')!='' AND status_track IN ({','.join('?'*4)})""", TR).fetchall()
print(f"   {len(rows)} rows")
for (tr, d), n in Counter((r[0], r[2]) for r in rows).most_common(15):
    print(f"   {n:>5}  {tr:<20} detail={d!r}")

print("\n3. Species holding the SAME track twice (one blank detail, one not):")
dup = c.execute(f"""SELECT COUNT(1) FROM (SELECT tvk, status_track FROM status_summary
                    WHERE status_track IN ({','.join('?'*4)}) GROUP BY 1,2 HAVING COUNT(1)>1)""", TR).fetchone()[0]
print(f"   {dup}")
print("\nREAD ONLY")
