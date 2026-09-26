import os, sys
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import sqlite3
import paths

c = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)

print("priority: distinct status_value")
for v, n in c.execute("""SELECT status_value, COUNT(*) FROM status_summary
                         WHERE status_track='priority' GROUP BY 1 ORDER BY 2 DESC"""):
    print(f"  {v!r:50} {n}")

print("")
print("priority: status_detail populated?")
for v, n in c.execute("""SELECT COALESCE(status_detail,'(null)'), COUNT(*)
                         FROM status_summary WHERE status_track='priority'
                         GROUP BY 1 ORDER BY 2 DESC LIMIT 10"""):
    print(f"  {v!r:50} {n}")

print("")
print("Cinnabar (Tyria jacobaeae) - all tracks")
tvk = c.execute("SELECT tvk FROM designations WHERE species_name='Tyria jacobaeae' LIMIT 1").fetchone()
if tvk:
    print("  tvk:", tvk[0])
    for r in c.execute("""SELECT status_track, status_value, status_detail, source
                          FROM status_summary WHERE tvk=?""", (tvk[0],)):
        print("  ", r)
    print("")
    print("  raw designations rows:")
    for r in c.execute("""SELECT designation_abbreviation, designation, source
                          FROM designations WHERE tvk=?""", (tvk[0],)):
        print("  ", r)
else:
    print("  not found in designations")
