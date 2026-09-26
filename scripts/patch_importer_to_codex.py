"""Patch import_status_review.py -- review accounts go to codex.db.

  * Accounts are written to codex.db.species_profiles under the review they
    came from, keyed (tvk, review_id): DELETE then INSERT, never REPLACE.
  * Statuses and accounts commit together -- one transaction, all or nothing.
  * observatum.db is no longer written by an import. Wil's own accounts live
    there and an import never touches them.
  * --profiles-only finds the already-registered review by name.
  * One account per TVK (was per name, which let a synonym collapse through).

Refuses if verify() reads species_profiles (it would need changing too) or if
the codex cursor 'c' is not defined where expected. Writes NOTHING unless every
marker is found exactly once. Backup: import_status_review.py.bak_codexprof

Run:  python scripts\\patch_importer_to_codex.py
"""
import ast, io, os, py_compile, re, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "scripts", "import_status_review.py")

raw = io.open(P, "rb").read()
bom = raw.startswith(b"\xef\xbb\xbf")
src = raw.decode("utf-8-sig")
lines = src.split("\n")
problems, edits = [], []


def one(pred, name):
    hits = [i for i, l in enumerate(lines) if pred(l)]
    if len(hits) != 1:
        problems.append(f"{name}: found {len(hits)} times")
        return None
    return hits[0]


def after(start, pred, name, span=40):
    if start is None:
        return None
    for i in range(start, min(len(lines), start + span)):
        if pred(lines[i]):
            return i
    problems.append(f"{name}: end marker not found")
    return None


def eol(i):
    return "\r" if lines[i].endswith("\r") else ""


def blk(i, body, ind=None):
    s = lines[i].rstrip("\r")
    ind = s[:len(s) - len(s.lstrip())] if ind is None else ind
    e = eol(i)
    return [(ind + b if b else "") + e for b in body.split("\n")]


# ---- safety: verify() and the cursor ----------------------------------------
tree = ast.parse(src)
fn = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
if "verify" in fn:
    vsrc = ast.get_source_segment(src, fn["verify"]) or ""
    if "species_profiles" in vsrc or "origin" in vsrc:
        problems.append("verify() reads species_profiles/origin -- needs changing too:\n"
                        + vsrc)
else:
    problems.append("verify() not found")
if "main" in fn:
    msrc = ast.get_source_segment(src, fn["main"]) or ""
    if not re.search(r"^\s+c\s*=\s*codex\.cursor\(\)", msrc, re.M):
        problems.append("main(): 'c = codex.cursor()' not found -- cursor name unknown")
else:
    problems.append("main() not found")

# ---- A. docstring paragraph ----------------------------------------------------
s = one(lambda l: "Species accounts go to observatum.db.species_profiles" in l, "docstring")
e = after(s, lambda l: l.strip("\r").strip() == "", "docstring end", span=8)
if s is not None and e is not None:
    edits.append((s, e - 1, blk(s, """Species accounts go to codex.db.species_profiles, one per species per review,
keyed (tvk, review_id), with the review's citation. An import never touches
observatum.db.species_profiles, which holds Wil's own accounts only."""), "docstring"))

# ---- B. profile planning -----------------------------------------------------
s = one(lambda l: "# ------------------------------------------------------------ profiles" in l,
        "planning start")
e = after(s, lambda l: 'left alone (your own / edited) {kept}")' in l, "planning end")
if s is not None and e is not None:
    edits.append((s, e, blk(s, '''# ------------------------------------------------------------ profiles
# Review accounts go to codex.db.species_profiles, one per species per
# review. Wil's own accounts live in observatum.db; an import never touches them.
obs_path = str(paths.OBSERVATUM_DB)
ob = sqlite3.connect(obs_path)        # kept open for verify()
existing_rid = find_review_id(c, a.name)
if existing_rid is not None and not a.profiles_only:
    print("")
    print(f"  NOTE: a review named {a.name!r} is already registered (id {existing_rid});")
    print("        importing again registers a second review. Use --profiles-only")
    print("        to refresh accounts under the existing one.")
have = set()
if a.profiles_only and existing_rid is not None:
    have = {r[0] for r in c.execute(
        "SELECT tvk FROM species_profiles WHERE review_id=?", (existing_rid,))}
new_prof = upd_prof = 0
prof_plan = []
seen_tvk = set()
for p in plan:
    if not p["row"]["ecology"] or p["tvk"] in seen_tvk:
        continue                      # one account per TVK
    seen_tvk.add(p["tvk"])
    if p["tvk"] in have:
        upd_prof += 1
    else:
        new_prof += 1
    prof_plan.append(p)
target = existing_rid if a.profiles_only else "new"
print("")
print(f"  SPECIES ACCOUNTS -> codex.db (review {target})")
print(f"    new {new_prof}   replacing this review's earlier text {upd_prof}")
print("    (your own accounts are in observatum.db and are never touched)")
if a.profiles_only and existing_rid is None:
    print("")
    print(f"  x --profiles-only needs the review registered; none named {a.name!r}")
    codex.close()
    ob.close()
    return 1'''), "planning"))

