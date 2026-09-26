"""patch_bridge_synonyms.py -- add a synonym pass to the TVK bridge.

    python scripts/patch_bridge_synonyms.py

What it fixes
-------------
The bridge maps Pantheon's 2017 TVKs to current UKSI TVKs by two passes:

    1. direct -- the Pantheon TVK exists in uksi.taxa
    2. name   -- the Pantheon name matches uksi.taxa.scientific_name

3,068 of 14,229 Pantheon species matched neither and were dropped, taking with
them 2,629 SQS scores, 2,628 feeding guilds, 2,487 habitats and 826 SATs.

It never tried `uksi.synonyms` -- the table that exists precisely to map an old
name to a current TVK. 3,000 of the 3,068 resolve through it. The recoveries are
ordinary post-2017 taxonomy: Aedes -> Ochlerotatus, Achaearanea -> Parasteatoda,
Acronicta megacephala -> Subacronicta.

What this patch does, and deliberately does not do
--------------------------------------------------
It adds a THIRD pass that accepts a synonym resolution **only when no other
Pantheon species has already claimed that UKSI TVK**.

The remaining ~1,697 are collisions: UKSI has synonymised two Pantheon taxa into
one current species (Abraeus globosus -> A. perpusillus), and Pantheon holds
separate SQS and ecology for each. Because the SQS import ends in

    INSERT OR REPLACE INTO sqs_scores VALUES (?,?,?)

and sqs_scores is keyed on tvk alone, adding a colliding row would silently
overwrite an existing score in whatever order the rows happened to arrive. That
needs a stated merge rule and taxonomic judgement -- backlog J2, not this patch.

Collisions are counted and reported so the number stays visible.

Note: uksi.synonyms is NAME-based (synonym string -> current tvk), so this sits
in the name-resolution family, not the direct-TVK one. Match method is recorded
as 'name' because the schema's CHECK constraint allows only 'direct' or 'name'.

Safe to re-run. Backs up as build_codex_db.py.bak_fix3 before writing.
"""
import os
import shutil
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(_ROOT, "scripts", "build_codex_db.py")
BACKUP = TARGET + ".bak_fix3"

# --- Anchor 1: load the synonym index alongside the name index -------------
OLD_NAMEIDX = "        uksi_name_tvk = {r[0].lower(): r[1] for r in uc.fetchall()}"
NEW_NAMEIDX = (
    "        uksi_name_tvk = {r[0].lower(): r[1] for r in uc.fetchall()}\n"
    "\n"
    "        # Synonym index: Pantheon's names are 2017-era, so most bridge\n"
    "        # failures are species since renamed or moved genus. uksi.synonyms\n"
    "        # is name-based (synonym string -> current tvk).\n"
    "        uksi_syn_tvk = {}\n"
    "        try:\n"
    "            uc.execute(\"SELECT synonym, tvk FROM synonyms\")\n"
    "            for _syn, _tvk in uc.fetchall():\n"
    "                if _syn:\n"
    "                    uksi_syn_tvk.setdefault(_syn.lower(), _tvk)\n"
    "        except sqlite3.OperationalError:\n"
    "            print(\"  ! uksi.synonyms unavailable -- synonym pass skipped\")"
)

# --- Anchor 2: third pass, inserted before the bridge write ----------------
OLD_WRITE = \
    '        c.executemany("INSERT OR REPLACE INTO tvk_bridge VALUES (?,?,?,?)", bridge_rows)'
