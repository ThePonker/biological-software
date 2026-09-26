import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3, paths

c = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
c.execute("ATTACH ? AS uksi", (str(paths.UKSI_DB),))

rows = c.execute("""
    SELECT s.order_name, u.superfamily, s.family,
           NULLIF(TRIM(COALESCE(s.subfamily,'')),''), s.species_name, COUNT(*)
    FROM specimens s LEFT JOIN uksi.taxa u ON s.species_tvk = u.tvk
    WHERE s.taxonomic_sort_key IS NOT NULL
    GROUP BY s.order_name, u.superfamily, s.family,
             NULLIF(TRIM(COALESCE(s.subfamily,'')),''), s.species_name
""").fetchall()

kept = {}
for o, sf, fam, sub, sp, n in rows:
    kept[(o, sf, fam, sp)] = kept.get((o, sf, fam, sp), 0) + n

ORDER = "Coleoptera"
nodes = {}          # what appears directly under the order
for (o, sf, fam, sp), n in kept.items():
    if o != ORDER:
        continue
    label = sf if sf else fam        # superfamily node, else family direct
    nodes[label] = nodes.get(label, 0) + n

print(f"{ORDER} total: {sum(nodes.values())}")
print(f"child nodes: {len(nodes)}")
print()
for label in sorted(nodes, key=lambda k: -nodes[k]):
    print(f"  {str(label)[:30]:30} {nodes[label]:>5}")
print()
print("sum of children:", sum(nodes.values()))
