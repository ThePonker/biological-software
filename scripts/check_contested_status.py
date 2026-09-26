"""check_contested_status.py -- where two designations compete for one slot.

    python scripts/check_contested_status.py

Read-only. Writes nothing.

Background
----------
status_summary holds one row per (tvk, status_track, status_detail). Where a
species has two designations that map to the same slot, build_codex_db.py keeps
one and drops the other, choosing by ABBR_PRIORITY. But all modern Red List
codes score 100, so ties are common -- and a tie is resolved by whichever row
the database returned first, not by any rule.

Nothing looks at date_designated. So where a newer review superseded an older
one, the stored status may be either.

This lists every contested slot with all competing designations, their dates and
their sources, so the "most recent wins" rule can be checked against real cases
before it is encoded.

Collapses that are CORRECT are still listed -- a species does have one GB Red
List status. The question is only which one is kept.
"""
import os
import sys
from collections import defaultdict

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "scripts"))

import sqlite3   # noqa: E402
import paths     # noqa: E402
from build_codex_db import DESIG_TO_TRACK, get_desig_priority  # noqa: E402


def main():
    c = sqlite3.connect(f"file:{paths.CODEX_DB}?mode=ro", uri=True)

    print("")
    print("Contested status slots -- two designations, one row")
    print("=" * 78)

    rows = c.execute(
        """SELECT tvk, species_name, taxon_group, category,
                  designation_abbreviation, designation, source,
                  date_designated, iucn_version
           FROM designations ORDER BY tvk""").fetchall()

    slots = defaultdict(list)
    for (tvk, name, group, cat, abbr, desig, source, date_d, iucn) in rows:
        m = DESIG_TO_TRACK.get(abbr)
        if not m:
            continue
        track, value, detail = m
        slots[(tvk, track, detail or "")].append(
            dict(name=name, group=group, cat=cat, abbr=abbr, value=value,
                 source=source, date=date_d or "", iucn=iucn or "",
                 prio=get_desig_priority(abbr)))

    contested = {k: v for k, v in slots.items() if len(v) > 1}

    # Only the slots where the competitors disagree on the VALUE matter --
    # two rows both saying "VU" collapse harmlessly.
    disagreeing = {k: v for k, v in contested.items()
                   if len({e["value"] for e in v}) > 1}

    by_track = defaultdict(int)
    for (_t, track, _d) in disagreeing:
        by_track[track] += 1

    print(f"  contested slots (more than one designation):  {len(contested):,}")
    print(f"  of those, competitors DISAGREE on the value:  {len(disagreeing):,}")
    print("")
    print("  disagreements by track:")
    for track, n in sorted(by_track.items(), key=lambda kv: -kv[1]):
        print(f"    {track:24} {n:>5}")

    # ------------------------------------------------------------------
    # How would a date rule differ from what is stored now?
    # ------------------------------------------------------------------
    print("")
    print("  WOULD 'MOST RECENT WINS' CHANGE THE ANSWER?")
    print("  " + "-" * 74)

    changed, undated, agreed = [], [], 0
    for (tvk, track, detail), entries in disagreeing.items():
        stored = c.execute(
            """SELECT status_value FROM status_summary
               WHERE tvk=? AND status_track=?
                 AND COALESCE(status_detail,'')=?""",
            (tvk, track, detail)).fetchone()
        if not stored:
            continue
        stored = stored[0]

        dated = [e for e in entries if e["date"]]
        if len(dated) < len(entries):
            undated.append((tvk, track, entries, stored))
            continue
        newest = max(dated, key=lambda e: e["date"])
        if newest["value"] != stored:
            changed.append((tvk, track, entries, stored, newest))
        else:
            agreed += 1

    print(f"    already the most recent:        {agreed:>5}")
    print(f"    WOULD CHANGE:                   {len(changed):>5}")
    print(f"    cannot tell (missing dates):    {len(undated):>5}")

    # ------------------------------------------------------------------
    # The cases that would change -- these are the ones to eyeball.
    # ------------------------------------------------------------------
    if changed:
        print("")
        print("  CASES THAT WOULD CHANGE -- check these by eye")
        print("  " + "-" * 74)
        for tvk, track, entries, stored, newest in changed[:40]:
            e0 = entries[0]
            print("")
            print(f"    {e0['name']}  ({e0['group']})")
            print(f"    track: {track}    stored now: {stored}"
                  f"    would become: {newest['value']}")
            for e in sorted(entries, key=lambda x: x["date"]):
                mark = "  <-- newest" if e is newest else ""
                star = " *" if e["value"] == stored else "  "
                print(f"      {star}{e['date'][:10]:12} {e['value']:>6}  "
                      f"{e['abbr'][:28]:28} {str(e['source'])[:34]}{mark}")
        if len(changed) > 40:
            print(f"\n    ... and {len(changed) - 40} more")

    if undated:
        print("")
        print("  UNDATED CONTESTS -- no date to rank by; a fallback rule is needed")
        print("  " + "-" * 74)
        for tvk, track, entries, stored in undated[:15]:
            e0 = entries[0]
            vals = ", ".join(f"{e['value']}({e['abbr'][:18]})" for e in entries)
            print(f"    {str(e0['name'])[:34]:34} {track:20} stored={stored:>6}"
                  f"   [{vals}]")
        if len(undated) > 15:
            print(f"    ... and {len(undated) - 15} more")

    print("")
    print("  Nothing has been changed.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
