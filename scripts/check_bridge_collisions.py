"""check_bridge_collisions.py -- characterise the unbridged Pantheon species.

    python scripts/check_bridge_collisions.py

Read-only. Writes nothing.

Supersedes check_bridge_gap.py, which re-derived the unmatched set from the
original two-pass logic and therefore reports every recovery as a collision once
the synonym pass (J1) is in. Use this one from now on.

Background
----------
After J1 the bridge resolves by three passes -- direct TVK, name, then synonym --
accepting a synonym match only where no other Pantheon species has already
claimed that UKSI TVK. 1,153 species were recovered; 1,847 were declined as
collisions; 68 resolve by no route at all.

A collision means UKSI has merged two Pantheon taxa into one current species.
Pantheon holds separate SQS and ecology for each, and sqs_scores is keyed on tvk
alone, so inserting one would silently overwrite the other.

But "collision" covers at least three different situations, and only one of them
needs a judgement:

  1. Spelling corrections  -- Actocharis readingi -> readingii
  2. Subgenus reformatting -- Acetropis gimmerthalii
                              -> Acetropis (Acetropis) gimmerthalii
  3. Genuine synonymisation -- Abraeus globosus -> A. perpusillus

(1) and (2) are the same animal under two spellings: merging is bookkeeping.
(3) is two species Pantheon treated separately, and their records may disagree.

This script sorts the collisions into those groups and, for the real merges,
measures how often the two Pantheon records actually disagree -- on SQS, and on
ecology. That decides whether a blanket rule is safe or whether a list needs
working through by eye.
"""
import os
import re
import sys
from collections import defaultdict

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import sqlite3  # noqa: E402
import paths    # noqa: E402


def epithet(name):
    """Last alphabetic word -- the species epithet, ignoring subgenus brackets."""
    if not name:
        return ""
    cleaned = re.sub(r"\([^)]*\)", " ", name)
    words = [w for w in re.split(r"[^A-Za-z]+", cleaned) if w]
    return words[-1].lower() if words else ""


def similar(a, b):
    """True if two epithets differ only trivially (i/ii, us/a, ending -e/-is)."""
    a, b = a.lower(), b.lower()
    if a == b:
        return True
    short, long_ = sorted((a, b), key=len)
    if long_.startswith(short) and len(long_) - len(short) <= 2:
        return True
    # common gender-ending swaps
    for x, y in (("us", "a"), ("us", "um"), ("is", "e"), ("i", "ii")):
        if a[:-len(x)] == b[:-len(y)] and a.endswith(x) and b.endswith(y):
            return True
        if b[:-len(x)] == a[:-len(y)] and b.endswith(x) and a.endswith(y):
            return True
    return False


