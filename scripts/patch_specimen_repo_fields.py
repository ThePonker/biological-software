"""patch_specimen_repo_fields.py -- the repository was discarding two columns.

    python scripts/patch_specimen_repo_fields.py

The root cause
--------------
`SpecimenRepository` filters every write through an `allowed_fields` whitelist,
and neither `taxonomic_sort_key` nor `superfamily` has ever been in it. Both
columns exist on the table; the repository simply never passed them through.

So a caller that sets them gets no error and no effect -- the fields are dropped
on the way to the INSERT. `AddSpecimenDialog` was patched an hour ago to compute
the sort key, and the very next specimen saved (Rutpela maculata, id 2622) still
came out NULL.

That is the actual root cause of the 244 invisible specimens, and it predates
March: any path writing through this repository has been losing the sort key
since the repository was written. Records that *do* have keys came in by another
route -- the Data Entry commit path, which writes through ObservationModel and
its own specimen insert.

Three whitelists to fix
-----------------------
    create()       allowed_fields
    update()       allowed_fields
    create_many()  the explicit field list

All three omit the same two columns. Missing one would leave a path that still
loses them, which is how this survived unnoticed.

A note on the lesson
--------------------
The dialog patch was correct and did nothing. It compiled, its logic was
verified against 2,566 existing keys, and it had no effect at all because a
layer below it was silently discarding the result. Only writing a real specimen
and reading the row back showed it.

Safe to re-run. Backs up as specimen_repository.py.bak_fields.
"""
import os
import shutil
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(_ROOT, "Observatum", "src", "repositories",
                      "specimen_repository.py")
BACKUP = TARGET + ".bak_fields"

# create() and update() carry identical whitelists, so each needs its own
# surrounding context to anchor uniquely.
OLD_CREATE = """        allowed_fields = {
            'specimen_code', 'species_name', 'species_tvk', 'common_name',
            'order_name', 'family', 'subfamily', 'date_collected', 'grid_ref',
            'vice_county', 'vc_number', 'site_name', 'site_name_local', 'collector', 'determiner',
            'sex', 'preparation_type', 'storage_location', 'drawer_unit',
            'condition', 'label_data', 'notes', 'import_notes', 'observation_id'
        }
        
        for field in allowed_fields:
            if field in data:
                fields.append(field)"""

NEW_CREATE = """        # taxonomic_sort_key and superfamily were absent from this list, so
        # every caller that set them had them silently dropped. The Insect
        # Collection sidebar filters on the sort key, so those specimens became
        # invisible to it -- 244 of them before anyone noticed.
        allowed_fields = {
            'specimen_code', 'species_name', 'species_tvk', 'common_name',
            'order_name', 'family', 'subfamily', 'superfamily',
            'taxonomic_sort_key', 'taxon_group',
            'date_collected', 'grid_ref',
            'vice_county', 'vc_number', 'site_name', 'site_name_local', 'collector', 'determiner',
            'sex', 'preparation_type', 'storage_location', 'drawer_unit',
            'condition', 'label_data', 'notes', 'import_notes', 'observation_id'
        }
        
        for field in allowed_fields:
            if field in data:
                fields.append(field)"""

OLD_UPDATE = """        allowed_fields = {
            'specimen_code', 'species_name', 'species_tvk', 'common_name',
            'order_name', 'family', 'subfamily', 'date_collected', 'grid_ref',
            'vice_county', 'vc_number', 'site_name', 'site_name_local', 'collector', 'determiner',
            'sex', 'preparation_type', 'storage_location', 'drawer_unit',
            'condition', 'label_data', 'notes', 'import_notes', 'observation_id'
        }
        
        set_parts = []"""

NEW_UPDATE = """        # Same omission as create(): without these two, correcting a species
        # on an existing specimen would leave a sort key belonging to the old
        # determination, or none at all.
        allowed_fields = {
            'specimen_code', 'species_name', 'species_tvk', 'common_name',
            'order_name', 'family', 'subfamily', 'superfamily',
            'taxonomic_sort_key', 'taxon_group',
            'date_collected', 'grid_ref',
            'vice_county', 'vc_number', 'site_name', 'site_name_local', 'collector', 'determiner',
            'sex', 'preparation_type', 'storage_location', 'drawer_unit',
            'condition', 'label_data', 'notes', 'import_notes', 'observation_id'
        }
        
        set_parts = []"""

OLD_MANY = """        fields = [
            'specimen_code', 'species_name', 'species_tvk', 'common_name',
            'order_name', 'family', 'subfamily', 'date_collected', 'grid_ref',
            'vice_county', 'vc_number', 'site_name', 'site_name_local', 'collector', 'determiner',
            'sex', 'preparation_type', 'storage_location', 'drawer_unit',
            'condition', 'label_data', 'notes', 'import_notes', 'observation_id',
            'created_at', 'updated_at'
        ]"""

NEW_MANY = """        # The batch path had the same gap. Missing one of the three would
        # leave a route that still loses the columns, which is how this
        # survived unnoticed.
        fields = [
            'specimen_code', 'species_name', 'species_tvk', 'common_name',
            'order_name', 'family', 'subfamily', 'superfamily',
            'taxonomic_sort_key', 'taxon_group',
            'date_collected', 'grid_ref',
            'vice_county', 'vc_number', 'site_name', 'site_name_local', 'collector', 'determiner',
            'sex', 'preparation_type', 'storage_location', 'drawer_unit',
            'condition', 'label_data', 'notes', 'import_notes', 'observation_id',
            'created_at', 'updated_at'
        ]"""


def main():
    if not os.path.exists(TARGET):
        print(f"NOT FOUND: {TARGET}")
        return 1
    with open(TARGET, "r", encoding="utf-8") as f:
        text = f.read()

    print("")
    print("Patching specimen_repository.py -- two columns it never passed on")
    print("=" * 70)

    if "taxonomic_sort_key" in text:
        print("  = already patched -- nothing to do")
        return 0

    failed = 0
    for label, old, new in [("create() whitelist", OLD_CREATE, NEW_CREATE),
                            ("update() whitelist", OLD_UPDATE, NEW_UPDATE),
                            ("create_many() field list", OLD_MANY, NEW_MANY)]:
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
    try:
        import py_compile
        py_compile.compile(TARGET, doraise=True)
        print("  + compiles cleanly")
        # Every column the whitelist now permits must exist on the table.
        sys.path.insert(0, _ROOT)
        import sqlite3
        import paths
        c = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
        cols = {r[1] for r in c.execute("PRAGMA table_info(specimens)")}
        c.close()
        for col in ("taxonomic_sort_key", "superfamily", "taxon_group"):
            mark = "+" if col in cols else "x"
            print(f"  {mark} {col} exists on the specimens table")
            if col not in cols:
                failed += 1
        if failed:
            print("  x a permitted column does not exist -- restore the backup")
            return 1
    except Exception as e:  # noqa: BLE001
        print(f"  x FAILED: {type(e).__name__}: {e}")
        print(f"    restore: copy {os.path.basename(BACKUP)} specimen_repository.py")
        return 1

    print("")
    print("  NEXT -- this needs a REAL test, not a compile:")
    print("    1. Fix the specimen added a moment ago:")
    print("         python scripts/backfill_sort_keys.py --apply")
    print("    2. Add another specimen through the dialog.")
    print("    3. Check it came out with a key:")
    print("         python scripts/check_recent_specimens.py")
    print("")
    print("  The dialog patch was correct and had no effect, because this")
    print("  layer was discarding the result. Only a real save proves it.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
