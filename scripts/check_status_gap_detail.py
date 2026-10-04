"""Why does Pantheon have a status Codex lacks?  READ ONLY.

For every species where Pantheon gives a GB Red List / GB Status (not LC/None)
and Codex has no threat/rarity status other than LC/NE/NA/WL/DD:

  MISSING      Codex holds no designation for the species at all
               -> a review JNCC's spreadsheet does not include
  SUPERSEDED   Codex holds an assessment (LC, NE, DD ...) in a threat/rarity
               track -> a newer review reassessed it; Codex is right
  DROPPED      Codex holds designation rows, but none reaches a threat/rarity
               track -> lost in the build (shows which codes)
  OTHER        designations reach only other tracks (priority, legal ...)

Run:  python scripts\\check_status_gap_detail.py | Out-File -FilePath status_gap_detail.txt -Encoding utf8
"""
import os, sqlite3, sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import paths

c = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)
p = sqlite3.connect(f"file:{paths.PANTHEON_DB}?mode=ro", uri=True)
u = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)

TR = ("threat_iucn_2001", "threat_iucn_legacy", "rarity_modern", "rarity_legacy")
WEAK = ("LC", "NE", "NA", "WL", "DD")
SKIP = {"none", "unknown", "not reviewed", "lc", "least concern", "ne", "na", ""}

bridge = dict(c.execute("SELECT pantheon_tvk, uksi_tvk FROM tvk_bridge"))
pan = defaultdict(set)
for tvk, ab in p.execute("""SELECT tvk, abbreviation FROM conservation_status
                            WHERE reporting_category IN ('GB Status','GB Red List')"""):
    if str(ab or "").strip().lower() not in SKIP:
        pan[bridge.get(tvk, tvk)].add(ab)

strong = {t for (t,) in c.execute(
    f"SELECT DISTINCT tvk FROM status_summary WHERE status_track IN ({','.join('?'*4)}) "
    f"AND status_value NOT IN ({','.join('?'*5)})", TR + WEAK)}

cats = defaultdict(list)
dropped_codes = Counter()
dropped_sources = Counter()
superseded_by = Counter()
for uk, vals in pan.items():
    if uk in strong:
        continue
    t = u.execute('SELECT scientific_name, "order", family FROM taxa WHERE tvk=?', (uk,)).fetchone() \
        or (uk, "?", "?")
    des = c.execute("""SELECT designation_abbreviation, source FROM designations WHERE tvk=?""",
                    (uk,)).fetchall()
    weak = c.execute(f"""SELECT status_track, status_value, source FROM status_summary
                         WHERE tvk=? AND status_track IN ({','.join('?'*4)})""",
                     (uk,) + TR).fetchall()
    tracks = {r[0] for r in c.execute("SELECT status_track FROM status_summary WHERE tvk=?", (uk,))}
    if not des:
        cat = "MISSING"
    elif weak:
        cat = "SUPERSEDED"
        for tr, v, s in weak:
            superseded_by[f"{v}  {str(s)[:60]}"] += 1
    elif not (tracks & set(TR)):
        threatish = [a for a, s in des if a and any(k in a for k in
                     ("NS", "NR", "Na", "Nb", "RDB", "Notable", "RedList", "Red"))]
        if threatish:
            cat = "DROPPED"
            for a, s in des:
                dropped_codes[a] += 1
                dropped_sources[str(s)[:70]] += 1
        else:
            cat = "OTHER"
    else:
        cat = "OTHER"
    cats[cat].append((t[1] or "?", t[2] or "?", t[0], "/".join(sorted(vals))))

print("Pantheon-only statuses, explained   READ ONLY")
print("=" * 86)
for k in ("MISSING", "SUPERSEDED", "DROPPED", "OTHER"):
    print(f"  {k:<11} {len(cats[k]):>5}")

for k in ("DROPPED", "MISSING", "SUPERSEDED", "OTHER"):
    rows = cats[k]
    if not rows:
        continue
    print("\n" + "-" * 86)
    print(f"{k}: {len(rows)} species, by order / family")
    fam = Counter((o, f) for o, f, _, _ in rows)
    ex = defaultdict(list)
    for o, f, n, v in rows:
        ex[(o, f)].append(f"{n} ({v})")
    for (o, f), n in fam.most_common(25):
        print(f"  {n:>4}  {o} / {f}: {'; '.join(ex[(o, f)][:3])[:90]}")
    if k == "DROPPED":
        print("\n  Designation codes these species carry (none reaches a track):")
        for a, n in dropped_codes.most_common(15):
            print(f"    {n:>5}  {a}")
        print("  From sources:")
        for s, n in dropped_sources.most_common(10):
            print(f"    {n:>5}  {s}")
    if k == "SUPERSEDED":
        print("\n  Codex's current assessment, and its source:")
        for s, n in superseded_by.most_common(12):
            print(f"    {n:>5}  {s}")

print("\nREAD ONLY -- nothing has been changed.")
