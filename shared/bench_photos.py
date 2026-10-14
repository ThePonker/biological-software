"""bench_photos -- Data Entry's bench photos wait in ONE holding folder until their row is
committed (bench photos take 2, agreed 14 Oct 2026). No Qt.

  Media/Photos/_Bench/   every photo attached to a Data Entry row that is not yet a record.

  attach            the photo is moved from the capture folder into _Bench, named for the row
                    ('Amara aenea male gen 5.vi.26'), and linked to the staging row.
  species changed   rename_for_species(): renamed inside _Bench. No species folder is made, so
                    a typing slip ('sde eff') leaves nothing behind in the library.
  commit            file_on_commit(): the photo moves to its species' Specimen folder -- only
                    when the row's species was picked from the list (it has a TVK) -- and its
                    link becomes the record's. A species without a TVK leaves the photo in
                    _Bench (linked to the record) and says so.
  row deleted /     release(): the photo goes back to the capture folder, or stays in _Bench;
  job discarded     either way its link to the deleted row is removed (the file never is).

Every move is os.rename (never a copy, never over another file) and logged in
paths.PHOTO_MOVES_DIR, as everywhere else (shared/photo_files.py).
"""
from __future__ import annotations

import datetime
import os
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from shared import photo_files as pf
from shared import photo_links as pl

BENCH_REL = "Photos/_Bench"
SEX_WORDS = {"male", "female", "males", "females", "mixed", "worker", "queen", "hermaphrodite"}


def bench_root() -> Path:
    return pf.media_root() / "Photos" / "_Bench"


def in_bench(stored_path: str) -> bool:
    return pl.norm(stored_path).casefold().startswith(BENCH_REL.casefold() + "/")


def bench_files() -> List[str]:
    """Every image waiting in _Bench, as stored paths (the cleaning report lists them)."""
    root = bench_root()
    if not root.is_dir():
        return []
    from shared.photo_names import IMAGE_EXTS
    return sorted(pf.rel(p) for p in root.iterdir()
                  if p.is_file() and p.suffix.lower() in IMAGE_EXTS)


def attach(conn, src: Path, staging_id: int, stem: str) -> str:
    """Move one capture-folder photo into _Bench as '<stem>.ext' (or '<stem> 2.ext'...) and link
    it to the staging row. Returns the stored path. Raises OSError with the photo left where it
    was if it cannot be moved or linked."""
    src = Path(src)
    dst = pf.free_path(bench_root(), stem, src.suffix)
    new_rel = pf.move_photo(conn, src, dst)
    try:
        pl.add_staging_link(conn, new_rel, staging_id)
        conn.commit()
    except Exception as e:
        conn.rollback()
        try:
            os.rename(dst, src)
        except OSError as e2:
            raise OSError(f"not linked ({e}) and could not be put back ({e2}); it is at {new_rel}")
        raise OSError(f"not linked ({e}); left in the capture folder")
    return new_rel


def _move_in_library(conn, src_rel: str, dst: Path, log) -> str:
    return pf.move_photo(conn, pf.absolute(src_rel), dst, log)


def rename_for_species(conn, staging_id: int, old_species: str, new_species: str
                       ) -> pf.RedetResult:
    """A staging row's species changed: rename its photos inside _Bench. A photo outside _Bench
    (attached before 14 Oct take 2) is left where it is and reported."""
    res = pf.RedetResult()
    old, new = pf.folder_name(old_species), pf.folder_name(new_species)
    if not old or not new or old.casefold() == new.casefold():
        return res
    log = pf.new_log_path()
    for p in pl.photos_for_staging(conn, staging_id):
        if not in_bench(p):
            res.left.append((p, "not in _Bench"))
            continue
        name = pf._new_name(os.path.basename(p), old, new)
        if name is None:
            res.left.append((p, f"name does not start with {old}"))
            continue
        stem, ext = os.path.splitext(name)
        try:
            new_rel = _move_in_library(conn, p, pf.free_path(bench_root(), stem, ext), log)
            res.moved.append((p, new_rel))
        except OSError as e:
            res.left.append((p, f"could not rename: {e}"))
    return res


