import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3, paths
c = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
print("vc columns on observations:",
      [r[1] for r in c.execute("PRAGMA table_info(observations)") if "vc" in r[1].lower() or "vice" in r[1].lower()])
print()
print("Glory Park 2024, vc_number values:")
for v, n in c.execute("""SELECT vc_number, COUNT(1) FROM observations
        WHERE record_type='Commercial' AND project_name LIKE '%Glory Park%'
          AND substr(date,1,4)='2024' GROUP BY 1"""):
    print(f"   {v!r:>12}  x{n}   type={type(v).__name__}")
print()
print("vice_county values:")
for v, n in c.execute("""SELECT vice_county, COUNT(1) FROM observations
        WHERE record_type='Commercial' AND project_name LIKE '%Glory Park%'
        GROUP BY 1"""):
    print(f"   {v!r:>20}  x{n}")
