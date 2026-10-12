"""Untick names the lector.db update ticked although the UKSI checks hold them back.

    py -3.14 scripts\\fix_lector_name_choices.py            dry run: lists what would change
    py -3.14 scripts\\fix_lector_name_choices.py --apply    backup (data\\_backups\\
                                 lector_pre_fix_names_<time>.db), then change (Lector closed)

Why (Round 8, L5): when lector.db was updated for saved searches (12 Oct), each species
fetched with the command line became a saved search, and EVERY name the old fetch had
used was stored ticked - including names the 7 Oct `--synonyms` fetch searched although
they are held back now (Lamia textor: L. rosenmulleri, sartor, sutor, titillator). They
then showed ticked, as if you had chosen them. The old fetch's names are history, not
your choices: Lector's update no longer does this, and this script puts right a
database already updated.

What it changes, and only this: in a search the update made (marker: it holds the run
the update made, status 'migrated'), a name that run lists, still ticked, other than the
species' own name, with no held-back reason stored (the update stored none; a held-back
name you tick yourself in Edit search and save keeps its reason), which the UKSI checks
hold back today (the same checks a new search uses, with your data\\lector_synonyms.txt)
-> unticked, with the reason. A name you added
yourself, and every other search, are left alone. Pages are not touched: pages found
only by these names stay until the search is next run, which lists them under "No longer
matched" (your notes on them are kept).
"""
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import paths  # noqa: E402,F401
from Lector import config, upgrade  # noqa: E402
from Lector.synonyms import SynonymRules, plain  # noqa: E402


def _ro(db):
    return sqlite3.connect(f"file:{Path(db).as_posix()}?mode=ro", uri=True)


def find_changes(conn, check, rules=None):
    """[{search_id, search, names: [(name, reason)], pages_only_these, plus_lines}]."""
    conn.row_factory = sqlite3.Row
    out = []
    migrated = conn.execute(
        "SELECT s.search_id, s.name, s.target_name, s.target_tvk, r.settings"
        " FROM saved_searches s JOIN runs r ON r.search_id=s.search_id AND r.status='migrated'"
        " WHERE s.kind='species' ORDER BY s.search_id").fetchall()
    for m in migrated:
        if not m["target_tvk"] or check is None:
            continue
        old = {n.lower() for n in (json.loads(m["settings"] or "{}").get("names") or [])}
        held = {c["name"].lower(): c["held_back_reason"]
                for c in check(m["target_name"], m["target_tvk"]) if not c["included"]}
        names = []
        # held_back_reason IS NULL: the update stored none; a held-back name you ticked
        # yourself in Edit search keeps its reason, and is left alone
        for r in conn.execute("SELECT name, origin FROM search_names WHERE search_id=?"
                              " AND included=1 AND held_back_reason IS NULL ORDER BY position",
                              (m["search_id"],)):
            key = r["name"].lower()
            if (key in old and key in held and r["origin"] != "user_added"
                    and key != (m["target_name"] or "").lower()):
                names.append((r["name"], held[key]))
        if not names:
            continue
        gone = {n.lower() for n, _r in names}
        only = 0
        for (matched,) in conn.execute("SELECT matched_names FROM search_pages WHERE"
                                       " search_id=? AND state='current'", (m["search_id"],)):
            ms = {x.strip().lower() for x in (matched or "").split(",") if x.strip()}
            if ms and ms <= gone:
                only += 1
        plus = [f"+ {r.name}" + (f" @ {r.target}" if r.target else "")
                for r in (rules.rules if rules else [])
                if r.sign == "+" and r.source == "your list" and plain(r.name).lower() in gone
                and r.applies_to(m["target_name"], m["target_tvk"])]
        out.append({"search_id": m["search_id"], "search": m["name"], "names": names,
                    "pages_only_these": only, "plus_lines": plus})
    return out


def report(changes):
    lines = []
    if not changes:
        lines.append("No ticked names to change: every search the update made matches the "
                     "UKSI checks.")
    for c in changes:
        lines.append(f"{c['search']} (search {c['search_id']}): untick "
                     f"{len(c['names'])} name{'s' if len(c['names']) != 1 else ''} the update "
                     "ticked:")
        for name, reason in c["names"]:
            lines.append(f"  {name}  -  {reason}")
        lines.append(f"  Pages held that were found only by these names: "
                     f"{c['pages_only_these']} (kept now; the next run lists them under "
                     "\"No longer matched\").")
        for p in c["plus_lines"]:
            lines.append(f"  Note: your lector_synonyms.txt has \"{p}\"; it is left as it is.")
    return "\n".join(lines)


def backup(db, backup_dir):
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    dest = backup_dir / f"lector_pre_fix_names_{datetime.now():%Y%m%d_%H%M%S}.db"
    src, dst = _ro(db), sqlite3.connect(str(dest))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return dest


def apply(db, changes):
    conn = sqlite3.connect(str(db))
    try:
        with conn:
            for c in changes:
                for name, reason in c["names"]:
                    conn.execute("UPDATE search_names SET included=0, held_back_reason=?"
                                 " WHERE search_id=? AND name=? AND included=1"
                                 " AND held_back_reason IS NULL",
                                 (reason, c["search_id"], name))
    finally:
        conn.close()


def main(argv=None, db=None, uksi_db=None, synonym_file=None, backup_dir=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    db = Path(db or config.LECTOR_DB)
    uksi_db = uksi_db or config.UKSI_DB
    synonym_file = synonym_file or config.SYNONYM_FILE
    print(f"lector.db: {db}")
    if not db.exists():
        print("No lector.db. Nothing has been changed.")
        return 0
    check = upgrade.name_checker(uksi_db, synonym_file)
    if check is None:
        print(f"uksi.db not found ({uksi_db}): the names cannot be checked. "
              "Nothing has been changed.")
        return 1
    conn = _ro(db)
    try:
        if "search_names" not in {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}:
            print("This lector.db has no saved searches yet (Lector will offer its update; "
                  "the update now checks the names itself). Nothing has been changed.")
            return 0
        changes = find_changes(conn, check, SynonymRules.load(synonym_file))
    finally:
        conn.close()
    print(report(changes))
    if "--apply" not in argv:
        print("\nDRY RUN - Nothing has been changed. Re-run with --apply (Lector closed).")
        return 0
    if not changes:
        print("\nNothing has been changed.")
        return 0
    dest = backup(db, backup_dir or config.BACKUP_DIR)
    apply(db, changes)
    print(f"\nDone. Backup: {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
