import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sqlite3, paths
import import_status_review as m

_, _, rows = m.read_review(r"data\reviews\NECR702_Chrysomelidae_2026.xlsx")
uksi = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)
hits = {}
for r in rows:
    iucn, _ = m.normalise_iucn(r["iucn_raw"])
    if iucn is None:
        continue
    res = m.resolve(uksi, r["name"], r["tvk"])
    if res:
        hits.setdefault(res[0], []).append((r["name"], r["tvk"], iucn,
                                            m.normalise_rarity(r["rarity_raw"]), res[1]))

codex = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)
clash = {t: v for t, v in hits.items() if len(v) > 1}
print(f"UKSI species reached by more than one review row: {len(clash)}")
for tvk, v in clash.items():
    print(f"\n  UKSI {tvk}  {v[0][4]}")
    for name, rtvk, iucn, rar, _ in v:
        print(f"    review row: {name:32} {rtvk:18} {iucn:3} {rar}")
    now = codex.execute("SELECT status_track, status_value FROM status_summary "
                        "WHERE tvk=? AND status_track IN ('threat_iucn_2001','rarity_modern')",
                        (tvk,)).fetchall()
    print(f"    Codex now holds: {now}")
