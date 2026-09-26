"""Species profiles -- where they live, how they survive, who reads them.
READ ONLY. Nothing is written.

Run:  python scripts\\check_profiles.py
"""
import io, os, re, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import paths


def ro(p):
    return sqlite3.connect(f"file:{p}?mode=ro", uri=True)


def table_report(con, table):
    cols = con.execute(f"PRAGMA table_info({table})").fetchall()
    if not cols:
        print(f"  {table}: does not exist")
        return False
    print(f"  {table} columns:")
    for c in cols:
        pk = f"  PK{c[5]}" if c[5] else ""
        nn = "  NOT NULL" if c[3] else ""
        print(f"      {c[1]:<18} {c[2]:<10}{nn}{pk}")
    for idx in con.execute(f"PRAGMA index_list({table})").fetchall():
        name, unique = idx[1], idx[2]
        icols = [r[2] for r in con.execute(f"PRAGMA index_info('{name}')")]
        print(f"      index {name}: {'UNIQUE ' if unique else ''}({', '.join(icols)})")
    n = con.execute(f"SELECT COUNT(1) FROM {table}").fetchone()[0]
    print(f"  rows: {n}")
    return True


print("Species profiles -- storage check  --  READ ONLY")
print("=" * 76)

# ------------------------------------------------------------------ codex.db
print("\n[1] codex.db")
c = ro(paths.CODEX_DB)
table_report(c, "species_profiles")
print()
if table_report(c, "reviews"):
    for r in c.execute("SELECT * FROM reviews"):
        print("      ", tuple(str(x)[:50] for x in r))
print()
table_report(c, "manual_entries")
c.close()

# ------------------------------------------------------------------ observatum.db
print("\n[2] observatum.db")
o = ro(paths.OBSERVATUM_DB)
if table_report(o, "species_profiles"):
    cols = [r[1] for r in o.execute("PRAGMA table_info(species_profiles)")]
    if "origin" in cols:
        for origin, n in o.execute(
                "SELECT COALESCE(origin,'(null)'), COUNT(1) FROM species_profiles GROUP BY 1"):
            print(f"      origin {origin:<10} {n}")
    tcol = "species_tvk" if "species_tvk" in cols else ("tvk" if "tvk" in cols else None)
    if tcol:
        nulls = o.execute(f"SELECT COUNT(1) FROM species_profiles "
                          f"WHERE {tcol} IS NULL OR {tcol}=''").fetchone()[0]
        dup = o.execute(f"SELECT COUNT(1) FROM (SELECT {tcol} FROM species_profiles "
                        f"WHERE {tcol} IS NOT NULL AND {tcol}!='' "
                        f"GROUP BY {tcol} HAVING COUNT(1)>1)").fetchone()[0]
        print(f"      without a TVK: {nulls}    TVKs held more than once: {dup}")
    print("  one review row, for shape:")
    row = o.execute("SELECT * FROM species_profiles WHERE origin='review' LIMIT 1").fetchone() \
        if "origin" in cols else o.execute("SELECT * FROM species_profiles LIMIT 1").fetchone()
    if row:
        for k, v in zip(cols, row):
            print(f"      {k:<18} {str(v).replace(chr(10), ' ')[:90]}")
o.close()


# ------------------------------------------------------------------ code
def grep(path, pattern, context=0, limit=60):
    if not os.path.exists(path):
        print(f"  (missing: {os.path.relpath(path, ROOT)})")
        return
    lines = io.open(path, encoding="utf-8", errors="replace").read().splitlines()
    hits = [i for i, l in enumerate(lines) if re.search(pattern, l)]
    shown, printed = set(), 0
    for i in hits:
        for j in range(max(0, i - context), min(len(lines), i + context + 1)):
            if j not in shown:
                if shown and j - 1 not in shown:
                    print("      ...")
                shown.add(j)
                print(f"  {j + 1:5}: {lines[j]}")
                printed += 1
        if printed > limit:
            print("      (truncated)")
            break


print("\n[3] build_codex_db.py -- what survives a rebuild")
grep(os.path.join(ROOT, "scripts", "build_codex_db.py"),
     r"species_profiles|PRESERVE|preserve|manual_entries|os\.remove|unlink", context=2)

print("\n[4] import_status_review.py -- where accounts are written")
grep(os.path.join(ROOT, "scripts", "import_status_review.py"),
     r"species_profiles|origin", context=1)

print("\n[5] Everything that reads or writes species_profiles")
SKIP = {"_archive", "_backups", ".git", "__pycache__", "data", "_dump"}
for d, dirs, files in os.walk(ROOT):
    dirs[:] = [x for x in dirs if x not in SKIP]
    for f in files:
        if not f.endswith(".py") or ".bak" in f:
            continue
        p = os.path.join(d, f)
        try:
            for i, line in enumerate(io.open(p, encoding="utf-8", errors="replace"), 1):
                if "species_profiles" in line or "profile_text" in line:
                    print(f"  {os.path.relpath(p, ROOT)}:{i}: {line.strip()[:100]}")
        except OSError:
            pass

print("\nREAD ONLY -- nothing has been changed.")
