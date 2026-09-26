"""Patch build_codex_db.py -- review accounts, review licence, stable review ids.

  1. species_profiles: keyed on (tvk, review_id) so a species can hold one
     account per review; review_id NOT NULL DEFAULT 0 (0 = not from a review)
     -- never NULL, because SQLite treats NULLs as distinct in a composite key.
     Adds species_name for auditing.
  2. reviews: gains a licence column.
  3. Preservation across rebuild now carries reviews.id explicitly. Before this,
     restored reviews were renumbered by AUTOINCREMENT, which would silently
     re-point manual_entries.review_id and supersedes_id after any deletion.
  4. Preservation of species_profiles carries the new columns; an older codex.db
     without them restores with review_id 0 and species_name NULL.

Line-based, mixed-line-ending safe. Writes NOTHING unless every marker is found
exactly once. Backs up to build_codex_db.py.bak_profiles.

Run:  python scripts\\patch_codex_profiles_schema.py
Undo: copy scripts\\build_codex_db.py.bak_profiles over scripts\\build_codex_db.py
"""
import ast, io, os, py_compile, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "scripts", "build_codex_db.py")

raw = io.open(P, "rb").read()
text = raw.decode("utf-8-sig")
lines = text.split("\n")          # each line keeps any trailing \r
bom = raw.startswith(b"\xef\xbb\xbf")

problems = []
edits = []                        # (start, end_inclusive, new_lines, name)


def find_one(pred, name, lo=0, hi=None):
    hi = len(lines) if hi is None else hi
    hits = [i for i in range(lo, hi) if pred(lines[i])]
    if len(hits) != 1:
        problems.append(f"{name}: found {len(hits)} times")
        return None
    return hits[0]


def find_after(start, pred, name, span=15):
    if start is None:
        return None
    for i in range(start, min(len(lines), start + span)):
        if pred(lines[i]):
            return i
    problems.append(f"{name}: end marker not found within {span} lines")
    return None


def indent_of(i):
    s = lines[i].rstrip("\r")
    return s[:len(s) - len(s.lstrip())]


def block(i, body):
    """Re-indent body (written at zero indent) to line i's indent, matching its EOL."""
    ind = indent_of(i)
    eol = "\r" if lines[i].endswith("\r") else ""
    return [(ind + b if b else "") + eol for b in body.split("\n")]


# ---- 1. CREATE TABLE species_profiles --------------------------------------
s = find_one(lambda l: "CREATE TABLE IF NOT EXISTS species_profiles (" in l,
             "CREATE species_profiles")
e = find_after(s, lambda l: l.strip().rstrip("\r") == ");", "CREATE species_profiles end")
if s is not None and e is not None:
    old_create = [l.rstrip("\r") for l in lines[s:e + 1]]
    edits.append((s, e, block(s, """CREATE TABLE IF NOT EXISTS species_profiles (
    tvk TEXT NOT NULL,
    review_id INTEGER NOT NULL DEFAULT 0,
    species_name TEXT,
    profile_text TEXT NOT NULL,
    source TEXT,
    date_added TEXT NOT NULL,
    date_updated TEXT,
    added_by TEXT,
    PRIMARY KEY (tvk, review_id)
);"""), "CREATE species_profiles"))

# ---- 2. CREATE TABLE reviews: add licence -----------------------------------
s = find_one(lambda l: "CREATE TABLE IF NOT EXISTS reviews (" in l, "CREATE reviews")
idl = find_after(s, lambda l: "id INTEGER PRIMARY KEY" in l, "reviews id line", span=3)
if idl is not None:
    if any("licence" in l for l in lines[s:s + 20]):
        problems.append("reviews already has a licence column -- patch already applied?")
    else:
        edits.append((idl, idl, [lines[idl]] + block(idl, "licence TEXT,"),
                      "reviews.licence"))

# ---- 3. preserve reviews, WITH id -------------------------------------------
s = find_one(lambda l: 'oc.execute("""SELECT review_name, author, taxon_group, status_track,' in l,
             "preserve reviews")
e = find_after(s, lambda l: "saved_reviews = oc.fetchall()" in l, "preserve reviews end")
if s is not None and e is not None:
    edits.append((s, e, block(s, '''try:
    oc.execute("""SELECT id, review_name, author, taxon_group, status_track,
                  date_published, date_imported, source_file,
                  species_count, supersedes_id, notes, licence
                  FROM reviews ORDER BY id""")
except sqlite3.OperationalError:
    # Older schema without licence
    oc.execute("""SELECT id, review_name, author, taxon_group, status_track,
                  date_published, date_imported, source_file,
                  species_count, supersedes_id, notes, NULL
                  FROM reviews ORDER BY id""")
saved_reviews = oc.fetchall()'''), "preserve reviews"))

