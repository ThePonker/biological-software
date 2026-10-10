"""Records -> squares for the Mapping tab's native map, and its time-period bands (backlog
H3, H4; item 4, 10 Oct 2026). No database access: the records come from map_selection.fetch
(read-only), which also decides the sources, embargo and the selection.

Squares come from shared/maps/grid_squares.py, which goes through shared/osgb.py -- so a
tetrad here is the same tetrad everywhere else.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional

from shared.maps import grid_squares as gs
from shared.species_rank import name_tier

# ---------------------------------------------------------------- time-period bands

UNDATED = "undated"           # MAP5: a square with no dated record is its own class
BAND_PRESETS = {
    "default": [{"name": "historical", "label": "Pre-2000", "max_year": 1999},
                {"name": "recent", "label": "2000–2019", "max_year": 2019},
                {"name": "current", "label": "2020+", "max_year": 9999}],
    "brc": [{"name": "historical", "label": "Pre-1970", "max_year": 1969},
            {"name": "recent", "label": "1970–1999", "max_year": 1999},
            {"name": "current", "label": "2000+", "max_year": 9999}],
}
BAND_PRESET_LABELS = {"default": "Pre-2000 / 2000–19 / 2020+",
                      "brc": "Pre-1970 / 1970–99 / 2000+"}


def year_to_band(year: Optional[int], bands: List[dict]) -> str:
    """The band name for a year; None (undated) -> 'undated', never the newest band."""
    if year is None:
        return UNDATED
    for band in sorted(bands, key=lambda b: b["max_year"]):
        if year <= band["max_year"]:
            return band["name"]
    return bands[-1]["name"]


def band_labels(bands: List[dict]) -> Dict[str, str]:
    """{band name: label}, oldest first, then 'Undated'."""
    out = {b["name"]: b["label"] for b in sorted(bands, key=lambda b: b["max_year"])}
    out[UNDATED] = "Undated"
    return out


# ---------------------------------------------------------------- squares

def squares_for(records: List[dict], size: int,
                year_to_band: Callable[[Optional[int]], str]):
    """(squares, too_coarse, unparsed): label -> {count, species, first_year, last_year,
    undated, years, band, chips, tip}. Each record gets its square in r['square'] (None if left out).

    `species` is the number of distinct species among the square's records (r['species'],
    see map_taxa.species_key) -- the richness style. `chips` lists the chosen taxa (indexes
    into the selection, from r['chips']) with records in the square -- the By taxon style. A square's band is that of its most
    recent dated record; a square with only undated records is 'undated' (MAP5).
    """
    squares: Dict[str, dict] = {}
    spp: Dict[str, set] = {}
    chips: Dict[str, set] = {}
    where: Dict[str, object] = {}                  # grid ref -> label, or 'coarse' / None
    coarse = unparsed = 0
    for r in records:
        ref = r.get("grid_ref")
        if ref not in where:
            p = gs.gridref_to_en(ref)
            if not p:
                where[ref] = None
            elif p[2] > size:
                where[ref] = "coarse"
            else:
                where[ref] = gs.square_for_point(p[0], p[1], size)
        label = where[ref]
        if label == "coarse":
            coarse += 1
            r["square"] = None
            continue
        if not label:
            unparsed += 1
            r["square"] = None
            continue
        r["square"] = label
        sq = squares.get(label)
        if sq is None:
            sq = squares[label] = {"count": 0, "first_year": None, "last_year": None,
                                   "undated": 0}
            spp[label] = set()
            chips[label] = set()
        sq["count"] += 1
        y = r.get("year")
        if y is None:
            sq["undated"] += 1
        else:
            if sq["first_year"] is None or y < sq["first_year"]:
                sq["first_year"] = y
            if sq["last_year"] is None or y > sq["last_year"]:
                sq["last_year"] = y
        if r.get("species"):
            spp[label].add(r["species"])
        chips[label].update(r.get("chips") or ())
    for label, sq in squares.items():
        a, b = sq["first_year"], sq["last_year"]
        sq["species"] = len(spp[label])
        sq["chips"] = sorted(chips[label])
        sq["years"] = "" if a is None else (str(a) if a == b else f"{a}–{b}")
        sq["band"] = year_to_band(b)
        n, k = sq["count"], sq["species"]
        when = sq["years"] + (" + undated" if sq["undated"] and sq["years"] else
                              "undated" if sq["undated"] else "")
        sq["tip"] = (f"{label}: {n:,} record{'s' if n != 1 else ''}, {k} species"
                     + (f" ({when})" if when else ""))
    return squares, coarse, unparsed


def records_in_square(records: List[dict], label: str, size: int) -> List[dict]:
    """The records that fall in one square (by the same rule the map squares them)."""
    return [r for r in records
            if (r["square"] if "square" in r else gs.square_for_ref(r["grid_ref"], size)) == label]


def rank_species(text: str, results: List[dict]) -> List[dict]:
    """Scientific-name prefix hits first (the suite's one ranking, species_rank.name_tier),
    then common names that start with the text, then by number of records."""
    t = (text or "").strip().lower()

    def key(r):
        common = (r.get("common_name") or "").lower()
        return (name_tier(text, r), 0 if t and common.startswith(t) else 1, -r.get("records", 0),
                r.get("scientific_name") or "")
    return sorted(results, key=key)
