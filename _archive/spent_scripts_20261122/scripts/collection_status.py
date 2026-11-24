import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3, paths
c = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)

total = c.execute("SELECT COUNT(1) FROM specimens").fetchone()[0]
recent = c.execute("SELECT COUNT(1) FROM specimens "
                   "WHERE created_at >= '2026-09-13'").fetchone()[0]
print(f"specimens: {total}   added since 13 Sept: {recent}")
print()
print("curatorial fields filled, whole collection:")
for label, col in (("Sex", "sex"), ("Preparation", "preparation_type"),
                   ("Condition", "condition"), ("Storage", "storage_location"),
                   ("Drawer", "drawer_number")):
    n = c.execute(f"SELECT COUNT(1) FROM specimens "
                  f"WHERE TRIM(COALESCE({col},'')) != ''").fetchone()[0]
    print(f"  {label:12} {n:>5} of {total}  ({n / total * 100:.0f}%)")
