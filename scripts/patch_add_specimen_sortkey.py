"""patch_add_specimen_sortkey.py -- stop new specimens vanishing from the sidebar.

    python scripts/patch_add_specimen_sortkey.py

The fault
---------
`AddSpecimenDialog.get_specimen_data()` copies four fields off the selected
species -- tvk, common_name, family, order_name -- and nothing else. It never
sets `taxonomic_sort_key`.

The Insect Collection sidebar filters on that column:

    WHERE s.taxonomic_sort_key IS NOT NULL

so **every specimen added through this dialog has been invisible to the tree**.
244 of them by 12 September 2026, accumulating at 16 to 33 a month since March.
Halictidae read 48 where the collection held 55.

The backfill (scripts/backfill_sort_keys.py) repaired the existing records.
This closes the source, or the gap simply reopens with the next specimen.

The key
-------
Measured against 2,323 of 2,324 existing specimens:

    taxonomic_sort_key = INSECT_ORDER_POSITION[order] * 1_000_000
                         + uksi.taxa.sort_code

so the collection sorts by order first and taxonomically within it. Orders
absent from that table take 99, which sorts them last.

Note UKSI holds both `sort_code` (the integer) and `sort_order` (a long hex path
string). It is `sort_code`; neither matches the stored value directly, which is
why this was measured rather than assumed.

Also set: `superfamily`, which the sidebar groups on and which the dialog was
likewise not recording.

Why the lookup is here
----------------------
`SpeciesSearch` is a pure widget -- it emits whatever its search service hands
it, so whether the dict carries a sort code depends on a service this dialog
does not own. One TVK, one query, once per specimen saved: negligible, and it
cannot be broken by a change elsewhere.

Safe to re-run. Backs up as add_specimen_dialog.py.bak_sortkey.
"""
import os
import shutil
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(_ROOT, "Observatum", "src", "views", "dialogs",
                      "add_specimen_dialog.py")
BACKUP = TARGET + ".bak_sortkey"

OLD = """        if self._selected_species:
            data['species_tvk'] = self._selected_species.get('tvk')
            data['common_name'] = self._selected_species.get('common_name')
            data['family'] = self._selected_species.get('family')
            data['order_name'] = self._selected_species.get('order')"""

NEW = """        if self._selected_species:
            data['species_tvk'] = self._selected_species.get('tvk')
            data['common_name'] = self._selected_species.get('common_name')
            data['family'] = self._selected_species.get('family')
            data['order_name'] = self._selected_species.get('order')
            self._add_taxonomy_keys(data)"""

# Inserted before get_specimen_data so it reads in call order.
HELPER = '''    def _add_taxonomy_keys(self, data: Dict[str, Any]):
        """Set taxonomic_sort_key and superfamily from UKSI.

        Without the sort key the specimen is invisible to the Insect Collection
        sidebar, which filters on `taxonomic_sort_key IS NOT NULL`. 244
        specimens were lost this way between March and September 2026 before
        anyone noticed -- the tree simply reported fewer than the collection
        held.

        The key is the order's position from INSECT_ORDER_POSITION, times a
        million, plus UKSI's sort_code: order first, taxonomic within it.
        Orders not in that table take 99 and sort last, which is what the
        sidebar does with them anyway.

        Fails soft. A specimen saved without a sort key is recoverable by
        scripts/backfill_sort_keys.py; one not saved at all is not.
        """
        tvk = data.get('species_tvk')
        if not tvk:
            return
        try:
            import sqlite3
            import paths
            from ...utils.constants import INSECT_ORDER_POSITION

            conn = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)
            row = conn.execute(
                "SELECT sort_code, superfamily FROM taxa WHERE tvk = ?", (tvk,)
            ).fetchone()
            conn.close()
            if not row or row[0] is None:
                return

            sort_code, superfamily = int(row[0]), row[1]
            order = (data.get('order_name') or '').strip()
            position = INSECT_ORDER_POSITION.get(order, 99)
            data['taxonomic_sort_key'] = position * 1000000 + sort_code
            if superfamily and not data.get('superfamily'):
                data['superfamily'] = superfamily
        except Exception as e:  # noqa: BLE001
            print(f"[AddSpecimen] taxonomy keys not set: {e}")

    def get_specimen_data(self) -> Dict[str, Any]:'''

OLD_SIG = """    def get_specimen_data(self) -> Dict[str, Any]:"""


def main():
    if not os.path.exists(TARGET):
        print(f"NOT FOUND: {TARGET}")
        return 1
    with open(TARGET, "r", encoding="utf-8") as f:
        text = f.read()

    print("")
    print("Patching add_specimen_dialog.py -- taxonomic sort key on save")
    print("=" * 70)

    if "_add_taxonomy_keys" in text:
        print("  = already patched -- nothing to do")
        return 0

    failed = 0
    for label, old, new in [("helper method", OLD_SIG, HELPER),
                            ("call it from get_specimen_data", OLD, NEW)]:
        n = text.count(old)
        if n == 1:
            text = text.replace(old, new)
            print(f"  + {label}")
        else:
            print(f"  x {label}  ({n} matches, expected 1)")
            failed += 1

    print("")
    if failed:
        print(f"  {failed} edit(s) failed -- NOTHING WRITTEN.")
        return 1

    shutil.copy2(TARGET, BACKUP)
    print(f"  backup written: {os.path.basename(BACKUP)}")
    with open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(text)

    print("")
    print("  Checking it compiles, and that the formula still reproduces")
    print("  the keys already in the database...")
    try:
        import py_compile
        py_compile.compile(TARGET, doraise=True)
        sys.path.insert(0, _ROOT)
        import sqlite3
        import paths
        from Observatum.src.utils.constants import INSECT_ORDER_POSITION

        c = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
        c.execute("ATTACH ? AS uksi", (str(paths.UKSI_DB),))
        rows = c.execute("""
            SELECT s.order_name, s.taxonomic_sort_key, u.sort_code
            FROM specimens s JOIN uksi.taxa u ON s.species_tvk = u.tvk
            WHERE s.taxonomic_sort_key IS NOT NULL
              AND u.sort_code IS NOT NULL""").fetchall()
        c.close()

        bad = 0
        for order, stored, code in rows:
            position = INSECT_ORDER_POSITION.get((order or "").strip(), 99)
            want = position * 1000000 + int(code)
            if want != stored:
                bad += 1
        print(f"  + compiles cleanly")
        print(f"  + formula reproduces {len(rows) - bad} of {len(rows)} "
              f"existing keys")
        if bad:
            print(f"    ({bad} differ -- expected 0 after the backfill; "
                  f"worth a look if this is not 0)")
    except Exception as e:  # noqa: BLE001
        print(f"  x FAILED: {type(e).__name__}: {e}")
        print(f"    restore: copy {os.path.basename(BACKUP)} add_specimen_dialog.py")
        return 1

    print("")
    print("  NEXT: add a specimen, then check it appears in the sidebar tree.")
    print("  Or re-run scripts/backfill_sort_keys.py -- it should report 2")
    print("  missing (the two longhorns with no TVK) and no more.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
