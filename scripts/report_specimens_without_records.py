"""report_specimens_without_records.py -- specimens with no field record, sorted into what
could become a record (11 Oct 2026, round 4). READ ONLY.

    py -3.14 scripts\\report_specimens_without_records.py
    py -3.14 scripts\\report_specimens_without_records.py --csv D:\\somewhere\\spec.csv

Takes the specimens shared/specimen_links.py puts in "no match" or "checked: no field
record" and sorts them (rules in scripts/specimen_breakdown.py):
  1  Wil's, complete -> would become a new observation (one per species + date + grid ref,
     quantity = number of specimens); split Commercial (project) / Personal / unknown
  2  Wil's, near miss -> an observation of the same species close in time and place: link?
  3  Wil's, details missing (what is missing)
  4  someone else's -> contributed_observations; by collector, likely historic or recent
  5  already recorded elsewhere (recording_scheme / contributed_observations) -- a flag
Works whether or not specimens.no_field_record_checked exists. Nothing is created.

CSV: one row per specimen, scripts\\_oneoff\\specimens_without_records_<date>.csv.
"""
import argparse
import os
import sqlite3
import sys
from collections import Counter, defaultdict

try:
    from scripts import report_common as rc
    from scripts import specimen_breakdown as sb
except ImportError:                       # run as py scripts\<name>.py
    import report_common as rc
    import specimen_breakdown as sb

import paths  # noqa: E402
from shared.specimen_links import load, match  # noqa: E402

HEADER = ["group", "sub_group", "reason", "tier", "specimen_id", "specimen_code",
          "species_name", "species_tvk", "date", "grid_ref", "site", "collector",
          "determiner", "record_key", "record_quantity", "record_type", "project_name",
          "client", "embargo_status", "embargo_until", "recorder", "record_determiner",
          "near_observations", "elsewhere"]
GROUPS = {1: "Wil's, complete: would become a record", 2: "Wil's, near miss: link?",
          3: "Wil's, details missing", 4: "someone else's: contributed"}
OBS_SQL = ("SELECT id, species_tvk, species_name, date, grid_ref, recorder, site_name, "
           "record_type, project_name, client, embargo_status, embargo_until FROM observations")
OTHER_SQL = "SELECT id, species_tvk, species_name, date, grid_ref, recorder, site_name FROM {}"


def _rows(conn, sql):
    cur = conn.execute(sql)
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur]


def _table(conn, name) -> bool:
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                             (name,)).fetchone())


def rollup_map(uksi_path, tvks):
    """{tvk: species tvk} via shared/record_kinds.species_tvks; {} without UKSI."""
    if not uksi_path or not os.path.exists(uksi_path):
        return {}
    from shared.record_kinds import species_tvks
    u = rc.connect_ro(uksi_path)
    try:
        return species_tvks(u, tvks)
    except sqlite3.Error:
        return {}
    finally:
        u.close()


