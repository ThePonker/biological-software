"""patch_reset_profile_provenance.py -- keep the reset script in step with the DB.

    python scripts/patch_reset_profile_provenance.py

Why
---
On 6 September three columns were added to the live observatum.db:

    species_profiles.origin          'own' | 'review' | 'edited'
    species_profiles.source_review
    species_profiles.source_year

so an account seeded from a published review stays distinguishable from Wil's
own writing -- reports cite reviews by name, and the distinction has to survive.

scripts/reset_database.py was not updated. Nothing goes wrong until the day the
database is rebuilt, when the columns would silently vanish and the provenance
of every profile with them. That is the same shape as the `superfamily` fault
that the Schema Change Rule in 05_Rules.md exists because of: a column present
in the live database and absent from the definition that recreates it.

The audit
---------
Per the rule, this does NOT search the whole file for a column name -- that is
what once reported "ALL OK" while `superfamily` was missing from two of three
tables. It extracts each CREATE TABLE block on its own and checks within it.

It also checks the `specimens` block for the columns this session's work
depends on (taxonomic_sort_key, superfamily, taxon_group), and searches the rest
of the codebase for any second definition of species_profiles that would need
the same change.

Line-based insertion, since line endings in this codebase are mixed.
Safe to re-run. Backs up as reset_database.py.bak_prov.
"""
import os
import re
import shutil
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(_ROOT, "scripts", "reset_database.py")
BACKUP = TARGET + ".bak_prov"

NEW_COLS = [
    "    origin TEXT DEFAULT 'own',          -- own | review | edited",
    "    source_review TEXT,                 -- citation, where seeded from a review",
    "    source_year INTEGER,",
]

EXPECT = {
    "species_profiles": ["origin", "source_review", "source_year"],
    "specimens": ["taxonomic_sort_key", "superfamily", "taxon_group"],
}


def table_blocks(text):
    """{table_name: block_text} for every CREATE TABLE in the file."""
    blocks = {}
    for m in re.finditer(
            r"CREATE TABLE(?: IF NOT EXISTS)?\s+(\w+)\s*\((.*?)\n\s*\);",
            text, flags=re.S | re.I):
        blocks[m.group(1)] = m.group(2)
    return blocks


def audit(text):
    blocks = table_blocks(text)
    ok = True
    for table, cols in EXPECT.items():
        body = blocks.get(table)
        if body is None:
            print(f"    x {table}: no CREATE TABLE found")
            ok = False
            continue
        names = {ln.strip().split()[0] for ln in body.splitlines()
                 if ln.strip() and not ln.strip().startswith("--")}
        for col in cols:
            present = col in names
            print(f"    {'+' if present else 'x'} {table}.{col}")
            ok &= present
    return ok


def main():
    if not os.path.exists(TARGET):
        print(f"NOT FOUND: {TARGET}")
        return 1
    with open(TARGET, "r", encoding="utf-8", newline="") as f:
        raw = f.read()
    ending = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.split(ending)

    print("")
    print("Patching reset_database.py -- species_profiles provenance")
    print("=" * 70)

    blocks = table_blocks(raw)
    body = blocks.get("species_profiles", "")
    if "source_review" in body:
        print("  = species_profiles already carries the provenance columns")
    else:
        # Locate image_path inside the species_profiles block, insert after it.
        start = next((i for i, l in enumerate(lines)
                      if "CREATE TABLE" in l and "species_profiles" in l), -1)
        if start < 0:
            print("  x could not find CREATE TABLE species_profiles")
            print("  NOTHING WRITTEN.")
            return 1
        at = next((i for i in range(start, min(start + 40, len(lines)))
                   if lines[i].strip().startswith("image_path")), -1)
        if at < 0:
            print("  x could not find image_path inside species_profiles")
            print("  NOTHING WRITTEN.")
            return 1
        lines[at + 1:at + 1] = NEW_COLS
        shutil.copy2(TARGET, BACKUP)
        raw = ending.join(lines)
        with open(TARGET, "w", encoding="utf-8", newline="") as f:
            f.write(raw)
        print(f"  + three columns inserted after line {at + 1}")
        print(f"  backup written: {os.path.basename(BACKUP)}")

    print("")
    print("  Per-table audit -- each CREATE TABLE checked on its own:")
    ok = audit(raw)

    # Any other definition of species_profiles in the codebase?
    print("")
    print("  Other definitions of species_profiles in the codebase:")
    others = []
    skip = {".git", "_archive", "_backups", "data", "__pycache__", "_dump"}
    for dp, dirs, files in os.walk(_ROOT):
        dirs[:] = [d for d in dirs if d not in skip]
        for fn in files:
            if not fn.endswith(".py"):
                continue
            p = os.path.join(dp, fn)
            if os.path.abspath(p) in (os.path.abspath(TARGET),
                                      os.path.abspath(__file__)):
                continue
            try:
                t = open(p, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            if re.search(r"CREATE TABLE(?: IF NOT EXISTS)?\s+species_profiles",
                         t, flags=re.I):
                has = "source_review" in t
                others.append((os.path.relpath(p, _ROOT), has))
    if not others:
        print("    none -- reset_database.py is the only definition")
    for rel, has in others:
        print(f"    {'+' if has else 'x'} {rel}"
              + ("" if has else "   <-- also needs the three columns"))
        ok &= has

    try:
        import py_compile
        py_compile.compile(TARGET, doraise=True)
        print("")
        print("  + reset_database.py compiles cleanly")
    except Exception as e:  # noqa: BLE001
        print(f"  x COMPILE FAILED: {e}")
        print(f"    restore: copy {os.path.basename(BACKUP)} reset_database.py")
        return 1

    print("")
    if ok:
        print("  All definitions agree with the live database.")
    else:
        print("  One or more definitions still disagree -- see the x lines above.")
    print("")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
