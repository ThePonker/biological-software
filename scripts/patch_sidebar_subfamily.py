"""patch_sidebar_subfamily.py -- stop the sidebar losing 94 specimens.

    python scripts/patch_sidebar_subfamily.py

The fault
---------
`subfamily` is stored as NULL on some specimens and as '' on others, for the
same species. SQL groups those separately, so the tree query returns two rows
where it should return one:

    Amara eurynota   Carabidae   [(None, 2), ('', 1)]

and `build_tree` then does

    orders[order][superfamily][family][species] = (count, sort_key)

which is an assignment, not an accumulation -- so the second row overwrites the
first and one of the two counts is simply dropped.

**94 specimens across 81 species**, every one of the same shape. Coleoptera read
1,550 against a true 1,613; All Specimens 2,472 against 2,566.

This is long-standing and unrelated to the sex breakdown; the sex totals were
correct throughout, which is what made the discrepancy visible.

Two fixes, both applied
-----------------------
1. **The query normalises subfamily** -- `NULLIF(TRIM(COALESCE(...,'')),'')` so
   NULL and '' collapse to one group. That stops the split at source.

2. **build_tree accumulates rather than assigns.** Even with the query fixed,
   a dict assignment silently discards data whenever two rows share a key. `+=`
   is correct regardless of what the query does, and the tree should not depend
   on the query being perfect.

The underlying data inconsistency -- why some rows hold '' and others NULL --
is left alone. It is a separate question and the display no longer cares.

Safe to re-run. Backs up as .bak_subfam alongside each file.
"""
import os
import shutil
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIXIN = os.path.join(_ROOT, "Observatum", "src", "views", "collection",
                     "ic_sidebar_mixin.py")
SIDEBAR = os.path.join(_ROOT, "Observatum", "src", "views", "collection",
                       "taxonomic_sidebar.py")

M_OLD = '''            cursor = conn.execute("""
                SELECT s.order_name, u.superfamily, s.family, s.subfamily,
                       s.species_name, s.species_tvk,
                       s.taxonomic_sort_key, COUNT(*) as specimen_count
                FROM specimens s
                LEFT JOIN uksi.taxa u ON s.species_tvk = u.tvk
                WHERE s.taxonomic_sort_key IS NOT NULL
                GROUP BY s.order_name, u.superfamily, s.family, s.subfamily, s.species_name
                ORDER BY s.taxonomic_sort_key
            """)'''

M_NEW = '''            # subfamily is stored as NULL on some rows and '' on others for the
            # same species; grouping on the raw column splits them in two and
            # the tree then keeps only one. Normalise both to NULL so they
            # group together. 94 specimens were being lost to this.
            cursor = conn.execute("""
                SELECT s.order_name, u.superfamily, s.family,
                       NULLIF(TRIM(COALESCE(s.subfamily, '')), '') AS subfamily,
                       s.species_name, s.species_tvk,
                       s.taxonomic_sort_key, COUNT(*) as specimen_count
                FROM specimens s
                LEFT JOIN uksi.taxa u ON s.species_tvk = u.tvk
                WHERE s.taxonomic_sort_key IS NOT NULL
                GROUP BY s.order_name, u.superfamily, s.family,
                         NULLIF(TRIM(COALESCE(s.subfamily, '')), ''),
                         s.species_name
                ORDER BY s.taxonomic_sort_key
            """)'''

S_OLD = """            if order not in orders:
                orders[order] = {}
            if superfamily not in orders[order]:
                orders[order][superfamily] = {}
            if family not in orders[order][superfamily]:
                orders[order][superfamily][family] = {}
            orders[order][superfamily][family][species] = (count, sort_key)"""

S_NEW = """            if order not in orders:
                orders[order] = {}
            if superfamily not in orders[order]:
                orders[order][superfamily] = {}
            if family not in orders[order][superfamily]:
                orders[order][superfamily][family] = {}
            # ACCUMULATE, do not assign. Two query rows can share a species --
            # they did for 81 species, through inconsistent subfamily storage --
            # and an assignment silently discards the first. The query has been
            # fixed too, but the tree should not depend on that being perfect.
            prev = orders[order][superfamily][family].get(species)
            if prev:
                orders[order][superfamily][family][species] = (
                    prev[0] + count, prev[1] or sort_key)
            else:
                orders[order][superfamily][family][species] = (count, sort_key)"""

# The order node collects species names across families; a name appearing in
# two families would be counted twice in the sex sum. Dedupe it.
S_OLD_ORDER = """            order_species = [s for fams in superfamilies.values()
                             for sd in fams.values() for s in sd]"""

