"""backfill_sort_keys.py -- restore taxonomic_sort_key on specimens that lack one.

    python scripts/backfill_sort_keys.py            # report only, changes nothing
    python scripts/backfill_sort_keys.py --apply    # write, after a backup

The problem
-----------
244 of 2,568 specimens have no `taxonomic_sort_key`. The Insect Collection
sidebar filters on it:

    WHERE s.taxonomic_sort_key IS NOT NULL

so those 244 do not appear in the tree at all. Halictidae reads 48 where the
collection holds 55.

They cluster by month added -- 113 in March 2026, then 18 to 33 every month
since -- so something in the Add Specimen path stopped populating it in March
and has not populated it since. **All 35 sexed specimens are in this set**,
which is why the sidebar sex breakdown showed nothing: the specimens carrying a
sex are exactly the ones the tree cannot see.

This script fixes the existing records. The Add Specimen path still needs
fixing separately, or the gap simply reopens.

What it does
------------
Resolves each missing key from `uksi.taxa`, by TVK where the specimen has one
and by scientific name where it does not. Reports what it cannot resolve and
why, rather than silently leaving it.

Nothing is written without --apply, and --apply takes a backup through SQLite's
online backup API first (never shutil.copy2 on a WAL database).
"""
import os
import sys
from datetime import datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import sqlite3  # noqa: E402
import paths    # noqa: E402

APPLY = "--apply" in sys.argv


