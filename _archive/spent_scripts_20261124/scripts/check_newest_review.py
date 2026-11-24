"""Is every species showing its NEWEST review's status?  READ ONLY.

Rule: each species takes its status from the newest review that assessed it.
check_legacy_conflicts.py covers an old status beside a newer one. This covers
the two cases it cannot see:

  (1) LEGACY ONLY IN A REVIEWED FAMILY -- a species has only an old pre-IUCN
      status (Notable / Na / Nb / RDB), but a newer review has assessed other
      species of its family. Either the newer review excluded it by JUDGEMENT
      (old status should go -- the Phaonia siebecki case) or by SCOPE (old status
      stands -- the tachinids). Listed for judgement, not changed.

  (2) OLDER MODERN SOURCE CHOSEN -- the Red List (2001-criteria) or NR/NS status
      shown comes from an older source than another designation JNCC holds for
      the same species and kind. Reviews loaded by us (origin 'manual') are skipped.

Run:  python scripts\\check_newest_review.py
"""
import os, re, sqlite3, sys
from collections import defaultdict
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import paths


def year(d, src=""):
    s = str(d or "").strip()
    if re.fullmatch(r"\d{5}(\.0)?", s):
        return (date(1899, 12, 30) + timedelta(days=int(float(s)))).year
    m = re.match(r"(19|20)\d{2}", s)
    if m:
        return int(m.group(0))
    m = re.search(r"\b(19[5-9]\d|20[0-2]\d)\b", str(src or ""))
    return int(m.group(0)) if m else 0


c = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)
u = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)
obs = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
fam_of = {}
def fam(t):
    if t not in fam_of:
        r = u.execute('SELECT family, scientific_name FROM taxa WHERE tvk=?', (t,)).fetchone()
        fam_of[t] = r or ("?", t)
    return fam_of[t]
mine = defaultdict(set)
for t, p, d in obs.execute("SELECT species_tvk, project_name, substr(date,1,4) FROM assessment_records "
                           "WHERE project_name IS NOT NULL AND project_name!=''"):
    mine[t].add(f"{p} {d}")
recorded = {t for (t,) in obs.execute("SELECT DISTINCT species_tvk FROM assessment_records")}

st = defaultdict(dict)
for t, tr, v, src, d, o in c.execute("""SELECT tvk, status_track, status_value, source, date_designated, origin
        FROM status_summary WHERE COALESCE(status_detail,'')='' AND status_track IN
        ('threat_iucn_2001','threat_iucn_legacy','rarity_modern','rarity_legacy')"""):
    st[t][tr] = (v, src or "", year(d, src), o)

print("Newest review shown?   READ ONLY")
print("=" * 96)

# ---------------- (1) legacy only, in a family a newer review has assessed
newest_mod = defaultdict(lambda: (0, ""))           # family -> (year, source) of newest modern assessment
for t, s in st.items():
    for tr in ("threat_iucn_2001", "rarity_modern"):
        if tr in s and s[tr][2] > newest_mod[fam(t)[0]][0]:
            newest_mod[fam(t)[0]] = (s[tr][2], s[tr][1])
flag = defaultdict(list)
for t, s in st.items():
    if any(k in s for k in ("threat_iucn_2001", "rarity_modern")):
        continue
    leg = [v for k, v in s.items() if k in ("threat_iucn_legacy", "rarity_legacy")]
    if not leg:
        continue
    f = fam(t)[0]
    ly = max(v[2] for v in leg)
    ny, nsrc = newest_mod.get(f, (0, ""))
    if ny > ly:
        flag[(f, nsrc[:60], ny)].append((fam(t)[1], "/".join(v[0] for v in leg), t))
n1 = sum(len(v) for v in flag.values())
print(f"\n(1) LEGACY ONLY IN A REVIEWED FAMILY: {n1} species in {len(flag)} families")
print("    (excluded by judgement -> old status should go; by scope -> it stands)")
for (f, src, y), spp in sorted(flag.items(), key=lambda kv: -len(kv[1])):
    yours = [s for s in spp if s[2] in recorded]
    print(f"  {len(spp):>4}  {f:<18} newer review {y}: {src}")
    print(f"        e.g. {', '.join(f'{n} ({v})' for n, v, _ in spp[:4])[:100]}")
    if yours:
        print(f"        in YOUR records: {', '.join(f'{n} ({v})' for n, v, _ in yours)[:100]}")
surveys = defaultdict(list)
for spp in flag.values():
    for n, v, t in spp:
        for sv in mine.get(t, ()):
            surveys[sv].append(f"{n} ({v})")
print("\n    in your surveys:")
for sv, spp in sorted(surveys.items()):
    print(f"      {sv:<36} {len(spp)}: {', '.join(spp)[:100]}")
if not surveys:
    print("      none")

# ---------------- (2) an older modern source chosen over a newer one
print(f"\n(2) OLDER MODERN SOURCE CHOSEN")
des = defaultdict(list)
for t, ab, src, d, iv in c.execute("""SELECT tvk, designation_abbreviation, source, date_designated, iucn_version
                                     FROM designations"""):
    ab = ab or ""
    if re.match(r"^N[RS]-(in|ex)cludes$", ab):
        des[(t, "rarity_modern")].append((year(d, src), src))
    elif str(iv or "").startswith("2001") and not ab.upper().endswith("WL") and "Global" not in ab:
        des[(t, "threat_iucn_2001")].append((year(d, src), src))
older = []
for (t, tr), lst in des.items():
    s = st.get(t, {}).get(tr)
    if not s or s[3] == "manual" or len({x[1] for x in lst}) < 2:
        continue
    ny, nsrc = max(lst)
    if ny > s[2] and nsrc != s[1]:
        older.append((fam(t)[1], tr, s[0], s[2], s[1][:45], ny, nsrc[:45], t))
print(f"    {len(older)} species-tracks")
for n, tr, v, sy, ss, ny, ns, t in older[:20]:
    print(f"      {n[:26]:26} {tr:<17} shows {v} ({sy}, {ss}) -- newer source {ny}: {ns}"
          + ("  [yours]" if t in recorded else ""))
print("\nREAD ONLY -- nothing has been changed.")
