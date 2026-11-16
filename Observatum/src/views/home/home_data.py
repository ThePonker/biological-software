"""What the redesigned Home tab (Round 19, changed in Round 20) reads: the map's squares (recorded
or not), the last ten new species and the Personal year list. No Qt. Read-only: nothing here
writes to a database.

Every rule is imported, not copied:
  * the map's records come from the Mapping tab's own query builder (services/map_selection:
    build_query, counting_exclusions, fetch), grouped by grid reference, then squared by
    shared/maps/grid_squares (hectad = 10 km);
  * "new species" is ObservationRepository.get_new_species_first_records (the panel it replaces);
  * the year list counts exactly as the Personal Quick Stats card does (ObservationRepository.
    count_unique_species_by_year): the same species-counting switches (shared/species_counting:
    counted_clause, species_key_expr), record_type 'Personal', the year by strftime('%Y', date).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from shared.db_open import connect_ro
from shared.maps import grid_squares as gs
from shared.species_counting import counted_clause, species_key_expr
from shared.taxon_groups import group_for_record, group_label

from ...services import map_selection as ms

THIS_YEAR, ALL_YEARS, SELECTED = "year", "all", "species"
SOURCES = ["personal", "commercial"]          # "your records": Personal + Commercial observations
YEAR_PREFIX = "y:"                            # a single year in the map's Show list: "y:2024"


def choice_mode(data) -> Tuple[str, int]:
    """The map's Show choice as (mode, year): "y:2024" -> (THIS_YEAR, 2024) (THIS_YEAR is the
    one-year filter); "year" -> this calendar year; "all" / "species" as they are."""
    text = str(data or THIS_YEAR)
    if text.startswith(YEAR_PREFIX) and text[len(YEAR_PREFIX):].isdigit():
        return THIS_YEAR, int(text[len(YEAR_PREFIX):])
    return (text if text in (ALL_YEARS, SELECTED) else THIS_YEAR), date.today().year


def map_years(db_path) -> List[int]:
    """Every year with one of your records the map shows (Personal + Commercial, as
    hectad_squares; the species-counting switches apply), newest first. Read-only; run it off the GUI thread."""
    conn = connect_ro(db_path)
    try:
        rows = conn.execute(
            "SELECT DISTINCT strftime('%Y', date) FROM observations "
            "WHERE record_type IN ('Personal', 'Commercial') "
            f"AND date IS NOT NULL{counted_clause('observations', db=db_path)}").fetchall()
    finally:
        conn.close()
    return sorted({int(r[0]) for r in rows if r[0] and str(r[0]).isdigit()}, reverse=True)


def _filters(mode: str, year: int) -> "ms.MapFilters":
    # Home is the user's own overview (the Quick Stats cards count embargoed records too)
    if mode == THIS_YEAR:
        return ms.MapFilters(date_from=f"{year}-01-01", date_to=f"{year}-12-31",
                             include_embargoed=True)
    return ms.MapFilters(include_embargoed=True)


def _selection(mode: str, tvk: str, name: str) -> List[dict]:
    if mode != SELECTED:
        return []
    return [{"kind": "taxon", "tvk": tvk, "scientific_name": name, "rank": "species"}]


def hectad_squares(db_path, mode: str = THIS_YEAR, year: Optional[int] = None,
                   tvk: str = "", name: str = "") -> Dict[str, dict]:
    """{10 km square: {count}} for your Personal + Commercial observations that hold a record:
    one year (mode THIS_YEAR, `year`; default this year), all years, or one species (mode SELECTED, by TVK, old names included as in Mapping). One
    aggregate query (records per grid reference); records with a grid reference coarser than
    10 km are left out, as the Mapping tab leaves them out."""
    year = year or date.today().year
    selection = _selection(mode, tvk, name)
    if mode == SELECTED and not tvk:
        return {}
    ctx = ms.get_context(db_path) if selection else None
    where, params = ms.build_query("observations", selection, SOURCES, _filters(mode, year), ctx,
                                   counting=ms.counting_exclusions(db_path))
    conn = connect_ro(db_path)
    try:
        rows = conn.execute(f"SELECT grid_ref, COUNT(*) FROM observations WHERE {where} "
                            "GROUP BY grid_ref", params).fetchall()
    finally:
        conn.close()
    squares: Dict[str, dict] = {}
    for ref, n in rows:
        label = gs.square_for_ref(ref, gs.HECTAD)
        if label:
            squares.setdefault(label, {"count": 0})["count"] += int(n)
    return squares


def square_records(db_path, label: str, mode: str = THIS_YEAR, year: Optional[int] = None,
                   tvk: str = "", name: str = "") -> List[dict]:
    """The records in one 10 km square, in the form the Mapping tab's SquareRecordsDialog takes
    (the same fetch and the same square rule as the map)."""
    from ...services import map_square_service as squares_svc
    year = year or date.today().year
    res = ms.fetch(_selection(mode, tvk, name), SOURCES, _filters(mode, year), db_path=db_path)
    return squares_svc.records_in_square(res.records, label, gs.HECTAD)


# ---------------------------------------------------------------- last 10 new species

def short_date(value) -> str:
    """'7 Sep' for an ISO date; the text as it is when it is not one."""
    text = str(value or "")[:10]
    try:
        d = datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return text
    return f"{d.day} {d:%b}"


def group_name(row: dict) -> str:
    """The group in plain words: the suite's display label for the record's taxon group
    ('Beetles (Coleoptera)' -> 'Beetles'), else its order."""
    grp = group_for_record(row.get("taxon_group"), row.get("order_name"), row.get("family"))
    label = group_label(grp).split(" (")[0].strip() if grp else ""
    return label or (row.get("order_name") or "")


def last_new_species(obs_repo, limit: int = 10) -> List[dict]:
    """The `limit` species whose first record is the most recent, newest first (ties: the
    same date by name). The set is get_new_species_first_records's (the old Recent New Species
    panel's); more are read than shown so a tie at the cut-off is settled by name, not by
    whatever order the database returned them in."""
    rows = obs_repo.get_new_species_first_records(limit=max(limit * 10, 100))
    rows = sorted(rows, key=lambda r: (r.get("species_name") or ""))
    rows = sorted(rows, key=lambda r: str(r.get("date") or ""), reverse=True)[:limit]
    return [{"species_name": r.get("species_name") or "", "common_name": r.get("common_name") or "",
             "species_tvk": r.get("species_tvk") or "", "date": r.get("date") or "",
             "short_date": short_date(r.get("date")), "site_name": r.get("site_name") or "",
             "grid_ref": r.get("grid_ref") or "", "group": group_name(r)} for r in rows]


# ---------------------------------------------------------------- Personal year list

PLACEABLE_DATE_TYPES = ("", "D", "O")        # a day or a month; year (Y, YY) and ranges (DD, OO) are not


def _year_rows(conn, db_path, year: int) -> list:
    """(species key, date, date type) of the Personal records the Quick Stats card counts for
    `year`: the card's own WHERE (ObservationRepository.count_unique_species_by_year)."""
    key = species_key_expr("observations", db=db_path)
    return conn.execute(
        f"SELECT DISTINCT {key}, date, COALESCE(date_type, 'D') FROM observations "
        "WHERE species_tvk IS NOT NULL AND strftime('%Y', date) = ? AND record_type = 'Personal'"
        f"{counted_clause('observations', db=db_path)}", (str(year),)).fetchall()