def _rebuilt(stem: str, old: tuple, new: tuple) -> Optional[str]:
    """The name a bench photo gets when its row's (species, sex, iso date) change from `old` to
    `new`: the view and any ' 2' number are kept. None when the name is not the one the row
    would have given it (renamed by hand): nothing is guessed."""
    from shared.photo_names import format_photo_date, specimen_photo_stem
    o_sp, o_sex, o_iso = old
    head = specimen_photo_stem(pf.folder_name(o_sp), o_sex, "", "")
    if not head or not (stem.casefold() == head.casefold() or stem.casefold().startswith(head.casefold() + " ")):
        return None
    words = stem[len(head):].split()
    num = words.pop() if words and words[-1].isdigit() else ""
    try:
        o_date = format_photo_date(o_iso) if o_iso else ""
    except ValueError:
        o_date = ""
    if o_date and words and words[-1] == o_date:
        words.pop()
    # only a name the row itself gave: at most one view word (the dialog's views are one word),
    # which is neither a sex nor a date, and the whole name exactly as the row would make it
    if len(words) > 1 or (words and (words[0].casefold() in SEX_WORDS or any(ch.isdigit() for ch in words[0]))):
        return None
    if stem != (specimen_photo_stem(pf.folder_name(o_sp), o_sex, " ".join(words), o_iso)
                + (f" {num}" if num else "")):
        return None
    n_sp, n_sex, n_iso = new
    out = specimen_photo_stem(pf.folder_name(n_sp), n_sex, " ".join(words), n_iso)
    return f"{out} {num}" if num else out


def rename_for_row(conn, staging_id: int, old: tuple, new: tuple) -> pf.RedetResult:
    """A staging row's species, sex or date changed (old / new: (species, sex, iso date or '')):
    rename its photos inside _Bench to match. A photo outside _Bench, or whose name is not the
    one the row gave it, is left and reported."""
    res = pf.RedetResult()
    if not pf.folder_name(new[0]) or tuple(old) == tuple(new):
        return res
    log = pf.new_log_path()
    for p in pl.photos_for_staging(conn, staging_id):
        if not in_bench(p):
            res.left.append((p, "not in _Bench"))
            continue
        stem, ext = os.path.splitext(os.path.basename(p))
        name = _rebuilt(stem, old, new)
        if name is None:
            res.left.append((p, "its name is not the one the row gave it"))
            continue
        if name == stem:
            continue
        try:
            if name.casefold() == stem.casefold():          # case only: via a free name
                tmp = _move_in_library(conn, p, pf.free_path(bench_root(), stem + " _", ext), log)
                try:
                    new_rel = _move_in_library(conn, tmp, bench_root() / f"{name}{ext}", log)
                except OSError as e:
                    res.left.append((tmp, f"could not rename: {e}"))
                    continue
            else:
                new_rel = _move_in_library(conn, p, pf.free_path(bench_root(), name, ext), log)
            res.moved.append((p, new_rel))
        except OSError as e:
            res.left.append((p, f"could not rename: {e}"))
    return res


