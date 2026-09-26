import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3, paths

c = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
c.execute("ATTACH ? AS uksi", (str(paths.UKSI_DB),))

total = c.execute("""SELECT COUNT(1) FROM specimens
                     WHERE taxonomic_sort_key IS NOT NULL""").fetchone()[0]
print("specimens with a sort key:", total)

rows = c.execute("""
    SELECT s.order_name, u.superfamily, s.family, s.subfamily,
           s.species_name, COUNT(*)
    FROM specimens s LEFT JOIN uksi.taxa u ON s.species_tvk = u.tvk
    WHERE s.taxonomic_sort_key IS NOT NULL
    GROUP BY s.order_name, u.superfamily, s.family, s.subfamily, s.species_name
""").fetchall()
print("tree query rows:", len(rows), " summing to:", sum(r[5] for r in rows))

# what build_tree keeps: last row wins per (order, sf, family, species)
kept = {}
for o, sf, fam, sub, sp, n in rows:
    kept[(o, sf, fam, sp)] = n
print("after the dict assignment:", sum(kept.values()), " <-- what the tree shows")
print("lost:", sum(r[5] for r in rows) - sum(kept.values()))

print()
print("species appearing under more than one subfamily:")
seen = {}
for o, sf, fam, sub, sp, n in rows:
    seen.setdefault((o, sf, fam, sp), []).append((sub, n))
dupes = {k: v for k, v in seen.items() if len(v) > 1}
print(f"  {len(dupes)} species affected")
for (o, sf, fam, sp), vals in list(dupes.items())[:10]:
    print(f"  {sp[:30]:30} {fam or '?':16} {vals}")
