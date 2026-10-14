"""stage_records_from_specimens.py -- Wil's specimens with no field record become Data Entry
rows, to check and commit as usual (14 Oct 2026; decisions Q23-Q33, 12 Oct).

    py -3.14 scripts\\stage_records_from_specimens.py            # dry run + plan CSV
    py -3.14 scripts\\stage_records_from_specimens.py --apply    # backup, then the rows
    py -3.14 scripts\\stage_records_from_specimens.py --undo     # list the jobs it made
    py -3.14 scripts\\stage_records_from_specimens.py --undo --apply   # backup, discard them

Nothing goes straight into Observatum. Each proposed record (one per species + date + grid
ref, count = number of specimens, a minimum; scripts/report_specimens_without_records.py
group 1) becomes ONE row in a Data Entry job; committing the job writes the records and links
the specimens to them (shared/specimen_staging.py). Deleting a row lets its specimens go.

  stage    Personal                     -> job "Records from specimens"
  stage    Commercial, same visit       -> job "<project> <year>: records from specimens"
                                           (the client and embargo that survey year's
                                           records carry -- Q26)
  review   Commercial, season match     -> job "<project> <year>: specimens, season match - check
                                           each" (Q25: check each row, delete any that is not
                                           that survey's, commit the rest)
  hold     unknown Personal/Commercial  (Q24: wait for those surveys' field data)
  hold     another species of the genus that day and place (Q29: check by hand first)
  hold     in the Recording Scheme: same species, same or close date and place (Q30)
  hold     specimens disagree on Personal/Commercial or project
  hold     already on a Data Entry row (an earlier run)
  hold     a survey or row still being entered in Data Entry: the same species within a week,
           or a Commercial job's rows within 2 km and 30 days (commit that job, run again)
Not here: near misses (Q28, link by hand), missing details (Q32), other people's (Q31).
All of them are in Insect Collection > Specimens to check.

The plan CSV (scripts\\_oneoff\\specimen_records_plan_<date>.csv) lists every proposed record
with its action. --apply backs up observatum.db first (conn.backup). Close Observatum and
Data Entry before --apply.
"""
import argparse
import os
import sqlite3
import sys
from collections import Counter

try:
    from scripts import report_common as rc
    from scripts import report_specimens_without_records as rs
    from scripts import specimen_breakdown as sb
except ImportError:                       # run as py scripts\<name>.py
    import report_common as rc
    import report_specimens_without_records as rs
    import specimen_breakdown as sb

import paths  # noqa: E402

HEADER = ["action", "job", "why", "species_name", "date", "grid_ref", "site_name", "quantity",
          "recorder", "determiner", "project", "client", "embargo_until", "specimen_ids", "record_key"]


def pending_rows(conn) -> list:
    """Data Entry rows not yet in Observatum (jobs still open or awaiting iRecord), other than
    rows made from specimens: {tvk, day, c (grid centre), job, commercial}. A survey still
    being entered has its records here, not in observations (14 Oct 2026)."""
    from DataEntry import date_utils
    from DataEntry.staging_repo import PENDING_STATUSES
    from shared import specimen_staging
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='entry_staging'").fetchone():
        return []
    mine = set(specimen_staging.staged(conn).values())
    marks = ",".join("?" * len(PENDING_STATUSES))
    out = []
    for rid, tvk, d, ref, name, mode in conn.execute(
            "SELECT s.id, s.species_tvk, s.date, s.grid_ref, j.name, j.mode FROM entry_staging s "
            f"JOIN entry_jobs j ON j.id = s.job_id WHERE j.status IN ({marks})", PENDING_STATUSES):
        if rid in mine:
            continue
        try:
            iso = date_utils.start_iso(d) if d else None
        except Exception:
            iso = None
        out.append({"tvk": tvk or "", "day": sb.day(iso), "c": sb.centre(ref), "job": name,
                    "commercial": (mode or "").lower().startswith("comm")})
    return out


