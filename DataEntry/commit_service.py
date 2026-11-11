"""The three job exits: commit to Observatum, export-and-discard, discard.

commit builds an Observation from each eligible staging row and writes it via Observatum's
canonical ObservationModel.create() (the survey columns, batch stamp and taxonomy columns go in
the same INSERT via create(extra=...), R18 B5), reusing the same pattern/guard as write_service. Job-level values
(record_type from mode, client, project) and the embargo come in at commit time.

build_kwargs_from_row is pure and unit-tested. commit_job takes an injectable observation_cls
so it can be exercised against a stand-in on machines without Observatum's src.
"""
from __future__ import annotations

import csv
from typing import Optional, Dict

from DataEntry import staging_repo as repo
from DataEntry.write_service import _ALLOWED_FIELDS, CERTAINTY


# What a row named by a UKSI synonym is stored as (R16, 10 Nov 2026). Both rules exist in the
# suite: "recommended" is the import wizards' (shared/species_lookup.lookup_names: the current
# UKSI name and TVK, the name as typed in the notes); "as_recorded" is Wil's 11 Oct 2026 rule
# for existing records (scripts/_oneoff/fix_tvks_not_in_uksi_20261011.py: keep the name, move
# only the TVK). In both the TVK, common name and taxonomy come from the recommended taxon.
# To be decided by Wil.
SYNONYM_NAME_RULE = "recommended"        # "recommended" | "as_recorded"


def synonym_status(row: Dict, tax: Dict) -> Optional[str]:
    """Does this row's name make it a UKSI synonym to be written under the recommended taxon?

    tax: the row's taxonomy entry with a "recommended" taxon (taxonomy_with_synonyms). Returns
    None (no recommended taxon), "rename" (go ahead), or why not -- the row is then written
    exactly as staged:
      "differ"    the row's name is not the name UKSI gives that TVK (the species was changed
                  and the TVK left, or the TVK is a vernacular-name row);
      "ambiguous" that name points to more than one recommended taxon (a homonym);
      "qualified" 'agg.', 's.l.' or 's.str.' (another taxon concept than the synonym's), or a
                  'cf.' that cannot be carried onto the recommended name cleanly."""
    rec = (tax or {}).get("recommended")
    if not rec:
        return None
    from shared.species_lookup import parse_qualifier
    from shared.taxon_groups import _plain_name
    qualifier, bare = parse_qualifier(row.get("species_name") or "")
    if not rec.get("name") or _plain_name(bare) != _plain_name(rec["name"]):
        return "differ"
    if int(rec.get("targets") or 1) > 1:
        return "ambiguous"
    if SYNONYM_NAME_RULE == "recommended" and _name_with_qualifier(
            rec.get("scientific_name") or "", qualifier) is None:
        return "qualified"
    if SYNONYM_NAME_RULE != "recommended" and qualifier in ("agg.", "s.l.", "s.str."):
        return "qualified"
    return "rename"


def _name_with_qualifier(name: str, qualifier: Optional[str]) -> Optional[str]:
    """The recommended name carrying the entered 'cf.'; None when that is not clean (agg.,
    s.l. and s.str. are not carried; cf. only onto a two-word name)."""
    if not qualifier:
        return name
    words = name.split()
    if qualifier == "cf." and len(words) == 2:
        return f"{words[0]} cf. {words[1]}"
    return None


