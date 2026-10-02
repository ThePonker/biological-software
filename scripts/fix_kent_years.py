"""Kent Deadwood: every record belongs to the 2024 survey.

Lists each Kent Deadwood observation dated outside 2024, with the evidence for
2024: is there a 2024 visit on the same day, at the same site? With --apply, the
YEAR is changed to 2024 and nothing else. Each row is updated only if its date
is still what was listed (guarded by id and current value).

DRY RUN by default; --apply to write. Close Observatum and Examen first.

Run:  python scripts\\fix_kent_years.py
      python scripts\\fix_kent_years.py --apply
"""
import datetime, os, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import paths

APPLY = "--apply" in sys.argv
BACKUP_DIR = r"C:\BiologicalSoftware_Backups\reference"
PROJECT = "Kent Deadwood"

o = sqlite3.connect(str(paths.OBSERVATUM_DB))
print("Kent Deadwood -- records outside 2024  --  " + ("APPLY" if APPLY else "DRY RUN"))
print("=" * 76)

rows = o.execute("""SELECT id, date, site_name, species_name, grid_ref, recorder, comment,
                           irecord_id, sync_status
                    FROM observations
                    WHERE project_name = ? AND substr(date,1,4) != '2024'
                    ORDER BY date, site_name, id""", (PROJECT,)).fetchall()
years = o.execute("""SELECT substr(date,1,4), COUNT(1) FROM observations
                     WHERE project_name = ? GROUP BY 1""", (PROJECT,)).fetchall()
print(f"  {PROJECT} by year now: {years}")
print(f"  records outside 2024: {len(rows)}\n")

plan = []
for rid, d, site, sp, grid, rec, cm, irec, sync in rows:
    new = "2024" + (d or "")[4:]
    same_visit = o.execute("""SELECT COUNT(1) FROM observations
                              WHERE project_name=? AND date=? AND site_name=?""",
                           (PROJECT, new, site)).fetchone()[0]
    print(f"    id={rid:<6} {d}  {str(site)[:20]:20} {str(sp)[:30]:30} {str(grid)[:14]:14}"
          f"  -> {new}  (2024 visit, same day+site: {same_visit} records)")
    if irec or (sync or "").lower() == "synced":
        print(f"           note: this record is on iRecord (irecord_id={irec}, {sync}) -- "
              "correct it there too")
    plan.append((rid, d, new, same_visit))

if not plan:
    print("  nothing to do.")
    sys.exit(0)
weak = [p for p in plan if p[3] == 0]
if weak:
    print(f"\n  {len(weak)} record(s) have no 2024 visit on the same day and site -- "
          "check those by eye before applying.")

if not APPLY:
    print("\nDRY RUN -- nothing has been changed. Close Observatum and Examen, then --apply.")
    sys.exit(0)

os.makedirs(BACKUP_DIR, exist_ok=True)
bp = os.path.join(BACKUP_DIR, "observatum_pre_kent_years_" +
                  datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".db")
t = sqlite3.connect(bp); o.backup(t); t.close()
print(f"\n  backup: {bp}")

now = datetime.datetime.now().isoformat(timespec="seconds")
with o:
    for rid, old, new, _ in plan:
        n = o.execute("UPDATE observations SET date=?, updated_at=? WHERE id=? AND date=?",
                      (new, now, rid, old)).rowcount
        if n != 1:
            raise SystemExit(f"  x id={rid}: date changed since listing -- rolled back, nothing written")
print(f"  {len(plan)} records moved to 2024")

years = o.execute("""SELECT substr(date,1,4), COUNT(1) FROM observations
                     WHERE project_name = ? GROUP BY 1""", (PROJECT,)).fetchall()
print(f"  {PROJECT} by year now: {years}   (expect 2024 only)")
print("\nDone.")
