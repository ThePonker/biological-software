"""After the Codex rebuild: did the new schema land, and did everything survive?
READ ONLY. Nothing is written.

Run:  python scripts\\check_codex_after_profiles_patch.py
"""
import os, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import paths

c = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)
ok = True


def check(label, cond, detail=""):
    global ok
    ok &= bool(cond)
    print(f"  {'ok' if cond else 'XX'}  {label}{('   ' + detail) if detail else ''}")


print("Codex after the profiles schema patch  --  READ ONLY")
print("=" * 72)

cols = {r[1]: r for r in c.execute("PRAGMA table_info(species_profiles)")}
pk = sorted((r[5], r[1]) for r in cols.values() if r[5])
check("species_profiles has review_id and species_name",
      "review_id" in cols and "species_name" in cols)
check("species_profiles keyed on (tvk, review_id)",
      [n for _, n in pk] == ["tvk", "review_id"], str([n for _, n in pk]))
check("review_id is NOT NULL", "review_id" in cols and cols["review_id"][3] == 1)

rcols = [r[1] for r in c.execute("PRAGMA table_info(reviews)")]
check("reviews has licence", "licence" in rcols)

reviews = c.execute("SELECT id, review_name FROM reviews ORDER BY id").fetchall()
check("NECR702 review still id 1",
      any(i == 1 and "NECR702" in (n or "") for i, n in reviews),
      "; ".join(f"{i}: {(n or '')[:40]}" for i, n in reviews))

me = c.execute("SELECT COUNT(1) FROM manual_entries").fetchone()[0]
check("manual_entries preserved", me == 1148, f"{me} (expected 1148)")

orphans = c.execute("""SELECT COUNT(1) FROM manual_entries
                       WHERE review_id IS NOT NULL
                         AND review_id NOT IN (SELECT id FROM reviews)""").fetchone()[0]
check("every manual entry's review_id points at a real review", orphans == 0,
      f"{orphans} orphaned")

dup = c.execute("""SELECT COUNT(1) FROM (SELECT tvk, status_track, COALESCE(status_detail,'')
                   FROM status_summary GROUP BY 1,2,3 HAVING COUNT(1) > 1)""").fetchone()[0]
check("no duplicated (tvk, track, detail) in status_summary", dup == 0, str(dup))

zs = c.execute("""SELECT s.status_track, s.status_value, s.origin FROM status_summary s
                  WHERE s.tvk = (SELECT tvk FROM manual_entries
                                 WHERE species_name LIKE 'Zeugophora subspinosa%' LIMIT 1)
                    AND s.origin = 'manual'""").fetchall()
print(f"      Zeugophora subspinosa: {zs}")

n = c.execute("SELECT COUNT(1) FROM species_profiles").fetchone()[0]
print(f"      species_profiles rows: {n} (0 expected until the accounts are moved)")

print("\n" + ("All checks pass." if ok else "SOMETHING FAILED -- restore the pre-rebuild backup."))
print("READ ONLY -- nothing has been changed.")
