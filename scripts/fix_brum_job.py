"""Tidy staging job 6 (Birmingham - Wheels Park) before it is committed.

  * Lists every row with a species name but no TVK, with UKSI suggestions.
  * Sets site_name and project_name to "Birmingham - Wheels Park" on the job's
    rows (and project on the job itself), plus client if --client is given.
  * --fix ROWID=TVK resolves an unmatched row against UKSI (name, order,
    family, rank, common name all taken from UKSI so the row is consistent).

DRY RUN by default. --apply to write. Close Observatum first: Data Entry holds
the grid in memory and could write its own values back over these.

Run:
  python scripts\\fix_brum_job.py
  python scripts\\fix_brum_job.py --client "Jukes" --fix 1234=NBNSYS0000012345 --apply
"""
import argparse, datetime, difflib, os, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import paths

JOB_ID = 6
NAME = "Birmingham - Wheels Park"
BACKUP_DIR = r"C:\BiologicalSoftware_Backups\reference"

ap = argparse.ArgumentParser()
ap.add_argument("--apply", action="store_true")
ap.add_argument("--client", default=None)
ap.add_argument("--fix", action="append", default=[], help="ROWID=TVK")
a = ap.parse_args()

o = sqlite3.connect(str(paths.OBSERVATUM_DB))
u = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)

print(f"Staging job {JOB_ID} -- tidy before commit  --  " + ("APPLY" if a.apply else "DRY RUN"))
print("=" * 76)

job = o.execute("SELECT id, name, mode, project, client FROM entry_jobs WHERE id=?",
                (JOB_ID,)).fetchone()
if not job:
    sys.exit(f"  job {JOB_ID} not found")
print(f"  job: {job}")
if (job[2] or "").lower() != "commercial":
    sys.exit("  job is not Commercial -- stopping")


def uksi_row(tvk):
    r = u.execute('SELECT tvk, scientific_name, rank, "order", family FROM taxa WHERE tvk=?',
                  (tvk,)).fetchone()
    if not r:
        return None
    cn = u.execute("SELECT common_name FROM common_names WHERE tvk=? AND preferred=1",
                   (tvk,)).fetchone()
    return r + ((cn[0] if cn else None),)


def suggest(name):
    name = (name or "").strip()
    out = []
    r = u.execute('SELECT tvk FROM taxa WHERE scientific_name=?', (name,)).fetchall()
    out += [(t[0], "exact name") for t in r]
    r = u.execute("SELECT tvk FROM synonyms WHERE synonym=?", (name,)).fetchall()
    out += [(t[0], "synonym") for t in r]
    genus = name.split(" ")[0] if name else ""
    if genus:
        cands = [x[0] for x in u.execute(
            "SELECT scientific_name FROM taxa WHERE scientific_name LIKE ? AND rank='Species'",
            (genus + " %",))]
        for m in difflib.get_close_matches(name, cands, n=4, cutoff=0.6):
            t = u.execute("SELECT tvk FROM taxa WHERE scientific_name=? AND rank='Species'",
                          (m,)).fetchone()
            if t:
                out.append((t[0], "close spelling"))
    if not out:
        cands = [x[0] for x in u.execute(
            "SELECT DISTINCT scientific_name FROM taxa WHERE rank='Species' "
            "AND substr(scientific_name,1,3)=?", (name[:3],))]
        for m in difflib.get_close_matches(name, cands, n=4, cutoff=0.6):
            t = u.execute("SELECT tvk FROM taxa WHERE scientific_name=?", (m,)).fetchone()
            if t:
                out.append((t[0], "close spelling, other genus"))
    seen, res = set(), []
    for t, how in out:
        if t not in seen:
            seen.add(t)
            res.append((t, how, uksi_row(t)))
    return res


# ---------------------------------------------------------------- unmatched rows
rows = o.execute("""SELECT id, row_order, species_name, date, method, quantity, comment
                    FROM entry_staging
                    WHERE job_id=? AND species_name IS NOT NULL AND trim(species_name)!=''
                      AND (species_tvk IS NULL OR trim(species_tvk)='')""",
                 (JOB_ID,)).fetchall()
