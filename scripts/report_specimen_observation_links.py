"""report_specimen_observation_links.py -- which Insect Collection specimens are the same find
as an observation (note 36 decision 13, review MAP2, 10 Oct 2026). READ ONLY.

    py -3.14 scripts\\report_specimen_observation_links.py
    py -3.14 scripts\\report_specimen_observation_links.py --csv D:\\somewhere\\links.csv

The link already has a home: specimens.observation_id (empty on every specimen so far). The
Mapping tab's "All records" counts a specimen as its observation through that link, else
through the same TVK + date + grid ref (map_selection._SPECIMEN_OBS). This report lists, per
specimen, the observations it matches so Wil can check them before the link is set
(link_specimens_to_observations.py sets the certain ones).

A specimen matches an observation with the same species TVK, the same date (date_collected =
date) and the same grid ref (case and spaces ignored, the Mapping rule), and -- where both
name somebody -- a collector and recorder naming the same person ('Heeney, W.J.' / 'Wil
Heeney' agree; a recorder field holding a method such as 'Collected' or 'Net' is not
compared; see report_common.same_person).

Tiers, per specimen
  linked       observation_id already set (checked against the rule; mismatches listed)
  certain      exactly one matching observation -- safe to link
  quantity short  exactly one matching observation, but more specimens point at it than its
               quantity (2 specimens, an observation of 1) -- Wil checks
  ambiguous    two or more matching observations -- Wil chooses
  recorder differs  same species, date and grid ref, but collector and recorder disagree
  no match     none
Several specimens may share one observation (two beetles from one record): that is
allowed -- the link is on the specimen -- and counted separately.

CSV: one row per specimen-observation candidate (specimens with no match left out),
scripts\\_oneoff\\specimen_observation_links_<date>.csv.
"""
import argparse
import sys
from collections import Counter, defaultdict

try:
    from scripts import report_common as rc
except ImportError:                       # run as py scripts\<name>.py
    import report_common as rc

import paths  # noqa: E402

TIERS = ("linked", "certain", "quantity short", "ambiguous", "recorder differs", "no match")
HEADER = ["tier", "specimen_id", "specimen_code", "observation_id", "species_name",
          "species_tvk", "date", "specimen_grid_ref", "observation_grid_ref", "collector",
          "recorder", "same_person", "specimen_sex", "observation_sex", "record_type", "project_name", "specimen_site",
          "observation_site", "candidates"]


def load(conn):
    spec = conn.execute(
        "SELECT id, specimen_code, species_name, species_tvk, date_collected, grid_ref, "
        "collector, site_name, observation_id, sex FROM specimens ORDER BY id").fetchall()
    obs = conn.execute(
        "SELECT id, species_tvk, date, grid_ref, recorder, record_type, project_name, "
        "site_name, sex, quantity FROM observations").fetchall()
    return spec, obs


def match(spec, obs) -> dict:
    """{"specimens": [{...per specimen, "tier", "cands": [(obs row, same_person)]}],
        "raw_text": n specimens matching on the exact stored grid-ref text (the review's
        1,337 rule), "rule": n matching on the Mapping rule, recorder not checked}"""
    by_key = defaultdict(list)
    for o in obs:
        if rc.blank(o[1]) or rc.blank(o[2]) or rc.blank(o[3]):
            continue
        by_key[(o[1], o[2], rc.norm_ref(o[3]))].append(o)
    obs_by_id = {o[0]: o for o in obs}
    out = {"specimens": [], "raw_text": 0, "rule": 0}
    for s in spec:
        sid, code, name, tvk, date, ref, collector, site, linked, sex = s
        cands = []
        if not (rc.blank(tvk) or rc.blank(date) or rc.blank(ref)):
            cands = by_key.get((tvk, date, rc.norm_ref(ref)), [])
        if cands:
            out["rule"] += 1
        if any(o[3] == ref for o in cands):
            out["raw_text"] += 1
        scored = []
        for o in cands:
            both = rc.comparable_people(collector, o[4])
            scored.append((o, rc.same_person(collector, o[4]) if both else None))
        ok = [c for c in scored if c[1] is not False]
        if not rc.blank(linked):
            tier = "linked"
            o = obs_by_id.get(int(linked))
            scored = [(o, None)] if o else []
            agrees = any(c[0][0] == int(linked) for c in ok)
        elif len(ok) == 1:
            tier, agrees = "certain", None
        elif len(ok) > 1:
            tier, agrees = "ambiguous", None
        elif scored:
            tier, agrees = "recorder differs", None
        else:
            tier, agrees = "no match", None
        out["specimens"].append({"id": sid, "code": code, "name": name, "tvk": tvk,
                                 "date": date, "ref": ref, "collector": collector,
                                 "site": site, "sex": sex, "tier": tier, "cands": scored,
                                 "ok": ok, "link_agrees": agrees})
    per_obs = Counter(s["ok"][0][0][0] for s in out["specimens"] if s["tier"] == "certain")
    for s in out["specimens"]:
        if s["tier"] == "certain":
            o = s["ok"][0][0]
            q = o[9]
            if per_obs[o[0]] > 1 and isinstance(q, int) and q < per_obs[o[0]]:
                s["tier"] = "quantity short"
    return out


def certain_links(found) -> list:
    """[(specimen id, observation id)] for the certain tier -- what the link script writes."""
    return [(s["id"], s["ok"][0][0][0]) for s in found["specimens"] if s["tier"] == "certain"]


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
        print(f"    {t:<18}{tiers[t]:>7,}")
    certain = [s for s in sp if s["tier"] == "certain"]
    per_obs = Counter(s["ok"][0][0][0] for s in certain)
    shared = sum(1 for n in per_obs.values() if n > 1)
    short = Counter(s["ok"][0][0][0] for s in sp if s["tier"] == "quantity short")
    print(f"  certain: {len(certain):,} specimens onto {len(per_obs):,} observations "
          f"({shared:,} observations hold 2+ specimens, within their quantity)")
    kinds = Counter((s["ok"][0][0][5] or "?") for s in certain)
    print("    by the observation's record type: "
          + ", ".join(f"{k} {v:,}" for k, v in kinds.most_common()))
    print(f"  quantity short: {tiers['quantity short']:,} specimens onto {len(short):,} "
          f"observations whose quantity is below their number of specimens")
    amb = [s for s in sp if s["tier"] == "ambiguous"]
    if amb:
        print(f"  ambiguous: {len(amb):,} specimens, "
              f"{sum(len(s['ok']) for s in amb):,} candidate observations")
    bad = [s for s in sp if s["tier"] == "linked" and not s["link_agrees"]]
    if tiers["linked"]:
        print(f"  already linked that the rule does not support: {len(bad):,}")
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
