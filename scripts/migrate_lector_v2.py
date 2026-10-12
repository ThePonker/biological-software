"""Update data/lector.db for saved searches (Lector stage A, 12 Oct 2026).

    py -3.14 scripts\\migrate_lector_v2.py            dry run: works on a copy in memory
    py -3.14 scripts\\migrate_lector_v2.py --apply    backup (data\\_backups\\lector_pre_v2_<time>.db),
                                                     then update in place (close Lector first)

Adds tables (saved searches, runs, review notes...) and columns; changes or removes no
stored row. Each species already fetched becomes a saved search with one run. Lector
itself offers the same update (it asks first), so running this is optional.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import paths  # noqa: E402,F401
from Lector import config, upgrade  # noqa: E402


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    db = config.LECTOR_DB
    st = upgrade.status(db)
    print(f"lector.db: {db}  (schema version {st['version']})")
    if not st["exists"]:
        print("No lector.db yet - Lector makes a new one when first used. Nothing has been changed.")
        return 0
    if not st["needs_update"]:
        print("Already up to date. Nothing has been changed.")
        return 0
    if "--apply" not in argv:
        print(upgrade.format_report(upgrade.dry_run(db)))
        print("\nDRY RUN - Nothing has been changed. Re-run with --apply (Lector closed).")
        return 0
    report = upgrade.apply(db, config.BACKUP_DIR)
    print(upgrade.format_report(report))
    print("\nDone: lector.db updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
