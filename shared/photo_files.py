"""photo_files -- the photo library on disk: species folders, a species' photos, and moving a
record's photos when it is re-determined (photos B3/B5, agreed 13 Oct 2026). No Qt.

The library is paths.MEDIA_ROOT; species folders live under Photos/Life (after B1, specimen
photos sit in '<species>/Specimen/'). A species' folder is found by its name -- the UKSI name
without subgenus or '(=...)' notes -- anywhere in the Life tree (directory listings only, never
a file opened; built once and cached, refresh() after a move).

move_for_redet() is the re-det rule (B5): a record's linked photos follow its new name, unless
  - the photo is linked to another record too            -> left, reported
  - its file name does not start with the old species     -> left, reported (no guessing)
  - the new name is taken, or the file is missing          -> left, reported
Every move is os.rename (never copy-and-delete, never overwrite), written as it happens to
its own log in paths.PHOTO_MOVES_DIR (one file per re-det, the columns of
scripts/move_photos.py, so `move_photos.py --reverse <log>` puts them back), and the links
follow (shared.photo_links), committed one photo at a time.
"""
from __future__ import annotations

import csv
import datetime
import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from shared import photo_links as pl
from shared.photo_names import IMAGE_EXTS, standard_photo_stem

SPECIMEN = "Specimen"
LOG_FIELDS = ["time", "source", "destination", "size_bytes"]

_lock = threading.RLock()
_folders: Dict[str, Dict[str, List[Path]]] = {}      # life root -> {name casefold: [folders]}


def media_root() -> Path:
    import paths
    return Path(paths.MEDIA_ROOT)


def life_root() -> Path:
    return media_root() / "Photos" / "Life"


def folder_name(species: str) -> str:
    """'Drymus (Sylvadrymus) sylvaticus' -> 'Drymus sylvaticus'; drops '(=nigra auctt.)'."""
    n = re.sub(r"\s*\(=.*?\)", "", species or "")
    n = re.sub(r"\s+\([A-Z][a-z]+\)", "", n)
    n = n.replace("/", "-").replace("\\", "-")       # 'Bombus terrestris/lucorum agg.'
    return " ".join(n.split())


def rel(path: Path) -> str:
    return pl.norm(os.path.relpath(str(path), str(media_root())))


def absolute(rel_path: str) -> Path:
    return media_root() / pl.norm(rel_path)


def refresh() -> None:
    with _lock:
        _folders.clear()


def _index(root: Path) -> Dict[str, List[Path]]:
    key = str(root)
    with _lock:
        if key in _folders:
            return _folders[key]
        out: Dict[str, List[Path]] = {}
        stack = [str(root)]
        while stack:
            d = stack.pop()
            try:
                with os.scandir(d) as it:
                    for e in it:
                        try:
                            if e.is_dir(follow_symlinks=False):
                                stack.append(e.path)
                                out.setdefault(e.name.casefold(), []).append(Path(e.path))
                        except OSError:
                            continue
            except OSError:
                continue
        _folders[key] = out
        return out


def species_folders(species: str, root: Optional[Path] = None) -> List[Path]:
    """The folder(s) in Life named for this species (usually one). Species and below only: a
    one-word name (a genus, an order) has no species folder, so nothing is listed."""
    name = folder_name(species).casefold()
    if len(name.split()) < 2:
        return []
    return sorted(_index(root or life_root()).get(name, []))


def species_photos(species: str, root: Optional[Path] = None) -> List[str]:
    """Every image in the species' folder(s) and their subfolders, as stored paths, sorted."""
    found = []
    for folder in species_folders(species, root):
        for dirpath, _dirs, files in os.walk(folder):
            for f in files:
                if os.path.splitext(f)[1].lower() in IMAGE_EXTS:
                    found.append(rel(Path(dirpath) / f))
    return sorted(dict.fromkeys(found), key=str.casefold)


