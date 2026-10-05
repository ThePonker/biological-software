"""What did the JNCC 2026 rebuild change?  READ ONLY.

Compares the pre-rebuild backup with codex.db now:
  1. threat/rarity rows by JNCC category and track, before -> after
  2. every invertebrate whose key standing changed: before and after statuses
     with sources, flagged where it is in your records / on a survey
  3. invertebrates that LOST a rarity_modern status: which source it came from

Run:  python scripts\\compare_codex_rebuild.py
"""
import glob, os, sqlite3, sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "scripts")]
import paths
from import_status_review import key_tiers

bk = sorted(glob.glob(r"C:\BiologicalSoftware_Backups\reference\codex_pre_jncc2026_*.db"))
if not bk:
    sys.exit("  x pre-rebuild backup not found")
TR = ("threat_iucn_2001", "threat_iucn_legacy", "rarity_modern", "rarity_legacy")


def load(db):
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    cat = dict(c.execute("SELECT tvk, MAX(category) FROM designations GROUP BY tvk"))
    st = defaultdict(dict)
    for t, tr, v, d, s in c.execute(f"""SELECT tvk, status_track, status_value, COALESCE(status_detail,''), source
                                        FROM status_summary WHERE status_track IN ({','.join('?'*4)})""", TR):
        st[t].setdefault(tr, []).append((v, d, (s or "")[:60]))
    return cat, st


ca, a = load(bk[-1])
cb, b = load(paths.CODEX_DB)
cat = {**ca, **cb}
print(f"JNCC 2026 rebuild -- what changed   (before: {os.path.basename(bk[-1])})   READ ONLY")
print("=" * 100)
print("\n1. Threat/rarity rows by category, before -> after")
cnt = lambda st: Counter((cat.get(t) or "?", tr) for t, d in st.items() for tr, vs in d.items() for _ in vs)
A, B = cnt(a), cnt(b)
for k in sorted(set(A) | set(B), key=lambda k: (k[0], k[1])):
    if A[k] != B[k]:
        print(f"   {k[0]:<20} {k[1]:<20} {A[k]:>6} -> {B[k]:>6}  ({B[k] - A[k]:+d})")

obs = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
recorded = {t for (t,) in obs.execute("SELECT DISTINCT species_tvk FROM assessment_records")}
surveys = defaultdict(set)
for t, p, d in obs.execute("""SELECT species_tvk, project_name, substr(date,1,4) FROM assessment_records
                              WHERE project_name IS NOT NULL AND project_name!=''"""):
    surveys[t].add(f"{p} {d}")
u = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)
name = lambda t: (u.execute("SELECT scientific_name FROM taxa WHERE tvk=?", (t,)).fetchone() or (t,))[0]
tier = lambda k, r: "Rare Key" if r else "Key" if k else "not key"
flat = lambda d: {tr: vs[0][0] for tr, vs in d.items()}
fmt = lambda d: "; ".join(f"{v}" + (f"/{dd}" if dd else "") + f" [{s[:28]}]" for tr, vs in d.items() for v, dd, s in vs) or "none"

print("\n2. Invertebrates whose key standing changed")
moved = []
for t in set(a) | set(b):
    if cat.get(t) != "Invertebrate":
        continue
    ka, kb = key_tiers(flat(a.get(t, {}))), key_tiers(flat(b.get(t, {})))
    if ka != kb:
        moved.append((t in recorded, name(t), tier(*ka), tier(*kb), fmt(a.get(t, {})), fmt(b.get(t, {})), t))
print(f"   {len(moved)} species; {sum(m[0] for m in moved)} in your records")
print(f"   {dict(Counter(f'{m[2]} -> {m[3]}' for m in moved))}")
for m in sorted(moved, reverse=True)[:40]:
    flag = ("YOURS " + ", ".join(sorted(surveys.get(m[6], [])))[:40]) if m[0] else ""
    print(f"   {m[1][:28]:28} {m[2]:>8} -> {m[3]:<8} {flag}")
    print(f"   {'':28} before: {m[4][:105]}")
    print(f"   {'':28} after:  {m[5][:105]}")

print("\n3. Invertebrates that lost a rarity_modern status, by the source it came from")
lost = Counter()
for t in a:
    if cat.get(t) == "Invertebrate" and "rarity_modern" in a[t] and "rarity_modern" not in b.get(t, {}):
        lost[a[t]["rarity_modern"][0][2]] += 1
for s, n in lost.most_common(15):
    print(f"   {n:>5}  {s}")
print(f"   total {sum(lost.values())}")
print("\nREAD ONLY -- nothing has been changed.")
