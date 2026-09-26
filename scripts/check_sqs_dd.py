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

print(f'{"case":34} {"count":>6}  derived scores')
for label, test in [
    ("NT only (no rarity)",      lambda t: "NT" in t.values() and not any(
        k.startswith("rarity") for k in t)),
    ("DD only (no rarity)",      lambda t: "DD" in t.values() and not any(
        k.startswith("rarity") for k in t)),
    ("DD with rarity",           lambda t: "DD" in t.values() and any(
        k.startswith("rarity") for k in t)),
]:
    hits = [t for tvk in invert - stored
            for t in [tracks.get(tvk, {})] if test(t)]
    scores = {}
    for t in hits:
        s = derive_from_tracks(t)
        scores[s] = scores.get(s, 0) + 1
    print(f'{label:34} {len(hits):>6}  {dict(sorted(scores.items()))}')
