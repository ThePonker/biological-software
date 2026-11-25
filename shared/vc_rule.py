"""vc_rule -- THE rule for a record's vice-county from its grid reference (R4, 24 Nov 2026).

The rule used to live only in Data Entry's grid (StagingTableModel._derive_vc). Rows made by
photo intake and by the workbook loader got no VC, and with no VC service a changed grid ref
kept the old VC. Every route -- the grid, photo intake, the workbook loader and the commit's
re-check -- now asks here. Shared (not DataEntry) because shared/photo_intake.py and the
scripts use it too and neither may import the grid. No Qt.

    vc_for_grid_ref(vc_service, grid_ref)
        -> None             nothing can be checked (no VC service): leave the VC as it is
        -> (None, None)     no grid ref, or one the service cannot place: there is no VC
        -> (number, name)   the vice-county

The grid ref is the authority: a cleared or unreadable ref clears the VC (DE2: 'XX123' kept
the previous VC41). A cleared ref clears it even with no service, as nothing needs checking.
"""
from __future__ import annotations

from typing import Optional, Tuple


def vc_for_grid_ref(vc_service, grid_ref) -> Optional[Tuple[Optional[int], Optional[str]]]:
    ref = str(grid_ref or "").strip()
    if not ref:
        return (None, None)
    if not vc_service:
        return None
    try:
        got = vc_service.get_vc_from_grid_ref(ref)
    except Exception:
        got = None
    if not got or got[0] is None:
        return (None, None)
    return (got[0], got[1])


def vc_fields(vc_service, grid_ref) -> dict:
    """The staging columns for the rule: {'vc_number', 'vice_county'}, or {} when nothing can
    be checked (leave the row's VC alone)."""
    got = vc_for_grid_ref(vc_service, grid_ref)
    if got is None:
        return {}
    return {"vc_number": got[0], "vice_county": got[1]}
