"""Undo withdrawals that hit a different species than the report named.  4 Oct 2026.

withdraw_statuses.py resolved NECR217's 'Taxonomy' exclusions through UKSI
synonyms to CURRENT species the same review had assessed, and cleared their new
statuses (e.g. Chlorops citrinellus -> Chlorops rufinus, NS cleared). A
withdrawal's stored species name is the resolved name; any whose name is not one
the scripts list is one of these. For each:
  * delete its 'review-withdrawal' manual entries
  * re-apply every remaining manual entry for that TVK (review loads), in order

DRY RUN by default; --apply to write.
"""
import os, sqlite3, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "scripts")]
import paths
from import_status_review import apply_status, backup
import importlib.util
spec = importlib.util.spec_from_file_location("w", os.path.join(ROOT, "scripts", "withdraw_statuses.py"))
listed = set()
src = open(os.path.join(ROOT, "scripts", "withdraw_statuses.py"), encoding="utf-8").read()
import re
listed = set(re.findall(r'"([A-Z][a-z]+ [a-z]+)": \(', src))      # every entry, wherever on the line
APPLY = "--apply" in sys.argv
codex = sqlite3.connect(str(paths.CODEX_DB)); c = codex.cursor()
wrong = c.execute("""SELECT DISTINCT tvk, species_name FROM manual_entries
                     WHERE added_by='review-withdrawal'""").fetchall()
wrong = [(t, n) for t, n in wrong if n not in listed]
print("Undo withdrawals of the wrong species -- " + ("APPLY" if APPLY else "DRY RUN"))
print("=" * 70)
for t, n in wrong:
    keep = c.execute("""SELECT status_track, status_value, source_review, date_added FROM manual_entries
                        WHERE tvk=? AND COALESCE(added_by,'')!='review-withdrawal' ORDER BY id""", (t,)).fetchall()
    print(f"  {n:<28} restore: {', '.join(f'{k}={v}' for k, v, s, d in keep) or 'nothing (JNCC only)'}")
print(f"\n  {len(wrong)} species")
if not APPLY or not wrong:
    sys.exit("\n  DRY RUN -- nothing changed. Re-run with --apply.\n" if not APPLY else "")
print(f"  backup: {backup(paths.CODEX_DB, 'codex')}")
try:
    for t, n in wrong:
        c.execute("DELETE FROM manual_entries WHERE tvk=? AND added_by='review-withdrawal'", (t,))
        for tr, v, s, d in c.execute("""SELECT status_track, status_value, source_review, date_added
                                        FROM manual_entries WHERE tvk=? ORDER BY id""", (t,)).fetchall():
            apply_status(c, t, tr, v, None, s, d)
    codex.commit()
except Exception as e:
    codex.rollback(); sys.exit(f"  x FAILED, rolled back: {e}")
for t, n in wrong:
    now = c.execute("""SELECT status_track, status_value FROM status_summary WHERE tvk=? AND status_track IN
                       ('threat_iucn_2001','rarity_modern','threat_iucn_legacy','rarity_legacy')""", (t,)).fetchall()
    print(f"  {n:<28} now: {', '.join(f'{k}={v}' for k, v in now) or 'no threat/rarity status'}")
