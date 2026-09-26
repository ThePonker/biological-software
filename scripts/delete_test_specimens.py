import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3, paths

APPLY = "--apply" in sys.argv
c = sqlite3.connect(str(paths.OBSERVATUM_DB))

rows = c.execute("""SELECT id, species_name, date_collected, site_name,
                           grid_ref, created_at
                    FROM specimens WHERE species_name = 'Rutpela maculata'
                    ORDER BY id""").fetchall()

print(f"all Rutpela maculata specimens ({len(rows)}):")
for r in rows:
    print(f"  id {r[0]:>5}  collected {r[2]}  {str(r[3])[:20]:20} {str(r[4]):10} "
          f"added {str(r[5])[:19]}")

targets = [r for r in rows if str(r[2]).startswith("2026-01-01")]
print()
print(f"dated 2026-01-01: {len(targets)}")
for r in targets:
    print(f"  id {r[0]}  added {str(r[5])[:19]}")

if not targets:
    print("\nnothing matches -- check the collected date and re-run")
elif not APPLY:
    print("\nNothing deleted. Re-run with --apply to remove those.")
else:
    import datetime, os.path
    b = os.path.join(r"C:\BiologicalSoftware_Backups", "reference",
                     "observatum_pre_testdelete_"
                     + datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".db")
    d = sqlite3.connect(b); c.backup(d); d.close()
    print(f"\nbacked up to {b}")
    for r in targets:
        c.execute("DELETE FROM specimens WHERE id = ?", (r[0],))
    c.commit()
    print(f"deleted {len(targets)} record(s)")
    print("remaining Rutpela maculata:",
          c.execute("SELECT COUNT(1) FROM specimens "
                    "WHERE species_name='Rutpela maculata'").fetchone()[0])
c.close()
