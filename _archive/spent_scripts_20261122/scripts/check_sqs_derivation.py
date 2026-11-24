"""check_sqs_derivation.py -- compare derived SQS against the stored scores.

    python scripts/check_sqs_derivation.py

Reports only. Writes nothing.

Applies Pantheon's published SQS rule (see shared/sqs_derivation.py) to the
current Codex statuses, and compares the result with the score stored in
codex.db.sqs_scores -- which came from Pantheon and reflects whatever status
each species held when Pantheon last assessed it.

Agreement means Pantheon's stored score is still correct. Disagreement means
either a status review has happened since, or the stored score never followed
the rule.
"""
import os
import sys
from collections import Counter, defaultdict

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import sqlite3          # noqa: E402
import paths            # noqa: E402
from shared.sqs_derivation import derive_from_tracks, VALID_SCORES  # noqa: E402

RARITY_TRACKS = ("rarity_modern", "rarity_legacy")
THREAT_TRACKS = ("threat_iucn_2001", "threat_iucn_legacy")
USED = RARITY_TRACKS + THREAT_TRACKS


def main() -> int:
    c = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row

    # statuses for every TVK that has a stored SQS
    tracks_by_tvk = defaultdict(dict)
    q = f"""SELECT s.tvk, s.status_track, s.status_value
            FROM status_summary s
            WHERE s.status_track IN ({','.join('?' * len(USED))})"""
    for r in c.execute(q, USED):
        tracks_by_tvk[r["tvk"]][r["status_track"]] = r["status_value"]

    stored = {r["tvk"]: (r["sqs"], r["source"])
              for r in c.execute("SELECT tvk, sqs, source FROM sqs_scores")}

    agree = 0
    disagree = Counter()          # (stored, derived) -> n
    examples = defaultdict(list)
    invalid_stored = Counter()
    no_status = 0

    for tvk, (sqs, source) in stored.items():
        tracks = tracks_by_tvk.get(tvk)
        if not tracks:
            no_status += 1
            continue
        if sqs not in VALID_SCORES:
            invalid_stored[sqs] += 1
        d = derive_from_tracks(tracks)
        if d == sqs:
            agree += 1
        else:
            disagree[(sqs, d)] += 1
            if len(examples[(sqs, d)]) < 3:
                examples[(sqs, d)].append((tvk, dict(tracks), source))

    total = agree + sum(disagree.values())
    print("\nSQS derivation check")
    print("=" * 66)
    print(f"  stored scores          {len(stored):,}")
    print(f"  with rarity/threat     {total:,}")
    print(f"  no rarity/threat       {no_status:,}  (cannot derive; left alone)")
    print()
    if total:
        print(f"  agree                  {agree:,}  ({agree / total * 100:.1f}%)")
        print(f"  disagree               {sum(disagree.values()):,}"
              f"  ({sum(disagree.values()) / total * 100:.1f}%)")

    if invalid_stored:
        print("\n  stored scores not in the published ladder (0,1,4,8,16,32):")
        for v, n in sorted(invalid_stored.items()):
            print(f"    sqs={v}  n={n}")

    if disagree:
        print("\n  disagreements, most common first")
        print("  stored -> derived      n     effect")
        for (s, d), n in disagree.most_common(15):
            effect = "raises SQI" if d > s else "lowers SQI"
            print(f"    {s:>3} -> {d:<3}      {n:>5}     {effect}")

        print("\n  examples")
        for (s, d), n in disagree.most_common(5):
            print(f"\n    {s} -> {d}:")
            for tvk, tracks, source in examples[(s, d)]:
                bits = ", ".join(f"{k}={v}" for k, v in sorted(tracks.items()))
                print(f"      {tvk}  [{source}]  {bits}")

    print("\n  Nothing has been changed.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
