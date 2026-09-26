"""patch_display_status.py -- stop labelling every priority listing "S41/BAP".

    python scripts/patch_display_status.py

The fault
---------
CodexRepository.SpeciesStatus.display_status renders any priority listing as:

    S41/BAP (2)

That label predates the 11-track scheme, when priority meant Section 41 or UK
BAP. The track now covers five jurisdictions:

    NERC S.41 England · Env (Wales) Act S7 · Scottish Biodiversity List
    NI Priority Species · UK BAP

Glory Park's four priority-tier bees are on the **Scottish Biodiversity List and
the NI Priority Species List. None is on Section 41.** The exported species
appendix uses `k.status_display or k.short_status`, so it currently prints
"S41/BAP (2)" against species with no English listing at all.

Nothing is invented -- the count is right -- but a client's ecologist reading
"S41/BAP" in an appendix would reasonably take it as Section 41. The appendix is
the artefact that leaves the office, so this is the label that matters most.

The fix
-------
Name what is actually held. `display_status` now renders the jurisdictions
themselves, abbreviated to keep the cell short:

    before:  NT, S41/BAP (2)
    after:   NT, SBL, NI Priority

Legal protection keeps its count form ("Legal (3)") -- the instruments are long
and the appendix has no room, and unlike the priority labels "Legal" is accurate
whatever the instrument.

`short_status` is left alone: it is documented as the shortest meaningful label
for dense table columns, and "Priority" there is vague but not misleading.
Naming jurisdictions in the Species tab is a separate change against
KeySpeciesEntry.priority, which now carries them.

Safe to re-run. Backs up as codex_repository.py.bak_fix1.
"""
import os
import shutil
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(_ROOT, "shared", "repositories", "codex_repository.py")
BACKUP = TARGET + ".bak_fix1"

OLD = """        # Priority
        if self.priority:
            parts.append(f"S41/BAP ({len(self.priority)})")"""

NEW = """        # Priority -- name the jurisdictions. The old "S41/BAP (n)" label
        # predated the 11-track scheme and read as Section 41 for species
        # listed only in Scotland, Wales or Northern Ireland.
        for entry in self.priority:
            parts.append(_priority_label(entry.value))"""

OLD_TAIL = '''        # Legal
        if self.legal_protection:
            parts.append(f"Legal ({len(self.legal_protection)})")
        return ", ".join(parts) if parts else ""'''

NEW_TAIL = '''        # Legal -- kept as a count. The instrument names are long, the
        # appendix cell is narrow, and "Legal" is accurate whichever it is.
        if self.legal_protection:
            parts.append(f"Legal ({len(self.legal_protection)})")
        return ", ".join(parts) if parts else ""'''

HELPER = '''

def _priority_label(value: str) -> str:
    """Short, honest label for a priority jurisdiction.

    Abbreviated to fit an appendix cell, but never collapsed to a different
    jurisdiction's name. Anything unrecognised is passed through unchanged
    rather than guessed at.
    """
    v = (value or "").lower()
    if "s.41" in v or "s41" in v or "section 41" in v:
        return "S41"
    if "wales" in v or "s7" in v:
        return "Wales S7"
    if "scottish" in v:
        return "SBL"
    if "northern ireland" in v or v.startswith("ni "):
        return "NI Priority"
    if "bap" in v:
        return "UK BAP"
    return value or ""

'''


def main():
    if not os.path.exists(TARGET):
        print(f"NOT FOUND: {TARGET}")
        print("  (the small file under Observatum/src/repositories is the shim)")
        return 1

    with open(TARGET, "r", encoding="utf-8") as f:
        text = f.read()

    print("")
    print("Patching codex_repository.py -- honest priority labels")
    print("=" * 70)

    if "_priority_label" in text:
        print("  = already patched -- nothing to do")
        return 0

    failed = 0
    if text.count(OLD) == 1:
        text = text.replace(OLD, NEW)
        print("  + display_status priority block  patched")
    else:
        print(f"  x display_status priority block  {text.count(OLD)} matches")
        failed += 1

    if text.count(OLD_TAIL) == 1:
        text = text.replace(OLD_TAIL, NEW_TAIL)
        print("  + legal comment                  patched")
    else:
        print(f"  x legal comment                  {text.count(OLD_TAIL)} matches")
        failed += 1

    # Insert the helper immediately before the SpeciesStatus dataclass, so it
    # is defined at module level before any method calls it at runtime.
    anchor = "@dataclass\nclass SpeciesStatus:"
    if text.count(anchor) == 1:
        text = text.replace(anchor, HELPER.lstrip("\n") + anchor)
        print("  + _priority_label helper         inserted")
    else:
        print(f"  x could not place helper         {text.count(anchor)} matches")
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
    print("  Checking the file still compiles...")
    try:
        import py_compile
        py_compile.compile(TARGET, doraise=True)
        print("  + compiles cleanly")
    except Exception as e:  # noqa: BLE001
        print(f"  x COMPILE FAILED: {e}")
        print(f"    restore: copy {os.path.basename(BACKUP)} codex_repository.py")
        return 1

    print("")
    print("  NEXT: python -m Examen -> Glory Park -> Export Appendix")
    print("  The four bees should read 'SBL' / 'NI Priority', not 'S41/BAP (n)'.")
    print("  Observatum also uses display_status -- worth a look at a species")
    print("  profile there too.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
