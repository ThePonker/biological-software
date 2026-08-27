"""List or undo DataEntry commit batches.

    python scripts/entry_batches.py                     # list recent batches
    python scripts/entry_batches.py --undo "<stamp>"    # delete one batch
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
    c.execute("DELETE FROM observations WHERE import_notes = ?", (args.undo,))
    c.commit()
    print("Deleted:", n)
else:
    rows = list(c.execute(
        "SELECT import_notes, COUNT(*) n, MIN(id), MAX(id) FROM observations "
        "WHERE import_notes LIKE 'DataEntry batch%' GROUP BY 1 ORDER BY 1 DESC LIMIT 20"))
    if not rows:
        print("No DataEntry batches found.")
    for stamp, n, lo, hi in rows:
        print(f"  {stamp}   {n:>5} records   ids {lo}-{hi}")