print(f"\n  Rows with a species but no TVK: {len(rows)}")
for rid, ro, sp, dt, me, q, cm in rows:
    print(f"\n    row id={rid} (grid row {ro}): {sp!r}  date={dt} method={me} qty={q} comment={cm!r}")
    sug = suggest(sp)
    if not sug:
        print("      no UKSI suggestions")
    for t, how, ur in sug[:6]:
        if ur:
            print(f"      {t}  {ur[1]:<36} {ur[2]:<10} {ur[4] or '':<18} "
                  f"{ur[5] or '':<24} ({how})")
    print(f"      to fix:  --fix {rid}=<TVK>")

# ---------------------------------------------------------------- planned changes
n_rows = o.execute("SELECT COUNT(1) FROM entry_staging WHERE job_id=?", (JOB_ID,)).fetchone()[0]
sites = o.execute("SELECT site_name, COUNT(1) FROM entry_staging WHERE job_id=? GROUP BY 1",
                  (JOB_ID,)).fetchall()
print(f"\n  Names: site and project -> {NAME!r} on all {n_rows} rows and the job")
print(f"    site names now: {sites}")
if a.client:
    print(f"    client -> {a.client!r}")
else:
    print("    client: unchanged (none given) -- Examen groups by project AND client,")
    print("            so set it now if the report names one: --client \"...\"")

fixes = []
for f in a.fix:
    rid, _, tvk = f.partition("=")
    ur = uksi_row(tvk.strip())
    if not ur:
        sys.exit(f"  --fix {f}: TVK not found in UKSI -- nothing written")
    if not any(r[0] == int(rid) for r in rows):
        sys.exit(f"  --fix {f}: row {rid} is not one of the unmatched rows -- nothing written")
    fixes.append((int(rid), ur))
    print(f"  fix row {rid} -> {ur[1]} ({ur[0]}), {ur[3]}/{ur[4]}, {ur[5] or 'no common name'}")

if not a.apply:
    print("\nDRY RUN -- nothing has been changed. Close Observatum, then --apply.")
    sys.exit(0)

# ---------------------------------------------------------------- write
os.makedirs(BACKUP_DIR, exist_ok=True)
bp = os.path.join(BACKUP_DIR, "observatum_pre_brum_tidy_" +
                  datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".db")
t = sqlite3.connect(bp); o.backup(t); t.close()
print(f"\n  backup: {bp}")

now = datetime.datetime.now().isoformat(timespec="seconds")
with o:
    o.execute("UPDATE entry_staging SET site_name=?, project_name=?, updated_at=? WHERE job_id=?",
              (NAME, NAME, now, JOB_ID))
    o.execute("UPDATE entry_jobs SET project=?, updated_at=? WHERE id=?", (NAME, now, JOB_ID))
    if a.client:
        o.execute("UPDATE entry_staging SET client=? WHERE job_id=?", (a.client, JOB_ID))
        o.execute("UPDATE entry_jobs SET client=? WHERE id=?", (a.client, JOB_ID))
    for rid, (tvk, sci, rank, order, family, common) in fixes:
        o.execute("""UPDATE entry_staging SET species_name=?, species_tvk=?, taxon_rank=?,
                     order_name=?, family=?, common_name=?, updated_at=? WHERE id=?""",
                  (sci, tvk, rank, order, family, common, now, rid))

# ---------------------------------------------------------------- read back
print("\n  Read back:")
print("   ", o.execute("SELECT project, client FROM entry_jobs WHERE id=?", (JOB_ID,)).fetchone())
for r in o.execute("""SELECT site_name, project_name, client, COUNT(1) FROM entry_staging
                      WHERE job_id=? GROUP BY 1,2,3""", (JOB_ID,)):
    print("   ", r)
left = o.execute("""SELECT COUNT(1) FROM entry_staging WHERE job_id=?
                    AND species_name IS NOT NULL AND trim(species_name)!=''
                    AND (species_tvk IS NULL OR trim(species_tvk)='')""", (JOB_ID,)).fetchone()[0]
print(f"    rows still without a TVK: {left}")
print("\nDone.")
