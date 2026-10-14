"""standardise_specimen_names.py -- specimen photo names to Wil's standard (14 Oct 2026):
no capitals but the genus's first letter, dates '15.ix.17'. 'Philonthus decorus GEN 16.iv.19'
becomes 'Philonthus decorus gen 16.iv.19'.

    py -3.14 scripts\\standardise_specimen_names.py              # dry run: lists the renames
    py -3.14 scripts\\standardise_specimen_names.py --apply      # backup, then rename

Only images in 'Specimen' folders under Photos\\Life are looked at (field photos keep their
'Genus species - Common Name' style). The extension is left as it is. A rename is a move in
the same folder (shared/photo_files.move_photo: never over another file, logged in
data\\photo_moves\\, the photo's record links follow). A name already taken is skipped and
listed. --apply backs observatum.db up first (the links change); close Observatum first.
"""
import argparse
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_ROOT, os.path.join(_ROOT, "Observatum")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import paths  # noqa: E402
from shared import photo_files as pf  # noqa: E402

BACKUP_DIR = os.path.join(r"C:\BiologicalSoftware_Backups", "reference")


def plan(life: Path):
    """[(path, new path)] for every specimen photo whose name is not yet the standard."""
    from shared.photo_housekeeping import nonstandard_names
    return nonstandard_names(life)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--root", default=str(paths.MEDIA_ROOT))
    ap.add_argument("--db", default=str(paths.OBSERVATUM_DB), help=argparse.SUPPRESS)
    ap.add_argument("--backup-dir", default=BACKUP_DIR, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    paths.MEDIA_ROOT = Path(a.root)
    life = Path(a.root) / "Photos" / "Life"
    print(f"\nSpecimen photo names -- the standard\n  library: {a.root}")
    if not life.is_dir():
        print("  Photos\\Life not found (give the library with --root). Nothing has been changed.")
        return 1
    todo = plan(life)
    taken = [(s, d) for s, d in todo if d.exists() and d.name.casefold() != s.name.casefold()]
    for s, d in todo:
        print(f"  {s.name}  ->  {d.name}" + ("   (name taken: skipped)" if (s, d) in taken else ""))
    print(f"  to rename: {len(todo) - len(taken)}; name already taken (left): {len(taken)}")
    if not a.apply:
        print("\nDRY RUN. Nothing has been changed. Run with --apply to rename.")
        return 0
    if not todo:
        print("  nothing to do. Nothing has been changed.")
        return 0
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    os.makedirs(a.backup_dir, exist_ok=True)
    dest = os.path.join(a.backup_dir, f"observatum_pre_specimen_names_{stamp}.db")
    src, d = sqlite3.connect(a.db), sqlite3.connect(dest)
    try:
        src.backup(d)
    finally:
        d.close()
        src.close()
    print(f"  backed up to {dest}")
    log = pf.new_log_path()
    conn = sqlite3.connect(a.db)
    done = failed = 0
    try:
        for s, d in todo:
            if (s, d) in taken:
                continue
            try:
                if d.name.casefold() == s.name.casefold():     # case only: via a free name
                    tmp = pf.free_path(s.parent, s.stem + " _", s.suffix)
                    pf.move_photo(conn, s, tmp, log)
                    pf.move_photo(conn, tmp, d, log)
                else:
                    pf.move_photo(conn, s, d, log)
                done += 1
            except OSError as e:
                failed += 1
                print(f"  ! {s.name}: {e}")
    finally:
        conn.close()
    print(f"  renamed: {done}; not renamed: {failed}. Log: {log}")
    print(f"  To put them back: py -3.14 scripts\\move_photos.py --reverse \"{log}\"")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
