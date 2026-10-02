"""Everything needed to build contributed_observations, in one console readback.
READ ONLY. Nothing is written.

  [1] observations schema                  -- what the new table mirrors
  [2] Examen: every query on observations  -- what the view must serve
  [3] Name matching                        -- the UKSI resolver to reuse
  [4] Spreadsheet loading + VC derivation  -- what to reuse for the importer
  [5] UKSI schema                          -- taxa / synonyms columns
  [6] observatum.db: existing views, contributed tables, reset_database layout
  [7] The Birmingham Wheels staging job    -- project, site, dates to match

Run:  python scripts\\check_contributed_build.py
"""
import ast, io, os, re, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import paths

MAXF = 70          # max lines printed per function
SKIP = {"_archive", "_backups", ".git", "__pycache__", "data", "_dump", "BackUps"}


def read(p):
    return io.open(p, encoding="utf-8-sig", errors="replace").read()


def rel(p):
    return os.path.relpath(p, ROOT)


def funcs(path):
    src = read(path)
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return src, []
    out = []
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append((n.lineno, n.end_lineno, n.name, ast.get_source_segment(src, n) or ""))
    return src, sorted(out)


def show(lineno, text, cap=MAXF):
    ls = text.splitlines()
    for i, l in enumerate(ls[:cap]):
        print(f"    {lineno + i:5}: {l.rstrip()[:120]}")
    if len(ls) > cap:
        print(f"    ... ({len(ls) - cap} more lines)")


def outline(path):
    _, fs = funcs(path)
    print(f"  {rel(path)} -- functions:")
    for a, b, name, _ in fs:
        print(f"    {a:5}-{b:<5} {name}")


def section(t):
    print("\n" + "=" * 78 + f"\n{t}\n" + "=" * 78)


print("Contributed records -- build readback  --  READ ONLY")

# ------------------------------------------------------------------ [1]
section("[1] observations schema")
o = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
for c in o.execute("PRAGMA table_info(observations)"):
    print(f"    {c[1]:<28} {c[2]:<10} {'NOT NULL' if c[3] else '':8} "
          f"{'default=' + str(c[4]) if c[4] is not None else ''}{'  PK' if c[5] else ''}")

# ------------------------------------------------------------------ [2]
section("[2] Examen / shared: every function that queries observations")
for base in ("Examen", "shared"):
    for d, dirs, files in os.walk(os.path.join(ROOT, base)):
        dirs[:] = [x for x in dirs if x not in SKIP]
        for f in sorted(files):
            if not f.endswith(".py") or ".bak" in f:
                continue
            p = os.path.join(d, f)
            src, fs = funcs(p)
            if not re.search(r"\bobservations\b", src):
                continue
            n_q = len(re.findall(r"FROM\s+observations|JOIN\s+observations", src, re.I))
            print(f"\n  {rel(p)}  ({n_q} FROM/JOIN observations)")
            for a, b, name, body in fs:
                if re.search(r"FROM\s+observations|JOIN\s+observations", body, re.I):
                    # print only innermost functions that contain the query
                    inner = [x for x in fs if x[0] > a and x[1] <= b and
                             re.search(r"FROM\s+observations|JOIN\s+observations", x[3], re.I)]
                    if inner:
                        continue
                    print(f"  -- {name}() lines {a}-{b}")
                    show(a, body)
            # module-level SQL outside any function
            for i, l in enumerate(src.splitlines(), 1):
                if re.search(r"FROM\s+observations", l, re.I) and \
                        not any(a <= i <= b for a, b, _, _ in fs):
                    print(f"    module-level {i}: {l.strip()[:110]}")

# ------------------------------------------------------------------ [3]
section("[3] Name matching -- import_status_review.py")
p = os.path.join(ROOT, "scripts", "import_status_review.py")
if os.path.exists(p):
    outline(p)
    _, fs = funcs(p)
    for a, b, name, body in fs:
        if re.search(r"synonym|uksi|taxa", body, re.I) and name != "main":
            print(f"\n  -- {name}() lines {a}-{b}")
            show(a, body)
else:
    print("  not found")

