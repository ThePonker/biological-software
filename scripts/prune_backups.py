"""Prune superseded pre-change backups in C:\\BiologicalSoftware_Backups\\reference.

KEEPS
  * everything that is not a dated codex_/observatum_ backup (UKSI.mdb, uksi.db,
    pantheon.db, vc_lookup.db, the reference codex.db) -- never touched
  * Codex milestones: before the SQS fix, before the NS-excludes fix, before the
    first review load of 4 Oct, and the newest Codex backup
  * the two newest observatum backups
DELETES the rest of the dated codex_/observatum_ backups -- each guarded a
change that is now verified, committed and superseded by a later backup.

Dates come from the FILENAME, never the file's modified time (OneDrive rule).
Lists everything first; deletes only after you type DELETE.

Run:  python scripts\\prune_backups.py
"""
import os, re, sys

D = r"C:\BiologicalSoftware_Backups\reference"
STAMP = re.compile(r"^(codex|observatum)_.+_(\d{8}_\d{6})(?:_\d+)?\.db$")
CODEX_KEEP = {"codex_pre_invert_filter_20261002_202956.db",
              "codex_pre_excludes_20261004_181520.db",
              "codex_pre_review_20261004_183836.db"}

files = sorted(os.listdir(D))
dated = [(f, STAMP.match(f)) for f in files]
codex = sorted((m.group(2), f) for f, m in dated if m and m.group(1) == "codex")
obs = sorted((m.group(2), f) for f, m in dated if m and m.group(1) == "observatum")
keep = set(CODEX_KEEP) | ({codex[-1][1]} if codex else set()) | {f for _, f in obs[-2:]}
missing = [k for k in CODEX_KEEP if k not in files]
if missing:
    sys.exit(f"  x expected milestone backups not found: {missing} -- nothing deleted")

size = lambda f: os.path.getsize(os.path.join(D, f)) / 1e6
delete = [f for f, m in dated if m and f not in keep]
print("Prune reference backups")
print("=" * 70)
print("KEEP")
for f in files:
    if f not in delete:
        why = "rebuild source / not a dated backup" if not STAMP.match(f) else "milestone / newest"
        print(f"  {size(f):>7.0f} MB  {f:<55} {why}")
print("\nDELETE")
for f in delete:
    print(f"  {size(f):>7.0f} MB  {f}")
total = sum(size(f) for f in delete)
print(f"\n  {len(delete)} files, {total / 1000:.2f} GB to delete; "
      f"{sum(size(f) for f in files if f not in delete) / 1000:.2f} GB kept")
if not delete:
    sys.exit("  nothing to delete")
if input("\nType DELETE to remove the files listed above: ").strip() != "DELETE":
    sys.exit("  cancelled -- nothing deleted")
for f in delete:
    os.remove(os.path.join(D, f))
print(f"  deleted {len(delete)} files ({total / 1000:.2f} GB)")
