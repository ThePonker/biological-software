"""backfill_vice_county.py -- fill missing vice-counties from the grid reference.

    python scripts/backfill_vice_county.py            # dry run, changes nothing
    python scripts/backfill_vice_county.py --apply    # write, after a backup

The gap
-------
Measured 26 September 2026:

    Commercial   3,332 of 4,511 records with no vice-county   (74%)
    Personal       830 of 19,523
    Specimens        7 of 2,745

Every one of them has a grid reference. Data Entry derives the vice-county as a
record is typed; older routes -- Tabella workbooks, the import wizards -- did not.

Why it matters now
------------------
Examen derives the jurisdiction from the vice-county. With none to read it falls
back to England and says "(default)". For an English site that gives the right
answer by luck. **Machen (610 records, 2024) is in Caerphilly -- VC 35,
Monmouthshire, which is Wales** -- and has been assessed under English rules:
Section 41 counted as Key, the Environment (Wales) Act S7 list ignored.

How
---
With exactly the call Data Entry makes, so a backfilled record is
indistinguishable from one Data Entry filled:

    vc_service.get_vc_from_grid_ref(grid_ref)  ->  (vc_number, vc_name) | None

No fourth copy of the grid-reference arithmetic -- there are already three, and
one that disagreed would produce wrong vice-counties with nothing to question
them. Where the lookup fails, the record is left alone and reported, as Data
Entry does.

Only empty vice-counties are filled. Nothing already set is touched.
"""
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "Observatum"))   # 'src' lives here

import sqlite3  # noqa: E402
import paths    # noqa: E402

APPLY = "--apply" in sys.argv

# Report only -- the authoritative mapping is SiteAnalysisView._country_for_vc.
_ENGLAND = set(range(1, 35)) | set(range(36, 41)) | set(range(53, 71))
_WALES = {35} | set(range(41, 53))


def country(vc):
    try:
        vc = int(vc)
    except (TypeError, ValueError):
        return "?"
    if vc in _ENGLAND:
        return "England"
    if vc in _WALES:
        return "Wales"
    if vc == 71:
        return "Isle of Man"
    if 72 <= vc <= 112:
        return "Scotland"
    return "?"


def empty(v):
    return v is None or str(v).strip() == ""


def main():
    print("")
    print("Vice-county backfill from grid reference" + ("" if APPLY else "  --  DRY RUN"))
    print("=" * 76)

    try:
        from src.services.vc_lookup_service import get_vc_service
        try:
            svc = get_vc_service()
        except Exception:  # noqa: BLE001 -- same fallback as DataEntry/bootstrap
            svc = get_vc_service(str(paths.VC_LOOKUP_DB))
    except Exception as e:  # noqa: BLE001
        print(f"  x VC lookup service unavailable: {e}")
        return 1

    db = sqlite3.connect(str(paths.OBSERVATUM_DB))

    targets = {}   # table -> list of (id, grid_ref, extra)
    targets["observations"] = db.execute(
        """SELECT id, TRIM(grid_ref), record_type, project_name,
                  substr(date,1,4), irecord_id
           FROM observations
           WHERE COALESCE(TRIM(CAST(vc_number AS TEXT)),'') = ''
             AND COALESCE(TRIM(grid_ref),'') != ''""").fetchall()
    targets["specimens"] = db.execute(
        """SELECT id, TRIM(grid_ref), 'Specimen', NULL, NULL, NULL
           FROM specimens
           WHERE COALESCE(TRIM(CAST(vc_number AS TEXT)),'') = ''
             AND COALESCE(TRIM(grid_ref),'') != ''""").fetchall()

    # Resolve each distinct grid reference once.
    refs = {r[1] for rows in targets.values() for r in rows}
    cache, failed = {}, Counter()
    for gr in refs:
        try:
            res = svc.get_vc_from_grid_ref(gr)
        except Exception:  # noqa: BLE001 -- as Data Entry: a failure is a skip
            res = None
        cache[gr] = res
    print(f"  distinct grid references to resolve: {len(refs)}")
    print(f"  resolved: {sum(1 for v in cache.values() if v)}   "
          f"unresolved: {sum(1 for v in cache.values() if not v)}")

    plan = defaultdict(list)
    for table, rows in targets.items():
        for rid, gr, rtype, proj, year, irec in rows:
            res = cache.get(gr)
            if res:
                plan[table].append((rid, res[0], res[1]))
            else:
                failed[gr] += 1

    print("")
    for table, rows in targets.items():
        print(f"  {table:13} missing a VC: {len(rows):>6}   "
              f"fillable: {len(plan[table]):>6}")

    if failed:
        print("")
        print(f"  Grid references the lookup could not place ({len(failed)}):")
        for gr, n in failed.most_common(12):
            print(f"    {gr!r:22} x{n}")

    # Per commercial project: what it will become, and in which country.
    obs_res = {rid: (num, name) for rid, num, name in plan["observations"]}
    proj = defaultdict(Counter)
    for rid, gr, rtype, pname, year, irec in targets["observations"]:
        if rtype == "Commercial" and rid in obs_res:
            num, name = obs_res[rid]
            proj[(pname, year)][(num, name)] += 1
    print("")
    print("  COMMERCIAL PROJECTS -- vice-county each would receive")
    for (pname, year), vcs in sorted(proj.items(), key=lambda kv: str(kv[0])):
        parts = ", ".join(f"VC{n} {nm} ({country(n)}) x{c}"
                          for (n, nm), c in vcs.most_common())
        flag = "   <-- not England" if any(country(n) != "England"
                                          for (n, _), _c in vcs.items()) else ""
        print(f"    {str(pname)[:26]:26} {year}  {parts}{flag}")

    synced = sum(1 for rid, gr, rtype, p, y, irec in targets["observations"]
                 if irec and rid in obs_res)
    if synced:
        print("")
        print(f"  {synced} of the fillable observations are synced to iRecord.")
        print("  Vice-county is derived locally and iRecord derives its own, so")
        print("  filling it here changes nothing there.")

    if not APPLY:
        print("")
        print("  DRY RUN -- nothing has been changed. Re-run with --apply to write.")
        print("")
        return 0

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(r"C:\BiologicalSoftware_Backups", "reference",
                        f"observatum_pre_vcbackfill_{stamp}.db")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    b = sqlite3.connect(dest)
    db.backup(b)
    b.close()
    print("")
    print(f"  backup: {dest}")

    n = 0
    for table, rows in plan.items():
        for rid, num, name in rows:
            db.execute(f"""UPDATE {table} SET vc_number = ?, vice_county = ?
                           WHERE id = ?
                             AND COALESCE(TRIM(CAST(vc_number AS TEXT)),'') = ''""",
                       (num, name, rid))
            n += 1
    db.commit()
    print(f"  filled: {n}")

    for table in ("observations", "specimens"):
        left = db.execute(f"""SELECT COUNT(1) FROM {table}
            WHERE COALESCE(TRIM(CAST(vc_number AS TEXT)),'') = ''
              AND COALESCE(TRIM(grid_ref),'') != ''""").fetchone()[0]
        print(f"  {table}: still missing a VC (with a grid ref): {left}")
    db.close()
    print("")
    print("  NEXT: reopen Examen and select Machen. The header should read")
    print("  'assessed under Wales (from vice-county)'.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
