"""Suite tidy-up -- 7 October 2026.   DRY RUN by default; --apply to do it.

Nothing is deleted. Everything moved is listed in _archive\\tidy_20261007_log.txt.

  1. Tabella retired     Tabella\\ + its 2 launchers  -> _archive\\Tabella_20261007\\
                         Atrium: Tabella button and Generate Workbook button removed
  2. scripts\\            one-off patches/checks/fixes -> _archive\\scripts_20261007\\
                         (working scripts stay; any script a kept script imports stays)
  3. build_gb_basemap.py root -> scripts\\
  4. leftovers           every .bak / .bak_* / .tmp outside data\\ -> _archive\\bak_20261007\\<same path>
                         loose root outputs -> _archive\\outputs_20261007\\
  5. root folders        _dump\\ -> _archive\\_dump\\
                         _backups\\ (60 MB, inside OneDrive) -> C:\\BiologicalSoftware_Backups\\old_in_tree_20261007\\
  6. .gitignore          _archive/ _dump/ _backups/ added; changes staged (you commit)

Refuses unless git has no uncommitted changes to tracked files, every Atrium
anchor matches exactly once, and no destination already exists.

  py -3.14 scripts\\tidy_suite_20261007.py            (dry run)
  py -3.14 scripts\\tidy_suite_20261007.py --apply
"""
import os, py_compile, re, shutil, subprocess, sys, tempfile

APPLY = "--apply" in sys.argv
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCH = os.path.join(ROOT, "_archive")
STAMP = "20261007"
BACKUP_ROOT = r"C:\BiologicalSoftware_Backups"
LOG = os.path.join(ARCH, f"tidy_{STAMP}_log.txt")

KEEP = {
    "__init__",
    # UKSI / Codex rebuild procedure
    "build_uksi_from_release", "build_uksi_name_map", "compare_uksi_release", "remap_record_tvks",
    "build_codex_db", "seed_codex", "compare_codex_rebuild", "compare_jncc_versions",
    "clear_legacy_detail", "clear_stale_legacy", "restore_dropped_statuses", "check_sqi_table",
    "check_legacy_conflicts", "check_sqs_derivation", "verify_codex",
    # reviews, statuses, accounts
    "import_status_review", "import_contributed", "import_own_profiles", "load_review",
    "withdraw_statuses", "identify_reviews", "organise_reviews", "prepare_ne_reviews",
    "prepare_butterflies_2022", "rank_reviews_for_accounts", "check_newest_review", "check_old_names",
    "extract_butterfly_red_list", "extract_macro_moth_red_list", "extract_sawfly_all",
    "extract_sawfly_red_list", "list_missing_accounts", "list_account_species", "combined_species_list",
    # database maintenance (launchers / settings point at these)
    "seed_database", "reset_database", "reset_insect_collection", "reset_observations",
    "reset_observations_commercial", "reset_observations_personal", "reset_recording_scheme",
    "restore_database", "prune_backups", "mark_irecord_commercial",
    "backfill_sort_keys", "backfill_vice_county", "collection_status",
    "create_vc_lookup_db", "convert_vc_shapefile", "VC_GENERATOR_README",
    "load_workbook_to_staging", "entry_batches",
    # tooling
    "make_source_bundle", "tidy_inventory", "tidy_suite_20261007", "show_funcs", "build_gb_basemap",
}
LOOSE_ROOT = ["before_uksi2025.txt", "missing_accounts.csv", "tidy_inventory.txt"]
BAK_RE = re.compile(r"\.bak(\d+|_[\w-]+)?$|\.tmp$", re.I)
NO_WALK = {".git", "data", "_archive", "_backups", "_dump", "__pycache__", "node_modules", "Tabella"}

# Atrium edits: (file, old, new)
ATRIUM = [
    (os.path.join(ROOT, "Atrium", "process_manager.py"),
     '    AppDef("Tabella", "Field entry workbook", "acorn.png",\n'
     '           "", "#b8860b", "#fdf4e3", special="tabella_workbook"),\n'
     '    AppDef("Generate Tabella", "Create new workbook", "acorn.png",\n'
     '           "", "#b8860b", "#fdf4e3", special="generate_workbook"),\n',
     ""),
    (os.path.join(ROOT, "Atrium", "atrium_ui.py"),
     '        main_app_names = {"Observatum", "Curator", "Tabella", "Munia"}\n',
     '        main_app_names = {"Observatum", "Curator", "Munia"}   # Tabella retired 2026-10-07\n'),
    (os.path.join(ROOT, "Atrium", "atrium_ui.py"),
     '        # Generate Workbook button\n'
     '        gen_btn = UtilityButton("Generate Workbook", TEXT_PRIMARY)\n'
     '        gen_btn.clicked.connect(self._on_generate)\n'
     '        util_row.addWidget(gen_btn)\n',
     ""),
]


