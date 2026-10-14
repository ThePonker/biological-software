"""specimens_to_check -- data and writes behind Insect Collection > Specimens to check (14 Oct 2026).

No Qt. load() reads (read-only) what scripts/report_specimens_without_records.gather and
scripts/stage_records_from_specimens.plan work out, and tabs() turns it into the seven tables
the window shows. The write functions take a path and open their own connection; the caller
(the window) backs up first and refuses unless is_live_db(). Nothing here applies a rule: the
rules are in the two scripts, shared/specimen_links.py and shared/specimen_records.py.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from shared import irecord_links, specimen_records, specimen_staging
from shared.record_match import norm_ref, norm_text
from shared.specimen_links import CHECK_COLUMN, has_check_column

KEYS = ("near", "reid", "ready", "season", "held", "missing", "onrow")
TITLES = {"near": "Near misses", "reid": "Possible re-identifications",
          "ready": "Ready to make", "season": "Season match (check each)", "held": "Held",
          "missing": "Missing details", "onrow": "On a Data Entry row"}
NOTES = {
    "near": "Specimens with no field record, but a record of the same species close by in time "
            "and place. Probably the same find: link them.",
    "reid": "Specimens with no field record, where another species of the same genus was "
            "recorded the same day at the same grid ref. The name may have changed: check, then "
            "link, or make a record if it is a separate find.",
    "ready": "Records the collection supports. Each row becomes one row in Data Entry, for you "
             "to check and commit there.",
    "season": "Probably from a survey, but not on a day that has records. Check that each one "
              "really belongs to that survey before making its Data Entry row.",
    "held": "Not made automatically, for the reason shown. Look at each by hand.",
    "missing": "Specimens without a species code, a readable date or a grid ref of 1 km or finer, "
               "so no record can be made yet.",
    "onrow": "Specimens already on a Data Entry row, waiting to be checked and committed there.",
}
NEAR_COLS = ("Specimen", "Species", "Date", "Grid ref", "Site", "Candidate", "Candidate species",
             "Candidate date", "Candidate grid ref", "Days apart", "Distance", "Reason")
PLAN_COLS = ("Species", "Date", "Grid ref", "Site", "Quantity", "Job")
COLUMNS = {"near": NEAR_COLS, "reid": NEAR_COLS, "ready": PLAN_COLS, "season": PLAN_COLS,
           "held": PLAN_COLS[:5] + ("Why held",),
           "missing": ("Specimen", "Species", "Date", "Grid ref", "Site", "What is missing"),
           "onrow": ("Specimen", "Species", "Date", "Grid ref", "Site", "Data Entry job")}


def is_live_db(path) -> bool:
    from DataEntry.data_entry_widget import LIVE_DB_BASENAME
    return os.path.basename(str(path or "")).lower() == LIVE_DB_BASENAME


def _ro(path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def load(db_path, uksi_path=None) -> dict:
    """{"g": gather result, "plan": plan items, "staged": {specimen id: job name},
    "has_check": bool, "irecord": {observation id: iRecord id}}."""
    from scripts import report_specimens_without_records as rs
    from scripts import stage_records_from_specimens as sp
    conn = _ro(db_path)
    try:
        g = rs.gather(conn, uksi_path)
        on_row = specimen_staging.staged(conn)
        items = sp.plan(g, set(on_row), sp.pending_rows(conn))
        names = {}
        try:
            names = {r[0]: r[1] for r in conn.execute(
                "SELECT s.id, j.name FROM entry_staging s JOIN entry_jobs j ON j.id = s.job_id")}
        except sqlite3.Error:
            pass
        obs_ids = {n[0]["id"] for s in g["specs"] for n in s["near"]}
        try:
            irecord = irecord_links.irecord_ids(conn, "observations", obs_ids)
        except sqlite3.Error:
            irecord = {}
        return {"g": g, "plan": items, "has_check": has_check_column(conn), "irecord": irecord,
                "staged": {sid: names.get(rid, f"row {rid}") for sid, rid in on_row.items()},
                "onrow_specs": specimen_records.specimens(conn, on_row)}
    finally:
        conn.close()


def _near_row(s, irecord) -> dict:
    r, dd, d = s["near"][0]
    dist = f"{d:.0f} m" if d is not None else "same site"
    cells = [s["code"], s["name"], s["date"], s["ref"], s["site"], r["id"], r.get("species_name"),
             r.get("date"), r.get("grid_ref"), dd, dist, s["reason"]]
    return {"cells": cells, "ids": [s["id"]], "obs": r["id"], "irecord": irecord.get(r["id"])}


def _plan_row(p, job=True) -> dict:
    r = p["rec"]
    from shared.specimen_records import job_name
    last = (job_name(p["kind"], p["project"], p["year"]) if p["kind"] else "") if job else p["why"]
    return {"cells": [r["species_name"], r["date"], r["grid_ref"], r["site_name"], len(p["ids"]),
                      last], "ids": list(p["ids"]), "item": p}


def tabs(data) -> Dict[str, List[dict]]:
    """{tab key: [row dicts {"cells", "ids", "obs", "irecord", "item"}]}."""
    specs = data["g"]["specs"]
    out = {k: [] for k in KEYS}
    on_row = set(data["staged"])          # made into a Data Entry row: listed on that tab only
    for s in specs:
        if s["id"] in on_row:
            continue
        if s["group"] == 2 and s["near"]:
            out["near"].append(_near_row(s, data["irecord"]))
        elif s["group"] == 1 and s.get("genus_note") and s["near"]:
            out["reid"].append(_near_row(s, data["irecord"]))
        elif s["group"] == 3:
            out["missing"].append({"cells": [s["code"], s["name"], s["date"], s["ref"], s["site"],
                                             s["reason"]], "ids": [s["id"]]})
    for p in data["plan"]:
        if p["action"] == "stage":
            out["ready"].append(_plan_row(p))
        elif p["action"] == "review":
            out["season"].append(_plan_row(p))
        elif p["action"] == "hold" and p["ids"]:
            out["held"].append(_plan_row(p, job=False))
    for s in data["onrow_specs"]:
        out["onrow"].append({"cells": [s["specimen_code"], s["species_name"], s["date_collected"],
                                       s["grid_ref"], s["site_name"], data["staged"].get(s["id"])],
                             "ids": [s["id"]]})
    return out


def specimen_rows(db_path, ids: Iterable[int]) -> List[dict]:
    conn = _ro(db_path)
    try:
        return specimen_records.specimens(conn, ids)
    finally:
        conn.close()


def picker_spec(db_path, sid) -> Optional[dict]:
    """The dict FieldRecordPicker wants (specimen_records.specimens has every key it reads)."""
    rows = specimen_rows(db_path, [sid])
    return rows[0] if rows else None


def visit_problem(rows: List[dict]) -> str:
    """'' when the specimens share one site name and grid ref, else why not."""
    if len({norm_text(r.get("site_name")) for r in rows}) > 1:
        return "The selected specimens come from more than one site name."
    if len({norm_ref(r.get("grid_ref")) for r in rows}) > 1:
        return "The selected specimens have more than one grid ref."
    if len({r.get("date_collected") or "" for r in rows}) > 1:
        return "The selected specimens have more than one date (more than one visit)."
    return ""


def _write(db_path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def link(db_path, specimen_id, observation_id) -> int:
    """0 when the specimen already has a field record or is on a Data Entry row (linking it
    as well would give its find two records once the row is committed)."""
    conn = _write(db_path)
    try:
        if int(specimen_id) in specimen_staging.staged_ids(conn):
            return 0
        n = conn.execute("UPDATE specimens SET observation_id=? WHERE id=? AND observation_id IS NULL",
                         (int(observation_id), int(specimen_id))).rowcount
        cols = {r[1] for r in conn.execute("PRAGMA table_info(specimens)")}
        if n and CHECK_COLUMN in cols:     # linked: no longer "checked, no field record" (as Edit Specimen)
            conn.execute(f"UPDATE specimens SET {CHECK_COLUMN}=NULL WHERE id=?", (int(specimen_id),))
        conn.commit()
        return n
    finally:
        conn.close()


def mark_checked(db_path, ids: Iterable[int]) -> int:
    """Same value the Field record box stores: the date and time ticked."""
    when = datetime.now().isoformat(timespec="seconds")
    conn = _write(db_path)
    try:
        n = 0
        for i in ids:
            n += conn.execute(f"UPDATE specimens SET {CHECK_COLUMN}=? WHERE id=? "
                              "AND observation_id IS NULL", (when, int(i))).rowcount
        conn.commit()
        return n
    finally:
        conn.close()


def change_date(db_path, ids: List[int], iso: str) -> int:
    """Specimens on a Data Entry row are left (the row keeps its own date; change it there)."""
    conn = _write(db_path)
    try:
        ids = [int(i) for i in ids if int(i) not in specimen_staging.staged_ids(conn)]
        if not ids:
            return 0
        marks = ",".join("?" * len(ids))
        n = conn.execute("UPDATE specimens SET date_collected=?, updated_at=CURRENT_TIMESTAMP "
                         f"WHERE id IN ({marks})", [iso] + [int(i) for i in ids]).rowcount
        conn.commit()
        return n
    finally:
        conn.close()


def make_records(db_path, jobs: List[dict]) -> int:
    """jobs: dicts kind, project, terms, year, ids, recorder. One Data Entry row each (specimens
    that gained a field record or a row meanwhile are left out). Returns rows made."""
    conn = _write(db_path)
    made = 0
    try:
        specimen_staging.ensure_schema(conn)
        for j in jobs:
            jid = specimen_records.find_or_make_job(conn, j["kind"], j["project"], j["terms"], j["year"])
            if specimen_records.stage(conn, jid, j["ids"], j.get("recorder")) is not None:
                made += 1
            conn.commit()
        return made
    finally:
        conn.close()


def jobs_for_choice(g, ids: Iterable[int], choice: str) -> List[dict]:
    """Make-record jobs for specimens Wil says are separate finds: `choice` is "Personal" or a
    project name from the plan's terms (year from the specimen date). One job per species,
    date and place (scripts/specimen_breakdown.record_key)."""
    from scripts import specimen_breakdown as sb
    from scripts.stage_records_from_specimens import year_terms
    by_year = year_terms(g)                  # that survey year's embargo, not the project's
    want = set(ids)
    groups: Dict[str, List[dict]] = {}
    for s in g["specs"]:
        if s["id"] in want:
            groups.setdefault(sb.record_key(s, g["roll"]), []).append(s)
    out = []
    for ss in groups.values():
        year = (ss[0]["date"] or "")[:4]
        if choice == "Personal":
            out.append({"kind": "Personal", "project": "", "terms": {}, "year": "",
                        "ids": [s["id"] for s in ss]})
        else:
            from scripts.stage_records_from_specimens import terms_for
            out.append({"kind": "Commercial", "project": choice,
                        "terms": terms_for(g, choice, year, by_year), "year": year,
                        "ids": [s["id"] for s in ss]})
    return out


def jobs_for_items(items: Iterable[dict]) -> List[dict]:
    """Make-record jobs for plan items (Ready to make / Season match)."""
    return [{"kind": p["kind"], "project": p["project"], "terms": p["terms"], "year": p["year"],
             "ids": p["ids"], "recorder": p["rec"]["recorder"]} for p in items if p["ids"]]
