"""Load the BRC provisional atlases' species accounts into Codex -- all at once.

Each atlas sits in data\\reviews\\<group>_brc_atlas_<year>\\ (or _ite_ / _cox_)
with source\\ (the PDF as downloaded) and extracted\\ (review.csv, accounts.csv,
an empty statuses.csv, and extraction_check.csv listing every name match and
every scanning correction). They are accounts only: no status is written.

This runs scripts\\load_review.py -- the one loader -- on each atlas folder not
yet in Codex, so every atlas goes in by exactly the same rules as the status
reviews. Accounts show newest first, so an atlas account sits under any later
review's account for the same species.

DRY RUN by default: each atlas's dry run, then a summary. Nothing is written.
--apply: one backup of codex.db, then each atlas loaded in turn.
Close Codex Manager and Observatum first.

Run:  py -3.14 scripts\\load_atlases.py
      py -3.14 scripts\\load_atlases.py --apply
"""
import argparse, csv, glob, os, re, sqlite3, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "scripts")]
import paths

ap = argparse.ArgumentParser()
ap.add_argument("--apply", action="store_true")
ap.add_argument("--only", help="load just this folder name")
a = ap.parse_args()

folders = sorted(f for f in glob.glob(os.path.join(ROOT, "data", "reviews", "*"))
                 if re.search(r"_(brc|ite|cox|bsbi)_atlas", os.path.basename(f))
                 and os.path.exists(os.path.join(f, "extracted", "accounts.csv")))
if a.only:
    folders = [f for f in folders if os.path.basename(f) == a.only]

c = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)
loaded = {n for (n,) in c.execute("SELECT review_name FROM reviews")}
c.close()

def held_accounts(name):
    c = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)
    rows = c.execute("""SELECT p.species_name, p.profile_text FROM species_profiles p
                        JOIN reviews r ON r.id = p.review_id WHERE r.review_name=?""", (name,)).fetchall()
    c.close()
    return sorted(t for _, t in rows)


def current(name, f):
    """True when Codex holds exactly this folder's accounts. Rows with a TVK must all be held;
    a row without one may also be held (load_review matched it by name) -- nothing else."""
    held = set(held_accounts(name))
    rows = [r for r in csv.DictReader(open(os.path.join(f, "extracted", "accounts.csv"), encoding="utf-8-sig"))
            if r["account_text"].strip()]
    return {r["account_text"] for r in rows if r.get("tvk")} <= held <= {r["account_text"] for r in rows}


todo, done, refresh = [], [], []
for f in folders:
    name = list(csv.DictReader(open(os.path.join(f, "extracted", "review.csv"), encoding="utf-8-sig")))[0]["review_name"]
    if name not in loaded:
        todo.append((f, name))
    elif not current(name, f):
        refresh.append((f, name))                 # re-extracted since it was loaded
    else:
        done.append((f, name))

print("")
print("Atlas accounts load" + ("" if a.apply else "  --  DRY RUN"))
print("=" * 78)
print(f"  atlas folders: {len(folders)}   already in Codex and current: {len(done)}   "
      f"to refresh (text improved since loading): {len(refresh)}   to load: {len(todo)}")
if not todo and not refresh:
    print("\n  Nothing to do. Nothing has been changed.\n")
    sys.exit(0)

backup_path = None
if a.apply:
    from import_status_review import backup
    backup_path = backup(paths.CODEX_DB, "codex_atlases")
    print(f"  backup: {backup_path}")

summary = []
for f, name in [(f, n) for f, n in refresh] + todo:
    cmd = [sys.executable, os.path.join(ROOT, "scripts", "load_review.py"), f]
    if (f, name) in refresh:
        cmd.append("--replace-accounts")
    if a.apply:
        cmd += ["--apply", "--backup-done", backup_path]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = r.stdout + r.stderr
    m = re.search(r"ACCOUNTS -> codex.db species_profiles: (\d+)\s+unmatched (\d+)", out)
    w = re.search(r"review #(\d+): \d+ status entries, (\d+) accounts written", out)
    ok = r.returncode == 0 and (w or not a.apply)
    summary.append((os.path.basename(f), m.group(1) if m else "?", m.group(2) if m else "?",
                    w.group(2) if w else "-", ("refreshed " if (f, name) in refresh else "") + ("ok" if ok else "FAILED")))
    if not ok or "x " in out.split("ACCOUNTS")[0][-400:]:
        print(out)
    if a.apply and not ok:
        print(f"  x stopped at {os.path.basename(f)} -- the atlases before it are loaded; nothing else written")
        break

print("\n  %-52s %8s %9s %8s" % ("atlas", "accounts", "unmatched", "written"))
for fold, acc, un, wr, st in summary:
    print("  %-52s %8s %9s %8s  %s" % (fold[:52], acc, un, wr, st))
print("\n  Unmatched names and every scanning correction: extracted\\extraction_check.csv in each folder.")
print("" if a.apply else "\n  DRY RUN -- nothing has been changed. Re-run with --apply to write.\n")
