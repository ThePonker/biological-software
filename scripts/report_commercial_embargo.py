"""report_commercial_embargo.py -- commercial observations by project: embargoed or not
(note 36 decision 14, review OBS-12, 10 Oct 2026). READ ONLY: Wil decides project by project;
any change afterwards is a separate dry-run + backup script.

    py -3.14 scripts\\report_commercial_embargo.py
    py -3.14 scripts\\report_commercial_embargo.py --today 2026-10-10

Commercial = record_type starting 'comm' (the suite's rule, map_selection._COMMERCIAL).
Embargoed = embargo_status 'Active' and embargo_until after today -- the rule the iRecord
export and Mapping use. Anything else is "not embargoed", split by why: no embargo set, an
embargo whose date has passed, or some other status.

Elmley is marked "unembargoed by choice" (Wil, note 36): it is listed, not a fault.
A project with both embargoed and un-embargoed records is marked "mixed".
CSV: scripts\\_oneoff\\commercial_embargo_<date>.csv.
"""
import argparse
import datetime as _dt
import sys
from collections import defaultdict

try:
    from scripts import report_common as rc
except ImportError:                       # run as py scripts\<name>.py
    import report_common as rc

import paths  # noqa: E402

BY_CHOICE = ("elmley",)                   # project names (lower case, contains) Wil left open
REVIEW_FIGURE = 1226                      # un-embargoed commercial records, review OBS-12
HEADER = ["project", "client", "records", "embargoed", "not_embargoed", "no_embargo_set",
          "embargo_expired", "other_status", "embargo_until", "earliest_date", "latest_date",
          "note", "by_year"]


def classify(status, until, today: str) -> str:
    """embargoed / none / expired / other, by the iRecord export's rule."""
    st = (status or "").strip()
    u = (until or "").strip()
    if st == "Active" and u > today:
        return "embargoed"
    if not st and not u:
        return "none"
    if st == "Active":
        return "expired"
    return "other"


def gather(conn, today: str) -> list:
    rows = conn.execute(
        "SELECT project_name, client, embargo_status, embargo_until, date FROM observations "
        "WHERE LOWER(COALESCE(record_type, '')) LIKE 'comm%'").fetchall()
    by = defaultdict(lambda: {"records": 0, "embargoed": 0, "none": 0, "expired": 0, "other": 0,
                              "until": set(), "dates": [], "stored": set(),
                              "years": defaultdict(lambda: [0, 0])})
    for proj, client, st, until, date in rows:
        key = ((proj or "").strip() or "(no project)", (client or "").strip() or "(no client)")
        p = by[key]
        p["records"] += 1
        kind = classify(st, until, today)
        p[kind] += 1
        p["years"][(date or "")[:4] or "undated"][0 if kind == "embargoed" else 1] += 1
        if until:
            p["until"].add(until)
        if date:
            p["dates"].append(date)
        p["stored"].add(proj)
    out = []
    for (proj, client), p in sorted(by.items(), key=lambda kv: kv[0][0].lower()):
        notes = []
        if any(w in proj.lower() for w in BY_CHOICE):
            notes.append("unembargoed by choice")
        not_emb = p["records"] - p["embargoed"]
        if p["embargoed"] and not_emb:
            notes.append("mixed")
        if any(s is not None and s != s.strip() for s in p["stored"]):
            notes.append("name stored with spaces")
        out.append({"project": proj, "client": client, "records": p["records"],
                    "embargoed": p["embargoed"], "not": not_emb, "none": p["none"],
                    "expired": p["expired"], "other": p["other"],
                    "until": ", ".join(sorted(p["until"])),
                    "first": min(p["dates"]) if p["dates"] else "",
                    "last": max(p["dates"]) if p["dates"] else "", "note": "; ".join(notes),
                    "years": "; ".join(f"{y}: {e:,} embargoed, {n:,} not"
                                       for y, (e, n) in sorted(p["years"].items()))})
    return out


def report(projects: list, today: str) -> None:
    w = max([len(p["project"]) for p in projects] + [7])
    print(f"  today: {today}")
    print("")
    print(f"  {'project':<{w}}  {'client':<16}{'records':>8}{'embargoed':>10}{'not':>6}"
          f"  {'until':<11}{'dates':<24}note")
    t = defaultdict(int)
    for p in projects:
        for k in ("records", "embargoed", "not", "none", "expired", "other"):
            t[k] += p[k]
        print(f"  {p['project']:<{w}}  {p['client'][:15]:<16}{p['records']:>8,}"
              f"{p['embargoed']:>10,}{p['not']:>6,}  {p['until'][:10]:<11}"
              f"{p['first']} - {p['last']:<11}{p['note']}")
    for p in projects:
        if "mixed" in p["note"]:
            print(f"    {p['project']} by year -- {p['years']}")
    print(f"  {'TOTAL':<{w}}  {'':<16}{t['records']:>8,}{t['embargoed']:>10,}{t['not']:>6,}")
    print("")
    print(f"  not embargoed: {t['not']:,} = no embargo set {t['none']:,} + embargo date passed "
          f"{t['expired']:,} + other status {t['other']:,}")
    choice = sum(p["not"] for p in projects if "by choice" in p["note"])
    print(f"    of which unembargoed by choice (Elmley): {choice:,}; for Wil to decide: "
          f"{t['not'] - choice:,}")
    if t["not"] == REVIEW_FIGURE:
        print(f"  agrees with the review's {REVIEW_FIGURE:,} un-embargoed commercial records.")
    else:
        print(f"  the review counted {REVIEW_FIGURE:,}; this database has {t['not']:,} "
              f"(difference {t['not'] - REVIEW_FIGURE:+,}): records added, edited or embargoes "
              f"that have run out since 9 Oct.")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--csv", default=rc.default_csv("commercial_embargo"))
    ap.add_argument("--today", default=_dt.date.today().isoformat(),
                    help="the date an embargo is tested against (default today)")
    ap.add_argument("--db", default=str(paths.OBSERVATUM_DB), help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    print("")
    print("Commercial observations by project -- embargoed or not (READ ONLY)")
    print("=" * 74)
    print(f"  observatum.db: {a.db}")
    conn = rc.connect_ro(a.db)
    try:
        projects = gather(conn, a.today)
    finally:
        conn.close()
    report(projects, a.today)
    n = rc.write_csv(a.csv, HEADER, ([p["project"], p["client"], p["records"], p["embargoed"],
                                      p["not"], p["none"], p["expired"], p["other"], p["until"],
                                      p["first"], p["last"], p["note"], p["years"]] for p in projects))
    print("")
    print(f"  CSV: {n:,} projects -> {a.csv}")
    print("")
    print("READ ONLY. Nothing has been changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