# ---- 4. preserve species_profiles, with review_id ---------------------------
s = find_one(lambda l: 'oc.execute("""SELECT tvk, profile_text, source, date_added,' in l,
             "preserve profiles")
e = find_after(s, lambda l: "saved_profiles = oc.fetchall()" in l, "preserve profiles end")
if s is not None and e is not None:
    edits.append((s, e, block(s, '''try:
    oc.execute("""SELECT tvk, review_id, species_name, profile_text, source,
                  date_added, date_updated, added_by
                  FROM species_profiles""")
except sqlite3.OperationalError:
    # Older schema: one account per TVK, no review link
    oc.execute("""SELECT tvk, 0, NULL, profile_text, source,
                  date_added, date_updated, added_by
                  FROM species_profiles""")
saved_profiles = oc.fetchall()'''), "preserve profiles"))

# ---- 5. restore reviews, WITH id --------------------------------------------
s = find_one(lambda l: 'c.executemany("""INSERT INTO reviews' in l, "restore reviews")
e = find_after(s, lambda l: "saved_reviews)" in l, "restore reviews end", span=8)
if s is not None and e is not None:
    edits.append((s, e, block(s, '''# id restored explicitly: manual_entries.review_id, supersedes_id and
# species_profiles.review_id all point at it, so it must not be renumbered.
c.executemany("""INSERT INTO reviews
    (id, review_name, author, taxon_group, status_track,
     date_published, date_imported, source_file,
     species_count, supersedes_id, notes, licence)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", saved_reviews)'''), "restore reviews"))

# ---- 6. restore species_profiles --------------------------------------------
s = find_one(lambda l: 'c.executemany("""INSERT INTO species_profiles' in l, "restore profiles")
e = find_after(s, lambda l: "saved_profiles)" in l, "restore profiles end", span=6)
if s is not None and e is not None:
    edits.append((s, e, block(s, '''c.executemany("""INSERT INTO species_profiles
    (tvk, review_id, species_name, profile_text, source,
     date_added, date_updated, added_by)
    VALUES (?,?,?,?,?,?,?,?)""", saved_profiles)'''), "restore profiles"))

# ---- guard -------------------------------------------------------------------
print("Patching build_codex_db.py -- review accounts, licence, stable review ids")
print("=" * 72)
if problems:
    for p in problems:
        print(f"  x {p}")
    print("\nABORTED -- nothing written.")
    sys.exit(1)

print("  Current species_profiles definition (for the record):")
for l in old_create:
    print(f"      {l}")

# apply bottom-up so earlier indices stay valid
for s, e, new, name in sorted(edits, key=lambda t: -t[0]):
    lines[s:e + 1] = new
    print(f"  ok {name}")

shutil.copy2(P, P + ".bak_profiles")
out = "\n".join(lines)
io.open(P, "w", encoding="utf-8-sig" if bom else "utf-8", newline="").write(out)
print("  + written (backup: build_codex_db.py.bak_profiles)")

# ---- check -------------------------------------------------------------------
print("\n  Checking...")
try:
    py_compile.compile(P, doraise=True)
    print("  ok compiles")
except py_compile.PyCompileError as ex:
    print(f"  x COMPILE FAILED -- restore the backup\n{ex}")
    sys.exit(1)

# Import only if the module is guarded -- importing an unguarded build script
# would rebuild codex.db.
tree = ast.parse(io.open(P, encoding="utf-8-sig").read())
guarded = any(isinstance(n, ast.If) and "__main__" in ast.dump(n.test) for n in tree.body)
if guarded:
    try:
        sys.path.insert(0, ROOT)
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import importlib
        importlib.import_module("build_codex_db")
        print("  ok imports")
    except Exception as ex:
        print(f"  x IMPORT FAILED: {type(ex).__name__}: {ex} -- restore the backup")
        sys.exit(1)
else:
    print("  (not imported: no __main__ guard, importing would run the build)")

# Re-read and show the changed regions -- don't trust the indices.
now = io.open(P, encoding="utf-8-sig").read().split("\n")
for marker in ("CREATE TABLE IF NOT EXISTS species_profiles (", "licence TEXT,",
               "FROM reviews ORDER BY id", 'INSERT INTO reviews',
               "SELECT tvk, review_id, species_name", "INSERT INTO species_profiles"):
    idx = [i for i, l in enumerate(now) if marker in l]
    print(f"  {'ok' if idx else 'x '} {marker!r} at line {', '.join(str(i + 1) for i in idx) or '-'}")

print("\nNothing has been rebuilt. Next: back up codex.db, then rebuild.")
