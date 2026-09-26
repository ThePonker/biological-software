"""patch_priority_detail.py -- fix the priority-track collapse in build_codex_db.py

    python scripts/patch_priority_detail.py

What it fixes
-------------
build_codex_db.py collapses designations at line ~607 with:

    key = (track, detail or "")

All five priority jurisdictions map to status_detail=None, so they compete for a
single slot per species and four are discarded. 2,303 species-jurisdiction facts
are missing from status_summary as a result:

    UK BAP                       1,150 true ->   142 stored
    Scottish Biodiversity List   2,088 true -> 1,537 stored
    Env (Wales) Act S7             568 true ->    80 stored
    NERC S.41 England              943 true ->   687 stored
    NI Priority Species            482 true ->   482 stored  (won every collision)

status_summary's primary key is (tvk, status_track, status_detail), so putting
the jurisdiction in status_detail lets all five coexist. legal_protection was
already done this way; priority was not.

status_value is left unchanged, so nothing downstream breaks. CodexRepository
already holds status.priority as a list and appends to it -- no consumer change
is needed.

Safe to re-run: reports each line as already-patched rather than failing.
Backs up the file as build_codex_db.py.bak_fix1 before writing.
"""
import os
import shutil
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(_ROOT, "scripts", "build_codex_db.py")
BACKUP = TARGET + ".bak_fix1"

# (description, old_line, new_line) -- single-line anchors only, because
# multi-line replacements fail unpredictably on this codebase's mixed endings.
EDITS = [
    (
        "comment above the priority block",
        '    # PRIORITY LISTINGS -- jurisdiction goes in status_value (per design)',
        '    # PRIORITY LISTINGS -- jurisdiction in BOTH status_value and status_detail.\n'
        '    # status_detail is part of the primary key and part of the collapse key at\n'
        '    # the status_summary build; leaving it None made all five jurisdictions\n'
        '    # compete for one slot per species. See patch_priority_detail.py.',
    ),
    (
        "BAP-2007",
        '    "BAP-2007":                     ("priority", "UK BAP",                     None),',
        '    "BAP-2007":                     ("priority", "UK BAP",                     "UK BAP"),',
    ),
    (
        "England_NERC_S.41",
        '    "England_NERC_S.41":            ("priority", "NERC S.41 England",          None),',
        '    "England_NERC_S.41":            ("priority", "NERC S.41 England",          "NERC S.41 England"),',
    ),
    (
        "Env (Wales) Act S7",
        '    "Env (Wales) Act S7":           ("priority", "Env (Wales) Act S7",         None),',
        '    "Env (Wales) Act S7":           ("priority", "Env (Wales) Act S7",         "Env (Wales) Act S7"),',
    ),
    (
        "Scottish_Biodiversity_List",
        '    "Scottish_Biodiversity_List":   ("priority", "Scottish Biodiversity List", None),',
        '    "Scottish_Biodiversity_List":   ("priority", "Scottish Biodiversity List", "Scottish Biodiversity List"),',
    ),
    (
        "NI_Priority",
        '    "NI_Priority":                  ("priority", "NI Priority Species",        None),',
        '    "NI_Priority":                  ("priority", "NI Priority Species",        "NI Priority Species"),',
    ),
]


def main():
    if not os.path.exists(TARGET):
        print(f"NOT FOUND: {TARGET}")
        return 1

    with open(TARGET, "r", encoding="utf-8") as f:
        text = f.read()
    original = text

    print("")
    print("Patching build_codex_db.py -- priority track status_detail")
    print("=" * 70)

    applied = skipped = failed = 0
    for desc, old, new in EDITS:
        if new in text:
            print(f"  = {desc:38} already patched")
            skipped += 1
        elif old in text:
            if text.count(old) != 1:
                print(f"  x {desc:38} NOT UNIQUE ({text.count(old)} matches)")
                failed += 1
                continue
            text = text.replace(old, new)
            print(f"  + {desc:38} patched")
            applied += 1
        else:
            print(f"  x {desc:38} ANCHOR NOT FOUND")
            failed += 1

    print("")
    if failed:
        print(f"  {failed} edit(s) failed -- NOTHING WRITTEN.")
        print("  The file may already differ from the version this was written")
        print("  against. Inspect it before proceeding.")
        return 1

    if not applied:
        print("  Nothing to do -- already fully patched.")
        return 0

    if not os.path.exists(BACKUP):
        shutil.copy2(TARGET, BACKUP)
        print(f"  backup written: {os.path.basename(BACKUP)}")
    else:
        print(f"  backup already exists, left alone: {os.path.basename(BACKUP)}")

    # Write without a BOM -- see the PowerShell Encoding Rule.
    with open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    print(f"  {applied} edit(s) applied to build_codex_db.py")

    # Verify by re-importing the mapping.
    print("")
    print("  Verifying the mapping now carries details...")
    sys.path.insert(0, _ROOT)
    sys.path.insert(0, os.path.join(_ROOT, "scripts"))
    try:
        import importlib
        import build_codex_db
        importlib.reload(build_codex_db)
        bad = [a for a, (t, _v, d) in build_codex_db.DESIG_TO_TRACK.items()
               if t == "priority" and not d]
        if bad:
            print(f"  x still None for: {bad}")
            return 1
        for a, (t, v, d) in build_codex_db.DESIG_TO_TRACK.items():
            if t == "priority":
                print(f"      {a:30} detail={d}")
        print("  + all five priority mappings carry a status_detail")
    except Exception as e:  # noqa: BLE001
        print(f"  ! could not verify by import: {e}")
        print("    Check the file by eye before rebuilding.")
        return 1

    print("")
    print("  NEXT: back up codex.db, then")
    print("        python scripts/build_codex_db.py")
    print("        python scripts/seed_codex.py")
    print("        python scripts/check_priority_impact.py   (expect 0 missing)")
    print("")
    print(f"  To undo: copy {os.path.basename(BACKUP)} back over build_codex_db.py")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
