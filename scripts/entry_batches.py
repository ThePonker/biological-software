"""List or undo DataEntry commit batches.

    python scripts/entry_batches.py                     # list recent batches
    python scripts/entry_batches.py --undo "<stamp>"    # delete one batch

--undo backs observatum.db up first, and the batch's photos go back to Photos\\_Bench (their
links to the deleted records removed; no photo is ever deleted).
"""
import argparse, os, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

ap = argparse.ArgumentParser()
ap.add_argument("--undo", default=None, help="Exact batch stamp to delete.")
args = ap.parse_args()

c = sqlite3.connect(str(paths.OBSERVATUM_DB))

if args.undo:
    n = c.execute("SELECT COUNT(*) FROM observations WHERE import_notes = ?", (args.undo,)).fetchone()[0]
    if not n:
        print("No records match that batch stamp."); sys.exit(1)
    if input(f"Delete {n} record(s) from {args.undo!r}? [y/N] ").strip().lower() != "y":
        print("Cancelled."); sys.exit(0)
    # 14 Oct 2026: a backup first (as every delete), and the batch's photos let go: they go
    # back to Photos/_Bench (never deleted), their links to the deleted records removed
    from datetime import datetime
    from shared import bench_photos
    bdir = os.path.join(r"C:\BiologicalSoftware_Backups", "reference")
    os.makedirs(bdir, exist_ok=True)
    dest = os.path.join(bdir, f"observatum_pre_undo_batch_{datetime.now():%Y%m%d_%H%M%S_%f}.db")
    d = sqlite3.connect(dest)
    try:
        c.backup(d)
    finally:
        d.close()
    print("Backed up to", dest)
    ids = [r[0] for r in c.execute("SELECT id FROM observations WHERE import_notes = ?", (args.undo,))]
    photos = bench_photos.record_photos(c, ids)
    c.execute("DELETE FROM observations WHERE import_notes = ?", (args.undo,))
    c.commit()
    print("Deleted:", n)
    if photos:
        moved, notes = bench_photos.release_records(c, photos, True)
        print(f"Photos of these records moved back to {bench_photos.BENCH_REL}: {moved}")
        for note in notes:
            print("  !", note)
else:
    rows = list(c.execute(
        "SELECT import_notes, COUNT(*) n, MIN(id), MAX(id) FROM observations "
        "WHERE import_notes LIKE 'DataEntry batch%' GROUP BY 1 ORDER BY 1 DESC LIMIT 20"))
    if not rows:
        print("No DataEntry batches found.")
    for stamp, n, lo, hi in rows:
        print(f"  {stamp}   {n:>5} records   ids {lo}-{hi}")
