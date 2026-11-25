"""make_specimens -- specimens made straight from Data Entry rows or committed records (25 Nov 2026).

Wil types up identified records, then decides which individuals he keeps as pinned specimens.
This makes those specimens from the records instead of re-typing each one in Add Specimen.
No Qt (the review screen is shared/make_specimens_dialog.py).

    load_rows(conn, row_ids, job)    candidates from STAGED Data Entry rows (not yet committed)
    load_records(conn, record_ids)   candidates from COMMITTED observations
    make_plan(cands, choices)        what would be written (raises ValueError on a bad number)
    describe(plan)                   the preview text
    apply(db_path, plan, linked)     away check -> backup -> ONE transaction -> read back

A candidate is a dict: kind ("row" | "record"), id, species_name, species_tvk, date, date_note,
grid_ref, site_name, sex, determiner, quantity, max (the most that can be made: the row's No.,
1 when blank), existing (specimens already made from it), refused (why it cannot be made, or
None), fields (the record-derived specimen columns), order_name.

Rules (Wil, 25 Nov 2026): one specimen per row by default, up to the row's No.; sex comes from the
row. A staged row's specimens are written with an origin of "made_from_row" in staging_specimens,
so at commit they take the committed record's fields (shared/specimen_staging.sync_from_record)
and are linked to it; a deleted row lets them go. Every job links (Personal jobs commit too); a
row sent to iRecord instead never commits, so its specimen waits in Specimens to check. Preparation, condition,
storage, drawer and notes are Wil's and are never touched by any later sync. No labels.
"""
from __future__ import annotations

import sqlite3
from typing import Callable, Dict, List, Optional

from shared import specimen_staging
from shared.specimen_vocab import default_prep_for_order, specimen_sex

CURATORIAL = ("preparation_type", "condition", "storage_location", "drawer_number", "notes")
_VAGUE = {"O": "a month", "Y": "a year"}


class MakeRefused(Exception):
    """Nothing was written (away mode, backup failed, or the write failed and was rolled back)."""


def is_linked_job(job: Optional[Dict]) -> bool:
    """Do specimens made from this job's rows get linked at commit? Yes for every job: Personal
    jobs commit like commercial ones (14 Oct 2026). A Personal row sent to iRecord instead never
    commits here, so its specimen simply stays without a field record (Specimens to check)."""
    return True


def _repo():
    try:
        from src.repositories.specimen_repository import SpecimenRepository
    except ImportError:                                    # outside Observatum (tests, scripts)
        from Observatum.src.repositories.specimen_repository import SpecimenRepository
    return SpecimenRepository


def _max_number(quantity) -> int:
    """The most specimens a row can make: its No.; 1 when blank or unreadable."""
    from DataEntry.commit_service import read_qty
    n = read_qty(quantity)
    return n if n and n >= 1 else 1


def _date_note(iso_date: str, date_type: Optional[str]) -> str:
    kind = _VAGUE.get(date_type or "D")
    if date_type in (None, "", "D"):
        return ""
    return (f"the date is {kind or 'a date range'}: stored as its first day ({iso_date}), "
            "as the record is")


def _vc_for_row(vc_service, row: Dict, kwargs: Dict) -> None:
    """The VC the record will get at commit (shared/vc_rule.py + commit_service's own check)."""
    from DataEntry.commit_service import _staged_vc_fits
    from shared.vc_rule import vc_for_grid_ref
    if not (vc_service and (row.get("grid_ref") or "").strip()):
        return
    placed = vc_for_grid_ref(vc_service, row["grid_ref"])
    if placed and placed[0] is not None and not _staged_vc_fits(
            vc_service, row["grid_ref"], kwargs.get("vc_number")):
        kwargs["vc_number"], kwargs["vice_county"] = placed


def _left(quantity, existing: int) -> int:
    """How many more can be made: the No. (1 when blank) less those already made (review 25 Nov)."""
    return max(_max_number(quantity) - int(existing or 0), 0)


def _still_there(conn, specimen_ids) -> int:
    """How many of these specimen ids still exist (a link to a deleted specimen is not counted)."""
    ids = [int(i) for i in specimen_ids]
    if not ids:
        return 0
    return conn.execute(f"SELECT COUNT(*) FROM specimens WHERE id IN ({','.join('?' * len(ids))})",
                        ids).fetchone()[0]