def build_kwargs_from_row(row: Dict, job: Dict, embargo_until: Optional[str] = None,
                          taxonomy: Optional[Dict] = None) -> Dict:
    """Map one staging row + its job to Observatum Observation kwargs (pure).

    taxonomy: this row's TVK in shared.taxon_groups.taxonomy_for_tvks() -- kingdom, rank and
    taxon group from UKSI (9 Oct 2026; commits wrote none of them before, 1,440 records).
    Without it the group still comes from the row's own order and family. When the entry
    carries a "recommended" taxon ({tvk, scientific_name, common_name}: the row's TVK is a UKSI
    synonym, see taxonomy_with_synonyms) the record is written under the recommended name and
    TVK with its taxonomy, and the name as entered goes to identification_remarks."""
    qty = read_qty(row.get("quantity")) or 1     # an unreadable No. never gets here (DE9)

    vc_number = read_vc(row.get("vc_number"))[1]   # an unreadable VC never gets here

    mode = job.get("mode") or "Personal"
    is_commercial = mode.lower().startswith("comm")

    from DataEntry import date_utils
    from shared.taxon_groups import taxon_group
    # a year or month-year commits as the period's first day with its date type (DE1)
    iso_date = date_utils.start_iso(row.get("date")) or row.get("date")
    tax = taxonomy or {}
    name = (row.get("species_name") or "").strip()
    tvk, common = row.get("species_tvk"), row.get("common_name")
    order, family = row.get("order_name"), row.get("family")
    remarks = None
    rec = tax.get("recommended")
    if rec and rec.get("tvk") and rec.get("scientific_name") and synonym_status(row, tax) == "rename":
        # The row's name is a non-recommended name (a UKSI synonym) of that TVK: see
        # SYNONYM_NAME_RULE. The TVK, common name, order and family are the recommended taxon's.
        from shared.species_lookup import parse_qualifier
        stored = rec["scientific_name"]
        if SYNONYM_NAME_RULE == "recommended":
            stored = _name_with_qualifier(stored, parse_qualifier(name)[0])
            if " ".join(name.lower().split()) != " ".join(stored.lower().split()):
                remarks = f"Entered as '{name}' (UKSI synonym of '{rec['scientific_name']}')"
            name = stored
        else:
            remarks = f"Recorded name '{name}' is a UKSI synonym of '{stored}': TVK is the recommended taxon's"
        tvk = rec["tvk"]
        common = rec.get("common_name") or common
        order, family = tax.get("order_name") or order, tax.get("family") or family
    elif rec:
        tax = {}            # not a synonym of this name: as staged, no taxonomy of another taxon

    kwargs = {
        "species_name": name,
        "species_tvk": tvk,
        "common_name": common,
        "order_name": order,
        "family": family,
        "identification_remarks": remarks,
        "taxon_rank": tax.get("taxon_rank") or row.get("taxon_rank"),
        "kingdom": tax.get("kingdom"),
        "taxon_group": tax.get("taxon_group") or taxon_group(order, family),
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
        # The iRecord export excludes a record only when embargo_status is 'Active' AND
        # embargo_until is in the future: both are written in the one create (R12 M1)
        "embargo_status": "Active" if (is_commercial and embargo_until) else None,
    }
    # Lat/long of the grid square's centre, with the OSGB36 -> WGS84 shift (9 Oct 2026);
    # commits used to leave it blank (1,301 records)
    from shared.osgb import gridref_to_wgs84
    ll = gridref_to_wgs84(kwargs["grid_ref"]) if kwargs["grid_ref"] else None
    if ll:
        kwargs["latitude"], kwargs["longitude"] = ll
        kwargs["geodetic_datum"] = "WGS84"
    return {k: v for k, v in kwargs.items() if k in _ALLOWED_FIELDS}


def read_qty(value) -> Optional[int]:
    """The No. as a whole number of 1 or more; blank counts as 1; None when unreadable.

    A mistyped No. ('c.20', '0', '2x') used to become 1 without a word (review DE9).
    Now it stays in the cell, is flagged there, and the row stays in staging.
    """
    s = "" if value is None else str(value).strip()
    if s == "":
        return 1
    try:
        n = int(s)
    except ValueError:
        try:
            f = float(s)                       # '3.0' from a spreadsheet paste
        except ValueError:
            return None
        if not f.is_integer():
            return None
        n = int(f)
    return n if n >= 1 else None


def is_zero_qty(value) -> bool:
    """True for a No. of 0 -- a mistake to fix, never stored: Wil doesn't record absence
    (decision 8, 10 Oct 2026). read_qty() gives None for it, like an unreadable No."""
    s = "" if value is None else str(value).strip()
    try:
        return s != "" and float(s) == 0
    except ValueError:
        return False


VC_MAX = 113        # the Watsonian vice-counties of Britain, 1-112, and the Channel Isles


def read_vc(value) -> tuple:
    """(readable, the VC No. or None). Blank is readable (no VC); a whole number 1-113
    is the VC; anything else ('0', '41a', '200') is unreadable -- flagged in its cell and
    left in staging like an unreadable No. (review 10 Oct: '0' was committed as VC 0)."""
    s = "" if value is None else str(value).strip()
    if s == "":
        return True, None
    try:
        f = float(s)
    except ValueError:
        return False, None
    if not f.is_integer() or not 1 <= f <= VC_MAX:
        return False, None
    return True, int(f)


def is_flagged(row: Dict) -> bool:
    """Is the row marked "To check" (not determined yet)? A database without the column
    has no flags."""
    try:
        return int(row.get("check_flag") or 0) == 1
    except (TypeError, ValueError):
        return False