def main():
    print("")
    print("Taxonomic sort keys -- specimens with none")
    print("=" * 74)

    obs = sqlite3.connect(str(paths.OBSERVATUM_DB))
    obs.execute("ATTACH ? AS uksi", (str(paths.UKSI_DB),))

    missing = obs.execute(
        """SELECT id, species_tvk, species_name, family, order_name
           FROM specimens WHERE taxonomic_sort_key IS NULL""").fetchall()
    print(f"  specimens with no sort key: {len(missing)}")
    if not missing:
        print("  nothing to do.")
        return 0

    # ------------------------------------------------------------------
    # The formula, confirmed against 2,323 of 2,324 existing specimens:
    #
    #     taxonomic_sort_key = INSECT_ORDER_POSITION[order] * 1_000_000
    #                          + uksi.taxa.sort_code
    #
    # so the collection sorts by order first and taxonomically within it.
    # Orders absent from the table take 99, which sorts them last -- the same
    # fallback the sidebar already applies.
    #
    # UKSI holds sort_code (the integer) and sort_order (a long hex path
    # string). It is sort_code that is used; neither matches the stored value
    # directly, which is why this was measured rather than assumed.
    # ------------------------------------------------------------------
    try:
        from Observatum.src.utils.constants import INSECT_ORDER_POSITION
    except ImportError:
        print("  x could not import INSECT_ORDER_POSITION -- nothing written")
        return 1

    by_tvk = {}
    for tvk, code, sf in obs.execute(
            "SELECT tvk, sort_code, superfamily FROM uksi.taxa "
            "WHERE sort_code IS NOT NULL"):
        by_tvk[tvk] = (code, sf)

    by_name = {}
    for name, code, sf in obs.execute(
            "SELECT scientific_name, sort_code, superfamily FROM uksi.taxa "
            "WHERE sort_code IS NOT NULL AND rank = 'Species'"):
        by_name.setdefault(name, (code, sf))

    def make_key(order, code):
        return INSECT_ORDER_POSITION.get(order, 99) * 1000000 + int(code)

    resolved, unresolved = [], []
    via_tvk = via_name = no_order = 0
    for sid, tvk, name, family, order in missing:
        hit = by_tvk.get(tvk) if tvk else None
        if hit:
            via_tvk += 1
        elif name:
            hit = by_name.get(name)
            if hit:
                via_name += 1
        if hit:
            if order not in INSECT_ORDER_POSITION:
                no_order += 1
            resolved.append((sid, make_key(order, hit[0]), hit[1]))
        else:
            unresolved.append((sid, tvk, name, family, order))

    print(f"    resolved by TVK:   {via_tvk}")
    print(f"    resolved by name:  {via_name}")
    print(f"    unresolved:        {len(unresolved)}")
    if no_order:
        print(f"    (of the resolved, {no_order} have an order not in")
        print(f"     INSECT_ORDER_POSITION and take the 99 fallback)")

    if unresolved:
        print("")
        print("  UNRESOLVED -- these stay invisible to the sidebar:")
        no_tvk = sum(1 for u in unresolved if not u[1])
        print(f"    of which have no TVK at all: {no_tvk}")
        for sid, tvk, name, family, order in unresolved[:15]:
            print(f"    id {sid:>5}  {str(name)[:32]:32} "
                  f"{'(no TVK)' if not tvk else tvk}")
        if len(unresolved) > 15:
            print(f"    ... and {len(unresolved) - 15} more")

    # ------------------------------------------------------------------
    # How many of the sexed specimens this recovers
    # ------------------------------------------------------------------
    sexed_ids = {r[0] for r in obs.execute(
        """SELECT id FROM specimens
           WHERE taxonomic_sort_key IS NULL
             AND TRIM(COALESCE(sex,'')) != ''""")}
    recovered = sum(1 for sid, _, _ in resolved if sid in sexed_ids)
    print("")
    print(f"  sexed specimens this would restore to the tree: "
          f"{recovered} of {len(sexed_ids)}")

    if not APPLY:
        print("")
        print("  Nothing has been changed. Re-run with --apply to write.")
        print("")
        return 0

    # ------------------------------------------------------------------
    # Apply, after a proper backup
    # ------------------------------------------------------------------
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = os.path.join(r"C:\BiologicalSoftware_Backups", "reference",
                          f"observatum_pre_sortkey_{stamp}.db")
    os.makedirs(os.path.dirname(backup), exist_ok=True)
    print("")
    print(f"  backing up to {backup}")
    dest = sqlite3.connect(backup)
    obs.backup(dest)          # online backup API -- safe on a WAL database
    dest.close()

    # One existing specimen carries a key that matches neither its order nor
    # its own sort_code: Tillus elongatus (id 994), added 29 March 2026 --
    # the same month the keys started going missing, so the same fault caught
    # mid-failure rather than a separate oddity. Recompute it here.
    stray = obs.execute(
        """SELECT s.id, s.order_name, u.sort_code
           FROM specimens s JOIN uksi.taxa u ON s.species_tvk = u.tvk
           WHERE s.taxonomic_sort_key IS NOT NULL AND u.sort_code IS NOT NULL
             AND s.taxonomic_sort_key !=
                 (CASE WHEN s.order_name IS NULL THEN 99 ELSE -1 END) * 1000000
                 + u.sort_code""").fetchall()
    fixed_stray = 0
    for sid, order, code in stray:
        correct = make_key(order, code)
        cur = obs.execute("SELECT taxonomic_sort_key FROM specimens WHERE id=?",
                          (sid,)).fetchone()[0]
        if cur != correct:
            obs.execute("UPDATE specimens SET taxonomic_sort_key=?, updated_at=? "
                        "WHERE id=?", (correct, datetime.now().isoformat(), sid))
            fixed_stray += 1
    if fixed_stray:
        print(f"  corrected {fixed_stray} existing key(s) that did not match "
              f"their order and sort_code")

    n = 0
    for sid, key, sf in resolved:
        obs.execute(
            """UPDATE specimens SET taxonomic_sort_key = ?,
                      superfamily = COALESCE(NULLIF(TRIM(COALESCE(superfamily,'')), ''), ?),
                      updated_at = ?
               WHERE id = ?""",
            (key, sf, datetime.now().isoformat(), sid))
        n += 1
    obs.commit()
    print(f"  updated {n} specimen(s)")

    left = obs.execute(
        "SELECT COUNT(1) FROM specimens WHERE taxonomic_sort_key IS NULL"
    ).fetchone()[0]
    print(f"  remaining without a sort key: {left}")

    print("")
    print("  NEXT: Observatum -> Insect Collection -> sidebar.")
    print("  Halictidae should now read 55, with the sex breakdown.")
    print("")
    print("  STILL TO FIX: whatever stopped setting the key in March, or the")
    print("  gap reopens with the next specimen entered.")
    print("")
    obs.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
