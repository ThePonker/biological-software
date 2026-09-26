import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3, paths
from shared.sex_summary import classify_sex, format_sex_summary

c = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
c.execute("ATTACH ? AS uksi", (str(paths.UKSI_DB),))

print("every sexed Coleoptera specimen, and where it sits in the tree:")
print(f'{"superfamily":22} {"family":20} {"species":28} {"sex"}')
for sf, fam, sp, sex, n in c.execute("""
        SELECT COALESCE(u.superfamily,'(none)'), COALESCE(s.family,'?'),
               s.species_name, s.sex, COUNT(*)
        FROM specimens s LEFT JOIN uksi.taxa u ON s.species_tvk = u.tvk
        WHERE s.order_name='Coleoptera'
          AND TRIM(COALESCE(s.sex,'')) != ''
          AND s.taxonomic_sort_key IS NOT NULL
        GROUP BY 1,2,3,4 ORDER BY 1,2,3"""):
    print(f"{sf[:22]:22} {fam[:20]:20} {sp[:28]:28} {sex} x{n}")
