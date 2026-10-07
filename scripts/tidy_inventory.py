"""Tidy-up inventory -- READ ONLY. Nothing is moved, deleted or changed.

Writes tidy_inventory.txt in the suite root:
  1. Root folder: every entry, its size, whether git tracks it
  2. scripts/: every file -- last commit date, who still refers to it
     (launchers, apps, other scripts, docs) and a suggested KEEP / ARCHIVE / REVIEW
  3. Leftovers: .bak / .tmp files from patches, loose output files in the root

Run:  py -3.14 scripts\\tidy_inventory.py
"""
import os, re, subprocess, sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tidy_inventory.txt")
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules"}

# operational scripts named in the procedures -- always KEEP
OPS = {
    "build_uksi_from_release", "build_codex_db", "remap_record_tvks", "make_source_bundle",
    "clear_legacy_detail", "clear_stale_legacy", "restore_dropped_statuses", "check_sqi_table",
    "import_own_profiles", "seed_codex", "mark_irecord_commercial", "tidy_inventory",
}
ONE_OFF = re.compile(r"^(patch|fix|apply|migrate|migration|oneoff|one_off|temp|tmp|test|debug|"
                     r"probe|diag|inspect|lookup|check|verify|repair|backfill|dedupe|rename|move)_",
                     re.I)


def git(*args):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.stdout


def size_of(path):
    if os.path.isfile(path):
        return os.path.getsize(path)
    total = 0
    for d, dirs, files in os.walk(path):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for f in files:
            try:
                total += os.path.getsize(os.path.join(d, f))
            except OSError:
                pass
    return total


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:,.0f} {unit}" if unit == "B" else f"{n:,.1f} {unit}"
        n /= 1024


tracked = set(git("ls-files").splitlines())
tracked_top = defaultdict(int)
for t in tracked:
    tracked_top[t.split("/")[0]] += 1

lines = []
w = lines.append
w("Tidy-up inventory  --  READ ONLY")
w("=" * 78)

# ------------------------------------------------------------------ 1 root
w("\n1. ROOT FOLDER")
w(f"   {'name':<34} {'type':<5} {'size':>10}  git-tracked files")
for name in sorted(os.listdir(ROOT), key=str.lower):
    if name in SKIP_DIRS:
        continue
    p = os.path.join(ROOT, name)
    kind = "dir" if os.path.isdir(p) else "file"
    n = tracked_top.get(name, 0)
    note = str(n) if n else ("-- untracked" if kind == "file" else "0")
    w(f"   {name:<34} {kind:<5} {human(size_of(p)):>10}  {note}")

# ------------------------------------------------------------------ 2 scripts
w("\n2. SCRIPTS")
sdir = os.path.join(ROOT, "scripts")
last = {}
cur = None
for ln in git("log", "--name-only", "--format=@%cs", "--", "scripts").splitlines():
    if ln.startswith("@"):
        cur = ln[1:]
    elif ln.strip() and ln not in last:
        last[ln] = cur

# text to search for references: launchers, every tracked .py/.bat/.md outside scripts/x itself
corpus = {}
for t in tracked:
    if t.endswith((".py", ".bat", ".md", ".ps1")):
        try:
            corpus[t] = open(os.path.join(ROOT, t), encoding="utf-8", errors="replace").read()
        except OSError:
            pass


def where(stem, self_path):
    hits = defaultdict(int)
    pat = re.compile(r"\b" + re.escape(stem) + r"\b")
    for t, text in corpus.items():
        if t == self_path or not pat.search(text):
            continue
        top = t.split("/")[0]
        group = ("launchers" if top in ("launchers", "run.bat") else
                 "docs" if top == "docs" else
                 "scripts" if top == "scripts" else "apps")
        hits[group] += 1
    return hits


rows = []
if os.path.isdir(sdir):
    for d, dirs, files in os.walk(sdir):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for f in files:
            if f.endswith((".pyc",)):
                continue
            full = os.path.join(d, f)
            rel = os.path.relpath(full, ROOT).replace("\\", "/")
            stem = os.path.splitext(f)[0]
            if f.endswith((".bak", ".tmp")):
                continue                          # reported in section 3
            hits = where(stem, rel)
            if stem in OPS or hits.get("launchers") or hits.get("apps"):
                verdict = "KEEP"
            elif ONE_OFF.match(f) and not hits.get("scripts"):
                verdict = "ARCHIVE"
            else:
                verdict = "REVIEW"
            refs = ", ".join(f"{k} {v}" for k, v in sorted(hits.items())) or "-"
            rows.append((verdict, rel, last.get(rel, "untracked" if rel not in tracked else "?"),
                         os.path.getsize(full), refs))

order = {"KEEP": 0, "REVIEW": 1, "ARCHIVE": 2}
for verdict in ("KEEP", "REVIEW", "ARCHIVE"):
    group = sorted((r for r in rows if r[0] == verdict), key=lambda r: r[1].lower())
    w(f"\n   {verdict}  ({len(group)})")
    for _, rel, date, size, refs in group:
        w(f"     {rel[8:]:<46} {date:<10} {human(size):>9}  refs: {refs}")

# ------------------------------------------------------------------ 3 leftovers
w("\n3. LEFTOVERS")
baks = []
for d, dirs, files in os.walk(ROOT):
    dirs[:] = [x for x in dirs if x not in SKIP_DIRS and x != "data"]
    for f in files:
        if f.endswith((".bak", ".tmp")) or re.search(r"\.bak\d*$", f):
            baks.append(os.path.relpath(os.path.join(d, f), ROOT))
w(f"\n   .bak / .tmp files outside data/  ({len(baks)}, {human(sum(size_of(os.path.join(ROOT, b)) for b in baks))})")
for b in sorted(baks, key=str.lower):
    w(f"     {b}")

loose = [n for n in os.listdir(ROOT)
         if os.path.isfile(os.path.join(ROOT, n)) and n not in tracked
         and not n.startswith(".") and n != "tidy_inventory.txt"]
w(f"\n   untracked loose files in the root  ({len(loose)})")
for n in sorted(loose, key=str.lower):
    w(f"     {n:<46} {human(size_of(os.path.join(ROOT, n))):>9}")

w("\nREAD ONLY -- nothing has been changed.")
open(OUT, "w", encoding="utf-8").write("\n".join(lines) + "\n")
print(f"  wrote {OUT}")
print(f"  scripts: {sum(r[0]=='KEEP' for r in rows)} keep, {sum(r[0]=='REVIEW' for r in rows)} review, "
      f"{sum(r[0]=='ARCHIVE' for r in rows)} archive  |  {len(baks)} .bak/.tmp  |  {len(loose)} loose root files")