def _eligibility(row: Dict) -> Optional[str]:
    """Return None if committable, else a reason string."""
    from DataEntry import date_utils
    if is_flagged(row):
        return "to_check"          # marked "To check": held back on purpose, stays in staging
    if not (row.get("species_name") or "").strip():
        return "no_species"
    if not (row.get("date") or "").strip():
        return "no_date"
    if not date_utils.is_readable(row.get("date")):
        return "bad_date"          # '31/02/2026', 'summer' -- stays in staging (DE1)
    if read_qty(row.get("quantity")) is None:
        return "bad_qty"           # 'c.20', '0' -- stays in staging (DE9)
    if not read_vc(row.get("vc_number"))[0]:
        return "bad_vc"            # '0', '41a' -- stays in staging
    return None


# What makes two records "the same entry twice": every field below equal. Usually a
# sex split typed with the sex left "Not recorded", or a block of sheet re-entered.
# One definition, used here before commit and by scripts/check_data_entry_batches.py
# after it (fault F28, 8 Oct 2026).
DOUBLE_KEY = ("species_name", "date", "grid_ref", "method", "trap_number", "sex", "stage")


def uksi_names_for_rows(rows, uksi_path=None) -> Dict[str, set]:
    """{tvk: UKSI's names for it} for the rows' TVKs, for precommit_issues' name/TVK check
    (shared.taxon_groups.names_for_tvks). Raises on a UKSI failure; the caller skips the check."""
    from shared.taxon_groups import names_for_tvks
    return names_for_tvks(((r.get("species_tvk") or "").strip() for r in rows), uksi_path)


def _name_matches_tvk(name: str, names: set) -> bool:
    """Is the row's species name one of the names UKSI gives its TVK (recommended or synonym)?
    Qualifiers (cf., agg., s.l.) and subgenus brackets are ignored."""
    from shared.species_lookup import parse_qualifier, tidy
    from shared.taxon_groups import _plain_name
    name = tidy(name)
    return _plain_name(name) in names or _plain_name(parse_qualifier(name)[1]) in names


def precommit_issues(rows, uksi_names: Optional[Dict[str, set]] = None) -> Dict[str, list]:
    """What a commit would write with gaps or doubles in it (pure; backlog B8).

    rows: staging rows in grid order (repo.fetch_rows). Only rows commit would write
    (species and date present) are checked, plus 'unreadable date' for rows with a species
    and a date that cannot be read (those stay in staging). Returns {issue: [grid row
    numbers]} for 'unreadable date', 'count of 0', 'unreadable No.', 'unreadable VC No.', 'future date', 'no site', 'no grid ref', 'no VC',
    'no recorder', 'no TVK', 'name and TVK differ' (uksi_names, {tvk: UKSI's names for it},
    given: the TVK is UKSI's but the species name is not one of its names -- the species was
    changed and the TVK left from the old one; rows whose TVK UKSI does not hold are not judged),
    and 'double' (each later copy of a repeated entry, with the
    row it repeats), and 'to check (held back)' (rows marked To check, which commit leaves in
    staging on purpose and which are not checked for gaps), leaving out issues with no rows.
    """
    from DataEntry import date_utils
    issues = {"unreadable date": [], "count of 0": [], "unreadable No.": [], "unreadable VC No.": [],
              "future date": [], "no site": [], "no grid ref": [],
              "no VC": [], "no recorder": [], "no TVK": [], "name and TVK differ": [], "double": [],
              "to check (held back)": []}
    seen = {}
    for n, row in enumerate(rows, start=1):
        why = _eligibility(row)
        if why == "to_check":
            issues["to check (held back)"].append(n)     # deliberate: not a problem, but said
            continue
        if why == "bad_date":
            issues["unreadable date"].append(n)
        if why == "bad_qty":
            issues["count of 0" if is_zero_qty(row.get("quantity")) else "unreadable No."].append(n)
        if why == "bad_vc":
            issues["unreadable VC No."].append(n)
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
        elif uksi_names:
            known = uksi_names.get(str(row.get("species_tvk")).strip())
            if known and not _name_matches_tvk(row.get("species_name") or "", known):
                issues["name and TVK differ"].append(n)
        key = tuple(str(row.get(k) or "").strip().lower() for k in DOUBLE_KEY)
        if key in seen:
            issues["double"].append((n, seen[key]))
        else:
            seen[key] = n
    return {k: v for k, v in issues.items() if v}


