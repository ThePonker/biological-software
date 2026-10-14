"""link_specimen_photos.py -- photos B2: link each specimen photo to its specimen where the
match is certain: exactly ONE specimen of that species on that date (13 Oct 2026: 987).

    py -3.14 scripts\\link_specimen_photos.py              # dry run: report only
    py -3.14 scripts\\link_specimen_photos.py --apply      # backup, then link

Reads the photo library (names only -- no photo is opened; scripts/check_media_library.py's
scan and matching), UKSI and observatum.db read-only, then for every photo whose species and
date match exactly one specimen, writes a link (shared/photo_links.py, method 'specimen
match'). A photo with several candidate specimens, or none, is not linked (they are counted;
the CSV lists them). Links already there are left as they are, so it can be re-run.
Needs the table: scripts\\add_photo_links_table.py first.

--apply backs observatum.db up first (C:\\BiologicalSoftware_Backups\\reference\\
observatum_pre_link_specimen_photos_<time>.db). Close Observatum first.
Writes scripts\\_oneoff\\specimen_photo_links_<date>.csv (photo, outcome, specimen ids).
"""
import argparse
import csv
import datetime
import os
import sqlite3
import sys
from collections import Counter
from pathlib import Path

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_ROOT, os.path.join(_ROOT, "Observatum")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import paths  # noqa: E402
from scripts.add_photo_links_table import BACKUP_DIR  # noqa: E402
from shared import photo_links as pl  # noqa: E402

LINK, SEVERAL, NO_SPECIMEN, HAVE = "link", "several specimens", "no specimen", "already linked"


def plan(rows, existing):
    """[(photo path, outcome, specimen id or None, ids text)] for the specimen-matched photos."""
    out = []
    for r in rows:
        if r.get("specimen_count") in ("", None):
            continue
        p = pl.norm(r["rel_path"])
        ids = r.get("specimen_ids") or ""
        if r["specimen_count"] == 1:
            sid = int(ids.split(":", 1)[0])
            out.append((p, HAVE if (p, sid) in existing else LINK, sid, ids))
        else:
            out.append((p, SEVERAL if r["specimen_count"] > 1 else NO_SPECIMEN, None, ids))
    return out


def backup(db_path, backup_dir) -> str:
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    dest = os.path.join(backup_dir, f"observatum_pre_link_specimen_photos_{stamp}.db")
    os.makedirs(backup_dir, exist_ok=True)
    if os.path.exists(dest):
        raise FileExistsError(f"backup already exists: {dest}")
    src, d = sqlite3.connect(str(db_path)), sqlite3.connect(dest)
    try:
        src.backup(d)
    finally:
        d.close()
        src.close()
    return dest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--root", default=str(paths.MEDIA_ROOT))
    ap.add_argument("--db", default=str(paths.OBSERVATUM_DB), help=argparse.SUPPRESS)
    ap.add_argument("--uksi", default=str(paths.UKSI_DB), help=argparse.SUPPRESS)
    ap.add_argument("--backup-dir", default=BACKUP_DIR, help=argparse.SUPPRESS)
    ap.add_argument("--csv", default=None)
    a = ap.parse_args(argv)
    from scripts.check_media_library import run_scan

    root = Path(a.root)
    print(f"\nPhotos -- link specimen photos\n  library: {root}\n  observatum.db: {a.db}")
    if not root.is_dir():
        print("  library not found (give it with --root). Nothing has been changed.")
        return 1
    ro = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    try:
        if not pl.has_table(ro):
            print("  the photo_links table is not there yet: run "
                  "scripts\\add_photo_links_table.py --apply first. Nothing has been changed.")
            return 1
        existing = {(r[0], r[1]) for r in ro.execute(
            f"SELECT photo_path, specimen_id FROM {pl.TABLE} WHERE specimen_id IS NOT NULL")}
        before = ro.execute(f"SELECT COUNT(*) FROM {pl.TABLE}").fetchone()[0]
    finally:
        ro.close()
    _entries, rows = run_scan(root, a.uksi, a.db)
    todo = plan(rows, existing)
    c = Counter(o for _, o, _, _ in todo)
    print(f"  specimen photos with a species and a date: {len(todo):,}")
    for k in (LINK, HAVE, SEVERAL, NO_SPECIMEN):
        print(f"    {k:<20}{c.get(k, 0):>7,}")
    out = a.csv or os.path.join(_ROOT, "scripts", "_oneoff",
                                f"specimen_photo_links_{datetime.date.today():%Y%m%d}.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["photo", "outcome", "specimen_id", "candidates"])
        w.writerows(todo)
    print(f"  list written to {out}")
    if not a.apply:
        print("\nDRY RUN. Nothing has been changed. Run with --apply to write the links.")
        return 0
    links = [(p, sid) for p, o, sid, _ in todo if o == LINK]
    if not links:
        print("  nothing to link. Nothing has been changed.")
        return 0
    dest = backup(a.db, a.backup_dir)
    print(f"  backed up to {dest}")
    conn = sqlite3.connect(a.db)
    try:
        with conn:
            made = sum(pl.add_link(conn, p, specimen_id=sid, method=pl.SPECIMEN_MATCH)
                       for p, sid in links)
        after = conn.execute(f"SELECT COUNT(*) FROM {pl.TABLE}").fetchone()[0]
    finally:
        conn.close()
    ok = after == before + made == before + len(links)
    print(f"  links written: {made:,}; table rows {before:,} -> {after:,}")
    print("  done." if ok else "  NOT as expected -- check the database.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
