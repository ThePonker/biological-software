"""import_status_review.backup(): unique names, never overwrite.

Two loads in the same second got the same backup name, and the second backup
overwrote the first (sawfly Phases 2 and 3, 4 October 2026). Now:
  * the name carries microseconds  -- codex_pre_review_20261004_183837_412907.db
  * if the file somehow exists, it refuses (FileExistsError) rather than overwrite

backup() is shared: load_review.py imports it, so both are fixed at once.
Writes NOTHING unless both anchors are found exactly once inside backup().
Backup of the script: .bak_backupname

Run:  python scripts\\patch_backup_unique.py
"""
import ast, io, os, py_compile, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "scripts", "import_status_review.py")
raw = io.open(P, "rb").read()
bom = raw.startswith(b"\xef\xbb\xbf")
lines = raw.decode("utf-8-sig").split("\n")
tree = ast.parse("\n".join(l.rstrip("\r") for l in lines))
fn = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "backup"]
print("backup() -- unique names")
print("=" * 60)
if any("%f" in l for l in lines[fn[0].lineno - 1:fn[0].end_lineno]) if fn else False:
    sys.exit("  already patched -- nothing written")
if len(fn) != 1:
    sys.exit("ABORTED -- backup() not found exactly once")
f = fn[0]
A = 'stamp = datetime.now().strftime("%Y%m%d_%H%M%S")'
B = "src = sqlite3.connect(str(db_path))"
ia = [i for i in range(f.lineno - 1, f.end_lineno) if lines[i].strip().rstrip("\r") == A]
ib = [i for i in range(f.lineno - 1, f.end_lineno) if lines[i].strip().rstrip("\r") == B]
print(f"  stamp line x{len(ia)}   connect line x{len(ib)}")
if len(ia) != 1 or len(ib) != 1:
    sys.exit("ABORTED -- anchors not found exactly once. Nothing written.")
i, j = ia[0], ib[0]
lines[i] = lines[i].replace('"%Y%m%d_%H%M%S"', '"%Y%m%d_%H%M%S_%f"')
ind = lines[j][:len(lines[j]) - len(lines[j].lstrip())]
eol = "\r" if lines[j].endswith("\r") else ""
lines[j:j] = [ind + "if os.path.exists(dest):   # never overwrite an earlier backup" + eol,
              ind + "    raise FileExistsError(f\"backup already exists: {dest}\")" + eol]
shutil.copy2(P, P + ".bak_backupname")
io.open(P, "w", encoding="utf-8-sig" if bom else "utf-8", newline="").write("\n".join(lines))
try:
    py_compile.compile(P, doraise=True)
except py_compile.PyCompileError as e:
    shutil.copy2(P + ".bak_backupname", P)
    sys.exit(f"  x COMPILE FAILED -- restored\n{e}")
print("  ok -- written and compiles")
for k in range(f.lineno - 1, f.end_lineno + 2):
    print(f"  {k + 1:4}: {lines[k].rstrip()}")
