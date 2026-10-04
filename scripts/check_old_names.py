"""Old names still holding an old status, where the CURRENT name holds a newer one.

READ ONLY by default. --apply clears the old names' statuses listed, each as a
manual entry naming the newer source (value 'none' = status removed), so it
survives Codex rebuilds -- the same way as clear_stale_legacy.py.

For each species with only a legacy status (rarity_legacy / threat_iucn_legacy):
looks the name up in UKSI's synonym table; if it now points to a DIFFERENT
current TVK that holds a modern status (threat_iucn_2001 / rarity_modern), the
old name's status is a leftover duplicate -- the newer review assessed the
species under its current name.

Run:  python scripts\\check_old_names.py
"""
import os, sqlite3, sys
from datetime import datetime
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import paths

APPLY = "--apply" in sys.argv
sys.path.insert(0, os.path.join(ROOT, "scripts"))
c = sqlite3.connect(str(paths.CODEX_DB)) if APPLY else sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)
u = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)
st = {}
for t, tr, v, src in c.execute("""SELECT tvk, status_track, status_value, source FROM status_summary
        WHERE COALESCE(status_detail,'')='' AND status_track IN
        ('threat_iucn_2001','threat_iucn_legacy','rarity_modern','rarity_legacy')"""):
    st.setdefault(t, {})[tr] = (v, (src or "")[:50])
print("Old names holding an old status   READ ONLY")
print("=" * 96)
hits = 0
plan = []
for t, s in st.items():
    if any(k in s for k in ("threat_iucn_2001", "rarity_modern")):
        continue
    r = u.execute("SELECT scientific_name FROM taxa WHERE tvk=?", (t,)).fetchone()
    name = r[0] if r else None
    if not name:
        continue
    for (cur,) in u.execute("SELECT DISTINCT tvk FROM synonyms WHERE synonym=? AND tvk!=?", (name, t)):
        mod = {k: v for k, v in st.get(cur, {}).items() if k in ("threat_iucn_2001", "rarity_modern")}
        if mod:
            hits += 1
            cn = (u.execute("SELECT scientific_name FROM taxa WHERE tvk=?", (cur,)).fetchone() or (cur,))[0]
            old = ", ".join(f"{v[0]}" for k, v in s.items())
            new = ", ".join(f"{v[0]} ({v[1]})" for v in mod.values())
            print(f"  {name[:28]:28} old {old:<14} -> now {cn[:28]:28} {new[:60]}")
            src = max(mod.values(), key=lambda v: v[1])[1]
            plan.append((t, name, [k for k in s], cn, src))
print(f"\n  {hits} old name(s) whose current name already holds a newer status")
if not APPLY:
    sys.exit("READ ONLY -- nothing has been changed. Re-run with --apply to clear these.")
if not plan:
    sys.exit("  nothing to clear")
from import_status_review import apply_status, backup, CLEAR
print(f"  backup: {backup(paths.CODEX_DB, 'codex')}")
cur = c.cursor()
try:
    for t, name, tracks, cn, src in plan:
        for tr in tracks:
            cur.execute("""INSERT INTO manual_entries (tvk, species_name, status_track, status_value, status_detail,
                           source_review, date_added, added_by, notes, review_id)
                           VALUES (?,?,?,?,NULL,?,?,?,?,NULL)""",
                        (t, name, tr, CLEAR, src, datetime.now().date().isoformat(), "old-name-superseded",
                         f"Old name; assessed under its current name {cn} by {src}"))
            apply_status(cur, t, tr, CLEAR, None, src, "")
    c.commit()
except Exception as e:
    c.rollback()
    sys.exit(f"  x FAILED, rolled back: {type(e).__name__}: {e}")
print(f"  cleared {sum(len(p[2]) for p in plan)} old statuses on {len(plan)} old names")
