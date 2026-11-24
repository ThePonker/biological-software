"""Photo health check: is the photo side of the suite in order? READ ONLY (Wil's list 11 Nov 2026, item 9).

    py -3.14 scripts\\check_photo_health.py

Looks at the record <-> photo links in observatum.db (opened read-only) and at the photo library
folders. Files are listed, never opened, so OneDrive cloud-only photos are not downloaded.

  1. Links: how many, how they were made, what they point at.
  2. Links to a photo whose file is not there (moved or renamed by hand).
  3. Links to a record, specimen or Data Entry row that no longer exists.
  4. Links stored in a non-standard form (backslashes etc.), which the lookups would miss.
  5. One photo linked to more than one field record.
  6. Specimen photos (in 'Specimen' folders) that nothing links to.
  7. Photos waiting on the bench (Photos/_Bench) and what each is waiting for.
  8. Empty folders under Photos/Life.
  9. Specimen photos not yet named to the standard.
 10. Names still carrying a bracket number such as "(2)" (fault F94's 33 renames).
 11. Possible duplicate files: same folder, same size, same type (sizes only; never opened).

Writes one CSV with every item found (scripts\\_oneoff\\photo_health_<date_time>.csv) -- the only file
it writes. Ends with "READ ONLY. Nothing has been changed."
"""
from __future__ import annotations

