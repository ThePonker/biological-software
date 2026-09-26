import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3, paths

c = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
c.execute("ATTACH ? AS uksi", (str(paths.UKSI_DB),))

print("specimens with a key, against both UKSI columns:")
print(f'{"species":34} {"stored":>11} {"sort_code":>11} {"sort_order":>11}')
for name, stored, code, order in c.execute("""
        SELECT s.species_name, s.taxonomic_sort_key, u.sort_code, u.sort_order
        FROM specimens s JOIN uksi.taxa u ON s.species_tvk = u.tvk
        WHERE s.taxonomic_sort_key IS NOT NULL
        GROUP BY s.species_name LIMIT 8"""):
    print(f"{str(name)[:34]:34} {str(stored):>11} {str(code):>11} {str(order):>11}")

for col in ("sort_code", "sort_order"):
    n = c.execute(f"""SELECT COUNT(1) FROM specimens s JOIN uksi.taxa u
                      ON s.species_tvk = u.tvk
                      WHERE s.taxonomic_sort_key IS NOT NULL
                        AND s.taxonomic_sort_key = u.{col}""").fetchone()[0]
    print(f"\nmatches on {col}: {n}")