# ---- C. write section ----------------------------------------------------------
s = one(lambda l: "# ------------------------------------------------------------ write" in l,
        "write start")
e = after(s, lambda l: "return verify(c, codex, ob)" in l, "write end", span=15)
if s is not None and e is not None:
    edits.append((s, e, blk(s, '''# ------------------------------------------------------------ write
# Statuses and accounts land in codex.db in ONE transaction: all or nothing.
print("")
print(f"  backup: {backup(paths.CODEX_DB, 'codex')}")

if a.profiles_only:
    rid = existing_rid
else:
    rid = write_statuses(c, a, plan, tracks_written, source, now)
write_profiles(c, prof_plan, rid, source, now)
codex.commit()
return verify(c, codex, ob)'''), "write section"))

# ---- D. write_statuses returns the review id -------------------------------------
s = one(lambda l: 'print(f"  review #{rid} registered; {writes} status entries written")' in l,
        "write_statuses print")
if s is not None:
    edits.append((s, s, [lines[s]] + blk(s, "return rid"), "write_statuses returns rid"))

# ---- E. write_profiles -> codex, plus find_review_id ------------------------------
s = one(lambda l: l.startswith("def write_profiles("), "write_profiles def")
e = after(s, lambda l: 'species accounts written")' in l, "write_profiles end", span=25)
if s is not None and e is not None:
    edits.append((s, e, blk(s, '''def find_review_id(c, name):
    """Id of the registered review with this name; the latest if several."""
    rows = c.execute("SELECT id FROM reviews WHERE review_name=? ORDER BY id",
                     (name,)).fetchall()
    if len(rows) > 1:
        print(f"  NOTE: {len(rows)} reviews share the name {name!r}; using id {rows[-1][0]}")
    return rows[-1][0] if rows else None


def write_profiles(c, prof_plan, rid, source, now):
    """Review accounts into codex.db, under the review they came from.

    DELETE then INSERT, never INSERT OR REPLACE -- the same rule as statuses.
    """
    for p in prof_plan:
        c.execute("DELETE FROM species_profiles WHERE tvk=? AND review_id=?",
                  (p["tvk"], rid))
        c.execute("""INSERT INTO species_profiles
            (tvk, review_id, species_name, profile_text, source,
             date_added, date_updated, added_by)
            VALUES (?,?,?,?,?,?,NULL,'review-import')""",
            (p["tvk"], rid, p["name"], p["row"]["ecology"], source, now))
    print(f"  {len(prof_plan)} species accounts written to codex.db (review {rid})")''', ind=""),
        "write_profiles"))

# ---- guard, apply, check ---------------------------------------------------------
print("Patching import_status_review.py -- review accounts to codex.db")
print("=" * 72)
if problems:
    for p in problems:
        print(f"  x {p}")
    print("\nABORTED -- nothing written.")
    sys.exit(1)

for s, e, new, name in sorted(edits, key=lambda t: -t[0]):
    lines[s:e + 1] = new
    print(f"  ok {name}")

shutil.copy2(P, P + ".bak_codexprof")
io.open(P, "w", encoding="utf-8-sig" if bom else "utf-8", newline="").write("\n".join(lines))
print("  + written (backup: import_status_review.py.bak_codexprof)")

print("\n  Checking...")
try:
    py_compile.compile(P, doraise=True)
    print("  ok compiles")
except py_compile.PyCompileError as ex:
    shutil.copy2(P + ".bak_codexprof", P)
    print(f"  x COMPILE FAILED -- restored from backup\n{ex}")
    sys.exit(1)

new_src = io.open(P, encoding="utf-8-sig").read()
guarded = any(isinstance(n, ast.If) and "__main__" in ast.dump(n.test)
              for n in ast.parse(new_src).body)
if guarded:
    try:
        sys.path.insert(0, ROOT)
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import importlib
        importlib.import_module("import_status_review")
        print("  ok imports")
    except Exception as ex:
        print(f"  x IMPORT FAILED: {type(ex).__name__}: {ex} -- restore the backup")
        sys.exit(1)
else:
    print("  (not imported: no __main__ guard)")

left = [l for l in new_src.split("\n") if "observatum.db.species_profiles" in l
        or ("INSERT INTO species_profiles" in l)]
print(f"  species_profiles writes now: {sum('INSERT INTO species_profiles' in l for l in left)} "
      f"(expect 1, in write_profiles, to codex)")
n_ob = len(re.findall(r"ob\.execute\([^)]*species_profiles", new_src))
print(f"  ob.execute(...species_profiles...) remaining: {n_ob} (expect 0)")
print("\nNothing has been imported. Next: a dry run with --profiles-only.")