def _candidate(kind, rid, fields, **kw) -> Dict:
    return {"kind": kind, "id": rid, "fields": fields, "refused": None, "date_note": "",
            "species_name": fields.get("species_name"), "species_tvk": fields.get("species_tvk"),
            "grid_ref": fields.get("grid_ref"), "site_name": fields.get("site_name"),
            "sex": fields.get("sex"), "determiner": fields.get("determiner"),
            "order_name": fields.get("order_name"), **kw}


def _refuse_if_unplaceable(c: Dict) -> None:
    f = c["fields"]
    if not c["refused"] and c["max"] < 1:
        c["refused"] = (f"already has {c['existing']} specimen(s), as many as its No. allows"
                        if c["existing"] else "nothing left to make")
    elif not c["refused"] and not (f.get("species_tvk") or "").strip():
        c["refused"] = "no species match (no TVK): pick the species in Data Entry first"
    elif not c["refused"] and f.get("taxonomic_sort_key") is None:
        c["refused"] = ("UKSI gives this species no place in the collection (no sort position), "
                        "so it would be invisible in Insect Collection")
    elif not c["refused"] and not f.get("date_collected"):
        c["refused"] = "no readable date"


def load_rows(conn, row_ids, job: Dict, taxonomy: Optional[Dict] = None, uksi_path=None,
              vc_service=None) -> List[Dict]:
    """Candidates from staged rows (grid order). The species, taxonomy, date and VC are worked out
    by commit_service.row_kwargs / taxonomy_with_synonyms, so they are what the record will get."""
    from DataEntry import commit_service as cs
    from DataEntry import date_utils
    from DataEntry import staging_repo as repo
    want = {int(i) for i in row_ids}
    rows = [r for r in repo.fetch_rows(conn, job["id"]) if r["id"] in want]
    tax_error = None
    if taxonomy is None:
        try:
            taxonomy = cs.taxonomy_with_synonyms(rows, uksi_path)
        except Exception as e:                           # UKSI unreadable: say so, refuse below
            taxonomy, tax_error = {}, str(e)
    out = []
    for row in rows:
        kw, tax, _why = cs.row_kwargs(row, job, None, taxonomy)
        _vc_for_row(vc_service, row, kw)
        fields = {"species_name": kw["species_name"], "species_tvk": kw["species_tvk"],
                  "common_name": kw.get("common_name"), "order_name": kw.get("order_name"),
                  "family": kw.get("family"), "taxon_group": kw.get("taxon_group"),
                  "superfamily": tax.get("superfamily"), "subfamily": tax.get("subfamily"),
                  "taxonomic_sort_key": tax.get("taxonomic_sort_key"),
                  "date_collected": kw.get("date"), "grid_ref": kw.get("grid_ref"),
                  "vice_county": kw.get("vice_county"), "vc_number": kw.get("vc_number"),
                  "site_name": kw.get("site_name"), "collector": kw.get("recorder"),
                  "determiner": kw.get("determiner"), "sex": specimen_sex(kw.get("sex"))}
        existing = _still_there(conn, specimen_staging.for_row(conn, row["id"]))
        c = _candidate("row", row["id"], fields, quantity=row.get("quantity"),
                       max=_left(row.get("quantity"), existing), existing=existing,
                       date=date_utils.to_display(row.get("date")))
        if cs.is_flagged(row):
            c["refused"] = "marked To check (not determined yet)"
        elif row.get("date") and not date_utils.is_readable(row.get("date")):
            c["refused"] = "the date cannot be read"
        elif tax_error and (fields["species_tvk"] or "").strip():
            c["refused"] = f"UKSI could not be read ({tax_error})"
        c["date_note"] = _date_note(fields["date_collected"] or "", date_utils.date_type(row.get("date")))
        _refuse_if_unplaceable(c)
        out.append(c)
    return out