def git(*args):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, r.stdout + r.stderr


def load(p):
    raw = open(p, "rb").read().decode("utf-8")
    return raw.replace("\r\n", "\n"), "\r\n" in raw


def rel(p):
    return os.path.relpath(p, ROOT)


print("Suite tidy-up  --  " + ("APPLY" if APPLY else "DRY RUN"))
print("=" * 78)
problems = []

code, out = git("status", "--porcelain", "--untracked-files=no")
if out.strip():
    problems.append("uncommitted changes to tracked files -- commit first:\n      "
                    + out.strip().replace("\n", "\n      "))

# ---------------------------------------------------------------- edits in memory
edits = {}
for path, old, new in ATRIUM:
    text, crlf = edits.get(path) or load(path)
    n = text.count(old)
    if n != 1:
        problems.append(f"{rel(path)}: anchor found {n} times, expected 1: {old.strip()[:60]!r}")
    else:
        text = text.replace(old, new)
    edits[path] = (text, crlf)

gb_src = os.path.join(ROOT, "build_gb_basemap.py")
gb_dst = os.path.join(ROOT, "scripts", "build_gb_basemap.py")
if os.path.exists(gb_src):
    t, crlf = load(gb_src)
    old = "sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n"
    if t.count(old) != 1:
        problems.append("build_gb_basemap.py: sys.path line not found exactly once")
    t = t.replace(old, "sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))\n")
    t = t.replace("    python build_gb_basemap.py\n", "    py -3.14 scripts\\build_gb_basemap.py\n")
    edits[gb_dst] = (t, crlf)
    if os.path.exists(gb_dst):
        problems.append("scripts\\build_gb_basemap.py already exists")

# ---------------------------------------------------------------- plan moves
moves = []          # (src, dst, label)

tab = os.path.join(ROOT, "Tabella")
tab_dst = os.path.join(ARCH, f"Tabella_{STAMP}")
if os.path.isdir(tab):
    moves.append((tab, tab_dst, "tabella"))
    for b in ("run_tabella.bat", "create_data_entry.bat"):
        p = os.path.join(ROOT, "launchers", b)
        if os.path.exists(p):
            moves.append((p, os.path.join(tab_dst, "launchers", b), "tabella"))

sdir = os.path.join(ROOT, "scripts")
keep_files, archive_files, subdirs = [], [], []
for f in sorted(os.listdir(sdir), key=str.lower):
    p = os.path.join(sdir, f)
    if os.path.isdir(p):
        if f != "__pycache__":
            subdirs.append(f)
        continue
    if BAK_RE.search(f) or f.endswith(".pyc"):
        continue                                   # handled with the leftovers
    (keep_files if os.path.splitext(f)[0] in KEEP else archive_files).append(f)

# never archive something a kept script imports or calls
kept_text = ""
for f in keep_files:
    try:
        kept_text += open(os.path.join(sdir, f), encoding="utf-8", errors="replace").read()
    except OSError:
        pass
launch_text = ""
for d in ("launchers", "Atrium"):
    for dp, _, fs in os.walk(os.path.join(ROOT, d)):
        for f in fs:
            if f.endswith((".bat", ".py")):
                launch_text += open(os.path.join(dp, f), encoding="utf-8", errors="replace").read()
rescued = []
for f in list(archive_files):
    stem = re.escape(os.path.splitext(f)[0])
    pat = re.compile(rf"(\bimport\s+(scripts\.)?{stem}\b|\bfrom\s+(scripts\.)?{stem}\b|"
                     rf"scripts[\\/.]{stem}\b|['\"]{stem}\.py['\"])")
    if pat.search(kept_text) or pat.search(launch_text):
        archive_files.remove(f)
        keep_files.append(f)
        rescued.append(f)
for f in archive_files:
    moves.append((os.path.join(sdir, f), os.path.join(ARCH, f"scripts_{STAMP}", f), "scripts"))

baks = []
for dp, dirs, fs in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in NO_WALK]
    for f in fs:
        if BAK_RE.search(f):
            p = os.path.join(dp, f)
            baks.append(p)
            moves.append((p, os.path.join(ARCH, f"bak_{STAMP}", rel(p)), "bak"))

for f in LOOSE_ROOT:
    p = os.path.join(ROOT, f)
    if os.path.exists(p):
        moves.append((p, os.path.join(ARCH, f"outputs_{STAMP}", f), "outputs"))

if os.path.isdir(os.path.join(ROOT, "_dump")):
    moves.append((os.path.join(ROOT, "_dump"), os.path.join(ARCH, "_dump"), "folders"))
