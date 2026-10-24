"""Codex Loaded Reviews: why do so many show 0 species?  READ ONLY.

The Species column shows reviews.species_count, a number stored when a review is
registered. This compares it with what is actually linked to each review:
  statuses  -- distinct species in manual_entries with that review_id
  accounts  -- distinct species in species_profiles with that review_id
  by name   -- distinct species in status_summary whose source names the review's NECR number

Run:  py -3.14 scripts\\check_review_counts.py
"""
import os, re, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import paths

con = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)


def cols(t):
    return {r[1] for r in con.execute(f"PRAGMA table_info({t})")}


me_ok = "review_id" in cols("manual_entries")
sp_ok = "review_id" in cols("species_profiles")
ss_ok = "source" in cols("status_summary")
print(f"links available: manual_entries.review_id={me_ok}  species_profiles.review_id={sp_ok}  "
      f"status_summary.source={ss_ok}")
print()
print(f"{'id':>3} {'stored':>6} {'statuses':>8} {'accounts':>8} {'by name':>7}  track         review")
print("-" * 110)
for r in con.execute("SELECT id, review_name, status_track, species_count FROM reviews ORDER BY id"):
    rid, name, track, stored = r
    st = con.execute("SELECT COUNT(DISTINCT tvk) FROM manual_entries WHERE review_id=?",
                     (rid,)).fetchone()[0] if me_ok else "-"
    ac = con.execute("SELECT COUNT(DISTINCT COALESCE(tvk, species_name)) FROM species_profiles "
                     "WHERE review_id=?", (rid,)).fetchone()[0] if sp_ok else "-"
    m = re.search(r"NECR\s*0*(\d+)", name or "", re.I)
    bn = "-"
    if ss_ok and m:
        bn = con.execute("SELECT COUNT(DISTINCT tvk) FROM status_summary WHERE source LIKE ?",
                         (f"%NECR%{m.group(1)}%",)).fetchone()[0]
    print(f"{rid:>3} {stored if stored is not None else '':>6} {st:>8} {ac:>8} {bn:>7}  "
          f"{(track or '')[:12]:<12}  {(name or '')[:60]}")
print("\nREAD ONLY -- nothing has been changed.")
