"""Which status reviews does Codex hold, and where does Pantheon know more?
READ ONLY.

  A. Every source behind Codex's INVERTEBRATE designations: rows, species,
     date, taxon groups -- i.e. which reviews JNCC's spreadsheet includes.
  B. Manually imported reviews (Codex reviews table).
  C. Coverage by order: species with a threat or rarity status in Codex vs in
     Pantheon (via the TVK bridge), and the gap -- species Pantheon gives a GB
     Red List / GB Status that Codex has no threat or rarity entry for.
  D. The gap by family (top 40), with examples -- the groups whose reviews are
     missing from Codex.

Run:  python scripts\\check_status_coverage.py | Out-File -FilePath status_coverage.txt -Encoding utf8
"""
import os, sqlite3, sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import paths

c = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)
p = sqlite3.connect(f"file:{paths.PANTHEON_DB}?mode=ro", uri=True)
u = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)


def short(s, n=78):
    s = str(s or "").replace("\n", " ")
    return s if len(s) <= n else s[:n] + "..."


print("Status coverage -- Codex vs Pantheon   READ ONLY")
print("=" * 90)

# ---------------------------------------------------------------- A
print("\nA. Sources behind Codex's invertebrate designations")
print(f"  {'rows':>5} {'spp':>5}  {'date':10}  source  [taxon groups]")
for src, n, spp, d, groups in c.execute("""
        SELECT source, COUNT(1), COUNT(DISTINCT tvk), MAX(substr(date_designated,1,10)),
               GROUP_CONCAT(DISTINCT taxon_group)
        FROM designations WHERE category = 'Invertebrate'
        GROUP BY source ORDER BY COUNT(1) DESC"""):
    g = ", ".join(sorted(set((groups or "").split(","))))
    print(f"  {n:>5} {spp:>5}  {str(d or ''):10}  {short(src, 70)}")
    print(f"  {'':24}[{short(g, 64)}]")

# ---------------------------------------------------------------- B
print("\nB. Manually imported reviews")
for r in c.execute("SELECT id, review_name, author, date_published, species_count, licence FROM reviews"):
    print(f"  #{r[0]} {short(r[1], 60)} | {r[2]} | {r[3]} | {r[4]} spp | {r[5]}")

# ---------------------------------------------------------------- C/D
TRACKS = ("threat_iucn_2001", "threat_iucn_legacy", "rarity_modern", "rarity_legacy")
codex_status = {t for (t,) in c.execute(
    f"SELECT DISTINCT tvk FROM status_summary WHERE status_track IN ({','.join('?' * len(TRACKS))}) "
    "AND status_value NOT IN ('LC','NE','NA','WL','DD')", TRACKS)}
bridge = dict(c.execute("SELECT pantheon_tvk, uksi_tvk FROM tvk_bridge"))

SKIP = {"none", "unknown", "not reviewed", "lc", "least concern", "ne", "na", ""}
pan_status = defaultdict(set)
for tvk, cat, ab in p.execute("""SELECT tvk, reporting_category, abbreviation FROM conservation_status
                                 WHERE reporting_category IN ('GB Status', 'GB Red List')"""):
    if str(ab or "").strip().lower() in SKIP:
        continue
    pan_status[bridge.get(tvk, tvk)].add(f"{ab}")

tax = {}
for uk in set(pan_status) | codex_status:
    r = u.execute('SELECT scientific_name, "order", family FROM taxa WHERE tvk=?', (uk,)).fetchone()
    tax[uk] = r or (uk, "?", "?")

by_order = defaultdict(lambda: [0, 0, 0])
gap_family = defaultdict(list)
for uk in codex_status:
    by_order[tax[uk][1] or "?"][0] += 1
for uk, vals in pan_status.items():
    o = tax[uk][1] or "?"
    by_order[o][1] += 1
    if uk not in codex_status:
        by_order[o][2] += 1
        gap_family[(o, tax[uk][2] or "?")].append(f"{tax[uk][0]} ({'/'.join(sorted(vals))})")

print("\nC. Species with a threat or rarity status, by order (invertebrates in Pantheon)")
print(f"  {'order':<22} {'Codex':>6} {'Pantheon':>9} {'Pantheon-only':>14}")
for o, (nc, np_, gap) in sorted(by_order.items(), key=lambda kv: -kv[1][2]):
    if np_:
        print(f"  {str(o)[:22]:<22} {nc:>6} {np_:>9} {gap:>14}")
tot_gap = sum(v[2] for v in by_order.values())
print(f"  {'TOTAL Pantheon-only':<22} {'':>6} {'':>9} {tot_gap:>14}")

print("\nD. Where the gap is -- families, largest first (examples)")
for (o, f), spp in sorted(gap_family.items(), key=lambda kv: -len(kv[1]))[:40]:
    print(f"  {len(spp):>4}  {o} / {f}: {short('; '.join(spp[:4]), 80)}")

print("\nNotes: 'Codex' counts threat/rarity statuses other than LC/NE/NA/WL/DD.")
print("'Pantheon-only' = Pantheon gives a GB Red List or GB Status Codex has no")
print("threat or rarity entry for. Pantheon is frozen at 2017; a Pantheon-only")
print("status may be one a newer review removed -- check before importing anything.")
print("\nREAD ONLY -- nothing has been changed.")
