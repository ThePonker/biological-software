import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3, paths
from collections import defaultdict

p = sqlite3.connect(f"file:{paths.PANTHEON_DB}?mode=ro", uri=True)

for tbl, col in [("feeding_guilds", "guild"),
                 ("habitats", "habitat"),
                 ("broad_biotope", "biotope"),
                 ("specific_assemblage_types", "sat_name")]:
    try:
        d = defaultdict(set)
        for (v,) in p.execute(f"SELECT DISTINCT {col} FROM {tbl}"):
            if v:
                d[v.lower()].add(v)
        clashes = {k: v for k, v in d.items() if len(v) > 1}
        print(f"{tbl}: {len(d)} distinct values, {len(clashes)} with case variants")
        for k, v in sorted(clashes.items()):
            print(f"    {sorted(v)}")
    except sqlite3.Error as e:
        print(f"{tbl}: {e}")
