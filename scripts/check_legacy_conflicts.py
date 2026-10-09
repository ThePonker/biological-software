"""Old statuses surviving beside a NEWER review's assessment.  READ ONLY.

Rule: each species takes its status from the newest review that assessed it.
Statuses arriving via JNCC can break that -- an old Notable / Na / Nb / RDB
designation kept beside a later review's assessment (Phaonia siebecki).

For every species holding a LEGACY status (rarity_legacy, threat_iucn_legacy)
AND a MODERN one (threat_iucn_2001, rarity_modern) from a different, LATER
source, it asks: does the legacy status change the species' key standing?
  STALE KEY   the old status makes it Key / Rare Key; the newer review alone
              would not -> the case to fix
  agree       both point the same way (harmless; listed by count only)
and which of your surveys hold the STALE KEY species.

Run:  python scripts\\check_legacy_conflicts.py
"""
import os, re, sqlite3, sys
from collections import Counter, defaultdict
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "scripts")]
import paths
from import_status_review import key_tiers

LEG = ("rarity_legacy", "threat_iucn_legacy")
MOD = ("threat_iucn_2001", "rarity_modern")


def year(d, src):
    s = str(d or "").strip()
    if re.fullmatch(r"\d{5}(\.0)?", s):                      # Excel serial date
        return (date(1899, 12, 30) + timedelta(days=int(float(s)))).year
    m = re.match(r"(19|20)\d{2}", s)
    if m:
        return int(m.group(0))
    m = re.search(r"\b(19[5-9]\d|20[0-2]\d)\b", str(src or ""))
    return int(m.group(0)) if m else None


c = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)
rows = defaultdict(dict)
for tvk, tr, v, src, d in c.execute(
        "SELECT tvk, status_track, status_value, source, date_designated FROM status_summary "
        "WHERE COALESCE(status_detail,'')='' AND status_track IN (?,?,?,?)", LEG + MOD):
    rows[tvk][tr] = (v, src or "", year(d, src))

stale, agree, undated = [], 0, 0
by_review = Counter()
for tvk, t in rows.items():
    leg = {k: v for k, v in t.items() if k in LEG}
    mod = {k: v for k, v in t.items() if k in MOD}
    if not leg or not mod:
        continue
    ly = max((v[2] or 0) for v in leg.values())
    my = max((v[2] or 0) for v in mod.values())
    msrc = max(mod.values(), key=lambda v: v[2] or 0)[1]
    if not ly or not my:
        undated += 1
        continue
    if my <= ly or all(v[1] == msrc for v in leg.values()):
        continue                                   # modern not newer, or same source
    k_all, r_all = key_tiers({k: v[0] for k, v in t.items()})
    k_mod, r_mod = key_tiers({k: v[0] for k, v in mod.items()})
    if (k_all, r_all) != (k_mod, r_mod):
        stale.append((tvk, leg, mod, msrc, k_all, r_all, k_mod, r_mod))
        by_review[msrc[:75]] += 1
    else:
        agree += 1

u = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)
name = lambda t: (u.execute("SELECT scientific_name FROM taxa WHERE tvk=?", (t,)).fetchone() or (t,))[0]
tier = lambda k, r: "Rare Key" if r else "Key" if k else "not key"

print("Old statuses beside a newer review   READ ONLY")
print("=" * 92)
print(f"  species with both an old and a newer, different-source status: {len(stale) + agree}")
print(f"    STALE KEY (old status changes key standing): {len(stale)}")
print(f"    agree (no effect on key standing):           {agree}")
print(f"    skipped, no usable date on one side:         {undated}")
print("\n  STALE KEY by the newer review that assessed them:")
for src, n in by_review.most_common():
    print(f"    {n:>4}  {src}")
print("\n  Examples (old -> newer):")
for tvk, leg, mod, msrc, k1, r1, k2, r2 in stale[:25]:
    o = ", ".join(f"{v[0]} ({v[2]})" for v in leg.values())
    n = ", ".join(f"{v[0]} ({v[2]})" for v in mod.values())
    print(f"    {name(tvk)[:30]:30} old {o:<26} newer {n:<22} {tier(k1, r1)} -> {tier(k2, r2)}")

obs = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
st = {s[0] for s in stale}
hits = defaultdict(set)
for tvk, proj, d in obs.execute("SELECT species_tvk, project_name, substr(date,1,4) FROM assessment_records "
                                "WHERE project_name IS NOT NULL AND project_name != ''"):
    if tvk in st:
        hits[f"{proj} {d}"].add(name(tvk))
mine = {t for (t,) in obs.execute("SELECT DISTINCT species_tvk FROM assessment_records")} & st
print(f"\n  STALE KEY species in your records: {len(mine)}")
print("  In your surveys:")
for s_, spp in sorted(hits.items()):
    print(f"    {s_:<38} {len(spp)}: {', '.join(sorted(spp))[:90]}")
if not hits:
    print("    none")
print("\nREAD ONLY -- nothing has been changed.")
