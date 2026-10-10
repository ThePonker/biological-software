"""irecord_export -- Personal jobs go to iRecord, then come back (review DE7, 9 Oct 2026).

Personal records are iRecord-first: spreadsheet -> iRecord -> Observatum by the sync. A
Personal job committed straight into Observatum would be held twice once iRecord sent it
back (faults F38/F39). So a Personal job has no Commit; it has:

  1. Export for iRecord -- a CSV laid out for iRecord's bulk import. The job's status
     becomes awaiting_irecord ("exported - awaiting iRecord"); its rows are kept.
  2. Check iRecord return (Jobs page) -- after the next iRecord sync, each row is matched
     to an observation that now carries an iRecord ID: same TVK (or name), date, grid ref
     and recorder. When every row is back the job can be closed (irecord_returned).

No Qt here: the dialogs are in irecord_return_dialog.py.

Column headings follow iRecord's import (Indicia) field names and the heading Observatum's
own iRecord export uses for the method; the import wizard lets each be re-mapped, and
remembers it. Dates are written as iRecord's import reads them: 05/06/2026, Jun 2026, 2026.
"""
from __future__ import annotations

import csv
import re
from datetime import date
from typing import Dict, Iterable, List, Optional, Set

from DataEntry import date_utils
from DataEntry import staging_repo as repo

IRECORD_COLUMNS = (
    "Species", "TVK", "Date", "Grid reference", "Location name", "Recorder(s)",
    "Determiner", "Abundance", "Stage", "Sex", "Sample method", "Comment",
)


def _has_species(row: Dict) -> bool:
    return bool((row.get("species_name") or "").strip())


def blocking_rows(rows: List[Dict]) -> List[int]:
    """Grid row numbers that iRecord could not take: a species with no or an unreadable
    date, or an unreadable No. (DE9: it used to be sent as 1)."""
    from DataEntry.commit_service import read_qty
    return [n for n, r in enumerate(rows, start=1)
            if _has_species(r) and (not date_utils.is_readable(r.get("date"))
                                    or read_qty(r.get("quantity")) is None)]


def accepted_tvks(tvks: Iterable[str], uksi_path=None) -> Set[str]:
    """The TVKs that are current UKSI taxa (others are written blank: iRecord then matches
    on the name). Raises if UKSI cannot be read."""
    from shared.db_open import connect_ro
    if uksi_path is None:
        import paths
        uksi_path = paths.UKSI_DB
    tvks = [t for t in dict.fromkeys(tvks) if t]
    out: Set[str] = set()
    if not tvks:
        return out
    conn = connect_ro(uksi_path)
    try:
        for i in range(0, len(tvks), 900):
            part = tvks[i:i + 900]
            out.update(t for (t,) in conn.execute(
                f"SELECT tvk FROM taxa WHERE tvk IN ({','.join('?' * len(part))})", part))
    finally:
        conn.close()
    return out


def irecord_row(row: Dict, accepted: Optional[Set[str]] = None) -> List[str]:
    """One staging row as a line of the iRecord CSV (pure)."""
    tvk = (row.get("species_tvk") or "").strip()
    if accepted is not None and tvk not in accepted:
        tvk = ""
    from DataEntry.commit_service import read_qty
    qty = read_qty(row.get("quantity")) or 1     # blocking_rows refuses an unreadable one
    t = lambda k: str(row.get(k) or "").strip()  # noqa: E731
    sex = "" if t("sex").casefold() == "not recorded" else t("sex")   # the grid's 'nothing'
    return [t("species_name"), tvk, date_utils.to_irecord(row.get("date")), t("grid_ref"),
            t("site_name"), t("recorder"), t("determiner"), str(qty), t("stage"), sex,
            t("method"), t("comment")]


def write_irecord_csv(rows: List[Dict], filepath: str, accepted: Optional[Set[str]] = None) -> int:
    """Write the rows that carry a species to an iRecord bulk-import CSV; return how many."""
    recs = [r for r in rows if _has_species(r)]
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:   # BOM: Excel-safe
        w = csv.writer(f)
        w.writerow(IRECORD_COLUMNS)
        for r in recs:
            w.writerow(irecord_row(r, accepted))
    return len(recs)


