import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3, paths

p = sqlite3.connect(f"file:{paths.PANTHEON_DB}?mode=ro", uri=True)
names = ["Hylaeus euryscapus", "Hylaeus masoni",
         "Hylaeus spilotus", "Hylaeus annularis"]

for n in names:
    row = p.execute("SELECT tvk FROM species WHERE species_name=?", (n,)).fetchone()
    if not row:
        print(f"--- {n} --- NOT FOUND")
        continue
    t = row[0]
    sqs = p.execute("SELECT sqs FROM sqs_scores WHERE tvk=?", (t,)).fetchone()
    print("")
    print(f"--- {n}  ({t}) ---")
    print("  sqs:     ", sqs[0] if sqs else "none")
    print("  habitats:", [r[0] for r in p.execute(
        "SELECT DISTINCT habitat FROM habitats WHERE tvk=?", (t,))])
    print("  guilds:  ", [f"{r[0]}:{r[1]}" for r in p.execute(
        "SELECT life_stage, guild FROM feeding_guilds WHERE tvk=?", (t,))])
    print("  sats:    ", [r[0] for r in p.execute(
        "SELECT DISTINCT sat_name FROM specific_assemblage_types WHERE tvk=?", (t,))])
    print("  status:  ", [(r[0], r[1]) for r in p.execute(
        "SELECT reporting_category, abbreviation FROM conservation_status WHERE tvk=?", (t,))])
