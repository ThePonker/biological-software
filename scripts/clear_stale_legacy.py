"""Clear old (pre-IUCN) statuses superseded by a newer review.

Rule: each species takes its status from the newest review that assessed it.
Finds every species holding a legacy status (rarity_legacy / threat_iucn_legacy)
beside a modern status (threat_iucn_2001 / rarity_modern) from a different,
LATER source -- exactly as check_legacy_conflicts.py does -- and clears the
legacy status:
  default   only STALE KEY species (the legacy status changes key standing)
  --all     every such species, including those where both agree

Each clearance is a manual entry (value 'none' = status removed) naming the
newer review that superseded it, so it survives every Codex rebuild. Uses
apply_status / key_tiers / backup / CLEAR from import_status_review.py.

DRY RUN by default; --apply to write.

Run:  python scripts\\clear_stale_legacy.py
      python scripts\\clear_stale_legacy.py --apply
"""
import os, re, sqlite3, sys
from collections import defaultdict
from datetime import date, datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "scripts")]
import paths
from import_status_review import apply_status, key_tiers, backup, CLEAR

LEG = ("rarity_legacy", "threat_iucn_legacy")
MOD = ("threat_iucn_2001", "rarity_modern")
APPLY, ALL = "--apply" in sys.argv, "--all" in sys.argv


def year(d, src):
    s = str(d or "").strip()
    if re.fullmatch(r"\d{5}(\.0)?", s):
        return (date(1899, 12, 30) + timedelta(days=int(float(s)))).year
    m = re.match(r"(19|20)\d{2}", s)
    if m:
        return int(m.group(0))
    m = re.search(r"\b(19[5-9]\d|20[0-2]\d)\b", str(src or ""))
    return int(m.group(0)) if m else None


codex = sqlite3.connect(str(paths.CODEX_DB))
c = codex.cursor()
rows = defaultdict(dict)
for tvk, tr, v, src, d in c.execute(
        "SELECT tvk, status_track, status_value, source, date_designated FROM status_summary "
        "WHERE COALESCE(status_detail,'')='' AND status_track IN (?,?,?,?)", LEG + MOD):
    rows[tvk][tr] = (v, src or "", year(d, src))

u = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)
nm = lambda t: (u.execute("SELECT scientific_name FROM taxa WHERE tvk=?", (t,)).fetchone() or (t,))[0]
tier = lambda k, r: "Rare Key" if r else "Key" if k else "not key"
plan = []
for tvk, t in rows.items():
    leg = {k: v for k, v in t.items() if k in LEG}
    mod = {k: v for k, v in t.items() if k in MOD}
    if not leg or not mod:
        continue
    ly = max((v[2] or 0) for v in leg.values()); my = max((v[2] or 0) for v in mod.values())
    newest = max(mod.values(), key=lambda v: v[2] or 0)
    if not ly or not my or my <= ly or all(v[1] == newest[1] for v in leg.values()):
        continue
    before = key_tiers({k: v[0] for k, v in t.items()})
    after = key_tiers({k: v[0] for k, v in mod.items()})
    if ALL or before != after:
        plan.append((tvk, nm(tvk), leg, newest, before, after))

print("Clear superseded old statuses -- " + ("APPLY" if APPLY else "DRY RUN") + (" (--all)" if ALL else " (STALE KEY only)"))
print("=" * 92)
for tvk, name, leg, newest, b, a in plan:
    old = ", ".join(f"{k}={v[0]} ({v[2]})" for k, v in leg.items())
    print(f"  {name[:30]:30} clear {old:<38} -> {tier(*b)} -> {tier(*a)}")
    print(f"  {'':30} superseded by: {newest[1][:70]} ({newest[2]})")
print(f"\n  {len(plan)} species, {sum(len(p[2]) for p in plan)} old statuses to clear")
if not APPLY or not plan:
    sys.exit("\n  DRY RUN -- nothing changed. Re-run with --apply.\n" if not APPLY else "  nothing to do")

print(f"  backup: {backup(paths.CODEX_DB, 'codex')}")
now = datetime.now().isoformat()
try:
    for tvk, name, leg, newest, b, a in plan:
        for tr, (v, src, y) in leg.items():
            c.execute("""INSERT INTO manual_entries (tvk, species_name, status_track, status_value, status_detail,
                         source_review, date_added, added_by, notes, review_id)
                         VALUES (?,?,?,?,NULL,?,?,?,?,NULL)""",
                      (tvk, name, tr, CLEAR, newest[1], str(newest[2] or ""), "superseded-legacy",
                       f"Old status {v} ({src[:60]}, {y}) superseded by {newest[1][:80]} ({newest[2]})"))
            apply_status(c, tvk, tr, CLEAR, None, newest[1], str(newest[2] or ""))
    codex.commit()
except Exception as e:
    codex.rollback()
    sys.exit(f"  x FAILED, rolled back: {type(e).__name__}: {e}")
dup = c.execute("""SELECT COUNT(1) FROM (SELECT tvk, status_track, COALESCE(status_detail,'')
                   FROM status_summary GROUP BY 1,2,3 HAVING COUNT(1) > 1)""").fetchone()[0]
print(f"  cleared {sum(len(p[2]) for p in plan)} old statuses on {len(plan)} species; duplicated statuses {dup} (should be 0)\n")
codex.close()