S_NEW_ORDER = """            order_species = {s for fams in superfamilies.values()
                             for sd in fams.values() for s in sd}"""


def apply(path, edits, marker):
    name = os.path.basename(path)
    if not os.path.exists(path):
        print(f"  x NOT FOUND: {path}")
        return False
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    if marker in text:
        print(f"  = {name}: already patched")
        return True
    ok = True
    for label, old, new in edits:
        n = text.count(old)
        if n == 1:
            text = text.replace(old, new)
            print(f"  + {name}: {label}")
        else:
            print(f"  x {name}: {label}  ({n} matches, expected 1)")
            ok = False
    if not ok:
        print(f"    -> {name} NOT written")
        return False
    backup = path + ".bak_subfam"
    if not os.path.exists(backup):
        shutil.copy2(path, backup)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    return True


def main():
    print("")
    print("Patching -- sidebar was losing specimens to NULL vs '' subfamily")
    print("=" * 70)

    ok = apply(MIXIN, [("normalise subfamily in the query", M_OLD, M_NEW)],
               "NULLIF(TRIM(COALESCE(s.subfamily")
    ok &= apply(SIDEBAR,
                [("accumulate instead of assign", S_OLD, S_NEW),
                 ("dedupe species for the order sex sum",
                  S_OLD_ORDER, S_NEW_ORDER)],
                "ACCUMULATE, do not assign")

    print("")
    if not ok:
        print("  One or more files unchanged.")
        return 1

    print("  Checking, and computing what the tree should now show...")
    try:
        import py_compile
        py_compile.compile(MIXIN, doraise=True)
        py_compile.compile(SIDEBAR, doraise=True)
        sys.path.insert(0, _ROOT)
        import sqlite3
        import paths
        from shared.sex_summary import classify_sex, format_sex_summary

        c = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
        c.execute("ATTACH ? AS uksi", (str(paths.UKSI_DB),))
        rows = c.execute("""
            SELECT s.order_name, u.superfamily, s.family,
                   NULLIF(TRIM(COALESCE(s.subfamily,'')),''),
                   s.species_name, COUNT(*)
            FROM specimens s LEFT JOIN uksi.taxa u ON s.species_tvk = u.tvk
            WHERE s.taxonomic_sort_key IS NOT NULL
            GROUP BY s.order_name, u.superfamily, s.family,
                     NULLIF(TRIM(COALESCE(s.subfamily,'')),''), s.species_name
        """).fetchall()
        kept = {}
        for o, sf, fam, sub, sp, n in rows:
            kept[(o, sf, fam, sp)] = kept.get((o, sf, fam, sp), 0) + n
        total = c.execute("SELECT COUNT(1) FROM specimens "
                          "WHERE taxonomic_sort_key IS NOT NULL").fetchone()[0]
        print(f"  + compiles cleanly")
        print(f"  + tree will now total {sum(kept.values())} of {total} "
              f"(was 2,472)")

        per_order = {}
        for (o, sf, fam, sp), n in kept.items():
            per_order[o] = per_order.get(o, 0) + n
        sexes = {}
        for name, sex, n in c.execute(
                """SELECT species_name, sex, COUNT(*) FROM specimens
                   WHERE taxonomic_sort_key IS NOT NULL
                   GROUP BY species_name, sex"""):
            sexes[name] = sexes.get(name, (0, 0, 0))
            m, f_, o_ = sexes[name]
            k = classify_sex(sex)
            sexes[name] = (m + n, f_, o_) if k == "m" else \
                          (m, f_ + n, o_) if k == "f" else (m, f_, o_ + n)
        print("")
        print("  Expected order nodes:")
        for o in sorted(per_order, key=lambda x: -per_order[x])[:6]:
            names = {sp for (oo, _sf, _f, sp) in kept if oo == o}
            m = sum(sexes.get(nm, (0, 0, 0))[0] for nm in names)
            f_ = sum(sexes.get(nm, (0, 0, 0))[1] for nm in names)
            o_ = sum(sexes.get(nm, (0, 0, 0))[2] for nm in names)
            s = format_sex_summary(m, f_, o_)
            print(f"    {str(o)[:22]:22} ({per_order[o]:,}"
                  + (f": {s})" if s else ")"))
        c.close()
    except Exception as e:  # noqa: BLE001
        print(f"  x FAILED: {type(e).__name__}: {e}")
        print("    restore: copy *.bak_subfam back over each file")
        return 1

    print("")
    print("  NEXT: restart Observatum and reopen the sidebar.")
    print("  The order totals and the sex sums should now agree.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
