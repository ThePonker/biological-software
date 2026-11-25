"""make_sandbox.py -- a copy of Wil's data\\*.db to try things on, away from the live data (25 Nov 2026).

    py -3.14 scripts\\make_sandbox.py                 # dry run: lists what it would copy
    py -3.14 scripts\\make_sandbox.py --apply         # copy into C:\\BiologicalSoftware_Sandbox\\data
    py -3.14 scripts\\make_sandbox.py --apply --refresh   # move the old sandbox data aside, copy anew
    py -3.14 scripts\\make_sandbox.py --dest D:\\Other  # another sandbox folder

Then start Observatum on it with launchers\\run_sandbox.bat (its window title says SANDBOX). The
live data is only ever opened read-only (sqlite3 file:...?mode=ro) and copied with conn.backup(),
never shutil. An existing sandbox data folder is never overwritten: --refresh moves it to
<sandbox>\\_old_<timestamp>\\ (nothing is deleted). An empty <sandbox>\\backups folder is made for
BIOSOFT_BACKUP_ROOT, so backups taken in the sandbox stay in the sandbox.
"""
import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_ROOT, os.path.join(_ROOT, "Observatum")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import paths  # noqa: E402

DEFAULT_DEST = r"C:\BiologicalSoftware_Sandbox"


def databases(source: str) -> list:
    """[(name, size)] of the *.db files directly in `source`."""
    return sorted((f, os.path.getsize(os.path.join(source, f))) for f in os.listdir(source)
                  if f.lower().endswith(".db") and os.path.isfile(os.path.join(source, f)))


# Not databases, but read by the apps (maps, checklists, saved filters): plain copies.
# Photos are NOT copied: the sandbox has its own empty Media folder (run_sandbox.bat sets
# BIOSOFT_MEDIA_ROOT), so nothing done in the sandbox can move or file a real photo.
EXTRAS = ("maps", "checklists", "saved_filters.json")


def extras(source: str) -> list:
    """[(name, size)] of the EXTRAS present in `source`."""
    out = []
    for name in EXTRAS:
        p = os.path.join(source, name)
        if os.path.isfile(p):
            out.append((name, os.path.getsize(p)))
        elif os.path.isdir(p):
            out.append((name, sum(os.path.getsize(os.path.join(d, f))
                                  for d, _, fs in os.walk(p) for f in fs)))
    return out


def _inside(inner: str, outer: str) -> bool:
    inner, outer = os.path.normcase(os.path.realpath(inner)), os.path.normcase(os.path.realpath(outer))
    return inner == outer or inner.startswith(outer + os.sep)


def copy_database(src_path: str, dest_path: str) -> None:
    """One database: read-only source, conn.backup() into a new file."""
    src = sqlite3.connect(f"file:{src_path}?mode=ro", uri=True)
    dst = sqlite3.connect(dest_path)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dest", default=DEFAULT_DEST, help="the sandbox folder")
    ap.add_argument("--apply", action="store_true", help="really copy (default: dry run)")
    ap.add_argument("--refresh", action="store_true", help="move an existing sandbox data folder aside")
    ap.add_argument("--source", default=str(paths.DATA_DIR), help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    source, dest = os.path.abspath(a.source), os.path.abspath(a.dest)
    data = os.path.join(dest, "data")
    print("\nSandbox copy of the data")
    print("=" * 40)
    print(f"  live data (read only): {source}")
    print(f"  sandbox:               {dest}")
    if _inside(dest, source) or _inside(source, dest) or _inside(dest, _ROOT):
        print("  refusing: the sandbox must be a folder apart from the live data and the code. "
              "Nothing has been changed.")
        return 1
    if not os.path.isdir(source):
        print("  refusing: the live data folder is not there. Nothing has been changed.")
        return 1
    dbs = databases(source)
    for name, size in dbs:
        print(f"    {name:<22} {size / 1048576:10.1f} MB")
    print(f"  {len(dbs)} database(s), {sum(s for _, s in dbs) / 1048576:,.1f} MB")
    ext = extras(source)
    for name, size in ext:
        print(f"    {name:<22} {size / 1048576:10.1f} MB  (plain copy)")
    exists = os.path.isdir(data) and bool(os.listdir(data))
    old = os.path.join(dest, f"_old_{datetime.now():%Y%m%d_%H%M%S}")
    if exists and not a.refresh:
        print(f"  refusing: {data} already holds a sandbox. Use --refresh to move it aside "
              f"(to {os.path.join(dest, '_old_<timestamp>')}) and copy again. Nothing has been changed.")
        return 1
    if exists:
        print(f"  --refresh: the old sandbox data would move to {old} (nothing is deleted)")
    if not a.apply:
        print("\n  DRY RUN: nothing has been copied. Add --apply to do it.")
        print("  READ ONLY on the live data: it was not changed.")
        return 0
    os.makedirs(dest, exist_ok=True)
    if exists:
        try:
            os.rename(data, old)
        except OSError as e:             # Windows: a sandbox app still has a database open
            print(f"  refusing: the old sandbox data could not be moved aside ({e.strerror}). "
                  "Close the sandbox Observatum / Data Entry and try again. Nothing has been changed.")
            return 1
        print(f"  moved the old sandbox data to {old}")
    os.makedirs(data, exist_ok=True)
    os.makedirs(os.path.join(dest, "backups"), exist_ok=True)
    os.makedirs(os.path.join(dest, "Media", "Photos", "Life"), exist_ok=True)
    for name, _size in dbs:
        copy_database(os.path.join(source, name), os.path.join(data, name))
        print(f"  copied {name}")
    for name, _size in ext:
        src, dst = os.path.join(source, name), os.path.join(data, name)
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        print(f"  copied {name}")
    print(f"\n  Done: {len(dbs)} database(s) in {data}. Start it with launchers\\run_sandbox.bat.")
    print("  READ ONLY on the live data: it was opened read-only and not changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
