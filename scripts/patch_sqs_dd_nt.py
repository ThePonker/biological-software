"""patch_sqs_dd_nt.py -- Data Deficient and Near Threatened do not elevate the SQS.

    python scripts/patch_sqs_dd_nt.py

No rebuild needed: derived scores are computed on demand (backlog D9), so the
correction takes effect the next time Examen runs.

The fault
---------
shared/sqs_derivation.py treats Data Deficient as conferring Nationally Rare
status, and gives Near Threatened its own score of 2. Both were documented as
"not in the published lexicon, but Pantheon's practice".

Measured against pantheon.db: **no species anywhere scores 2** (11,311 scores,
values 0, 1, 4, 8, 16, 32 only). And Pantheon's own scoring-systems page
(https://pantheon.brc.ac.uk/content/scoring-systems) sets out five criteria,
in which DD and NT appear only as things a rare or scarce species may ALSO be:

  1 -> 1    species not classed as RDB-App, RDB 1-3, or notable
  2 -> 4    "Nationally Scarce species that do not qualify under any of the
            other criteria. They may be classed as IUCN Least Concern, Near
            Threatened, or Data Deficient, Not Evaluated, or Not Assessed. In
            older reviews, species classed as Notable, Notable A, Notable B,
            Scarce, RDB I and RDB K."
  3 -> 8    "Nationally Rare species that do not qualify under any of the other
            criteria. They may be classed as IUCN Least Concern, Near
            Threatened, or Data Deficient... In older reviews, RDB 3"
  4 -> 16   "In older reviews, species classed as RDB 2"
  5 -> 32   "In older reviews, species classed as RDB 1"

So the score is driven by RARITY, and by THREAT only from Vulnerable upwards.
Neither DD nor NT qualifies a species for anything on its own.

The module's own docstrings already said so -- "Note there is no score of 2 in
the published rule" and "Returns 0, 1, 4, 8, 16 or 32". The code had drifted
from its own documentation.

Scale of the error, measured on codex.db (invertebrates with no Pantheon score):

    NT alone       38 species scoring 2, should be 1
    DD alone      156 species scoring 8, should be 1   <-- eight times too high
    DD + rarity    27 species scoring 8, ALREADY CORRECT (the rarity qualifies them)

196 species in total, and the error is always upward, so it inflates any SQI
for a site holding them.

Note on the judgement being reversed
------------------------------------
35_SQS_Stored_vs_Derived.md recorded "DD -> rare" as a deliberate reading: Data
Deficient means the species was reviewed and could not be assessed, not that it
is common, so treating it as potentially rare is a defensible precaution.

That is a reasonable position, but it is not Pantheon's, and the entire purpose
of the derived score is to apply Pantheon's published rule to current statuses.
A score computed by a different rule is not comparable with a published SQI,
which is the one thing the derived score exists to preserve.

Safe to re-run. Backs up as sqs_derivation.py.bak_fix1.
"""
import os
import shutil
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(_ROOT, "shared", "sqs_derivation.py")
BACKUP = TARGET + ".bak_fix1"

OLD_COMMENT = '''# Not in the published lexicon, but Pantheon's practice and already present in
# Codex as derived scores. Data Deficient means the species went through review
# and could not be assessed -- not that it is common -- so Pantheon scores it as
# rare. Near Threatened sits between common and scarce at 2.
_DATA_DEFICIENT = {"DD", "DATA DEFICIENT"}
_NEAR_THREATENED = {"NT", "NEAR THREATENED"}'''

NEW_COMMENT = '''# Data Deficient and Near Threatened DO NOT elevate the score.
#
# Pantheon's scoring-systems page lists five criteria, and DD and NT appear in
# them only as things a Nationally Scarce or Nationally Rare species may ALSO
# be -- never as a qualification in their own right:
#
#   "Nationally Scarce species that do not qualify under any of the other
#    criteria. They may be classed as IUCN Least Concern, Near Threatened, or
#    Data Deficient, Not Evaluated, or Not Assessed."
#
# So a species that is DD or NT and nothing else scores 1, and one that is DD
# AND Nationally Rare scores 8 because of the rarity, not the DD.
#
# These sets are retained for readability and for any caller that wants to
# report the status; they take no part in the score. See patch_sqs_dd_nt.py.
_DATA_DEFICIENT = {"DD", "DATA DEFICIENT"}
_NEAR_THREATENED = {"NT", "NEAR THREATENED"}'''

