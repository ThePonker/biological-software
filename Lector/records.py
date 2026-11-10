"""Extracted records: what a BHL page says, typed in by you (Round 15b).

Plain functions over an open connection; service.py is the public API. A record keeps a
copy of the page's citation, so it stays whole if the page later leaves a search. Removing
a record deletes that one row only, after a conn.backup() (removal.backup_database).

The CSV (export_csv) uses the headings scripts/import_contributed.py finds its columns by
(species, date, site, grid, recorder, determiner, count, sex, stage, notes), plus extra
columns the importer ignores and a data_reference column, "BHL: <short citation>".
"""
import csv
import datetime
from pathlib import Path

from shared import osgb

from . import removal
from .store import now

FIELDS = ("species", "species_tvk", "date_printed", "day", "month", "year", "place",
          "vice_county", "grid_ref", "recorder", "determiner", "count", "sex", "stage",
          "comment", "citation", "source_title", "source_volume", "source_page",
          "source_year", "bhl_url")
TEXT = ("species", "species_tvk", "date_printed", "place", "recorder", "determiner", "count",
        "sex", "stage", "comment", "citation", "source_title", "source_volume", "source_page",
        "bhl_url")
INTS = ("day", "month", "year", "vice_county", "source_year")
FILTER_SQL = {"search_id": "search_id=?", "species": "species=? COLLATE NOCASE",
              "year": "year=?"}
CSV_COLUMNS = ("species", "date", "site", "grid ref", "recorder", "determiner", "count", "sex",
               "stage", "notes", "date as printed", "vice county", "source citation",
               "BHL page URL", "data_reference")


def _num(value, name, low, high):
    if value in (None, ""):
        return None
    try:
        n = int(str(value).strip())
    except ValueError:
        raise ValueError(f"{name} must be a whole number.") from None
    if not low <= n <= high:
        raise ValueError(f"{name} must be between {low} and {high}.")
    return n


def clean(fields):
    """The fields as stored: text trimmed ('' -> None), numbers checked, the grid reference
    validated with shared.osgb. ValueError carries a plain message."""
    f = {k: fields.get(k) for k in FIELDS}
    for k in TEXT:
        v = " ".join(str(f[k]).split()) if f[k] not in (None, "") else None
        f[k] = v or None
    if not f["species"]:
        raise ValueError("Type the species the page names.")
    f["day"] = _num(f["day"], "Day", 1, 31)
    f["month"] = _num(f["month"], "Month", 1, 12)
    f["year"] = _num(f["year"], "Year", 1000, datetime.date.today().year)
    f["vice_county"] = _num(f["vice_county"], "Vice county", 1, 112)
    f["source_year"] = _num(f["source_year"], "Source year", 1000, 2200)
    if f["day"] and not (f["month"] and f["year"]):
        raise ValueError("A day needs a month and a year too.")
    if f["month"] and not f["year"]:
        raise ValueError("A month needs a year too.")
    if f["day"]:
        try:
            datetime.date(f["year"], f["month"], f["day"])
        except ValueError:
            raise ValueError("That day does not exist in that month.") from None
    if f["grid_ref"]:
        ref = "".join(str(f["grid_ref"]).split()).upper()
        if osgb.gridref_to_en(ref) is None:
            raise ValueError(f"“{f['grid_ref']}” is not a grid reference Lector can read "
                             "(for example SP580207).")
        f["grid_ref"] = ref
    return f


def short_citation(rec):
    """'Entomologist's monthly magazine, v.7, p. 81 (1870)' from the record's source fields."""
    bits = [rec.get("source_title"), rec.get("source_volume"), rec.get("source_page")]
    text = ", ".join(b for b in bits if b) or rec.get("citation") or "BHL"
    y = rec.get("source_year")
    return f"{text} ({y})" if y and str(y) not in text else text


def iso_date(rec):
    """The date as Observatum reads it: 1873-06-14, 1873-06 or 1873; '' when no year."""
    y, m, d = rec.get("year"), rec.get("month"), rec.get("day")
    if not y:
        return ""
    if m and d:
        return f"{y:04d}-{m:02d}-{d:02d}"
    return f"{y:04d}-{m:02d}" if m else f"{y:04d}"


