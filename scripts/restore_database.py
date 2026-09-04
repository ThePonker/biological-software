"""restore_database.py -- restore observatum.db from a backup, with the app closed.

    python scripts/restore_database.py                     # pick from current/previous
    python scripts/restore_database.py "C:\\path\\to\\a.db"  # restore a specific file

Why standalone
--------------
Restoring a database from inside the application that is holding it open is
awkward and risky: connections stay open, and stale -wal / -shm side-files can be
left behind that do not match the restored main file. Doing it with nothing
holding the database avoids the whole problem.

What it does
------------
1. Refuses to run if observatum.db looks to be in use.
2. Verifies the chosen backup with PRAGMA integrity_check BEFORE touching anything.
3. Takes a safety copy of the current database via the SQLite backup API.
4. Removes stale -wal / -shm side-files.
5. Copies the backup into place and verifies it again.

Nothing is overwritten until the source has been checked.
"""
import os
import shutil
import sqlite3
import sys
from datetime import datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
import paths  # noqa: E402

BACKUP_ROOT = r"C:\BiologicalSoftware_Backups"


def integrity_ok(path: str) -> bool:
    try:
        c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        result = c.execute("PRAGMA integrity_check").fetchone()[0]
        c.close()
        return result == "ok"
    except Exception as e:
        print(f"  cannot read {path}: {e}")
        return False


def describe(path: str) -> str:
    try:
        c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        obs = c.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
        spec = c.execute("SELECT COUNT(*) FROM specimens").fetchone()[0]
        try:
            stg = c.execute("SELECT COUNT(*) FROM entry_staging").fetchone()[0]
        except sqlite3.Error:
            stg = 0
        c.close()
        when = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M")
        mb = os.path.getsize(path) / 1048576
        return f"{obs:,} obs / {spec:,} specimens / {stg:,} staged  -  {mb:.0f} MB  -  {when}"
    except Exception as e:
        return f"(unreadable: {e})"


def in_use(path: str) -> bool:
    """Best-effort check that nothing holds the database."""
    for ext in ("-wal", "-shm"):
        if os.path.exists(path + ext) and os.path.getsize(path + ext) > 0:
            return True
    try:                                   # an exclusive lock fails if it is open
        c = sqlite3.connect(path, timeout=1)
        c.execute("PRAGMA locking_mode = EXCLUSIVE")
        c.execute("BEGIN EXCLUSIVE")
        c.execute("COMMIT")
        c.close()
        return False
    except sqlite3.OperationalError:
        return True
    except Exception:
        return False


def choose_backup() -> str:
    candidates = []
    for sub in ("current", "previous"):
        p = os.path.join(BACKUP_ROOT, sub, "observatum.db")
        if os.path.exists(p):
            candidates.append(p)
    if not candidates:
        print(f"No backups found under {BACKUP_ROOT}")
        return ""
    print("\nAvailable backups:\n")
    for i, p in enumerate(candidates, 1):
        print(f"  {i}. {os.path.relpath(p, BACKUP_ROOT)}")
        print(f"     {describe(p)}")
    print()
    choice = input(f"Restore which? [1-{len(candidates)}, or Enter to cancel] ").strip()
    if not choice.isdigit() or not (1 <= int(choice) <= len(candidates)):
        return ""
    return candidates[int(choice) - 1]


def main() -> int:
    live = str(paths.OBSERVATUM_DB)

    print("\nRestore observatum.db")
    print("=" * 60)
    print(f"  live database: {live}")
    if os.path.exists(live):
        print(f"  currently:     {describe(live)}")

    if in_use(live):
        print("\n  The database appears to be IN USE.")
        print("  Close Observatum (and any other tool using it) and run this again.")
        return 1

    src = sys.argv[1] if len(sys.argv) > 1 else choose_backup()
    if not src:
        print("\nCancelled.")
        return 0
    if not os.path.exists(src):
        print(f"\nNot found: {src}")
        return 1

    print(f"\n  restoring from: {src}")
    print(f"  that file is:   {describe(src)}")

    print("\n  checking the backup before touching anything...")
    if not integrity_ok(src):
        print("  BACKUP FAILED ITS INTEGRITY CHECK - nothing has been changed.")
        return 1
    print("  backup integrity: ok")

    if input("\nProceed? This replaces your live database. [y/N] ").strip().lower() != "y":
        print("Cancelled.")
        return 0

    # safety copy of what is there now, via the backup API
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safety = os.path.join(BACKUP_ROOT, f"pre_restore_{stamp}.db")
    if os.path.exists(live):
        try:
            s = sqlite3.connect(f"file:{live}?mode=ro", uri=True)
            d = sqlite3.connect(safety)
            s.backup(d)
            d.close()
            s.close()
            print(f"\n  safety copy: {safety}")
        except Exception as e:
            print(f"\n  could not make a safety copy: {e}")
            print("  stopping - nothing has been changed.")
            return 1

    # clear stale side-files, then copy in
    for ext in ("-wal", "-shm"):
        p = live + ext
        if os.path.exists(p):
            try:
                os.remove(p)
                print(f"  removed stale {os.path.basename(p)}")
            except OSError as e:
                print(f"  could not remove {p}: {e}")
                print("  stopping - nothing has been changed.")
                return 1

    try:
        shutil.copy2(src, live)
    except Exception as e:
        print(f"\n  RESTORE FAILED: {e}")
        print(f"  your data is still in the safety copy: {safety}")
        return 1

    if not integrity_ok(live):
        print("\n  RESTORED FILE FAILED ITS INTEGRITY CHECK.")
        print(f"  put the safety copy back: {safety}")
        return 1

    print("\n  restored and verified.")
    print(f"  now: {describe(live)}")
    print("\nDone. Start Observatum and check the record counts.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