def _why_pending(rec, ss, pending, roll) -> str:
    """Hold a proposal whose find may be a record still being entered in Data Entry: the same
    species within NEAR_DAYS, or a Commercial survey's rows within VISIT_M and SEASON_DAYS
    (any species: the survey's entry may not have reached it yet)."""
    d, c = sb.day(rec["date"]), sb.centre(rec["grid_ref"])
    if not d:
        return ""
    tvks = {roll.get(s["tvk"], s["tvk"]) for s in ss} | {s["tvk"] for s in ss}
    for r in pending:
        if r["day"] and r["tvk"] and (r["tvk"] in tvks or roll.get(r["tvk"]) in tvks) \
                and abs((r["day"] - d).days) <= sb.NEAR_DAYS:
            return f"same species in Data Entry, not yet committed ({r['job']}): commit that job first"
    for r in pending:
        if r["commercial"] and r["day"] and abs((r["day"] - d).days) <= sb.SEASON_DAYS:
            far = sb.dist(c, r["c"])
            if far is not None and far <= sb.VISIT_M:
                return f"near a survey still being entered in Data Entry ({r['job']}): commit that job first"
    return ""


def _why_held(rec, ss, staged) -> str:
    if any(s["id"] in staged for s in ss):
        # a specimen added to a group already on a row is not given a second row (review)
        return "already on a Data Entry row" if all(s["id"] in staged for s in ss) else \
            "partly on a Data Entry row: add the rest to that row by hand"
    if rec["sub"] == "unknown" or not rec["sub"]:
        return "unknown Personal/Commercial: " + rs.basis(ss[0]["reason"]) + " (Q24)"
    if any(s.get("genus_note") for s in ss):
        return "another species of the genus that day and place: check by hand first (Q29)"
    if any(e[0] == "scheme" for s in ss for e in s["elsewhere"]):
        return "in the Recording Scheme (same or close date and place): list only (Q30)"
    if rec["conflict"]:
        return "specimens disagree: " + rec["conflict"]
    if rec["sub"] == "Commercial" and not (rec["project"] or "").strip():
        return "Commercial with no project"
    return ""


def year_terms(g) -> dict:
    """{(project, year): client / embargo most of that survey year's records carry} -- a
    project can be embargoed one year and not another (Graven Hill 2023 / 2025; Q26)."""
    from collections import defaultdict
    c = defaultdict(Counter)
    raw = defaultdict(Counter)
    for r in g["rule"].obs.rows:
        if not sb.is_commercial(r.get("record_type")) or sb.blank(r.get("project_name")):
            continue
        y = (r.get("date") or "")[:4]
        p = r["project_name"].strip()
        c[(p, y)][(r.get("client"), r.get("embargo_status"), r.get("embargo_until"))] += 1
        raw[p][r["project_name"]] += 1
    out = {}
    for k, cc in c.items():
        (client, st, until), _n = cc.most_common(1)[0]
        out[k] = {"client": client, "embargo_status": st, "embargo_until": until,
                  "project_name": raw[k[0]].most_common(1)[0][0]}
    return out


def terms_for(g, project: str, year: str, by_year=None) -> dict:
    """Client, embargo and stored project name for a project's survey year (else the
    project's most common terms, with its stored name)."""
    by_year = by_year if by_year is not None else year_terms(g)
    t = by_year.get((project, year))
    if t:
        return t
    t = dict(g["rule"].terms.get(project, {}))
    names = [v["project_name"] for (p, _y), v in by_year.items() if p == project]
    if names:
        t["project_name"] = names[0]
    return t


