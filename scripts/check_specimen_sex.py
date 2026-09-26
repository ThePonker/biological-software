import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3, paths

c = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
print("total specimens:", c.execute("SELECT COUNT(1) FROM specimens").fetchone()[0])
print()
print("sex values as stored:")
for v, n in c.execute("""SELECT COALESCE(NULLIF(TRIM(sex), ''), '(blank)'), COUNT(1)
                         FROM specimens GROUP BY 1 ORDER BY 2 DESC"""):
    print(f"  {n:>6}  {v}")

print()
print("by order, where sex is recorded:")
for o, n, s in c.execute("""SELECT COALESCE(order_name, '(none)'), COUNT(1),
                                   SUM(CASE WHEN TRIM(COALESCE(sex,'')) != ''
                                            THEN 1 ELSE 0 END)
                            FROM specimens GROUP BY 1 ORDER BY 3 DESC LIMIT 12"""):
    pct = f"{s / n * 100:.0f}%" if n else "-"
    print(f"  {o[:28]:28} {s:>5} of {n:>5}  ({pct})")
