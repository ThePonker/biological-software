"""patch_key_species_tracks.py -- carry structured tracks on KeySpeciesEntry.

    python scripts/patch_key_species_tracks.py

Run this BEFORE patch_conservation_tab.py -- that patch reads the fields this
one adds.

The fault
---------
KeySpeciesEntry carries only display strings: status_display, short_status,
tier, sqs. The structured 11-track data is available in `cs` when the entry is
built and is then discarded.

So conservation_tab._parse_status has to reverse-engineer status codes out of
short_status. For a priority species short_status returns the literal string
"Priority", which matches no token, so it falls through to the tier fallback and
labels EVERY priority species "S41" -- regardless of which jurisdiction actually
listed it. Glory Park shows "Section 41: 4" without ever reading Section 41.

For an English site that happens to be the right citation. For a Scottish or
Welsh job it would be wrong.

The fix
-------
Add five fields to KeySpeciesEntry, populated from the SpeciesStatus that is
already in hand. All default to empty, so existing consumers (site_analysis_view
freeze, appendix export) are unaffected.

    rarity          str        NR / NS / Na / Nb / Notable
    threat          str        CR / EN / VU / NT ... (2001 IUCN)
    threat_legacy   str        RDB1 / RDB2 / RDB3 / RDBK
    priority        list[str]  every jurisdiction, e.g. ["NERC S.41 England", ...]
    legal           list[str]  every instrument, e.g. ["WCA 1981 Sch5", ...]

In PANTHEON_ONLY mode only `rarity` is populated, from Pantheon's own GB status.

Safe to re-run. Backs up as pantheon_analysis_service.py.bak_fix2.
"""
import os
import shutil
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(_ROOT, "shared", "services", "pantheon_analysis_service.py")
BACKUP = TARGET + ".bak_fix2"

OLD_DATACLASS = """    broad_biotope: str
    habitat: str"""

NEW_DATACLASS = """    broad_biotope: str
    habitat: str

    # Structured tracks, so consumers do not have to parse display strings.
    # Empty by default -- PANTHEON_ONLY mode fills only `rarity`.
    rarity: str = ""
    threat: str = ""
    threat_legacy: str = ""
    priority: list = field(default_factory=list)
    legal: list = field(default_factory=list)"""

OLD_CODEX_ENTRY = """                    broad_biotope=", ".join(tvk_bios[:2]),
                    habitat=", ".join(tvk_habs[:2]),
                ))"""

NEW_CODEX_ENTRY = """                    broad_biotope=", ".join(tvk_bios[:2]),
                    habitat=", ".join(tvk_habs[:2]),
                    rarity=(cs.rarity_modern.value if cs.rarity_modern
                            else (cs.rarity_legacy.value if cs.rarity_legacy else "")),
                    threat=(cs.threat_iucn_2001.value if cs.threat_iucn_2001 else ""),
                    threat_legacy=(cs.threat_iucn_legacy.value
                                   if cs.threat_iucn_legacy else ""),
                    priority=[e.value for e in (cs.priority or [])],
                    legal=[(e.detail or e.value) for e in (cs.legal_protection or [])],
                ))"""

OLD_PAN_ENTRY = """                    broad_biotope=", ".join(profile.broad_biotopes[:2]),
                    habitat=", ".join(profile.habitats[:2]),
                ))"""

NEW_PAN_ENTRY = """                    broad_biotope=", ".join(profile.broad_biotopes[:2]),
                    habitat=", ".join(profile.habitats[:2]),
                    rarity=profile.gb_status or "",
                ))"""

EDITS = [
    ("KeySpeciesEntry fields", OLD_DATACLASS, NEW_DATACLASS),
    ("Codex-mode entry", OLD_CODEX_ENTRY, NEW_CODEX_ENTRY),
    ("Pantheon-mode entry", OLD_PAN_ENTRY, NEW_PAN_ENTRY),
]


def main():
    if not os.path.exists(TARGET):
        print(f"NOT FOUND: {TARGET}")
        return 1

    with open(TARGET, "r", encoding="utf-8") as f:
        text = f.read()

    print("")
    print("Patching pantheon_analysis_service.py -- structured tracks on entries")
    print("=" * 70)

    applied = failed = 0
    for desc, old, new in EDITS:
        if new in text:
            print(f"  = {desc:24} already patched")
        elif old in text:
            if text.count(old) != 1:
                print(f"  x {desc:24} NOT UNIQUE ({text.count(old)} matches)")
                failed += 1
                continue
            text = text.replace(old, new)
            print(f"  + {desc:24} patched")
            applied += 1
        else:
            print(f"  x {desc:24} ANCHOR NOT FOUND")
            failed += 1

    print("")
    if failed:
        print(f"  {failed} edit(s) failed -- NOTHING WRITTEN.")
        print("  Line endings may differ from the copy this was written against.")
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
        print(f"    restore: copy {os.path.basename(BACKUP)} pantheon_analysis_service.py")
        return 1

    print("")
    print("  NEXT: python scripts/patch_conservation_tab.py")
    print("  (Examen will run unchanged until then -- the new fields are")
    print("   populated but nothing reads them yet.)")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
