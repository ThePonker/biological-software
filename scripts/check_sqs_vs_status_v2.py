"""check_sqs_vs_status.py -- where does a stored SQS contradict its own status?

    python scripts/check_sqs_vs_status.py

Read-only. Writes nothing.

Corrected version
-----------------
An earlier run of this script imported seed_codex.SQS_DEFAULTS as "the rule".
That was wrong. SQS_DEFAULTS is the GAP-FILL table, and it differs from the
published rule in two material ways:

  * it scores ("threat_iucn_legacy", "RDB3") as 16, "per Fowles original SQI" --
    a different index. The published Pantheon rule puts RDB 2 and RDB 3 at 8.
  * it maps single (track, value) pairs and takes the maximum, whereas the
    published rule is a function of rarity AND threat together. "Nationally Rare
    with RDB K" is capped at 4 by the rule but scores 8 under max-of-pairs.

The earlier figures (52% agreement, 408 bad incumbents) were artefacts of that
substitution and should be disregarded.

This version imports shared.sqs_derivation, which implements the published rule
from https://pantheon.brc.ac.uk/lexicon/sqs.

What it answers
---------------
1. How often does a stored Pantheon SQS disagree with the rule applied to
   current Codex statuses? (Expect ~20% -- finding 54.)
2. Of the J2 merge incumbents, how many carry a score their own conservation
   status does not support? That decides whether "incumbent wins" is a safe
   merge rule.

The trigger case: Hylaeus annularis is stored at 1 but carries RDB 3, which the
rule scores at 8 for a rare species. Its three synonyms are all stored at 8.
"""
import os
import sys
from collections import Counter

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import sqlite3  # noqa: E402
import paths    # noqa: E402
from shared.sqs_derivation import derive_from_tracks  # noqa: E402


def main():
    cx = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)
    pan = sqlite3.connect(f"file:{paths.PANTHEON_DB}?mode=ro", uri=True)
    uk = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)

    print("")
    print("Stored SQS vs the published rule applied to Codex statuses")
    print("=" * 78)
    print("  rule: shared/sqs_derivation.py (Pantheon lexicon)")

    invert = {r[0] for r in cx.execute(
        "SELECT DISTINCT tvk FROM designations WHERE category='Invertebrate'")}

    tracks = {}
    for tvk, track, value in cx.execute(
            "SELECT tvk, status_track, status_value FROM status_summary"):
        tracks.setdefault(tvk, {})[track] = value

    stored = {r[0]: (r[1], r[2]) for r in cx.execute(
        "SELECT tvk, sqs, source FROM sqs_scores")}

    # ------------------------------------------------------------------
    # 1. Overall agreement, Pantheon-sourced scores only.
    # ------------------------------------------------------------------
    agree = higher = lower = 0
    shifts = Counter()
    for tvk, (sqs, source) in stored.items():
        if tvk not in invert or source != "pantheon":
            continue
        d = derive_from_tracks(tracks.get(tvk, {}))
        if d == sqs:
            agree += 1
        else:
            shifts[(sqs, d)] += 1
            if d > sqs:
                higher += 1
            else:
                lower += 1

    total = agree + higher + lower
    print("")
    print(f"  Pantheon-sourced invertebrate scores:   {total:,}")
    if total:
        print(f"    stored matches the rule:      {agree:>6,}"
              f"   ({agree * 100 // total}%)")
        print(f"    rule scores HIGHER:           {higher:>6,}")
        print(f"    rule scores LOWER:            {lower:>6,}")
    print("")
    print("  most common stored -> derived shifts:")
    for (a, b), n in shifts.most_common(12):
        print(f"    {a:>3} -> {b:<3} {'UP  ' if b > a else 'DOWN'}  {n:>5,}")

    # ------------------------------------------------------------------
    # 2. The gap-filled scores -- computed by the WRONG table.
    # ------------------------------------------------------------------
    d_agree = d_diff = 0
    d_shifts = Counter()
    for tvk, (sqs, source) in stored.items():
        if source != "derived":
            continue
        d = derive_from_tracks(tracks.get(tvk, {}))
        if d == sqs:
            d_agree += 1
        else:
            d_diff += 1
            d_shifts[(sqs, d)] += 1

    print("")
    print("  GAP-FILLED SCORES vs the published rule")
    print("  " + "-" * 74)
    print("  (seed_codex derived these from its own table, not this rule)")
    print(f"    agree with the rule:          {d_agree:>6,}")
    print(f"    DIFFER from the rule:         {d_diff:>6,}")
    for (a, b), n in d_shifts.most_common(10):
        print(f"      {a:>3} -> {b:<3} {'UP  ' if b > a else 'DOWN'}  {n:>5,}")

    # ------------------------------------------------------------------
    # 3. Does this affect the J2 merge incumbents?
    # ------------------------------------------------------------------
    print("")
    print("  DOES THIS AFFECT THE MERGE INCUMBENTS?")
    print("  " + "-" * 74)

    synonyms = {}
    for syn, tvk in uk.execute("SELECT synonym, tvk FROM synonyms"):
        if syn:
            synonyms.setdefault(syn.lower(), tvk)

    bridged = {r[0]: r[1] for r in cx.execute(
        "SELECT pantheon_tvk, uksi_tvk FROM tvk_bridge")}
    claimed = set(bridged.values())

    incumbents = set()
    for ptvk, pname in pan.execute("SELECT tvk, species_name FROM species"):
        if ptvk in bridged or not pname:
            continue
        target = synonyms.get(pname.lower())
        if target and target in claimed:
            incumbents.add(target)

    bad = []
    for tvk in incumbents:
        if tvk not in stored or tvk not in invert:
            continue
        sqs = stored[tvk][0]
        d = derive_from_tracks(tracks.get(tvk, {}))
        if d != sqs:
            nm = uk.execute("SELECT scientific_name FROM taxa WHERE tvk=?",
                            (tvk,)).fetchone()
            st = ", ".join(f"{k}={v}" for k, v in tracks.get(tvk, {}).items()
                           if k.startswith(("rarity", "threat")))
            bad.append((nm[0] if nm else tvk, sqs, d, st))

    print(f"    merge incumbents (invertebrate, scored):   {len(incumbents):,}")
    print(f"    whose stored SQS differs from the rule:    {len(bad):,}")

    if bad:
        under = [b for b in bad if b[2] > b[1]]
        print(f"      of those, stored is TOO LOW:             {len(under):,}")
        print("")
        print("    worst under-scores -- 'incumbent wins' would carry these:")
        for nm, sqs, d, st in sorted(bad, key=lambda r: -(r[2] - r[1]))[:25]:
            print(f"      {nm[:34]:34} stored {sqs:>2} -> rule {d:>2}   {st[:38]}")
        if len(bad) > 25:
            print(f"      ... and {len(bad) - 25} more")

    print("")
    print("  Nothing has been changed.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