def gather(conn, uksi_path=None) -> dict:
    """Everything the report prints: {"specs": [...], "records": {key: proposed}, ...}."""
    spec_rows, obs_rows = load(conn)
    found = match(spec_rows, obs_rows)
    extra = {r[0]: r[1:] for r in conn.execute(
        "SELECT id, determiner FROM specimens")}
    todo = [s for s in found["specimens"] if s["tier"] in ("no match", "checked: no field record")]
    obs = _rows(conn, OBS_SQL)
    others = {t: _rows(conn, OTHER_SQL.format(t)) for t in ("recording_scheme",
              "contributed_observations") if _table(conn, t)}
    tvks = {s["tvk"] for s in todo} | {r["species_tvk"] for r in obs}
    for rows in others.values():
        tvks |= {r["species_tvk"] for r in rows}
    roll = rollup_map(uksi_path, tvks)
    O = sb.Records(obs, roll)
    E = {t: sb.Records(rows, roll) for t, rows in others.items()}
    rule = sb.CommercialRule(O)
    specs = []
    for s in todo:
        s = dict(s, determiner=extra.get(s["id"], (None,))[0])
        s["own"] = sb.owner(s["collector"], s["determiner"])
        s["miss"] = sb.missing(s["tvk"], s["date"], s["ref"])
        s["sub"] = s["project"] = s["reason"] = ""
        s["near"], s["elsewhere"] = [], []
        if not s["miss"]:
            for t, R in E.items():
                short = "scheme" if t == "recording_scheme" else "contributed"
                for r in R.exact(s):
                    s["elsewhere"].append((short, "exact", r, 0, 0.0))
                for r, dd, d in R.near(s):
                    s["elsewhere"].append((short, "close", r, dd, d))
        if s["own"] == "other":
            s["group"] = 4
            s["sub"] = ("likely historic" if (s["date"] or "9999") < sb.HISTORIC_BEFORE
                        else "recent")
            s["reason"] = "; ".join(s["miss"]) or "complete"
        elif s["miss"]:
            s["group"], s["reason"] = 3, "; ".join(s["miss"])
        else:
            near = [(r, dd, d) for r, dd, d in O.near(s)
                    if sb.person_ok(s["collector"], r.get("recorder"))]
            same_place = []
            if s["tier"] == "checked: no field record":
                near = []                  # Wil has looked: there is none
            elif not near:
                same_place = [(r, 0, d) for r, d in
                              O.by_date[s["date"]].near(sb.centre(s["ref"]), 1)
                              if sb.norm_ref(r.get("grid_ref")) == sb.norm_ref(s["ref"])
                              and sb.genus(r.get("species_name")) == sb.genus(s["name"])
                              and sb.person_ok(s["collector"], r.get("recorder"))]
            if near:
                s["group"], s["near"] = 2, near
                s["sub"], s["reason"] = near_kind(s, near)
            else:
                s["group"] = 1
                s["sub"], s["project"], s["reason"] = rule.classify(s)
                if same_place:             # usually a second species, not a misidentification
                    s["near"] = same_place
                    s["genus_note"] = True
                    s["reason"] += ("; NB an observation of another species of the genus the "
                                    "same day at the same grid ref (name differs?)")
        specs.append(s)
    g1 = [s for s in specs if s["group"] == 1]
    g4 = [s for s in specs if s["group"] == 4 and not s["miss"]]
    return {"specs": specs, "records": sb.proposed_records(g1, roll),
            "contributed": sb.proposed_records(g4, roll), "rule": rule, "roll": roll,
            "tiers": Counter(s["tier"] for s in found["specimens"]),
            "has_uksi": bool(roll), "tables": sorted(others)}


def basis(reason) -> str:
    """The short why of a group 1 sub-group: same visit / season / site name / ..."""
    r = reason or ""
    for k, lab in (("same visit", "same visit"), ("same day", "same day, mixed"),
                   ("presumed", "other dates nearby"), ("no field records", "no records nearby"),
                   ("site name", "site name"), ("near more", "season, several projects"),
                   ("survey record within", "season"), ("no records that day", "other dates nearby")):
        if r.startswith(k) or (k == "survey record within" and k in r):
            return lab
    return r[:30]


def near_kind(s, near):
    """(sub-group, reason) for the nearest candidate."""
    r, dd, d = near[0]
    a, b = sb.gridref_to_en(sb.norm_ref(s["ref"])), sb.gridref_to_en(sb.norm_ref(r.get("grid_ref")))
    nested = bool(a and b) and (sb.inside(a, b) or sb.inside(b, a))
    if dd == 0 and nested:
        return ("same day, same place at another grid-ref precision",
                f"observation {r['id']} the same day, grid ref {r.get('grid_ref')} "
                f"inside / around {s['ref']}: almost certainly the same find -- link")
    if dd == 0:
        where = f"{d:.0f} m away" if d is not None else "at the same site"
        return ("same day, nearby", f"observation {r['id']} the same day, {where}: link?")
    return (f"within {sb.NEAR_DAYS} days",
            f"observation {r['id']} {dd} day(s) apart, "
            + (f"{d:.0f} m away" if d is not None else "same site") + ": date slip? link?")


