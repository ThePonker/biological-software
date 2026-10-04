"""Which species in YOUR records now have a review account?  READ ONLY.

For every review with accounts in Codex: how many of its accounts are for
species you have recorded (observations, contributed records, specimens), and
up to 6 of them, most-recorded first -- good candidates to open in Observatum.

Run:  python scripts\\list_account_species.py
"""
import os, sqlite3, sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import paths

obs = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
n = Counter()
for (t,) in obs.execute("SELECT species_tvk FROM assessment_records WHERE species_tvk IS NOT NULL"):
    n[t] += 1
for (t,) in obs.execute("SELECT species_tvk FROM specimens WHERE species_tvk IS NOT NULL"):
    n[t] += 1

c = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)
print("Species in your records with a review account   READ ONLY")
print("=" * 90)
for rid, name, author, date in c.execute(
        "SELECT id, review_name, author, substr(date_published,1,4) FROM reviews ORDER BY id"):
    rows = c.execute("SELECT tvk, species_name FROM species_profiles WHERE review_id=?", (rid,)).fetchall()
    if not rows:
        continue
    mine = sorted(((n[t], s) for t, s in rows if n[t]), reverse=True)
    print(f"\n#{rid} {author.split(',')[0] if author else ''} {date}  {name[:60]}")
    print(f"    {len(rows)} accounts, {len(mine)} for species in your records")
    if mine:
        print("    e.g. " + ", ".join(f"{s} ({k})" for k, s in mine[:6]))
print("\n(number in brackets = your records of that species)\nREAD ONLY -- nothing has been changed.")