def plan(g, staged=(), pending=()) -> list:
    """One dict per proposed record: action stage/review/hold, kind (Personal / Commercial /
    season), project, terms, why, specimen ids."""
    staged = set(staged)
    by_year = year_terms(g)
    by_key = {}
    for s in g["specs"]:
        if s["group"] == 1:
            by_key.setdefault(sb.record_key(s, g["roll"]), []).append(s)
    out = []
    for key, rec in sorted(g["records"].items(), key=lambda kv: (kv[1]["date"] or "", kv[0])):
        ss = by_key.get(key, [])
        held = _why_held(rec, ss, staged) or _why_pending(rec, ss, pending, g["roll"])
        year = (rec["date"] or "")[:4]
        terms = {}
        if rec["sub"] == "Commercial":
            terms = terms_for(g, rec["project"], year, by_year)
        if held:
            action, kind = "hold", ""
        elif rec["sub"] == "Personal":
            action, kind = "stage", "Personal"
        elif all(rs.basis(s["reason"]) == "same visit" for s in ss):
            action, kind = "stage", "Commercial"
        else:
            action, kind = "review", "season"
        why = held or "; ".join(sorted({rs.basis(s["reason"]) for s in ss}))
        out.append({"key": key, "action": action, "kind": kind, "project": rec["project"] or "",
                    "year": year if kind in ("Commercial", "season") else "",
                    "terms": terms, "why": why, "rec": rec,
                    "ids": [s["id"] for s in ss if s["id"] not in staged]})
    return out


def csv_rows(items):
    from shared.specimen_records import job_name
    for p in items:
        r, t = p["rec"], p["terms"]
        yield [p["action"], job_name(p["kind"], p["project"], p["year"]) if p["kind"] else "", p["why"],
               r["species_name"], r["date"], r["grid_ref"], r["site_name"], r["quantity"],
               r["recorder"], r["determiner"], p["project"], t.get("client"),
               t.get("embargo_until"), " ".join(str(i) for i in p["ids"]), p["key"]]


def summary(items) -> None:
    from shared.specimen_records import job_name
    c = Counter((p["action"], job_name(p["kind"], p["project"], p["year"]) if p["kind"] else p["why"])
                for p in items)
    n = Counter()
    for p in items:
        n[(p["action"], job_name(p["kind"], p["project"], p["year"]) if p["kind"] else p["why"])] += len(p["ids"])
    for act in ("stage", "review", "hold"):
        rows = [(k[1], v) for k, v in c.items() if k[0] == act]
        if not rows:
            continue
        print(f"  {act}: {sum(v for _k, v in rows):,} records")
        for lab, v in sorted(rows, key=lambda x: -x[1]):
            print(f"      {v:>6,} records / {n[(act, lab)]:>5,} specimens  {lab}")


