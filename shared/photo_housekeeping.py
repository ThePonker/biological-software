"""photo_housekeeping -- the Photos part of the cleaning report (bench photos take 2, 14 Oct
2026). Read-only, except archive_empty_folders(), which MOVES empty folders out of the library
(never deletes). No Qt.

  empty_folders()      folders under Photos/Life with no file anywhere inside (a re-det or a
                       rename can leave one). Only the topmost empty folder is listed.
  bench_waiting()      photos in Photos/_Bench: still on a Data Entry row, on a record whose
                       species was not picked from the list, or on nothing (row deleted).
  missing_files()      links to a photo whose file is not there (moved or renamed by hand).
  nonstandard_names()  specimen photos not yet named to the standard ('... gen 16.iv.19').
"""
from __future__ import annotations

import csv
import datetime
import os
from pathlib import Path
from typing import List, Optional, Tuple

from shared import bench_photos as bp
from shared import photo_files as pf
from shared import photo_links as pl
from shared.photo_names import IMAGE_EXTS, specimen_stem

# Windows / OneDrive / macOS keep these in folders; they do not make a folder "in use"
IGNORED_FILES = {"desktop.ini", "thumbs.db", ".ds_store"}


def _has_files(folder: str) -> bool:
    for _dirpath, _dirs, files in os.walk(folder):
        if any(f.casefold() not in IGNORED_FILES for f in files):
            return True
    return False


def empty_folders(life: Optional[Path] = None) -> List[str]:
    """Folders under Life holding no file at any depth, as paths relative to Life ('/'),
    topmost only, sorted."""
    life = Path(life or pf.life_root())
    if not life.is_dir():
        return []
    out = []
    stack = [str(life)]
    while stack:
        d = stack.pop()
        try:
            subs = [e.path for e in os.scandir(d) if e.is_dir(follow_symlinks=False)]
        except OSError:
            continue
        for s in subs:
            if _has_files(s):
                stack.append(s)
            else:
                out.append(pl.norm(os.path.relpath(s, str(life))))
    return sorted(out, key=str.casefold)


def archive_empty_folders(folders: List[str], life: Optional[Path] = None,
                          archive_root: Optional[Path] = None) -> Tuple[List[str], List[str], Path]:
    """Move these empty folders (relative to Life) into _archive/empty_folders_<date>/<same
    path>. A folder that is no longer empty is left. Returns (moved, notes, log path)."""
    import paths
    life = Path(life or pf.life_root())
    day = datetime.date.today().strftime("%Y%m%d")
    dest_root = Path(archive_root or Path(paths.ROOT) / "_archive") / f"empty_folders_{day}"
    log = Path(paths.PHOTO_MOVES_DIR) / f"empty_folders_{datetime.datetime.now():%Y%m%d_%H%M%S_%f}.csv"
    moved, notes = [], []
    for r in folders:
        src = life / r
        dst = dest_root / r
        try:
            if not src.is_dir():
                notes.append(f"{r}: not there any more")
                continue
            if _has_files(str(src)):
                notes.append(f"{r}: no longer empty -- left")
                continue
            if dst.exists():
                notes.append(f"{r}: already in {dest_root.name} -- left")
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.rename(src, dst)
            moved.append(r)
            new = not log.exists()
            log.parent.mkdir(parents=True, exist_ok=True)
            with open(log, "a", encoding="utf-8-sig" if new else "utf-8", newline="") as f:
                w = csv.writer(f)
                if new:
                    w.writerow(["time", "source", "destination"])
                w.writerow([datetime.datetime.now().isoformat(timespec="seconds"), str(src), str(dst)])
        except OSError as e:
            notes.append(f"{r}: not moved ({e})")
    if moved:
        pf.refresh()
    return moved, notes, log


def bench_waiting(conn) -> List[Tuple[str, str]]:
    """(stored path, what it is waiting for) for every photo in _Bench."""
    out = []
    for p in bp.bench_files():
        why = "not linked to anything (its row was deleted)"
        if conn is not None and pl.has_table(conn):
            st = pl.STAGING if pl.has_staging_column(conn) else "NULL"
            rows = conn.execute(f"SELECT {st}, observation_id, specimen_id FROM {pl.TABLE} WHERE photo_path = ?",
                                (p,)).fetchall()
            if any(r[0] is not None for r in rows):
                why = "on a Data Entry row not yet committed"
            elif any(r[1] is not None or r[2] is not None for r in rows):
                why = "on a record whose species was not picked from the list"
        out.append((p, why))
    return out


def missing_files(conn) -> List[Tuple[str, str]]:
    """(stored path, linked to) for links whose file is not there."""
    if conn is None or not pl.has_table(conn):
        return []
    st = pl.STAGING if pl.has_staging_column(conn) else "NULL"
    out = []
    for path, sid, oid, rid in conn.execute(
            f"SELECT DISTINCT photo_path, specimen_id, observation_id, {st} FROM {pl.TABLE} ORDER BY photo_path"):
        if not pf.absolute(path).is_file():
            what = (f"specimen {sid}" if sid is not None else f"record {oid}" if oid is not None
                    else f"Data Entry row {rid}")
            out.append((path, what))
    return out


def nonstandard_names(life: Optional[Path] = None) -> List[Tuple[Path, Path]]:
    """(path, standard path) for specimen photos (in 'Specimen' folders) not yet named to the
    standard. THE list scripts/standardise_specimen_names.py renames."""
    life = Path(life or pf.life_root())
    out = []
    for dirpath, _dirs, files in os.walk(life):
        if Path(dirpath).name.casefold() != pf.SPECIMEN.casefold():
            continue
        for f in sorted(files):
            stem, ext = os.path.splitext(f)
            if ext.lower() not in IMAGE_EXTS:
                continue
            new = specimen_stem(stem)
            if new != stem:
                out.append((Path(dirpath) / f, Path(dirpath) / f"{new}{ext}"))
    return out


__all__ = ["empty_folders", "archive_empty_folders", "bench_waiting", "missing_files",
           "nonstandard_names", "IGNORED_FILES"]
