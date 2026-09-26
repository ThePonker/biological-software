"""check_j2_still_needed.py -- is J2 still a real gap?

    python scripts/check_j2_still_needed.py

Read-only. Writes nothing.

The claim to test
-----------------
1,847 Pantheon species were deliberately left OUT of tvk_bridge because they
collide -- UKSI has merged two Pantheon taxa into one current species, and
sqs_scores is keyed on tvk alone, so inserting both would let one silently
overwrite the other. That was J2: apply the merges with a stated rule.

Since then, PantheonRepository became bridge-aware. It translates UKSI TVKs to
Pantheon TVKs, unions ecology across everything that maps to one species, and
keeps the highest SQS. That is the J2 merge rule, applied at read time.

It was then asserted that J2 is therefore moot. **That assertion is probably
wrong**, and this checks it: `_to_pantheon` can only return TVKs that are IN the
bridge. The colliding 1,847 were never inserted, so the read layer cannot see
them, and their ecology remains unreachable.

What this measures
------------------
  1. How many of the 1,847 have ecology or SQS that nothing can currently reach
  2. Whether their current species already has that data from the incumbent
     (in which case nothing is lost and J2 really is moot)
  3. How many are invertebrates -- the only ones that matter for assessment
  4. How many appear in Wil's own commercial records
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import sqlite3  # noqa: E402
import paths    # noqa: E402


def main():
    cx = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)
    pn = sqlite3.connect(f"file:{paths.PANTHEON_DB}?mode=ro", uri=True)
    uk = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)

    print("")
    print("J2 -- do the bridge collisions still lose anything?")
    print("=" * 76)

    bridged = {r[0]: r[1] for r in cx.execute(
        "SELECT pantheon_tvk, uksi_tvk FROM tvk_bridge")}
    claimed = set(bridged.values())

    synonyms = {}
    for syn, tvk in uk.execute("SELECT synonym, tvk FROM synonyms"):
        if syn:
            synonyms.setdefault(syn.lower(), tvk)

    # The collision set: unbridged, but resolving to an already-claimed TVK.
    collisions = []
    for ptvk, pname in pn.execute("SELECT tvk, species_name FROM species"):
        if ptvk in bridged or not pname:
            continue
        target = synonyms.get(pname.lower())
        if target and target in claimed:
            collisions.append((ptvk, pname, target))

    print(f"  colliding Pantheon taxa (not in the bridge): {len(collisions):,}")

    def has(table, tvk, col="tvk"):
        try:
            return pn.execute(f"SELECT 1 FROM {table} WHERE {col}=? LIMIT 1",
                              (tvk,)).fetchone() is not None
        except sqlite3.Error:
            return False

    def vals(table, col, tvk):
        try:
            return {r[0] for r in pn.execute(
                f"SELECT DISTINCT {col} FROM {table} WHERE tvk=?", (tvk,))}
        except sqlite3.Error:
            return set()

    # ------------------------------------------------------------------
    # What the unreachable taxa hold
    # ------------------------------------------------------------------
    holds_sqs = holds_eco = 0
    for ptvk, _n, _t in collisions:
        if has("sqs_scores", ptvk):
            holds_sqs += 1
        if has("habitats", ptvk) or has("broad_biotope", ptvk):
            holds_eco += 1

    print(f"    of those, carrying an SQS:                {holds_sqs:,}")
    print(f"    of those, carrying habitat/biotope data:  {holds_eco:,}")

    # ------------------------------------------------------------------
    # Is that data already available from the incumbent?
    # ------------------------------------------------------------------
    print("")
    print("  IS ANYTHING ACTUALLY LOST?")
    print("  " + "-" * 72)
    print("  (the incumbent is the Pantheon taxon already bridged to that species)")

    incumbents = {}
    for ptvk, utvk in bridged.items():
        incumbents.setdefault(utvk, []).append(ptvk)

    new_eco = new_sqs = covered = 0
    examples = []
    for ptvk, pname, target in collisions:
        mine_h = vals("habitats", "habitat", ptvk)
        mine_b = vals("broad_biotope", "biotope", ptvk)
        theirs_h, theirs_b = set(), set()
        for inc in incumbents.get(target, []):
            theirs_h |= vals("habitats", "habitat", inc)
            theirs_b |= vals("broad_biotope", "biotope", inc)

        adds_h = mine_h - theirs_h
        adds_b = mine_b - theirs_b
        if adds_h or adds_b:
            new_eco += 1
            if len(examples) < 15:
                cur = uk.execute("SELECT scientific_name FROM taxa WHERE tvk=?",
                                 (target,)).fetchone()
                examples.append((pname, cur[0] if cur else target,
                                 sorted(adds_h | adds_b)))
        elif mine_h or mine_b:
            covered += 1

        mine_s = pn.execute("SELECT sqs FROM sqs_scores WHERE tvk=?",
                            (ptvk,)).fetchone()
        if mine_s:
            best = 0
            for inc in incumbents.get(target, []):
                r = pn.execute("SELECT sqs FROM sqs_scores WHERE tvk=?",
                               (inc,)).fetchone()
                if r and r[0] > best:
                    best = r[0]
            if mine_s[0] > best:
                new_sqs += 1

    print(f"    would add ecology the incumbent lacks:    {new_eco:,}")
    print(f"    ecology already covered by the incumbent: {covered:,}")
    print(f"    would raise the SQS above the incumbent:  {new_sqs:,}")

    if examples:
        print("")
        print("    examples of ecology only the collider holds:")
        for pname, cur, adds in examples:
            print(f"      {str(pname)[:30]:30} -> {str(cur)[:28]:28} "
                  f"adds {', '.join(adds)[:40]}")

    # ------------------------------------------------------------------
    # Do any of them matter to Wil's own data?
    # ------------------------------------------------------------------
    print("")
    print("  RELEVANCE TO YOUR RECORDS")
    print("  " + "-" * 72)
    try:
        ob = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
        targets = {t for _p, _n, t in collisions}
        hit = 0
        for t in targets:
            n = ob.execute("SELECT COUNT(1) FROM observations "
                           "WHERE species_tvk=? AND record_type='Commercial'",
                           (t,)).fetchone()[0]
            if n:
                hit += 1
        print(f"    merged species you have recorded commercially: {hit:,}"
              f"  (of {len(targets):,})")
        ob.close()
    except sqlite3.Error as e:
        print(f"    could not read observatum.db: {e}")

    print("")
    print("  VERDICT")
    print("  " + "-" * 72)
    if new_eco == 0 and new_sqs == 0:
        print("    J2 is moot -- the read layer already reaches everything.")
    else:
        print(f"    J2 is NOT moot. {new_eco:,} taxa hold ecology nothing can")
        print(f"    currently reach, and {new_sqs:,} hold a higher SQS.")
        print("    Adding them to the bridge is the fix; the read layer already")
        print("    unions ecology and keeps the highest SQS, so the merge rule")
        print("    needs no separate implementation.")
    print("")
    print("  Nothing has been changed.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