def export_job(conn, job: Dict, filepath: str, uksi_path=None) -> Dict:
    """Export a Personal job for iRecord and mark it awaiting_irecord. Rows are kept.

    Refuses (ValueError) while any row has a species without a readable date. The standing
    'Personal' job is renamed 'Personal - exported <date>' so a fresh standing job takes
    its place (ensure_personal_job). Returns {written, tvk_check, name}."""
    rows = repo.fetch_rows(conn, job["id"])
    bad = blocking_rows(rows)
    if bad:
        raise ValueError(f"{len(bad)} row(s) have no readable date or No. (rows "
                         f"{', '.join(str(n) for n in bad[:15])}) -- iRecord needs both.")
    if not any(_has_species(r) for r in rows):
        raise ValueError("there are no records to export.")
    tvk_check = "checked against UKSI"
    try:
        accepted = accepted_tvks((r.get("species_tvk") for r in rows), uksi_path)
    except Exception as e:
        accepted, tvk_check = set(), f"UKSI could not be read ({e}) -- TVKs left blank"
    n = write_irecord_csv(rows, filepath, accepted)
    today = date.today().isoformat()
    fields = {"status": repo.AWAITING_IRECORD,
              "notes": f"Exported for iRecord {today}: {n} record(s) to {filepath}"}
    name = job.get("name") or ""
    if repo.is_personal(job):
        name = f"{repo.PERSONAL_JOB_NAME} – exported {date_utils.to_display(today)}"
        fields["name"] = name
    repo.update_job(conn, job["id"], **fields)
    return {"written": n, "tvk_check": tvk_check, "name": name}


# ---------------------------------------------------------------- the return check

def _grid(v) -> str:
    return re.sub(r"\s+", "", str(v or "")).upper()


def _person(v) -> tuple:
    """'Heeney, W.J.' and 'W. J. Heeney' compare equal: the words, any order, any case."""
    return tuple(sorted(re.findall(r"[a-z0-9]+", str(v or "").casefold())))


def _same_taxon(row: Dict, obs: Dict) -> bool:
    rt, ot = (row.get("species_tvk") or "").strip(), (obs.get("species_tvk") or "").strip()
    if rt and ot and rt == ot:
        return True
    rn = " ".join(str(row.get("species_name") or "").split()).casefold()
    on = " ".join(str(obs.get("species_name") or "").split()).casefold()
    return bool(rn) and rn == on


def match_return(rows: List[Dict], observations: List[Dict]) -> Dict:
    """Pair each staging row (with a species) with one observation holding an iRecord ID.

    Same TVK or name, same date (the period's first day for a vague date) and grid ref
    (spaces and case ignored). A pass with the recorder too, then one without it for what
    is left, since iRecord may write a name differently ('matched_loose'). Each observation
    is used once. Returns {total, matched: [(row, obs)], matched_loose: [(row, obs)],
    missing: [(grid row number, row)]} (pure)."""
    recs = [(n, r) for n, r in enumerate(rows, start=1) if _has_species(r)]
    by_key: Dict[tuple, List[Dict]] = {}
    for o in observations:
        by_key.setdefault((str(o.get("date") or "")[:10], _grid(o.get("grid_ref"))), []).append(o)
    used: Set = set()
    matched, loose, left = [], [], []

    def find(row, strict):
        for o in by_key.get((date_utils.start_iso(row.get("date")) or "", _grid(row.get("grid_ref"))), []):
            if o["id"] in used or not _same_taxon(row, o):
                continue
            if strict and _person(o.get("recorder")) != _person(row.get("recorder")):
                continue
            return o
        return None

    for n, r in recs:
        o = find(r, True)
        if o is None:
            left.append((n, r))
            continue
        used.add(o["id"])
        matched.append((r, o))
    missing = []
    for n, r in left:
        o = find(r, False)
        if o is None:
            missing.append((n, r))
            continue
        used.add(o["id"])
        loose.append((r, o))
    return {"total": len(recs), "matched": matched, "matched_loose": loose, "missing": missing}


def check_return(conn, job: Dict) -> Dict:
    """match_return() for a job against observatum.db's records that carry an iRecord ID
    (read only)."""
    rows = repo.fetch_rows(conn, job["id"])
    days = [d for d in (date_utils.start_iso(r.get("date")) for r in rows if _has_species(r)) if d]
    if not days:
        return match_return(rows, [])
    cur = conn.execute(
        "SELECT id, species_tvk, species_name, date, grid_ref, recorder FROM observations "
        "WHERE irecord_id IS NOT NULL AND TRIM(CAST(irecord_id AS TEXT)) <> '' "
        "AND substr(date, 1, 10) BETWEEN ? AND ?", (min(days), max(days)))
    cols = [d[0] for d in cur.description]
    obs = [dict(zip(cols, t)) for t in cur.fetchall()]
    return match_return(rows, obs)


def close_job(conn, job: Dict) -> None:
    """Close a job whose records are all back from iRecord. Its rows are kept (not counted
    as staged any more)."""
    note = (job.get("notes") or "").strip()
    stamp = f"Closed {date.today().isoformat()}: all records back from iRecord."
    repo.update_job(conn, job["id"], status=repo.RETURNED_IRECORD,
                    notes=(note + " | " + stamp) if note else stamp)
