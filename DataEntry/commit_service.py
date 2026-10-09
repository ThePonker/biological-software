"""The three job exits: commit to Observatum, export-and-discard, discard.

commit builds an Observation from each eligible staging row and writes it via Observatum's
canonical ObservationModel.create() (then the supplementary UPDATE for the three Session-26
internal columns), reusing the same pattern/guard as write_service. Job-level values
(record_type from mode, client, project) and the embargo come in at commit time.

build_kwargs_from_row is pure and unit-tested. commit_job takes an injectable observation_cls
so it can be exercised against a stand-in on machines without Observatum's src.
"""
from __future__ import annotations

import csv
from typing import Optional, Dict

from DataEntry import staging_repo as repo
from DataEntry.write_service import _ALLOWED_FIELDS, CERTAINTY


def build_kwargs_from_row(row: Dict, job: Dict, embargo_until: Optional[str] = None,
                          taxonomy: Optional[Dict] = None) -> Dict:
    """Map one staging row + its job to Observatum Observation kwargs (pure).

    taxonomy: this row's TVK in shared.taxon_groups.taxonomy_for_tvks() -- kingdom, rank and
    taxon group from UKSI (9 Oct 2026; commits wrote none of them before, 1,440 records).
    Without it the group still comes from the row's own order and family."""
    try:
        qty = int(row.get("quantity"))
    except (TypeError, ValueError):
        qty = 1
    if qty < 1:
        qty = 1

    vc_number = row.get("vc_number")
    if not (isinstance(vc_number, int) or (str(vc_number or "").strip().isdigit())):
        vc_number = None
    elif not isinstance(vc_number, int):
        vc_number = int(vc_number)

    mode = job.get("mode") or "Personal"
    is_commercial = mode.lower().startswith("comm")

    from DataEntry import date_utils
    from shared.taxon_groups import taxon_group
    # a year or month-year commits as the period's first day with its date type (DE1)
    iso_date = date_utils.start_iso(row.get("date")) or row.get("date")
    tax = taxonomy or {}

    kwargs = {
        "species_name": (row.get("species_name") or "").strip(),
        "species_tvk": row.get("species_tvk"),
        "common_name": row.get("common_name"),
        "order_name": row.get("order_name"),
        "family": row.get("family"),
        "taxon_rank": tax.get("taxon_rank") or row.get("taxon_rank"),
        "kingdom": tax.get("kingdom"),
        "taxon_group": tax.get("taxon_group") or taxon_group(row.get("order_name"), row.get("family")),
        "recorder_certainty": CERTAINTY,
        "date": iso_date,
        "date_type": date_utils.date_type(row.get("date")) or "D",
        "grid_ref": row.get("grid_ref") or None,
        "vice_county": row.get("vice_county") or None,
        "vc_number": vc_number,
        "site_name": row.get("site_name") or None,
        "recorder": row.get("recorder") or None,
        "determiner": row.get("determiner") or None,
        "sex": row.get("sex") or None,
        "stage": row.get("stage") or None,
        "quantity": qty,
        "method": row.get("method") or None,
        "comment": (row.get("comment") or "").strip() or None,
        "record_type": mode,
        "project_name": (job.get("project") or None) if is_commercial else None,
        "client": (job.get("client") or None) if is_commercial else None,
        "embargo_until": (embargo_until or None) if is_commercial else None,
    }
    # Lat/long of the grid square's centre, with the OSGB36 -> WGS84 shift (9 Oct 2026);
    # commits used to leave it blank (1,301 records)
    from shared.osgb import gridref_to_wgs84
    ll = gridref_to_wgs84(kwargs["grid_ref"]) if kwargs["grid_ref"] else None
    if ll:
        kwargs["latitude"], kwargs["longitude"] = ll
        kwargs["geodetic_datum"] = "WGS84"
    return {k: v for k, v in kwargs.items() if k in _ALLOWED_FIELDS}