def _photos_follow_row(conn, staging_id: int, new_id: int, problems: list, row: Dict) -> bool:
    """Bench photos (take 2, 14 Oct 2026): the row's photos leave _Bench for the species'
    Specimen folder and belong to its record (shared/bench_photos.file_on_commit). Never stops
    a commit (the record is already written); anything not done is listed in the summary
    ('photo_problems').
    True when the row's photo links are safe to let go of with the row (they are the record's
    now); False keeps them on the row (its delete must not drop them)."""
    try:
        from shared import bench_photos
        safe, notes = bench_photos.file_on_commit(conn, staging_id, row, new_id)
        problems.extend(notes)
        return safe
    except Exception as e:
        problems.append(f"row {staging_id} -> record {new_id}: {e}")
        return False


def _specimens_follow_row(conn, staging_id: int, new_id: int, problems: list) -> None:
    """Records made from specimens (14 Oct 2026): the row's specimens are linked to its new
    record (shared/specimen_staging.py). Never stops a commit; notes go in the summary."""
    try:
        from shared import specimen_staging
        problems.extend(specimen_staging.link_on_commit(conn, staging_id, new_id))
    except Exception as e:
        problems.append(f"row {staging_id} -> record {new_id}: specimens not linked ({e})")


def _out_of_staging(conn, row: Dict, new_id: int, release_photos: bool) -> Optional[str]:
    """Take a committed row out of staging. If that fails the record IS written, so the commit
    stops and says which row to delete by hand -- committing it again would write it twice
    (review 14 Oct 2026). None when done."""
    try:
        repo.delete_row(conn, row["id"], release_photos=release_photos)
        return None
    except Exception as e:
        return (f"{row.get('species_name')} was written (id {new_id}) but its row could not be "
                f"taken out of staging ({e}). Delete that row by hand before committing again, "
                "or it will be written twice")


def taxonomy_with_synonyms(rows, uksi_path=None) -> Dict[str, dict]:
    """{tvk: taxonomy} for the rows' TVKs (shared.taxon_groups.taxonomy_for_tvks), and for a
    TVK UKSI holds only as a synonym, the RECOMMENDED taxon's taxonomy under the synonym's TVK,
    with a "recommended" entry ({tvk, scientific_name, common_name}) that build_kwargs_from_row
    writes the record under. Raises on a UKSI failure (commit_job reports it)."""
    from shared.taxon_groups import recommended_for_tvks, taxonomy_for_tvks
    tvks = [(r.get("species_tvk") or "").strip() for r in rows]
    taxonomy = taxonomy_for_tvks(tvks, uksi_path)
    rec = recommended_for_tvks([t for t in tvks if t and t not in taxonomy], uksi_path)
    if rec:
        base = taxonomy_for_tvks([v["tvk"] for v in rec.values()], uksi_path)
        for tvk, v in rec.items():
            if v["tvk"] in base:
                taxonomy[tvk] = {**base[v["tvk"]], "recommended": v}
    return taxonomy