import csv
import os
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (ROOT, os.path.join(ROOT, "Observatum")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import paths  # noqa: E402
from shared import photo_files as pf  # noqa: E402
from shared import photo_housekeeping as ph  # noqa: E402
from shared import photo_links as pl  # noqa: E402
from shared.photo_names import IMAGE_EXTS  # noqa: E402

BRACKET = re.compile(r"\(\d+\)\s*$")
Item = Tuple[str, str, str]          # (check, photo path, detail)


def link_summary(conn) -> Dict[str, Counter]:
    """Counts of links by method and by what they point at."""
    by_method, by_target = Counter(), Counter()
    st = pl.STAGING if pl.has_staging_column(conn) else "NULL"
    for method, sid, oid, rid in conn.execute(
            f"SELECT method, specimen_id, observation_id, {st} FROM {pl.TABLE}"):
        by_method[method or "(none)"] += 1
        by_target["specimen" if sid is not None else "record" if oid is not None
                  else "Data Entry row" if rid is not None else "nothing"] += 1
    return {"method": by_method, "target": by_target}


def unnormalised_links(conn) -> List[Item]:
    return [("non-standard link path", p, f"would be stored as {pl.norm(p)!r}")
            for (p,) in conn.execute(f"SELECT DISTINCT photo_path FROM {pl.TABLE}") if pl.norm(p) != p]


def shared_photos(conn) -> List[Item]:
    """Photos linked directly to more than one field record (a specimen link is not counted)."""
    out = []
    for p, n, ids in conn.execute(
            f"SELECT photo_path, COUNT(DISTINCT observation_id), GROUP_CONCAT(DISTINCT observation_id) "
            f"FROM {pl.TABLE} WHERE observation_id IS NOT NULL GROUP BY photo_path HAVING COUNT(DISTINCT observation_id) > 1"):
        out.append(("photo on several records", p, f"records {ids}"))
    return out


def walk_library(life: Path):
    """(path, size) for every image under Life. Directory listing only."""
    for dirpath, _dirs, files in os.walk(life):
        for f in files:
            if os.path.splitext(f)[1].lower() in IMAGE_EXTS:
                full = Path(dirpath) / f
                try:
                    yield full, full.stat().st_size
                except OSError:
                    yield full, -1


def unlinked_specimen_photos(conn, files) -> List[Item]:
    linked = {pl.norm(p).casefold() for (p,) in conn.execute(f"SELECT DISTINCT photo_path FROM {pl.TABLE}")}
    out = []
    for full, _size in files:
        if full.parent.name.casefold() == pf.SPECIMEN.casefold() and pf.rel(full).casefold() not in linked:
            out.append(("specimen photo not linked", pf.rel(full), "in a Specimen folder, linked to nothing"))
    return out


def bracket_names(files) -> List[Item]:
    return [("bracket number in name", pf.rel(full), "F94 rename not done for this file")
            for full, _s in files if BRACKET.search(full.stem)]


def possible_duplicates(files) -> List[Item]:
    groups = defaultdict(list)
    for full, size in files:
        if size > 0:
            groups[(str(full.parent).casefold(), size, full.suffix.lower())].append(full)
    out = []
    for g in groups.values():
        if len(g) > 1:
            names = sorted(f.name for f in g)
            for f in sorted(g):
                out.append(("possible duplicate", pf.rel(f),
                            f"same size as {', '.join(n for n in names if n != f.name)}"))
    return out


def run(conn: Optional[sqlite3.Connection], csv_path: Optional[Path] = None, out=print) -> Tuple[List[Item], dict]:
    """Every check. Returns (items, summary). Writes the CSV when csv_path is given."""
    items: List[Item] = []
    summary = {}
    life = Path(pf.life_root())
    out(f"Photo library: {pf.media_root()}")
    if not life.is_dir():
        out("  Photos\\Life was not found -- library checks skipped.")
    files = list(walk_library(life)) if life.is_dir() else []
    summary["library photos"] = len(files)
    out(f"  {len(files):,} photos under Photos\\Life")

    have_links = conn is not None and pl.has_table(conn)
    if not have_links:
        out("\nThe photo_links table was not found -- link checks skipped.")
    else:
        s = link_summary(conn)
        n = sum(s["method"].values())
        summary["links"] = n
        out(f"\n1. Links: {n:,}")
        out("   by how made:   " + ", ".join(f"{k} {v:,}" for k, v in s["method"].most_common()))
        out("   pointing at:   " + ", ".join(f"{k} {v:,}" for k, v in s["target"].most_common()))

    checks = []
    if have_links:
        checks += [("2. Linked photo file not there",                       # needs the library to judge
                    [("missing file", p, w) for p, w in ph.missing_files(conn)] if life.is_dir() else []),
                   ("3. Links to something deleted", [("dead link", p, w) for p, w in ph.dead_links(conn)]),
                   ("4. Links in a non-standard form", unnormalised_links(conn)),
                   ("5. One photo on several field records", shared_photos(conn)),
                   ("6. Specimen photos linked to nothing", unlinked_specimen_photos(conn, files))]
    checks += [("7. Photos waiting on the bench", [("on the bench", p, w) for p, w in ph.bench_waiting(conn)]),
               ("8. Empty folders under Photos\\Life",
                [("empty folder", f, "no file inside") for f in (ph.empty_folders() if life.is_dir() else [])]),
               ("9. Specimen photos not named to the standard",
                [("non-standard name", pf.rel(a), f"standard: {Path(b).name}")
                 for a, b in (ph.nonstandard_names() if life.is_dir() else [])]),
               ("10. Bracket numbers left in names (F94)", bracket_names(files)),
               ("11. Possible duplicate files (same folder, size and type)", possible_duplicates(files))]
    for title, found in checks:
        summary[title] = len(found)
        out(f"\n{title}: {len(found):,}")
        for _c, p, d in found[:8]:
            out(f"   {p}  --  {d}")
        if len(found) > 8:
            out(f"   ... and {len(found) - 8:,} more (all in the CSV)")
        items += found

    if csv_path is not None:
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["check", "photo", "detail"])
            w.writerows(items)
        out(f"\nEvery item is listed in: {csv_path}")
    return items, summary


def main(argv=None) -> int:
    db = Path(paths.OBSERVATUM_DB)
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True) if db.is_file() else None
    try:
        csv_path = Path(paths.ROOT) / "scripts" / "_oneoff" / f"photo_health_{datetime.now():%Y%m%d_%H%M%S}.csv"
        items, _s = run(conn, csv_path)
    finally:
        if conn is not None:
            conn.close()
    print(f"\n{len(items):,} items in all. READ ONLY. Nothing has been changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
