"""tidy_bench_links.py -- remove photo links that point at a Data Entry row, record or specimen
that no longer exists (bench photos take 2; records and specimens added 14 Oct 2026 evening).

    py -3.14 scripts\\tidy_bench_links.py              # dry run: lists them
    py -3.14 scripts\\tidy_bench_links.py --apply      # backup, then remove those links

Deleting a staging row before take 2, or a record or specimen some other way than the apps'
delete (which asks), left its photo links behind, pointing at something gone (ids are never
reused, so they cannot attach to anything else). Only those link rows are removed -- never a
photo file, never a link to something that exists. A photo left linked to nothing shows in
the cleaning report (Photos > Waiting in _Bench, or in its species folder). --apply backs
observatum.db up first; close Observatum and Data Entry first.
"""
import argparse
import os
import sqlite3
import sys
from datetime import datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_ROOT, os.path.join(_ROOT, "Observatum")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import paths  # noqa: E402
from shared import photo_links as pl  # noqa: E402

BACKUP_DIR = os.path.join(r"C:\BiologicalSoftware_Backups", "reference")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--db", default=str(paths.OBSERVATUM_DB), help=argparse.SUPPRESS)
    ap.add_argument("--backup-dir", default=BACKUP_DIR, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    print("\nPhoto links to deleted Data Entry rows, records and specimens")
    print("=" * 40)
    ro = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    try:
        orphans = [(i, p, f"Data Entry row {s}") for i, p, s in pl.orphan_staging_links(ro)]
        orphans += pl.orphan_record_links(ro)
        orphans = list({o[0]: o for o in orphans}.values())      # one line per link
        total = ro.execute(f"SELECT COUNT(*) FROM {pl.TABLE}").fetchone()[0] if pl.has_table(ro) else 0
    finally:
        ro.close()
    print(f"  photo links: {total:,}; pointing at something deleted: {len(orphans)}")
    for lid, path, what in orphans[:30]:
        print(f"    link {lid}: {what} (deleted)  {path}")
    if len(orphans) > 30:
        print(f"    ... and {len(orphans) - 30} more")
    if not a.apply:
        print("\nDRY RUN. Nothing has been changed. Run with --apply to remove these links.")
        return 0
    if not orphans:
        print("  nothing to do. Nothing has been changed.")
        return 0
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    os.makedirs(a.backup_dir, exist_ok=True)
    dest = os.path.join(a.backup_dir, f"observatum_pre_tidy_bench_links_{stamp}.db")
    src, d = sqlite3.connect(a.db), sqlite3.connect(dest)
    try:
        src.backup(d)
    finally:
        d.close()
        src.close()
    print(f"  backed up to {dest}")
    conn = sqlite3.connect(a.db)
    try:
        ids = [o[0] for o in orphans]
        with conn:
            for i in range(0, len(ids), 900):
                part = ids[i:i + 900]
                conn.execute(f"DELETE FROM {pl.TABLE} WHERE id IN ({','.join('?' * len(part))})", part)
        left = len(pl.orphan_staging_links(conn)) + len(pl.orphan_record_links(conn))
        total2 = conn.execute(f"SELECT COUNT(*) FROM {pl.TABLE}").fetchone()[0]
    finally:
        conn.close()
    ok = left == 0 and total2 == total - len(orphans)
    print(f"  removed {total - total2}; still pointing at something deleted: {left}; links now {total2:,}")
    print("  done." if ok else "  NOT as expected -- check the database.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
