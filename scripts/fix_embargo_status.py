"""Embargo status -- data and code.

The iRecord export excludes a record only when embargo_status == 'Active' AND
embargo_until is in the future. DataEntry's commit set the date but never the
status, so the first committed batch (Birmingham - Wheels Park, 172 records)
was eligible for upload despite its embargo date.

  1. CODE   DataEntry/commit_service.py: after each commit, set
            embargo_status='Active' on the new row when it has an embargo date.
            Raw SQL in commit_job, like the existing supplementary UPDATE, so no
            model whitelist can drop it.
  2. DATA   Every observation with a FUTURE embargo_until and an empty status
            gets embargo_status='Active'. Listed by project first.

DRY RUN by default; --apply to write. Close Observatum first.

Run:  python scripts\\fix_embargo_status.py
      python scripts\\fix_embargo_status.py --apply
"""
import datetime, importlib, io, os, py_compile, shutil, sqlite3, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "Observatum"))
import paths

APPLY = "--apply" in sys.argv
CS = os.path.join(ROOT, "DataEntry", "commit_service.py")
BACKUP_DIR = r"C:\BiologicalSoftware_Backups\reference"
TODAY = datetime.date.today().isoformat()

print("Embargo status -- data and code  --  " + ("APPLY" if APPLY else "DRY RUN"))
print("=" * 76)

# ---------------------------------------------------------------- code: plan
raw = io.open(CS, "rb").read()
bom = raw.startswith(b"\xef\xbb\xbf")
lines = raw.decode("utf-8-sig").split("\n")
already = any("embargo_status='Active'" in l for l in lines)
# Search ONLY inside commit_job(): the same line appears in another function,
# where new_id and kwargs do not exist.
import ast
_fn = next((n for n in ast.walk(ast.parse("\n".join(l.rstrip("\r") for l in lines)))
            if isinstance(n, ast.FunctionDef) and n.name == "commit_job"), None)
if _fn is None:
    print("  x code: commit_job() not found -- ABORTED")
    sys.exit(1)
_lo, _hi = _fn.lineno - 1, _fn.end_lineno
print(f"  code: commit_job() spans lines {_lo + 1}-{_hi}")
hits = [i for i in range(_lo, _hi)
        if lines[i].strip().rstrip("\r") == 'repo.delete_row(conn, row["id"])']
for _need in ("new_id = model.create(", "kwargs = build_kwargs_from_row("):
    if not any(_need in lines[i] for i in range(_lo, _hi)):
        print(f"  x code: {_need!r} not inside commit_job() -- ABORTED")
        sys.exit(1)
kw = [i for i, l in enumerate(lines) if '"embargo_until":' in l]
code_ok = True
if already:
    print("  code: commit_service.py already sets embargo_status -- skipped")
    code_ok = False
elif len(hits) != 1:
    print(f"  x code: 'repo.delete_row(conn, row[\"id\"])' found {len(hits)} times inside commit_job() -- ABORTED")
    sys.exit(1)
elif not kw:
    print("  x code: build_kwargs_from_row has no \"embargo_until\" key -- ABORTED")
    sys.exit(1)
else:
    print(f"  code: insert before line {hits[0] + 1} of commit_service.py")

# ---------------------------------------------------------------- data: plan
o = sqlite3.connect(str(paths.OBSERVATUM_DB))
WHERE = ("embargo_until IS NOT NULL AND embargo_until != '' AND embargo_until > ? "
         "AND (embargo_status IS NULL OR trim(embargo_status) = '')")
rows = o.execute(f"""SELECT project_name, record_type, embargo_until, COUNT(1)
                     FROM observations WHERE {WHERE} GROUP BY 1,2,3 ORDER BY 1""",
                 (TODAY,)).fetchall()
total = sum(r[3] for r in rows)
print(f"\n  data: observations with a future embargo date but no status: {total}")
for p, rt, until, n in rows:
    print(f"    {str(p)[:32]:32} {rt:<11} until {until}   {n}")
other = o.execute("""SELECT embargo_status, COUNT(1) FROM observations
                     WHERE embargo_status IS NOT NULL AND trim(embargo_status) != ''
                     GROUP BY 1""").fetchall()
print(f"  existing statuses, for comparison: {other}")

if not APPLY:
    print("\nDRY RUN -- nothing has been changed. Close Observatum, then --apply.")
    sys.exit(0)

# ---------------------------------------------------------------- code: write
if code_ok:
    i = hits[0]
    ind = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
    eol = "\r" if lines[i].endswith("\r") else ""
    block = [
        "if new_id and kwargs.get(\"embargo_until\"):",
        "    # The iRecord export excludes a record only when embargo_status is",
        "    # 'Active' AND embargo_until is in the future. Setting the date alone",
        "    # left the first committed batch uploadable (found 2 October 2026).",
        "    db.execute_main_write(",
        "        \"UPDATE observations SET embargo_status='Active' WHERE id=?\", (new_id,))",
    ]
    lines[i:i] = [ind + b + eol for b in block]
    shutil.copy2(CS, CS + ".bak_embargo")
    io.open(CS, "w", encoding="utf-8-sig" if bom else "utf-8", newline="").write("\n".join(lines))
    try:
        py_compile.compile(CS, doraise=True)
        importlib.import_module("DataEntry.commit_service")
        print("\n  code: commit_service.py patched, compiles and imports (backup: .bak_embargo)")
    except Exception as e:
        shutil.copy2(CS + ".bak_embargo", CS)
        print(f"\n  x code: patched file failed ({type(e).__name__}: {e}) -- restored. Data NOT changed.")
        sys.exit(1)

# ---------------------------------------------------------------- data: write
os.makedirs(BACKUP_DIR, exist_ok=True)
bp = os.path.join(BACKUP_DIR, "observatum_pre_embargo_status_" +
                  datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".db")
t = sqlite3.connect(bp); o.backup(t); t.close()
print(f"  backup: {bp}")
with o:
    n = o.execute(f"UPDATE observations SET embargo_status='Active' WHERE {WHERE}",
                  (TODAY,)).rowcount
print(f"  data: {n} records set to embargo_status='Active'")

# ---------------------------------------------------------------- read back
left = o.execute(f"SELECT COUNT(1) FROM observations WHERE {WHERE}", (TODAY,)).fetchone()[0]
bw = o.execute("""SELECT embargo_status, embargo_until, COUNT(1) FROM observations
                  WHERE project_name='Birmingham - Wheels Park' GROUP BY 1,2""").fetchall()
eligible = o.execute("""SELECT COUNT(1) FROM observations
                        WHERE project_name='Birmingham - Wheels Park'
                          AND NOT (embargo_status='Active' AND embargo_until > ?)
                          AND COALESCE(never_upload_to_irecord,0)=0""", (TODAY,)).fetchone()[0]
print(f"\n  still with a date but no status: {left}")
print(f"  Birmingham - Wheels Park: {bw}")
print(f"  Birmingham - Wheels Park records the iRecord export would now take: {eligible} (expect 0)")
print("\nDone.")