def main():
    pan = sqlite3.connect(f"file:{paths.PANTHEON_DB}?mode=ro", uri=True)
    uk = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)
    cx = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)

    print("")
    print("Unbridged Pantheon species -- what kind of problem is each?")
    print("=" * 78)

    bridged_pan = {r[0]: r[1] for r in
                   cx.execute("SELECT pantheon_tvk, uksi_tvk FROM tvk_bridge")}
    claimed = defaultdict(list)
    for ptvk, utvk in bridged_pan.items():
        claimed[utvk].append(ptvk)

    synonyms = {}
    for syn, tvk in uk.execute("SELECT synonym, tvk FROM synonyms"):
        if syn:
            synonyms.setdefault(syn.lower(), tvk)

    pan_species = pan.execute("SELECT tvk, species_name FROM species").fetchall()
    pan_names = {t: n for t, n in pan_species}

    unbridged = [(t, n) for t, n in pan_species if t not in bridged_pan]
    print(f"  Pantheon species:        {len(pan_species):,}")
    print(f"  bridged after J1:        {len(bridged_pan):,}")
    print(f"  still unbridged:         {len(unbridged):,}")

    # ------------------------------------------------------------------
    # Split: collides with a claimed target, or resolves by nothing.
    # ------------------------------------------------------------------
    collisions, unresolvable = [], []
    for ptvk, pname in unbridged:
        target = synonyms.get((pname or "").lower())
        if target and target in claimed:
            collisions.append((ptvk, pname, target))
        else:
            unresolvable.append((ptvk, pname))

    print(f"    of which collisions:   {len(collisions):,}")
    print(f"    resolve by no route:   {len(unresolvable):,}")

    # ------------------------------------------------------------------
    # Classify the collisions.
    # ------------------------------------------------------------------
    spelling, subgenus, real_merge = [], [], []
    for ptvk, pname, target in collisions:
        cur = uk.execute("SELECT scientific_name FROM taxa WHERE tvk=?",
                         (target,)).fetchone()
        cur_name = cur[0] if cur else ""
        incumbents = [pan_names.get(p, "") for p in claimed[target]]

        if "(" in cur_name and epithet(cur_name) == epithet(pname):
            subgenus.append((pname, cur_name, incumbents))
        elif similar(epithet(pname), epithet(cur_name)):
            spelling.append((pname, cur_name, incumbents))
        else:
            real_merge.append((ptvk, pname, target, cur_name, incumbents))

    print("")
    print("  COLLISIONS BY KIND")
    print("  " + "-" * 74)
    print(f"    spelling / gender variants:   {len(spelling):>5}   bookkeeping")
    print(f"    subgenus reformatting:        {len(subgenus):>5}   bookkeeping")
    print(f"    genuine synonymisation:       {len(real_merge):>5}   needs a rule")

    # ------------------------------------------------------------------
    # For the real merges: do the two Pantheon records actually disagree?
    # ------------------------------------------------------------------
    def pan_sqs(tvk):
        r = pan.execute("SELECT sqs FROM sqs_scores WHERE tvk=?", (tvk,)).fetchone()
        return r[0] if r else None

    def pan_set(table, tvk, col):
        try:
            return {r[0] for r in pan.execute(
                f"SELECT DISTINCT {col} FROM {table} WHERE tvk=?", (tvk,))}
        except sqlite3.Error:
            return set()

    both_sqs = agree_sqs = disagree_sqs = one_only = neither = 0
    disagreements = []
    ecology_differs = 0

    for ptvk, pname, target, cur_name, _inc in real_merge:
        others = claimed[target]
        mine = pan_sqs(ptvk)
        theirs = [pan_sqs(o) for o in others]
        theirs = [t for t in theirs if t is not None]

        if mine is not None and theirs:
            both_sqs += 1
            if all(t == mine for t in theirs):
                agree_sqs += 1
            else:
                disagree_sqs += 1
                disagreements.append(
                    (pname, mine, cur_name, theirs,
                     [pan_names.get(o, o) for o in others]))
        elif mine is not None or theirs:
            one_only += 1
        else:
            neither += 1

        for table, col in (("habitats", "habitat"),
                           ("feeding_guilds", "guild"),
                           ("specific_assemblage_types", "sat")):
            a = pan_set(table, ptvk, col)
            b = set()
            for o in others:
                b |= pan_set(table, o, col)
            if a and b and a != b:
                ecology_differs += 1
                break

    print("")
    print("  DO THE MERGING RECORDS DISAGREE?  (genuine synonymisations only)")
    print("  " + "-" * 74)
    print(f"    both sides carry an SQS:      {both_sqs:>5}")
    print(f"      and they AGREE:             {agree_sqs:>5}   merge is trivial")
    print(f"      and they DISAGREE:          {disagree_sqs:>5}   needs a rule")
    print(f"    only one side has an SQS:     {one_only:>5}   take the one")
    print(f"    neither has an SQS:           {neither:>5}   nothing to merge")
    print(f"    ecology sets differ:          {ecology_differs:>5}   union or pick")

    if disagreements:
        print("")
        print("  SQS DISAGREEMENTS -- the cases a rule would decide")
        print("  " + "-" * 74)
        for pname, mine, cur_name, theirs, othernames in disagreements[:30]:
            th = ", ".join(str(t) for t in theirs)
            print(f"    {str(pname)[:30]:30} SQS {mine}"
                  f"  vs  {th}  ({', '.join(othernames)[:34]})")
            print(f"      -> both are now {cur_name}")
        if len(disagreements) > 30:
            print(f"    ... and {len(disagreements) - 30} more")

    # ------------------------------------------------------------------
    # How many of these would you actually meet?
    # ------------------------------------------------------------------
    print("")
    print("  RELEVANCE TO YOUR OWN RECORDS")
    print("  " + "-" * 74)
    try:
        obs = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
        hit = 0
        for _p, pname, _t, _c, _i in real_merge:
            n = obs.execute(
                "SELECT COUNT(1) FROM observations WHERE species_name=?",
                (pname,)).fetchone()[0]
            if n:
                hit += 1
        print(f"    merging species you have recorded under the old name: {hit:,}")
        obs.close()
    except sqlite3.Error as e:
        print(f"    could not read observatum.db: {e}")

    # ------------------------------------------------------------------
    # The 68 that resolve by nothing.
    # ------------------------------------------------------------------
    if unresolvable:
        print("")
        print("  RESOLVE BY NO ROUTE")
        print("  " + "-" * 74)
        vernacular = [n for _t, n in unresolvable
                      if n and (" " not in n.strip()
                                or n.strip()[0].isupper() and n.strip().split()[-1][0].isupper())]
        print(f"    total: {len(unresolvable)}   of which look vernacular: "
              f"{len(vernacular)}")
        for _t, n in unresolvable[:20]:
            print(f"      {n}")
        if len(unresolvable) > 20:
            print(f"      ... and {len(unresolvable) - 20} more")

    print("")
    print("  Nothing has been changed.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
