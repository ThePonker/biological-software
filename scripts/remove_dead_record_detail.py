"""Remove the two dead Record Detail copies.

  Observatum/src/views/observations/record_detail.py           (whole file)
  Observatum/src/views/observations/record_detail_ui_mixin.py  (whole file)
  SchemeRecordDetailDialog class in views/scheme/scheme_dialogs.py
      (the file stays -- SaveFilterDialog in it is used) and its re-export
      in views/scheme/__init__.py

The live windows are views/dialogs/record_detail_dialog.py and
views/dialogs/scheme_record_detail_dialog.py -- untouched.

Checks first, across every tracked .py file, that nothing else imports the dead
code; refuses if anything does. After the change: compiles the edited files and
imports the three view packages in a fresh Python. On any failure, restores
everything from git (all four files are tracked).

DRY RUN by default; --apply to remove.

Run:  python scripts\\remove_dead_record_detail.py
      python scripts\\remove_dead_record_detail.py --apply
"""
import ast, io, os, py_compile, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V = os.path.join(ROOT, "Observatum", "src", "views")
DEAD_FILES = [os.path.join(V, "observations", "record_detail.py"),
              os.path.join(V, "observations", "record_detail_ui_mixin.py")]
SD = os.path.join(V, "scheme", "scheme_dialogs.py")
SI = os.path.join(V, "scheme", "__init__.py")
APPLY = "--apply" in sys.argv
rel = lambda p: os.path.relpath(p, ROOT)

print("Remove dead Record Detail copies  --  " + ("APPLY" if APPLY else "DRY RUN"))
print("=" * 72)
tracked = subprocess.run(["git", "ls-files", "*.py"], cwd=ROOT, capture_output=True, text=True).stdout.split()
problems = []
pat_obs = re.compile(r"(from\s+\.+record_detail(_ui_mixin)?\s+import|observations\.record_detail|"
                     r"from\s+\.+observations\.record_detail)")
pat_sch = re.compile(r"SchemeRecordDetailDialog")
for f in tracked:
    p = os.path.join(ROOT, f)
    if os.path.abspath(p) in map(os.path.abspath, DEAD_FILES):
        continue
    txt = io.open(p, encoding="utf-8-sig", errors="replace").read()
    for n, line in enumerate(txt.splitlines(), 1):
        if pat_obs.search(line) and "record_detail_dialog" not in line:
            problems.append(f"{f}:{n} imports the dead observations copy: {line.strip()}")
        if pat_sch.search(line) and os.path.abspath(p) not in (os.path.abspath(SD), os.path.abspath(SI)) \
                and re.search(r"(from\s+\.+scheme(\.scheme_dialogs)?\s+import|scheme\.scheme_dialogs|views\.scheme\s+import)", line):
            problems.append(f"{f}:{n} imports the scheme copy: {line.strip()}")

sd = io.open(SD, encoding="utf-8-sig").read()
cls = [n for n in ast.parse(sd).body if isinstance(n, ast.ClassDef) and n.name == "SchemeRecordDetailDialog"]
si = io.open(SI, encoding="utf-8-sig").read()
imp = "from .scheme_dialogs import SchemeRecordDetailDialog, SaveFilterDialog"
for p in DEAD_FILES:
    print(f"  delete file   {rel(p):<60} {'found' if os.path.isfile(p) else 'MISSING'}")
print(f"  remove class  SchemeRecordDetailDialog in {rel(SD)}: x{len(cls)}")
print(f"  edit import   {rel(SI)}: x{si.count(imp)}")
if len(cls) != 1: problems.append("SchemeRecordDetailDialog class not found exactly once")
if si.count(imp) != 1: problems.append("re-export line in scheme/__init__.py not found exactly once")
if not all(os.path.isfile(p) for p in DEAD_FILES): problems.append("a dead file is missing (already removed?)")
for p in problems:
    print(f"  x {p}")
if problems:
    sys.exit("\nABORTED -- nothing removed.")
if not APPLY:
    print("\n  nothing else imports the dead code.\nDRY RUN -- re-run with --apply.")
    sys.exit(0)


def restore(msg):
    subprocess.run(["git", "checkout", "--", rel(SD), rel(SI)] + [rel(p) for p in DEAD_FILES], cwd=ROOT)
    sys.exit(f"  x {msg} -- everything restored from git")


for p in DEAD_FILES:
    os.remove(p)
lines = sd.split("\n")
c = cls[0]
start = c.lineno - 1 - len(c.decorator_list)
end = c.end_lineno
while end < len(lines) and not lines[end].strip():
    end += 1
new_sd = "\n".join(lines[:start] + lines[end:])
io.open(SD, "w", encoding="utf-8", newline="").write(new_sd)
new_si = si.replace(imp, "from .scheme_dialogs import SaveFilterDialog")
new_si = re.sub(r"""\s*['"]SchemeRecordDetailDialog['"],?""", "", new_si) if "__all__" in new_si else new_si
io.open(SI, "w", encoding="utf-8", newline="").write(new_si)
try:
    py_compile.compile(SD, doraise=True)
    py_compile.compile(SI, doraise=True)
except py_compile.PyCompileError as e:
    restore(f"compile failed: {e}")
env = dict(os.environ, PYTHONPATH=os.pathsep.join([ROOT, os.path.join(ROOT, "Observatum")]),
           QT_QPA_PLATFORM="offscreen")
r = subprocess.run([sys.executable, "-c", "import src.views.dialogs, src.views.scheme, src.views.observations; print('imports ok')"],
                   cwd=ROOT, env=env, capture_output=True, text=True)
print("  " + (r.stdout.strip() or r.stderr.strip()[-600:]))
if r.returncode:
    restore("view packages no longer import")
print("\n  removed: 2 files, 1 class, 1 re-export. Launch Observatum and open a record")
print("  from Observations and from Recording Scheme to confirm, then commit.")
