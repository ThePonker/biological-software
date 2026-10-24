"""Prune superseded pre-change backups in C:\\BiologicalSoftware_Backups\\reference.

KEEPS
  * everything that is not a dated codex_/observatum_ backup (UKSI.mdb, uksi.db,
    pantheon.db, vc_lookup.db, the reference codex.db) -- never touched
  * Codex milestones: before the SQS fix, before the NS-excludes fix, before the
    first review load of 4 Oct
  * the newest backups PER LABEL: a label is the file name with its timestamp taken
    off (observatum_pre_import_20261010_101500.db -> observatum_pre_import.db).
    Newest 1 per codex label, newest 2 per observatum label.
MOVES the rest of the dated codex_/observatum_ backups into reference\\_expired\\
(never deletes -- empty that folder by hand when you want the space back).

Dates come from the FILENAME, never the file's modified time (OneDrive rule).
Dry run by default: lists what would move and changes nothing.

Run:  py -3.14 scripts\\prune_backups.py            (dry run)
      py -3.14 scripts\\prune_backups.py --apply    (move them)
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import backup_service  # noqa: E402

STAMP = re.compile(r"^(codex|observatum)_.+_(\d{8}_\d{6})(?:[-_]\d+)?\.db$")
_STAMP_TAIL = re.compile(r"_\d{8}_\d{6}(?:[-_]\d+)?(?=\.db$)")
CODEX_KEEP = {"codex_pre_invert_filter_20261002_202956.db",
              "codex_pre_excludes_20261004_181520.db",
              "codex_pre_review_20261004_183836.db"}
KEEP_NEWEST = {"codex": 1, "observatum": 2}   # per label


def label_of(name):
    """File name with its timestamp removed."""
    return _STAMP_TAIL.sub("", name)


def reference_dir():
    return os.path.join(backup_service.BACKUP_ROOT, backup_service.REFERENCE)


def plan(folder):
    """(files, keep set, move list) for the dated backups in folder."""
    files = sorted(f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f)))
    groups = {}
    for f in files:
        m = STAMP.match(f)
        if m:
            groups.setdefault((m.group(1), label_of(f)), []).append((m.group(2), f))
    keep = {f for f in CODEX_KEEP if f in files}
    for (kind, _label), items in groups.items():
        items.sort()
        keep |= {f for _, f in items[-KEEP_NEWEST[kind]:]}
    move = [f for f in files if STAMP.match(f) and f not in keep]
    return files, keep, move


def move_expired(folder, names):
    """Move names into folder\\_expired\\ (a clash gets a number). Returns how many moved."""
    exp = os.path.join(folder, backup_service.EXPIRED)
    os.makedirs(exp, exist_ok=True)
    n = 0
    for f in names:
        dest = os.path.join(exp, f)
        k = 1
        while os.path.exists(dest):
            k += 1
            dest = os.path.join(exp, f"{k}_{f}")
        os.replace(os.path.join(folder, f), dest)
        n += 1
    return n


def main(argv=None):
    apply = "--apply" in (sys.argv[1:] if argv is None else argv)
    D = reference_dir()
    if not os.path.isdir(D):
        sys.exit(f"  x {D} not found -- nothing moved")
    if apply:
        from shared.away_mode import refuse_if_away
        refuse_if_away("prune_backups")
    files, keep, move = plan(D)
    missing = [k for k in CODEX_KEEP if k not in files]
    if missing:
        sys.exit(f"  x expected milestone backups not found: {missing} -- nothing moved")

    size = lambda f: os.path.getsize(os.path.join(D, f)) / 1e6
    print("Prune reference backups" + ("" if apply else "  (DRY RUN)"))
    print("=" * 70)
    print("KEEP")
    for f in files:
        if f not in move:
            why = ("rebuild source / not a dated backup" if not STAMP.match(f)
                   else "milestone" if f in CODEX_KEEP else "newest of its label")
            print(f"  {size(f):>7.0f} MB  {f:<55} {why}")
    print("\nMOVE to _expired" if apply else "\nWOULD MOVE to _expired")
    for f in move:
        print(f"  {size(f):>7.0f} MB  {f}")
    total = sum(size(f) for f in move)
    print(f"\n  {len(move)} files, {total / 1000:.2f} GB; "
          f"{sum(size(f) for f in files if f not in move) / 1000:.2f} GB stays")
    if not move:
        print("  nothing to move")
    elif apply:
        n = move_expired(D, move)
        print(f"  moved {n} files into {os.path.join(D, backup_service.EXPIRED)}")
        return 0
    if not apply:
        print("\nRun again with --apply to move them. Nothing has been changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
