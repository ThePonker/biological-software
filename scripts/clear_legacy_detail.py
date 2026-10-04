"""Clear OLD statuses stored with a qualifier in status_detail, where a newer
review assessed the species.

JNCC stores some legacy statuses with a detail -- RDBK / 'Insufficiently Known',
'1994 IUCN', 'Indeterminate', 'Pre-1994 RDB'. Every check and clearance on
4 Oct 2026 looked only at rows with an EMPTY detail, so these survived even where
a newer review assessed the species (Chlorops rufinus: NS in NECR217, still
RDBK / Insufficiently Known from Falk 1991).

A legacy row with a detail is cleared when the species was assessed later by:
  (a) a review loaded with statuses (manual entries added_by 'review-load')
  (b) a modern status (threat_iucn_2001 / rarity_modern) from a later source
  (c) a withdrawal, supersession or old-name clearance made on 4 Oct
Rows where the species has no later assessment are left: the old status stands.

Each clearance is a manual entry carrying the SAME detail (value 'none'), so a
rebuild restores it to the right row. After writing, it checks the rows are
gone; if any remain, everything is rolled back.

DRY RUN by default; --apply to write.
"""
import os, re, sqlite3, sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "scripts")]
import paths
from import_status_review import apply_status, key_tiers, backup, CLEAR

LEG = ("threat_iucn_legacy", "rarity_legacy")
MOD = ("threat_iucn_2001", "rarity_modern")
APPLY = "--apply" in sys.argv


def year(d, src=""):
    s = str(d or "").strip()
    if re.fullmatch(r"\d{5}(\.0)?", s):
        return (date(1899, 12, 30) + timedelta(days=int(float(s)))).year
    m = re.match(r"(19|20)\d{2}", s)
    if m:
        return int(m.group(0))
    m = re.search(r"\b(19[5-9]\d|20[0-2]\d)\b", str(src or ""))
    return int(m.group(0)) if m else 0


codex = sqlite3.connect(str(paths.CODEX_DB)); c = codex.cursor()
u = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)
obs = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
name = lambda t: (u.execute("SELECT scientific_name FROM taxa WHERE tvk=?", (t,)).fetchone() or (t,))[0]

rows = defaultdict(list)                 # tvk -> [(track, value, detail, source, year)]
for t, tr, v, d, s, dd in c.execute("""SELECT tvk, status_track, status_value, status_detail, source, date_designated
                                       FROM status_summary WHERE status_track IN (?,?,?,?)""", LEG + MOD):
    rows[t].append((tr, v, d or "", s or "", year(dd, s)))
loaded = {t: s for t, s in c.execute("SELECT tvk, source_review FROM manual_entries WHERE added_by='review-load'")}
cleared = {t: s for t, s in c.execute("""SELECT tvk, source_review FROM manual_entries WHERE added_by IN
                                         ('review-withdrawal','superseded-legacy','old-name-superseded')""")}

plan = []
for t, rs in rows.items():
    legd = [r for r in rs if r[0] in LEG and r[2]]
    if not legd:
        continue
    mods = [r for r in rs if r[0] in MOD]
    for r in legd:
        later = [m for m in mods if m[4] > r[4] and m[3] != r[3]]
        why = ("review load: " + loaded[t][:60]) if t in loaded else \
              ("withdrawn/superseded: " + cleared[t][:55]) if t in cleared else \
              (f"newer status {later[0][1]} ({later[0][4]}): {later[0][3][:45]}") if later else None
        if why:
            plan.append((t, r, why))

def tiers(t, drop):
    vals = {}
    for tr, v, d, s, y in rows[t]:
        if (tr, v, d) in drop:
            continue
        if tr in vals and tr in LEG:
            continue
        vals[tr] = v
    return key_tiers(vals)

by_t = defaultdict(list)
for t, r, why in plan:
    by_t[t].append((r, why))
changes = Counter(); mine = []
recorded = {x for (x,) in obs.execute("SELECT DISTINCT species_tvk FROM assessment_records")}
surveys = defaultdict(list)
for t, p, d in obs.execute("""SELECT species_tvk, project_name, substr(date,1,4) FROM assessment_records
                              WHERE project_name IS NOT NULL AND project_name!=''"""):
    if t in by_t:
        surveys[f"{p} {d}"].append(t)
tier = lambda k, r: "Rare Key" if r else "Key" if k else "not key"
print("Clear legacy statuses stored with a detail -- " + ("APPLY" if APPLY else "DRY RUN"))
print("=" * 96)
print("  by detail:", dict(Counter(r[2] for t, r, w in plan)))
print("  by reason:", dict(Counter(w.split(':')[0] for t, r, w in plan)))
shown = 0
for t, items in by_t.items():
    drop = {(r[0], r[1], r[2]) for r, w in items}
    b, a = tiers(t, set()), tiers(t, drop)
    if b != a:
        changes[f"{tier(*b)} -> {tier(*a)}"] += 1
        if t in recorded:
            mine.append(name(t))
        if shown < 15:
            r, w = items[0]
            print(f"  {name(t)[:28]:28} {r[1]}/{r[2][:22]:<22} {tier(*b)} -> {tier(*a)}   [{w[:40]}]")
            shown += 1
print(f"\n  {len(plan)} legacy rows on {len(by_t)} species to clear")
print(f"  key standing changes: {dict(changes)}")
print(f"  ...of which in your records: {mine or 'none'}")
for s, ts in sorted(surveys.items()):
    print(f"  survey {s}: {', '.join(name(t) for t in ts)}")
if not APPLY or not plan:
    sys.exit("\n  DRY RUN -- nothing changed. Re-run with --apply.\n" if not APPLY else "  nothing to do")

print(f"  backup: {backup(paths.CODEX_DB, 'codex')}")
today = datetime.now().date().isoformat()
try:
    for t, (tr, v, d, s, y), why in plan:
        c.execute("""INSERT INTO manual_entries (tvk, species_name, status_track, status_value, status_detail,
                     source_review, date_added, added_by, notes, review_id)
                     VALUES (?,?,?,?,?,?,?,?,?,NULL)""",
                  (t, name(t), tr, CLEAR, d, why.split(": ", 1)[-1], today, "superseded-legacy-detail",
                   f"Old status {v} / {d} ({s[:60]}) superseded -- {why}"))
        apply_status(c, t, tr, CLEAR, d, why.split(": ", 1)[-1], today)
    left = [(t, tr, d) for t, (tr, v, d, s, y), why in plan if c.execute(
        "SELECT 1 FROM status_summary WHERE tvk=? AND status_track=? AND COALESCE(status_detail,'')=?",
        (t, tr, d)).fetchone()]
    if left:
        raise RuntimeError(f"{len(left)} rows still present after clearing, e.g. {left[:3]} -- "
                           "apply_status does not clear by detail")
    codex.commit()
except Exception as e:
    codex.rollback()
    sys.exit(f"  x FAILED, rolled back -- nothing changed: {e}")
print(f"  cleared {len(plan)} rows; verified gone\n")