def _obs_text(r, dd, d):
    where = f"{d / 1000:.1f} km" if d is not None else "same site"
    return (f"{r['id']} {r.get('species_name') or ''} {r.get('date')} {r.get('grid_ref')} "
            f"({dd} d, {where}, {r.get('recorder') or ''})")


def csv_rows(g):
    for s in sorted(g["specs"], key=lambda s: (s["group"], s["sub"], s["id"])):
        key = rec = None
        if s["group"] == 1:
            key = sb.record_key(s, g["roll"])
            rec = g["records"][key]
        elif s["group"] == 4 and not s["miss"]:
            key = sb.record_key(s, g["roll"])
            rec = g["contributed"][key]
        terms = g["rule"].terms.get(rec["project"], {}) if rec and s["group"] == 1 and \
            rec["sub"] == "Commercial" else {}
        rtype = {1: rec["sub"] if rec else "", 4: "contributed"}.get(s["group"], "")
        yield [s["group"], s["sub"], s["reason"], s["tier"], s["id"], s["code"], s["name"],
               s["tvk"], s["date"], s["ref"], s["site"], s["collector"], s["determiner"],
               key, rec["quantity"] if rec else "", rtype,
               rec["project"] if rec and s["group"] == 1 else "", terms.get("client"),
               terms.get("embargo_status"), terms.get("embargo_until"),
               rec["recorder"] if rec else "", rec["determiner"] if rec else "",
               " | ".join(_obs_text(*n) for n in s["near"][:5]),
               " | ".join(f"{t} {k} {r['id']} {r.get('date')} {r.get('grid_ref')} "
                          f"{r.get('recorder') or ''}" for t, k, r, _dd, _d in s["elsewhere"][:5])]


def report(g, examples=3) -> None:
    sp = g["specs"]
    print(f"  specimens with no field record: {len(sp):,} "
          f"(no match {g['tiers']['no match']:,}, checked: no field record "
          f"{g['tiers']['checked: no field record']:,}); species roll-up via UKSI: "
          f"{'yes' if g['has_uksi'] else 'no (exact TVK only)'}")
    print(f"  rules: near = same species, within {sb.NEAR_DAYS} days and within {sb.NEAR_M} m "
          f"(grid-square centres) or the same site name; same visit = records that day within "
          f"{sb.VISIT_M} m; season = a Commercial survey record within {sb.SEASON_DAYS} days and "
          f"{sb.VISIT_M} m; historic = collected before {sb.HISTORIC_BEFORE[:4]}")
    who = Counter((s["collector"], s["own"]) for s in sp)
    print("  collectors (Wil's = names him alone or with others):")
    for (c, o), n in who.most_common():
        print(f"    {n:>6,}  {'Wil  ' if o == 'wil' else 'other'}  {c!r}")
    for gid, title in GROUPS.items():
        ss = [s for s in sp if s["group"] == gid]
        print("")
        print(f"  {gid}. {title}: {len(ss):,} specimens")
        subs = Counter((s["sub"], s["project"], basis(s["reason"])) if gid == 1
                       else s["sub"] or s["reason"] for s in ss)
        for k, n in subs.most_common(20):
            lab = f"{k[0]}{' - ' + k[1] if k[1] else ''}  [{k[2]}]" if gid == 1 else k
            print(f"      {n:>6,}  {lab}")
        if gid == 1:
            _records_summary(g, ss)
        if gid == 4:
            _collectors(ss, g["roll"])
        for s in ss[:examples]:
            print(f"        e.g. specimen {s['id']} {s['name']} {s['date']} {s['ref']} "
                  f"{s['site'] or ''} [{s['collector']}] -- {s['reason']}")
            for n in s["near"][:2]:
                print(f"             near: observation {_obs_text(*n)}")
    print("")
    el = [s for s in sp if s["elsewhere"]]
    print(f"  5. already recorded elsewhere ({', '.join(g['tables'])}): {len(el):,} specimens")
    tab = Counter((s["group"], "exact" if any(e[1] == "exact" for e in s["elsewhere"]) else "close",
                   "/".join(sorted({e[0] for e in s["elsewhere"]}))) for s in el)
    for (gid, k, t), n in sorted(tab.items()):
        print(f"      {n:>6,}  group {gid}, {k}, in {t}")
    for s in el[:examples]:
        t, k, r, _dd, _d = s["elsewhere"][0]
        print(f"        e.g. specimen {s['id']} {s['name']} {s['date']} {s['ref']} -> {t} {k} "
              f"{r['id']} {r.get('date')} {r.get('grid_ref')} {r.get('recorder') or ''}")