OLD_FLAGS = '''    rdb_confers_rare = tl in _RDB1 or tl in _RDB23 or tl in _RDB_KI or tl in _RDB_EXTINCT
    is_dd = t in _DATA_DEFICIENT or tl in _DATA_DEFICIENT
    is_nt = t in _NEAR_THREATENED or tl in _NEAR_THREATENED
    iucn_confers_listing = t in _CRITICAL or t in _ENDANGERED or t in _VULNERABLE
    is_rare = r in _RARE or rdb_confers_rare or is_dd'''

NEW_FLAGS = '''    rdb_confers_rare = tl in _RDB1 or tl in _RDB23 or tl in _RDB_KI or tl in _RDB_EXTINCT
    iucn_confers_listing = t in _CRITICAL or t in _ENDANGERED or t in _VULNERABLE
    # DD is deliberately NOT included: it qualifies a species for nothing on its
    # own. A Data Deficient species that is also Nationally Rare still scores 8,
    # through r in _RARE.
    is_rare = r in _RARE or rdb_confers_rare'''

OLD_NT_BLOCK = '''    # 2 -- Near Threatened, per Pantheon practice
    if is_nt:
        return 2

    # 1 -- everything else that is native and neither rare nor scarce
    return 1'''

NEW_NT_BLOCK = '''    # 1 -- everything else that is native and neither rare nor scarce.
    #      This includes species that are only Near Threatened, Data Deficient,
    #      Least Concern, Not Evaluated or Not Assessed: under Pantheon's rule
    #      none of those qualifies a species for a higher score.
    return 1'''

OLD_VALID = "VALID_SCORES = (0, 1, 2, 4, 8, 16, 32)"
NEW_VALID = "VALID_SCORES = (0, 1, 4, 8, 16, 32)"

EDITS = [
    ("DD / NT vocabulary comment", OLD_COMMENT, NEW_COMMENT),
    ("DD no longer confers rare", OLD_FLAGS, NEW_FLAGS),
    ("NT no longer scores 2", OLD_NT_BLOCK, NEW_NT_BLOCK),
    ("VALID_SCORES", OLD_VALID, NEW_VALID),
]


def main():
    if not os.path.exists(TARGET):
        print(f"NOT FOUND: {TARGET}")
        return 1
    with open(TARGET, "r", encoding="utf-8") as f:
        text = f.read()

    print("")
    print("Patching shared/sqs_derivation.py -- DD and NT do not elevate")
    print("=" * 70)

    if "DO NOT elevate the score" in text:
        print("  = already patched -- nothing to do")
        return 0

    failed = 0
    for label, old, new in EDITS:
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

    # ---- verify the rule directly ------------------------------------
    print("")
    print("  Checking the rule now matches Pantheon's five criteria...")
    try:
        import py_compile
        py_compile.compile(TARGET, doraise=True)
        sys.path.insert(0, _ROOT)
        import importlib
        m = importlib.import_module("shared.sqs_derivation")
        importlib.reload(m)

        cases = [
            ("nothing",                    dict(),                                    1),
            ("NT alone",                   dict(threat="NT"),                         1),
            ("DD alone",                   dict(threat="DD"),                         1),
            ("LC alone",                   dict(threat="LC"),                         1),
            ("Nationally Scarce",          dict(rarity="NS"),                         4),
            ("Notable B",                  dict(rarity="Nb"),                         4),
            ("Nationally Rare",            dict(rarity="NR"),                         8),
            ("DD + Nationally Rare",       dict(rarity="NR", threat="DD"),            8),
            ("NT + Nationally Scarce",     dict(rarity="NS", threat="NT"),            4),
            ("RDB3 (rare, pre-1994)",      dict(rarity="NR", threat_legacy="RDB3"),   8),
            ("Vulnerable + scarce",        dict(rarity="NS", threat="VU"),            8),
            ("Endangered + rare",          dict(rarity="NR", threat="EN"),           16),
            ("Critically Endangered",      dict(rarity="NR", threat="CR"),           32),
            ("non-native",                 dict(rarity="NR", native=False),           0),
        ]
        bad = 0
        for label, kw, expect in cases:
            got = m.derive_sqs(**kw)
            mark = " " if got == expect else "x"
            if got != expect:
                bad += 1
            print(f"    {mark} {label:26} -> {got:>2}  (expected {expect})")
        if bad:
            print(f"  x {bad} case(s) wrong -- restore from the backup")
            return 1
        print("  + all cases match the published rule")
    except Exception as e:  # noqa: BLE001
        print(f"  x FAILED: {type(e).__name__}: {e}")
        print(f"    restore: copy {os.path.basename(BACKUP)} sqs_derivation.py")
        return 1

    print("")
    print("  No rebuild needed -- derivation is live.")
    print("  Re-run scripts/check_sqs_dd.py: 'NT only' and 'DD only' should")
    print("  now show {1: ...}, and 'DD with rarity' should stay at 8.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