def commit_job(db, model, conn, job: Dict, embargo_until: Optional[str] = None,
               observation_cls=None, taxonomy: Optional[Dict] = None, uksi_path=None) -> Dict:
    """Write eligible staging rows into observations; delete the committed ones.

    Rows missing species or date, or with an unreadable date, are left in staging and
    reported. taxonomy ({tvk: ...}, shared.taxon_groups.taxonomy_for_tvks) is looked up
    when not given. A failure part-way stops the commit and is returned in 'error' with
    how many were written before it (DE4) -- never raised after the first write.
    Returns a summary dict.
    """
    if observation_cls is None:
        from src.models.observation import Observation as observation_cls  # noqa: N806

    from DataEntry.staging_repo import is_test_copy
    if is_test_copy(job):
        raise ValueError("this is a test copy of a job: it cannot be committed (discard it when "
                         "you have finished with it)")
    if (job.get("mode") or "").lower().startswith("comm") and not (job.get("project") or "").strip():
        # backstop for the grid's own check: no project means "(no project)" everywhere
        raise ValueError("this commercial job has no Project -- set it with Jobs > Edit details")

    committed = 0
    skipped_species = 0
    skipped_date = 0
    skipped_bad_date = 0
    skipped_bad_qty = 0
    skipped_zero_qty = 0           # a No. of 0: left in staging (decision 8)
    skipped_bad_vc = 0
    skipped_check = 0              # marked "To check": held back on purpose
    unresolved = 0
    synonyms = []                  # names written under their current UKSI TVK ("X -> Y")
    name_tvk_differ = []           # name is not its TVK's: written as staged
    ambiguous_names = []           # name is a homonym of several taxa: written as staged
    qualified_names = []           # agg./s.l./s.str./cf. not carried: written as staged
    future = 0
    error = None
    taxonomy_error = None
    from DataEntry import date_utils
    from datetime import datetime
    batch = 'DataEntry batch ' + datetime.now().isoformat(timespec='seconds')
    rows = repo.fetch_rows(conn, job["id"])
    committed_rows = []            # (staging row, new observation id) -- A3's iRecord file
    photo_problems = []            # bench photos whose link could not follow (row -> record)
    if taxonomy is None:
        try:
            taxonomy = taxonomy_with_synonyms(rows, uksi_path)
        except Exception as e:          # commit without; say so (the backfill script fills later)
            taxonomy, taxonomy_error = {}, str(e)
    for row in rows:
        reason = _eligibility(row)
        if reason == "to_check":
            skipped_check += 1
            continue
        if reason == "no_species":
            skipped_species += 1
            continue
        if reason == "no_date":
            skipped_date += 1
            continue
        if reason == "bad_date":
            skipped_bad_date += 1
            continue
        if reason == "bad_qty":
            if is_zero_qty(row.get("quantity")):
                skipped_zero_qty += 1
            else:
                skipped_bad_qty += 1
            continue
        if reason == "bad_vc":
            skipped_bad_vc += 1
            continue
        tax = taxonomy.get((row.get("species_tvk") or "").strip()) or {}
        why_not = synonym_status(row, tax)
        if why_not and why_not != "rename":       # written exactly as staged, and said so
            {"differ": name_tvk_differ, "ambiguous": ambiguous_names,
             "qualified": qualified_names}[why_not].append((row.get("species_name") or "").strip())
            tax = {}
        try:
            kwargs = build_kwargs_from_row(row, job, embargo_until, tax)
            # the survey fields, the batch stamp and the taxonomy columns go in the same INSERT
            # (R18 B5; they used to be written by a second UPDATE)
            new_id = model.create(observation_cls(**kwargs), extra={
                "sub_location": row.get("sub_location") or None,
                "trap_number": row.get("trap_number") or None,
                "visit_number": row.get("visit_number") or None,
                "import_notes": batch,
                "superfamily": tax.get("superfamily"),
                "taxonomic_sort_key": tax.get("taxonomic_sort_key"),
            })
        except Exception as e:
            error = f"{row.get('species_name')}: {e}"
            break
        if not new_id:
            error = f"{row.get('species_name')}: Observatum did not return a record id"
            break
        filing = row
        if tax.get("recommended"):
            # photos are filed under the record's species, not the synonym it was entered as
            filing = dict(row, species_name=kwargs["species_name"], species_tvk=kwargs["species_tvk"],
                          order_name=kwargs["order_name"], family=kwargs["family"])
            synonyms.append(f"{(row.get('species_name') or '').strip()} -> {kwargs['species_name']}"
                            + (f" ({kwargs['species_tvk']})" if SYNONYM_NAME_RULE != "recommended" else ""))
        if not (row.get("species_tvk") or "").strip():
            unresolved += 1  # committed anyway (species_name is the required field), but flagged
        if date_utils.is_future(row.get("date")):
            future += 1
        committed_rows.append((dict(row), new_id))
        safe = _photos_follow_row(conn, row["id"], new_id, photo_problems, filing)
        _specimens_follow_row(conn, row["id"], new_id, photo_problems)
        committed += 1
        gone = _out_of_staging(conn, row, new_id, safe)
        if gone:
            error = gone
            break

    remaining = repo.row_count(conn, job["id"])
    if remaining == 0 and not repo.is_personal(job):
        repo.update_job(conn, job["id"], status="committed")
    return {
        "committed": committed,
        "skipped_species": skipped_species,
        "skipped_date": skipped_date,
        "skipped_bad_date": skipped_bad_date,
        "skipped_bad_qty": skipped_bad_qty,
        "skipped_zero_qty": skipped_zero_qty,
        "skipped_bad_vc": skipped_bad_vc,
        "skipped_check": skipped_check,
        "unresolved": unresolved,
        "synonyms": synonyms,
        "name_tvk_differ": name_tvk_differ,
        "ambiguous_names": ambiguous_names,
        "qualified_names": qualified_names,
        "future": future,
        "remaining": remaining,
        "batch": batch,
        "error": error,
        "taxonomy_error": taxonomy_error,
        "committed_rows": committed_rows,
        "photo_problems": photo_problems,
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