def load_records(conn, record_ids, taxonomy: Optional[Dict] = None, uksi_path=None) -> List[Dict]:
    """Candidates from committed observations, in the order given."""
    from DataEntry import date_utils
    ids = [int(i) for i in dict.fromkeys(record_ids)]
    found: Dict[int, Dict] = {}
    for i in range(0, len(ids), 500):
        part = ids[i:i + 500]
        cur = conn.execute(f"SELECT * FROM observations WHERE id IN ({','.join('?' * len(part))})", part)
        names = [d[0] for d in cur.description]
        for r in cur:
            found[r[names.index("id")]] = dict(zip(names, tuple(r)))
    have = {}
    for i in range(0, len(ids), 500):
        part = ids[i:i + 500]
        have.update(dict(conn.execute(
            f"SELECT observation_id, COUNT(*) FROM specimens WHERE observation_id IN "
            f"({','.join('?' * len(part))}) GROUP BY observation_id", part)))
    need = [r["species_tvk"] for r in found.values()
            if r.get("species_tvk") and r.get("taxonomic_sort_key") is None]
    if need and taxonomy is None:
        try:
            from shared.taxon_groups import taxonomy_for_tvks
            taxonomy = taxonomy_for_tvks(need, uksi_path)
        except Exception:
            taxonomy = {}
    out = []
    for rid in ids:
        rec = found.get(rid)
        if rec is None:
            continue
        fields = {sc: rec.get(rc) for rc, sc in specimen_staging.RECORD_TO_SPECIMEN}
        fields["sex"] = specimen_sex(fields.get("sex"))
        if fields.get("taxonomic_sort_key") is None and fields.get("species_tvk"):
            t = (taxonomy or {}).get(fields["species_tvk"]) or {}
            for k in ("superfamily", "subfamily", "taxonomic_sort_key"):
                fields[k] = fields.get(k) or t.get(k)
        existing = int(have.get(rid, 0))
        c = _candidate("record", rid, fields, quantity=rec.get("quantity"),
                       max=_left(rec.get("quantity"), existing), existing=existing,
                       date=date_utils.to_display(rec.get("date")))
        c["date_note"] = _date_note(fields.get("date_collected") or "", rec.get("date_type"))
        _refuse_if_unplaceable(c)
        out.append(c)
    return out


DEFAULT_CONDITION = "Good"          # a freshly made specimen starts as Good (Wil, 25 Nov 2026)


def default_choice(c: Dict) -> Dict:
    """What the review screen starts with: 1 (0 when it already has specimens or is refused),
    the preparation the order is usually kept as, condition Good (Wil, 25 Nov 2026)."""
    n = 0 if c["refused"] or c["existing"] else 1
    return {"n": n, "preparation_type": default_prep_for_order(c.get("order_name")),
            "condition": DEFAULT_CONDITION, "storage_location": "", "drawer_number": "", "notes": ""}


def make_plan(cands: List[Dict], choices: Dict) -> List[Dict]:
    """[{cand, specimens: [specimen dicts]}] for every candidate with a number above 0.
    choices: {(kind, id): {"n", preparation_type, condition, storage_location, drawer_number,
    notes}}. A refused row, or a number outside 0..max, raises ValueError (nothing is planned)."""
    plan = []
    for c in cands:
        ch = {**default_choice(c), **choices.get((c["kind"], c["id"]), {})}
        n = int(ch["n"])
        if n == 0:
            continue
        if c["refused"]:
            raise ValueError(f"{c['species_name'] or 'a row'} cannot be made: {c['refused']}")
        if not 1 <= n <= c["max"]:
            raise ValueError(f"{c['species_name']}: make 1 to {c['max']} specimens, not {n}")
        one = {**c["fields"], **{k: (ch.get(k) or "").strip() for k in CURATORIAL}}
        if c["kind"] == "record":
            one["observation_id"] = c["id"]
        plan.append({"cand": c, "specimens": [dict(one) for _ in range(n)]})
    return plan


