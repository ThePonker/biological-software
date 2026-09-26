import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3, paths

c = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
c.execute("ATTACH ? AS uksi", (str(paths.UKSI_DB),))

rows = c.execute("""SELECT s.order_name, s.taxonomic_sort_key, u.sort_code
                    FROM specimens s JOIN uksi.taxa u ON s.species_tvk = u.tvk
                    WHERE s.taxonomic_sort_key IS NOT NULL
                      AND u.sort_code IS NOT NULL""").fetchall()

print(f"{len(rows)} rows to test")
prefixes, bad = {}, 0
for order, stored, code in rows:
    q, r = divmod(int(stored), 100000)
    if r != int(code):
        bad += 1
        if bad <= 5:
            print(f"  MISMATCH {order} stored={stored} code={code} remainder={r}")
    else:
        prefixes.setdefault(order, set()).add(q)

print(f"remainder == sort_code for {len(rows) - bad} of {len(rows)}")
print()
print("prefix per order:")
for order in sorted(prefixes):
    p = prefixes[order]
    flag = "" if len(p) == 1 else "   <-- NOT CONSTANT"
    print(f"  {str(order)[:26]:26} {sorted(p)}{flag}")

try:
    from Observatum.src.utils.constants import INSECT_ORDER_POSITION
    print()
    print("against INSECT_ORDER_POSITION:")
    for order in sorted(prefixes):
        print(f"  {str(order)[:26]:26} prefix={sorted(prefixes[order])[0]:>3}"
              f"   constant={INSECT_ORDER_POSITION.get(order)}")
except Exception as e:
    print("\ncould not import INSECT_ORDER_POSITION:", e)
