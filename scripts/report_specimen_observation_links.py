"""report_specimen_observation_links.py -- which Insect Collection specimens are the same find
as an observation (note 36 decision 13, review MAP2, 10 Oct 2026). READ ONLY.

    py -3.14 scripts\\report_specimen_observation_links.py
    py -3.14 scripts\\report_specimen_observation_links.py --csv D:\\somewhere\\links.csv

The link has a home: specimens.observation_id. The Mapping tab's "All records" counts a
specimen as its observation through that link, else through the same TVK + date + grid ref
(map_selection._SPECIMEN_OBS). This report lists, per specimen, the observations it matches
so Wil can check them before the link is set (link_specimens_to_observations.py sets the
certain ones; the Edit Specimen dialog's "Field record" box sets, changes or clears one by
hand, or marks "Checked: no field record exists"; unlink_specimens_from_observations.py
undoes links in bulk).

The rule and the tiers are in shared/specimen_links.py (one home, used by the dialog too):
  linked                    observation_id set (those the rule does not support are listed)
  checked: no field record  Wil ticked "Checked: no field record exists"
  certain                   exactly one matching observation -- safe to link
  quantity short            exactly one, but more specimens on it than its quantity
  ambiguous                 two or more matching observations -- Wil chooses
  recorder differs          same species, date and grid ref; collector and recorder disagree
  no match                  none
The first two are the work done; quantity short, ambiguous and recorder differs are the work
still to do ("Progress" at the end). Several specimens may share one observation (two
beetles from one record): that is allowed -- the link is on the specimen.

CSV: one row per specimen-observation candidate (specimens with no match left out),
scripts\\_oneoff\\specimen_observation_links_<date>.csv.
"""
import argparse
import sys
from collections import Counter

try:
    from scripts import report_common as rc
except ImportError:                       # run as py scripts\<name>.py
    import report_common as rc

import paths  # noqa: E402
# the matching itself lives in shared/specimen_links.py (the Edit Specimen dialog uses it);
# links.load / links.match / links.certain_links / links.TIERS keep working for the scripts
from shared.specimen_links import (  # noqa: E402,F401
    TIERS, TO_WORK_THROUGH, certain_links, load, match)

HEADER = ["tier", "specimen_id", "specimen_code", "observation_id", "species_name",
          "species_tvk", "date", "specimen_grid_ref", "observation_grid_ref", "collector",
          "recorder", "same_person", "specimen_sex", "observation_sex", "record_type", "project_name", "specimen_site",
          "observation_site", "candidates"]


def csv_rows(found):
    for s in found["specimens"]:
        for o, same in s["cands"]:
            yield [s["tier"], s["id"], s["code"], o[0], s["name"], s["tvk"], s["date"], s["ref"],
                   o[3], s["collector"], o[4], {True: "yes", False: "no", None: ""}[same],
                   s["sex"], o[8],
                   o[5], o[6], s["site"], o[7], len(s["cands"])]


def report(found) -> None:
    sp = found["specimens"]
    tiers = Counter(s["tier"] for s in sp)
    print(f"  specimens: {len(sp):,}")
    for t in TIERS:
        print(f"    {t:<26}{tiers[t]:>7,}")
    certain = [s for s in sp if s["tier"] == "certain"]
    per_obs = Counter(s["ok"][0][0][0] for s in certain)
    shared = sum(1 for n in per_obs.values() if n > 1)
    short = Counter(s["ok"][0][0][0] for s in sp if s["tier"] == "quantity short")
    print(f"  certain: {len(certain):,} specimens onto {len(per_obs):,} observations "
          f"({shared:,} observations hold 2+ specimens, within their quantity)")
    kinds = Counter((s["ok"][0][0][5] or "?") for s in certain)
    if kinds:
        print("    by the observation's record type: "
              + ", ".join(f"{k} {v:,}" for k, v in kinds.most_common()))
    print(f"  quantity short: {tiers['quantity short']:,} specimens onto {len(short):,} "
          f"observations whose quantity is below their number of specimens")
    amb = [s for s in sp if s["tier"] == "ambiguous"]
    if amb:
        print(f"  ambiguous: {len(amb):,} specimens, "
              f"{sum(len(s['ok']) for s in amb):,} candidate observations")
    diff = [s for s in sp if s["tier"] == "recorder differs"]
    if diff:
        pairs = Counter((s["collector"], s["cands"][0][0][4]) for s in diff)
        print("  recorder differs (collector / recorder), most common:")
        for (c, r), n in pairs.most_common(6):
            print(f"    {n:>5,}  '{c}' / '{r}'")
    print("")
    print("  Reconciling with the 9 Oct review (MAP2: 'All records' counted 1,337 specimens again")
    print("  on top of their observation):")
    print(f"    specimens with an observation of the same TVK, date and grid ref, exact text: "
          f"{found['raw_text']:,}")
    print(f"    the same with case and spaces in the grid ref ignored (Mapping's rule now):  "
          f"{found['rule']:,}")
    print(f"    of those, collector and recorder agree or one is blank (certain, quantity short, ambiguous): "
          f"{tiers['certain'] + tiers['quantity short'] + tiers['ambiguous']:,}; disagree: {tiers['recorder differs']:,}")
    progress(found)


def progress(found) -> None:
    """The work done (linked, checked) and still to do, with the links the rule does not
    support listed so a hand-made link can be checked."""
    sp = found["specimens"]
    tiers = Counter(s["tier"] for s in sp)
    linked = [s for s in sp if s["tier"] == "linked"]
    off_rule = [s for s in linked if not s["link_agrees"]]
    print("")
    print("  Progress")
    print(f"    linked to a field record:       {len(linked):>7,}"
          f"  ({len(linked) - len(off_rule):,} the rule agrees with, {len(off_rule):,} chosen by hand"
          " or not supported by the rule)")
    print(f"    checked, no field record:       {tiers['checked: no field record']:>7,}")
    print(f"    certain, ready for the link script: {tiers['certain']:>3,}")
    todo = sum(tiers[t] for t in TO_WORK_THROUGH)
    print(f"    still to decide:                {todo:>7,}  ("
          + ", ".join(f"{t} {tiers[t]:,}" for t in TO_WORK_THROUGH) + ")")
    print(f"    no matching observation:        {tiers['no match']:>7,}")
    for s in off_rule[:10]:
        o = s["cands"][0][0] if s["cands"] else None
        what = (f"observation {o[0]} ({o[2]}, {o[3]})" if o else "an observation that no longer exists")
        print(f"      specimen {s['id']} {str(s['name'] or '')[:30]} {s['date']} {s['ref']} -> {what}")
    if len(off_rule) > 10:
        print(f"      ... and {len(off_rule) - 10:,} more (tier 'linked' in the CSV)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--csv", default=rc.default_csv("specimen_observation_links"))
    ap.add_argument("--db", default=str(paths.OBSERVATUM_DB), help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    print("")
    print("Specimens that are the same find as an observation (READ ONLY)")
    print("=" * 74)
    print(f"  observatum.db: {a.db}")
    conn = rc.connect_ro(a.db)
    try:
        found = match(*load(conn))
    finally:
        conn.close()
    report(found)
    n = rc.write_csv(a.csv, HEADER, csv_rows(found))
    print("")
    print(f"  CSV: {n:,} specimen-observation rows -> {a.csv}")
    print("")
    print("READ ONLY. Nothing has been changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