@dataclass
class RedetResult:
    moved: List[tuple] = field(default_factory=list)     # (old stored path, new stored path)
    left: List[tuple] = field(default_factory=list)      # (stored path, reason)

    def summary(self, new_name: str) -> str:
        bits = []
        if self.moved:
            bits.append(f"{len(self.moved)} photo{'s' if len(self.moved) != 1 else ''} moved to "
                        f"{folder_name(new_name)}")
        if self.left:
            bits.append(f"{len(self.left)} left where {'they are' if len(self.left) != 1 else 'it is'}: "
                        + "; ".join(f"{os.path.basename(p)} ({why})" for p, why in self.left))
        return ". ".join(bits)


def _new_name(fname: str, old: str, new: str) -> Optional[str]:
    stem, ext = os.path.splitext(fname)
    if not stem.casefold().startswith(old.casefold() + " ") and stem.casefold() != old.casefold():
        return None
    out, _ = standard_photo_stem(new + stem[len(old):])
    return out + ext


def _target_folder(src: Path, old: str, new: str, root: Path) -> Optional[Path]:
    """Where the photo goes: the same place under the new species' folder as it had under the
    old one ('Specimen', or none). The new species' existing folder if there is exactly one,
    else a new folder beside the old species' folder. None when the photo is not inside a
    folder named for the old species (nothing is guessed)."""
    species_dir, below = None, []
    for anc in src.parents:
        if anc.name.casefold() == old.casefold():
            species_dir = anc
            break
        below.insert(0, anc.name)
        if anc == root:
            break
    if species_dir is None:
        return None
    existing = species_folders(new, root)
    base = existing[0] if len(existing) == 1 else species_dir.parent / folder_name(new)
    return base.joinpath(*below) if below else base


