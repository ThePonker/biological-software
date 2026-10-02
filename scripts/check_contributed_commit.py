"""What happens if a collaborator's records are committed through Data Entry?
READ ONLY. Nothing is written.

  [1] commit_service: what a commit writes (recorder, determiner, embargo,
      never_upload_to_irecord, sync_status, batch stamp)
  [2] iRecord: which flags keep a record out of an upload
  [3] stats / dashboards: do they filter observations on anything
  [4] entry_batches.py: can a batch be removed cleanly
  [5] live database: observation flags in use, and the staging jobs

Run:  python scripts\\check_contributed_commit.py > contributed_check.txt
"""
import ast, io, os, re, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import paths

SKIP = {"_archive", "_backups", ".git", "__pycache__", "data", "_dump", "BackUps"}


def pyfiles(base):
    for d, dirs, files in os.walk(base):
        dirs[:] = [x for x in dirs if x not in SKIP]
        for f in files:
            if f.endswith(".py") and ".bak" not in f:
                yield os.path.join(d, f)


def read(p):
    return io.open(p, encoding="utf-8-sig", errors="replace").read()


def rel(p):
    return os.path.relpath(p, ROOT)


def func_source(path, name):
    src = read(path)
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node.lineno, ast.get_source_segment(src, node)
    return None, None


def hits(path, pattern, ctx=0, limit=40):
    ls = read(path).splitlines()
    out, shown = [], set()
    for i, l in enumerate(ls):
        if re.search(pattern, l):
            for j in range(max(0, i - ctx), min(len(ls), i + ctx + 1)):
                if j not in shown:
                    shown.add(j)
                    out.append(f"    {j + 1:5}: {ls[j].rstrip()[:110]}")
    return out[:limit]


print("Contributed records through Data Entry -- code and data check  --  READ ONLY")
print("=" * 78)

# ------------------------------------------------------------------ [1]
print("\n[1] DataEntry commit -- what a commit writes")
cs = [p for p in pyfiles(os.path.join(ROOT, "DataEntry")) if p.endswith("commit_service.py")]
if not cs:
    print("  commit_service.py not found")
for p in cs:
    ln, src = func_source(p, "commit_job")
    if src:
        print(f"  {rel(p)}  commit_job() at line {ln}, {len(src.splitlines())} lines:")
        for i, l in enumerate(src.splitlines()):
            print(f"    {ln + i:5}: {l[:110]}")
    else:
        print(f"  {rel(p)}: commit_job() not found; keyword hits:")
    print("  keyword hits across the file:")
    for h in hits(p, r"never_upload|embargo|sync_status|recorder|determiner|batch|record_type"):
        print(h)

# ------------------------------------------------------------------ [2]
print("\n[2] iRecord -- what keeps a record out of an upload")
for p in pyfiles(os.path.join(ROOT, "Observatum")):
    if "irecord" in p.lower() or "upload" in p.lower() or "export" in os.path.basename(p).lower():
        h = hits(p, r"never_upload|embargo_status|embargo_until|sync_status\s*=|record_type\s*=|sensitive")
        if h:
            print(f"  {rel(p)}")
            for x in h[:15]:
                print(x)

# ------------------------------------------------------------------ [3]
print("\n[3] Stats / dashboards / pills -- do observation queries filter on anything?")
print("  file                                              queries  recorder  record_type  never_upload")
cands = [p for p in pyfiles(os.path.join(ROOT, "Observatum")) if re.search(r"stat|dashboard|game|achiev", p.lower())]
cands += [p for p in pyfiles(os.path.join(ROOT, "DataEntry")) if re.search(r"banner|info|pill|count", p.lower())]
for p in sorted(set(cands)):
    t = read(p)
    q = len(re.findall(r"FROM\s+observations", t, re.I))
    if not q:
        continue
    print(f"  {rel(p)[:50]:50} {q:7}  {len(re.findall(r'recorder|determiner', t)):8}  "
          f"{len(re.findall(r'record_type', t)):11}  {len(re.findall(r'never_upload', t)):12}")

# ------------------------------------------------------------------ [4]
print("\n[4] entry_batches.py -- removing a batch")
eb = os.path.join(ROOT, "scripts", "entry_batches.py")
if os.path.exists(eb):
    t = read(eb)
    print("  " + "\n  ".join((ast.get_docstring(ast.parse(t)) or "(no docstring)").splitlines()[:20]))
    for h in hits(eb, r"DELETE|import_notes|LIKE|argparse|add_argument"):
        print(h)
else:
    print("  scripts/entry_batches.py not found")

# ------------------------------------------------------------------ [5]
print("\n[5] Live database")
o = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
cols = [r[1] for r in o.execute("PRAGMA table_info(observations)")]
for c in ("recorder", "determiner", "never_upload_to_irecord", "embargo_status",
          "embargo_until", "sync_status", "record_type", "import_notes"):
    print(f"  observations.{c:<26} {'present' if c in cols else 'MISSING'}")
if "never_upload_to_irecord" in cols:
    for v, n in o.execute("SELECT never_upload_to_irecord, COUNT(1) FROM observations GROUP BY 1"):
        print(f"    never_upload_to_irecord={v!r}: {n}")
if "sync_status" in cols:
    for v, n in o.execute("SELECT sync_status, COUNT(1) FROM observations GROUP BY 1"):
        print(f"    sync_status={v!r}: {n}")
n = o.execute("SELECT COUNT(1) FROM observations WHERE import_notes LIKE '%DataEntry batch%'").fetchone()[0]
print(f"  observations committed through Data Entry so far: {n}")

print("\n  Recorder values on observations (top 12):")
for v, n in o.execute("SELECT recorder, COUNT(1) FROM observations GROUP BY 1 ORDER BY 2 DESC LIMIT 12"):
    print(f"    {str(v)[:30]:30} {n}")

jcols = [r[1] for r in o.execute("PRAGMA table_info(entry_jobs)")]
scols = [r[1] for r in o.execute("PRAGMA table_info(entry_staging)")]
print(f"\n  entry_jobs columns:    {jcols}")
print(f"  entry_staging columns: {scols}")
print("\n  Staging jobs:")
fk = "job_id" if "job_id" in scols else next((c for c in scols if "job" in c), None)
want = [c for c in ("id", "name", "mode", "project", "client", "embargo_until", "status") if c in jcols]
try:
    cnt = f", (SELECT COUNT(1) FROM entry_staging s WHERE s.{fk} = j.id)" if fk else ", NULL"
    for row in o.execute(f"SELECT {', '.join('j.' + c for c in want)}{cnt} FROM entry_jobs j ORDER BY j.id"):
        print("    " + "  ".join(f"{c}={str(v)[:24]}" for c, v in zip(want + ["rows"], row)))
except sqlite3.Error as e:
    print(f"    (could not list jobs: {e})")
o.close()

print("\nREAD ONLY -- nothing has been changed.")
