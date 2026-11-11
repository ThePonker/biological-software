"""What the redesigned Home tab (Round 19) reads: the map's squares, the last ten new species
and the notable records. No Qt. Read-only: nothing here writes to a database.

Every rule is imported, not copied:
  * the map's records come from the Mapping tab's own query builder (services/map_selection:
    build_query, counting_exclusions, fetch), grouped by grid reference, then squared by
    shared/maps/grid_squares (hectad = 10 km);
  * "new species" is ObservationRepository.get_new_species_first_records (the panel it replaces);
  * "notable" is shared.repositories.codex_repository.notable_status (NOTABLE_STATUS_ORDER).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List, Optional

from shared.db_open import connect_ro
from shared.maps import grid_squares as gs
from shared.repositories.codex_repository import NOTABLE_STATUS_ORDER, notable_status
from shared.taxon_groups import group_for_record, group_label

from ...services import map_selection as ms

THIS_YEAR, ALL_YEARS, SELECTED = "year", "all", "species"
SOURCES = ["personal", "commercial"]          # "your records": Personal + Commercial observations
CLASSES = ((1, 9, "1–9"), (10, 99, "10–99"), (100, None, "100+ records"))

NEWEST, HIGHEST = "newest", "highest"
NOTABLE_LIST_MAX = 200                         # rows drawn; the link counts them all


def record_class(n: int) -> int:
    """0, 1 or 2: the number of records in a square as CLASSES (1-9, 10-99, 100+)."""
    for i, (lo, hi, _label) in enumerate(CLASSES):
        if n >= lo and (hi is None or n <= hi):
            return i
    return 0


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
    """{10 km square: {count, class}} for your Personal + Commercial observations: this year,
    all years, or one species (mode SELECTED, by TVK, old names included as in Mapping). One
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
    for sq in squares.values():
        sq["class"] = record_class(sq["count"])
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


# ---------------------------------------------------------------- notable records

def notable_records(db_path, year: Optional[int] = None, personal_only: bool = False,
                    sort: str = NEWEST, codex=None) -> dict:
    """{"total": records, "species": n, "ids": [every record's id], "rows": [one per species]}: your records of the year of notable species (notable_status:
    NS or rarer, Red List VU/EN/CR; not NT), newest first or highest status first. Each row:
    id, status, species_name, common_name, tvk, site_name, grid_ref, date, short_date (its latest record), n.
    `codex`: a CodexRepository (default: a new one, closed afterwards)."""
    year = year or date.today().year
    srcs = ["personal"] if personal_only else SOURCES
    where, params = ms.build_query("observations", [], srcs, _filters(THIS_YEAR, year), None,
                                   counting=ms.counting_exclusions(db_path))
    conn = connect_ro(db_path)
    try:
        recs = conn.execute(
            "SELECT id, species_name, common_name, species_tvk, site_name, grid_ref, date "
            f"FROM observations WHERE COALESCE(species_tvk, '') <> '' AND {where}",
            params).fetchall()
    finally:
        conn.close()
    tvks = sorted({r[3] for r in recs})
    own = codex is None
    if own:
        from shared.repositories.codex_repository import CodexRepository
        codex = CodexRepository()
    try:
        status = {t: notable_status(s) for t, s in codex.get_statuses_batch(tvks).items()} \
            if tvks else {}
    finally:
        if own:
            codex.close()
    rows = [{"id": r[0], "species_name": r[1] or "", "common_name": r[2] or "", "tvk": r[3],
             "site_name": r[4] or "", "grid_ref": r[5] or "", "date": r[6] or "",
             "short_date": short_date(r[6]), "status": status[r[3]]}
            for r in recs if status.get(r[3])]
    rows.sort(key=lambda r: r["species_name"])
    rows.sort(key=lambda r: str(r["date"]), reverse=True)
    ids = [r["id"] for r in rows]
    # One row per species: its latest record, with how many records it has this year (R19 review:
    # a species recorded several times filled the list with repeats).
    per, seen = {}, []
    for r in rows:
        if r["tvk"] in per:
            per[r["tvk"]]["n"] += 1
        else:
            per[r["tvk"]] = dict(r, n=1)
            seen.append(per[r["tvk"]])
    rows = seen
    if sort == HIGHEST:
        rank = {v: i for i, v in enumerate(NOTABLE_STATUS_ORDER)}
        rows.sort(key=lambda r: rank[r["status"]])         # stable: newest first within a status
    return {"total": len(ids), "species": len(rows), "ids": ids, "rows": rows[:NOTABLE_LIST_MAX]}
