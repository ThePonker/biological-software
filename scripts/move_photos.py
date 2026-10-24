"""B1: move photos as listed in a move list, with a log, and put them back from that log.

    py -3.14 scripts\\move_photos.py                          dry run (the default): checks only
    py -3.14 scripts\\move_photos.py --apply                  moves, logging each one
    py -3.14 scripts\\move_photos.py --reverse <log.csv>      dry run of putting them back
    py -3.14 scripts\\move_photos.py --reverse <log.csv> --apply

The move list is scripts\\_oneoff\\photo_moves_<date>.csv (newest; scripts\\build_photo_moves.py),
columns source, destination -- both relative to the library root (--root, default
OneDrive\\Documents\\Media, as the check script).

NOTHING IS EVER DELETED OR OVERWRITTEN. Each move is os.rename on the same drive (inside OneDrive
it is a rename); a move to another drive is refused. Before any move, every row is checked:
the source exists, the destination does not, no two rows share a destination, both stay inside
the root. --apply refuses to start if any check fails. Folders are created as needed; emptied
folders are left in place.

The log (scripts\\_oneoff\\photo_moves_log_<date-time>.csv) gets one line per move as it
happens (source, destination, size, time), flushed each time, so a run that stops half way can
still be reversed. After each move the destination is checked (exists, same size, source gone).
--reverse reads a log and moves each file back, newest first, with the same checks and its own
log.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import glob
import os
import sqlite3
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRY = "DRY RUN. Nothing has been moved."
LOG_FIELDS = ["time", "source", "destination", "size_bytes"]


def newest_moves():
    found = sorted(glob.glob(os.path.join(ROOT, "scripts", "_oneoff", "photo_moves_2*.csv")))
    return found[-1] if found else None


def read(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def inside(root: Path, rel: str) -> Path:
    p = (root / rel).resolve()
    if p != root and root not in p.parents:
        raise ValueError(f"outside the library: {rel}")
    return p


_BAD_CHARS = set('<>:"|?*')
MAX_PATH = 259                     # Windows without long paths: 260 including the end mark


def name_problem(rel: str) -> str:
    """Why Windows would refuse or silently change this relative path, or ''."""
    for part in rel.replace("\\", "/").split("/"):
        if not part or part in (".", ".."):
            continue
        if _BAD_CHARS & set(part) or any(ord(c) < 32 for c in part):
            return f"character Windows does not allow in '{part}'"
        if part != part.rstrip(" ."):
            return f"'{part}' ends in a space or dot (Windows would drop it)"
    return ""


def check(pairs, root: Path):
    """[(source path, destination path, problem or '')] for (source, destination) pairs."""
    out, dests, sources = [], {}, {}
    root = root.resolve()
    dest_dirs = set()
    for src, dst in pairs:
        problem = ""
        try:
            s, d = inside(root, src), inside(root, dst)
        except ValueError as e:
            out.append((None, None, str(e)))
            continue
        key, skey = str(d).casefold(), str(s).casefold()
        blocking = next((a for a in d.parents if a != root and root in a.parents and a.is_file()), None)
        if not s.is_file():
            problem = "source not found"
        elif skey in sources:
            problem = f"source listed twice (also row for {sources[skey]})"
        elif d.exists():
            problem = "destination already exists"
        elif key in dests:
            problem = f"same destination as {dests[key]}"
        elif blocking is not None:
            problem = f"a file is in the way of the folder: {blocking.name}"
        elif len(str(d)) > MAX_PATH and os.name == "nt":
            problem = f"path too long for Windows ({len(str(d))} characters)"
        else:
            problem = name_problem(dst)
        dests.setdefault(key, src)
        sources.setdefault(skey, dst)
        dest_dirs.update(str(a).casefold() for a in d.parents)
        out.append((s, d, problem))
    # a planned destination FILE that another row needs as a FOLDER
    return [(s, d, p or ("another row's destination is in the way of this folder"
                         if d is not None and str(d).casefold() in dest_dirs else ""))
            for s, d, p in out]


def same_drive(a: Path, b: Path) -> bool:
    return os.path.splitdrive(str(a))[0].casefold() == os.path.splitdrive(str(b))[0].casefold()


def stored(rel: str) -> str:
    """A path as photo_links stores it ('/' separators, no leading './' or '/')."""
    from shared import photo_links as pl
    return pl.norm(rel)


def run(pairs, root: Path, apply: bool, log_path: str, label: str, db_path=None) -> int:
    checked = check(pairs, root)
    bad = [(i, c) for i, c in enumerate(checked) if c[2]]
    print(f"{label}: {len(pairs):,} files; problems: {len(bad)}")
    for i, (s, d, problem) in bad[:30]:
        print(f"  {pairs[i][0]}  ->  {pairs[i][1]}: {problem}")
    if len(bad) > 30:
        print(f"  ... and {len(bad) - 30} more")
    new_dirs = {str(d.parent) for s, d, p in checked if d is not None and not d.parent.exists()}
    print(f"New folders needed: {len(new_dirs):,}")
    if not apply:
        print(DRY + (" Fix the problems above before --apply." if bad else
                     " All checks passed: run again with --apply."))
        return 1 if bad else 0
    if bad:
        print("Refused: --apply needs every check to pass. " + DRY)
        return 1
    if any(not same_drive(s, d) for s, d, _ in checked):
        print("Refused: a move to another drive (copy and delete) is not done by this script. " + DRY)
        return 1
    from shared.away_mode import refuse_if_away
    refuse_if_away("move_photos")                        # photos are the live library
    from shared.backup_service import backup_file_written, backup_main_only
    if not (backup_file_written(db_path, "pre-move-photos") if db_path
            else backup_main_only("pre-move-photos")):
        print("Refused: the backup of observatum.db failed, so nothing was moved. " + DRY)
        return 1
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    conn = None
    if db_path:
        if not Path(str(db_path)).is_file():
            print(f"Refused: {db_path} not found, so photo links could not follow (give --db). "
                  "Nothing was moved.")
            return 1
        conn = sqlite3.connect(str(db_path))
    try:
        return _apply(checked, pairs, log_path, conn)
    finally:
        if conn is not None:
            conn.close()


def _apply(checked, pairs, log_path, conn) -> int:
    from shared import photo_links as pl
    moved = relinked = 0
    if conn is not None and not pl.has_table(conn):
        conn = None                                  # a database without photo links: nothing to follow
    with open(log_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        w.writeheader()
        f.flush()
        for (rel_s, rel_d), (s, d, _) in zip(pairs, checked):
            size = s.stat().st_size
            if d.exists():                       # appeared since the check: stop, never overwrite
                print(f"STOPPED: {rel_d} appeared since the check. Moved {moved}; log {log_path}")
                return 1
            try:
                d.parent.mkdir(parents=True, exist_ok=True)
                os.rename(s, d)
            except OSError as e:
                print(f"STOPPED at {rel_s}: {e}. Moved {moved}; log {log_path}")
                return 1
            # logged the moment it has moved, before the check, so --reverse always finds it
            w.writerow({"time": datetime.datetime.now().isoformat(timespec="seconds"),
                        "source": rel_s, "destination": rel_d, "size_bytes": size})
            f.flush()
            moved += 1
            if conn is not None:                   # the photo's links follow it, one move at a time
                try:
                    relinked += pl.repoint(conn, stored(rel_s), stored(rel_d))
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    print(f"STOPPED: {rel_s} moved (it is in the log) but its links could not "
                          f"follow: {e}. Moved {moved}; log {log_path}")
                    return 1
            if not d.is_file() or d.stat().st_size != size or s.exists():
                print(f"STOPPED: {rel_s} -> {rel_d} did not check out after the move "
                      f"(it is in the log). Moved {moved}; log {log_path}")
                return 1
    print(f"Moved {moved:,} files; {relinked:,} photo links repointed. Log: {log_path}")
    print(f"To put them back: py -3.14 scripts\\move_photos.py --reverse \"{log_path}\"")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--moves", default=None, help="the move list (newest photo_moves_*.csv)")
    ap.add_argument("--reverse", default=None, metavar="LOG", help="put back the moves in this log")
    ap.add_argument("--root", default=None, help="the library (default paths.MEDIA_ROOT)")
    ap.add_argument("--db", default=None, help="observatum.db whose photo links follow the moves "
                                               "(default paths.OBSERVATUM_DB)")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--log", default=None)
    a = ap.parse_args(argv)
    sys.path.insert(0, ROOT)
    import paths
    if a.root is None:
        a.root = str(paths.MEDIA_ROOT)
    if a.db is None:
        a.db = str(paths.OBSERVATUM_DB)
    if a.apply:
        from shared.away_mode import refuse_if_away
        refuse_if_away("move_photos")
    root = Path(a.root)
    if not root.is_dir():
        print(f"Library not found: {root} (give it with --root). " + DRY)
        return 1
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if a.reverse:
        rows = read(a.reverse)
        pairs = [(r["destination"], r["source"]) for r in reversed(rows)]
        log = a.log or os.path.join(ROOT, "scripts", "_oneoff", f"photo_moves_reverse_log_{stamp}.csv")
        return run(pairs, root, a.apply, log, f"Reverse of {a.reverse}", a.db)
    moves = a.moves or newest_moves()
    if not moves or not os.path.exists(moves):
        print("No move list found: run scripts\\build_photo_moves.py first. " + DRY)
        return 1
    pairs = [(r["source"], r["destination"]) for r in read(moves)]
    log = a.log or os.path.join(ROOT, "scripts", "_oneoff", f"photo_moves_log_{stamp}.csv")
    print(f"Library: {root}\nMove list: {moves}")
    return run(pairs, root, a.apply, log, "Moves", a.db)


if __name__ == "__main__":
    sys.exit(main())
