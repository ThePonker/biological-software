"""Records for the Mapping tab's native map: fetch, square up, search (backlog H3, H4, H6).

Read-only throughout (connect_ro). Squares come from shared/maps/grid_squares.py, which
goes through shared/osgb.py -- so a tetrad here is the same tetrad everywhere else.

The record sources match MapDataService: "personal" = observations + specimens,
"scheme" = recording_scheme, "all" = the three. A species is matched by its TVK when one
is known (so records under an older name of the same taxon are included), else by name.
"""
from __future__ import annotations

import sqlite3
from typing import Callable, Dict, List, Optional

import paths
from shared.db_open import connect_ro
from shared.maps import grid_squares as gs
from shared.species_rank import name_tier

# table -> (source label, date column, person column, extra column)
_TABLES = {
    "observations": ("Observation", "date", "recorder", "individual_count"),
    "specimens": ("Specimen", "date_collected", "collector", "specimen_code"),
    "recording_scheme": ("Recording scheme", "date", "recorder", "quantity"),
}
_SOURCES = {
    "personal": ("observations", "specimens"),
    "scheme": ("recording_scheme",),
    "all": ("observations", "specimens", "recording_scheme"),
}


def _year(date_str) -> Optional[int]:
    try:
        y = int(str(date_str)[:4])
        return y if 1000 <= y <= 2999 else None
    except (TypeError, ValueError):
        return None


def fetch_records(species: Optional[dict], data_source: str = "personal",
                  date_from: Optional[str] = None, date_to: Optional[str] = None,
                  db_path=None) -> List[dict]:
    """Every record with a grid reference for the species (None = all species)."""
    out: List[dict] = []
    tvk = (species or {}).get("tvk")
    name = (species or {}).get("scientific_name")
    conn = connect_ro(db_path or paths.OBSERVATUM_DB)
    try:
        for table in _SOURCES.get(data_source, _SOURCES["personal"]):
            label, dcol, pcol, xcol = _TABLES[table]
            where, params = ["grid_ref IS NOT NULL", "grid_ref != ''"], []
            if tvk:
                where.append("species_tvk = ?"); params.append(tvk)
            elif name:
                where.append("species_name = ?"); params.append(name)
            if date_from:
                where.append(f"{dcol} >= ?"); params.append(date_from)
            if date_to:
                where.append(f"{dcol} <= ?")
                params.append(date_to + "-12-31" if len(date_to) == 4 else date_to)
            sql = (f"SELECT id, species_name, common_name, grid_ref, {dcol}, site_name, "
                   f"{pcol}, {xcol} FROM {table} WHERE " + " AND ".join(where))
            try:
                rows = conn.execute(sql, params).fetchall()
            except sqlite3.OperationalError as e:
                print(f"[MapSquareService] {table}: {e}")
                continue
            for rid, sp, common, gr, d, site, person, extra in rows:
                out.append({"source": label, "table": table, "id": rid, "species_name": sp,
                            "common_name": common or "", "grid_ref": gr, "date": d or "",
                            "year": _year(d), "site_name": site or "", "person": person or "",
                            "extra": "" if extra is None else str(extra)})
    finally:
        conn.close()
    return out


def squares_for(records: List[dict], size: int,
                year_to_band: Callable[[Optional[int]], str]):
    """(squares, too_coarse, unparsed): label -> {count, first_year, last_year, years, band}.

    A square's band is that of its most recent record, as MapDataService does.
    """
    squares, coarse, unparsed = gs.aggregate(((r["grid_ref"], r["year"]) for r in records), size)
    for sq in squares.values():
        a, b = sq["first_year"], sq["last_year"]
        sq["years"] = "" if a is None else (str(a) if a == b else f"{a}–{b}")
        sq["band"] = year_to_band(b)
    return squares, coarse, unparsed


def records_in_square(records: List[dict], label: str, size: int) -> List[dict]:
    """The records that fall in one square (by the same rule the map squares them)."""
    return [r for r in records if gs.square_for_ref(r["grid_ref"], size) == label]


# ---------------------------------------------------------------- species search (H6)

def _uksi_tvks_by_common_name(words: List[str], uksi_path, limit: int = 300) -> Dict[str, str]:
    """TVK -> preferred-looking common name, for UKSI common names containing every word."""
    if not words:
        return {}
    try:
        conn = connect_ro(uksi_path)
    except sqlite3.Error:
        return {}
    try:
        where = " AND ".join("common_name LIKE ?" for _ in words)
        rows = conn.execute(
            f"SELECT tvk, common_name, preferred FROM common_names WHERE {where} "
            f"ORDER BY preferred DESC LIMIT {int(limit)}", [f"%{w}%" for w in words]).fetchall()
    except sqlite3.Error:
        rows = []
    finally:
        conn.close()
    out: Dict[str, str] = {}
    for tvk, common, _pref in rows:
        out.setdefault(tvk, common)
    return out


def search_species(text: str, data_source: str = "all", limit: int = 10,
                   db_path=None, uksi_path=None) -> List[dict]:
    """Recorded species matching a scientific or common name, best match first.

    Every typed word must appear ("rut mac" finds Rutpela maculata; "wasp beetle" finds
    Clytus arietis), in the record's own names or in any UKSI common name for its TVK.
    Returns [{scientific_name, tvk, common_name, records}] grouped by TVK.
    """
    words = [w for w in (text or "").lower().split() if w]
    if not words:
        return []
    uksi = _uksi_tvks_by_common_name(words, uksi_path or paths.UKSI_DB)
    found: Dict[str, dict] = {}
    conn = connect_ro(db_path or paths.OBSERVATUM_DB)
    try:
        for table in _SOURCES.get(data_source, _SOURCES["all"]):
            hay = "lower(coalesce(species_name,'') || ' ' || coalesce(common_name,''))"
            cond = "(" + " AND ".join(f"{hay} LIKE ?" for _ in words) + ")"
            params = [f"%{w}%" for w in words]
            if uksi:
                cond += f" OR species_tvk IN ({','.join('?' * len(uksi))})"
                params += list(uksi)
            sql = (f"SELECT species_tvk, species_name, common_name, COUNT(*) FROM {table} "
                   f"WHERE {cond} GROUP BY species_tvk, species_name, common_name")
            try:
                rows = conn.execute(sql, params).fetchall()
            except sqlite3.OperationalError:
                continue
            for tvk, name, common, n in rows:
                key = tvk or f"name:{name}"
                hit = found.setdefault(key, {"tvk": tvk, "names": {}, "common_name": "",
                                             "records": 0})
                hit["records"] += n
                hit["names"][name] = hit["names"].get(name, 0) + n
                if common and not hit["common_name"]:
                    hit["common_name"] = common
    finally:
        conn.close()
    results = []
    for hit in found.values():
        name = max(hit["names"].items(), key=lambda kv: kv[1])[0]
        common = hit["common_name"] or uksi.get(hit["tvk"] or "", "")
        results.append({"scientific_name": name, "tvk": hit["tvk"], "common_name": common,
                        "records": hit["records"]})
    return rank_species(text, results)[:limit]


def rank_species(text: str, results: List[dict]) -> List[dict]:
    """Scientific-name prefix hits first (the suite's one ranking, species_rank.name_tier),
    then common names that start with the text, then by number of records."""
    t = (text or "").strip().lower()

    def key(r):
        common = (r.get("common_name") or "").lower()
        return (name_tier(text, r), 0 if t and common.startswith(t) else 1, -r.get("records", 0),
                r.get("scientific_name") or "")
    return sorted(results, key=key)