def _eligibility(row: Dict) -> Optional[str]:
    """Return None if committable, else a reason string."""
    from DataEntry import date_utils
    if not (row.get("species_name") or "").strip():
        return "no_species"
    if not (row.get("date") or "").strip():
        return "no_date"
    if not date_utils.is_readable(row.get("date")):
        return "bad_date"          # '31/02/2026', 'summer' -- stays in staging (DE1)
    return None


# What makes two records "the same entry twice": every field below equal. Usually a
# sex split typed with the sex left "Not recorded", or a block of sheet re-entered.
# One definition, used here before commit and by scripts/check_data_entry_batches.py
# after it (fault F28, 8 Oct 2026).
DOUBLE_KEY = ("species_name", "date", "grid_ref", "method", "trap_number", "sex", "stage")


def precommit_issues(rows) -> Dict[str, list]:
    """What a commit would write with gaps or doubles in it (pure; backlog B8).

    rows: staging rows in grid order (repo.fetch_rows). Only rows commit would write
    (species and date present) are checked, plus 'unreadable date' for rows with a species
    and a date that cannot be read (those stay in staging). Returns {issue: [grid row
    numbers]} for 'unreadable date', 'future date', 'no site', 'no grid ref', 'no VC',
    'no recorder', 'no TVK', and 'double' (each later copy of a repeated entry, with the
    row it repeats), leaving out issues with no rows.
    """
    from DataEntry import date_utils
    issues = {"unreadable date": [], "future date": [], "no site": [], "no grid ref": [],
              "no VC": [], "no recorder": [], "no TVK": [], "double": []}
    seen = {}
    for n, row in enumerate(rows, start=1):
        why = _eligibility(row)
        if why == "bad_date":
            issues["unreadable date"].append(n)
        if why is not None:
            continue
        blank = lambda k: not str(row.get(k) or "").strip()  # noqa: E731
        if date_utils.is_future(row.get("date")):
            issues["future date"].append(n)
        if blank("site_name"):
            issues["no site"].append(n)
        if blank("grid_ref"):
            issues["no grid ref"].append(n)
        if blank("vc_number") and blank("vice_county"):
            issues["no VC"].append(n)
        if blank("recorder"):
            issues["no recorder"].append(n)
        if blank("species_tvk"):
            issues["no TVK"].append(n)
        key = tuple(str(row.get(k) or "").strip().lower() for k in DOUBLE_KEY)
        if key in seen:
            issues["double"].append((n, seen[key]))
        else:
            seen[key] = n
    return {k: v for k, v in issues.items() if v}


