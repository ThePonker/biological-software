import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3, paths
c = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
print(f'{"id":>3} {"status":10} {"rows":>6}  name | project | client')
for r in c.execute("SELECT id, name, status, project, client FROM entry_jobs ORDER BY id"):
    n = c.execute("SELECT COUNT(1) FROM entry_staging WHERE job_id=?", (r[0],)).fetchone()[0]
    print(f'{r[0]:>3} {str(r[2]):10} {n:>6}  {r[1]} | {r[3] or ""} | {r[4] or ""}')
