import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3, paths

c = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)

print("20 most recently added specimens:")
print(f'{"id":>5} {"added":19} {"species":30} {"sort key":>11} {"sf":>3}')
for sid, created, name, key, sf in c.execute("""
        SELECT id, COALESCE(created_at,''), COALESCE(species_name,''),
               taxonomic_sort_key, COALESCE(superfamily,'')
        FROM specimens ORDER BY id DESC LIMIT 20"""):
    flag = "  <-- INVISIBLE" if key is None else ""
    print(f"{sid:>5} {created[:19]:19} {name[:30]:30} "
          f"{str(key) if key is not None else 'NONE':>11} {'y' if sf else '-':>3}{flag}")

n = c.execute("SELECT COUNT(1) FROM specimens "
              "WHERE taxonomic_sort_key IS NULL").fetchone()[0]
print()
print(f"total with no sort key: {n}   (2 expected -- the TVK-less longhorns)")
