"""Invertebrates whose threat/rarity status VANISHED in the JNCC 2026 rebuild,
with nothing newer replacing it.  READ ONLY.

For each: is the same species in the 2026 spreadsheet under a DIFFERENT TVK
(JNCC re-keyed it to a newer UKSI) -- and does our uksi.db know that TVK?
Also: how many 2026 TVKs our uksi.db does not know at all, and whether any of
your records use a TVK the 2026 spreadsheet has dropped.

Run:  python scripts\\check_lost_statuses.py
"""
import glob, os, sqlite3, sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import paths

bk = sorted(glob.glob(r"C:\BiologicalSoftware_Backups\reference\codex_pre_jncc2026_*.db"))[-1]
TR = ("threat_iucn_2001", "threat_iucn_legacy", "rarity_modern", "rarity_legacy")
a = sqlite3.connect(f"file:{bk}?mode=ro", uri=True)
b = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)
u = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)
obs = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)


def statuses(c):
    d = defaultdict(list)
    for t, tr, v, s in c.execute(f"SELECT tvk, status_track, status_value, source FROM status_summary "
                                 f"WHERE status_track IN ({','.join('?'*4)})", TR):
        d[t].append(f"{v} [{(s or '')[:30]}]")
    return d


sa, sb = statuses(a), statuses(b)
cat_a = dict(a.execute("SELECT tvk, MAX(category) FROM designations GROUP BY tvk"))
names_a = dict(a.execute("SELECT tvk, MAX(species_name) FROM designations GROUP BY tvk"))
by_name_b = defaultdict(set)
for t, n in b.execute("SELECT DISTINCT tvk, species_name FROM designations"):
    by_name_b[(n or "").strip()].add(t)
in_uksi = lambda t: u.execute("SELECT 1 FROM taxa WHERE tvk=?", (t,)).fetchone() is not None
recorded = Counter(t for (t,) in obs.execute("SELECT species_tvk FROM assessment_records"))

print("Statuses that vanished in the JNCC 2026 rebuild   READ ONLY")
print("=" * 100)
lost = [t for t in sa if cat_a.get(t) == "Invertebrate" and not sb.get(t)]
rekeyed, dropped = [], []
for t in lost:
    other = by_name_b.get((names_a.get(t) or "").strip(), set()) - {t}
    (rekeyed if other else dropped).append((t, other))
print(f"  invertebrates with a status before and NONE after: {len(lost)}")
print(f"    same name now under a different TVK (re-keyed): {len(rekeyed)}")
print(f"    not in the 2026 spreadsheet at all (dropped):   {len(dropped)}")
print("\n  RE-KEYED (old TVK -> new TVK; 'not in uksi.db' = our UKSI is older than JNCC's)")
for t, other in rekeyed[:25]:
    for o in other:
        print(f"    {names_a.get(t,'')[:30]:30} {t} -> {o}  {'in uksi.db' if in_uksi(o) else 'NOT in uksi.db'}"
              f"  your records on old TVK: {recorded.get(t, 0)}  now: {'; '.join(sb.get(o, ['none']))[:40]}")
print("\n  DROPPED (no 2026 entry under any TVK)")
for t, _ in dropped[:30]:
    print(f"    {names_a.get(t,'')[:30]:30} {t}  before: {'; '.join(sa[t])[:60]}  your records: {recorded.get(t, 0)}")

tv_b = {t for (t,) in b.execute("SELECT DISTINCT tvk FROM designations")}
unk = [t for t in tv_b if not in_uksi(t)]
print(f"\n  2026 spreadsheet TVKs our uksi.db does not know: {len(unk)} of {len(tv_b)}")
print("  e.g. " + ", ".join(f"{t} ({(b.execute('SELECT MAX(species_name) FROM designations WHERE tvk=?', (t,)).fetchone() or [''])[0]})" for t in unk[:8]))
mine_unk = [t for t in unk if recorded.get(t)]
print(f"  ...of which used by your records: {len(mine_unk)}  {[(t, recorded[t]) for t in mine_unk[:5]]}")
print("\nREAD ONLY -- nothing has been changed.")
