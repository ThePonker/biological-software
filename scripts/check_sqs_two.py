import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3, paths
from shared.sqs_derivation import derive_from_tracks

c = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)

invert = {r[0] for r in c.execute(
    "SELECT DISTINCT tvk FROM designations WHERE category='Invertebrate'")}
stored = {r[0] for r in c.execute("SELECT tvk FROM sqs_scores")}

tracks = {}
for tvk, tr, val in c.execute(
        "SELECT tvk, status_track, status_value FROM status_summary"):
    tracks.setdefault(tvk, {})[tr] = val

n_nt = twos = 0
examples = []
for tvk in invert:
    if tvk in stored:
        continue                      # Pantheon published a score; not derived
    t = tracks.get(tvk, {})
    if t.get("threat_iucn_2001") == "NT":
        n_nt += 1
    if derive_from_tracks(t) == 2:
        twos += 1
        if len(examples) < 12:
            nm = c.execute("SELECT species_name FROM designations WHERE tvk=? LIMIT 1",
                           (tvk,)).fetchone()
            examples.append((nm[0] if nm else tvk,
                             {k: v for k, v in t.items()
                              if k.startswith(("rarity", "threat"))}))

print("invertebrates with no Pantheon score:", len(invert - stored))
print("  of those, NT on threat_iucn_2001:", n_nt)
print("  of those, DERIVED SQS = 2:", twos, " <-- a value Pantheon never uses")
for nm, t in examples:
    print("   ", nm, t)