def describe(plan: List[Dict], linked: bool = True) -> str:
    """The preview: what will be written, and anything Wil should know first."""
    total = sum(len(p["specimens"]) for p in plan)
    kind = plan[0]["cand"]["kind"] if plan else "row"
    lines = [f"{total} specimen(s) from {len(plan)} {kind}(s):"]
    for p in plan:
        c = p["cand"]
        one = p["specimens"][0]       # what goes on the specimen: rec., det. (Wil, 25 Nov) and curation
        kept = ", ".join(v for v in (one.get("preparation_type"), one.get("condition"),
                                     one.get("storage_location"),
                                     f"drawer {one['drawer_number']}" if one.get("drawer_number") else "")
                         if v)
        parts = [f"{len(p['specimens'])} x {c['species_name']}", c["date"] or "", c["grid_ref"] or "",
                 c["sex"] or "", f"rec. {one.get('collector') or '(none)'}",
                 f"det. {one.get('determiner') or '(none)'}", kept]
        lines.append("  " + "   ".join(x for x in parts if x))        # one line per row (Wil, 25 Nov)
        if c["date_note"]:
            lines.append(f"      note: {c['date_note']}")
        if c["existing"]:
            lines.append(f"      already has {c['existing']} specimen(s)")
    if kind == "record":
        lines.append("They are linked to their records now.")
    elif linked:
        lines.append("At commit they are linked to the record and take its final details; "
                     "your preparation, storage and notes are never changed. (A row sent to "
                     "iRecord instead is never committed here: its specimen waits in Specimens "
                     "to check.)")
    else:
        lines.append("Made WITHOUT a field record link (Personal job): they will appear in "
                     "Specimens to check.")
    return "\n".join(lines)


def _default_backup(db_path) -> bool:
    from shared.backup_service import backup_file_written
    return bool(backup_file_written(db_path, "pre-make-specimens"))   # = backup_main_only on the live db


def apply(db_path, plan: List[Dict], linked: bool = True,
          backup: Optional[Callable] = None) -> Dict:
    """Write the plan. Refuses in away mode, backs up (a failure writes nothing), then writes the
    specimens and their staging_specimens rows in ONE transaction and reads them back.
    Returns {"ids": [specimen ids], "by_source": {(kind, id): [ids]}}. Raises MakeRefused."""
    from shared.away_mode import away_active
    from shared.db_open import connect_ro, connect_rw
    if not plan:
        raise MakeRefused("There is nothing to make.")
    if away_active():
        raise MakeRefused("This is a read-only copy (away mode), so nothing was written. "
                          "Make the specimens on the desktop.")
    try:
        ok = (backup or _default_backup)(db_path)
    except Exception as e:  # noqa: BLE001
        raise MakeRefused(f"Backup unavailable, so nothing was written.\n{e}") from e
    if not ok:
        raise MakeRefused("The backup failed, so nothing was written.")
    insert = _repo().build_insert
    by_source: Dict = {}
    conn = connect_rw(db_path)
    conn.isolation_level = None                          # explicit BEGIN / COMMIT below
    try:
        conn.execute("BEGIN IMMEDIATE")
        have_cols = {r[1] for r in conn.execute("PRAGMA table_info(specimens)")}
        for p in plan:
            c = p["cand"]
            table, col = ("entry_staging", "id") if c["kind"] == "row" else ("observations", "id")
            if not conn.execute(f"SELECT 1 FROM {table} WHERE {col} = ?", (c["id"],)).fetchone():
                raise ValueError(f"{c['species_name']}: the {c['kind']} is no longer there")
            ids = []
            for spec in p["specimens"]:
                sql, values = insert({k: v for k, v in spec.items() if k in have_cols})
                ids.append(conn.execute(sql, values).lastrowid)
            by_source[(c["kind"], c["id"])] = ids
            if c["kind"] == "row" and linked:
                specimen_staging.add(conn, c["id"], ids, specimen_staging.ORIGIN_MADE)
        conn.execute("COMMIT")
    except Exception as e:  # noqa: BLE001 -- any failure: roll back, say so, never a traceback
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise MakeRefused(f"Nothing was written.\n\n{e}") from e
    finally:
        conn.close()
    ids = [i for v in by_source.values() for i in v]
    ro = connect_ro(db_path)
    try:
        got = sum(ro.execute(f"SELECT COUNT(*) FROM specimens WHERE id IN ({','.join('?' * len(ids))})",
                             ids).fetchone())
    finally:
        ro.close()
    if got != len(ids):
        raise MakeRefused(f"Read-back found {got} of {len(ids)} specimens: check Insect Collection.")
    return {"ids": ids, "by_source": by_source}


__all__ = ["MakeRefused", "CURATORIAL", "is_linked_job", "load_rows", "load_records",
           "default_choice", "make_plan", "describe", "apply"]