def commit_job(db, model, conn, job: Dict, embargo_until: Optional[str] = None,
               observation_cls=None, taxonomy: Optional[Dict] = None) -> Dict:
    """Write eligible staging rows into observations; delete the committed ones.

    Rows missing species or date, or with an unreadable date, are left in staging and
    reported. taxonomy ({tvk: ...}, shared.taxon_groups.taxonomy_for_tvks) is looked up
    when not given. A failure part-way stops the commit and is returned in 'error' with
    how many were written before it (DE4) -- never raised after the first write.
    Returns a summary dict.
    """
    if observation_cls is None:
        from src.models.observation import Observation as observation_cls  # noqa: N806

    if (job.get("mode") or "").lower().startswith("comm") and not (job.get("project") or "").strip():
        # backstop for the grid's own check: no project means "(no project)" everywhere
        raise ValueError("this commercial job has no Project -- set it with Jobs > Edit details")

    committed = 0
    skipped_species = 0
    skipped_date = 0
    skipped_bad_date = 0
    unresolved = 0
    future = 0
    error = None
    taxonomy_error = None
    from DataEntry import date_utils
    from datetime import datetime
    batch = 'DataEntry batch ' + datetime.now().isoformat(timespec='seconds')
    rows = repo.fetch_rows(conn, job["id"])
    if taxonomy is None:
        try:
            from shared.taxon_groups import taxonomy_for_tvks
            taxonomy = taxonomy_for_tvks(r.get("species_tvk") for r in rows)
        except Exception as e:          # commit without; say so (the backfill script fills later)
            taxonomy, taxonomy_error = {}, str(e)
    for row in rows:
        reason = _eligibility(row)
        if reason == "no_species":
            skipped_species += 1
            continue
        if reason == "no_date":
            skipped_date += 1
            continue
        if reason == "bad_date":
            skipped_bad_date += 1
            continue
        tax = taxonomy.get(row.get("species_tvk") or "") or {}
        try:
            kwargs = build_kwargs_from_row(row, job, embargo_until, tax)
            new_id = model.create(observation_cls(**kwargs))
        except Exception as e:
            error = f"{row.get('species_name')}: {e}"
            break
        if not new_id:
            error = f"{row.get('species_name')}: Observatum did not return a record id"
            break
        if not (row.get("species_tvk") or "").strip():
            unresolved += 1  # committed anyway (species_name is the required field), but flagged
        if date_utils.is_future(row.get("date")):
            future += 1
        try:
            db.execute_main_write(
                "UPDATE observations SET sub_location=?, trap_number=?, visit_number=?, import_notes=?, "
                "superfamily=?, taxonomic_sort_key=? WHERE id=?",
                (row.get("sub_location") or None, row.get("trap_number") or None,
                 row.get("visit_number") or None, batch,
                 tax.get("superfamily"), tax.get("taxonomic_sort_key"), new_id),
            )
            if kwargs.get("embargo_until"):
                # The iRecord export excludes a record only when embargo_status is
                # 'Active' AND embargo_until is in the future. Setting the date alone
                # left the first committed batch uploadable (found 2 October 2026).
                db.execute_main_write(
                    "UPDATE observations SET embargo_status='Active' WHERE id=?", (new_id,))
        except Exception as e:
            # the record IS written: take it out of staging so a retry cannot double it
            error = f"{row.get('species_name')} was written (id {new_id}) but its survey " \
                    f"fields or embargo were not: {e}"
            repo.delete_row(conn, row["id"])
            committed += 1
            break
        repo.delete_row(conn, row["id"])
        committed += 1

    remaining = repo.row_count(conn, job["id"])
    if remaining == 0 and not repo.is_personal(job):
        repo.update_job(conn, job["id"], status="committed")
    return {
        "committed": committed,
        "skipped_species": skipped_species,
        "skipped_date": skipped_date,
        "skipped_bad_date": skipped_bad_date,
        "unresolved": unresolved,
        "future": future,
        "remaining": remaining,
        "batch": batch,
        "error": error,
        "taxonomy_error": taxonomy_error,
    }


def export_job(conn, job: Dict, filepath: str, columns) -> int:
    """Write ALL of the job's staging rows to a CSV (the user's data to take), return count."""
    rows = repo.fetch_rows(conn, job["id"])
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([label for (_, label, _, _) in columns])
        for row in rows:
            w.writerow([("" if row.get(key) is None else row.get(key)) for (key, _, _, _) in columns])
    return len(rows)


def _clear_rows(conn, job: Dict) -> int:
    rows = repo.fetch_rows(conn, job["id"])
    for row in rows:
        repo.delete_row(conn, row["id"])
    return len(rows)


def export_and_discard(conn, job: Dict, filepath: str, columns) -> int:
    n = export_job(conn, job, filepath, columns)
    _clear_rows(conn, job)
    if not repo.is_personal(job):
        repo.update_job(conn, job["id"], status="exported")
    return n


def discard_job(conn, job: Dict) -> int:
    """Delete the job's staging rows. Commercial/named jobs are marked discarded;
    the canonical standing Personal job stays active."""
    n = _clear_rows(conn, job)
    if not repo.is_personal(job):
        repo.update_job(conn, job["id"], status="discarded")
    return n
