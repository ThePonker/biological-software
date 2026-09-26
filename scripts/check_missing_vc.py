import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3, paths
c = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
q = """SELECT record_type, COUNT(1),
         SUM(CASE WHEN COALESCE(TRIM(CAST(vc_number AS TEXT)),'')='' THEN 1 ELSE 0 END),
         SUM(CASE WHEN COALESCE(TRIM(CAST(vc_number AS TEXT)),'')=''
                   AND COALESCE(TRIM(grid_ref),'')!='' THEN 1 ELSE 0 END)
       FROM observations GROUP BY 1"""
print(f"{'type':12} {'records':>8} {'no VC':>8} {'no VC, has grid ref':>20}")
for t, n, novc, fix in c.execute(q):
    print(f"{str(t):12} {n:>8} {novc:>8} {fix:>20}")
print()
print("commercial projects with no VC on any record:")
for p, y, n in c.execute("""SELECT project_name, substr(date,1,4), COUNT(1) FROM observations
        WHERE record_type='Commercial' GROUP BY 1,2
        HAVING SUM(CASE WHEN COALESCE(TRIM(CAST(vc_number AS TEXT)),'')!='' THEN 1 ELSE 0 END)=0
        ORDER BY 1"""):
    print(f"   {str(p)[:34]:34} {y}  {n:>5} records")
print()
print("specimens with no VC:", c.execute("""SELECT COUNT(1) FROM specimens
        WHERE COALESCE(TRIM(CAST(vc_number AS TEXT)),'')=''""").fetchone()[0], "of",
      c.execute("SELECT COUNT(1) FROM specimens").fetchone()[0])