def file_on_commit(conn, staging_id: int, row: dict, observation_id: int) -> Tuple[bool, List[str]]:
    """The row became record `observation_id`: its photo links become the record's FIRST
    (committed), then its _Bench photos go to the species' Specimen folder (only when the row
    has a TVK; a moved photo's link follows it). Returns (links safe, notes for the commit
    summary). links safe False = the links still point at the staging row: the caller must not
    drop them when it deletes the row. Never raises."""
    notes = []
    try:
        photos = pl.photos_for_staging(conn, staging_id)
        if not photos:
            return True, notes
        pl.promote_staging(conn, staging_id, observation_id)
        conn.commit()
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return False, [f"row {staging_id} -> record {observation_id}: photos not linked ({e}); "
                       "they are still on the Data Entry row"]
    try:
        species = (row.get("species_name") or "").strip()
        matched = bool((row.get("species_tvk") or "").strip())
        log = pf.new_log_path()
        for p in photos:
            if not in_bench(p):
                continue                              # already in the library: just link it
            if not matched:
                notes.append(f"{os.path.basename(p)}: {species or 'no species'} was not picked "
                             f"from the list, so it stays in {BENCH_REL}")
                continue
            stem, ext = os.path.splitext(os.path.basename(p))
            folder = pf.specimen_folder_for(species, row.get("family") or "", row.get("order_name") or "")
            try:
                _move_in_library(conn, p, pf.free_path(folder, stem, ext), log)
            except Exception as e:
                notes.append(f"{os.path.basename(p)}: not moved ({e}); it stays in {BENCH_REL}, "
                             f"linked to record {observation_id}")
    except Exception as e:
        notes.append(f"record {observation_id}: photos linked, but not filed ({e})")
    return True, notes


def detach(conn, staging_id: int, stored_path: str, to_folder: Path) -> Path:
    """Take one photo off a Data Entry row (a wrong photo or view): it goes back to the
    capture folder under its current name and its link to the row is removed. Only a photo in
    _Bench linked to this row. Returns its new path; raises with nothing changed if it cannot."""
    p = pl.norm(stored_path)
    if not in_bench(p) or p not in pl.photos_for_staging(conn, staging_id):
        raise ValueError(f"{os.path.basename(p)} is not one of this row's photos in {BENCH_REL}")
    src = pf.absolute(p)
    stem, ext = os.path.splitext(src.name)
    dst = pf.free_path(Path(to_folder), stem, ext)
    size = src.stat().st_size
    Path(to_folder).mkdir(parents=True, exist_ok=True)
    os.rename(src, dst)
    try:
        conn.execute(f"DELETE FROM {pl.TABLE} WHERE photo_path = ? AND {pl.STAGING} = ?", (p, staging_id))
        conn.commit()
    except Exception:
        conn.rollback()
        os.rename(dst, src)
        raise
    pf._log({"time": datetime.datetime.now().isoformat(timespec="seconds"),
             "source": p, "destination": str(dst), "size_bytes": size}, pf.new_log_path())
    pf.refresh()
    return dst


def count_for_rows(conn, staging_ids: Iterable[int]) -> int:
    return sum(pl.staging_counts(conn, staging_ids).values())


def release(conn, staging_ids: Iterable[int], to_folder: Optional[Path] = None) -> Tuple[int, List[str]]:
    """Rows about to be deleted: their _Bench photos go back to `to_folder` (the capture folder)
    or, with None, stay in _Bench; their links to these rows are removed. The photo files are
    never deleted. Returns (photos sent back, notes). Commits."""
    ids = [int(i) for i in staging_ids if i is not None]
    back, notes = 0, []
    if not ids or not pl.has_staging_column(conn):
        return back, notes
    log = pf.new_log_path()
    for sid in ids:
        for p in pl.photos_for_staging(conn, sid):
            if to_folder is None or not in_bench(p):
                continue
            src = pf.absolute(p)
            stem, ext = os.path.splitext(src.name)
            dst = pf.free_path(Path(to_folder), stem, ext)
            try:
                if not src.is_file():
                    raise FileNotFoundError(p)
                size = src.stat().st_size
                Path(to_folder).mkdir(parents=True, exist_ok=True)
                os.rename(src, dst)
                pf._log({"time": datetime.datetime.now().isoformat(timespec="seconds"),
                         "source": p, "destination": str(dst), "size_bytes": size}, log)
                back += 1
            except OSError as e:
                notes.append(f"{os.path.basename(p)}: not sent back ({e}); it stays in {BENCH_REL}")
    pl.drop_staging_links(conn, ids)
    conn.commit()
    if back:
        pf.refresh()
    return back, notes


