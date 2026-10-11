"""fix_irecord_format_sort_keys_20261010.py -- the observations whose taxonomic_sort_key holds
iRecord's text code instead of Observatum's number (note 36 decision 6, 10 Oct 2026).

    py -3.14 scripts\\_oneoff\\fix_irecord_format_sort_keys_20261010.py            # dry run
    py -3.14 scripts\\_oneoff\\fix_irecord_format_sort_keys_20261010.py --apply    # after a backup

Observatum's sort key is a whole number: order position x 1,000,000 + UKSI sort_code
(compute_taxonomic_sort_key, via shared.import_core.taxonomy_for_tvks -- the import wizards'
rule; imported here, not copied). A few iRecord-era observations hold iRecord's own taxonomic
sort string instead, e.g. '000204040N051J040C01000000000000000000000000000000' (50 characters,
digits and capitals), which sorts after every number.

Only those rows change: a text key made of digits and capitals, 20 characters or more, on a
record whose TVK is in UKSI. It is recomputed from the record's TVK. Any other odd key is
listed and left. A NULL key is not touched (backfill_taxon_groups.py fills those).

--apply backs observatum.db up with conn.backup() first, then writes in one transaction, each
UPDATE guarded so it only changes a key that still holds the old text. CSV of every row:
scripts\\_oneoff\\irecord_format_sort_keys_<date>.csv.
"""
import argparse
import os
import re
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (_ROOT, os.path.join(_ROOT, "Observatum")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import paths  # noqa: E402
from scripts import report_common as rc  # noqa: E402
from shared.import_core import taxonomy_for_tvks  # noqa: E402

_IRECORD_KEY = re.compile(r"[0-9A-Z]{20,}")
HEADER = ["id", "species_name", "species_tvk", "source", "irecord_id", "old_key", "new_key",
          "action"]


def is_our_key(v) -> bool:
    """Our sort key: a whole number (order position x 1,000,000 + UKSI sort code)."""
    if isinstance(v, int):
        return True
    return isinstance(v, str) and v.strip().isdigit() and len(v.strip()) <= 9


def is_irecord_key(v) -> bool:
    return (isinstance(v, str) and not is_our_key(v)
            and _IRECORD_KEY.fullmatch(v.strip()) is not None)


def _remapped(uksi_path, tvks) -> dict:
    """{old tvk: (new tvk, new name)} from UKSI's tvk_remap, for the message only."""
    if not tvks:
        return {}
    u = rc.connect_ro(uksi_path)
    try:
        if not u.execute("SELECT 1 FROM sqlite_master WHERE name = 'tvk_remap'").fetchone():
            return {}
        ph = ",".join("?" * len(tvks))
        return {o: (n, nm) for o, n, nm in u.execute(
            f"SELECT old_tvk, new_tvk, new_name FROM tvk_remap WHERE old_tvk IN ({ph})",
            list(tvks))}
    finally:
        u.close()


def plan(conn, uksi_path) -> dict:
    """{"rows": n, "null": n, "ours": n, "fix": [(id, name, tvk, source, irecord_id, old, new)],
        "left": [(id, name, tvk, source, irecord_id, old, reason)]}"""
    rows = conn.execute("SELECT id, species_name, species_tvk, source, irecord_id, "
                        "taxonomic_sort_key FROM observations ORDER BY id").fetchall()
    out = {"rows": len(rows), "null": 0, "ours": 0, "fix": [], "left": []}
    odd = []
    for r in rows:
        key = r[5]
        if rc.blank(key):
            out["null"] += 1
        elif is_our_key(key):
            out["ours"] += 1
        else:
            odd.append(r)
    tax = taxonomy_for_tvks({r[2] for r in odd if not rc.blank(r[2])}, uksi_path)
    remap = _remapped(uksi_path, {r[2] for r in odd if not rc.blank(r[2]) and r[2] not in tax})
    for r in odd:
        rid, name, tvk, source, irec, key = r
        if not is_irecord_key(key):
            out["left"].append((*r, "not iRecord's format"))
        elif rc.blank(tvk) or tvk not in tax:
            why = "no TVK" if rc.blank(tvk) else "TVK not in UKSI"
            if tvk in remap:
                why += (f"; UKSI moves it to {remap[tvk][1]} {remap[tvk][0]}: "
                        f"remap_record_tvks.py sets its TVK and sort key")
            out["left"].append((*r, why))
        else:
            out["fix"].append((*r, tax[tvk]["sort_key"]))
    return out


def apply(conn, found) -> int:
    n = 0
    with conn:
        for rid, _name, _tvk, _src, _irec, old, new in found["fix"]:
            n += conn.execute("UPDATE observations SET taxonomic_sort_key = ? "
                              "WHERE id = ? AND taxonomic_sort_key = ?", (new, rid, old)).rowcount
    return n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true", help="write (after a backup)")
    ap.add_argument("--csv", default=rc.default_csv("irecord_format_sort_keys"))
    ap.add_argument("--db", default=str(paths.OBSERVATUM_DB), help=argparse.SUPPRESS)
    ap.add_argument("--uksi", default=str(paths.UKSI_DB), help=argparse.SUPPRESS)
    ap.add_argument("--backup-dir", default=rc.BACKUP_DIR, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)

    print("")
    print("Observation sort keys in iRecord's text format -> Observatum's number")
    print("=" * 74)
    print(f"  observatum.db: {a.db}")
    ro = rc.connect_ro(a.db)
    try:
        found = plan(ro, a.uksi)
    finally:
        ro.close()
    print(f"  observations: {found['rows']:,}  (sort key blank {found['null']:,}; "
          f"our number {found['ours']:,}; other {len(found['fix']) + len(found['left']):,})")
    print(f"  iRecord-format keys to recompute from the TVK: {len(found['fix']):,}")
    for rid, name, tvk, _s, _i, old, new in found["fix"]:
        print(f"    id {rid:<6} {str(name or '')[:30]:<30} {tvk:<17} {old} -> {new}")
    if found["left"]:
        print(f"  odd keys left as they are: {len(found['left']):,}")
        for rid, name, tvk, _s, _i, old, why in found["left"]:
            print(f"    id {rid:<6} {str(name or '')[:30]:<30} {old!r}  ({why})")
    n = rc.write_csv(a.csv, HEADER,
                     [list(r[:6]) + [r[6], "recompute"] for r in found["fix"]]
                     + [list(r[:6]) + ["", f"left: {r[6]}"] for r in found["left"]])
    print(f"  CSV: {n:,} rows -> {a.csv}")

    if not a.apply:
        print("")
        print("DRY RUN. Nothing has been changed. Run with --apply to write.")
        return 0
    if not found["fix"]:
        print("  nothing to do. Nothing has been changed.")
        return 0
    print("")
    dest = rc.backup(a.db, "fix_irecord_sort_keys", a.backup_dir)
    print(f"  backed up to {dest}")
    conn = rc.sqlite3.connect(a.db)
    try:
        done = apply(conn, found)
        after = plan(conn, a.uksi)
    finally:
        conn.close()
    print(f"  sort keys rewritten: {done:,} of {len(found['fix']):,}")
    print(f"  after: iRecord-format keys left {len(after['fix']):,}; our number "
          f"{after['ours']:,} (was {found['ours']:,}); blank {after['null']:,}")
    print("  done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