def _log(row: dict, log_path) -> bool:
    """Append one move to the log. False (never an exception) if it could not be written."""
    try:
        new = not os.path.exists(log_path)
        os.makedirs(os.path.dirname(str(log_path)) or ".", exist_ok=True)
        with open(log_path, "a", encoding="utf-8-sig" if new else "utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
            if new:
                w.writeheader()
            w.writerow(row)
        return True
    except OSError:
        return False


def new_log_path() -> Path:
    import paths
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return Path(paths.PHOTO_MOVES_DIR) / f"redet_{stamp}.csv"


def move_for_redet(conn, photo_paths: Iterable[str], old_species: str, new_species: str,
                   specimen_ids: Iterable[int] = (), observation_ids: Iterable[int] = (),
                   log_path=None, staging_ids: Iterable[int] = ()) -> RedetResult:
    """Move and rename a re-determined record's photos (see the module note). `specimen_ids` /
    `observation_ids`: the record's own ids -- a link to anything else means 'shared'.
    Each moved photo's links are committed on `conn` as soon as it has moved."""
    log_path = log_path or new_log_path()
    res = RedetResult()
    old, new = folder_name(old_species), folder_name(new_species)
    if not old or not new or old.casefold() == new.casefold():
        return res
    mine_s, mine_o = {int(i) for i in specimen_ids}, {int(i) for i in observation_ids}
    mine_st = {int(i) for i in staging_ids}
    st_col = pl.STAGING if pl.has_staging_column(conn) else "NULL"
    root, lroot = media_root(), life_root()
    for p in dict.fromkeys(pl.norm(x) for x in photo_paths):
        others = [r for r in conn.execute(
            f"SELECT specimen_id, observation_id, {st_col} FROM {pl.TABLE} WHERE photo_path = ?", (p,))
            if not ((r[0] is not None and r[0] in mine_s) or (r[1] is not None and r[1] in mine_o)
                    or (r[2] is not None and r[2] in mine_st))]
        if others:
            res.left.append((p, "linked to another record too"))
            continue
        src = root / p
        if not src.is_file():
            res.left.append((p, "file not found"))
            continue
        name = _new_name(src.name, old, new)
        if name is None:
            res.left.append((p, f"name does not start with {old}"))
            continue
        folder = _target_folder(src, old, new, lroot)
        if folder is None:
            res.left.append((p, f"not inside a folder named {old}"))
            continue
        dst = folder / name
        if dst.exists():
            res.left.append((p, "new name already taken"))
            continue
        size = src.stat().st_size
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.rename(src, dst)
        except OSError as e:
            res.left.append((p, f"could not move: {e}"))
            continue
        new_rel = rel(dst)
        try:
            pl.repoint(conn, p, new_rel)
            conn.commit()
        except Exception as e:                      # links could not follow: put the file back
            try:
                conn.rollback()
                os.rename(dst, src)
                res.left.append((p, f"link not updated, moved back: {e}"))
            except Exception as e2:
                res.left.append((p, f"link not updated and NOT moved back ({e2}): now {new_rel}"))
            continue
        res.moved.append((p, new_rel))
        if not _log({"time": datetime.datetime.now().isoformat(timespec="seconds"),
                     "source": p, "destination": new_rel, "size_bytes": size}, log_path):
            res.left.append((new_rel, f"moved, but the log {log_path} could not be written"))
    if res.moved:
        refresh()
    return res


# --- bench photos and renames: one photo moved, never overwritten, logged, links follow ------
def specimen_folder_for(species: str, family: str = "", order: str = "",
                        root: Optional[Path] = None) -> Path:
    """Where a new specimen photo of this species goes (agreed 13 Oct 2026): the species'
    existing folder; else a new species folder in its family's folder; else a new family
    folder in its order's folder; else Life/_New species/<species>. Always '.../Specimen'."""
    root = root or life_root()
    name = folder_name(species)
    found = species_folders(name, root)
    if len(found) == 1:
        return found[0] / SPECIMEN
    idx = _index(root)
    fam = sorted(idx.get((family or "").casefold(), [])) if family else []
    if len(fam) == 1:
        return fam[0] / name / SPECIMEN
    orders = sorted(idx.get((order or "").casefold(), [])) if order else []
    if len(orders) == 1 and family:
        return orders[0] / family / name / SPECIMEN
    return root / "_New species" / name / SPECIMEN


def free_path(folder: Path, stem: str, ext: str) -> Path:
    """folder/stem.ext, or 'stem 2.ext', 'stem 3.ext'... -- the first not taken."""
    p, n = folder / f"{stem}{ext}", 2
    while p.exists():
        p, n = folder / f"{stem} {n}{ext}", n + 1
    return p


def move_photo(conn, src: Path, dst: Path, log_path=None) -> str:
    """Move one photo (os.rename: never a copy, never over another file), log it, and point
    any links at its new place (committed at once). Returns the new stored path; raises
    OSError / FileExistsError with nothing changed if it cannot."""
    src, dst = Path(src), Path(dst)
    if dst.exists():
        raise FileExistsError(f"{dst.name} is already there")
    if not src.is_file():
        raise FileNotFoundError(str(src))
    size = src.stat().st_size
    dst.parent.mkdir(parents=True, exist_ok=True)
    os.rename(src, dst)                         # across drives this raises: nothing moved
    new_rel = rel(dst)
    try:
        old_rel = rel(src)
    except ValueError:                          # from outside the library (the capture folder)
        old_rel = None
    if conn is not None and old_rel and not old_rel.startswith(".."):
        try:
            pl.repoint(conn, old_rel, new_rel)
            conn.commit()
        except Exception:
            conn.rollback()
            os.rename(dst, src)
            raise
    _log({"time": datetime.datetime.now().isoformat(timespec="seconds"),
          "source": str(src) if not old_rel or old_rel.startswith("..") else old_rel,
          "destination": new_rel, "size_bytes": size}, log_path or new_log_path())
    refresh()
    return new_rel


# --- the hook the record models call after a save (B5) -------------------------------------
_listeners: List = []          # callables(summary: str) -- the main window shows the note


def add_listener(fn) -> None:
    """fn(summary) is called after a re-det moved or left photos. A bound method is held
    weakly, so a window that has gone does not keep being called."""
    import inspect
    import weakref
    ref = weakref.WeakMethod(fn) if inspect.ismethod(fn) else (lambda f=fn: f)
    if all(r() is not fn for r in _listeners):
        _listeners.append(ref)


def follow_redet(db, kind: str, record_id: int, old_species: str, new_species: str,
                 notify: bool = True) -> Optional[RedetResult]:
    """Called when a record's species changed: a hand edit (Observation tab, Insect
    Collection) or an iRecord sync (notify=False: the sync shows one note for all).
    kind 'observation' or 'specimen'; db a DatabaseManager or a path. Never raises:
    a photo problem must not undo or block the record's save (it is reported instead)."""
    try:
        if folder_name(old_species).casefold() == folder_name(new_species).casefold():
            return None
        import sqlite3
        path = str(getattr(db, "main_db_path", None) or getattr(db, "_main_db_path", None) or db)
        conn = sqlite3.connect(path)
        try:
            if not pl.has_table(conn):
                return None
            if kind == "specimen":
                photos = pl.photos_for_specimen(conn, record_id)
                spec_ids, obs_ids = [record_id], []
            else:
                # the record's own photos, and its specimens' photos only when the specimen
                # carries the new name too (a specimen left on the old name keeps its photos)
                photos = [r[0] for r in conn.execute(
                    f"SELECT photo_path FROM {pl.TABLE} WHERE observation_id = ?", (record_id,))]
                spec_ids, waiting = [], []
                for sid, sname in conn.execute(
                        "SELECT id, species_name FROM specimens WHERE observation_id = ?", (record_id,)):
                    linked = pl.photos_for_specimen(conn, sid)
                    if folder_name(sname or "").casefold() == folder_name(new_species).casefold():
                        spec_ids.append(sid)
                        photos += linked
                    else:
                        waiting += linked
                obs_ids = [record_id]
            if not photos and not (kind != "specimen" and waiting):
                return None
            res = move_for_redet(conn, photos, old_species, new_species, spec_ids, obs_ids)
            if kind != "specimen":
                res.left += [(p, "its specimen still has the old name") for p in waiting]
            # photos still in _Bench (committed before the species had a TVK) are filed now
            from shared import bench_photos
            filed, _notes = bench_photos.file_record_photos(
                conn, obs_ids if kind != "specimen" else (), spec_ids or ([record_id] if kind == "specimen" else ()))
            res.moved += filed
            filed_from = {old for old, _new in filed}
            res.left = [(p, why) for p, why in res.left if p not in filed_from]
            res.left = [(p, "in _Bench: its species is not picked from the list yet" if
                         bench_photos.in_bench(p) and "not inside a folder" in why else why)
                        for p, why in res.left]
        finally:
            conn.close()
    except Exception as e:                          # report, never block the save
        res = RedetResult(left=[("", f"photos not moved: {e}")])
    note = res.summary(new_species)
    if note and notify:
        for ref in list(_listeners):
            fn = ref()
            if fn is None:
                _listeners.remove(ref)
                continue
            try:
                fn(note)
            except Exception:
                pass
    return res


def species_now(db, kind: str, record_id: int) -> str:
    """The species stored on a record now -- read before an edit is saved. '' on any problem."""
    try:
        import sqlite3
        path = str(getattr(db, "main_db_path", None) or db)
        table = "specimens" if kind == "specimen" else "observations"
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            row = conn.execute(f"SELECT species_name FROM {table} WHERE id = ?", (record_id,)).fetchone()
        finally:
            conn.close()
        return (row[0] if row else "") or ""
    except Exception:
        return ""


__all__ = ["add_listener", "follow_redet", "species_now", "new_log_path", "SPECIMEN",
           "specimen_folder_for", "free_path", "move_photo", "media_root", "life_root", "folder_name", "rel", "absolute", "refresh",
           "species_folders", "species_photos", "RedetResult", "move_for_redet"]
