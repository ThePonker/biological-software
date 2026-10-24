"""Codex Loaded Reviews: count species live instead of showing the stored number.

reviews.species_count is written once, and only by Codex Manager's import screen,
so every review registered another way (the NECR account reviews) shows 0.
get_reviews() / get_review() now return species_count = distinct species linked to
the review through statuses (manual_entries) or accounts (species_profiles).
If either table lacks review_id (an old codex.db), it falls back to the stored number.

  py -3.14 scripts\\patch_review_species_live.py      (refuses a second run; keeps .bak)
"""
import os, py_compile, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.join(ROOT, "shared", "repositories", "codex_repository.py")
MARK = "_LIVE_SPECIES_COUNT"

OLD_LIST = '''            c.execute("""SELECT id, review_name, author, taxon_group,
                                status_track, date_published, date_imported,
                                source_file, species_count, supersedes_id, notes
                         FROM reviews ORDER BY id""")
            return [dict(r) for r in c.fetchall()]
        except sqlite3.OperationalError:
            return []
'''
NEW_LIST = '''            try:
                c.execute(f"""SELECT id, review_name, author, taxon_group,
                                status_track, date_published, date_imported,
                                source_file, {_LIVE_SPECIES_COUNT} AS species_count,
                                supersedes_id, notes
                         FROM reviews ORDER BY id""")
            except sqlite3.OperationalError:      # old codex.db: stored count
                c.execute("""SELECT id, review_name, author, taxon_group,
                                status_track, date_published, date_imported,
                                source_file, species_count, supersedes_id, notes
                         FROM reviews ORDER BY id""")
            return [dict(r) for r in c.fetchall()]
        except sqlite3.OperationalError:
            return []
'''
OLD_ONE = '''            c.execute("""SELECT id, review_name, author, taxon_group,
                                status_track, date_published, date_imported,
                                source_file, species_count, supersedes_id, notes
                         FROM reviews WHERE id = ?""", (review_id,))
'''
NEW_ONE = '''            try:
                c.execute(f"""SELECT id, review_name, author, taxon_group,
                                status_track, date_published, date_imported,
                                source_file, {_LIVE_SPECIES_COUNT} AS species_count,
                                supersedes_id, notes
                         FROM reviews WHERE id = ?""", (review_id,))
            except sqlite3.OperationalError:      # old codex.db: stored count
                c.execute("""SELECT id, review_name, author, taxon_group,
                                status_track, date_published, date_imported,
                                source_file, species_count, supersedes_id, notes
                         FROM reviews WHERE id = ?""", (review_id,))
'''
OLD_HDR = '''    # ================================================================
    # Reviews
    # ================================================================
'''
NEW_HDR = OLD_HDR + '''
# species linked to a review by status or account -- the stored reviews.species_count
# is only set by Codex Manager's import screen, so it reads 0 for most reviews
_LIVE_SPECIES_COUNT = """(SELECT COUNT(*) FROM (
        SELECT tvk FROM manual_entries m WHERE m.review_id = reviews.id
        UNION
        SELECT COALESCE(tvk, species_name) FROM species_profiles p
        WHERE p.review_id = reviews.id))"""

'''

raw = open(REPO, "rb").read().decode("utf-8")
crlf = "\r\n" in raw
text = raw.replace("\r\n", "\n")
if MARK in text:
    sys.exit("  already patched -- nothing done")
for label, old in (("get_reviews", OLD_LIST), ("get_review", OLD_ONE), ("Reviews header", OLD_HDR)):
    n = text.count(old)
    if n != 1:
        sys.exit(f"  x {label}: anchor found {n} times, expected 1 -- nothing written")

# the constant must sit at module level: put it just before the class's Reviews section
# is inside the class, so instead insert it before the first 'class ' line
text = text.replace(OLD_LIST, NEW_LIST).replace(OLD_ONE, NEW_ONE)
const = NEW_HDR[len(OLD_HDR):]
i = text.find("\nclass ")
if i < 0:
    sys.exit("  x no class definition found -- nothing written")
text = text[:i + 1] + const.lstrip("\n") + "\n" + text[i + 1:]

tmp = REPO + ".tmp"
open(tmp, "wb").write((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
try:
    py_compile.compile(tmp, cfile=os.path.join(os.environ.get("TEMP", "."), "lv.pyc"), doraise=True)
except py_compile.PyCompileError as e:
    os.remove(tmp)
    sys.exit(f"  x would not compile -- nothing written: {e}")
shutil.copy2(REPO, REPO + ".bak")
os.replace(tmp, REPO)
print(f"  wrote {os.path.relpath(REPO, ROOT)}")

# exercise it against the real codex.db
sys.path.insert(0, ROOT)
import paths, sqlite3
from shared.repositories import codex_repository as cr
con = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)
rows = con.execute(f"SELECT id, species_count, {cr._LIVE_SPECIES_COUNT} FROM reviews ORDER BY id").fetchall()
zero = [r[0] for r in rows if not r[2]]
print(f"  check: {len(rows)} reviews, {sum(1 for r in rows if not r[1])} stored as 0, "
      f"{len(zero)} with a live count of 0" + (f" (ids {zero})" if zero else ""))