def photos_by_row(conn, staging_ids: Iterable[int]) -> dict:
    """{staging row id: [its photos in _Bench]} -- read before the rows are deleted."""
    out = {}
    for sid in [int(i) for i in staging_ids if i is not None]:
        paths = [p for p in pl.photos_for_staging(conn, sid) if in_bench(p)]
        if paths:
            out[sid] = paths
    return out


def send_back(conn, by_row: dict, to_folder: Path) -> Tuple[int, List[str]]:
    """After the rows were deleted: move their _Bench photos (read with photos_by_row before)
    back to `to_folder`. Only for rows that are really gone, and only photos no longer linked
    to anything; the rest stay where they are. Returns (sent back, notes)."""
    back, notes = 0, []
    log = pf.new_log_path()
    for sid, paths in by_row.items():
        if conn.execute("SELECT 1 FROM entry_staging WHERE id = ?", (sid,)).fetchone():
            continue                                   # the row was not deleted: keep its photos
        for p in paths:
            src = pf.absolute(p)
            try:
                if pl.link_count(conn, p) or not src.is_file():
                    continue
                stem, ext = os.path.splitext(src.name)
                dst = pf.free_path(Path(to_folder), stem, ext)
                size = src.stat().st_size
                Path(to_folder).mkdir(parents=True, exist_ok=True)
                os.rename(src, dst)
                pf._log({"time": datetime.datetime.now().isoformat(timespec="seconds"),
                         "source": p, "destination": str(dst), "size_bytes": size}, log)
                back += 1
            except OSError as e:
                notes.append(f"{os.path.basename(p)}: not sent back ({e}); it stays in {BENCH_REL}")
    return back, notes


# --- records deleted in Observatum (14 Oct 2026) --------------------------------------------
def record_photos(conn, observation_ids: Iterable[int]) -> dict:
    """{observation id: [photos linked to the record itself]} -- read before a delete. Photos
    linked through a specimen stay with the specimen and are not listed."""
    out = {}
    if conn is None or not pl.has_table(conn):
        return out
    for oid in [int(i) for i in observation_ids if i is not None]:
        paths = [r[0] for r in conn.execute(
            f"SELECT DISTINCT photo_path FROM {pl.TABLE} WHERE observation_id = ? ORDER BY photo_path", (oid,))]
        if paths:
            out[oid] = paths
    return out


def release_records(conn, by_record: dict, to_bench: bool) -> Tuple[int, List[str]]:
    """After the records were deleted: remove their photo links (only for records really gone)
    and, with to_bench, move each photo that is now linked to nothing into _Bench. The files
    are never deleted. Returns (moved to _Bench, notes). Commits."""
    moved, notes = 0, []
    gone = [oid for oid in by_record
            if not conn.execute("SELECT 1 FROM observations WHERE id = ?", (oid,)).fetchone()]
    if not gone:
        return moved, notes
    for i in range(0, len(gone), 900):
        part = gone[i:i + 900]
        conn.execute(f"DELETE FROM {pl.TABLE} WHERE observation_id IN ({','.join('?' * len(part))})", part)
    conn.commit()
    if not to_bench:
        return moved, notes
    log = pf.new_log_path()
    for oid in gone:
        for p in by_record[oid]:
            try:
                if pl.link_count(conn, p) or in_bench(p) or not pf.absolute(p).is_file():
                    continue                      # still another record's, or already there
                stem, ext = os.path.splitext(os.path.basename(p))
                _move_in_library(conn, p, pf.free_path(bench_root(), stem, ext), log)
                moved += 1
            except OSError as e:
                notes.append(f"{os.path.basename(p)}: not moved ({e}); left where it is")
    return moved, notes


__all__ = ["detach", "record_photos", "release_records", "photos_by_row", "send_back", "BENCH_REL", "bench_root", "in_bench", "bench_files", "attach", "rename_for_species",
           "file_on_commit", "rename_for_row", "count_for_rows", "release"]