old_bk = os.path.join(ROOT, "_backups")
if os.path.isdir(old_bk):
    if os.path.isdir(BACKUP_ROOT):
        moves.append((old_bk, os.path.join(BACKUP_ROOT, f"old_in_tree_{STAMP}"), "folders"))
    else:
        print(f"  note: {BACKUP_ROOT} not found -- _backups left where it is")

tracked = set(git("ls-files")[1].splitlines())
for src, dst, label in moves:
    if os.path.exists(dst):
        problems.append(f"destination already exists: {dst}")
    if label == "bak" and rel(src).replace("\\", "/") in tracked:
        problems.append(f"{rel(src)} is tracked by git -- not treating it as a leftover")

# ---------------------------------------------------------------- report
def show(label, title):
    items = [m for m in moves if m[2] == label]
    print(f"\n  {title}  ({len(items)})")
    for src, dst, _ in items[:12] if label in ("bak", "scripts") else items:
        print(f"    {rel(src):<52} -> {dst if not dst.startswith(ROOT) else rel(dst)}")
    if label in ("bak", "scripts") and len(items) > 12:
        print(f"    ... and {len(items) - 12} more (all listed in the log)")

show("tabella", "1. Tabella retired")
print("     Atrium: Tabella + Generate Tabella entries, Generate Workbook button removed")
print(f"\n  2. scripts: {len(keep_files)} stay, {len(archive_files)} archived"
      + (f"; kept because a kept script uses them: {', '.join(rescued)}" if rescued else ""))
show("scripts", "   archived")
if subdirs:
    print(f"     sub-folders left alone: {', '.join(subdirs)}")
print(f"\n  3. build_gb_basemap.py -> scripts\\ (root path adjusted)" if os.path.exists(gb_src) else "")
show("bak", "4. .bak / .tmp leftovers")
show("outputs", "   loose root outputs")
show("folders", "5. root folders")

if problems:
    print("\nREFUSED -- nothing has been changed:")
    for p in problems:
        print("   x", p)
    sys.exit(1)

# compile edited Python before touching anything
for path, (text, crlf) in edits.items():
    tmp = path + ".tidytmp"
    open(tmp, "wb").write((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
    try:
        py_compile.compile(tmp, cfile=os.path.join(tempfile.gettempdir(), "tidy_check.pyc"), doraise=True)
    except py_compile.PyCompileError as e:
        for q in edits:
            if os.path.exists(q + ".tidytmp"):
                os.remove(q + ".tidytmp")
        print(f"\nREFUSED -- {rel(path)} would not compile: {e}\nNothing has been changed.")
        sys.exit(1)
    if not APPLY:
        os.remove(tmp)

if not APPLY:
    print("\nAll checks pass.  DRY RUN -- nothing has been changed. Re-run with --apply.")
    sys.exit(0)

# ---------------------------------------------------------------- apply
os.makedirs(ARCH, exist_ok=True)
log = open(LOG, "w", encoding="utf-8")
log.write(f"Suite tidy-up {STAMP}. Every move, source -> destination. Nothing was deleted.\n\n")
done = 0
try:
    for src, dst, label in moves:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(src, dst)
        log.write(f"[{label}] {src} -> {dst}\n")
        done += 1
    for path, (text, crlf) in edits.items():
        os.replace(path + ".tidytmp", path)
        log.write(f"[edit] {path}\n")
    if os.path.exists(gb_src):
        os.remove(gb_src)                          # its edited copy is now scripts\build_gb_basemap.py
        log.write(f"[moved+edited] {gb_src} -> {gb_dst}\n")
except Exception as e:
    log.close()
    print(f"\nSTOPPED after {done} of {len(moves)} moves: {e}\nEverything done so far is in {LOG}")
    sys.exit(1)
log.close()

gi = os.path.join(ROOT, ".gitignore")
text, crlf = load(gi)
have = {l.strip() for l in text.splitlines()}
add = [x for x in ("_archive/", "_dump/", "_backups/") if x not in have]
if add:
    text = text.rstrip("\n") + "\n# local-only folders (tidy-up 2026-10-07)\n" + "\n".join(add) + "\n"
    open(gi, "wb").write((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))

git("add", "-A", "--", "scripts", "Tabella", "launchers", "Atrium", "build_gb_basemap.py", ".gitignore")
print(f"\n  moved {done}, edited {len(edits)} files. Log: {rel(LOG)}")
print("\n  staged:")
print("   " + git("status", "--short", "--untracked-files=no")[1].strip().replace("\n", "\n   ")[:3000])
print("\n  Now: open Atrium (Observatum, Curator, Munia, Codex Manager), then commit:")
print('    git commit -m "Tidy-up: Tabella retired to _archive, one-off scripts archived, leftovers cleared"')
