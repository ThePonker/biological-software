import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3, paths
c = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
print(f'{"site":24} {"recs":>6} {"with irecord_id":>16} {"record_key":>11}')
for s, n, ir, rk in c.execute("""
        SELECT site_name, COUNT(1),
               SUM(CASE WHEN irecord_id IS NOT NULL AND irecord_id != '' THEN 1 ELSE 0 END),
               SUM(CASE WHEN record_key IS NOT NULL AND record_key != '' THEN 1 ELSE 0 END)
        FROM observations
        WHERE LOWER(COALESCE(project_name,'')) LIKE '%bicester%'
        GROUP BY 1 ORDER BY 2 DESC"""):
    print(f'{str(s):24} {n:>6} {ir or 0:>16} {rk or 0:>11}')
print()
print("embargo / commercial flags:")
for r in c.execute("""SELECT COALESCE(embargo_until,'(none)'), COUNT(1)
                      FROM observations
                      WHERE LOWER(COALESCE(project_name,'')) LIKE '%bicester%'
                      GROUP BY 1"""):
    print("  ", r)
