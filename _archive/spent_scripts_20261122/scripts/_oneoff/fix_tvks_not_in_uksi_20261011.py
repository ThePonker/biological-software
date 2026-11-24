"""fix_tvks_not_in_uksi_20261011.py -- decision 4 (Round 9, 11 Oct 2026): move records whose
TVK is not in uksi.db onto the current UKSI taxon their name matches.

    py -3.14 scripts\\_oneoff\\fix_tvks_not_in_uksi_20261011.py            # dry run: report only
    py -3.14 scripts\\_oneoff\\fix_tvks_not_in_uksi_20261011.py --apply    # back up, then write

Which records
-------------
Exactly the ones scripts\\report_tvks_not_in_uksi.py lists as "exact" or "synonym" (its
find() is imported, so the two always agree): the stored name is a current UKSI name, or a
UKSI synonym of one. "No match" records are never touched; they are listed at the end for
Wil to settle by hand (in iRecord, or by a later decision).

Why not remap_record_tvks.py
----------------------------
That script only follows uksi.db's tvk_remap table (old UKSI key -> new); these keys are
NEWER than the July 2025 extract, so tvk_remap knows only one of them (Isoaeschna), and it
does not recompute taxon_group. So this is its own script.

What it changes (the F43 way -- scripts\\_oneoff\\fix_melanotus_tvk_20261011.py, whose
helpers are reused)
------------------------------------------------------------------------------------
    species_tvk, taxon_rank, kingdom, order_name, family     from UKSI for the new TVK
    phylum, class_name, superfamily, subfamily, genus         only where the record already
                                                              holds a value; a blank stays
                                                              blank (backfill_taxon_groups.py)
    taxon_group      recomputed by shared/taxon_groups.py (listed when it changes)
    taxonomic_sort_key  kept (the old TVK is not in UKSI, so there is no "old key" to replace)
    import_notes     a note is appended: what was corrected, from what, and why
    updated_at       now
species_name and common_name are not touched: a synonym match keeps the name as recorded
(e.g. "Isoaeschna isoceles" stays, on the Aeshna isoceles TVK).

--apply backs observatum.db up with SQLite's backup API into
C:\\BiologicalSoftware_Backups\\reference\\ first, then writes in one transaction, each UPDATE
guarded so it only touches a row still on its old TVK. Run it with the apps closed.
"""
import argparse
import importlib.util
import os
import sqlite3
import sys
from datetime import datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (_ROOT, os.path.join(_ROOT, "Observatum"), os.path.join(_ROOT, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import paths  # noqa: E402
from shared.db_open import connect_ro  # noqa: E402
from shared.taxon_groups import taxonomy_for_tvks  # noqa: E402
from scripts import report_common as rc  # noqa: E402
from scripts import report_tvks_not_in_uksi as rep  # noqa: E402


def _load_f43():
    """The F43 script's helpers (_uksi_row, _subfamily, _blank, FILL_ONLY, TAXA_FIELDS)."""
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fix_melanotus_tvk_20261011.py")
    spec = importlib.util.spec_from_file_location("fix_melanotus_tvk_20261011", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


F43 = _load_f43()
TODAY = datetime.now().strftime("%Y-%m-%d")
SHOW = ("species_tvk", "taxon_rank", "kingdom", "order_name", "family", "superfamily",
        "subfamily", "genus", "taxon_group")


def note(old_tvk, m) -> str:
    how = "the same name" if m["match"] == "exact" else "a UKSI synonym of it"
    return (f"[TVK corrected {TODAY} (decision 4): was {old_tvk}, not in UKSI (July 2025); "
            f"now {m['tvk']} {m['name']} ({how})]")


def targets(uksi_path, tvks) -> dict:
    """{new tvk: {column: value}} -- the F43 target block, for each new TVK."""
    tvks = sorted(set(tvks))
    tax = taxonomy_for_tvks(tvks, uksi_path)
    out = {}
    u = connect_ro(uksi_path)
    try:
        for tvk in tvks:
            t, g = F43._uksi_row(u, tvk), tax.get(tvk)
            if not t or not g:
                continue
            new = {c: t.get(src) for c, src in F43.TAXA_FIELDS.items()}
            new["subfamily"] = F43._subfamily(u, tvk)
            new.update({"species_tvk": tvk, "taxon_rank": g["taxon_rank"],
                        "kingdom": g["kingdom"], "order_name": g["order_name"],
                        "family": g["family"], "superfamily": g["superfamily"],
                        "taxon_group": g["taxon_group"]})
            out[tvk] = new
    finally:
        u.close()
    return out


def plan(conn, uksi_path, found=None) -> dict:
    """{"items": [{'table', 'id', 'old_tvk', 'match', 'row', 'set'}], "no_match": [groups],
        "missing": [groups whose new TVK UKSI could not give]}"""
    found = found or rep.find(conn, uksi_path)
    remap = [g for g in found["groups"] if g["match"]["match"] in rep.REMAPPABLE]
    tgt = targets(uksi_path, [g["match"]["tvk"] for g in remap])
    out = {"items": [], "missing": [],
           "no_match": [g for g in found["groups"] if g["match"]["match"] not in rep.REMAPPABLE]}
    conn.row_factory = sqlite3.Row
    try:
        for g in remap:
            new = tgt.get(g["match"]["tvk"])
            if new is None:
                out["missing"].append(g)
                continue
            cols = {r[1] for r in conn.execute(f"PRAGMA table_info({g['table']})")}
            ph = ",".join("?" * len(g["ids"]))
            for r in conn.execute(f"SELECT * FROM {g['table']} WHERE id IN ({ph}) AND species_tvk = ? "
                                  "ORDER BY id", (*g["ids"], g["tvk"])):
                r = dict(r)
                want = {c: v for c, v in new.items()
                        if c in cols and not (c in F43.FILL_ONLY and F43._blank(r.get(c)))}
                change = {c: v for c, v in want.items() if r.get(c) != v}
                if "import_notes" in cols:
                    old = (r.get("import_notes") or "").strip()
                    change["import_notes"] = f"{old} {note(g['tvk'], g['match'])}".strip()
                if "updated_at" in cols:
                    change["updated_at"] = datetime.now().isoformat()
                out["items"].append({"table": g["table"], "id": r["id"], "old_tvk": g["tvk"],
                                     "match": g["match"], "row": r, "set": change})
    finally:
        conn.row_factory = None
    return out


def report(p) -> int:
    items = p["items"]
    by = {}
    for i in items:
        by.setdefault((i["table"], i["old_tvk"], i["row"].get("species_name") or ""), []).append(i)
    for (table, old, name), lst in by.items():
        m = lst[0]["match"]
        print("")
        print(f"  {table}: {len(lst)} x {name}   {old} -> {m['tvk']} {m['name']} ({m['match']})")
        for c in SHOW:
            afters = {str(i["set"][c]) for i in lst if c in i["set"]}
            if afters:
                befores = sorted({str(i["row"].get(c)) for i in lst if c in i["set"]})
                print(f"      {c:<20} {' / '.join(befores)[:34]:<34} -> {' / '.join(sorted(afters))}")
        print(f"      import_notes         + {note(old, m)}")
        print(f"      ids: {' '.join(str(i['id']) for i in lst)}")
    for g in p["missing"]:
        print(f"  ! {g['table']} {g['tvk']} {g['name']}: {g['match']['tvk']} not found in UKSI "
              "-- left alone")
    if p["no_match"]:
        print("")
        print("  NOT changed -- no exact or synonym match (for Wil):")
        for g in p["no_match"]:
            print(f"      {g['table']:<14} {g['tvk']}  {g['records']:>3} x {g['name'][:40]:<40} "
                  f"ids {' '.join(str(i) for i in g['ids'][:12])}{' ...' if len(g['ids']) > 12 else ''}")
    return len(items)


def apply(conn, p) -> dict:
    done = {}
    with conn:
        for i in p["items"]:
            cols = list(i["set"])
            done[i["table"]] = done.get(i["table"], 0) + conn.execute(
                f"UPDATE {i['table']} SET {', '.join(c + ' = ?' for c in cols)} "
                "WHERE id = ? AND species_tvk = ?",                    # still on its old TVK
                (*[i["set"][c] for c in cols], i["id"], i["old_tvk"])).rowcount
    return done


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Decision 4: records on TVKs not in UKSI")
    ap.add_argument("--apply", action="store_true", help="write (after a backup)")
    ap.add_argument("--db", default=str(paths.OBSERVATUM_DB), help=argparse.SUPPRESS)
    ap.add_argument("--uksi", default=str(paths.UKSI_DB), help=argparse.SUPPRESS)
    ap.add_argument("--backup-dir", default=rc.BACKUP_DIR, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)

    print("")
    print("Decision 4 -- records on TVKs not in uksi.db, onto the current UKSI taxon -- "
          + ("APPLY" if a.apply else "DRY RUN"))
    print("=" * 78)
    print(f"  observatum.db: {a.db}")
    print(f"  uksi.db:       {a.uksi}")
    ro = rc.connect_ro(a.db)
    try:
        p = plan(ro, a.uksi)
    finally:
        ro.close()
    total = report(p)
    print("")
    print(f"  in all: {total} record{'s' if total != 1 else ''} to move; "
          f"{sum(g['records'] for g in p['no_match'])} left for Wil (no match)")
    if not a.apply:
        print("")
        print("DRY RUN. Nothing has been changed. Run with --apply to write.")
        return 0
    if not total:
        print("  nothing to do. Nothing has been changed.")
        return 0
    dest = rc.backup(a.db, "fix_tvks_not_in_uksi", a.backup_dir)
    print(f"  backed up to {dest}")
    conn = sqlite3.connect(a.db)
    try:
        done = apply(conn, p)
        old = sorted({i["old_tvk"] for i in p["items"]})
        left = {t: conn.execute(f"SELECT COUNT(*) FROM {t} WHERE species_tvk IN "
                                f"({','.join('?' * len(old))}) AND id IN "
                                f"({','.join(str(i['id']) for i in p['items'] if i['table'] == t)})",
                                old).fetchone()[0] for t in done}
    finally:
        conn.close()
    for t, n in done.items():
        print(f"  {t}: updated {n}   still on their old TVK: {left[t]} (should be 0)")
    print("  done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
