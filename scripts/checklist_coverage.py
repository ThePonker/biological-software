"""How much of Wil's data gets a checklist position (shared/checklists). READ ONLY.

For each order, the distinct species in the Insect Collection (specimens) and in the
observations, and how many of them shared/checklist_order.py can place:

  placed        family, genus and species all in a checklist -> sorted to its listed place
  genus only    the genus is listed in that family but the species is not -> after the
                listed species of its genus (UKSI order among themselves); aggregates and
                slash pairs ("Leiopus linnei/nebulosus") always land here
  not placed    the genus is not listed in that family -> after the listed genera
  no list       the family is in no checklist -> the whole family stays in UKSI order

Specimens are matched on their stored name and family (as "Drawer in hand" does);
observations on UKSI's name and family for the TVK, falling back to the stored ones (as
batch maps do).
Genus-only, family-or-higher and hybrid names are left out (shared/record_kinds).

  py -3.14 scripts\\checklist_coverage.py              prints the table
  py -3.14 scripts\\checklist_coverage.py --csv FILE   also writes every species not placed
"""
from __future__ import annotations

import argparse
import csv
import os
import sqlite3
import sys
from collections import defaultdict
from typing import Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import paths  # noqa: E402
from shared import checklist_order  # noqa: E402
from shared.record_kinds import classify  # noqa: E402

ORDERS = ("Coleoptera", "Diptera", "Hymenoptera", "Hemiptera", "Lepidoptera", "Araneae")
SKIP_KINDS = {"genus", "family_plus", "hybrid"}


def _ro(p) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{p}?mode=ro", uri=True)


def species_rows(obs_conn, uksi_conn, table: str, use_uksi_family: bool) -> List[Dict]:
    """Distinct (order, family, binomial) for one table, species-level names only."""
    uksi_fam: Dict[str, tuple] = {}
    if use_uksi_family:
        uksi_fam = {t: (o, f, n) for t, o, f, n in uksi_conn.execute(
            'SELECT tvk, "order", family, scientific_name FROM taxa')}
    seen: Dict[tuple, Dict] = {}
    for name, tvk, order, fam, rank in obs_conn.execute(
            f"SELECT species_name, species_tvk, order_name, family, "
            f"{'taxon_rank' if table == 'observations' else 'NULL'} FROM {table}"):
        kinds = classify(name, rank) if name else {"genus"}
        if kinds & SKIP_KINDS:
            continue
        if use_uksi_family and tvk in uksi_fam and uksi_fam[tvk][1]:
            order, fam, name = uksi_fam[tvk]
        b = checklist_order._binomial(name)
        if len(b.split()) < 2:
            continue
        key = (order or "", (fam or "").lower(), b)
        if key not in seen:
            plain = [w for w in name.split() if not w.startswith("(")]
            seen[key] = {"order": order or "", "family": fam or "", "binomial": b,
                         "name": " ".join(plain[:2]), "agg": "agg" in kinds, "records": 0}
        seen[key]["records"] += 1
    return list(seen.values())


def place(rows: List[Dict], cl) -> None:
    for r in rows:
        fam, gen = r["family"].lower(), r["binomial"].split()[0]
        if fam not in cl.families:
            r["status"] = "no list"
        elif (fam, gen) not in cl.genus_pos:
            r["status"] = "not placed"
        elif r["binomial"] not in cl.species_pos:
            r["status"] = "genus only (aggregate)" if r.get("agg") else "genus only"
        else:
            r["status"] = "placed"


def table(rows: List[Dict]) -> Dict[str, Dict[str, int]]:
    out: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in rows:
        o = r["order"] if r["order"] in ORDERS else "(other orders)"
        out[o]["species"] += 1
        out[o][r["status"].split(" (")[0]] += 1
        if r["status"] == "genus only (aggregate)":
            out[o]["agg"] += 1
    return out


def report(folder: Optional[str] = None, obs_db=None, uksi_db=None, csv_path=None) -> Dict:
    cl = checklist_order.load(folder)
    obs, uksi = _ro(obs_db or paths.OBSERVATUM_DB), _ro(uksi_db or paths.UKSI_DB)
    result = {}
    try:
        for label, tbl, use_uksi in (("Specimens", "specimens", False),
                                     ("Observations", "observations", True)):
            rows = species_rows(obs, uksi, tbl, use_uksi)
            place(rows, cl)
            result[label] = rows
    finally:
        obs.close()
        uksi.close()
    for label, rows in result.items():
        print(f"\n{label}: distinct species per order")
        print(f"  {'order':16}{'species':>8}{'placed':>8}{'genus only':>12}{'(of them agg.)':>15}"
              f"{'not placed':>12}{'no list':>9}")
        t = table(rows)
        for o in list(ORDERS) + ["(other orders)"]:
            if o in t:
                c = t[o]
                print(f"  {o:16}{c['species']:8}{c['placed']:8}{c['genus only']:12}{c['agg']:15}"
                      f"{c['not placed']:12}{c['no list']:9}")
    if csv_path:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["source", "order", "family", "species", "status", "records"])
            for label, rows in result.items():
                for r in sorted(rows, key=lambda r: (r["order"], r["family"], r["binomial"])):
                    if r["status"] != "placed" and r["order"] in ORDERS:
                        w.writerow([label, r["order"], r["family"], r["name"], r["status"],
                                    r["records"]])
        print(f"\nNot-placed list written to {csv_path}")
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--checklists", default=None, help="folder of checklist CSVs")
    ap.add_argument("--csv", default=None)
    a = ap.parse_args(argv)
    report(a.checklists, csv_path=a.csv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
