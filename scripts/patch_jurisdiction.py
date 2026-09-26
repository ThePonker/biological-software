"""patch_jurisdiction.py -- key species only count designations that apply.

    python scripts/patch_jurisdiction.py

Corrected twice:
  v1 anchored on individual _classify call sites and refused to write -- there
     are four, and the batch line is a substring of the single line.
  v2 placed the constants immediately before _classify, which sits at the BOTTOM
     of the module, while the method signatures referencing DEFAULT_JURISDICTION
     are in the class above. Default arguments evaluate when the class body runs,
     so it raised NameError on import.

This version puts the jurisdiction block near the top, alongside
PANTHEON_GB_STATUS_MAP and the RARE_/SCARCE_ threshold sets -- the same kind of
vocabulary, and defined before anything uses it.

The problem
-----------
_classify sets the Priority tier for ANY priority listing or ANY legal
protection, regardless of where the site is. So an English site picks up key
species on the strength of Scottish or Northern Irish listings.

Glory Park, Northamptonshire: four of its twelve key species qualify only via
the Scottish Biodiversity List and the NI Priority Species List. None is on
Section 41. One is Osmia bicornis, the Red Mason Bee -- among the commonest
solitary bees in England.

Why this is the right reading
-----------------------------
Section 41 of the NERC Act 2006 requires the Secretary of State to publish a
list of species of principal importance for the conservation of biodiversity
IN ENGLAND, and the section 40 biodiversity duty points public bodies at that
list as a material consideration in planning. A list made by Scottish Ministers
carries no such weight in an English determination.

Reviewed English EcIAs are consistent: they scope "habitats and species of
principal importance (Section 41 list)" and never cite the SBL. JNCC's own UK
BAP priority invertebrate list is published with per-country Y/N columns, so the
profession already treats priority listings as jurisdiction-specific at source.

What changes
------------
Rarity and threat are GB-wide and untouched. Only priority and legal_protection
are filtered, and only for conferring KEY SPECIES status. Every designation is
still stored, returned and displayed -- an SBL listing recorded in England stays
visible in the appendix and is worth a sentence. It simply does not make the
species a key species there.

England: NERC S.41 and UK BAP count. SBL, NI Priority and Env (Wales) Act S7 do
not. Legal protection counts except the Northern Ireland-only instruments.

Default is England. Pass jurisdiction="Scotland" (etc.) for work elsewhere.

Safe to re-run. Backs up as codex_repository.py.bak_fix3.
"""
import os
import shutil
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(_ROOT, "shared", "repositories", "codex_repository.py")
BACKUP = TARGET + ".bak_fix3"

# Inserted immediately BEFORE this existing anchor, so the names exist before
# the class body is executed.
ANCHOR = "# Key-species classification thresholds"

HELPER = '''# ============================================================
# Jurisdiction -- which designations confer key-species status where
# ============================================================
# A priority listing is made under the law of one country and is a material
# consideration only there. Section 41 is England's list; the Scottish
# Biodiversity List is Scotland's. Rarity and threat are GB-wide and are not
# filtered. This affects the KEY SPECIES decision only -- every designation is
# still stored, returned and displayed.
#
# Defined here, above the class, because method default arguments are evaluated
# when the class body runs.

DEFAULT_JURISDICTION = "England"

# Substrings matched case-insensitively against status_value.
_PRIORITY_BY_JURISDICTION = {
    "England":          ("s.41", "s41", "section 41", "bap"),
    "Wales":            ("wales", "s7", "bap"),
    "Scotland":         ("scottish", "bap"),
    "Northern Ireland": ("northern ireland", "ni priority", "bap"),
    "UK":               (),   # empty tuple = accept everything
}

# Legal instruments that apply only in Northern Ireland, matched against
# status_detail. Everything else (WACA, Habitats Regs, Bern, CITES, CMS, the
# Directives) is GB-wide or international.
_NI_ONLY_LEGAL = ("ni wildlife order", "ni conservation regs")


def _priority_applies(value, jurisdiction):
    keys = _PRIORITY_BY_JURISDICTION.get(jurisdiction)
    if keys is None or keys == ():
        return True          # unknown or UK-wide: do not filter
    v = (value or "").lower()
    return any(k in v for k in keys)


def _legal_applies(entry, jurisdiction):
    if jurisdiction in ("Northern Ireland", "UK"):
        return True
    d = ((entry.detail or entry.value) or "").lower()
    return not any(k in d for k in _NI_ONLY_LEGAL)


'''

OLD_CLASSIFY_DEF = '''def _classify(status):
    """Classify into Rare / Scarce / Priority / None.

    Called ONLY for invertebrate species (the caller is responsible for
    checking status.is_invertebrate). This function assumes invert-only.
    """'''

NEW_CLASSIFY_DEF = '''def _classify(status, jurisdiction=DEFAULT_JURISDICTION):
    """Classify into Rare / Scarce / Priority / None.

    Called ONLY for invertebrate species (the caller is responsible for
    checking status.is_invertebrate). This function assumes invert-only.

    `jurisdiction` filters which priority listings and legal instruments count
    towards the Priority tier. Rarity and threat are GB-wide and unfiltered.
    """'''

OLD_PRIORITY_TEST = '''    # Legal / priority -- priority tier
    if status.legal_protection or status.priority:
        is_priority = True'''