def apply(db_path, items, backup_dir=rc.BACKUP_DIR) -> dict:
    """Back up, then one Data Entry row per stage/review item. Returns counts."""
    from shared import specimen_records as sr
    from shared import specimen_staging
    dest = rc.backup(db_path, "stage_specimen_records", backup_dir)
    print(f"  backup: {dest}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    made, skipped, jobs = 0, 0, Counter()
    try:
        specimen_staging.ensure_schema(conn)
        for p in items:
            if p["action"] == "hold" or not p["ids"]:
                continue
            jid = sr.find_or_make_job(conn, p["kind"], p["project"], p["terms"], p["year"])
            rid = sr.stage(conn, jid, p["ids"], p["rec"]["recorder"])
            conn.commit()
            if rid is None:
                skipped += 1
            else:
                made += 1
                jobs[sr.job_name(p["kind"], p["project"], p["year"])] += 1
    finally:
        conn.close()
    return {"rows": made, "skipped": skipped, "jobs": jobs, "backup": dest}


def made_jobs(conn) -> list:
    """The open jobs this script made: named as job_name() names them and every row made
    from specimens (shared/specimen_staging). A job with any row of Wil's own is never
    one of them. [(job dict, rows, specimens)]."""
    from DataEntry import staging_repo as repo
    from shared import specimen_staging
    if not specimen_staging.has_table(conn):
        return []
    on_row = specimen_staging.staged(conn)                 # specimen -> row
    per_row = {}
    for _sid, rid in on_row.items():
        per_row[rid] = per_row.get(rid, 0) + 1
    out = []
    for job in repo.list_jobs(conn):
        name = job.get("name") or ""
        if not (name == "Records from specimens" or name.endswith(": records from specimens")
                or name.endswith(": specimens, season match - check each")):
            continue
        rows = [r["id"] for r in repo.fetch_rows(conn, job["id"])]
        if not rows or any(r not in per_row for r in rows):
            continue
        out.append((job, len(rows), sum(per_row[r] for r in rows)))
    return out


def undo(db_path, apply_it: bool, backup_dir=rc.BACKUP_DIR) -> int:
    """Take the rows this script made out of Data Entry (Data Entry's own discard: the rows
    go, their specimens are free again, the job is marked discarded). Nothing else is
    touched: committed records stay. Run the script again later to make them afresh."""
    from DataEntry import commit_service
    print("")
    print("Records from specimens: take the jobs this script made out of Data Entry"
          + ("" if apply_it else " (DRY RUN)"))
    print("=" * 74)
    print(f"  observatum.db: {db_path}")
    ro = rc.connect_ro(db_path)
    ro.row_factory = sqlite3.Row
    try:
        jobs = made_jobs(ro)
    finally:
        ro.close()
    if not jobs:
        print("  no open jobs made by this script. Nothing to do.")
        return 0
    for job, rows, specs in jobs:
        print(f"  {rows:>6,} rows / {specs:>5,} specimens  {job['name']}")
    print(f"  {sum(j[1] for j in jobs):,} rows in {len(jobs)} job(s)")
    print("")
    if not apply_it:
        print("DRY RUN. Nothing has been changed. With --undo --apply (Observatum and Data Entry")
        print("closed) these rows are discarded and their specimens freed; committed records stay.")
        return 0
    if os.path.basename(str(db_path)).lower() != "observatum.db":
        print("  --apply works on observatum.db only")
        return 2
    print(f"  backup: {rc.backup(db_path, 'undo_specimen_records', backup_dir)}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        n = 0
        for job, _rows, _specs in made_jobs(conn):         # read again on the open connection
            n += commit_service.discard_job(conn, job)
        conn.commit()
        left = len(made_jobs(conn))
    finally:
        conn.close()
    print(f"  discarded {n:,} row(s); jobs left from this script: {left}")
    print("")
    print("Done. Run the script again (dry run first) when you want the rows back.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true", help="back up, then make the Data Entry rows")
    ap.add_argument("--csv", default=rc.default_csv("specimen_records_plan"))
    ap.add_argument("--db", default=str(paths.OBSERVATUM_DB), help=argparse.SUPPRESS)
    ap.add_argument("--uksi", default=str(paths.UKSI_DB), help=argparse.SUPPRESS)
    ap.add_argument("--backup-dir", default=rc.BACKUP_DIR, help=argparse.SUPPRESS)
    ap.add_argument("--undo", action="store_true",
                    help="take the jobs this script made out of Data Entry (with --apply)")
    a = ap.parse_args(argv)
    if a.undo:
        return undo(a.db, a.apply, a.backup_dir)
    print("")
    print("Records from specimens: Data Entry rows to check and commit"
          + ("" if a.apply else " (DRY RUN)"))
    print("=" * 74)
    print(f"  observatum.db: {a.db}")
    if os.path.basename(a.db).lower() != "observatum.db" and a.apply:
        print("  --apply works on observatum.db only")
        return 2
    conn = rc.connect_ro(a.db)
    try:
        from shared import specimen_staging
        g = rs.gather(conn, a.uksi)
        items = plan(g, specimen_staging.staged_ids(conn), pending_rows(conn))
    finally:
        conn.close()
    summary(items)
    n = rc.write_csv(a.csv, HEADER, csv_rows(items))
    print(f"  plan CSV: {n:,} proposed records -> {a.csv}")
    print("")
    if not a.apply:
        print("DRY RUN. Nothing has been changed. With --apply (Observatum and Data Entry closed),")
        print("the stage and review rows are made in Data Entry; nothing is committed.")
        return 0
    res = apply(a.db, items, a.backup_dir)
    print(f"  made {res['rows']:,} Data Entry row(s); {res['skipped']:,} skipped (their "
          "specimens already have a field record or a row)")
    for name, v in res["jobs"].most_common():
        print(f"      {v:>6,}  {name}")
    print("")
    print("Done. Open Data Entry, check each job's rows (the season jobs one by one), then commit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