def add(conn, page_id, search_id, fields):
    f = clean(fields)
    stamp = now()
    cols = ("page_id", "search_id") + FIELDS + ("created", "updated")
    cur = conn.execute(
        f"INSERT INTO extracted_records ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
        [page_id, search_id] + [f[k] for k in FIELDS] + [stamp, stamp])
    conn.commit()
    return cur.lastrowid


def get(conn, record_id):
    r = conn.execute("SELECT * FROM extracted_records WHERE record_id=?", (record_id,)).fetchone()
    if r is None:
        raise KeyError(f"No record {record_id}")
    return dict(r)


def update(conn, record_id, fields):
    get(conn, record_id)
    f = clean(fields)
    sets = ", ".join(f"{k}=?" for k in FIELDS) + ", updated=?"
    conn.execute(f"UPDATE extracted_records SET {sets} WHERE record_id=?",
                 [f[k] for k in FIELDS] + [now(), record_id])
    conn.commit()


def listing(conn, search_id=None, species=None, year=None):
    """Records (newest first), optionally for one search / species / year; each with
    'search_name' (None when the search has since been deleted)."""
    where, vals = [], []
    for key, v in (("search_id", search_id), ("species", species), ("year", year)):
        if v not in (None, ""):
            where.append("r." + FILTER_SQL[key])
            vals.append(v)
    q = ("SELECT r.*, s.name AS search_name FROM extracted_records r"
         " LEFT JOIN saved_searches s USING(search_id)"
         + (" WHERE " + " AND ".join(where) if where else "")
         + " ORDER BY r.created DESC, r.record_id DESC")
    return [dict(r) for r in conn.execute(q, vals)]


def filter_choices(conn):
    """What the filters offer: searches that have records, species, years."""
    return {
        "searches": [dict(r) for r in conn.execute(
            "SELECT DISTINCT r.search_id, COALESCE(s.name, '(deleted search)') AS name"
            " FROM extracted_records r LEFT JOIN saved_searches s USING(search_id)"
            " WHERE r.search_id IS NOT NULL ORDER BY name")],
        "species": [r[0] for r in conn.execute(
            "SELECT DISTINCT species FROM extracted_records ORDER BY species COLLATE NOCASE")],
        "years": [r[0] for r in conn.execute(
            "SELECT DISTINCT year FROM extracted_records WHERE year IS NOT NULL ORDER BY year")]}


def remove(conn, record_id, backup_dir):
    """Back up (lector_pre_remove_record_<time>.db), then delete that one row."""
    get(conn, record_id)
    dest = removal.backup_database(conn, backup_dir, "remove_record")
    conn.execute("DELETE FROM extracted_records WHERE record_id=?", (record_id,))
    conn.commit()
    return {"record_id": record_id, "backup": str(dest)}


def csv_row(rec):
    """One export row (see CSV_COLUMNS). A count that is not a whole number goes to the
    notes, because the importer reads that column as a number."""
    count = (rec.get("count") or "").strip()
    notes = [rec.get("comment")]
    if count and not count.isdigit():
        notes.append(f"Count as printed: {count}")
    if rec.get("date_printed"):
        notes.append(f"Date as printed: {rec['date_printed']}")
    return {
        "species": rec["species"], "date": iso_date(rec), "site": rec.get("place") or "",
        "grid ref": rec.get("grid_ref") or "", "recorder": rec.get("recorder") or "",
        "determiner": rec.get("determiner") or "", "count": count if count.isdigit() else "",
        "sex": rec.get("sex") or "", "stage": rec.get("stage") or "",
        "notes": " | ".join(n for n in notes if n),
        "date as printed": rec.get("date_printed") or "",
        "vice county": rec.get("vice_county") or "",
        "source citation": rec.get("citation") or "", "BHL page URL": rec.get("bhl_url") or "",
        "data_reference": "BHL: " + short_citation(rec)}


def export_csv(records, path):
    """Write the records as CSV (UTF-8 with a BOM, so Excel reads the accents)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        w.writeheader()
        for r in records:
            w.writerow(csv_row(r))
    return {"path": str(path), "rows": len(records)}
