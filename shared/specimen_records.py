"""specimen_records -- records made from specimens that have no field record (14 Oct 2026).

A record is never written straight into Observatum: specimens become a Data Entry row (one
per species + date + grid ref, count = number of specimens, a minimum), in a job Wil can
check, edit and commit as usual. On commit the specimens are linked to the new record
(shared/specimen_staging.py). Used by scripts/stage_records_from_specimens.py (in bulk)
and by Insect Collection > Specimens to check > Make record (one specimen or a few).

Jobs (found again by name, so a second run adds to the same job while it is open):
  Personal                      "Records from specimens"                         (Personal)
  Commercial, same visit        "<project> <year>: records from specimens"        (Commercial)
  Commercial, season match      "<project> <year>: specimens, season match - check each"
A Commercial job takes the client and embargo most of that survey year's records carry.

No Qt. The caller commits the connection.
"""
from __future__ import annotations

from collections import Counter
from typing import Dict, Iterable, List, Optional

from shared import specimen_staging

PERSONAL_JOB = "Records from specimens"
SPEC_COLUMNS = ("id", "specimen_code", "species_name", "species_tvk", "common_name",
                "order_name", "family", "date_collected", "grid_ref", "site_name",
                "vice_county", "vc_number",
                "collector", "determiner", "sex", "observation_id")


def job_name(kind: str, project: str = "", year: str = "") -> str:
    if kind == "Personal":
        return PERSONAL_JOB
    survey = f"{project} {year}".strip()
    if kind == "season":
        return f"{survey}: specimens, season match - check each"
    return f"{survey}: records from specimens"


def find_or_make_job(conn, kind: str, project: str = "", terms: Optional[Dict] = None,
                     year: str = "") -> int:
    """The open job for this kind ('Personal', 'Commercial' or 'season'), project and survey
    year (a project's embargo can differ by year)."""
    from DataEntry import staging_repo as repo
    repo.ensure_schema(conn)
    name = job_name(kind, project, year)
    mode = "Personal" if kind == "Personal" else "Commercial"
    row = conn.execute("SELECT id FROM entry_jobs WHERE name = ? AND mode = ? AND status = 'active' "
                       "ORDER BY id LIMIT 1", (name, mode)).fetchone()
    if row:
        return row[0]
    t = terms or {}
    # the project name exactly as the survey's records store it ('Derby ' with its space), so
    # the new records join that survey in Examen and the reports (review 14 Oct 2026)
    stored = t.get("project_name") or project
    jid = repo.create_job(conn, name, mode, client=t.get("client") if mode == "Commercial" else None,
                          project=stored if mode == "Commercial" else None, commit=False)
    if mode == "Commercial" and t.get("embargo_until"):
        repo.update_job(conn, jid, commit=False, embargo_until=t["embargo_until"])
    conn.commit()
    return jid


def specimens(conn, ids: Iterable[int]) -> List[Dict]:
    have = {r[1] for r in conn.execute("PRAGMA table_info(specimens)")}
    cols = ", ".join(c if c in have else f"NULL AS {c}" for c in SPEC_COLUMNS)
    ids = [int(i) for i in ids]
    out = []
    for i in range(0, len(ids), 500):
        part = ids[i:i + 500]
        cur = conn.execute(f"SELECT {cols} FROM specimens WHERE id IN ({','.join('?' * len(part))})", part)
        out += [dict(zip(SPEC_COLUMNS, r)) for r in cur]
    return sorted(out, key=lambda s: s["id"])


def _top(specs, field):
    c = Counter((s.get(field) or "").strip() for s in specs if (s.get(field) or "").strip())
    return c.most_common(1)[0][0] if c else None


def _top_value(specs, field):
    c = Counter(s.get(field) for s in specs if s.get(field) not in (None, ""))
    return c.most_common(1)[0][0] if c else None


def row_data(specs: List[Dict], recorder: Optional[str] = None) -> Dict:
    """The Data Entry row for these specimens (one species, date and place). recorder: the
    name to record under (default: the most common collector)."""
    sexes = Counter((s.get("sex") or "").strip().lower() for s in specs)
    sex = None
    if len(sexes) == 1 and "" not in sexes:
        sex = (specs[0].get("sex") or "").strip()
    codes = [s.get("specimen_code") or f"id {s['id']}" for s in specs]
    bits = [f"From {len(specs)} specimen(s) in the collection ({', '.join(codes[:8])}"
            + (", ..." if len(codes) > 8 else "") + "); the count is a minimum"]
    if sex is None and any(sexes):
        bits.append(", ".join(f"{n} {k or 'sex not given'}" for k, n in sorted(sexes.items())))
    return {
        "species_name": _top(specs, "species_name"), "species_tvk": _top(specs, "species_tvk"),
        "common_name": _top(specs, "common_name"), "order_name": _top(specs, "order_name"),
        "family": _top(specs, "family"), "date": _top(specs, "date_collected"),
        "grid_ref": _top(specs, "grid_ref"), "site_name": _top(specs, "site_name"),
        "vice_county": _top(specs, "vice_county"), "vc_number": _top_value(specs, "vc_number"),
        "recorder": recorder or _top(specs, "collector"), "determiner": _top(specs, "determiner"),
        "sex": sex, "quantity": len(specs), "method": None, "comment": "; ".join(bits),
    }


def free(conn, ids: Iterable[int]) -> List[int]:
    """Those of `ids` with no field record and not already on a Data Entry row."""
    on_row = specimen_staging.staged_ids(conn)
    rows = specimens(conn, ids)
    return [s["id"] for s in rows if s.get("observation_id") is None and s["id"] not in on_row]


def stage(conn, job_id: int, specimen_ids: Iterable[int], recorder: Optional[str] = None) -> Optional[int]:
    """One Data Entry row in job `job_id` for these specimens (already grouped by the caller:
    one species, date and place). Specimens with a field record, or already on a row, are
    left out; None when nothing is left. Returns the staging row id."""
    from DataEntry import staging_repo as repo
    ids = free(conn, specimen_ids)
    if not ids:
        return None
    data = row_data(specimens(conn, ids), recorder)
    try:                                       # the row and its specimen list together, or neither
        rid = repo.insert_row(conn, job_id, data, commit=False)
        specimen_staging.add(conn, rid, ids)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return rid


__all__ = ["PERSONAL_JOB", "job_name", "find_or_make_job", "specimens", "row_data", "free",
           "stage"]
