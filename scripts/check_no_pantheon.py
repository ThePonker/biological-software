"""Why do these species show "no Pantheon data"?  READ ONLY.

For every species in a project with no Pantheon score, biotope or habitat:
  - the TVK(s) on the records
  - UKSI: is that TVK current?  its name and rank; other TVKs for the same name
  - the TVK bridge: is that TVK (or the current one) a bridge target?
  - Pantheon's species table: is the NAME there, and under which TVK?
Then a verdict per species: genuinely absent from Pantheon, or present but
not linked (and why).

Run:  python scripts\\check_no_pantheon.py "Birmingham - Wheels Park" 2026
"""
import os, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "Observatum")]
import paths

project = sys.argv[1] if len(sys.argv) > 1 else "Birmingham - Wheels Park"
year = sys.argv[2] if len(sys.argv) > 2 else "2026"

o = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
u = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)
c = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)
p = sqlite3.connect(f"file:{paths.PANTHEON_DB}?mode=ro", uri=True)

pcols = [r[1] for r in p.execute("PRAGMA table_info(species)")]
name_col = next((x for x in ("species", "species_name", "scientific_name", "name") if x in pcols), None)
tvk_col = "tvk" if "tvk" in pcols else None
print(f"No-Pantheon check -- {project} {year}   READ ONLY")
print("=" * 78)
print(f"  pantheon.species columns: {pcols}  (name={name_col}, tvk={tvk_col})")

recs = o.execute("""SELECT species_name, species_tvk, COUNT(1) FROM assessment_records
                    WHERE project_name=? AND substr(date,1,4)=? AND species_tvk IS NOT NULL
                    GROUP BY 1,2""", (project, year)).fetchall()
tvks = {t for _, t, _ in recs}

bridged = {}
for pan, uk in c.execute("SELECT pantheon_tvk, uksi_tvk FROM tvk_bridge"):
    bridged.setdefault(uk, []).append(pan)
pan_sqs = {r[0] for r in p.execute("SELECT tvk FROM sqs_scores")}
pan_bio = {r[0] for r in p.execute("SELECT tvk FROM broad_biotope")}
pan_hab = {r[0] for r in p.execute("SELECT tvk FROM habitats")}


def has_pantheon(uk):
    pans = bridged.get(uk, [])
    return any(t in pan_sqs or t in pan_bio or t in pan_hab for t in pans)


missing = [(n, t, k) for n, t, k in recs if not has_pantheon(t)]
print(f"  species in project: {len(tvks)}   with no Pantheon data through the bridge: {len(missing)}\n")

verdicts = {}
for name, tvk, n in sorted(missing):
    print(f"  {name}  [{tvk}]  x{n}")
    t = u.execute("SELECT scientific_name, rank FROM taxa WHERE tvk=?", (tvk,)).fetchone()
    print(f"    UKSI: {'current' if t else 'NOT a current TVK'}{(' -- ' + t[0] + ', ' + str(t[1])) if t else ''}")
    others = [r[0] for r in u.execute("SELECT tvk FROM taxa WHERE scientific_name=? AND tvk!=?", (name, tvk))]
    syn = [r[0] for r in u.execute("SELECT tvk FROM synonyms WHERE synonym=?", (name,))]
    if others or syn:
        print(f"    UKSI other TVKs for this name: taxa {others}  synonyms -> {syn}")
    print(f"    bridge: {bridged.get(tvk) or 'no entry targets this TVK'}")
    hits = []
    if name_col:
        genus_sp = " ".join(name.split()[:2])
        hits = p.execute(f"SELECT {tvk_col or 'NULL'}, {name_col} FROM species "
                         f"WHERE {name_col} = ? OR {name_col} LIKE ?",
                         (name, genus_sp + "%")).fetchall()
    print(f"    Pantheon species by name: {hits or 'none'}")
    for ptvk, pname in hits:
        if ptvk:
            inb = c.execute("SELECT uksi_tvk, match_method FROM tvk_bridge WHERE pantheon_tvk=?",
                            (ptvk,)).fetchall()
            print(f"      {ptvk}: sqs={ptvk in pan_sqs} biotope={ptvk in pan_bio}  bridge -> {inb or 'NOT BRIDGED'}")
    if not hits:
        v = "absent from Pantheon"
    elif any(c.execute("SELECT 1 FROM tvk_bridge WHERE pantheon_tvk=?", (h[0],)).fetchone() for h in hits if h[0]):
        v = "IN PANTHEON, bridged to a different TVK than the records use"
    else:
        v = "IN PANTHEON, not in the bridge"
    verdicts[v] = verdicts.get(v, 0) + 1
    print(f"    => {v}\n")

print("Summary:")
for v, k in sorted(verdicts.items(), key=lambda kv: -kv[1]):
    print(f"  {k:>3}  {v}")
print("\nREAD ONLY -- nothing has been changed.")
