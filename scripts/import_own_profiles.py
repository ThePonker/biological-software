"""Import YOUR OWN species profiles into Observatum (observatum.db species_profiles).

These are the profiles the Species Profile dialog edits and reports use (origin 'own').
Input: a CSV with columns  species_name, profile_text  (optional: order_name, family).

  python scripts\\import_own_profiles.py kent_deadwood_profiles.csv
  python scripts\\import_own_profiles.py kent_deadwood_profiles.csv --apply
  add --replace to overwrite profiles that already exist (default: skip them)

DRY RUN unless --apply.  --apply backs up observatum.db first.
"""
import csv, os, shutil, sqlite3, sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import paths

if len(sys.argv) < 2 or sys.argv[1].startswith("--"):
    sys.exit(__doc__)
SRC_CSV = sys.argv[1]
APPLY, REPLACE = "--apply" in sys.argv, "--replace" in sys.argv

rows = [r for r in csv.DictReader(open(SRC_CSV, encoding="utf-8-sig")) if (r.get("profile_text") or "").strip()]
u = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)
o = sqlite3.connect(str(paths.OBSERVATUM_DB))
cols = {r[1] for r in o.execute("PRAGMA table_info(species_profiles)")}
if not {"species_name", "species_tvk", "profile_text"} <= cols:
    sys.exit(f"  x observatum.db species_profiles lacks expected columns (has: {sorted(cols)}) -- nothing done")


def resolve(name):
    r = u.execute("SELECT tvk, scientific_name FROM taxa WHERE scientific_name=? COLLATE NOCASE", (name,)).fetchone()
    if r:
        return r
    try:
        r = u.execute("SELECT s.tvk, t.scientific_name FROM synonyms s JOIN taxa t ON t.tvk=s.tvk "
                      "WHERE s.synonym=? COLLATE NOCASE", (name,)).fetchone()
    except sqlite3.Error:
        r = None
    return r


print("Import own species profiles -- " + ("APPLY" if APPLY else "DRY RUN"))
print("=" * 78)
print(f"  file: {SRC_CSV}   profiles: {len(rows)}\n")
plan, skipped, unmatched = [], [], []
for r in rows:
    name = r["species_name"].strip()
    hit = resolve(name)
    if not hit:
        unmatched.append(name); continue
    tvk, current = hit
    have = o.execute(f"SELECT id, {'origin' if 'origin' in cols else "'own'"}, length(COALESCE(profile_text,'')), "
                     f"{'COALESCE(notes,\'\')' if 'notes' in cols else "''"} FROM species_profiles "
                     "WHERE species_tvk=? OR species_name=?", (tvk, current)).fetchone()
    if have and have[2] and not REPLACE:
        skipped.append((current, have[1])); continue
    plan.append((have[0] if have else None, current, tvk, r, have[3] if have else ""))
print(f"  to write: {len(plan)}   already have a profile (skipped): {len(skipped)}   no UKSI match: {len(unmatched)}")
for n, org in skipped:
    print(f"    skipped -- already has a profile ({org}): {n}")
for n in unmatched:
    print(f"    x no UKSI match: {n}")
for _, n, tvk, r, _nt in plan[:3]:
    print(f"\n    e.g. {n} ({tvk}): {r['profile_text'][:150]}...")
if not APPLY:
    sys.exit("\n  DRY RUN -- nothing changed. Re-run with --apply.\n")
if not plan:
    sys.exit("  nothing to write")

bk = os.path.join(os.path.dirname(str(paths.OBSERVATUM_DB)),
                  f"observatum_pre_profiles_{datetime.now():%Y%m%d_%H%M%S}.db")
src = sqlite3.connect(str(paths.OBSERVATUM_DB)); dst = sqlite3.connect(bk); src.backup(dst); dst.close(); src.close()
print(f"\n  backup: {bk}")
now = datetime.now().isoformat(timespec="seconds")
extra = [c for c in ("order_name", "family") if c in cols]
try:
    for pid, n, tvk, r, old_notes in plan:
        vals = {"species_name": n, "species_tvk": tvk, "profile_text": r["profile_text"].strip()}
        if "updated_at" in cols: vals["updated_at"] = now
        if "origin" in cols: vals["origin"] = "own"
        for c in extra:
            if r.get(c): vals[c] = r[c].strip()
        if pid:
            o.execute(f"UPDATE species_profiles SET {', '.join(k + '=?' for k in vals)} WHERE id=?", (*vals.values(), pid))
        else:
            o.execute(f"INSERT INTO species_profiles ({', '.join(vals)}) VALUES ({','.join('?' * len(vals))})",
                      tuple(vals.values()))
    o.commit()
except Exception as e:
    o.rollback(); sys.exit(f"  x FAILED, rolled back: {type(e).__name__}: {e}")
n = o.execute("SELECT COUNT(1) FROM species_profiles WHERE COALESCE(profile_text,'')!=''").fetchone()[0]
print(f"  written: {len(plan)}   species with a profile in Observatum now: {n}")