def _first_dates(rows) -> Tuple[Dict[str, Tuple[int, int]], int]:
    """({species: (month, day) of its first usable record}, species with none): a record is
    placed in a month only when its date is a day or a month (PLACEABLE_DATE_TYPES); a month
    date is placed at the 1st."""
    first: Dict[str, Tuple[int, int]] = {}
    seen = set()
    for key, d, dtype in rows:
        seen.add(key)
        text = str(d or "")[:10]
        if str(dtype).upper() not in PLACEABLE_DATE_TYPES or len(text) < 7:
            continue
        try:
            md = (int(text[5:7]), int(text[8:10]) if len(text) >= 10 else 1)
        except ValueError:
            continue
        if 1 <= md[0] <= 12 and (key not in first or md < first[key]):
            first[key] = md
    return first, len(seen) - len(first)


def _monthly(first: Dict[str, Tuple[int, int]], unplaced: int, last_month: int) -> List[Optional[int]]:
    """Cumulative species by the end of each month 1..12 (None after `last_month`). The species
    with no usable month are added to the last point drawn, so that point is the year's total."""
    out: List[Optional[int]] = []
    for m in range(1, 13):
        n = sum(1 for md in first.values() if md[0] <= m)
        if m == last_month:                    # also those first recorded after it (a future date)
            n += unplaced + sum(1 for md in first.values() if md[0] > m)
        out.append(n if m <= last_month else None)
    return out


def year_list(db_path, year: Optional[int] = None, today: Optional[date] = None) -> dict:
    """The Personal year list, month by month, for `year` (default this year) and the year before.

    {"year", "this": [12 cumulative counts, None after the current month], "last": [12],
     "total": species this year, "last_by_date": last year's count at today's day of the year,
     "best": (month, new species) or None, "unplaced": species with no usable month this year,
     "unplaced_last": the same last year}.

    Counting is the Personal Quick Stats card's (see the module docstring), so the last drawn
    point of "this" equals the card's "This Year Species". A species is on the list from its first
    record placed in a month (a day or a month date). Species whose records are all dated by year
    (or a range) cannot be placed in a month: they are added to the last point only (the current
    month this year, December last year), and counted in "unplaced". A species first recorded
    after the current month (a future date) is likewise counted in the last point."""
    today = today or date.today()
    year = year or today.year
    last_month = today.month if year == today.year else 12
    conn = connect_ro(db_path)
    try:
        this_rows, last_rows = _year_rows(conn, db_path, year), _year_rows(conn, db_path, year - 1)
    finally:
        conn.close()
    first, unplaced = _first_dates(this_rows)
    first_last, unplaced_last = _first_dates(last_rows)
    this = _monthly(first, unplaced, last_month)
    placed = [sum(1 for md in first.values() if md[0] <= m) for m in range(1, last_month + 1)]
    gains = [n - (placed[i - 1] if i else 0) for i, n in enumerate(placed)]
    best = None
    if gains and max(gains) > 0:
        best = (gains.index(max(gains)) + 1, max(gains))
    cutoff = (today.month, today.day)
    return {"year": year, "this": this, "last": _monthly(first_last, unplaced_last, 12),
            "total": len({r[0] for r in this_rows}),
            "last_by_date": sum(1 for md in first_last.values() if md <= cutoff),
            "best": best, "unplaced": unplaced, "unplaced_last": unplaced_last}
