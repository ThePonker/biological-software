"""fix_melanotus_tvk_20261011.py -- fault F43: "Melanotus" records on the fungus genus TVK.

    py -3.14 scripts\\_oneoff\\fix_melanotus_tvk_20261011.py            # dry run: report only
    py -3.14 scripts\\_oneoff\\fix_melanotus_tvk_20261011.py --apply    # back up, then write

Why
---
10 Kent Deadwood observations named "Melanotus" (click beetles, Elateridae) carry
BMSSYS0000020490, the Agaricales genus of the same name (a homonym across kingdoms). So Record
Detail shows Order Agaricales / Family Strophariaceae, Examen's taxonomic summary lists an
"Agaricales" group, and the Stats group curves count them as "fungus" (found 9 Oct by E8b;
seen again in Round 9 testing, 11 Oct).

What it changes
---------------
Rows in observations, recording_scheme, specimens and contributed_observations (where the
table has the columns) whose species_tvk is BMSSYS0000020490 and whose name's first word is
"Melanotus". Each such row moves to NHMSYS0000079906 (Melanotus, Elateridae) and its whole
taxonomy block is re-derived from UKSI for the new TVK, the way remap_record_tvks.py does it:
    species_tvk, taxon_rank, kingdom, phylum, class_name, order_name, superfamily, family,
    subfamily, genus                                   (whichever the table has)
    taxon_group      recomputed by shared/taxon_groups.py -- ALSO on rows that came from
                     iRecord (Wil, 11 Oct: the label is wrong only because of the bad TVK);
                     those rows are listed separately in the output
    superfamily, subfamily, taxonomic_sort_key, phylum, class_name, genus
                     only where the record already holds a value (one the fungus TVK gave
                     it); a BLANK is left blank -- filling blanks is backfill_taxon_groups.py's
                     job, which does it for every record alike (decisions 8 and 12). A sort
                     key is replaced only when it is the fungus TVK's key (import formula,
                     shared.import_core); any other key is kept and reported
    import_notes     a note is appended saying what was corrected and when
    updated_at       set to now
species_name and common_name are not touched (the name is already right).

Not changed: Examen's saproxylic_scores.csv also gives the beetle genus the fungus TVK
(harmless there -- genus entries match by name; listed in F43). codex.db is never touched.

--apply backs observatum.db up with SQLite's backup API into
C:\\BiologicalSoftware_Backups\\reference\\ first, then writes in one transaction, each
UPDATE guarded so it only touches a row still on the fungus TVK. Run it with the apps closed.
"""
import argparse
import os
import sqlite3
import sys
from datetime import datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (_ROOT, os.path.join(_ROOT, "Observatum")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import paths  # noqa: E402
from shared.taxon_groups import taxonomy_for_tvks  # noqa: E402

BAD_TVK = "BMSSYS0000020490"          # Melanotus, Fungi: Agaricales, Strophariaceae
GOOD_TVK = "NHMSYS0000079906"         # Melanotus, Animalia: Coleoptera, Elateridae
GENUS = "Melanotus"
TABLES = ("observations", "recording_scheme", "specimens", "contributed_observations")
BACKUP_DIR = os.path.join(r"C:\BiologicalSoftware_Backups", "reference")
TODAY = datetime.now().strftime("%Y-%m-%d")
NOTE = (f"[TVK corrected {TODAY} (F43): was {BAD_TVK}, the fungus genus Melanotus "
        f"(Agaricales); now {GOOD_TVK}, the click-beetle genus (Elateridae)]")

# columns written only where the record already holds a value (blanks are backfill's job)
FILL_ONLY = ("superfamily", "subfamily", "phylum", "class_name", "genus")

# record column -> UKSI taxa column (written where the record table has the column)
TAXA_FIELDS = {"kingdom": "kingdom", "phylum": "phylum", "class_name": "class",
               "order_name": "order", "family": "family", "genus": "genus"}


def _blank(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def _uksi_row(conn, tvk) -> dict:
    cols = [r[1] for r in conn.execute("PRAGMA table_info(taxa)")]
    row = conn.execute(f"SELECT {', '.join('[' + c + ']' for c in cols)} FROM taxa WHERE tvk = ?",
                       (tvk,)).fetchone()
    return dict(zip(cols, row)) if row else {}


def _subfamily(conn, tvk) -> str:
    """The taxon's subfamily from the UKSI parent chain ('' when it has none)."""
    seen, cur = set(), _uksi_row(conn, tvk).get("parent_tvk")
    while cur and cur not in seen:
        seen.add(cur)
        t = _uksi_row(conn, cur)
        if not t:
            break
        if (t.get("rank") or "").lower() == "subfamily":
            return t.get("scientific_name") or ""
        cur = t.get("parent_tvk")
    return ""


def target_values(uksi_path) -> dict:
    """{'new': {column: value}, 'bad_key': the fungus TVK's sort key} for the beetle genus."""
    from shared.db_open import connect_ro
    tax = taxonomy_for_tvks([GOOD_TVK, BAD_TVK], uksi_path)
    if GOOD_TVK not in tax:
        raise SystemExit(f"  x {GOOD_TVK} is not in {uksi_path}. Nothing has been changed.")
    u = connect_ro(uksi_path)
    try:
        t = _uksi_row(u, GOOD_TVK)
        if (t.get("scientific_name"), t.get("kingdom"), t.get("family")) != (GENUS, "Animalia",
                                                                              "Elateridae"):
            raise SystemExit(f"  x {GOOD_TVK} is not the click-beetle genus in this UKSI "
                             f"({t.get('scientific_name')}, {t.get('kingdom')}, {t.get('family')})."
                             " Nothing has been changed.")
        new = {c: t.get(src) for c, src in TAXA_FIELDS.items()}
        new["subfamily"] = _subfamily(u, GOOD_TVK)
    finally:
        u.close()
    g = tax[GOOD_TVK]
    new.update({"species_tvk": GOOD_TVK, "taxon_rank": g["taxon_rank"],
                "kingdom": g["kingdom"], "order_name": g["order_name"], "family": g["family"],
                "superfamily": g["superfamily"], "taxon_group": g["taxon_group"]})
    return {"new": new, "key": g.get("taxonomic_sort_key"),
            "bad_key": tax.get(BAD_TVK, {}).get("taxonomic_sort_key")}


def plan(conn, target) -> dict:
    """{table: [{'id', 'row' (before), 'set' (column -> new), 'irecord', 'key_kept'}]}"""
    out = {}
    for table in TABLES:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
        if "species_tvk" not in cols or "species_name" not in cols:
            continue
        conn.row_factory = sqlite3.Row
        rows = conn.execute(f"SELECT * FROM {table} WHERE species_tvk = ? ORDER BY id",
                            (BAD_TVK,)).fetchall()
        conn.row_factory = None
        items = []
        for r in rows:
            r = dict(r)
            if (r.get("species_name") or "").split(" ")[0] != GENUS:
                continue
            new = {c: v for c, v in target["new"].items()
                   if c in cols and not (c in FILL_ONLY and _blank(r.get(c)))}
            key_kept = None
            k = r.get("taxonomic_sort_key")
            if "taxonomic_sort_key" in cols and not _blank(k):
                if str(k) == str(target["bad_key"]) and target["key"] is not None:
                    new["taxonomic_sort_key"] = target["key"]
                else:
                    key_kept = k
            change = {c: v for c, v in new.items() if r.get(c) != v}
            if "import_notes" in cols:
                old = (r.get("import_notes") or "").strip()
                change["import_notes"] = f"{old} {NOTE}".strip()
            if "updated_at" in cols:
                change["updated_at"] = datetime.now().isoformat()
            irec = (not _blank(r.get("irecord_id"))) or (
                table == "observations" and not _blank(r.get("source")))
            items.append({"id": r["id"], "row": r, "set": change, "irecord": irec,
                          "key_kept": key_kept})
        out[table] = items
    return out


SHOW = ("species_tvk", "kingdom", "order_name", "family", "subfamily", "superfamily",
        "taxon_group", "taxon_rank", "taxonomic_sort_key")


def report(found) -> int:
    total = 0
    for table, items in found.items():
        print("")
        print(f"{table}: {len(items)} record{'s' if len(items) != 1 else ''} named {GENUS} "
              f"on {BAD_TVK}")
        if not items:
            continue
        total += len(items)
        first = items[0]
        print("  each record changes (before -> after):")
        for c in SHOW:
            if c in first["set"]:
                befores = sorted({str(i["row"].get(c)) for i in items})
                print(f"    {c:<20} {' / '.join(befores)[:40]:<40} -> {first['set'][c]!r}")
        print("    import_notes         + " + NOTE)
        print("  the records:")
        for i in items:
            r = i["row"]
            print(f"    id {r['id']:<6} {str(r.get('date') or ''):<10} "
                  f"{str(r.get('grid_ref') or ''):<13} {str(r.get('site_name') or '')[:22]:<22} "
                  f"{str(r.get('project_name') or '')[:14]:<14} det. {r.get('determiner') or ''}"
                  f"{'   [iRecord]' if i['irecord'] else ''}")
        kept = [i for i in items if i["key_kept"] is not None]
        for i in kept:
            print(f"  ! id {i['id']}: sort key {i['key_kept']!r} kept (not the fungus TVK's key)")
        irec = [i for i in items if i["irecord"]]
        print(f"  from iRecord (taxon group recomputed all the same): {len(irec)}")
        for i in irec:
            print(f"    id {i['id']}: iRecord ID {i['row'].get('irecord_id')}, taxon_group "
                  f"{i['row'].get('taxon_group')!r} -> {i['set'].get('taxon_group', i['row'].get('taxon_group'))!r}")
    return total


def backup(db_path, backup_dir=BACKUP_DIR) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    dest = os.path.join(backup_dir, f"observatum_pre_fix_melanotus_tvk_{stamp}.db")
    os.makedirs(backup_dir, exist_ok=True)
    if os.path.exists(dest):
        raise FileExistsError(f"backup already exists: {dest}")
    src = sqlite3.connect(str(db_path))
    d = sqlite3.connect(dest)
    try:
        src.backup(d)
    finally:
        d.close()
        src.close()
    return dest


def apply(conn, found) -> dict:
    done = {}
    with conn:
        for table, items in found.items():
            n = 0
            for i in items:
                cols = list(i["set"])
                n += conn.execute(
                    f"UPDATE {table} SET {', '.join(c + ' = ?' for c in cols)} "
                    f"WHERE id = ? AND species_tvk = ?",               # still on the fungus TVK
                    (*[i["set"][c] for c in cols], i["id"], BAD_TVK)).rowcount
            done[table] = n
    return done


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="F43: Melanotus records onto the click-beetle TVK")
    ap.add_argument("--apply", action="store_true", help="write (after a backup)")
    ap.add_argument("--db", default=str(paths.OBSERVATUM_DB), help=argparse.SUPPRESS)
    ap.add_argument("--uksi", default=str(paths.UKSI_DB), help=argparse.SUPPRESS)
    ap.add_argument("--backup-dir", default=BACKUP_DIR, help=argparse.SUPPRESS)
    a = ap.parse_args(argv)

    print("")
    print(f"F43 -- {GENUS} records from the fungus TVK to the click-beetle TVK -- "
          + ("APPLY" if a.apply else "DRY RUN"))
    print("=" * 78)
    print(f"  observatum.db: {a.db}")
    print(f"  uksi.db:       {a.uksi}")
    print(f"  {BAD_TVK} -> {GOOD_TVK}")
    target = target_values(a.uksi)
    ro = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    try:
        found = plan(ro, target)
    finally:
        ro.close()
    total = report(found)
    print("")
    print(f"  in all: {total} record{'s' if total != 1 else ''} to move")
    if not a.apply:
        print("")
        print("DRY RUN. Nothing has been changed. Run with --apply to write.")
        return 0
    if not total:
        print("  nothing to do. Nothing has been changed.")
        return 0
    dest = backup(a.db, a.backup_dir)
    print(f"  backed up to {dest}")
    conn = sqlite3.connect(a.db)
    try:
        done = apply(conn, found)
        left = {t: conn.execute(f"SELECT COUNT(*) FROM {t} WHERE species_tvk = ? AND "
                                f"species_name LIKE '{GENUS}%'", (BAD_TVK,)).fetchone()[0]
                for t in found}
    finally:
        conn.close()
    for t, n in done.items():
        print(f"  {t}: updated {n}   still on {BAD_TVK}: {left[t]} (should be 0)")
    print("  done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