NEW_WRITE = (
    "        # Third pass -- synonym resolution for what the first two missed.\n"
    "        # Accept ONLY where no other Pantheon species has already claimed\n"
    "        # the target TVK. A collision means UKSI has merged two Pantheon\n"
    "        # taxa into one species, each with its own SQS and ecology; since\n"
    "        # sqs_scores is keyed on tvk alone, inserting one would silently\n"
    "        # overwrite the other. Those need a merge rule -- backlog J2.\n"
    "        syn_match = 0\n"
    "        syn_collision = 0\n"
    "        claimed = {r[1] for r in bridge_rows}\n"
    "        resolved_pan = {r[0] for r in bridge_rows}\n"
    "        for pan_tvk, pan_name in pan_species:\n"
    "            if pan_tvk in resolved_pan or not pan_name:\n"
    "                continue\n"
    "            new_tvk = uksi_syn_tvk.get(pan_name.lower())\n"
    "            if not new_tvk:\n"
    "                continue\n"
    "            if new_tvk in claimed:\n"
    "                syn_collision += 1\n"
    "                continue\n"
    "            bridge_rows.append((pan_tvk, new_tvk, pan_name, \"name\"))\n"
    "            claimed.add(new_tvk)\n"
    "            syn_match += 1\n"
    "            unmatched -= 1\n"
    "\n"
    '        c.executemany("INSERT OR REPLACE INTO tvk_bridge VALUES (?,?,?,?)", bridge_rows)'
)

# --- Anchor 3: report the new counts ---------------------------------------
OLD_REPORT = '        print(f"  Unmatched:        {unmatched:,}")'
NEW_REPORT = (
    '        print(f"  Synonym-resolved: {syn_match:,}")\n'
    '        print(f"  Unmatched:        {unmatched:,}")\n'
    '        if syn_collision:\n'
    '            print(f"  Synonym collisions (not bridged): {syn_collision:,}"\n'
    '                  f"  -- two Pantheon taxa merged into one species; see J2")'
)

EDITS = [
    ("synonym index load", OLD_NAMEIDX, NEW_NAMEIDX),
    ("third pass", OLD_WRITE, NEW_WRITE),
    ("counter reporting", OLD_REPORT, NEW_REPORT),
]


def main():
    if not os.path.exists(TARGET):
        print(f"NOT FOUND: {TARGET}")
        return 1

    with open(TARGET, "r", encoding="utf-8") as f:
        text = f.read()

    print("")
    print("Patching build_codex_db.py -- synonym pass on the TVK bridge")
    print("=" * 70)

    applied = failed = 0
    for desc, old, new in EDITS:
        if new in text:
            print(f"  = {desc:26} already patched")
        elif old in text:
            if text.count(old) != 1:
                print(f"  x {desc:26} NOT UNIQUE ({text.count(old)} matches)")
                failed += 1
                continue
            text = text.replace(old, new)
            print(f"  + {desc:26} patched")
            applied += 1
        else:
            print(f"  x {desc:26} ANCHOR NOT FOUND")
            failed += 1

    print("")
    if failed:
        print(f"  {failed} edit(s) failed -- NOTHING WRITTEN.")
        return 1
    if not applied:
        print("  Nothing to do -- already patched.")
        return 0

    if not os.path.exists(BACKUP):
        shutil.copy2(TARGET, BACKUP)
        print(f"  backup written: {os.path.basename(BACKUP)}")

    with open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    print(f"  {applied} edit(s) applied")

    print("")
    print("  Checking the file still compiles...")
    try:
        import py_compile
        py_compile.compile(TARGET, doraise=True)
        print("  + compiles cleanly")
    except Exception as e:  # noqa: BLE001
        print(f"  x COMPILE FAILED: {e}")
        print(f"    restore with: copy {os.path.basename(BACKUP)} build_codex_db.py")
        return 1

    print("")
    print("  BEFORE REBUILDING -- back up codex.db:")
    print("    (the reference copy from earlier is the pre-J1 state)")
    print("")
    print("  THEN:")
    print("        python scripts/build_codex_db.py")
    print("        python scripts/seed_codex.py")
    print("        python scripts/check_bridge_gap.py")
    print("")
    print("  Expect: bridge total 11,161 -> ~12,464; synonym collisions ~1,697")
    print("  reported and NOT bridged; SQS count to RISE (recovered species")
    print("  bringing their Pantheon scores in).")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
