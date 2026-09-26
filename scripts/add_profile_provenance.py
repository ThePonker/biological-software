import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3, paths

c = sqlite3.connect(str(paths.OBSERVATUM_DB))
cols = [r[1] for r in c.execute("PRAGMA table_info(species_profiles)")]

# origin: 'own' | 'review' | 'edited'  -- how the account came to exist.
# A profile seeded from a published review is quotable and attributable; one
# Wil wrote is professional opinion; an edited one is neither cleanly. Reports
# cite reviews by name, so the distinction has to survive.
for name, ddl in [
        ("origin",        "TEXT DEFAULT 'own'"),
        ("source_review", "TEXT"),
        ("source_year",   "INTEGER")]:
    if name not in cols:
        c.execute(f"ALTER TABLE species_profiles ADD COLUMN {name} {ddl}")
        print("added:", name)
    else:
        print("already present:", name)
c.commit()
print([r[1] for r in c.execute("PRAGMA table_info(species_profiles)")])
