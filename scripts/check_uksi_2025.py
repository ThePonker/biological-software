"""Checks on data\\uksi_2025.db before switching it in.   READ ONLY

 1. duplicate current species names in taxa (homonyms across kingdoms, or a fault?)
 2. old names (current uksi.db taxa + synonyms) no longer searchable in the new file
 3. everything keyed by TVK that is not a current taxon in the new file:
      observatum: observations, specimens, recording_scheme, species_profiles (your own)
      codex: manual_entries (review statuses), species_profiles (review accounts),
             status_summary, sqs_scores
    -> mappable (name_map) or not, with names

  python scripts\\check_uksi_2025.py
"""
import os, sqlite3, sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import paths

NEW = os.path.join(os.path.dirname(str(paths.UKSI_DB)), "uksi_2025.db")
if not os.path.exists(NEW):
    sys.exit("  x uksi_2025.db not found -- run build_uksi_from_release.py first")
n = sqlite3.connect(f"file:{NEW}?mode=ro", uri=True)
old = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)
cur = {t: (s, k, o, f) for t, s, k, o, f in n.execute("SELECT tvk, scientific_name, kingdom, [order], family FROM taxa")}
nmap = {t: r for t, r in n.execute("SELECT tvk, recommended_tvk FROM name_map")}
oldname = {t: s for t, s in old.execute("SELECT tvk, scientific_name FROM taxa")}


try:
    remap = {a: b for a, b in n.execute("SELECT old_tvk, new_tvk FROM tvk_remap")}
except sqlite3.Error:
    remap = None


def to_cur(t, d=0):
    """the replacement the switchover will use (tvk_remap: name map, then exact unique name)"""
    if t in cur:
        return t
    if remap is not None:
        return remap.get(t)
    if d > 4 or t not in nmap or nmap[t] == t:
        return None
    return to_cur(nmap[t], d + 1)


print("uksi_2025.db checks   READ ONLY")
print("=" * 90)
print("\n 1. DUPLICATE CURRENT SPECIES NAMES")
d = list(n.execute("""SELECT scientific_name, GROUP_CONCAT(tvk || ' ' || COALESCE(kingdom,'?') || '/' || COALESCE([order],'?') || '/' || COALESCE(family,'?'), '  |  ')
                      FROM taxa WHERE lower(rank)='species' GROUP BY lower(scientific_name) HAVING COUNT(1)>1"""))
kingdoms = Counter()
for nm, tv in d:
    ks = {p.split(' ')[1].split('/')[0] for p in tv.split('  |  ')}
    kingdoms["across kingdoms (homonym)" if len(ks) > 1 else "same kingdom"] += 1
print(f"    {len(d)} names: {dict(kingdoms)}")
for nm, tv in d[:40]:
    print(f"      {nm[:34]:34} {tv[:120]}")

print("\n 2. OLD NAMES NO LONGER SEARCHABLE")
newnames = {s.lower() for (s,) in n.execute("SELECT scientific_name FROM taxa")} | \
           {s.lower() for (s,) in n.execute("SELECT synonym FROM synonyms")}
lost = Counter(); ex = []
for nm, t, src in list(old.execute("SELECT scientific_name, tvk, 'taxa' FROM taxa")) + list(old.execute("SELECT synonym, tvk, 'synonyms' FROM synonyms")):
    if nm and nm.lower() not in newnames:
        k = old.execute("SELECT kingdom, rank FROM taxa WHERE tvk=?", (t,)).fetchone() if src == "synonyms" else None
        lost[src] += 1
        if len(ex) < 400:
            ex.append((nm, t, src))
print(f"    old names not findable in the new file: {dict(lost)}")
ranks = Counter((old.execute("SELECT rank FROM taxa WHERE tvk=?", (t,)).fetchone() or ['(synonym target gone)'])[0] for nm, t, s in ex)
print(f"    (sample by rank of the old taxon: {ranks.most_common(6)})")
anim = [(nm, t, s) for nm, t, s in ex if (old.execute("SELECT kingdom FROM taxa WHERE tvk=?", (t,)).fetchone() or [''])[0] == "Animalia"]
print(f"    animal examples ({len(anim)} in this sample):")
for nm, t, s in anim[:15]:
    print(f"      {nm[:40]:40} {t} ({s})")

print("\n 3. TVK-KEYED DATA NOT ON A CURRENT TAXON")
o = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
c = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)
targets = [(o, "observatum", "observations", "species_tvk"), (o, "observatum", "specimens", "species_tvk"),
           (o, "observatum", "recording_scheme", "species_tvk"), (o, "observatum", "species_profiles", "species_tvk"),
           (c, "codex", "manual_entries", "tvk"), (c, "codex", "species_profiles", "tvk"),
           (c, "codex", "status_summary", "tvk"), (c, "codex", "sqs_scores", "tvk")]
for db, dbn, tbl, col in targets:
    try:
        rows = list(db.execute(f"SELECT {col}, COUNT(1) FROM {tbl} WHERE COALESCE({col},'')!='' GROUP BY {col}"))
    except sqlite3.Error as e:
        print(f"    {dbn}.{tbl}: not checked ({e})"); continue
    bad = [(t, k) for t, k in rows if t not in cur]
    mp = [(t, k) for t, k in bad if to_cur(t)]
    nomap = [(t, k) for t, k in bad if not to_cur(t)]
    print(f"    {dbn}.{tbl:<17} TVKs {len(rows):>6}   not current {len(bad):>4} (rows {sum(k for _, k in bad):>5})"
          f"   map {len(mp):>4}   no mapping {len(nomap):>4}")
    if tbl in ("observations", "specimens", "recording_scheme", "manual_entries", "species_profiles"):
        for t, k in nomap[:10]:
            print(f"        no mapping: {oldname.get(t, '?')[:36]:36} {t}  rows {k}")
print("\nREAD ONLY -- nothing has been changed.")
