"""check_summary_loss.py -- size the status_summary collapse.

    python scripts/check_summary_loss.py

Why
---
build_codex_db.py line ~607 collapses designations with:

    key = (track, detail or "")

Every abbreviation that maps to the same (track, detail) pair competes for a
single slot, and the winner is decided by ABBR_PRIORITY. All five priority
jurisdictions map to detail=None and score the default 10, so the first one
encountered wins and the rest are discarded.

This script measures how many designations are lost that way, per track, and
checks whether any track other than 'priority' has the same problem.

Read-only. Writes nothing.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import sqlite3  # noqa: E402
import paths    # noqa: E402

sys.path.insert(0, os.path.join(_ROOT, "scripts"))
from build_codex_db import DESIG_TO_TRACK, get_desig_priority  # noqa: E402


def main():
    c = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)

    print("")
    print("status_summary collapse -- how much is being dropped")
    print("=" * 74)

    # ------------------------------------------------------------------
    # 1. Replay the collapse against designations, without writing.
    # ------------------------------------------------------------------
    rows = c.execute(
        "SELECT tvk, designation_abbreviation FROM designations").fetchall()

    routed = 0
    unrouted = 0
    kept = set()          # (tvk, track, detail) that would survive
    per_track_in = {}     # track -> routed designation count
    contested = {}        # (track, detail) -> count of collisions
    best = {}             # (tvk, track, detail) -> priority

    for tvk, abbr in rows:
        m = DESIG_TO_TRACK.get(abbr)
        if not m:
            unrouted += 1
            continue
        routed += 1
        track, _value, detail = m
        per_track_in[track] = per_track_in.get(track, 0) + 1
        key = (tvk, track, detail or "")
        prio = get_desig_priority(abbr)
        if key in best:
            contested[(track, detail or "")] = \
                contested.get((track, detail or ""), 0) + 1
        if key not in best or prio > best[key]:
            best[key] = prio
        kept.add(key)

    print(f"  designation rows:            {len(rows):,}")
    print(f"    routed to a track:         {routed:,}")
    print(f"    unrouted (no mapping):     {unrouted:,}")
    print(f"  surviving summary rows:      {len(kept):,}")
    print(f"  LOST to collapse:            {routed - len(kept):,}")

    # ------------------------------------------------------------------
    # 2. Per-track: in vs out.
    # ------------------------------------------------------------------
    per_track_out = {}
    for _tvk, track, _detail in kept:
        per_track_out[track] = per_track_out.get(track, 0) + 1

    print("")
    print("  per track:")
    print(f"    {'track':22} {'routed':>8} {'kept':>8} {'lost':>8}")
    for track in sorted(per_track_in, key=lambda t: -(per_track_in[t] - per_track_out.get(t, 0))):
        i = per_track_in[track]
        o = per_track_out.get(track, 0)
        flag = "   <-- COLLAPSING" if i - o else ""
        print(f"    {track:22} {i:>8,} {o:>8,} {i-o:>8,}{flag}")

    # ------------------------------------------------------------------
    # 3. Which (track, detail) slots are contested at all?
    # ------------------------------------------------------------------
    if contested:
        print("")
        print("  contested (track, detail) slots -- more than one designation competing:")
        for (track, detail), n in sorted(contested.items(), key=lambda kv: -kv[1]):
            print(f"    {track:22} detail={detail!r:34} {n:>6,} collisions")

    # ------------------------------------------------------------------
    # 4. Priority jurisdictions: true totals vs what survived.
    # ------------------------------------------------------------------
    print("")
    print("  priority jurisdictions -- true count vs what reached status_summary:")
    print(f"    {'jurisdiction':32} {'in designations':>16} {'in summary':>12}")
    for abbr, (track, value, _d) in DESIG_TO_TRACK.items():
        if track != "priority":
            continue
        true_n = c.execute(
            "SELECT COUNT(DISTINCT tvk) FROM designations "
            "WHERE designation_abbreviation=?", (abbr,)).fetchone()[0]
        got_n = c.execute(
            "SELECT COUNT(*) FROM status_summary "
            "WHERE status_track='priority' AND status_value=?",
            (value,)).fetchone()[0]
        loss = "" if true_n == got_n else f"   lost {true_n - got_n:,}"
        print(f"    {value:32} {true_n:>16,} {got_n:>12,}{loss}")

    print("")
    print("  Nothing has been changed.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