# ------------------------------------------------------------------ [4]
section("[4] Spreadsheet loading + VC derivation")
for name in ("load_workbook_to_staging.py", "backfill_vice_county.py"):
    p = os.path.join(ROOT, "scripts", name)
    if not os.path.exists(p):
        print(f"  {name}: not found")
        continue
    outline(p)
    src = read(p)
    for i, l in enumerate(src.splitlines(), 1):
        if re.match(r"\s*(from|import)\s", l):
            print(f"    import {i}: {l.strip()[:110]}")
    _, fs = funcs(p)
    for a, b, fname, body in fs:
        if re.search(r"vc|vice|date", fname, re.I):
            print(f"\n  -- {fname}() lines {a}-{b}")
            show(a, body, cap=40)

# ------------------------------------------------------------------ [5]
section("[5] UKSI schema")
u = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)
for t in ("taxa", "synonyms", "common_names"):
    cols = [f"{c[1]}:{c[2]}" for c in u.execute(f"PRAGMA table_info({t})")]
    n = u.execute(f"SELECT COUNT(1) FROM {t}").fetchone()[0] if cols else 0
    print(f"  {t} ({n:,} rows): {', '.join(cols) or 'MISSING'}")
u.close()

# ------------------------------------------------------------------ [6]
section("[6] observatum.db objects, and reset_database.py layout")
for typ, name in o.execute("SELECT type, name FROM sqlite_master "
                           "WHERE type IN ('view','table') ORDER BY type, name"):
    if typ == "view" or "contrib" in name.lower():
        print(f"  {typ}: {name}")
print("  (tables other than contributed* not listed)")
p = os.path.join(ROOT, "scripts", "reset_database.py")
if os.path.exists(p):
    for i, l in enumerate(read(p).splitlines(), 1):
        if re.search(r"CREATE (TABLE|VIEW|INDEX)", l) and "observations" in l \
                or re.match(r"\s*CREATE_\w+\s*=", l) or re.search(r"^\s*\('\w+',\s*CREATE_", l):
            print(f"    reset {i}: {l.strip()[:100]}")

# ------------------------------------------------------------------ [7]
section("[7] Staging job 6 (Jukes Brum?)")
try:
    for r in o.execute("""SELECT project_name, client, site_name, MIN(date), MAX(date),
                                 COUNT(1), COUNT(DISTINCT grid_ref)
                          FROM entry_staging WHERE job_id=6 GROUP BY 1,2,3"""):
        print(f"  project={r[0]!r} client={r[1]!r} site={r[2]!r} "
              f"dates {r[3]}..{r[4]} rows={r[5]} grid refs={r[6]}")
    for r in o.execute("""SELECT method, recorder, determiner, stage, COUNT(1)
                          FROM entry_staging WHERE job_id=6 GROUP BY 1,2,3,4
                          ORDER BY 5 DESC LIMIT 8"""):
        print(f"    method={r[0]!r} recorder={r[1]!r} det={r[2]!r} stage={r[3]!r} n={r[4]}")
    for r in o.execute("""SELECT grid_ref, COUNT(1) FROM entry_staging WHERE job_id=6
                          GROUP BY 1 ORDER BY 2 DESC LIMIT 5"""):
        print(f"    grid {r[0]!r} x{r[1]}")
    n = o.execute("""SELECT COUNT(1) FROM entry_staging WHERE job_id=6
                     AND (species_tvk IS NULL OR species_tvk='')""").fetchone()[0]
    print(f"    rows without a TVK: {n}")
    print("  Existing observations under that project name, if any:")
    for r in o.execute("""SELECT project_name, record_type, substr(date,1,4), COUNT(1)
                          FROM observations
                          WHERE project_name IN (SELECT DISTINCT project_name
                                                 FROM entry_staging WHERE job_id=6)
                             OR project_name LIKE '%Wheels%' OR project_name LIKE '%Brum%'
                          GROUP BY 1,2,3"""):
        print(f"    {r}")
except sqlite3.Error as e:
    print(f"  ({e})")
o.close()

print("\nREAD ONLY -- nothing has been changed.")