def _records_summary(g, ss):
    recs = g["records"]
    by = defaultdict(lambda: [0, 0])
    for r in recs.values():
        lab = f"{r['sub']}{' - ' + r['project'] if r['project'] else ''}"
        by[lab][0] += 1
        by[lab][1] += r["quantity"]
    print(f"    -> {len(recs):,} new observation records covering {len(ss):,} specimens "
          f"({sum(1 for r in recs.values() if r['quantity'] > 1):,} with quantity 2+, "
          f"largest {max((r['quantity'] for r in recs.values()), default=0)})")
    for lab, (n, q) in sorted(by.items(), key=lambda x: -x[1][0]):
        t = g["rule"].terms.get(lab.split(" - ", 1)[1], {}) if " - " in lab else {}
        emb = (f"; embargo {t.get('embargo_status')} {t.get('embargo_until') or ''}"
               f"{' (project mixed)' if t.get('mixed_embargo') else ''}") if t else ""
        print(f"         {n:>6,} records / {q:,} specimens  {lab}{emb}")
    conf = [r for r in recs.values() if r["conflict"]]
    if conf:
        print(f"    {len(conf):,} records whose specimens disagree on Personal/Commercial "
              "(the most common is proposed; see CSV)")
    gn = sum(1 for s in ss if s.get("genus_note"))
    if gn:
        print(f"    {gn:,} of these have an observation of another species of the same genus that "
              "day at the same grid ref (mostly a second species; a renamed or re-identified "
              "find is possible -- 'NB' in the reason)")
    pers = Counter(s["site"] for s in ss if s["sub"] == "Personal")
    print("    Personal, top sites (check none is a survey): "
          + ", ".join(f"{k} {n}" for k, n in pers.most_common(12)))
    unk = Counter((s["site"], (s["date"] or "")[:7]) for s in ss if s["sub"] == "unknown")
    print("    unknown, top site / month (a survey not yet entered?): "
          + ", ".join(f"{k[0]} {k[1]} {n}" for k, n in unk.most_common(12)))


def _collectors(ss, roll):
    by = defaultdict(list)
    for s in ss:
        by[s["collector"]].append(s)
    print("    by collector (dates, specimens, complete, would-be contributed records):")
    for c, xs in sorted(by.items(), key=lambda x: -len(x[1])):
        ds = sorted(x["date"] for x in xs if x["date"])
        comp = [x for x in xs if not x["miss"]]
        keys = {sb.record_key(x, roll) for x in comp}
        hist = sum(1 for x in xs if x["sub"] == "likely historic")
        print(f"      {c!r}: {ds[0] if ds else '?'} to {ds[-1] if ds else '?'}, {len(xs):,} "
              f"specimens, {len(comp):,} complete, {len(keys):,} records"
              f"{f', {hist} likely historic' if hist else ''}; determiners: "
              + ", ".join(sorted({str(x['determiner']) for x in xs})))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--csv", default=rc.default_csv("specimens_without_records"))
    ap.add_argument("--db", default=str(paths.OBSERVATUM_DB), help=argparse.SUPPRESS)
    ap.add_argument("--uksi", default=str(paths.UKSI_DB), help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    print("")
    print("Specimens with no field record: what could become a record (READ ONLY)")
    print("=" * 74)
    print(f"  observatum.db: {a.db}")
    conn = rc.connect_ro(a.db)
    try:
        g = gather(conn, a.uksi)
    finally:
        conn.close()
    report(g)
    n = rc.write_csv(a.csv, HEADER, csv_rows(g))
    print("")
    print(f"  CSV: {n:,} specimens -> {a.csv}")
    print("")
    print("READ ONLY. Nothing has been changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
