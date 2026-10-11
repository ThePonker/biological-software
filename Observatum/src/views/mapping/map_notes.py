"""What the Mapping tab says about its map, in words (no Qt): what was left off (the line in
the map's corner) and what was held back or folded together (the subtitle and the atlas PNG).

Round 2 (10 Oct 2026): 2 km tetrad grid refs held back unless switched on (decision 10);
"embargoed records included" always said when the box is ticked (decision 13).
"""
from typing import List, Tuple

from shared.maps.grid_squares import is_tetrad_ref


def hold_tetrads(records: List[dict], include: bool) -> Tuple[List[dict], int]:
    """(records to square, tetrad refs held back). Decision 10: a 2 km tetrad grid ref
    (SP46Q) is left off unless `include`; then squares_for maps it on hectad and tetrad grids
    and counts it too coarse for a 1 km grid. A held record gets square None, so no square's
    record list shows it."""
    if include:
        return records, 0
    out, held = [], 0
    for r in records:
        if is_tetrad_ref(r.get("grid_ref")):
            r["square"] = None
            held += 1
        else:
            out.append(r)
    return out, held


def left_out_text(total: int, coarse: int, unparsed: int, tetrads: int, grid: str) -> str:
    """Say what the map leaves out, so an empty or thin map explains itself (grid: 'hectad')."""
    if not total:
        return "No records with a grid reference match these filters."
    parts = []
    if coarse:
        parts.append(f"{coarse:,} record{'s' if coarse != 1 else ''} too coarse for a {grid}")
    if unparsed:
        parts.append(f"{unparsed:,} not on the GB grid (Irish, Channel Islands or lat/long)")
    if tetrads:
        parts.append(f"{tetrads:,} with a 2 km (tetrad) grid ref (tick \"Include 2 km (tetrad) "
                     f"grid refs\" to map {'them' if tetrads != 1 else 'it'})")
    return ("Not mapped: " + "; ".join(parts) + ".") if parts else ""


def map_note(result, filters) -> str:
    """What the map holds back or folds together (the subtitle and the PNG). `filters`: the
    MapFilters the map was made with."""
    if result is None:
        return ""
    parts = []
    n = result.embargoed
    if filters is not None and filters.include_embargoed:
        parts.append(f"includes {n:,} embargoed record{'s' if n != 1 else ''}" if n
                     else "embargoed records included (none here)")
    elif n:
        parts.append(f"{n:,} embargoed not shown")
    if result.merged:
        parts.append(f"{result.merged:,} duplicate records shown once")
    return ", ".join(parts)
