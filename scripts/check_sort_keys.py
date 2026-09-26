import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3, paths
c = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)

n = c.execute("SELECT COUNT(1) FROM specimens WHERE taxonomic_sort_key IS NULL").fetchone()[0]
print("specimens with no taxonomic_sort_key:", n, "of 2568")
print()
print("by year added:")
for y, k in c.execute("""SELECT substr(COALESCE(created_at,'?'),1,7), COUNT(1)
                         FROM specimens WHERE taxonomic_sort_key IS NULL
                         GROUP BY 1 ORDER BY 1 DESC LIMIT 12"""):
    print(f"   {y}  {k}")
print()
print("are the sexed ones all in that set?")
print("  sexed with no sort key:", c.execute(
    """SELECT COUNT(1) FROM specimens WHERE taxonomic_sort_key IS NULL
       AND TRIM(COALESCE(sex,'')) != ''""").fetchone()[0])
print("  sexed with a sort key: ", c.execute(
    """SELECT COUNT(1) FROM specimens WHERE taxonomic_sort_key IS NOT NULL
       AND TRIM(COALESCE(sex,'')) != ''""").fetchone()[0])