NEW_PRIORITY_TEST = '''    # Legal / priority -- priority tier, but only designations that apply in
    # this jurisdiction. An SBL listing does not make a species key in England.
    if any(_priority_applies(e.value, jurisdiction) for e in status.priority):
        is_priority = True
    if any(_legal_applies(e, jurisdiction) for e in status.legal_protection):
        is_priority = True'''

SIGNATURE_EDITS = [
    ("get_status_summary signature",
     "    def get_status_summary(self, tvk, mode=AnalysisMode.CODEX_FULL):",
     "    def get_status_summary(self, tvk, mode=AnalysisMode.CODEX_FULL,\n"
     "                           jurisdiction=DEFAULT_JURISDICTION):", 1),
    ("get_statuses_batch signature",
     "    def get_statuses_batch(self, tvks, mode=AnalysisMode.CODEX_FULL):",
     "    def get_statuses_batch(self, tvks, mode=AnalysisMode.CODEX_FULL,\n"
     "                           jurisdiction=DEFAULT_JURISDICTION):", 1),
    ("_pantheon_status signature",
     "    def _pantheon_status(self, tvk):",
     "    def _pantheon_status(self, tvk, jurisdiction=DEFAULT_JURISDICTION):", 1),
    ("_pantheon_statuses_batch signature",
     "    def _pantheon_statuses_batch(self, tvks):",
     "    def _pantheon_statuses_batch(self, tvks, jurisdiction=DEFAULT_JURISDICTION):", 1),
    ("_pantheon_status delegation",
     "            return self._pantheon_status(tvk)",
     "            return self._pantheon_status(tvk, jurisdiction)", 1),
    ("_pantheon_statuses_batch delegation",
     "            return self._pantheon_statuses_batch(tvks)",
     "            return self._pantheon_statuses_batch(tvks, jurisdiction)", 1),
]


def main():
    if not os.path.exists(TARGET):
        print(f"NOT FOUND: {TARGET}")
        return 1

    with open(TARGET, "r", encoding="utf-8") as f:
        text = f.read()

    print("")
    print("Patching codex_repository.py -- jurisdiction-aware key species")
    print("=" * 70)

    if "_PRIORITY_BY_JURISDICTION" in text:
        print("  = already patched -- nothing to do")
        return 0

    failed = 0

    # 1. Constants near the top, before the class body executes.
    if text.count(ANCHOR) == 1:
        text = text.replace(ANCHOR, HELPER + ANCHOR)
        print("  + jurisdiction tables (above the class)")
    else:
        print(f"  x could not place constants  ({text.count(ANCHOR)} matches)")
        failed += 1

    # 2. _classify signature and body.
    if text.count("def _classify(status)") == 1:
        text = text.replace(OLD_CLASSIFY_DEF, NEW_CLASSIFY_DEF)
        print("  + _classify signature")
    else:
        print("  x could not locate _classify definition")
        failed += 1

    if text.count(OLD_PRIORITY_TEST) == 1:
        text = text.replace(OLD_PRIORITY_TEST, NEW_PRIORITY_TEST)
        print("  + priority/legal test")
    else:
        print(f"  x priority/legal test  ({text.count(OLD_PRIORITY_TEST)} matches)")
        failed += 1

    # 3. Signatures and delegations.
    for desc, old, new, expect in SIGNATURE_EDITS:
        n = text.count(old)
        if n == expect:
            text = text.replace(old, new)
            print(f"  + {desc}")
        else:
            print(f"  x {desc}  ({n} matches, expected {expect})")
            failed += 1

    # 4. All four call sites.
    n_calls = text.count("_classify(status)")
    if n_calls == 4:
        text = text.replace("_classify(status)", "_classify(status, jurisdiction)")
        print(f"  + {n_calls} _classify call sites")
    else:
        print(f"  x _classify calls  ({n_calls} found, expected 4)")
        failed += 1

    print("")
    if failed:
        print(f"  {failed} edit(s) failed -- NOTHING WRITTEN.")
        return 1

    shutil.copy2(TARGET, BACKUP)
    print(f"  backup written: {os.path.basename(BACKUP)}")
    with open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(text)

    # 5. Compile AND import -- compiling alone would not have caught the
    #    NameError that the previous version introduced.
    print("")
    print("  Checking the file compiles and imports...")
    try:
        import py_compile
        py_compile.compile(TARGET, doraise=True)
        sys.path.insert(0, _ROOT)
        import importlib
        m = importlib.import_module("shared.repositories.codex_repository")
        importlib.reload(m)
        assert hasattr(m, "DEFAULT_JURISDICTION")
        print(f"  + imports cleanly, default jurisdiction: {m.DEFAULT_JURISDICTION}")
    except Exception as e:  # noqa: BLE001
        print(f"  x FAILED: {type(e).__name__}: {e}")
        print(f"    restore: copy {os.path.basename(BACKUP)} codex_repository.py")
        return 1

    print("")
    print("  NEXT: python -m Examen -> Glory Park")
    print("  Expect key species 12 -> 8, Priority listings group gone,")
    print("  Rare 0 / Scarce 8 / Priority 0.")
    print("")
    print("  Every site's figures change -- check each against what you")
    print("  reported at the time, Kent Deadwood especially.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
