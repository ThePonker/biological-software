import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3, paths
from shared.sex_summary import classify_sex, format_sex_summary

c = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)

# exactly what the tree query returns
tree = c.execute("""SELECT species_name, COUNT(*) FROM specimens
                    WHERE taxonomic_sort_key IS NOT NULL
                    GROUP BY order_name, family, subfamily, species_name""").fetchall()
print("tree rows:", len(tree))

# exactly what the patch's sex query returns
sexes = {}
for name, sex, n in c.execute("""SELECT species_name, sex, COUNT(*) FROM specimens
                                 WHERE taxonomic_sort_key IS NOT NULL
                                 GROUP BY species_name, sex"""):
    m, f, o = sexes.get(name, (0, 0, 0))
    k = classify_sex(sex)
    if k == "m": m += n
    elif k == "f": f += n
    else: o += n
    sexes[name] = (m, f, o)

sexed = {k: v for k, v in sexes.items() if v[0] or v[1]}
print("species with a sex, after the sort-key filter:", len(sexed))
for name, (m, f, o) in list(sexed.items())[:10]:
    print(f"   {name[:34]:34} {format_sex_summary(m, f, o)}")

print()
print("do those names appear in the tree rows?")
tree_names = {r[0] for r in tree}
for name in list(sexed)[:10]:
    print(f"   {name[:34]:34} {'yes' if name in tree_names else 'NO'}")
